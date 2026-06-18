# QA Platform v2 — Domain and Class-Level Design Specification

**Document Type**: Implementation-Ready Technical Design
**Status**: Design — No Implementation
**Date**: 2026-06-18
**Author Role**: Senior Software Architect
**Input**: Architecture Design Specification (02), Engineering Planning Document (01)

---

# Part 1: Domain Model Overview

## 1.1 Domain Map

The platform is decomposed into 7 bounded domains. Each domain owns its entities, defines its interfaces, and communicates with other domains through explicit contracts (data transfer objects and interfaces).

```
┌─────────────────────────────────────────────────────────────┐
│                     CORE LAYER                              │
│  (No external dependencies — pure domain logic)             │
│                                                             │
│  ┌───────────┐  ┌───────────┐  ┌───────────────────────┐   │
│  │ Finding    │  │ Agent     │  │ Tool                  │   │
│  │ Domain    │  │ Domain    │  │ Domain                │   │
│  │           │  │           │  │                       │   │
│  │ Finding   │  │ AgentSpec │  │ ToolSpec              │   │
│  │ Severity  │  │ AgentRole │  │ ToolResult            │   │
│  │ Confidence│  │ Memory    │  │                       │   │
│  │ Category  │  │ ToolSet   │  │                       │   │
│  └───────────┘  └───────────┘  └───────────────────────┘   │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Shared Kernel: FindingSchema, ScanRequest, ScanResult │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   APPLICATION LAYER                         │
│  (Orchestrates domain logic — depends on Core only)         │
│                                                             │
│  ┌──────────────┐  ┌────────────────┐  ┌────────────────┐  │
│  │ Orchestration │  │ Assessment     │  │ Reporting      │  │
│  │ Domain        │  │ Domain         │  │ Domain         │  │
│  └──────────────┘  └────────────────┘  └────────────────┘  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  INFRASTRUCTURE LAYER                       │
│  (Implements Core interfaces — depends inward)              │
│                                                             │
│  ┌───────────┐  ┌──────────┐  ┌────────────┐  ┌─────────┐ │
│  │ Repository │  │ LLM      │  │ Integration│  │ Config  │ │
│  │ Access     │  │ Client   │  │ Layer      │  │ Manager │ │
│  └───────────┘  └──────────┘  └────────────┘  └─────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 1.2 Dependency Rules

1. **Core layer** has ZERO external dependencies. It defines interfaces (abstract classes / protocols) that infrastructure implements.
2. **Application layer** depends on Core only. It orchestrates domain logic through Core interfaces.
3. **Infrastructure layer** depends on Core (implements its interfaces) and external libraries (anthropic, httpx, git, etc.).
4. **Interface layer** (CLI) depends on Application layer only.

Dependencies always point inward: Interface → Application → Core ← Infrastructure.

---

# Part 2: Domain Specifications

---

## Domain 1: Finding Domain

### Purpose
The central domain of the entire system. Defines the universal Finding entity — the data contract that every component produces, processes, and consumes. All tools, agents, validators, reporters, and integrations operate on Findings.

### Business Responsibility
Represent a discovered code quality or security issue with full context: what is wrong, where it is, why it matters, who introduced it, how to fix it, and how confident we are.

### Key Entities

#### Entity: `Finding`

| Property | Type | Description |
|---|---|---|
| `id` | `str` | Unique identifier, assigned by FindingManager. Format: `F-<scan_short_id>-<seq>` |
| `source` | `str` | Name of the agent or tool that produced this finding |
| `tier` | `int` | Analysis tier (1=deterministic, 2=per-file agent, 3=cross-file agent) |
| `category` | `FindingCategory` | correctness, security, design, consistency, hygiene |
| `severity` | `Severity` | critical, high, medium, low, info |
| `confidence` | `Confidence` | confirmed, likely, uncertain |
| `classification` | `Classification` | introduced, modified, pre_existing, unclassified |
| `file` | `str` | Relative file path from repository root |
| `start_line` | `int` | Starting line number (1-based, clamped to file length) |
| `end_line` | `int` | Ending line number (>= start_line, clamped to file length) |
| `title` | `str` | Concise description, max 120 characters |
| `explanation` | `str` | Detailed explanation with evidence |
| `evidence` | `Evidence` | Tool calls, code references, metrics that support this finding |
| `recommendation` | `str` | Concrete, actionable fix description |
| `cwe` | `str | None` | CWE identifier for security findings (e.g., "CWE-89") |
| `author` | `AuthorAttribution | None` | Who introduced the code (from git blame) |
| `code_under_review` | `str` | Code snippet with line numbers and markers |
| `validation_status` | `ValidationStatus` | confirmed, likely, uncertain, suppressed, unvalidated |
| `validation_reasoning` | `str` | Validator's reasoning for its verdict |
| `suppression_key` | `str` | Pattern for matching against suppression rules |
| `lifecycle_state` | `LifecycleState` | open, resolved, suppressed |
| `first_seen` | `datetime` | When this finding was first detected |
| `last_seen` | `datetime` | Most recent scan that detected this finding |
| `related_findings` | `list[str]` | IDs of related findings (same cluster) |
| `root_cause_cluster` | `str | None` | Cluster ID if part of a group |

#### Value Object: `Severity`
Enum: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`

Ordering: CRITICAL > HIGH > MEDIUM > LOW > INFO

#### Value Object: `Confidence`
Enum: `CONFIRMED`, `LIKELY`, `UNCERTAIN`

`CONFIRMED` = independently verified by Validator Agent or deterministic tool.
`LIKELY` = reported by detection agent, not refuted by Validator.
`UNCERTAIN` = evidence is ambiguous or validation was not performed.

#### Value Object: `FindingCategory`
Enum: `CORRECTNESS`, `SECURITY`, `DESIGN`, `CONSISTENCY`, `HYGIENE`

Maps to agent responsibility: Correctness Agent → CORRECTNESS, Security Agent → SECURITY, Design Agent → DESIGN, Cross-File Agent → CONSISTENCY, Hygiene Checker → HYGIENE.

#### Value Object: `ValidationStatus`
Enum: `CONFIRMED`, `LIKELY`, `UNCERTAIN`, `SUPPRESSED`, `UNVALIDATED`

`UNVALIDATED` = Validator did not process this finding (LLM failure, timeout, or Tier 1 finding bypassing validation).

#### Value Object: `Evidence`
```
tool_calls: list[str]       — Tool invocations that support this finding
code_references: list[str]  — Specific code locations referenced as evidence
metrics: dict[str, Any]     — Quantitative data (complexity score, line count, etc.)
```

#### Value Object: `AuthorAttribution`
```
name: str
email: str
github_username: str | None
attribution_source: str     — "git-blame", "pr-author", "commit-author", "default"
```

