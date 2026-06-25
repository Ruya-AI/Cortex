from __future__ import annotations
import pytest
from cortex_engine.core.finding import (
    Finding, Severity, Confidence, FindingCategory, ValidationStatus,
    Classification, LifecycleState, Evidence, AuthorAttribution,
)


class TestSeverity:
    def test_ordering(self):
        assert Severity.CRITICAL > Severity.HIGH
        assert Severity.HIGH > Severity.MEDIUM
        assert Severity.MEDIUM > Severity.LOW
        assert Severity.LOW > Severity.INFO

    def test_values(self):
        assert Severity.CRITICAL == 4
        assert Severity.INFO == 0


class TestConfidence:
    def test_ordering(self):
        assert Confidence.CONFIRMED > Confidence.LIKELY
        assert Confidence.LIKELY > Confidence.UNCERTAIN


class TestFinding:
    def test_default_values(self):
        f = Finding()
        assert f.id == ""
        assert f.severity == Severity.MEDIUM
        assert f.confidence == Confidence.LIKELY
        assert f.validation_status == ValidationStatus.UNVALIDATED
        assert f.lifecycle_state == LifecycleState.OPEN
        assert f.cwe is None
        assert f.author is None

    def test_mutable(self):
        f = Finding()
        f.id = "test-001"
        assert f.id == "test-001"

    def test_evidence_isolation(self):
        f1 = Finding()
        f2 = Finding()
        f1.evidence.tool_calls.append("test")
        assert len(f2.evidence.tool_calls) == 0

    def test_to_dict(self):
        f = Finding(id="F-001", severity=Severity.HIGH, file="test.py", title="Test finding")
        d = f.to_dict()
        assert isinstance(d, dict)
        assert d["id"] == "F-001"
        assert d["severity"] == 3  # IntEnum value
        assert d["file"] == "test.py"

    def test_category_values(self):
        assert FindingCategory.CORRECTNESS.value == "correctness"
        assert FindingCategory.SECURITY.value == "security"


class TestEvidence:
    def test_defaults(self):
        e = Evidence()
        assert e.tool_calls == []
        assert e.code_references == []
        assert e.metrics == {}
