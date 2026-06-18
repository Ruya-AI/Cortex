from __future__ import annotations
from qa_platform.core.finding import Finding, Severity, Confidence
from qa_platform.assessment.quality_gate import QualityGate


class TestQualityGate:
    def test_shadow_mode_always_passes(self):
        gate = QualityGate()
        findings = [Finding(severity=Severity.CRITICAL, confidence=Confidence.CONFIRMED)]
        config = {"quality_gates": {"current_mode": "shadow"}}
        result = gate.evaluate(findings, config)
        assert result.status == "pass"
        assert "Shadow" in result.reasoning

    def test_enforced_mode_fails_on_critical(self):
        gate = QualityGate()
        findings = [Finding(severity=Severity.CRITICAL, confidence=Confidence.CONFIRMED)]
        config = {"quality_gates": {"current_mode": "enforced", "thresholds": {"max_critical": 0}}}
        result = gate.evaluate(findings, config)
        assert result.status == "fail"

    def test_enforced_mode_passes_when_under_threshold(self):
        gate = QualityGate()
        findings = [Finding(severity=Severity.MEDIUM, confidence=Confidence.CONFIRMED)]
        config = {"quality_gates": {"current_mode": "enforced", "thresholds": {"max_critical": 0, "max_high": 0}}}
        result = gate.evaluate(findings, config)
        assert result.status == "pass"

    def test_advisory_mode_warns(self):
        gate = QualityGate()
        findings = [Finding(severity=Severity.HIGH, confidence=Confidence.CONFIRMED)]
        config = {"quality_gates": {"current_mode": "advisory", "thresholds": {"max_high": 0}}}
        result = gate.evaluate(findings, config)
        assert result.status == "advisory"

    def test_low_confidence_excluded(self):
        gate = QualityGate()
        findings = [Finding(severity=Severity.CRITICAL, confidence=Confidence.UNCERTAIN)]
        config = {"quality_gates": {"current_mode": "enforced", "thresholds": {"max_critical": 0, "required_confidence": "confirmed"}}}
        result = gate.evaluate(findings, config)
        assert result.status == "pass"
