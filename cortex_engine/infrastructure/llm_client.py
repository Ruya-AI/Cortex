from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from enum import Enum

from cortex_engine.core.schemas import LLMResponse

logger = logging.getLogger(__name__)

# Cost per million tokens (approximate)
MODEL_COSTS = {
    "claude-opus-4-6": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
    "claude-haiku-4-20250514": {"input": 0.80, "output": 4.0},
}


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class LLMClient:
    """Abstract interface for LLM calls."""

    def call(self, system_prompt: str, user_message: str,
             output_schema: dict | None = None, model: str | None = None) -> LLMResponse:
        raise NotImplementedError

    @property
    def total_cost(self) -> float:
        return 0.0

    @property
    def total_tokens(self) -> tuple[int, int]:
        return (0, 0)

    @property
    def call_count(self) -> int:
        return 0


class AnthropicLLMClient(LLMClient):
    def __init__(
        self,
        primary_model: str = "claude-sonnet-4-20250514",
        fallback_models: list[str] | None = None,
        max_retries: int = 3,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_cooldown: float = 60.0,
        audit_logger_fn=None,
        provider: str | None = None,
        api_key: str | None = None,
        vertex_project_id: str | None = None,
        vertex_region: str | None = None,
    ):
        self._primary_model = primary_model
        self._fallback_models = fallback_models or []
        self._max_retries = max_retries
        self._cb_threshold = circuit_breaker_threshold
        self._cb_cooldown = circuit_breaker_cooldown
        self._audit_logger_fn = audit_logger_fn

        # Circuit breaker state
        self._cb_state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._cb_opened_at = 0.0

        # Tracking
        self._total_cost = 0.0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._call_count = 0

        # LLM provider config (explicit params take priority over env vars)
        self._provider = provider
        self._api_key = api_key
        self._vertex_project_id = vertex_project_id
        self._vertex_region = vertex_region

        # Initialize anthropic client lazily
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic
            import os
            provider = self._provider or ("vertex_ai" if os.environ.get("CLAUDE_CODE_USE_VERTEX") else "anthropic")
            project_id = self._vertex_project_id or os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID", "")
            region = self._vertex_region or os.environ.get("CLOUD_ML_REGION", "global")
            api_key = self._api_key or os.environ.get("ANTHROPIC_API_KEY", "")

            if provider == "vertex_ai" and project_id:
                self._client = anthropic.AnthropicVertex(
                    project_id=project_id,
                    region=region,
                    max_retries=0,
                )
                logger.info("Using Vertex AI (project=%s, region=%s)", project_id, region)
            else:
                kwargs: dict = {"max_retries": 0, "timeout": 120.0}
                if api_key:
                    kwargs["api_key"] = api_key
                self._client = anthropic.Anthropic(**kwargs)
                logger.info("Using direct Anthropic API")
        return self._client

    @property
    def total_cost(self) -> float:
        return self._total_cost

    @property
    def total_tokens(self) -> tuple[int, int]:
        return (self._total_input_tokens, self._total_output_tokens)

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def primary_model(self) -> str:
        return self._primary_model

    def call(self, system_prompt: str, user_message: str,
             output_schema: dict | None = None, model: str | None = None) -> LLMResponse:
        # Check circuit breaker
        if self._cb_state == CircuitState.OPEN:
            if time.time() - self._cb_opened_at > self._cb_cooldown:
                self._cb_state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker half-open — testing with one call")
            else:
                return LLMResponse(success=False, error="Circuit breaker open")

        # Build model chain: specified model or primary, then fallbacks
        models_to_try = []
        if model:
            models_to_try.append(model)
        else:
            models_to_try.append(self._primary_model)
        models_to_try.extend(self._fallback_models)
        # Remove duplicates preserving order
        seen: set[str] = set()
        unique_models: list[str] = []
        for m in models_to_try:
            if m not in seen:
                seen.add(m)
                unique_models.append(m)

        last_error = ""
        for m in unique_models:
            response = self._try_model(m, system_prompt, user_message, output_schema)
            if response.success:
                self._on_success()
                return response
            last_error = response.error or "Unknown error"
            logger.warning("Model %s failed: %s", m, last_error)

        # All models failed
        self._on_failure()
        return LLMResponse(success=False, error=f"All models failed. Last error: {last_error}")

    def _try_model(self, model: str, system_prompt: str, user_message: str,
                   output_schema: dict | None) -> LLMResponse:
        import anthropic

        last_error = ""

        for attempt in range(self._max_retries):
            try:
                start = time.time()
                client = self._get_client()

                kwargs = {
                    "model": model,
                    "max_tokens": 8192,
                    "temperature": 0,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_message}],
                }

                response = client.messages.create(**kwargs)
                duration_ms = int((time.time() - start) * 1000)

                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                cost = self._compute_cost(model, input_tokens, output_tokens)

                self._total_input_tokens += input_tokens
                self._total_output_tokens += output_tokens
                self._total_cost += cost
                self._call_count += 1

                content = response.content[0].text if response.content else ""

                # Try to parse as JSON if schema expected
                parsed_content = content
                if output_schema and isinstance(content, str):
                    try:
                        parsed_content = json.loads(content)
                    except json.JSONDecodeError:
                        # Try to extract JSON from markdown code blocks
                        if "```json" in content:
                            json_str = content.split("```json")[-1].split("```")[0].strip()
                            try:
                                parsed_content = json.loads(json_str)
                            except json.JSONDecodeError:
                                pass
                        elif "```" in content:
                            json_str = content.split("```")[1].split("```")[0].strip()
                            try:
                                parsed_content = json.loads(json_str)
                            except json.JSONDecodeError:
                                pass

                # Log audit
                if self._audit_logger_fn:
                    prompt_hash = hashlib.sha256((system_prompt + user_message).encode()).hexdigest()
                    self._audit_logger_fn(model, prompt_hash, input_tokens, output_tokens, cost, duration_ms, "success")

                return LLMResponse(
                    content=parsed_content,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost,
                    success=True,
                )

            except anthropic.AuthenticationError as e:
                # Permanent error -- don't retry
                logger.error("Authentication failed: %s", e)
                return LLMResponse(success=False, error=f"Authentication failed: {e}", model=model)
            except anthropic.BadRequestError as e:
                # Permanent error -- don't retry
                logger.error("Bad request: %s", e)
                return LLMResponse(success=False, error=f"Bad request: {e}", model=model)
            except (anthropic.RateLimitError, anthropic.APITimeoutError, anthropic.APIConnectionError) as e:
                last_error = str(e)
                logger.debug("LLM call attempt %d/%d (transient): %s", attempt + 1, self._max_retries, last_error)

                # Log audit for failure
                if self._audit_logger_fn:
                    prompt_hash = hashlib.sha256((system_prompt + user_message).encode()).hexdigest()
                    self._audit_logger_fn(model, prompt_hash, 0, 0, 0.0, 0, f"error: {last_error[:100]}")

                if attempt < self._max_retries - 1:
                    delay = min(1.0 * (2 ** attempt), 8.0) + random.uniform(0, 0.5)
                    time.sleep(delay)
            except Exception as e:
                last_error = str(e)
                logger.debug("LLM call attempt %d/%d failed: %s", attempt + 1, self._max_retries, last_error)

                # Log audit for failure
                if self._audit_logger_fn:
                    prompt_hash = hashlib.sha256((system_prompt + user_message).encode()).hexdigest()
                    self._audit_logger_fn(model, prompt_hash, 0, 0, 0.0, 0, f"error: {last_error[:100]}")

                if attempt < self._max_retries - 1:
                    delay = min(1.0 * (2 ** attempt), 8.0) + random.uniform(0, 0.5)
                    time.sleep(delay)

        return LLMResponse(success=False, error=last_error, model=model)

    def _compute_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        costs = MODEL_COSTS.get(model, {"input": 3.0, "output": 15.0})
        return (input_tokens * costs["input"] + output_tokens * costs["output"]) / 1_000_000

    def _on_success(self) -> None:
        if self._cb_state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker closed — call succeeded")
        self._cb_state = CircuitState.CLOSED
        self._consecutive_failures = 0

    def _on_failure(self) -> None:
        self._consecutive_failures += 1
        if self._cb_state == CircuitState.HALF_OPEN:
            self._cb_state = CircuitState.OPEN
            self._cb_opened_at = time.time()
            logger.error("Circuit breaker re-opened after half-open test failure")
        elif self._consecutive_failures >= self._cb_threshold:
            self._cb_state = CircuitState.OPEN
            self._cb_opened_at = time.time()
            logger.error("Circuit breaker opened after %d consecutive failures", self._consecutive_failures)
