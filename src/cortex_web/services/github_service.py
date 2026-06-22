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

    async def fetch_org_repos(self, org: str) -> list[dict]:
        """Fetch all repositories for a GitHub organization or user."""
        all_repos: list[dict] = []
        page = 1
        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                # Try org endpoint first, fall back to user endpoint
                for endpoint in [f"{self._api_url}/orgs/{org}/repos", f"{self._api_url}/users/{org}/repos"]:
                    try:
                        response = await client.get(
                            endpoint,
                            headers=self._headers,
                            params={"per_page": 100, "page": page, "sort": "updated", "direction": "desc"},
                        )
                        if response.status_code == 200:
                            repos = response.json()
                            if not repos:
                                return all_repos
                            all_repos.extend([
                                {
                                    "owner": repo["owner"]["login"],
                                    "repo_name": repo["name"],
                                    "full_name": repo["full_name"],
                                    "description": repo.get("description") or "",
                                    "default_branch": repo.get("default_branch", "main"),
                                    "html_url": repo["html_url"],
                                    "language": repo.get("language") or "",
                                    "private": repo.get("private", False),
                                    "archived": repo.get("archived", False),
                                    "stars": repo.get("stargazers_count", 0),
                                    "updated_at": repo.get("updated_at", ""),
                                }
                                for repo in repos
                                if not repo.get("archived", False)
                            ])
                            page += 1
                            break
                    except httpx.HTTPStatusError:
                        continue
                else:
                    break
                if len(repos) < 100:
                    break
        return all_repos

    async def get_pr_details(self, owner: str, repo: str, pr_number: int) -> dict:
        """Fetch detailed PR information including file changes."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self._api_url}/repos/{owner}/{repo}/pulls/{pr_number}",
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()
