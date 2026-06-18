from __future__ import annotations

from pathlib import Path

from qa_platform.core.finding import Finding


class FindingLineValidator:
    """Clamp finding line ranges to actual file lengths."""

    def validate(self, findings: list[Finding], repo_path: Path) -> None:
        """Validate and clamp line numbers for *findings* against files in *repo_path*.

        Mutates findings in place.  Files that cannot be read are silently
        skipped.
        """

        line_count_cache: dict[str, int] = {}

        for finding in findings:
            file_key = finding.file
            if file_key not in line_count_cache:
                full_path = repo_path / file_key
                try:
                    text = full_path.read_text(encoding="utf-8", errors="replace")
                    line_count_cache[file_key] = len(text.splitlines())
                except (OSError, ValueError):
                    # File not found or unreadable -- skip this finding.
                    continue

            line_count = line_count_cache[file_key]
            if line_count == 0:
                # Empty file -- nothing to clamp against.
                continue

            finding.start_line = max(1, min(finding.start_line, line_count))
            finding.end_line = max(finding.start_line, min(finding.end_line, line_count))
