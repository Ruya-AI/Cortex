from __future__ import annotations

from cortex_engine.core.finding import Classification, Finding


# Classification ordering: INTRODUCED first, then MODIFIED, then PRE_EXISTING,
# everything else last.
_CLASSIFICATION_ORDER: dict[Classification, int] = {
    Classification.INTRODUCED: 0,
    Classification.MODIFIED: 1,
    Classification.PRE_EXISTING: 2,
    Classification.UNCLASSIFIED: 3,
}


class FindingRanker:
    """Sort findings by severity, confidence, classification, and file path."""

    def rank(self, findings: list[Finding]) -> list[Finding]:
        """Return a new list of *findings* sorted by priority.

        Sort key (descending priority):
        1. Severity descending (CRITICAL first).
        2. Confidence descending (CONFIRMED first).
        3. Classification (INTRODUCED > MODIFIED > PRE_EXISTING > UNCLASSIFIED).
        4. File path ascending (alphabetical).
        """

        return sorted(
            findings,
            key=lambda f: (
                -f.severity,
                -f.confidence,
                _CLASSIFICATION_ORDER.get(f.classification, 99),
                f.file,
            ),
        )
