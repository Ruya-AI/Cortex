"""Tests for AnthropicLLMClient — config injection and provider selection."""
from cortex_engine.infrastructure.llm_client import AnthropicLLMClient, CircuitState


class TestLLMClientConfig:
    def test_default_model(self):
        client = AnthropicLLMClient()
        assert client.primary_model == "claude-sonnet-4-20250514"

    def test_custom_model(self):
        client = AnthropicLLMClient(primary_model="claude-opus-4-6")
        assert client.primary_model == "claude-opus-4-6"

    def test_fallback_models(self):
        client = AnthropicLLMClient(fallback_models=["claude-sonnet-4-6"])
        assert client._fallback_models == ["claude-sonnet-4-6"]

    def test_provider_stored(self):
        client = AnthropicLLMClient(provider="vertex_ai", vertex_project_id="test-proj")
        assert client._provider == "vertex_ai"
        assert client._vertex_project_id == "test-proj"

    def test_api_key_stored(self):
        client = AnthropicLLMClient(provider="anthropic", api_key="sk-test")
        assert client._api_key == "sk-test"

    def test_circuit_breaker_initial_state(self):
        client = AnthropicLLMClient()
        assert client._cb_state == CircuitState.CLOSED
        assert client._consecutive_failures == 0

    def test_tracking_initial(self):
        client = AnthropicLLMClient()
        assert client.total_cost == 0.0
        assert client.total_tokens == (0, 0)
        assert client.call_count == 0

    def test_max_retries(self):
        client = AnthropicLLMClient(max_retries=5)
        assert client._max_retries == 5

    def test_no_env_vars_needed_with_explicit_config(self):
        client = AnthropicLLMClient(
            provider="vertex_ai",
            vertex_project_id="my-project",
            vertex_region="us-east5",
            primary_model="claude-opus-4-6",
        )
        assert client._provider == "vertex_ai"
        assert client._vertex_project_id == "my-project"
        assert client._vertex_region == "us-east5"
        assert client._client is None
