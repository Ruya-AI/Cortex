from __future__ import annotations

from typing import Any

from qa_platform.core.author_attributor import AuthorAttributor, BlameFn, GitConfigFn
from qa_platform.core.diff_classifier import DiffClassifier
from qa_platform.core.finding import Finding
from qa_platform.core.finding_clusterer import FindingClusterer
from qa_platform.core.finding_deduplicator import FindingDeduplicator
from qa_platform.core.finding_line_validator import FindingLineValidator
from qa_platform.core.finding_ranker import FindingRanker
from qa_platform.core.schemas import ChangeSet, ProcessedFindings, RepositoryContext
from qa_platform.core.snippet_extractor import SnippetExtractor
from qa_platform.core.suppression import SuppressionApplicator


class FindingManager:
    """Orchestrates the complete finding-processing pipeline.

    Pipeline steps execute in a fixed order:

    1. Line validation (clamp to file length)
    2. Deduplication
    3. Diff classification (INTRODUCED / MODIFIED / PRE_EXISTING)
    4. Author attribution
    5. Snippet extraction
    6. Suppression
    7. Clustering
    8. Ranking
    9. ID assignment
    """

    def __init__(
        self,
        blame_fn: BlameFn | None = None,
        git_config_fn: GitConfigFn | None = None,
    ) -> None:
        self._line_validator = FindingLineValidator()
        self._deduplicator = FindingDeduplicator()
        self._diff_classifier = DiffClassifier()
        self._author_attributor = AuthorAttributor(
            blame_fn=blame_fn, git_config_fn=git_config_fn
        )
        self._snippet_extractor = SnippetExtractor()
        self._suppression_applicator = SuppressionApplicator()
        self._clusterer = FindingClusterer()
        self._ranker = FindingRanker()

    def process(
        self,
        findings: list[Finding],
        repo_context: RepositoryContext,
        change_set: ChangeSet,
        config: dict[str, Any],
        scan_id: str = "",
    ) -> ProcessedFindings:
        """Run all pipeline steps and return :class:`ProcessedFindings`.

        The order of steps is fixed and must not be reordered.
        """

        # 1. Validate / clamp line numbers.
        self._line_validator.validate(findings, repo_context.local_path)

        # 2. Deduplicate.
        findings = self._deduplicator.deduplicate(findings)

        # 3. Classify against the change set.
        self._diff_classifier.classify(findings, change_set)

        # 4. Attribute authors.
        self._author_attributor.attribute(findings, repo_context, config)

        # 5. Extract code snippets.
        self._snippet_extractor.extract(findings, repo_context.local_path)

        # 6. Apply suppressions.
        active, suppressed = self._suppression_applicator.apply(findings, config)

        # 7. Cluster related findings.
        clusters = self._clusterer.cluster(active)

        # 8. Rank active findings by priority.
        active = self._ranker.rank(active)

        # 9. Assign human-readable IDs.
        short_id = scan_id[:8] if scan_id else "000"
        for i, f in enumerate(active, 1):
            f.id = f"F-{short_id}-{i:03d}"

        return ProcessedFindings(
            active_findings=active,
            suppressed_findings=suppressed,
            clusters=clusters,
        )
