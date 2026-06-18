from __future__ import annotations

import json
import logging
import sqlite3

logger = logging.getLogger(__name__)


class SQLiteScanRepository:
    """CRUD operations for persisted scan records."""

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    @staticmethod
    def save_scan(conn: sqlite3.Connection, scan_data: dict) -> None:
        """Insert a new scan record.

        ``scan_data`` should contain keys matching the ``scans`` table columns.
        ``severity_counts`` and ``tiers_executed`` are serialised to JSON if
        they are not already strings.
        """
        # Normalise composite fields to JSON strings
        sev = scan_data.get("severity_counts", {})
        if isinstance(sev, dict):
            sev = json.dumps(sev)
        tiers = scan_data.get("tiers_executed", "")
        if isinstance(tiers, (list, tuple)):
            tiers = json.dumps(tiers)

        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO scans (
                scan_id, repository, branch, commit_sha,
                trigger_type, tiers_executed,
                finding_count, severity_counts,
                gate_status, duration_seconds, cost_usd,
                report_json_path, report_pdf_path,
                created_at, config_hash
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?
            )
            """,
            (
                scan_data.get("scan_id"),
                scan_data.get("repository"),
                scan_data.get("branch"),
                scan_data.get("commit_sha"),
                scan_data.get("trigger_type"),
                tiers,
                scan_data.get("finding_count", 0),
                sev,
                scan_data.get("gate_status"),
                scan_data.get("duration_seconds"),
                scan_data.get("cost_usd"),
                scan_data.get("report_json_path"),
                scan_data.get("report_pdf_path"),
                scan_data.get("created_at"),
                scan_data.get("config_hash"),
            ),
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @staticmethod
    def get_scan(conn: sqlite3.Connection, scan_id: str) -> dict | None:
        """Fetch a single scan by ID, or ``None`` if not found."""
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scans WHERE scan_id = ?", (scan_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        result = dict(row)
        # Deserialise JSON fields
        for key in ("severity_counts", "tiers_executed"):
            val = result.get(key)
            if isinstance(val, str):
                try:
                    result[key] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
        return result

    @staticmethod
    def list_scans(
        conn: sqlite3.Connection,
        repo: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """List recent scans, optionally filtered by repository."""
        cursor = conn.cursor()
        if repo:
            cursor.execute(
                "SELECT * FROM scans WHERE repository = ? ORDER BY created_at DESC LIMIT ?",
                (repo, limit),
            )
        else:
            cursor.execute(
                "SELECT * FROM scans ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        results = []
        for row in cursor.fetchall():
            d = dict(row)
            for key in ("severity_counts", "tiers_executed"):
                val = d.get(key)
                if isinstance(val, str):
                    try:
                        d[key] = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass
            results.append(d)
        return results
