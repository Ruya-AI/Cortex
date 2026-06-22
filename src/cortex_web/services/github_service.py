from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class GitHubService:
    """Fetches PRs from GitHub API."""

    def __init__(self, token: str, api_url: str = "https://api.github.com"):
        self._token = token
        self._api_url = api_url
        self._headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

    async def fetch_open_prs(self, owner: str, repo: str) -> list[dict]:
        """Fetch all open PRs for a repository."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self._api_url}/repos/{owner}/{repo}/pulls",
                headers=self._headers,
                params={"state": "open", "per_page": 100, "sort": "updated", "direction": "desc"},
            )
            response.raise_for_status()
            prs = response.json()

            return [
                {
                    "github_pr_number": pr["number"],
                    "github_pr_id": str(pr["id"]),
                    "title": pr["title"],
                    "author": pr["user"]["login"],
                    "author_avatar_url": pr["user"]["avatar_url"],
                    "source_branch": pr["head"]["ref"],
                    "target_branch": pr["base"]["ref"],
                    "state": pr["state"],
                    "html_url": pr["html_url"],
                    "diff_url": pr.get("diff_url", ""),
                    "additions": pr.get("additions", 0),
                    "deletions": pr.get("deletions", 0),
                    "changed_files": pr.get("changed_files", 0),
                    "github_created_at": pr["created_at"],
                    "github_updated_at": pr["updated_at"],
                }
                for pr in prs
            ]

    async def get_pr_details(self, owner: str, repo: str, pr_number: int) -> dict:
        """Fetch detailed PR information including file changes."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self._api_url}/repos/{owner}/{repo}/pulls/{pr_number}",
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()
