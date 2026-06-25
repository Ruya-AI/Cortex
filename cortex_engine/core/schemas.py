from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from cortex_engine.core.finding import Finding


# ---------------------------------------------------------------------------
# Diff / change-set schemas
# ---------------------------------------------------------------------------


@dataclass
class FileDiff:
    """Raw diff information for a single file."""

    file_path: str
    added_lines: list[int] = field(default_factory=list)
    deleted_lines: list[int] = field(default_factory=list)
    diff_text: str = ""
    is_new_file: bool = False
    is_deleted_file: bool = False
    is_renamed: bool = False
    old_path: str | None = None


@dataclass
class FileChange:
    """A single file that changed in a commit or PR."""

    file_path: str
    diff: FileDiff | None = None
    is_new: bool = False
    is_deleted: bool = False
    is_renamed: bool = False


@dataclass
class ChangeSet:
    """Aggregated set of file changes for a scan."""

    changed_files: list[FileChange] = field(default_factory=list)
    modules_detected: list[str] = field(default_factory=list)
    is_full_scan: bool = False
    lines_added: int = 0
    lines_deleted: int = 0


# ---------------------------------------------------------------------------
# File filtering / selection
# ---------------------------------------------------------------------------


@dataclass
class FileSet:
    """Result of file filtering -- which files to review and which to skip."""

    reviewable_files: list[str] = field(default_factory=list)
    skipped_binary: list[str] = field(default_factory=list)
    skipped_large: list[str] = field(default_factory=list)
    skipped_excluded: list[str] = field(default_factory=list)
    skipped_hidden: list[str] = field(default_factory=list)
    hygiene_findings: list[Finding] = field(default_factory=list)
    skip_summary: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Repository context
# ---------------------------------------------------------------------------


@dataclass
class RepositoryContext:
    """Metadata about the repository being scanned."""

    local_path: Path
    branch: str = ""
    commit_sha: str = ""
    commit_message: str = ""
    remote_url: str = ""
    is_temporary: bool = False


# ---------------------------------------------------------------------------
# Scan request / result
# ---------------------------------------------------------------------------


@dataclass
class ScanRequest:
    """Input parameters for a QA scan."""

    repo: str
    branch: str | None = None
    commit: str | None = None
    compare_to: str | None = None
    tiers: list[int] = field(default_factory=lambda: [1, 2])
    agents: list[str] | None = None
    trigger: str = "ad-hoc"
    report_formats: list[str] = field(default_factory=lambda: ["json"])
    output_path: str | None = None
    pr_number: int | None = None
    pr_title: str | None = None
    pr_author: str | None = None
    full_scan: bool = False
    cost_limit: float | None = None
    post_comment: bool = False
    github_token: str | None = None
    dry_run: bool = False


@dataclass
class ScanResult:
    """Output of a completed QA scan."""

    report_id: str = ""
    finding_count: int = 0
    severity_counts: dict[str, int] = field(default_factory=dict)
    quality_gate_status: str = "pass"
    execution_duration: float = 0.0
    execution_cost: float = 0.0
    json_path: Path | None = None
    pdf_path: Path | None = None
    executive_json_path: Path | None = None
    executive_pdf_path: Path | None = None
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Risk assessment
# ---------------------------------------------------------------------------


@dataclass
class RiskAssessment:
    """Risk scoring output for files under review."""

    high_risk_files: list[str] = field(default_factory=list)
    low_risk_files: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Tool / memory helpers
# ---------------------------------------------------------------------------


@dataclass
class ToolCallRecord:
    """Record of a single tool invocation during a scan."""

    tool_name: str
    arguments: dict = field(default_factory=dict)
    result_summary: str = ""
    timestamp: str = ""


@dataclass
class MemoryDocument:
    """A semantic-memory document provided to an agent for context."""

    name: str
    content: str
    memory_type: str = "semantic"


# ---------------------------------------------------------------------------
# Review context (per-file and grouped)
# ---------------------------------------------------------------------------


@dataclass
class FileReviewContext:
    """Context bundle for reviewing a single file."""

    file_path: str
    file_content: str
    diff_content: str | None = None
    tier1_findings: list[Finding] = field(default_factory=list)
    semantic_memory: list[MemoryDocument] = field(default_factory=list)
    repository_path: Path = field(default_factory=lambda: Path("."))


@dataclass
class FileGroupReviewContext:
    """Context bundle for reviewing a group of related files."""

    file_group: list[FileReviewContext] = field(default_factory=list)
    module_name: str | None = None


# ---------------------------------------------------------------------------
# Agent execution results
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    """Result from a single agent execution."""

    agent_name: str = ""
    findings: list[Finding] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    model_used: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)


@dataclass
class Tier1RunResult:
    """Aggregated result from Tier-1 (static tool) analysis."""

    findings: list[Finding] = field(default_factory=list)
    tool_summary: dict[str, dict] = field(default_factory=dict)
    finding_count: int = 0
    duration_seconds: float = 0.0
    tools_available: list[str] = field(default_factory=list)
    tools_skipped: list[str] = field(default_factory=list)


@dataclass
class AgentReviewResult:
    """Aggregated result from Tier-2 (agent) review."""

    findings: list[Finding] = field(default_factory=list)
    agents_used: list[str] = field(default_factory=list)
    models_used: list[dict] = field(default_factory=list)
    total_cost: float = 0.0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Validation / post-processing
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Result of the finding validation pass."""

    validated_findings: list[Finding] = field(default_factory=list)
    suppressed_findings: list[Finding] = field(default_factory=list)
    suppressed_count: int = 0


@dataclass
class FindingCluster:
    """A group of related findings sharing a common root cause."""

    cluster_id: str = ""
    root_cause: str = ""
    finding_ids: list[str] = field(default_factory=list)
    finding_count: int = 0
    systemic_recommendation: str = ""


@dataclass
class ProcessedFindings:
    """Fully processed findings after dedup, clustering, and suppression."""

    active_findings: list[Finding] = field(default_factory=list)
    suppressed_findings: list[Finding] = field(default_factory=list)
    clusters: list[FindingCluster] = field(default_factory=list)
    resolved_issues: list[dict] = field(default_factory=list)
    positive_observations: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Quality gate
# ---------------------------------------------------------------------------


@dataclass
class QualityGateResult:
    """Outcome of the quality-gate evaluation."""

    status: str = "pass"
    mode: str = "shadow"
    severity_counts: dict[str, int] = field(default_factory=dict)
    blocking_findings: list[str] = field(default_factory=list)
    reasoning: str = ""
    has_override: bool = False


# ---------------------------------------------------------------------------
# Integration / LLM
# ---------------------------------------------------------------------------


@dataclass
class IntegrationResult:
    """Result of posting findings to an external integration."""

    target_name: str = ""
    status: str = "skipped"
    details: dict = field(default_factory=dict)
    error_message: str | None = None


@dataclass
class LLMResponse:
    """Normalised response from any LLM provider."""

    content: str | dict = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    success: bool = False
    error: str | None = None
