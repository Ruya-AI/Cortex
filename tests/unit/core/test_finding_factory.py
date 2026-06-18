from __future__ import annotations
from qa_platform.core.finding import Severity, FindingCategory, Confidence, Evidence
from qa_platform.core.finding_factory import FindingFactory


class TestFindingFactory:
    def test_create_from_tool(self):
        f = FindingFactory.create_from_tool(
            tool_name="ruff", file="src/main.py",
            start_line=10, end_line=15,
            severity=Severity.MEDIUM, category=FindingCategory.CORRECTNESS,
            title="Unused variable", explanation="Variable x is defined but never used",
            recommendation="Remove unused variable",
        )
        assert f.source == "ruff"
        assert f.tier == 1
        assert f.file == "src/main.py"
        assert f.start_line == 10
        assert f.suppression_key == "ruff-correctness"
        assert f.id == ""  # Assigned later

    def test_line_clamping(self):
        f = FindingFactory.create_from_tool(
            tool_name="test", file="test.py",
            start_line=-5, end_line=0,
            severity=Severity.LOW, category=FindingCategory.DESIGN,
            title="Test", explanation="Test",
        )
        assert f.start_line == 1
        assert f.end_line == 1

    def test_title_truncation(self):
        long_title = "x" * 200
        f = FindingFactory.create_from_tool(
            tool_name="test", file="test.py",
            start_line=1, end_line=1,
            severity=Severity.LOW, category=FindingCategory.DESIGN,
            title=long_title, explanation="Test",
        )
        assert len(f.title) == 120

    def test_create_from_agent(self):
        f = FindingFactory.create_from_agent(
            agent_name="correctness", tier=2,
            category=FindingCategory.CORRECTNESS,
            file="src/app.py", start_line=42, end_line=50,
            severity=Severity.HIGH,
            title="Null dereference", explanation="get_user returns None",
            evidence=Evidence(tool_calls=["read_file(src/db.py)"]),
            recommendation="Add null check",
            cwe="CWE-476",
        )
        assert f.source == "correctness"
        assert f.tier == 2
        assert f.cwe == "CWE-476"