#### Value Object: `Classification`
Enum: `INTRODUCED`, `MODIFIED`, `PRE_EXISTING`, `UNCLASSIFIED`

### Aggregates

**FindingSet**: An ordered collection of Findings from a single scan. The aggregate root for finding operations (dedup, cluster, rank, filter).

### Services

#### `FindingFactory`
- **Purpose**: Create well-formed Finding instances with validation
- **Methods**:
  - `create_from_tool(tool_name, file, start_line, end_line, severity, category, title, explanation, recommendation) → Finding` — Creates a Tier 1 finding with defaults for agent-specific fields
  - `create_from_agent(agent_name, tier, category, file, start_line, end_line, severity, title, explanation, evidence, recommendation, cwe?) → Finding` — Creates an agent finding with full evidence
- **Validation**: Clamps line numbers to actual file length. Enforces title length. Validates severity/confidence enums.

#### `FindingDeduplicator`
- **Purpose**: Remove duplicate findings from the FindingSet
- **Methods**:
  - `deduplicate(findings: list[Finding]) → list[Finding]` — Removes duplicates by matching: same file + overlapping line range (±3 lines) + similar title (>0.8 cosine similarity or exact suppression_key match). Keeps the finding with highest confidence. Merges evidence from duplicates into the surviving finding.

#### `FindingClusterer`
- **Purpose**: Group related findings by root cause
- **Methods**:
  - `cluster(findings: list[Finding]) → list[FindingCluster]` — Groups by suppression_key prefix + file proximity. Each cluster has a cluster_id, root_cause description, and member finding IDs.

#### `FindingRanker`
- **Purpose**: Sort findings by priority for developer attention
- **Methods**:
  - `rank(findings: list[Finding]) → list[Finding]` — Sort order: severity (desc) → confidence (desc) → classification (introduced first) → file path (alpha)

#### `FindingLineValidator`
- **Purpose**: Ensure all finding line numbers are within actual file boundaries
- **Methods**:
  - `validate(findings: list[Finding], repo_path: Path) → None` — Mutates findings in place: clamps start_line and end_line to [1, file_line_count]. Uses a file-line-count cache to avoid re-reading files.

### Repositories

#### `FindingRepository` (interface)
- `save_findings(scan_id: str, findings: list[Finding]) → None`
- `get_findings_by_scan(scan_id: str) → list[Finding]`
- `get_findings_by_file(file_path: str, limit: int) → list[Finding]`
- `get_finding_history(suppression_key: str) → list[Finding]`
- `update_lifecycle_state(finding_id: str, state: LifecycleState) → None`

### Events

| Event | When | Data |
|---|---|---|
| `FindingCreated` | Finding factory produces a new finding | finding_id, source, severity, file |
| `FindingValidated` | Validator assigns a verdict | finding_id, validation_status, reasoning |
| `FindingSuppressed` | Suppression rule matches | finding_id, suppression_rule_id |
| `FindingResolved` | Lifecycle transitions to resolved | finding_id, resolved_at |

### External Dependencies
None. This is a Core domain. All types are pure Python. No external libraries.

---

## Domain 2: Agent Domain

### Purpose
Define the contract for all agentic components — what an agent is, what it receives, what it produces, and how it operates. This domain provides interfaces that concrete agent implementations fulfill.

### Business Responsibility
Enable specialized AI-powered code review through autonomous agents that plan, explore, reason, and verify — producing findings that deterministic tools cannot.

### Key Entities

#### Interface: `ReviewAgent` (Abstract)
```
Properties:
  name: str                    — Unique agent identifier
  tier: int                    — 2 (per-file) or 3 (cross-file)
  category: FindingCategory    — Primary finding category this agent produces
  cognitive_mode: str          — "constructive", "adversarial", "evaluative", "comparative", "skeptical"

Methods:
  review_file(context: FileReviewContext) → AgentResult
    — Review a single file and produce findings.
    — The agent operates in its observation-action loop within this method.
    — Must return structured findings matching the Finding schema.

  review_file_group(context: FileGroupReviewContext) → AgentResult
    — Review a group of files for cross-file analysis (Agent 4 only).
    — Default implementation raises NotImplementedError.

  get_system_prompt() → str
    — Return the agent's system prompt including role, workflow, and output format.
    — Loaded from external prompt file, not hardcoded.

  get_semantic_memory() → list[MemoryDocument]
    — Return the agent's semantic memory documents to include in context.
    — Loaded from bundled knowledge files.
```

#### Value Object: `FileReviewContext`
```
file_path: str                    — Relative path of the file under review
file_content: str                 — Full content of the file
diff_content: str | None          — Diff for this file (None for full audit)
tier1_findings: list[Finding]     — Tier 1 findings for this file
repository_path: Path             — Root path for tool invocations
config: dict                      — Scan configuration relevant to this agent
```

#### Value Object: `FileGroupReviewContext`
```
file_group: list[FileReviewContext]  — Multiple files for cross-file analysis
module_name: str | None              — Module identifier for the group
```

#### Value Object: `AgentResult`
```
agent_name: str
findings: list[Finding]
tool_calls: list[ToolCallRecord]    — Log of all tool invocations
model_used: str
input_tokens: int
output_tokens: int
cost_usd: float
duration_seconds: float
errors: list[str]
```

#### Value Object: `ToolCallRecord`
```
tool_name: str
arguments: dict
result_summary: str                 — Truncated result for logging
timestamp: datetime
```

#### Value Object: `MemoryDocument`
```
name: str                          — Document identifier (e.g., "sast_rules", "cwe_tree")
content: str                       — Document content loaded into agent context
memory_type: str                   — "semantic", "working", "episodic"
```

### Services

#### `AgentRegistry`
- **Purpose**: Register and discover available agents
- **Pattern**: Registry pattern
- **Methods**:
  - `register(agent: ReviewAgent) → None` — Register an agent implementation
  - `get_agent(name: str) → ReviewAgent` — Retrieve by name
  - `get_agents_for_tier(tier: int) → list[ReviewAgent]` — Get all agents for a tier
  - `get_all_agents() → list[ReviewAgent]` — Get all registered agents
- **Design**: Agents register themselves at startup. The orchestrator queries the registry to determine which agents to run. Adding a new agent requires only implementing `ReviewAgent` and registering it — no orchestrator changes.

#### `AgentToolProvider`
- **Purpose**: Provide read-only tools to agents during execution
- **Pattern**: Strategy pattern
- **Methods**:
  - `read_file(path: str, start_line: int?, end_line: int?) → str`
  - `grep(pattern: str, path: str?, scope: str?) → list[GrepResult]`
  - `git_diff(file: str?, base: str?) → str`
  - `list_directory(path: str) → list[str]`
  - `expand_context(file: str, line: int, radius: int) → str`
- **Constraint**: All methods are read-only. No method can write to the filesystem. This is enforced by the interface definition — there are no write methods to call.
- **Dependencies**: Repository access layer (infrastructure)

