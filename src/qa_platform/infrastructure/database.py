from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = ".qa-platform.db"


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Open (or create) a SQLite database and return the connection."""
    path = db_path or _DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes if they do not already exist."""
    cursor = conn.cursor()
    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS scans (
            scan_id         TEXT PRIMARY KEY,
            repository      TEXT NOT NULL,
            branch          TEXT,
            commit_sha      TEXT,
            trigger_type    TEXT,
            tiers_executed  TEXT,
            finding_count   INTEGER,
            severity_counts TEXT,
            gate_status     TEXT,
            duration_seconds REAL,
            cost_usd        REAL,
            report_json_path TEXT,
            report_pdf_path  TEXT,
            created_at      TEXT,
            config_hash     TEXT
        );

        CREATE TABLE IF NOT EXISTS findings (
            finding_id          TEXT PRIMARY KEY,
            scan_id             TEXT NOT NULL REFERENCES scans(scan_id),
            source              TEXT NOT NULL,
            tier                INTEGER,
            category            TEXT,
            severity            TEXT,
            confidence          TEXT,
            classification      TEXT,
            file_path           TEXT,
            start_line          INTEGER,
            end_line            INTEGER,
            title               TEXT,
            explanation         TEXT,
            recommendation      TEXT,
            cwe                 TEXT,
            validation_status   TEXT,
            validation_reasoning TEXT,
            lifecycle_state     TEXT DEFAULT 'open',
            author_name         TEXT,
            author_email        TEXT,
            first_seen_at       TEXT,
            last_seen_at        TEXT,
            resolved_at         TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_findings_scan
            ON findings(scan_id);
        CREATE INDEX IF NOT EXISTS idx_findings_file
            ON findings(file_path);
        CREATE INDEX IF NOT EXISTS idx_findings_severity
            ON findings(severity);

        CREATE TABLE IF NOT EXISTS suppressions (
            suppression_id TEXT PRIMARY KEY,
            pattern        TEXT NOT NULL,
            file_scope     TEXT,
            reason         TEXT NOT NULL,
            approved_by    TEXT,
            approved_at    TEXT,
            expires_at     TEXT,
            finding_count  INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            log_id        TEXT PRIMARY KEY,
            scan_id       TEXT,
            agent_name    TEXT,
            model         TEXT,
            prompt_hash   TEXT,
            input_tokens  INTEGER,
            output_tokens INTEGER,
            cost_usd      REAL,
            duration_ms   INTEGER,
            finding_ids   TEXT,
            timestamp     TEXT,
            status        TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_audit_scan
            ON audit_log(scan_id);

        CREATE TABLE IF NOT EXISTS gate_overrides (
            override_id TEXT PRIMARY KEY,
            scan_id     TEXT,
            approved_by TEXT NOT NULL,
            reason      TEXT NOT NULL,
            expires_at  TEXT NOT NULL,
            created_at  TEXT
        );
        """
    )
    conn.commit()
