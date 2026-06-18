from __future__ import annotations

from collections import defaultdict

from qa_platform.core.finding import Classification, Finding
from qa_platform.core.schemas import ChangeSet


class DiffClassifier:
    """Classify findings as INTRODUCED, MODIFIED, or PRE_EXISTING based on
    the change set."""

    def classify(self, findings: list[Finding], change_set: ChangeSet) -> None:
        """Classify *findings* against *change_set*.  Mutates in place.

        * If ``change_set.is_full_scan`` is ``True``, all findings become
          ``UNCLASSIFIED``.
        * Otherwise, each finding is checked against the added/deleted lines
          in the matching file change.
        """

        if change_set.is_full_scan:
            for f in findings:
                f.classification = Classification.UNCLASSIFIED
            return

        # Build a map: file_path -> (set of added lines, set of all changed lines).
        added_map: dict[str, set[int]] = defaultdict(set)
        changed_map: dict[str, set[int]] = defaultdict(set)

        for fc in change_set.changed_files:
            if fc.diff is None:
                continue
            added_set = set(fc.diff.added_lines)
            changed_set = added_set | set(fc.diff.deleted_lines)
            added_map[fc.file_path] = added_set
            changed_map[fc.file_path] = changed_set

        for f in findings:
            added_lines = added_map.get(f.file)
            changed_lines = changed_map.get(f.file)

            if added_lines is None and changed_lines is None:
                f.classification = Classification.PRE_EXISTING
                continue

            finding_lines = set(range(f.start_line, f.end_line + 1))

            if added_lines and finding_lines & added_lines:
                f.classification = Classification.INTRODUCED
            elif changed_lines and finding_lines & changed_lines:
                f.classification = Classification.MODIFIED
            else:
                f.classification = Classification.PRE_EXISTING
