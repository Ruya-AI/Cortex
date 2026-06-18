from __future__ import annotations

from collections import defaultdict

from qa_platform.core.finding import Finding
from qa_platform.core.schemas import FindingCluster


class FindingClusterer:
    """Group related findings into clusters based on shared suppression-key prefix."""

    def cluster(self, findings: list[Finding]) -> list[FindingCluster]:
        """Cluster *findings* by suppression-key prefix (everything before the
        last ``-`` segment).

        Findings in groups of two or more are assigned to a
        :class:`FindingCluster`.  Each finding's ``root_cause_cluster`` and
        ``related_findings`` fields are updated in place.

        Returns the list of newly created clusters.
        """

        groups: dict[str, list[Finding]] = defaultdict(list)

        for f in findings:
            prefix = self._suppression_prefix(f.suppression_key)
            groups[prefix].append(f)

        clusters: list[FindingCluster] = []
        cluster_seq = 0

        for prefix, group in groups.items():
            if len(group) < 2:
                continue

            cluster_seq += 1
            cluster_id = f"C-{cluster_seq:03d}"
            finding_ids = [f.id for f in group]

            cluster = FindingCluster(
                cluster_id=cluster_id,
                root_cause=prefix,
                finding_ids=finding_ids,
                finding_count=len(group),
            )
            clusters.append(cluster)

            # Update each finding in the cluster.
            for f in group:
                f.root_cause_cluster = cluster_id
                f.related_findings = [
                    fid for fid in finding_ids if fid != f.id
                ]

        return clusters

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _suppression_prefix(key: str) -> str:
        """Return the prefix of *key* up to (but not including) the last ``-``."""

        idx = key.rfind("-")
        if idx <= 0:
            return key
        return key[:idx]