#### `SemanticMemoryLoader`
- **Purpose**: Load knowledge documents for agent semantic memory
- **Methods**:
  - `load_sast_rules() → MemoryDocument` — Load SAST rules (CodeQL patterns, CWE mappings)
  - `load_cwe_tree() → MemoryDocument` — Load CWE taxonomy tree
  - `load_project_conventions(config: QAConfig) → MemoryDocument | None` — Load from config
  - `load_design_principles() → MemoryDocument` — Load SOLID, patterns catalog
- **Storage**: Bundled JSON/YAML files in the platform package. Read-only.

### Repositories
None. Agent definitions are in-code (registered at startup), not persisted.

### Events

| Event | When | Data |
|---|---|---|
| `AgentStarted` | Agent begins review of a file | agent_name, file_path, model |
| `AgentCompleted` | Agent finishes review | agent_name, file_path, finding_count, cost, duration |
| `AgentFailed` | Agent LLM call fails | agent_name, file_path, error, fallback_action |
| `AgentSkipped` | Agent skipped (cost limit, not applicable) | agent_name, reason |

### External Dependencies (interface only — implementation in infrastructure)
- `LLMClient` (interface) — For sending prompts and receiving structured responses
- `AgentToolProvider` (interface) — For read-only code exploration

---

## Domain 3: Tool Domain

### Purpose
Define the contract for deterministic Tier 1 analysis tools and their execution.

### Business Responsibility
Execute static analysis tools in check-only mode, producing candidate findings with high recall that agents subsequently validate for precision.

### Key Entities

#### Interface: `Tier1Tool` (Abstract)
```
Properties:
  name: str              — Unique tool identifier (e.g., "ruff", "bandit", "semgrep")
  tier: int = 1          — Always 1 for deterministic tools

Methods:
  is_available() → bool
    — Check if the tool binary is installed and accessible.
    — Called at scan start to determine which tools can run.

  is_applicable(file_path: str) → bool
    — Check if this tool applies to the given file (by extension, pattern, etc.).
    — Called per file to skip inapplicable tools.

  run(file_path: str, repo_path: Path) → list[Finding]
    — Execute the tool on a single file and return findings.
    — MUST NOT modify any files.
    — MUST return findings in the universal Finding schema.
    — MUST handle tool execution errors internally (return empty list on failure).
```

#### Value Object: `ToolExecutionResult`
```
tool_name: str
findings: list[Finding]
files_scanned: int
duration_seconds: float
status: str                — "success", "skipped", "error", "timeout"
error_message: str | None
```

### Services

