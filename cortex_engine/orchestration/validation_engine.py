from __future__ import annotations

import logging
from pathlib import Path

from cortex_engine.core.finding import Finding, ValidationStatus
from cortex_engine.core.schemas import ValidationResult

logger = logging.getLogger(__name__)


class ValidationEngine:
    def __init__(self, validator_agent=None, batch_size: int = 15):
        self._validator = validator_agent
        self._batch_size = batch_size

    def validate(self, findings: list[Finding], repo_path: Path) -> ValidationResult:
        if not self._validator:
            logger.warning("No validator agent configured — all findings marked UNVALIDATED")
            for f in findings:
                f.validation_status = ValidationStatus.UNVALIDATED
                f.validation_reasoning = "No validator agent configured"
            return ValidationResult(validated_findings=findings)

        validated = []
        suppressed = []

        # Process in batches
        for i in range(0, len(findings), self._batch_size):
            batch = findings[i:i + self._batch_size]
            try:
                result = self._validator.validate(batch, repo_path)
                validated.extend(result.validated_findings)
                suppressed.extend(result.suppressed_findings)
            except Exception as e:
                # FAIL-OPEN: on batch failure, retain ALL findings as UNVALIDATED
                logger.error("Validator failed on batch %d: %s — retaining all findings", i // self._batch_size, e)
                for f in batch:
                    f.validation_status = ValidationStatus.UNVALIDATED
                    f.validation_reasoning = f"Validation failed: {e}"
                validated.extend(batch)

        return ValidationResult(
            validated_findings=validated,
            suppressed_findings=suppressed,
            suppressed_count=len(suppressed),
        )
