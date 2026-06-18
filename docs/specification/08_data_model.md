# Document 08: Data Model Documentation

**QA Platform v2**
**Date**: 2026-06-18

---

## 1. Storage Strategy

| Data | Storage | Rationale |
|---|---|---|
| Scan results + findings | SQLite (or PostgreSQL) | Relational queries for history, trending |
| Report files (JSON, PDF) | Local filesystem | Path stored in DB, no DB bloat |
| Knowledge (SAST rules, CWE) | Bundled JSON files | Read-only, versioned with platform |
| Configuration | YAML in repository | Repo-specific, version-controlled |
| Agent prompts | Text files in platform | Externalized, versioned with platform |
| Audit log | Database table | Structured, queryable |
| Temporary clones | System temp directory | Auto-cleaned |

## 2. Database Schema

### Table: scans
```sql
CREATE TABLE scans (
    scan_id          TEXT PRIMARY KEY,
    repository       TEXT NOT NULL,
    branch           TEXT,
    commit_sha       TEXT,
    trigger_type     TEXT,
    tiers_executed   TEXT,    -- JSON: [1,2,3]
    finding_count    INTEGER,
    severity_counts  TEXT,    -- JSON: {"critical":0,"high":1,...}
    gate_status      TEXT,    -- pass | advisory | fail
    duration_seconds REAL,
    cost_usd         REAL,
    report_json_path TEXT,
    report_pdf_path  TEXT,
    created_at       TEXT,    -- ISO 8601
    config_hash      TEXT
);
```

### Table: findings
```sql
CREATE TABLE findings (
    finding_id           TEXT PRIMARY KEY,
    scan_id              TEXT NOT NULL REFERENCES scans(scan_id),
    source               TEXT NOT NULL,
    tier                 INTEGER,
    category             TEXT,
    severity             TEXT,
    confidence           TEXT,
    classification       TEXT,
    file_path            TEXT,
    start_line           INTEGER,
    end_line             INTEGER,
    title                TEXT,
    explanation          TEXT,
    recommendation       TEXT,
    cwe                  TEXT,
    validation_status    TEXT,
    validation_reasoning TEXT,
    lifecycle_state      TEXT DEFAULT 'open',
    author_name          TEXT,
    author_email         TEXT,
    first_seen_at        TEXT,
    last_seen_at         TEXT,
    resolved_at          TEXT
);
CREATE INDEX idx_findings_scan ON findings(scan_id);
CREATE INDEX idx_findings_file ON findings(file_path);
CREATE INDEX idx_findings_severity ON findings(severity);
CREATE INDEX idx_findings_lifecycle ON findings(lifecycle_state);
```

### Table: suppressions
```sql
CREATE TABLE suppressions (
    suppression_id TEXT PRIMARY KEY,
    pattern        TEXT NOT NULL,
    file_scope     TEXT,
    reason         TEXT NOT NULL,
    approved_by    TEXT,
    approved_at    TEXT,
    expires_at     TEXT,
    finding_count  INTEGER DEFAULT 0
);
```

### Table: audit_log
```sql
CREATE TABLE audit_log (
    log_id       TEXT PRIMARY KEY,
    scan_id      TEXT REFERENCES scans(scan_id),
    agent_name   TEXT,
    model        TEXT,
    prompt_hash  TEXT,    -- SHA-256 of prompt (not the prompt itself)
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd     REAL,
    duration_ms  INTEGER,
    finding_ids  TEXT,    -- JSON array
    timestamp    TEXT,
    status       TEXT     -- success | error | timeout | circuit_breaker
);
CREATE INDEX idx_audit_scan ON audit_log(scan_id);
```

### Table: gate_overrides
```sql
CREATE TABLE gate_overrides (
    override_id TEXT PRIMARY KEY,
    scan_id     TEXT,
    approved_by TEXT NOT NULL,
    reason      TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    created_at  TEXT
);
```

## 3. Data Ownership

| Data | Owner | Readers |
|---|---|---|
| Scan metadata | Orchestrator | Reports, Integrations, History |
| Findings | Finding sources (tools, agents) | Validator, FindingManager, Reports, Integrations |
| Validation verdicts | Validator Agent | FindingManager, Reports |
| Gate decisions | QualityGate | Reports, Integrations |
| Audit entries | LLM Client | Compliance, Debugging |
| Configuration | ConfigManager | All (read-only) |

## 4. No LLM Response Cache

Rationale: LLM responses depend on file content that changes between scans. A cached "no issues" for a changed file is a false negative. Risk scorer already prevents unnecessary LLM calls.

## 5. Audit Trail

Every LLM call logs: scan_id, agent_name, model, prompt_hash (SHA-256), input/output tokens, cost, finding_ids produced, timestamp, status. Prompt hash enables correlation without storing sensitive code.
