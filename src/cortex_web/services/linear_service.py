from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

LINEAR_API_URL = "https://api.linear.app/graphql"


class LinearService:
    """Create and manage Linear issues."""

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
        }

    async def create_issue(self, team_id: str, title: str, description: str, priority: int = 3) -> dict:
        """Create a Linear issue."""
        mutation = """
        mutation CreateIssue($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue {
                    id
                    identifier
                    url
                }
            }
        }
        """
        variables = {
            "input": {
                "teamId": team_id,
                "title": title,
                "description": description,
                "priority": priority,
            }
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                LINEAR_API_URL,
                headers=self._headers,
                json={"query": mutation, "variables": variables},
            )
            response.raise_for_status()
            data = response.json()
            issue_data = data.get("data", {}).get("issueCreate", {}).get("issue", {})
            return {
                "id": issue_data.get("id", ""),
                "identifier": issue_data.get("identifier", ""),
                "url": issue_data.get("url", ""),
            }

    async def get_issue_status(self, issue_id: str) -> str:
        """Get the status of a Linear issue."""
        query = """
        query GetIssue($id: String!) {
            issue(id: $id) {
                state { name }
            }
        }
        """
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                LINEAR_API_URL,
                headers=self._headers,
                json={"query": query, "variables": {"id": issue_id}},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", {}).get("issue", {}).get("state", {}).get("name", "unknown")
