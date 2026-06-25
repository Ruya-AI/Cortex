from __future__ import annotations

from pathlib import Path

import pytest

from cortex_engine.core.finding import (
    Confidence,
    Evidence,
    Finding,
    FindingCategory,
    Severity,
)


@pytest.fixture
def sample_finding() -> Finding:
    return Finding(
        id="F-test-001",
        source="test-tool",
        tier=1,
        category=FindingCategory.CORRECTNESS,
        severity=Severity.MEDIUM,
        confidence=Confidence.LIKELY,
        file="src/example.py",
        start_line=42,
        end_line=42,
        title="Sample finding for testing",
        explanation="This is a test finding.",
        evidence=Evidence(tool_calls=["test-tool check on src/example.py"]),
        recommendation="Fix the issue.",
        suppression_key="test-tool-correctness",
    )


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    output_dir = tmp_path / "qa_output"
    output_dir.mkdir()
    return output_dir
