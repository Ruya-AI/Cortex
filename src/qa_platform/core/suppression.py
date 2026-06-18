from __future__ import annotations

import fnmatch
from datetime import datetime, timezone

from qa_platform.core.finding import Finding, LifecycleState


class SuppressionApplicator:
    """Apply suppression rules to findings."""

    def apply(
        self, findings: list[Finding], config: dict
    ) -> tuple[list[Finding], list[Finding]]:
        """Partition *findings* into active and suppressed lists.

        Suppression entries are read from
        ``config["suppressions"]["entries"]``.  Each entry is a dict with:

        * ``pattern`` -- matched against ``finding.suppression_key``
          (supports ``fnmatch`` globs).
        * ``file_scope`` (optional) -- if set, the finding's ``file`` must
          also match this glob.
        * ``expires`` (optional) -- ISO-8601 timestamp; the rule is ignored
          once expired.

        Returns ``(active, suppressed)``.
        """

        entries = (
            config.get("suppressions", {}).get("entries", [])
        )
        if not entries:
            return list(findings), []

        now = datetime.now(timezone.utc)

        active: list[Finding] = []
        suppressed: list[Finding] = []

        for finding in findings:
            if self._is_suppressed(finding, entries, now):
                finding.lifecycle_state = LifecycleState.SUPPRESSED
                suppressed.append(finding)
            else:
                active.append(finding)

        return active, suppressed

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_suppressed(
        finding: Finding,
        entries: list[dict],
        now: datetime,
    ) -> bool:
        for entry in entries:
            pattern = entry.get("pattern", "")
            if not fnmatch.fnmatch(finding.suppression_key, pattern):
                continue

            # Check file scope.
            file_scope = entry.get("file_scope")
            if file_scope and not fnmatch.fnmatch(finding.file, file_scope):
                continue

            # Check expiry.
            expires_str = entry.get("expires")
            if expires_str:
                try:
                    expires_dt = datetime.fromisoformat(expires_str)
                    if expires_dt.tzinfo is None:
                        expires_dt = expires_dt.replace(tzinfo=timezone.utc)
                    if now > expires_dt:
                        # Rule has expired -- skip it.
                        continue
                except (ValueError, TypeError):
                    # Malformed date -- treat as non-expiring.
                    pass

            return True

        return False
