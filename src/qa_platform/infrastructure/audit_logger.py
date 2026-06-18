from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SQLiteAuditLogger:
    """Append-only audit log for LLM calls made during scans."""

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    @staticmethod
    def log_call(
        conn: sqlite3.Connection,
        scan_id: str,
        agent_name: str,
        model: str,
        prompt_hash: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        finding_ids: list[str] | None = None,
        status: str = "success",
        duration_ms: int = 0,
    ) -> str:
        """Record a single LLM invocation. Returns the generated log_id."""
        log_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        ids_json = json.dumps(finding_ids) if finding_ids else "[]"

        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO audit_log (
                log_id, scan_id, agent_name, model,
                prompt_hash, input_tokens, output_tokens,
                cost_usd, duration_ms, finding_ids,
                timestamp, status
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?
            )
            """,
            (
                log_id,
                scan_id,
                agent_name,
                model,
                prompt_hash,
                input_tokens,
                output_tokens,
                cost,
                duration_ms,
                ids_json,
                now,
                status,
            ),
        )
        conn.commit()
        return log_id

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @staticmethod
    def get_audit_trail(
        conn: sqlite3.Connection,
        scan_id: str,
    ) -> list[dict]:
        """Return all audit entries for a given scan, ordered by timestamp."""
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM audit_log WHERE scan_id = ? ORDER BY timestamp ASC",
            (scan_id,),
        )
        results = []
        for row in cursor.fetchall():
            d = dict(row)
            # Deserialise finding_ids
            val = d.get("finding_ids")
            if isinstance(val, str):
                try:
                    d["finding_ids"] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
            results.append(d)
        return results
