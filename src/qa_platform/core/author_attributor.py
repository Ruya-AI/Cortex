from __future__ import annotations

from typing import Any, Callable

from qa_platform.core.finding import AuthorAttribution, Classification, Finding
from qa_platform.core.schemas import RepositoryContext


# Type aliases for the injected callbacks.
BlameFn = Callable[..., list[dict[str, str]]]
GitConfigFn = Callable[..., str]


class AuthorAttributor:
    """Attribute findings to authors using injected git helpers.

    The attributor does **not** call ``subprocess`` directly; instead it
    receives callback functions for ``git blame`` and ``git config`` from the
    infrastructure layer.  This keeps ``core/`` free of infrastructure
    dependencies.
    """

    def __init__(
        self,
        blame_fn: BlameFn | None = None,
        git_config_fn: GitConfigFn | None = None,
    ) -> None:
        self._blame_fn = blame_fn
        self._git_config_fn = git_config_fn

    def attribute(
        self,
        findings: list[Finding],
        repo_context: RepositoryContext,
        config: dict[str, Any],
    ) -> None:
        """Assign :class:`AuthorAttribution` to each finding that lacks one.

        Attribution strategy (first match wins):

        1. **Pre-commit trigger**: use ``git config`` user.name / user.email.
        2. **PR author + INTRODUCED**: use the PR author from *config*.
        3. **Git blame**: blame the finding's file/line range.
        4. **Default author**: fall back to config values.

        Mutates findings in place.
        """

        trigger = config.get("trigger", "")
        pr_author = config.get("pr_author", "")
        default_name = (
            config.get("reporting", {}).get("default_author_name", "Unknown")
        )
        default_email = (
            config.get("reporting", {}).get("default_author_email", "unknown@unknown")
        )

        for finding in findings:
            if finding.author is not None:
                continue

            # Strategy 1: pre-commit -- current git user.
            if trigger == "pre-commit":
                author = self._from_git_config(repo_context)
                if author is not None:
                    finding.author = author
                    continue

            # Strategy 2: PR author for introduced findings.
            if pr_author and finding.classification == Classification.INTRODUCED:
                finding.author = AuthorAttribution(
                    name=pr_author,
                    email="",
                    attribution_source="pr_author",
                )
                continue

            # Strategy 3: git blame.
            author = self._from_blame(
                repo_context, finding.file, finding.start_line, finding.end_line
            )
            if author is not None:
                finding.author = author
                continue

            # Strategy 4: configurable default.
            finding.author = AuthorAttribution(
                name=default_name,
                email=default_email,
                attribution_source="default",
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _from_git_config(
        self, repo_context: RepositoryContext
    ) -> AuthorAttribution | None:
        if self._git_config_fn is None:
            return None
        try:
            name = self._git_config_fn(repo_context.local_path, "user.name")
            email = self._git_config_fn(repo_context.local_path, "user.email")
            if name:
                return AuthorAttribution(
                    name=name,
                    email=email or "",
                    attribution_source="git_config",
                )
        except Exception:
            pass
        return None

    def _from_blame(
        self,
        repo_context: RepositoryContext,
        file: str,
        start_line: int,
        end_line: int,
    ) -> AuthorAttribution | None:
        if self._blame_fn is None:
            return None
        try:
            entries = self._blame_fn(
                repo_context.local_path, file, start_line, end_line
            )
            if entries:
                entry = entries[0]
                return AuthorAttribution(
                    name=entry.get("author", ""),
                    email=entry.get("author-mail", "").strip("<>"),
                    attribution_source="git_blame",
                )
        except Exception:
            pass
        return None
