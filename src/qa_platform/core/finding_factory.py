from __future__ import annotations

from datetime import datetime, timezone

from qa_platform.core.finding import (
    Confidence,
    Evidence,
    Finding,
    FindingCategory,
    Severity,
)


class FindingFactory:
    """Factory methods for creating :class:`Finding` instances."""

    @staticmethod
    def create_from_tool(
        tool_name: str,
        file: str,
        start_line: int,
        end_line: int,
        severity: Severity,
        category: FindingCategory,
        title: str,
        explanation: str,
        recommendation: str = "",
        confidence: Confidence = Confidence.LIKELY,
    ) -> Finding:
        """Create a Tier-1 finding from a static-analysis tool."""

        start_line = max(1, start_line)
        end_line = max(start_line, end_line)
        title = title[:120]
        suppression_key = f"{tool_name}-{category.value}"
        now_iso = datetime.now(timezone.utc).isoformat()

        return Finding(
            source=tool_name,
            tier=1,
            category=category,
            severity=severity,
            confidence=confidence,
            file=file,
            start_line=start_line,
            end_line=end_line,
            title=title,
            explanation=explanation,
            evidence=Evidence(tool_calls=[f"{tool_name} check on {file}"]),
            recommendation=recommendation,
            suppression_key=suppression_key,
            first_seen=now_iso,
            last_seen=now_iso,
        )

    @staticmethod
    def create_from_agent(
        agent_name: str,
        tier: int,
        category: FindingCategory,
        file: str,
        start_line: int,
        end_line: int,
        severity: Severity,
        title: str,
        explanation: str,
        evidence: Evidence,
        recommendation: str,
        cwe: str | None = None,
        confidence: Confidence = Confidence.LIKELY,
    ) -> Finding:
        """Create a finding from an AI agent review."""

        start_line = max(1, start_line)
        end_line = max(start_line, end_line)
        title = title[:120]
        suppression_key = f"{agent_name}-{category.value}"
        now_iso = datetime.now(timezone.utc).isoformat()

        return Finding(
            source=agent_name,
            tier=tier,
            category=category,
            severity=severity,
            confidence=confidence,
            file=file,
            start_line=start_line,
            end_line=end_line,
            title=title,
            explanation=explanation,
            evidence=evidence,
            recommendation=recommendation,
            cwe=cwe,
            suppression_key=suppression_key,
            first_seen=now_iso,
            last_seen=now_iso,
        )
