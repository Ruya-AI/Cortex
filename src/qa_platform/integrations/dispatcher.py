from __future__ import annotations

import logging

from qa_platform.core.finding import Finding
from qa_platform.core.schemas import IntegrationResult, QualityGateResult

logger = logging.getLogger(__name__)


class IntegrationTarget:
    """Abstract base for integration targets."""

    name: str = "base"

    def is_configured(self) -> bool:
        return False

    def dispatch(
        self,
        findings: list[Finding],
        gate_result: QualityGateResult,
        scan_metadata: dict,
        config: dict,
    ) -> IntegrationResult:
        return IntegrationResult(target_name=self.name, status="skipped")


class IntegrationDispatcher:
    """Fan-out dispatcher that sends findings to every configured target."""

    def __init__(self, targets: list[IntegrationTarget] | None = None) -> None:
        self._targets: list[IntegrationTarget] = targets or []

    def register(self, target: IntegrationTarget) -> None:
        self._targets.append(target)

    def dispatch(
        self,
        findings: list[Finding],
        gate_result: QualityGateResult,
        scan_metadata: dict,
        config: dict,
    ) -> list[IntegrationResult]:
        results: list[IntegrationResult] = []
        for target in self._targets:
            if not target.is_configured():
                results.append(
                    IntegrationResult(target_name=target.name, status="skipped")
                )
                continue
            try:
                result = target.dispatch(
                    findings, gate_result, scan_metadata, config
                )
                results.append(result)
            except Exception as e:
                logger.error("Integration %s failed: %s", target.name, e)
                results.append(
                    IntegrationResult(
                        target_name=target.name,
                        status="error",
                        error_message=str(e),
                    )
                )
        return results
