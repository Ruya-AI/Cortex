from __future__ import annotations
from pathlib import Path
from qa_platform.core.finding import Finding, Severity, Confidence, FindingCategory, Classification
from qa_platform.core.schemas import ChangeSet, RepositoryContext, ProcessedFindings
from qa_platform.core.finding_manager import FindingManager


class TestFindingManager:
    def test_process_empty(self):
        fm = FindingManager()
        ctx = RepositoryContext(local_path=Path("/tmp"))
        cs = ChangeSet()
        result = fm.process([], ctx, cs, {})
        assert isinstance(result, ProcessedFindings)
        assert result.active_findings == []

    def test_process_assigns_ids(self):
        fm = FindingManager()
        findings = [
            Finding(source="test", file="a.py", start_line=1, severity=Severity.HIGH, title="Issue 1"),
            Finding(source="test", file="b.py", start_line=1, severity=Severity.MEDIUM, title="Issue 2"),
        ]
        ctx = RepositoryContext(local_path=Path("/tmp"))
        cs = ChangeSet()
        result = fm.process(findings, ctx, cs, {}, scan_id="abc12345")
        assert result.active_findings[0].id.startswith("F-abc12345-")

    def test_process_ranks_by_severity(self):
        fm = FindingManager()
        findings = [
            Finding(source="test", file="a.py", start_line=1, severity=Severity.LOW, title="Low"),
            Finding(source="test", file="b.py", start_line=1, severity=Severity.CRITICAL, title="Critical"),
            Finding(source="test", file="c.py", start_line=1, severity=Severity.HIGH, title="High"),
        ]
        ctx = RepositoryContext(local_path=Path("/tmp"))
        cs = ChangeSet()
        result = fm.process(findings, ctx, cs, {})
        severities = [f.severity for f in result.active_findings]
        assert severities[0] == Severity.CRITICAL
        assert severities[1] == Severity.HIGH
        assert severities[2] == Severity.LOW
