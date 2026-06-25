from __future__ import annotations

import logging
import os

from cortex_engine.core.finding import Finding
from cortex_engine.core.schemas import IntegrationResult, QualityGateResult
from cortex_engine.integrations.dispatcher import IntegrationTarget

logger = logging.getLogger(__name__)

_LINEAR_API_URL = "https://api.linear.app/graphql"


class LinearIntegration(IntegrationTarget):
    """Creates parent issue + sub-issues in Linear for each scan."""

    name = "linear"

    def __init__(
        self,
        api_key: str | None = None,
        team_id: str | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("LINEAR_API_KEY", "")
        self._team_id = team_id or os.environ.get("LINEAR_TEAM_ID", "")

    def is_configured(self) -> bool:
        return bool(self._api_key and self._team_id)

    def dispatch(
        self,
        findings: list[Finding],
        gate_result: QualityGateResult,
        scan_metadata: dict,
        config: dict,
    ) -> IntegrationResult:
        max_issues = config.get("max_issues_per_scan", 20)
        repo = scan_metadata.get("repository", "unknown")

        try:

            headers = {
                "Authorization": self._api_key,
                "Content-Type": "application/json",
            }

            # Create parent issue
            parent_title = f"QA Scan: {repo} ({len(findings)} findings)"
            sev = gate_result.severity_counts
            parent_desc = (
                f"**Gate status**: {gate_result.status.upper()}\n\n"
                f"Critical: {sev.get('critical', 0)} | "
                f"High: {sev.get('high', 0)} | "
                f"Medium: {sev.get('medium', 0)} | "
                f"Low: {sev.get('low', 0)}\n\n"
                f"{gate_result.reasoning}"
            )

            parent_id = self._create_issue(
                headers, parent_title, parent_desc
            )
            if not parent_id:
                return IntegrationResult(
                    target_name=self.name,
                    status="error",
                    error_message="Failed to create parent issue",
                )

            # Create sub-issues for each finding (up to max_issues)
            created = 0
            for f in findings[:max_issues]:
                sub_title = f"[{f.severity.name}] {f.title}"
                location = (
                    f"`{f.file}:{f.start_line}`" if f.file else "N/A"
                )
                sub_desc = (
                    f"**Location**: {location}\n\n"
                    f"**Explanation**: {f.explanation}\n\n"
                    f"**Recommendation**: {f.recommendation}"
                )
                sub_id = self._create_issue(
                    headers, sub_title, sub_desc, parent_id=parent_id
                )
                if sub_id:
                    created += 1

            return IntegrationResult(
                target_name=self.name,
                status="success",
                details={
                    "parent_issue_id": parent_id,
                    "sub_issues_created": created,
                },
            )
        except Exception as e:
            logger.error("Linear integration error: %s", e)
            return IntegrationResult(
                target_name=self.name, status="error", error_message=str(e)
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_issue(
        self,
        headers: dict,
        title: str,
        description: str,
        parent_id: str | None = None,
    ) -> str:
        """Create a Linear issue via GraphQL and return the issue ID."""
        import httpx

        mutation = """
            mutation CreateIssue($input: IssueCreateInput!) {
                issueCreate(input: $input) {
                    success
                    issue { id }
                }
            }
        """
        variables: dict = {
            "input": {
                "teamId": self._team_id,
                "title": title,
                "description": description,
            }
        }
        if parent_id:
            variables["input"]["parentId"] = parent_id

        try:
            resp = httpx.post(
                _LINEAR_API_URL,
                headers=headers,
                json={"query": mutation, "variables": variables},
                timeout=30,
            )
            data = resp.json()
            issue_data = data.get("data", {}).get("issueCreate", {})
            if issue_data.get("success"):
                return issue_data["issue"]["id"]
            logger.warning("Linear issue creation failed: %s", data)
            return ""
        except Exception as e:
            logger.debug("Failed to create Linear issue: %s", e)
            return ""
