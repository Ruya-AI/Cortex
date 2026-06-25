from __future__ import annotations

import logging

from cortex_engine.core.finding import Finding, Severity, Confidence
from cortex_engine.core.schemas import QualityGateResult

logger = logging.getLogger(__name__)


class QualityGate:
    def evaluate(self, findings: list[Finding], config: dict) -> QualityGateResult:
        gate_config = config.get("quality_gates", {})
        mode = gate_config.get("current_mode", "shadow")
        thresholds = gate_config.get("thresholds", {})
        max_critical = thresholds.get("max_critical", 0)
        max_high = thresholds.get("max_high", 0)
        min_confidence_str = thresholds.get("required_confidence", "likely")

        min_confidence = {
            "confirmed": Confidence.CONFIRMED,
            "likely": Confidence.LIKELY,
            "uncertain": Confidence.UNCERTAIN,
        }.get(min_confidence_str, Confidence.LIKELY)

        severity_counts: dict[str, int] = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0,
        }
        blocking_findings: list[str] = []

        for f in findings:
            if f.confidence < min_confidence:
                continue
            sev_name = f.severity.name.lower()
            severity_counts[sev_name] = severity_counts.get(sev_name, 0) + 1

        # Check thresholds
        blocked = False
        reasons: list[str] = []
        if severity_counts["critical"] > max_critical:
            blocked = True
            reasons.append(f"{severity_counts['critical']} critical (max {max_critical})")
            blocking_findings.extend(
                [
                    f.id
                    for f in findings
                    if f.severity == Severity.CRITICAL and f.confidence >= min_confidence
                ]
            )
        if severity_counts["high"] > max_high:
            blocked = True
            reasons.append(f"{severity_counts['high']} high (max {max_high})")
            blocking_findings.extend(
                [
                    f.id
                    for f in findings
                    if f.severity == Severity.HIGH and f.confidence >= min_confidence
                ]
            )

        # Apply mode
        if mode == "shadow":
            status = "pass"
            reasoning = (
                f"Shadow mode: would {'fail' if blocked else 'pass'}. {'; '.join(reasons)}"
                if reasons
                else "Shadow mode: pass"
            )
        elif mode == "advisory":
            status = "advisory" if blocked else "pass"
            reasoning = f"Advisory: {'; '.join(reasons)}" if reasons else "Advisory: pass"
        elif mode == "enforced":
            status = "fail" if blocked else "pass"
            reasoning = f"Enforced: {'; '.join(reasons)}" if reasons else "Enforced: pass"
        else:
            status = "pass"
            reasoning = f"Unknown mode '{mode}' -- defaulting to pass"

        return QualityGateResult(
            status=status,
            mode=mode,
            severity_counts=severity_counts,
            blocking_findings=blocking_findings,
            reasoning=reasoning,
        )
