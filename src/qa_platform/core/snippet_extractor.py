from __future__ import annotations

import re
from pathlib import Path

from qa_platform.core.finding import Finding

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class SnippetExtractor:
    """Extract annotated code snippets and attach them to findings."""

    def extract(self, findings: list[Finding], repo_path: Path) -> None:
        """Populate ``finding.code_under_review`` with a formatted snippet.

        For each finding the relevant file is read, and lines surrounding the
        finding's range are formatted with line numbers and a ``FLAGGED``
        marker.  Mutates findings in place.
        """

        file_cache: dict[str, list[str] | None] = {}

        for finding in findings:
            lines = self._get_lines(finding.file, repo_path, file_cache)
            if lines is None:
                continue

            total = len(lines)
            # Context window: 3 lines before, 3 lines after the finding range.
            context_start = max(0, finding.start_line - 4)
            context_end = min(total, finding.end_line + 3)

            snippet_parts: list[str] = []
            for idx in range(context_start, context_end):
                line_num = idx + 1  # 1-based
                clean_line = _CONTROL_CHARS.sub("", lines[idx])
                marker = (
                    " ◄── FLAGGED"
                    if finding.start_line <= line_num <= finding.end_line
                    else ""
                )
                snippet_parts.append(f"    {line_num:4d} | {clean_line}{marker}")

            finding.code_under_review = "\n".join(snippet_parts)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_lines(
        file_rel: str,
        repo_path: Path,
        cache: dict[str, list[str] | None],
    ) -> list[str] | None:
        if file_rel in cache:
            return cache[file_rel]

        full_path = (repo_path / file_rel).resolve()
        if not full_path.is_relative_to(repo_path.resolve()):
            result = None
            cache[file_rel] = result
            return result
        try:
            text = full_path.read_text(encoding="utf-8", errors="replace")
            result = text.splitlines()
        except (OSError, ValueError):
            result = None

        cache[file_rel] = result
        return result
