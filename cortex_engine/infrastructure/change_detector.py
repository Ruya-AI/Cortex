from __future__ import annotations

import logging
import re
from pathlib import Path

from cortex_engine.core.schemas import (
    ChangeSet,
    FileChange,
    FileDiff,
    RepositoryContext,
    ScanRequest,
)
from cortex_engine.infrastructure.git import GitOperations

logger = logging.getLogger(__name__)


class ChangeDetector:
    """Detect changed files and parse git diffs into structured data."""

    def detect(
        self,
        context: RepositoryContext,
        request: ScanRequest,
    ) -> ChangeSet:
        """Build a ChangeSet from the repository state and scan request.

        * full_scan: list all tracked files.
        * compare_to: diff against the given base ref.
        * default: diff HEAD~1..HEAD.
        """
        repo_path = context.local_path

        if request.full_scan:
            return self._full_scan(repo_path)

        base_branch = request.compare_to
        diff_text = GitOperations.get_diff(repo_path, base_branch=base_branch)
        changed_paths = GitOperations.get_changed_files(repo_path, base_branch=base_branch)

        file_diffs = self._parse_diff(diff_text)
        file_changes: list[FileChange] = []
        total_added = 0
        total_deleted = 0

        for path in changed_paths:
            diff = file_diffs.get(path)
            is_new = diff.is_new_file if diff else False
            is_deleted = diff.is_deleted_file if diff else False
            is_renamed = diff.is_renamed if diff else False

            if diff:
                total_added += len(diff.added_lines)
                total_deleted += len(diff.deleted_lines)

            file_changes.append(
                FileChange(
                    file_path=path,
                    diff=diff,
                    is_new=is_new,
                    is_deleted=is_deleted,
                    is_renamed=is_renamed,
                )
            )

        modules = self._detect_modules(changed_paths)

        return ChangeSet(
            changed_files=file_changes,
            modules_detected=modules,
            is_full_scan=False,
            lines_added=total_added,
            lines_deleted=total_deleted,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _full_scan(self, repo_path: Path) -> ChangeSet:
        """List all tracked files for a full-scan request."""
        output = GitOperations._run_git(["ls-files"], cwd=repo_path)
        if not output:
            return ChangeSet(is_full_scan=True)

        paths = [line for line in output.split("\n") if line]
        file_changes = [
            FileChange(file_path=p, is_new=False, is_deleted=False)
            for p in paths
        ]
        modules = self._detect_modules(paths)

        return ChangeSet(
            changed_files=file_changes,
            modules_detected=modules,
            is_full_scan=True,
        )

    def _parse_diff(self, diff_text: str) -> dict[str, FileDiff]:
        """Parse unified diff output into per-file FileDiff objects."""
        if not diff_text:
            return {}

        file_diffs: dict[str, FileDiff] = {}
        current_path: str | None = None
        current_diff: FileDiff | None = None
        current_hunk_new_line = 0
        current_hunk_old_line = 0

        for line in diff_text.split("\n"):
            # New file header
            if line.startswith("diff --git "):
                # Save previous
                if current_path and current_diff:
                    file_diffs[current_path] = current_diff
                current_path = None
                current_diff = None

            elif line.startswith("+++ b/"):
                current_path = line[len("+++ b/"):]
                current_diff = FileDiff(file_path=current_path)

            elif line.startswith("+++ /dev/null") and current_diff:
                current_diff.is_deleted_file = True

            elif line.startswith("--- /dev/null") and current_diff:
                current_diff.is_new_file = True

            elif line.startswith("--- a/") and current_diff:
                old_path = line[len("--- a/"):]
                if current_path and old_path != current_path:
                    current_diff.is_renamed = True
                    current_diff.old_path = old_path

            elif line.startswith("@@ "):
                # Parse hunk header: @@ -old_start[,old_count] +new_start[,new_count] @@
                match = re.match(
                    r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@",
                    line,
                )
                if match:
                    current_hunk_old_line = int(match.group(1))
                    current_hunk_new_line = int(match.group(2))

            elif current_diff is not None:
                if line.startswith("+") and not line.startswith("+++"):
                    current_diff.added_lines.append(current_hunk_new_line)
                    current_hunk_new_line += 1
                elif line.startswith("-") and not line.startswith("---"):
                    current_diff.deleted_lines.append(current_hunk_old_line)
                    current_hunk_old_line += 1
                else:
                    # Context line
                    current_hunk_new_line += 1
                    current_hunk_old_line += 1

            # Accumulate raw diff text per file
            if current_diff is not None:
                current_diff.diff_text += line + "\n"

        # Save last file
        if current_path and current_diff:
            file_diffs[current_path] = current_diff

        return file_diffs

    @staticmethod
    def _detect_modules(paths: list[str]) -> list[str]:
        """Extract top-level directory names from file paths as module names."""
        seen: set[str] = set()
        modules: list[str] = []
        for path in paths:
            parts = path.split("/")
            if len(parts) > 1 and parts[0] not in seen:
                seen.add(parts[0])
                modules.append(parts[0])
        return modules
