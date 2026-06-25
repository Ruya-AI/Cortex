from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from cortex_engine.core.finding import Finding

logger = logging.getLogger(__name__)


class SQLiteFindingRepository:
    """CRUD operations for persisted findings."""

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    @staticmethod
    def save_findings(
        conn: sqlite3.Connection,
        scan_id: str,
        findings: list[Finding],
    ) -> int:
        """Insert a batch of findings. Returns the number of rows inserted."""
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        inserted = 0
        for f in findings:
            author_name = f.author.name if f.author else None
            author_email = f.author.email if f.author else None
            cursor.execute(
                """
                INSERT OR REPLACE INTO findings (
                    finding_id, scan_id, source, tier, category,
                    severity, confidence, classification,
                    file_path, start_line, end_line,
                    title, explanation, recommendation, cwe,
                    validation_status, validation_reasoning,
                    lifecycle_state,
                    author_name, author_email,
                    first_seen_at, last_seen_at
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?,
                    ?,
                    ?, ?,
                    ?, ?
                )
                """,
                (
                    f.id,
                    scan_id,
                    f.source,
                    f.tier,
                    f.category.value if f.category else None,
                    f.severity.name if f.severity else None,
                    f.confidence.name if f.confidence else None,
                    f.classification.value if f.classification else None,
                    f.file,
                    f.start_line,
                    f.end_line,
                    f.title,
                    f.explanation,
                    f.recommendation,
                    f.cwe,
                    f.validation_status.value if f.validation_status else None,
                    f.validation_reasoning,
                    f.lifecycle_state.value if f.lifecycle_state else "open",
                    author_name,
                    author_email,
                    f.first_seen or now,
                    now,
                ),
            )
            inserted += 1
        return inserted

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @staticmethod
    def get_findings_by_scan(
        conn: sqlite3.Connection,
        scan_id: str,
    ) -> list[dict]:
        """Return all findings for a given scan as a list of dicts."""
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM findings WHERE scan_id = ? ORDER BY severity DESC",
            (scan_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    @staticmethod
    def update_lifecycle_state(
        conn: sqlite3.Connection,
        finding_id: str,
        state: str,
    ) -> bool:
        """Update the lifecycle_state of a finding. Returns True if a row was updated."""
        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()
        resolved_at = now if state == "resolved" else None
        cursor.execute(
            """
            UPDATE findings
               SET lifecycle_state = ?,
                   resolved_at = COALESCE(?, resolved_at)
             WHERE finding_id = ?
            """,
            (state, resolved_at, finding_id),
        )
        return cursor.rowcount > 0
