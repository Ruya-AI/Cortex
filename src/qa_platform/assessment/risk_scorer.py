from __future__ import annotations

import logging

from qa_platform.core.schemas import RiskAssessment, Tier1RunResult

logger = logging.getLogger(__name__)

HIGH_RISK_PATHS = {"auth/", "security/", "crypto/", "payment/", "admin/"}
LOW_RISK_PATHS = {"test/", "tests/", "docs/", "doc/", "config/", "generated/", ".github/"}


class RiskScorer:
    def __init__(self, threshold: float = 5.0):
        self._threshold = threshold

    def score(self, files: list[str], tier1_result: Tier1RunResult, config: dict) -> RiskAssessment:
        # Count tier1 findings per file
        findings_per_file: dict[str, int] = {}
        for f in tier1_result.findings:
            findings_per_file[f.file] = findings_per_file.get(f.file, 0) + 1

        high_risk: list[str] = []
        low_risk: list[str] = []
        scores: dict[str, float] = {}

        for fp in files:
            score = self._compute_score(fp, findings_per_file.get(fp, 0))
            scores[fp] = score
            if score >= self._threshold:
                high_risk.append(fp)
            else:
                low_risk.append(fp)

        logger.info(
            "Risk scoring: %d high-risk, %d low-risk (threshold=%.1f)",
            len(high_risk),
            len(low_risk),
            self._threshold,
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
