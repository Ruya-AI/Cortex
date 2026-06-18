# Document 05: Domain Model Documentation

**QA Platform v2**
**Date**: 2026-06-18

---

## 1. Domain Map

```
┌────────────────────────────────────────────────────┐
│ CORE LAYER (zero external dependencies)            │
│                                                    │
│  Finding Domain    Agent Domain    Tool Domain      │
│  (entities)        (interfaces)    (interfaces)     │
│                                                    │
│  Shared Kernel: FindingSchema, ScanRequest          │
└────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────┐
│ APPLICATION LAYER                                  │
│                                                    │
│  Orchestration   Assessment   Reporting             │
└────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────┐
│ INFRASTRUCTURE + INTEGRATION                       │
│                                                    │
│  Git   LLM   Config   Persistence   Integrations   │
└────────────────────────────────────────────────────┘
```

## 2. Finding Domain (Central)

The Finding is the universal data contract. Every component produces, processes, or consumes Findings.

### Finding Entity

| Field | Type | Description |
|---|---|---|
| id | str | `F-<scan_short>-<seq>`, assigned by FindingManager |
| source | str | Agent or tool name |
| tier | int | 1 (deterministic), 2 (per-file agent), 3 (cross-file) |
| category | FindingCategory | CORRECTNESS, SECURITY, DESIGN, CONSISTENCY, HYGIENE |
| severity | Severity | CRITICAL > HIGH > MEDIUM > LOW > INFO |
| confidence | Confidence | CONFIRMED, LIKELY, UNCERTAIN |
| classification | Classification | INTRODUCED, MODIFIED, PRE_EXISTING, UNCLASSIFIED |
| file | str | Relative path from repo root |
| start_line, end_line | int | 1-based, clamped to file length |
| title | str | Max 120 characters |
| explanation | str | Detailed with evidence |
| evidence | Evidence | Tool calls, code references, metrics |
| recommendation | str | Concrete, actionable fix |
| cwe | str or None | CWE-89, etc. (security only) |
| author | AuthorAttribution or None | Name, email, source |
| validation_status | ValidationStatus | CONFIRMED, LIKELY, UNCERTAIN, SUPPRESSED, UNVALIDATED |
| validation_reasoning | str | Validator's verdict reasoning |
| lifecycle_state | LifecycleState | OPEN, RESOLVED, SUPPRESSED |

### Value Objects

- **Severity**: Enum with ordering (CRITICAL > HIGH > MEDIUM > LOW > INFO)
- **Confidence**: CONFIRMED (independently verified), LIKELY (not refuted), UNCERTAIN (ambiguous)
- **FindingCategory**: Maps to agent responsibility
- **ValidationStatus**: UNVALIDATED is the default (finding not yet processed by validator)
- **Evidence**: `{tool_calls: list[str], code_references: list[str], metrics: dict}`
- **AuthorAttribution**: `{name, email, github_username, attribution_source}`

### Aggregates

- **FindingSet**: Ordered collection of Findings from a single scan. Root for dedup, cluster, rank operations.

### Services

- **FindingFactory**: Create validated Finding instances with line clamping and title truncation
- **FindingDeduplicator**: Same file + overlapping lines (±3) + similar title → merge
- **FindingClusterer**: Group by suppression_key prefix
- **FindingRanker**: Sort by severity desc → confidence desc → classification → file
- **FindingLineValidator**: Clamp line numbers to file length, cache counts
- **DiffClassifier**: Mark INTRODUCED/MODIFIED/PRE_EXISTING from diff data
- **AuthorAttributor**: Git blame → PR author → git config → default (configurable)
- **SnippetExtractor**: 3 lines above/below, control chars stripped per line
- **SuppressionApplicator**: Match rules, check expiry/scope

## 3. Agent Domain

### ReviewAgent Interface
```
name: str
tier: int
category: FindingCategory
cognitive_mode: str

review_file(context: FileReviewContext) → AgentResult
review_file_group(context: FileGroupReviewContext) → AgentResult
get_system_prompt() → str
get_semantic_memory() → list[MemoryDocument]
```

### Supporting Types
- **FileReviewContext**: file_path, file_content, diff_content, tier1_findings, semantic_memory, repository_path
- **AgentResult**: agent_name, findings, tool_calls, model, tokens, cost, errors
- **MemoryDocument**: name, content, memory_type

### Services
- **AgentRegistry**: Register/discover agents by name or tier
- **AgentToolProvider**: Read-only tools for agent code exploration
- **SemanticMemoryLoader**: Load SAST rules, CWE tree, conventions, design principles

## 4. Tool Domain

### Tier1Tool Interface
```
name: str
is_available() → bool
is_applicable(file_path: str) → bool
run(file_path: str, repo_path: Path) → list[Finding]
```

### Services
- **Tier1Runner**: Discover, filter, execute, validate line numbers, aggregate

## 5. Orchestration Domain

### Value Objects
- **ScanRequest**: All CLI flags and scan parameters
- **ScanResult**: Report paths, finding count, gate status, cost, duration, errors
- **RepositoryContext**: local_path, branch, commit_sha, is_temporary
- **ChangeSet**: changed_files, modules_detected, is_full_scan
- **FileSet**: reviewable, skipped, hygiene_findings
- **RiskAssessment**: high_risk_files, low_risk_files, scores

### Services
- **ScanOrchestrator**: Main pipeline controller (facade + pipeline pattern)
- **RiskScorer**: Per-file risk score formula
- **CostTracker**: Cumulative LLM spend tracking

## 6. Assessment Domain

### Value Objects
- **QualityGateResult**: status, mode, severity_counts, blocking_findings, reasoning

### Services
- **QualityGate**: Threshold evaluation with graduated enforcement

## 7. Reporting Domain

### Services
- **ReportGenerator**: 11-section full report (JSON + PDF)
- **ExecutiveReportGenerator**: Curated actionable summary
- **TextSanitizer**: Control character stripping for PDF

## 8. Integration Domain

### IntegrationTarget Interface
```
is_configured() → bool
dispatch(findings, gate_result, scan_metadata, config) → IntegrationResult
```

### Implementations
- GitHubIntegration: PR comments + status check
- LinearIntegration: Parent issue + sub-issues
- SlackIntegration: Webhook notification
