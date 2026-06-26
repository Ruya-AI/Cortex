from __future__ import annotations

import logging

from cortex_engine.core.schemas import RiskAssessment, Tier1RunResult

logger = logging.getLogger(__name__)

HIGH_RISK_PATHS = {"auth/", "security/", "crypto/", "payment/", "admin/"}
LOW_RISK_PATHS = {"test/", "tests/", "docs/", "doc/", "config/", "generated/", ".github/"}


class RiskScorer:
    def __init__(self, threshold: float = 5.0):
        self._threshold = threshold

    def score(self, files: list[str], tier1_result: Tier1RunResult, config: dict, code_graph=None) -> RiskAssessment:
        findings_per_file: dict[str, int] = {}
        for f in tier1_result.findings:
            findings_per_file[f.file] = findings_per_file.get(f.file, 0) + 1

        god_node_files = self._get_god_node_files(code_graph) if code_graph else set()

        high_risk: list[str] = []
        low_risk: list[str] = []
        scores: dict[str, float] = {}

        for fp in files:
            score = self._compute_score(fp, findings_per_file.get(fp, 0))
            if fp in god_node_files:
                score += 3.0
            scores[fp] = score
            if score >= self._threshold:
                high_risk.append(fp)
            else:
                low_risk.append(fp)

        logger.info(
            "Risk scoring: %d high-risk, %d low-risk (threshold=%.1f, graph=%s)",
            len(high_risk), len(low_risk), self._threshold,
            f"{len(god_node_files)} god nodes" if god_node_files else "no graph",
        )
        return RiskAssessment(high_risk_files=high_risk, low_risk_files=low_risk, scores=scores)

    def _compute_score(self, file_path: str, sast_finding_count: int) -> float:
        path_factor = 0.5
        for prefix in HIGH_RISK_PATHS:
            if prefix in file_path.lower():
                path_factor = 1.0
                break
        for prefix in LOW_RISK_PATHS:
            if file_path.lower().startswith(prefix):
                path_factor = 0.2
                break

        sast_score = min(sast_finding_count * 2.0, 10.0)
        return sast_score * path_factor + path_factor * 3.0

    @staticmethod
    def _get_god_node_files(code_graph) -> set[str]:
        """Extract file paths from the most-connected graph nodes."""
        try:
            from cortex_engine.infrastructure.code_graph import CodeGraph
            gods = CodeGraph.get_god_nodes(code_graph, top_n=10)
            files = set()
            for g in gods:
                node_id = g.get("id", "")
                for node, data in code_graph.nodes(data=True):
                    if node == node_id:
                        file_attr = data.get("file", "")
                        if file_attr:
                            files.add(file_attr)
                        else:
                            parts = node_id.split("_")
                            if parts:
                                files.add(parts[0].replace("_", "/") + ".py")
            return files
        except Exception:
            return set()