#### `Tier1Runner`
- **Purpose**: Execute all applicable Tier 1 tools across a file set
- **Methods**:
  - `run(repo_path: Path, file_paths: list[str], trigger: str) → Tier1RunResult`
    - Discovers available tools via `is_available()`
    - Filters applicable tools per file via `is_applicable()`
    - Executes tools with error isolation (one tool failure doesn't stop others)
    - Validates line numbers on all findings (clamp to file length)
    - Returns aggregated results with per-tool summary
- **Pattern**: Template method + Strategy (each tool implements the strategy, runner provides the template)
- **Properties**:
  - `tools: list[Tier1Tool]` — Registered tools
  - `timeout_per_tool: int` — Seconds before killing a tool execution (default: 60)

#### Value Object: `Tier1RunResult`
```
findings: list[Finding]
tool_summary: dict[str, ToolExecutionResult]  — Per-tool results
finding_count: int
duration_seconds: float
tools_available: list[str]
tools_skipped: list[str]
```

### Repositories
None. Tools are in-code implementations, not persisted.

### Events

| Event | When | Data |
|---|---|---|
| `ToolExecuted` | Tool completes on a file | tool_name, file_path, finding_count, status |
| `ToolSkipped` | Tool not available or not applicable | tool_name, reason |

### External Dependencies (interface only)
- Subprocess execution for tool binaries (infrastructure concern)

---

## Domain 4: Orchestration Domain

### Purpose
Control the end-to-end scan pipeline execution, coordinating all domains in the correct sequence.

### Business Responsibility
Accept a scan request, execute the analysis pipeline, and produce a complete scan result with reports.

### Key Entities

#### Value Object: `ScanRequest`
```
repo: str                        — Local path or remote URL
branch: str | None
commit: str | None
compare_to: str | None           — Base branch for diff comparison
tiers: list[int]                 — [1], [1,2], [1,2,3]
agents: list[str] | None        — Specific agents to run (None = all applicable)
trigger: str                     — "pr-push", "commit", "audit", "ad-hoc", "scheduled", "pre-commit"
report_formats: list[str]        — ["json"], ["json", "pdf"]
output_path: str | None
pr_number: int | None
pr_title: str | None
pr_author: str | None
full_scan: bool                  — True for audit mode (all files, not just changed)
cost_limit: float | None         — Maximum LLM spend in USD
post_comment: bool               — Post findings to GitHub PR
github_token: str | None
```

#### Value Object: `ScanResult`
```
report_id: str
finding_count: int
severity_counts: dict[str, int]
quality_gate_status: str          — "pass", "advisory", "fail"
execution_duration: float
execution_cost: float
json_path: Path | None
pdf_path: Path | None
executive_json_path: Path | None
executive_pdf_path: Path | None
errors: list[str]
```

#### Value Object: `RepositoryContext`
```
local_path: Path                 — Resolved local path (original or clone)
branch: str
commit_sha: str
commit_message: str
remote_url: str
is_temporary: bool               — True if cloned (needs cleanup)
```

#### Value Object: `FileSet`
```
reviewable_files: list[str]      — Files to analyze
skipped_binary: list[str]        — Binary files skipped
skipped_large: list[str]         — Files exceeding size limit
flagged_files: list[str]         — Files that shouldn't be committed
hygiene_findings: list[Finding]  — Hygiene violation findings
privacy_excluded: list[str]      — Files excluded by privacy config
generated_files: list[str]       — Detected generated files
```

#### Value Object: `ChangeSet`
```
changed_files: list[FileChange]
modules_detected: set[str]
is_full_scan: bool
lines_added: int
lines_deleted: int
```

#### Value Object: `FileChange`
```
file_path: str
diff: FileDiff | None
is_new: bool
is_deleted: bool
is_renamed: bool
```

### Services

#### `ScanOrchestrator`
- **Purpose**: Execute the complete scan pipeline
- **Pattern**: Facade + Pipeline
- **Properties**:
  ```
  repository_resolver: RepositoryResolver        — Interface
  change_detector: ChangeDetector                 — Interface
  hygiene_checker: HygieneChecker                — Interface
  tier1_runner: Tier1Runner
  risk_scorer: RiskScorer
  agentic_review_engine: AgenticReviewEngine
  validation_engine: ValidationEngine
  finding_manager: FindingManager
  quality_gate: QualityGate
  report_generator: ReportGenerator
  integration_dispatcher: IntegrationDispatcher   — Interface
  config_manager: ConfigManager                   — Interface
  cost_tracker: CostTracker
  ```
- **Methods**:
  - `scan(request: ScanRequest, progress: Callable[[str], None]?) → ScanResult`
    - Main entry point. Executes all pipeline phases in sequence.
    - Accepts optional progress callback for CLI feedback.
    - Handles cleanup of temporary clones in finally block.
    - Tracks cost and enforces cost_limit.
    - Never raises — returns ScanResult with errors list on partial failure.

**Sequence Flow for `scan()`**:
```
1. config = config_manager.load(repo_path)
2. repo_context = repository_resolver.resolve(request)
3. change_set = change_detector.detect(repo_context, request)
4. file_set = hygiene_checker.check(repo_context, change_set, config)
5. tier1_result = tier1_runner.run(repo_context.local_path, file_set.reviewable_files, request.trigger)
6. risk_assessment = risk_scorer.score(file_set.reviewable_files, tier1_result, config)
7. IF tiers include 2 or 3:
     agent_result = agentic_review_engine.run(
       repo_context, risk_assessment.high_risk_files, tier1_result, config, request
     )
8. all_findings = tier1_result.findings + agent_result.findings + file_set.hygiene_findings
9. IF any agent ran:
     validation_result = validation_engine.validate(all_findings, repo_context)
     all_findings = validation_result.validated_findings
10. processed = finding_manager.process(all_findings, repo_context, change_set, config)
11. gate_result = quality_gate.evaluate(processed.active_findings, config)
12. reports = report_generator.generate(processed, gate_result, repo_context, request, config)
13. IF request.post_comment:
      integration_dispatcher.dispatch(processed, gate_result, request)
14. persist_scan(scan_id, processed, gate_result)
15. cleanup temporary clone IF repo_context.is_temporary
16. RETURN ScanResult
```

#### `RiskScorer`
- **Purpose**: Determine which files warrant agent review
- **Methods**:
  - `score(files: list[str], tier1_result: Tier1RunResult, config: QAConfig) → RiskAssessment`
    - Computes per-file risk score.
    - Routes files to high-risk (agent review) or low-risk (Tier 1 only).
    - Formula: `complexity_weight × complexity + change_weight × lines_changed + sast_weight × sast_count + path_weight × path_sensitivity`
    - Returns `RiskAssessment` with categorized file lists.
- **Properties**:
  - `threshold: float` — Score threshold for high-risk classification (configurable)

#### Value Object: `RiskAssessment`
```
high_risk_files: list[str]
low_risk_files: list[str]
scores: dict[str, float]          — File → risk score
```

#### `CostTracker`
- **Purpose**: Track LLM spend across a scan and enforce limits
- **Methods**:
  - `record(agent_name: str, model: str, input_tokens: int, output_tokens: int, cost: float) → None`
  - `total_cost() → float`
  - `is_limit_reached(limit: float | None) → bool`
  - `get_summary() → dict` — Per-agent and per-model cost breakdown

### Repositories

#### `ScanRepository` (interface)
- `save_scan(scan: ScanRecord) → None`
- `get_scan(scan_id: str) → ScanRecord | None`
- `list_scans(repo: str, limit: int) → list[ScanRecord]`

### Events

| Event | When | Data |
|---|---|---|
| `ScanStarted` | Pipeline begins | scan_id, repo, trigger, tiers |
| `ScanPhaseCompleted` | A pipeline phase finishes | scan_id, phase_name, duration |
| `ScanCompleted` | Pipeline finishes | scan_id, finding_count, gate_status, duration, cost |
| `ScanFailed` | Unrecoverable error | scan_id, error |

### External Dependencies (interfaces)
- `RepositoryResolver` — Resolve repo path/URL to local path
- `ChangeDetector` — Detect file changes
- `HygieneChecker` — Check file hygiene
- `ConfigManager` — Load configuration
- `IntegrationDispatcher` — Dispatch to external services

---

## Domain 5: Assessment Domain

### Purpose
Evaluate scan findings against quality thresholds and produce pass/fail decisions.

### Business Responsibility
Enforce quality standards through configurable gates that protect production from critical issues while allowing teams to calibrate strictness over time.

### Key Entities

#### Value Object: `QualityGateResult`
```
status: str                      — "pass", "advisory", "fail"
mode: str                        — "shadow", "advisory", "enforced"
severity_counts: dict[str, int]
blocking_findings: list[str]     — Finding IDs that caused a fail
reasoning: str                   — Human-readable explanation
has_override: bool
override_details: OverrideInfo | None
```

#### Value Object: `GateThresholds`
```
max_critical: int                — Default: 0
max_high: int                    — Default: 0
max_medium: int | None           — None = unlimited
max_low: int | None              — None = unlimited
required_confidence: Confidence  — Minimum confidence to count toward gate
```

#### Value Object: `OverrideInfo`
```
approved_by: str
reason: str
expires_at: datetime
created_at: datetime
```

### Services

#### `QualityGate`
- **Purpose**: Evaluate findings against thresholds and produce gate decision
- **Methods**:
  - `evaluate(findings: list[Finding], config: QAConfig) → QualityGateResult`
    - Counts findings by severity, filtering by minimum confidence.
    - Compares counts against thresholds for the configured mode (shadow/advisory/enforced).
    - Checks for valid override if gate would fail.
    - Shadow mode: always returns "pass" but logs what would have happened.
    - Advisory mode: returns "advisory" on threshold breach (warning, not blocking).
    - Enforced mode: returns "fail" on threshold breach.
- **Properties**: None (stateless pure function — all config from QAConfig)
- **Pattern**: Strategy (gate mode determines evaluation strategy)

### Repositories

#### `OverrideRepository` (interface)
- `save_override(override: OverrideInfo) → None`
- `get_active_override(scan_id: str) → OverrideInfo | None`
- `expire_overrides() → int` — Expire overrides past their expiry date

### Events

| Event | When | Data |
|---|---|---|
| `GateEvaluated` | Gate runs | status, mode, severity_counts |
| `GateOverrideApplied` | Override changes gate result | override_id, approved_by |

### External Dependencies
None. Pure domain logic.

---

## Domain 6: Reporting Domain

### Purpose
Transform scan results into human-readable and machine-readable reports.

### Business Responsibility
Present findings clearly and actionably — enabling developers to understand what's wrong, why it matters, and how to fix it.

### Key Entities

#### Value Object: `ReportData`
```
report_metadata: ReportMetadata
repository_context: dict
attribution: dict
scope_summary: dict
executive_summary: ExecutiveSummary
findings: list[Finding]
finding_clusters: list[FindingCluster]
resolved_issues: list[dict]
positive_observations: list[str]
suppressed_findings: list[dict]
appendix: ReportAppendix
```

#### Value Object: `ReportMetadata`
```
report_id: str
generated_at: datetime
trigger: str
platform_version: str
models_used: list[dict]
execution_duration_seconds: float
execution_cost_usd: float
```

#### Value Object: `ExecutiveSummary`
```
verdict: str
risk_level: str                  — "CRITICAL", "HIGH", "MEDIUM", "LOW", "CLEAN"
quality_gate_status: str
finding_counts_by_severity: dict
actionable_count: int
noise_removed_percentage: str
must_fix: list[ActionItem]
should_fix: list[ActionItem]
consider: list[ActionItem]
```

#### Value Object: `ActionItem`
```
source: str
severity: str
category: str
file: str
line: int
issue: str
action: str                      — Full recommendation text, no truncation
```

#### Value Object: `ReportResult`
```
report_id: str
report_data: ReportData
json_path: Path | None
pdf_path: Path | None
executive_json_path: Path | None
executive_pdf_path: Path | None
```

### Services

#### `ReportGenerator`
- **Purpose**: Build report data structure and serialize to output formats
- **Methods**:
  - `generate(findings, gate_result, repo_context, scan_metadata, config) → ReportResult`
    - Builds full report data structure (11 sections)
    - Serializes to JSON
    - Renders HTML and converts to PDF (via WeasyPrint)
    - Sanitizes control characters for PDF output
  - `_build_report_data(...) → ReportData` — Assemble the 11-section structure
  - `_render_html(report_data: ReportData) → str` — HTML template rendering
  - `_write_pdf(html: str, path: Path) → None` — WeasyPrint conversion with fallback
- **Pattern**: Builder (assembles report data) + Template Method (rendering)

#### `ExecutiveReportGenerator`
- **Purpose**: Generate a concise, actionable executive report from the full report
- **Methods**:
  - `generate(full_report: ReportData, output_dir: Path, formats: list[str]) → ExecutiveReportResult`
    - Curates findings (filters low-confidence, low-severity, pre-existing non-critical)
    - Produces action items table with FULL text (no truncation)
    - Computes noise reduction metrics
    - Generates PDF with proper column widths and word-wrap

### Services (shared)

#### `TextSanitizer`
- **Purpose**: Strip control characters from text before PDF rendering
- **Methods**:
  - `sanitize(text: str) → str` — Remove `[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]`, preserve tab/newline/CR
- **Used by**: ReportGenerator, ExecutiveReportGenerator — applied to all text entering HTML templates

### Repositories
None. Reports are written to filesystem, not to a database.

### Events
None. Report generation is a terminal step.

### External Dependencies
- WeasyPrint (optional, for PDF generation)
- File system (for writing output files)

---

## Domain 7: Integration Domain

### Purpose
Connect the platform to external services for finding delivery and notification.

### Business Responsibility
Deliver scan results to where developers work — PR comments, issue trackers, chat notifications.

### Key Entities

#### Interface: `IntegrationTarget` (Abstract)
```
Methods:
  is_configured() → bool
    — Check if credentials and configuration are present.

  dispatch(findings: list[Finding], gate_result: QualityGateResult,
           scan_metadata: dict, config: QAConfig) → IntegrationResult
    — Send findings to the external service.
    — Must handle its own errors (never crash the scan pipeline).
```

#### Value Object: `IntegrationResult`
```
target_name: str
status: str                     — "success", "partial", "skipped", "error"
details: dict                   — Target-specific details (comment IDs, issue IDs, etc.)
error_message: str | None
```

### Services

#### `IntegrationDispatcher`
- **Purpose**: Dispatch scan results to all configured integration targets
- **Pattern**: Observer / Chain of Responsibility
- **Methods**:
  - `dispatch(findings, gate_result, scan_metadata, config) → list[IntegrationResult]`
    - Iterates over all registered IntegrationTargets
    - Calls `dispatch()` on each that `is_configured()`
    - Collects results — one target's failure doesn't affect others
    - Returns list of all results

#### Concrete Targets (Infrastructure Layer)

**`GitHubIntegration` implements `IntegrationTarget`**:
- `post_pr_summary_comment(findings, gate_result, pr_number, token)`
- `post_inline_comments(findings, pr_number, token)` — On specific file:line in diff
- `set_commit_status(gate_result, commit_sha, token)`

**`LinearIntegration` implements `IntegrationTarget`**:
- `create_parent_issue(scan_metadata)`
- `create_sub_issues(findings, parent_id)` — One per finding, up to configurable max
- `assign_to_developer(issue_id, developer_email)`

**`SlackIntegration` implements `IntegrationTarget`**:
- `send_webhook(summary_message, webhook_url)`

### Repositories
None. Integrations are stateless — they push data to external services.

### Events

| Event | When | Data |
|---|---|---|
| `IntegrationDispatched` | A target completes | target_name, status |
| `IntegrationFailed` | A target fails | target_name, error |

### External Dependencies
- GitHub REST API (httpx)
- Linear GraphQL API (httpx)
- Slack Incoming Webhook (httpx)

---

# Part 3: Infrastructure Implementations

These classes implement the interfaces defined in Core domains.

## Repository Access Layer

#### `GitRepositoryResolver` implements `RepositoryResolver`
- **Purpose**: Resolve local paths and remote URLs to local repository paths
- **Methods**:
  - `resolve(request: ScanRequest) → RepositoryContext`
    - If local path: validate it's a git repo, extract metadata
    - If remote URL: clone to temp directory (shallow, configurable depth)
    - If commit specified: checkout that commit
    - If PR specified: resolve PR number to branch
  - `cleanup(context: RepositoryContext) → None` — Remove temporary clone if is_temporary

#### `GitChangeDetector` implements `ChangeDetector`
- **Methods**:
  - `detect(context: RepositoryContext, request: ScanRequest) → ChangeSet`
    - Full scan: list all files in repository
    - Diff scan: `git diff base...head` to get changed files with hunks
    - Parse diff output into FileChange objects with line-level tracking

#### `GitOperations`
- **Purpose**: Wrapper around git subprocess calls
- **Methods**:
  - `clone(url, branch?, depth?, target_dir?) → CloneResult`
  - `diff(repo_path, base?, head?, staged?) → list[FileDiff]`
  - `blame(repo_path, file_path, start_line, end_line) → list[BlameEntry]`
  - `log(repo_path, file_path?, count?) → list[CommitInfo]`
  - `get_config(repo_path, key) → str` — Silent on failure (no warning log)
  - `get_current_branch(repo_path) → str`
  - `get_current_commit(repo_path) → str`
- **All methods**: Use `errors="replace"` for Unicode handling. Configurable timeout.

#### `HygieneChecker` implements `HygieneChecker`
- **Methods**:
  - `check(context: RepositoryContext, change_set: ChangeSet, config: QAConfig) → FileSet`
    - Detect binary files by extension and content sniffing
    - Detect large files by size threshold (configurable, default 10MB)
    - Detect flagged files (node_modules, .env, __pycache__)
    - Apply privacy exclusion paths from config
    - Detect generated code by markers and path patterns
    - Classify each file: reviewable, skipped, or flagged

## LLM Infrastructure

#### `AnthropicLLMClient` implements `LLMClient`
- **Purpose**: Managed interface to Claude API with reliability features
- **Properties**:
  ```
  primary_model: str
  fallback_models: list[str]
  temperature: float = 0.0
  max_retries: int = 3
  circuit_breaker_threshold: int = 5
  _consecutive_failures: int = 0
  _total_cost: float = 0.0
  _total_tokens: tuple[int, int] = (0, 0)
  _call_count: int = 0
  ```
- **Methods**:
  - `call(system_prompt: str, user_message: str, output_schema: dict | None, model: str | None) → LLMResponse`
    - Check circuit breaker (if open, return failure immediately)
    - Attempt primary model
    - On failure: retry with backoff, then try fallback models
    - On success: reset circuit breaker counter, track tokens/cost
    - On all failures: open circuit breaker if threshold reached
    - Return structured response or failure indicator
  - `total_cost → float`
  - `total_tokens → tuple[int, int]`
  - `call_count → int`

#### Value Object: `LLMResponse`
```
content: str | dict              — Raw text or parsed structured output
model: str                       — Model that actually responded
input_tokens: int
output_tokens: int
cost_usd: float
success: bool
error: str | None
```

## Persistence

#### `SQLiteFindingRepository` implements `FindingRepository`
- Standard SQLite implementation of the finding repository interface
- Uses `sqlite3` stdlib module, no ORM for simplicity
- Schema matches the database design in the architecture spec

#### `SQLiteScanRepository` implements `ScanRepository`
- Scan metadata persistence
- Used for history and trending queries

#### `SQLiteAuditLogger`
- **Purpose**: Persist LLM call audit entries
- **Methods**:
  - `log_call(scan_id, agent_name, model, prompt_hash, tokens, cost, finding_ids, status)`
  - `get_audit_trail(scan_id) → list[AuditEntry]`

## Configuration

#### `YAMLConfigManager` implements `ConfigManager`
- **Methods**:
  - `load(repo_path: Path) → QAConfig`
    - Read `.qa-config.yml` from repository root
    - Validate against Pydantic schema
    - Return defaults if file absent
    - Resolve environment variable references (`${ENV_VAR}`)

---

# Part 4: Concrete Agent Implementations

Each agent extends the `ReviewAgent` interface from the Agent Domain.

## Agent 1: `CorrectnessAgent`

| Field | Detail |
|---|---|
| **Purpose** | Detect logic bugs, correctness errors, edge cases, error handling failures |
| **Properties** | `name = "correctness"`, `tier = 2`, `category = CORRECTNESS`, `cognitive_mode = "constructive"` |
| **System prompt source** | `prompts/correctness_agent.txt` |
| **Semantic memory** | Project coding conventions (from config) |
| **review_file(context)** | Sends system prompt + file content + diff + Tier 1 findings to LLM. The prompt instructs a 3-pass review (scan → investigate → verify). Agent can invoke tools via structured tool-use protocol. Returns parsed findings. |
| **Output schema** | JSON array of findings with: file, start_line, end_line, severity, title, explanation, evidence, recommendation |

## Agent 2: `SecurityAgent`

| Field | Detail |
|---|---|
| **Purpose** | Validate SAST findings, detect security vulnerabilities, classify by CWE, provide remediation |
| **Properties** | `name = "security"`, `tier = 2`, `category = SECURITY`, `cognitive_mode = "adversarial"` |
| **System prompt source** | `prompts/security_agent.txt` |
| **Semantic memory** | SAST rules (CodeQL patterns + CWE mappings), CWE taxonomy tree |
| **review_file(context)** | Receives SAST findings as structured input. Prompt instructs adversarial reasoning: trace taint paths, validate each SAST finding as TP/FP. For TPs: CWE + remediation. For FPs: documented reasoning. |
| **Fail-open** | If LLM call fails, ALL SAST findings for the file are returned as-is with `validation_status = UNVALIDATED` |

## Agent 3: `DesignAgent`

| Field | Detail |
|---|---|
| **Purpose** | Evaluate code structure, identify maintainability issues, suggest improvements |
| **Properties** | `name = "design"`, `tier = 2`, `category = DESIGN`, `cognitive_mode = "evaluative"` |
| **System prompt source** | `prompts/design_agent.txt` |
| **Semantic memory** | Design principles (SOLID, patterns), project conventions |
| **review_file(context)** | Evaluates structural quality: complexity, coupling, naming, abstraction, test adequacy, documentation. Each suggestion includes what to change, why, and an example. |

## Agent 4: `CrossFileAgent`

| Field | Detail |
|---|---|
| **Purpose** | Detect consistency issues and systemic patterns across module boundaries |
| **Properties** | `name = "cross_file"`, `tier = 3`, `category = CONSISTENCY`, `cognitive_mode = "comparative"` |
| **System prompt source** | `prompts/cross_file_agent.txt` |
| **Semantic memory** | Module boundary definitions (derived at scan time from project structure) |
| **review_file_group(context)** | Receives a group of related files (e.g., all controllers). Compares patterns across them. Identifies inconsistencies, missing implementations, broken contracts. |
| **Execution condition** | Only runs when trigger is "audit" OR changed files span 3+ modules |

## Agent 5: `ValidatorAgent`

| Field | Detail |
|---|---|
| **Purpose** | Adversarially challenge findings, filter false positives, assign confidence |
| **Properties** | `name = "validator"`, `tier = 2`, `category = None (cross-cutting)`, `cognitive_mode = "skeptical"` |
| **System prompt source** | `prompts/validator_agent.txt` |
| **Semantic memory** | Common false positive patterns, validation criteria |
| **Model** | Claude Opus (different from detection agents for model diversity) |
| **validate(findings, repo_context) → list[ValidatedFinding]** | Processes findings in batches. For each finding: re-reads the code, tries to REFUTE it, checks if evidence is accurate, assigns validation_status + reasoning. Resolves semantic duplicates across agents. |
| **Fail-open** | If LLM fails, ALL findings retained with `validation_status = UNVALIDATED` |

---

# Part 5: Agentic Review Engine

#### `AgenticReviewEngine`
- **Purpose**: Manage agent execution lifecycle
- **Properties**:
  ```
  agent_registry: AgentRegistry
  tool_provider: AgentToolProvider
  memory_loader: SemanticMemoryLoader
  llm_client: LLMClient
  cost_tracker: CostTracker
  max_parallel: int = 3             — Max concurrent agent executions per file
  ```
- **Methods**:
  - `run(repo_context, high_risk_files, tier1_result, config, request) → AgentReviewResult`
    1. Get applicable agents from registry for requested tiers
    2. Load semantic memory for each agent
    3. For each high-risk file:
       a. Build `FileReviewContext` with file content, diff, Tier 1 findings
       b. Execute Agents 1, 2, 3 in parallel (asyncio.gather or thread pool)
       c. Collect findings, handle failures per-agent (fail-open)
       d. Check cost limit after each file
    4. If cross-file analysis warranted:
       a. Group files by module
       b. Execute Agent 4 per module group
    5. Aggregate all agent findings
    6. Return `AgentReviewResult`

#### `ValidationEngine`
- **Purpose**: Manage the Finding Validator Agent execution
- **Properties**:
  ```
  validator_agent: ValidatorAgent
  llm_client: LLMClient           — Separate client instance with Opus model
  batch_size: int = 15
  ```
- **Methods**:
  - `validate(all_findings: list[Finding], repo_context: RepositoryContext) → ValidationResult`
    1. Batch findings into groups of `batch_size`
    2. For each batch: invoke ValidatorAgent
    3. Collect validation verdicts
    4. On batch failure: mark all findings in batch as UNVALIDATED (fail-open)
    5. Return `ValidationResult` with validated + unvalidated findings

---

# Part 6: Finding Management Pipeline

#### `FindingManager`
- **Purpose**: Orchestrate all deterministic post-processing of findings
- **Methods**:
  - `process(findings, repo_context, change_set, config) → ProcessedFindings`
    1. `FindingLineValidator.validate(findings, repo_path)` — Clamp line numbers
    2. `FindingDeduplicator.deduplicate(findings)` — Remove duplicates
    3. `DiffClassifier.classify(findings, change_set)` — Mark introduced/modified/pre-existing
    4. `AuthorAttributor.attribute(findings, repo_context, config)` — Git blame
    5. `SnippetExtractor.extract(findings, repo_path)` — Add code snippets
    6. `SuppressionApplicator.apply(findings, config)` — Apply suppression rules
    7. `FindingClusterer.cluster(findings)` — Group by root cause
    8. `FindingRanker.rank(findings)` — Sort by priority
    9. Assign finding IDs
    10. Return `ProcessedFindings`

#### `DiffClassifier`
- **Methods**:
  - `classify(findings: list[Finding], change_set: ChangeSet) → None` — Mutates findings in place. If the finding's line range overlaps with added/modified lines in the diff → `INTRODUCED`/`MODIFIED`. Otherwise → `PRE_EXISTING`.

#### `AuthorAttributor`
- **Methods**:
  - `attribute(findings: list[Finding], repo_context: RepositoryContext, config: QAConfig) → None`
    - For each finding without an author:
      1. Pre-commit trigger → use git config user
      2. PR author + introduced classification → use PR author
      3. Otherwise → git blame on finding's line range
      4. Blame failure → fall back to configurable default author
    - Git config lookup is silent on failure (no warning log)

#### `SnippetExtractor`
- **Methods**:
  - `extract(findings: list[Finding], repo_path: Path) → None` — Reads file, extracts 3 lines above and below the finding's line range, marks flagged lines with `◄── FLAGGED`, strips control characters from each line. Mutates `code_under_review` field.

#### `SuppressionApplicator`
- **Methods**:
  - `apply(findings: list[Finding], config: QAConfig) → tuple[list[Finding], list[Finding]]`
    - Matches each finding's suppression_key against configured suppression rules
    - Checks file scope, expiry date, and approval status
    - Returns (active_findings, suppressed_findings)

#### Value Object: `ProcessedFindings`
```
active_findings: list[Finding]
suppressed_findings: list[Finding]
clusters: list[FindingCluster]
resolved_issues: list[dict]
positive_observations: list[str]
```

---

# Part 7: Sequence Flows

## 7.1 PR Review — Full Sequence

```
Developer → [Push PR] → CI/CD → [qa run --repo . --pr 42 --post-comment]
    │
    ▼
ScanOrchestrator.scan(request)
    │
    ├─→ ConfigManager.load(repo_path) → QAConfig
    ├─→ RepositoryResolver.resolve(request) → RepositoryContext
    ├─→ ChangeDetector.detect(context, request) → ChangeSet {12 files changed}
    ├─→ HygieneChecker.check(context, change_set, config) → FileSet {10 reviewable, 2 binary skipped}
    │
    ├─→ Tier1Runner.run(repo_path, 10 files, "pr-push")
    │     ├─→ ruff.run(file1) → [Finding, Finding]
    │     ├─→ bandit.run(file1) → [Finding]
    │     ├─→ mypy.run(file1) → []
    │     ├─→ semgrep.run(file1) → [Finding]
    │     └─→ ... (27 tools × 10 files, parallel)
    │     → Tier1RunResult {35 findings}
    │
    ├─→ RiskScorer.score(10 files, tier1_result)
    │     → RiskAssessment {4 high-risk, 6 low-risk}
    │
    ├─→ AgenticReviewEngine.run(context, 4 high-risk files, tier1_result)
    │     │
    │     ├─→ FOR EACH high-risk file (parallel across files):
    │     │     ├─→ CorrectnessAgent.review_file(context) → [Finding, Finding]
    │     │     ├─→ SecurityAgent.review_file(context) → [Finding] + 2 SAST FP suppressed
    │     │     └─→ DesignAgent.review_file(context) → [Finding]
    │     │
    │     └─→ AgentReviewResult {14 agent findings}
    │
    ├─→ ValidationEngine.validate(35 tier1 + 14 agent + 2 hygiene = 51 findings)
    │     ├─→ ValidatorAgent.validate(batch1: 15 findings)
    │     │     ├─→ read_file(evidence check) × N
    │     │     └─→ 12 confirmed, 2 suppressed, 1 uncertain
    │     ├─→ ValidatorAgent.validate(batch2: 15 findings)
    │     ├─→ ValidatorAgent.validate(batch3: 15 findings)
    │     ├─→ ValidatorAgent.validate(batch4: 6 findings)
    │     └─→ ValidationResult {42 validated, 5 suppressed, 4 uncertain}
    │
    ├─→ FindingManager.process(46 findings)
    │     ├─→ LineValidator.validate() — clamp line numbers
    │     ├─→ Deduplicator.deduplicate() → 40 unique
    │     ├─→ DiffClassifier.classify() → 28 introduced, 8 modified, 4 pre-existing
    │     ├─→ AuthorAttributor.attribute() → 38 blamed, 2 default
    │     ├─→ SnippetExtractor.extract()
    │     ├─→ SuppressionApplicator.apply() → 38 active, 2 suppressed
    │     ├─→ Clusterer.cluster() → 5 clusters
    │     └─→ Ranker.rank() → sorted by severity × confidence
    │
    ├─→ QualityGate.evaluate(38 active findings)
    │     → QualityGateResult {status: "fail", 2 critical, 5 high}
    │
    ├─→ ReportGenerator.generate() → full report + executive report
    │
    ├─→ IntegrationDispatcher.dispatch()
    │     ├─→ GitHubIntegration.post_pr_summary_comment()
    │     ├─→ GitHubIntegration.post_inline_comments() × 38
    │     ├─→ GitHubIntegration.set_commit_status("failure")
    │     └─→ LinearIntegration.create_parent_issue() + create_sub_issues() × 20
    │
    └─→ ScanResult {38 findings, gate: fail, duration: 3.2min, cost: $0.42}
```

## 7.2 Agent Internal Loop — Correctness Agent

```
CorrectnessAgent.review_file(context)
    │
    ├─→ Load system prompt from prompts/correctness_agent.txt
    ├─→ Load semantic memory: project conventions
    ├─→ Build initial message: system prompt + file content + diff + Tier 1 findings
    │
    ├─→ LLM CALL 1 (Pass 1: Scan)
    │     Agent observes the code and identifies candidate issues.
    │     Agent may invoke tools:
    │       → read_file("src/utils/helpers.py") — to check imported function
    │       → grep("validate_input", scope="src/") — to find validation patterns
    │     Agent produces: candidate issue list with initial evidence
    │
    ├─→ LLM CALL 2 (Pass 2: Investigate)
    │     For each candidate, agent gathers evidence:
    │       → expand_context("src/api/users.py", line=42, radius=10)
    │       → read_file("tests/test_users.py") — to check test coverage
    │       → grep("get_user", scope="src/") — to check all callers
    │     Agent strengthens or weakens each candidate based on evidence
    │
    ├─→ LLM CALL 3 (Pass 3: Verify)
    │     Agent challenges each surviving candidate:
    │       "Would a senior engineer flag this?"
    │       "Is there context that makes this intentional?"
    │     Agent suppresses unsupported candidates
    │     Agent produces final structured findings
    │
    └─→ Parse JSON output → list[Finding]
         Validate against Finding schema
         Return AgentResult
```

---

# Part 8: Error Handling Strategy

## 8.1 Error Categories

| Category | Examples | Handling |
|---|---|---|
| **Recoverable infrastructure** | LLM rate limit, network timeout, tool timeout | Retry with backoff (max 3 retries). If all retries fail → degrade gracefully. |
| **Non-recoverable infrastructure** | Invalid API key, disk full, git not installed | Fail fast with clear error message. No retry. |
| **Agent failure** | LLM returns malformed output, agent timeout, circuit breaker open | Fail-open: retain Tier 1 findings for the affected file. Log error. Continue with other files/agents. |
| **Validation failure** | Validator LLM fails, batch timeout | Fail-open: mark all findings in batch as UNVALIDATED. Retain all findings. |
| **Data error** | File not found, line number out of range, git blame failure | Handle locally: skip the operation, use fallback (default author, empty snippet), continue. |
| **Configuration error** | Invalid YAML, schema validation failure | Fail fast at scan start with descriptive error. Don't run a scan with invalid config. |

## 8.2 Fail-Open Implementation

Every component that can fail has a fail-open default:

```
Component fails → What happens:

LLM call fails        → Tier 1 findings retained unfiltered for affected file
Agent timeout          → Partial findings (if any) retained, remaining files continue
Validator fails        → All findings marked UNVALIDATED (retained, not suppressed)
Git blame fails        → Fall back to configurable default author
File read fails        → Skip code snippet, finding still reported
Tool execution fails   → Tool skipped, other tools continue
Report PDF fails       → HTML report written instead
Integration fails      → Scan result still returned, integration error logged
```

## 8.3 Circuit Breaker

The LLM client implements a circuit breaker with 3 states:

- **Closed** (normal): All calls proceed. Failures increment counter.
- **Open** (failed): All calls return failure immediately without API contact. Prevents cascading cost.
- **Half-open** (testing): After cooldown period, one call proceeds. If successful → Closed. If failed → Open.

Threshold: 5 consecutive failures → Open.
Cooldown: 60 seconds before half-open test.

---

# Part 9: Extension Points

| Extension | Mechanism | What to Implement |
|---|---|---|
| **Add a new Tier 1 tool** | Implement `Tier1Tool` interface, register in tool list | `is_available()`, `is_applicable()`, `run()` — 3 methods |
| **Add a new agent** | Implement `ReviewAgent` interface, register in AgentRegistry | `review_file()`, `get_system_prompt()`, `get_semantic_memory()` |
| **Add a new integration** | Implement `IntegrationTarget` interface, register in dispatcher | `is_configured()`, `dispatch()` — 2 methods |
| **Add a new report format** | Add rendering method to ReportGenerator | `_render_<format>(report_data) → bytes` |
| **Add new semantic memory** | Add JSON/YAML file to knowledge directory | Update `SemanticMemoryLoader` to load the new document |
| **Customize agent prompts** | Edit text files in `prompts/` directory | No code changes required |
| **Add new quality gate mode** | Extend `QualityGate.evaluate()` strategy | Add evaluation logic for the new mode |
| **Add new risk scoring signal** | Extend `RiskScorer.score()` formula | Add new factor with configurable weight |

Each extension point follows the Open/Closed Principle — the system is open for extension (new tools, agents, integrations) without modifying existing code (orchestrator, pipeline, other agents).

---

# Part 10: Design Patterns Summary

| Pattern | Where Used | Purpose |
|---|---|---|
| **Pipeline** | ScanOrchestrator | Sequential phase execution with clear data contracts between stages |
| **Strategy** | Tier1Tool, ReviewAgent, IntegrationTarget | Each implementation provides a different strategy for the same interface |
| **Registry** | AgentRegistry | Decouple agent discovery from orchestration logic |
| **Factory** | FindingFactory | Ensure well-formed Finding creation with validation |
| **Builder** | ReportGenerator._build_report_data | Assemble complex report structure step by step |
| **Template Method** | Tier1Runner.run | Define execution skeleton, delegate tool-specific logic to implementations |
| **Observer** | IntegrationDispatcher | Notify multiple targets of scan completion without coupling |
| **Circuit Breaker** | AnthropicLLMClient | Prevent cascading failures when LLM API is down |
| **Facade** | ScanOrchestrator.scan() | Single entry point that coordinates multiple subsystems |
| **Repository** | FindingRepository, ScanRepository | Abstract persistence behind an interface |
| **Dependency Injection** | All services | Constructor injection of dependencies; no service creates its own dependencies |
| **Null Object** | Default config, empty semantic memory | Avoid null checks by providing safe defaults |
