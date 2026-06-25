from __future__ import annotations

from collections import defaultdict

from cortex_engine.core.finding import Finding


class FindingDeduplicator:
    """Remove duplicate findings based on location overlap and similarity."""

    _LINE_TOLERANCE = 3

    def deduplicate(self, findings: list[Finding]) -> list[Finding]:
        """Return a deduplicated list of findings.

        Within each file, two findings are considered duplicates when their
        line ranges overlap (within a tolerance of +/- 3 lines) **and** they
        share a suppression key or have very similar titles.

        The finding with higher confidence survives; evidence from the
        duplicate is merged into it.
        """

        by_file: dict[str, list[Finding]] = defaultdict(list)
        for f in findings:
            by_file[f.file].append(f)

        result: list[Finding] = []

        for _file, group in by_file.items():
            merged_away: set[int] = set()

            for i in range(len(group)):
                if i in merged_away:
                    continue
                for j in range(i + 1, len(group)):
                    if j in merged_away:
                        continue

                    a, b = group[i], group[j]

                    if not self._lines_overlap(a, b):
                        continue
                    if not (
                        a.suppression_key == b.suppression_key
                        or self._titles_similar(a.title, b.title)
                    ):
                        continue

                    # Merge: keep the higher-confidence finding.
                    if b.confidence > a.confidence:
                        survivor, duplicate = b, a
                        merged_away.add(i)
                        group[j] = survivor
                    else:
                        survivor, duplicate = a, b
                        merged_away.add(j)

                    # Merge evidence from the duplicate into the survivor.
                    survivor.evidence.tool_calls.extend(duplicate.evidence.tool_calls)
                    survivor.evidence.code_references.extend(
                        duplicate.evidence.code_references
                    )
                    for k, v in duplicate.evidence.metrics.items():
                        survivor.evidence.metrics.setdefault(k, v)

                    # If finding[i] was merged away, stop comparing it.
                    if i in merged_away:
                        break

            for idx, f in enumerate(group):
                if idx not in merged_away:
                    result.append(f)

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _lines_overlap(self, a: Finding, b: Finding) -> bool:
        tol = self._LINE_TOLERANCE
        return (
            a.start_line - tol <= b.end_line and b.start_line - tol <= a.end_line
        )

    @staticmethod
    def _titles_similar(t1: str, t2: str) -> bool:
        """Very simple similarity check: normalised titles share > 80 % of words."""

        words1 = set(t1.lower().split())
        words2 = set(t2.lower().split())
        if not words1 or not words2:
            return False
        intersection = words1 & words2
        smaller = min(len(words1), len(words2))
        return len(intersection) / smaller >= 0.8
