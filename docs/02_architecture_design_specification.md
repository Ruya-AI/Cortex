# Cortex QA Platform — Architecture Design Specification

**Document Type**: Architecture Specification
**Status**: Design — No Implementation
**Date**: 2026-06-18
**Author Role**: Chief Architect
**Input**: Engineering Planning Document (01), Research Papers (7)

---

# 1. High-Level Architecture

## 1.1 Overall System Architecture

The QA Platform follows a **pipeline-funnel architecture** with an agentic review core. The design combines three architectural patterns validated by research:

1. **Multi-stage funnel** (RADAR, Meta): Each stage progressively refines the analysis — broad deterministic scanning narrows to targeted agentic review, then adversarial validation filters noise before output. Each stage acts as a gate for the next.

2. **Deterministic-first, agentic-second** (SAST-Genius, IEEE S&P 2025): Deterministic tools produce candidate findings with high recall. Agentic review provides contextual reasoning with high precision. The LLM never searches from scratch.

3. **Detector-validator chain** (AgenticSCR, FSE 2026): Detection agents produce findings. An independent validator agent adversarially challenges them. Separation prevents correlated errors between finding and verification.

The system is **CLI-first** with CI/CD integration capabilities. It operates as a **batch processor** — receives a scan request, executes the pipeline, produces reports. No long-running server process is required for core operation.

## 1.2 Major Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         INTERFACE LAYER                         │
│   CLI (primary)  │  CI/CD Webhook  │  GitHub Actions  │  API   │
└────────┬────────────────┬──────────────────┬──────────┬────────┘
         │                │                  │          │
         ▼                ▼                  ▼          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                          │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  SCAN ORCHESTRATOR                        │   │
│  │  Request validation → Pipeline execution → Result         │   │
│  │  assembly → Cost tracking → Progress reporting            │   │
│  └──────────┬───────────────────────────────────────────────┘   │
│             │                                                   │
│  ┌──────────▼───────────────────────────────────────────────┐   │
│  │              ANALYSIS PIPELINE                            │   │
│  │                                                           │   │
│  │  ┌─────────────┐  ┌──────────┐  ┌─────────────────────┐  │   │
│  │  │ Repository   │  │ Change   │  │ File Hygiene        │  │   │
│  │  │ Resolver     │→ │ Detector │→ │ Checker             │  │   │
│  │  └─────────────┘  └──────────┘  └──────────┬──────────┘  │   │
│  │                                             │             │   │
│  │  ┌──────────────────────────────────────────▼──────────┐  │   │
│  │  │              TIER 1 TOOL ENGINE                      │  │   │
│  │  │  27 deterministic tools in parallel                  │  │   │
│  │  │  Output: candidate findings in universal schema      │  │   │
│  │  └──────────────────────────────────┬─────────────────┘  │   │
│  │                                     │                     │   │
│  │  ┌──────────────────────────────────▼─────────────────┐  │   │
│  │  │              RISK SCORER                            │  │   │
│  │  │  Per-file risk assessment → route to agents or skip │  │   │
│  │  └──────────────┬──────────────────────┬──────────────┘  │   │
│  │                 │                      │                  │   │
│  │           high-risk                low-risk               │   │
│  │                 │                      │                  │   │
│  │  ┌──────────────▼──────────────────┐   │                  │   │
│  │  │     AGENTIC REVIEW ENGINE       │   │                  │   │
│  │  │                                 │   │                  │   │
│  │  │  Agent 1: Correctness  ─┐       │   │                  │   │
│  │  │  Agent 2: Security     ─┤ par.  │   │                  │   │
│  │  │  Agent 3: Design       ─┘       │   │                  │   │
│  │  │  Agent 4: Cross-File (cond.)    │   │                  │   │
│  │  └──────────────┬──────────────────┘   │                  │   │
│  │                 │                      │                  │   │
│  │  ┌──────────────▼──────────────────────▼──────────────┐  │   │
│  │  │        FINDING VALIDATION ENGINE                    │  │   │
│  │  │  Agent 5: Validator (independent, adversarial)      │  │   │
│  │  └──────────────────────────┬─────────────────────────┘  │   │
│  │                             │                             │   │
│  │  ┌──────────────────────────▼─────────────────────────┐  │   │
│  │  │        FINDING MANAGEMENT PIPELINE                  │  │   │
│  │  │  Dedup → Cluster → Classify → Attribute → Rank     │  │   │
│  │  └──────────────────────────┬─────────────────────────┘  │   │
│  └─────────────────────────────┼─────────────────────────────┘   │
│                                │                                 │
│  ┌─────────────────────────────▼─────────────────────────────┐   │
│  │  ASSESSMENT     │  REPORTING          │  INTEGRATION       │   │
│  │  Quality Gate   │  Full Report        │  GitHub PR         │   │
│  │  Risk Summary   │  Executive Report   │  Linear Tickets    │   │
│  │                 │                     │  Slack Webhook     │   │
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
         │                                            │
         ▼                                            ▼
┌─────────────────────────┐          ┌────────────────────────────┐
│   INFRASTRUCTURE LAYER  │          │     EXTERNAL SERVICES      │
│                         │          │                            │
│  LLM Client (Anthropic) │          │  Claude API (Anthropic)    │
│  Git Operations         │          │  GitHub API                │
│  File System (read-only)│          │  Linear API (GraphQL)      │
│  SQLite / PostgreSQL    │          │  Slack Webhook             │
│  Configuration Loader   │          │  SAST Tools (binaries)     │
└─────────────────────────┘          └────────────────────────────┘
```

## 1.3 Communication Patterns

**Internal communication**: Synchronous, in-process function calls. The entire pipeline runs in a single process per scan. No message queues, no service mesh, no microservices. This is a batch processing system, not a distributed service.

**Rationale**: A scan is a bounded operation (start → process → finish). There is no benefit to distributing pipeline stages across processes for a single scan. In-process communication eliminates serialization overhead, network latency, and distributed failure modes.

**Agent communication**: Agents do NOT communicate with each other. Data flows through the pipeline:
- Detection agents (1-4) produce findings → pipeline collects them
- Validator agent (5) receives collected findings → produces validated findings
- No agent reads another agent's output directly

**External communication**:
- LLM API: HTTPS to Anthropic Claude API (or compatible endpoint). Request/response per agent invocation. Retry with exponential backoff.
- GitHub API: HTTPS REST/GraphQL for PR comments, status checks. Post-pipeline only.
- Linear API: HTTPS GraphQL for ticket creation. Post-pipeline only.
- Slack API: HTTPS webhook POST. Post-pipeline only.
- Git: Local subprocess calls (`git clone`, `git diff`, `git blame`, `git log`).
- Tier 1 tools: Local subprocess calls (binary execution with timeout).

## 1.4 Data Flow

```
ScanRequest
    │
    ▼
RepositoryContext {repo_path, branch, commit, diff, changed_files}
    │
    ▼
FileSet {reviewable_files[], skipped_files[], hygiene_findings[]}
    │
    ├──────────────────────────────────────────────────────┐
    ▼                                                      │
Tier1Findings[] ──→ RiskScores{file→score}                │
    │                    │                                 │
    │              ┌─────┴─────┐                          │
    │         high-risk    low-risk                        │
    │              │           │                           │
    │              ▼           │                           │
    │    AgentFindings[]       │                           │
    │    (from Agents 1-4)     │                           │
    │              │           │                           │
    │              ▼           │                           │
    │    ┌─────────┴───────────┴──┐                       │
    └───►│ AllFindings[]           │◄──────────────────────┘
         │ (Tier1 + Agent + Hygiene)                       
         └────────────┬───────────┘
                      │
                      ▼
         ValidatedFindings[] (from Agent 5)
                      │
                      ▼
         ProcessedFindings[] (deduped, clustered, classified, attributed)
                      │
                      ▼
         QualityGateResult {status, severity_counts, blocked_findings}
                      │
                      ▼
         ScanResult {reports, gate_result, finding_count, cost, duration}
                      │
                      ▼
         ExternalOutputs {pr_comments, linear_tickets, slack_message}
```

## 1.5 External Dependencies

| Dependency | Type | Required | Failure Impact |
|---|---|---|---|
| **Anthropic Claude API** | LLM inference | Required for Tier 2+ | Graceful degradation to Tier 1-only report |
| **Git binary** | Version control | Required | Cannot scan — scan fails |
| **Python 3.11+** | Runtime | Required | Cannot run |
| **Tier 1 tool binaries** | Static analysis (ruff, bandit, mypy, semgrep, etc.) | Optional per tool | Missing tools skipped; available tools run |
| **GitHub API** | PR integration | Optional | PR comments skipped; report still generated |
| **Linear API** | Ticket creation | Optional | Tickets skipped; report still generated |
| **Slack Webhook** | Notifications | Optional | Notification skipped |
| **WeasyPrint** | PDF generation | Optional | Falls back to HTML output |
| **SQLite** | Finding persistence | Optional | History/trending unavailable; scan still works |

## 1.6 Runtime Workflow Explanation

A scan execution follows this sequence:

**Phase 1: Initialization** (synchronous, fast)
1. Parse CLI arguments or webhook payload into `ScanRequest`
2. Load `.qa-config.yml` from repository (or use defaults)
3. Resolve repository (local path or clone remote)
4. Detect changes (diff against base branch, or full file list for audits)
5. Run file hygiene checks (binary detection, large file detection, flagged files)
6. Produce `FileSet` with reviewable files, skipped files, and hygiene findings

**Phase 2: Deterministic Analysis** (parallel per tool, synchronous overall)
1. Run all applicable Tier 1 tools in parallel across reviewable files
2. Each tool produces findings in the universal schema
3. Validate line numbers on all findings (clamp to actual file length)
4. Aggregate into `Tier1Findings[]`

**Phase 3: Risk Scoring** (synchronous, fast)
1. Compute risk score per file: `complexity × change_size × sast_finding_count × path_sensitivity`
2. Route files: high-risk → agentic review, low-risk → skip to finding management

**Phase 4: Agentic Review** (parallel per agent per file)
1. For each high-risk file, invoke Agents 1, 2, 3 in parallel
2. Each agent receives: file content, diff context, relevant Tier 1 findings, semantic memory
3. Each agent operates in its observation-action loop (plan → act → observe → reason → verify)
4. Each agent produces structured findings
5. If audit mode or multi-module PR: invoke Agent 4 (Cross-File) with file groups
6. Collect all agent findings

**Phase 5: Finding Validation** (synchronous)
1. Merge Tier 1 findings + agent findings + hygiene findings into `AllFindings[]`
2. Invoke Agent 5 (Validator) with all findings
3. Validator adversarially challenges each finding, re-reads code, assigns confidence
4. Produce `ValidatedFindings[]` with validation status and reasoning

**Phase 6: Post-Processing** (synchronous, deterministic)
1. Algorithmic deduplication (same file + overlapping lines + similar title → merge)
2. Clustering (group by root cause or suppression key)
3. Diff-awareness classification (introduced / modified / pre-existing)
4. Author attribution (git blame → per-finding author)
5. Code snippet extraction (3 lines above/below, flagged lines marked)
6. Suppression application (match against configured suppression rules)
7. Prioritization (severity × confidence ranking)

**Phase 7: Assessment and Output** (synchronous)
1. Quality gate evaluation against configured thresholds
2. Full report generation (JSON + PDF)
3. Executive report generation (JSON + PDF)
4. Integration outputs: GitHub PR comments, Linear tickets, Slack notification
5. Persist scan results to database (for history/trending)
6. Return `ScanResult` to CLI for display

---

# 2. System Components

## 2.1 Scan Orchestrator

| Field | Detail |
|---|---|
| **Purpose** | Controls end-to-end pipeline execution for a single scan |
| **Responsibilities** | Request validation, phase sequencing, cost tracking, cost limit enforcement, progress callback emission, error aggregation, result assembly |
| **Inputs** | `ScanRequest` (repo, branch, tiers, agents, report formats, cost limit, trigger type) |
| **Outputs** | `ScanResult` (report paths, finding count, severity counts, gate status, duration, cost, errors) |
| **Dependencies** | All pipeline components (Tier 1 Engine, Risk Scorer, Agentic Review Engine, Validation Engine, Finding Manager, Quality Gate, Report Generator, Integration Layer), Configuration Manager |
| **Failure scenarios** | (1) Repository resolution fails → scan aborts with error. (2) All Tier 1 tools fail → scan proceeds with zero Tier 1 findings, agents still run. (3) All LLM calls fail → scan produces Tier 1-only report. (4) Cost limit reached mid-scan → remaining agents skipped, available findings processed. (5) Timeout → scan produces partial results with warning. |
| **Scaling strategy** | One orchestrator instance per scan. Multiple scans run as independent processes. No shared state between scans. |

## 2.2 Repository Resolver

| Field | Detail |
|---|---|
| **Purpose** | Resolve scan target to a local repository path with full context |
| **Responsibilities** | Accept local paths or remote URLs, clone remote repos (shallow, with depth control), checkout specific branch/commit, extract repository metadata (branch, commit SHA, remote URL), manage temporary clone lifecycle |
| **Inputs** | Repository path or URL, optional branch/commit/PR reference |
| **Outputs** | `RepositoryContext` (local path, branch, commit SHA, commit message, remote URL, is_temporary flag) |
| **Dependencies** | Git binary, file system, network (for remote clones) |
| **Failure scenarios** | (1) Invalid URL or path → scan aborts. (2) Clone timeout → scan aborts. (3) Branch/commit not found → scan aborts with descriptive error. (4) Disk space insufficient → clone fails, scan aborts. |
| **Scaling strategy** | Temporary clones are isolated per scan. Cleanup is guaranteed (try/finally). No shared clone cache (simplicity over optimization). |

## 2.3 Change Detector

| Field | Detail |
|---|---|
| **Purpose** | Determine which files changed and how |
| **Responsibilities** | Compute diff between branches/commits, extract changed file list, parse hunks for line-level change tracking, detect added/modified/deleted files, identify modules touched, detect generated code |
| **Inputs** | `RepositoryContext`, base branch (optional), scan mode (diff vs full) |
| **Outputs** | `ChangeSet` (changed_files with diffs, modules_detected, is_full_scan, lines_added, lines_deleted) |
| **Dependencies** | Git binary, generated code configuration |
| **Failure scenarios** | (1) Base branch doesn't exist → fall back to HEAD~1. (2) No changes detected → scan completes with zero findings. (3) Binary files in diff → flagged, excluded from text analysis. |
| **Scaling strategy** | Diff computation is a single git operation regardless of repo size. File listing is O(n) in changed files. |

## 2.4 File Hygiene Checker

| Field | Detail |
|---|---|
| **Purpose** | Identify files that should be skipped or flagged before analysis |
| **Responsibilities** | Detect binary files (by extension and content sniffing), detect large files (configurable threshold, default 10MB), detect files that shouldn't be committed (node_modules, .env, __pycache__, etc.), classify each file: scan, skip+flag, or flag+scan |
| **Inputs** | File list, repository path, ignore configuration |
| **Outputs** | `FileSet` (reviewable_files[], skipped_binary_files[], skipped_large_files[], flagged_files[], hygiene_findings[]) |
| **Dependencies** | File system, ignore configuration |
| **Failure scenarios** | (1) File read error → skip file with warning. (2) Permission denied → skip file with warning. |
| **Scaling strategy** | O(n) in file count. No external dependencies. |

## 2.5 Tier 1 Tool Engine

| Field | Detail |
|---|---|
| **Purpose** | Execute deterministic static analysis tools and produce normalized findings |
| **Responsibilities** | Discover available tools (check binary availability), determine tool applicability per file (by extension/pattern), execute tools with timeout and error isolation, parse tool output into universal finding schema, validate finding line numbers against actual file length, aggregate results across all tools |
| **Inputs** | Reviewable file list, repository path, trigger type |
| **Outputs** | `Tier1Result` (findings[], tool_summary{tool→count}, execution_time, tools_skipped[]) |
| **Dependencies** | Tier 1 tool binaries (ruff, bandit, mypy, semgrep, radon, pip-audit, gitleaks, hadolint, shellcheck, jscpd, etc.), file system |
| **Failure scenarios** | (1) Tool binary not found → skip that tool, log warning. (2) Tool execution timeout → skip file for that tool. (3) Tool output parse error → skip findings from that execution. (4) All tools unavailable → empty Tier 1 result (agents still run). |
| **Scaling strategy** | Tools run in parallel per file. Each tool execution is independent. Adding new tools requires only implementing the `Tier1Tool` interface — no orchestrator changes. |

**Tool Interface Contract**:
```
Tier1Tool:
  name: string
  is_available() → bool
  is_applicable(file_path) → bool
  run(file_path, repo_path) → Finding[]
```

## 2.6 Risk Scorer

| Field | Detail |
|---|---|
| **Purpose** | Determine which files warrant agentic review based on risk heuristics |
| **Responsibilities** | Compute per-file risk score from multiple signals, route files to agent review or bypass, provide score transparency in scan metadata |
| **Inputs** | File list with Tier 1 findings, file metadata (size, extension, path) |
| **Outputs** | `RiskAssessment` (high_risk_files[], low_risk_files[], scores{file→score}) |
| **Dependencies** | Tier 1 results, file metadata |
| **Failure scenarios** | (1) Unable to compute score → default to high-risk (fail-open). |
| **Scaling strategy** | Pure computation, O(n) in file count. No external dependencies. |

**Risk Score Formula**:
```
score = (complexity_weight × cyclomatic_complexity) +
        (change_weight × lines_changed) +
        (sast_weight × sast_finding_count) +
        (path_weight × path_sensitivity_factor)

path_sensitivity_factor:
  auth/, security/, crypto/, payment/ → 1.0 (always high)
  src/, lib/ → 0.5 (normal)
  test/, docs/, config/ → 0.2 (usually low)
  generated/ → 0.0 (skip)

Threshold: score > configurable_threshold → high-risk
Default threshold: calibrated to route ~30-50% of files to agent review
```

## 2.7 Agentic Review Engine

| Field | Detail |
|---|---|
| **Purpose** | Manage the lifecycle and execution of all review agents |
| **Responsibilities** | Instantiate agents with appropriate configuration and semantic memory, provide read-only tool access to agents, execute Agents 1-3 in parallel per file, execute Agent 4 conditionally with file groups, enforce agent constraints (read-only, token budget, timeout), collect structured agent output, track cost per agent |
| **Inputs** | High-risk files with Tier 1 findings, repository path, agent configuration, semantic memory resources |
| **Outputs** | `AgentReviewResult` (findings[], agents_used[], models_used[], cost, errors[]) |
| **Dependencies** | LLM Client, agent implementations, semantic memory resources, repository access tools |
| **Failure scenarios** | (1) Agent LLM call fails → apply fail-open (retain Tier 1 findings for that file). (2) Agent timeout → abort agent, retain partial findings if any. (3) Agent produces malformed output → discard agent output, retain Tier 1 findings. (4) Cost limit reached → skip remaining agents. (5) All agents fail → produce Tier 1-only result. |
| **Scaling strategy** | Agents 1-3 run in parallel per file (independent, no shared state). Multiple files can be processed concurrently up to a configurable concurrency limit. Agent 4 runs sequentially after 1-3 complete. |

## 2.8 Finding Validation Engine

| Field | Detail |
|---|---|
| **Purpose** | Host the Finding Validator Agent and manage the validation process |
| **Responsibilities** | Aggregate all findings from Tier 1 + Agents 1-4 + hygiene, batch findings for validator processing, invoke Agent 5 with finding batches, collect validation verdicts, apply fail-open for unvalidated findings |
| **Inputs** | All findings from all sources, repository path (for code re-reading) |
| **Outputs** | `ValidationResult` (validated_findings[] with confidence scores and validation_reasoning, suppressed_findings[] with suppression reasoning) |
| **Dependencies** | LLM Client (ideally different model from detection agents), repository access tools |
| **Failure scenarios** | (1) Validator LLM fails → ALL findings retained with confidence="uncertain" (fail-open). (2) Validator timeout → partial validation, remaining findings marked "uncertain". (3) Validator output malformed → findings retained unvalidated. |
| **Scaling strategy** | Findings processed in batches (configurable batch size, default 15). Batching balances context window utilization against latency. |

## 2.9 Finding Management Pipeline

| Field | Detail |
|---|---|
| **Purpose** | Deterministic post-processing of validated findings |
| **Responsibilities** | Deduplication (algorithmic: same file + overlapping lines + similar title), clustering by root cause or suppression key, diff-awareness classification (introduced/modified/pre-existing), author attribution via git blame, code snippet extraction with line markers, suppression rule application with expiry checking, prioritization ranking (severity × confidence), finding ID assignment, lifecycle state management |
| **Inputs** | Validated findings, repository context, suppression configuration, diff information |
| **Outputs** | `ProcessedFindings` (active_findings[], suppressed_findings[], clusters[], resolved_issues[]) |
| **Dependencies** | Git binary (for blame), file system (for snippets), suppression configuration |
| **Failure scenarios** | (1) Git blame fails for a file → fall back to commit-author attribution. (2) File not found for snippet → empty snippet. (3) Line numbers out of range → clamp to file length. |
| **Scaling strategy** | O(n²) worst case for dedup (pairwise comparison), O(n) for all other operations. For large finding sets (>1000), use hash-based dedup to reduce to O(n). |

## 2.10 Quality Gate

| Field | Detail |
|---|---|
| **Purpose** | Evaluate overall scan quality against configured thresholds |
| **Responsibilities** | Count findings by severity and confidence, evaluate against graduated thresholds (shadow/advisory/enforced), check for override existence and validity, produce gate decision with reasoning |
| **Inputs** | Processed findings, quality gate configuration, active overrides |
| **Outputs** | `QualityGateResult` (status: pass/advisory/fail, severity_counts, blocking_findings[], reasoning) |
| **Dependencies** | Quality gate configuration, override storage |
| **Failure scenarios** | None — pure computation on in-memory data. |
| **Scaling strategy** | O(n) in finding count. Trivial computation. |

## 2.11 Report Generator

| Field | Detail |
|---|---|
| **Purpose** | Transform scan results into human-readable and machine-readable reports |
| **Responsibilities** | Build full report data structure (11 sections), build executive report data structure, serialize to JSON, render HTML from templates, convert HTML to PDF via WeasyPrint, sanitize control characters for PDF rendering, write output files |
| **Inputs** | Processed findings, quality gate result, scan metadata (duration, cost, models used), repository context, execution history |
| **Outputs** | `ReportResult` (json_path, pdf_path, executive_json_path, executive_pdf_path, report_data) |
| **Dependencies** | WeasyPrint (optional, falls back to HTML), file system |
| **Failure scenarios** | (1) WeasyPrint unavailable → write HTML instead of PDF. (2) File write error → report generation fails, scan still returns results in memory. |
| **Scaling strategy** | Report generation is O(n) in finding count. Template rendering is single-threaded. For very large reports (>1000 findings), the executive report's top-20 filter prevents output bloat. |

## 2.12 Integration Layer

**GitHub Integration**:
| Field | Detail |
|---|---|
| **Purpose** | Post findings as PR comments and set status checks |
| **Responsibilities** | Post summary comment on PR, post inline review comments on specific file:line in the diff, set commit status check (pass/fail) |
| **Inputs** | Processed findings, quality gate result, PR metadata, GitHub token |
| **Outputs** | Comment IDs, status check ID |
| **Dependencies** | GitHub REST API, authentication token |
| **Failure scenarios** | (1) Token invalid → skip posting with error. (2) Rate limit → retry with backoff. (3) PR not found → skip with error. |

**Linear Integration**:
| Field | Detail |
|---|---|
| **Purpose** | Create tickets for findings in Linear |
| **Responsibilities** | Create one parent issue per scan, create sub-issues per finding (up to configurable max), assign to developer by email match |
| **Inputs** | Processed findings (filtered by minimum severity), scan metadata, Linear configuration |
| **Outputs** | Parent issue ID, sub-issue IDs |
| **Dependencies** | Linear GraphQL API, API key, team ID |
| **Failure scenarios** | (1) API key invalid → skip with error. (2) Rate limit → retry. (3) Developer not found → create unassigned. |

**Slack Integration**:
| Field | Detail |
|---|---|
| **Purpose** | Notify teams of scan completion |
| **Responsibilities** | Send webhook POST with scan summary |
| **Inputs** | Scan result summary, Slack webhook URL |
| **Outputs** | HTTP response status |
| **Dependencies** | Slack Incoming Webhook URL |
| **Failure scenarios** | (1) Webhook URL invalid → skip. (2) Network error → skip (notification is non-critical). |

## 2.13 Configuration Manager

| Field | Detail |
|---|---|
| **Purpose** | Load, validate, and provide repository-level configuration |
| **Responsibilities** | Load `.qa-config.yml` from repository root, validate against Pydantic schema with clear error messages, provide defaults when config file is absent, resolve environment variables for secrets, version-check config schema |
| **Inputs** | Repository path |
| **Outputs** | `QAConfig` (validated, typed configuration object) |
| **Dependencies** | File system, YAML parser, Pydantic |
| **Failure scenarios** | (1) Config file missing → use defaults. (2) Config invalid YAML → error with file location. (3) Config fails validation → error with field-level messages. |
| **Scaling strategy** | Single file read at scan start. Cached for duration of scan. |

## 2.14 LLM Client

| Field | Detail |
|---|---|
| **Purpose** | Managed interface to LLM API with reliability features |
| **Responsibilities** | Send prompts to Claude API, enforce structured JSON output with schema validation, retry with exponential backoff on transient errors, implement circuit breaker (N consecutive failures → skip), track token usage and cost per call, enforce model fallback chain (primary → secondary → skip), enforce temperature=0 for deterministic output |
| **Inputs** | System prompt, user message, output schema, model identifier |
| **Outputs** | Structured response (validated against schema) or failure indicator |
| **Dependencies** | Anthropic Claude API, network |
| **Failure scenarios** | (1) Rate limit → retry with backoff. (2) Timeout → retry once, then fail. (3) Invalid response → retry with same prompt. (4) Circuit breaker open → return failure immediately (no API call). (5) All models in fallback chain exhausted → return failure. |
| **Scaling strategy** | One client instance per scan, shared across all agents. Connection pooling via httpx. Concurrent requests bounded by agent parallelism limit. |

---

# 3. Agentic AI Architecture

## 3.1 Agent Ecosystem Overview

The platform contains exactly **5 agents**. Each agent is justified by a distinct capability boundary — a unique combination of input scope, cognitive mode, and knowledge requirement that no other agent covers.

```
                    ┌─────────────────────┐
                    │   SCAN ORCHESTRATOR  │
                    │   (deterministic     │
                    │    pipeline control) │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
   │   AGENT 1    │ │   AGENT 2    │ │   AGENT 3    │
   │ Correctness  │ │  Security    │ │   Design     │
   │              │ │              │ │              │
   │ Constructive │ │ Adversarial  │ │ Evaluative   │
   │ Execution    │ │ Taint trace  │ │ Structural   │
   │ tracing      │ │ CWE classify │ │ assessment   │
   │              │ │              │ │              │
   │ Per-file     │ │ Per-file     │ │ Per-file     │
   │ Parallel     │ │ Parallel     │ │ Parallel     │
   └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
          │                │                │
          │         ┌──────┴───────┐        │
          │         │   AGENT 4    │        │
          │         │  Cross-File  │        │
          │         │              │        │
          │         │ Comparative  │        │
          │         │ Multi-file   │        │
          │         │ Conditional  │        │
          │         └──────┬───────┘        │
          │                │                │
          └────────────────┼────────────────┘
                           │
                    ┌──────▼───────┐
                    │   AGENT 5    │
                    │  Validator   │
                    │              │
                    │ Skeptical    │
                    │ Adversarial  │
                    │ Independent  │
                    │ (diff model) │
                    └──────────────┘
```

## 3.2 Agent Communication Model

**Pattern: Pipeline-mediated, zero direct communication.**

Agents never communicate with each other. Data flows exclusively through the pipeline:

```
Agent 1 ──→ findings[] ──┐
Agent 2 ──→ findings[] ──┤
Agent 3 ──→ findings[] ──┼──→ Aggregated findings ──→ Agent 5 ──→ validated findings
Agent 4 ──→ findings[] ──┘
```

**Rationale**: Direct agent-to-agent communication introduces coordination complexity, ordering dependencies, and potential for cascading failures. Pipeline-mediated flow keeps agents independent, enables parallel execution, and makes the system easier to test (each agent can be tested in isolation with fixture inputs).

This is supported by QASecClaw's architecture (Section III, Figure 2) where the Mission Orchestrator manages all inter-agent data flow, and by RADAR's funnel design where each layer operates on the output of the previous layer without lateral communication.

## 3.3 Agent Memory Strategy

Each agent uses a three-tier memory model inspired by AgenticSCR (FSE 2026, Section 3.4):

**Semantic Memory (long-term, read-only, loaded at agent start)**:
- Agent 1 (Correctness): Project coding conventions, language idioms, error handling patterns — loaded from `.qa-config.yml` knowledge_base configuration or project documentation
- Agent 2 (Security): SAST rules (CodeQL patterns with CWE mappings, severity, examples, remediation), CWE taxonomy tree — loaded from bundled knowledge files. AgenticSCR proved SAST rules contribute +5.7% and CWE tree +4.5% absolute improvement
- Agent 3 (Design): Design principles (SOLID, coupling/cohesion metrics, pattern catalog), project conventions — loaded from configuration
- Agent 4 (Cross-File): Module boundary definitions, interface contracts — derived from project structure at scan time
- Agent 5 (Validator): Common false positive patterns, validation criteria per finding type — loaded from bundled knowledge files

**Working Memory (short-term, transient, per-review-session)**:
- Current file content, expanded code chunks, grep results, tool outputs
- Accumulated findings from current review pass
- Maintained implicitly through the LLM conversation context within a single agent invocation
- Discarded after agent completes its review of a file

**Episodic Memory (session log, write-once)**:
- Reasoning traces and tool call history captured during agent execution
- Stored in the audit log for debugging and transparency
- Not shared between agents — each agent's episodic memory is independent

**Critical constraint**: Semantic memory is READ-ONLY. Agents do not learn or update their knowledge during execution. Knowledge improvement happens through configuration updates between scans, not during scans.

## 3.4 Tool Usage Strategy

All agents share a common set of read-only tools for code exploration:

| Tool | Purpose | Invocation |
|---|---|---|
| `read_file(path, start_line?, end_line?)` | Read file content, optionally a line range | Agent decides which files to read based on observations |
| `grep(pattern, path?, scope?)` | Search for patterns in the codebase | Agent decides what to search for based on findings |
| `git_diff(file?, base?)` | View diff for a file or the entire changeset | Agent reads diff to understand what changed |
| `list_directory(path)` | List files in a directory | Agent explores project structure |
| `expand_context(file, line, radius)` | Read code around a specific line with expanded context | Agent investigates specific code locations |

**Tool invocation is agent-directed**: The orchestrator provides tools to the agent, but the AGENT decides which tools to call and when. This is the core agentic property — the agent's tool calls are decisions driven by its observations, not a predetermined sequence.

**Tool constraint enforcement**: All tools are read-only. No tool can write to the repository, execute code, or modify state. This is enforced at the tool interface level — the tool implementations physically cannot write.

## 3.5 Planning / Execution Loop

Each detection agent (1-4) follows a three-pass observation-action loop:

```
PASS 1: SCAN
┌─────────────────────────────────────────┐
│ Observe: Read file content + diff       │
│ Plan: Identify areas of concern         │
│ Act: Use tools to gather initial context │
│ Reason: Produce candidate issues list   │
└─────────────────────┬───────────────────┘
                      │
                      ▼
PASS 2: INVESTIGATE
┌─────────────────────────────────────────┐
│ For each candidate issue:               │
│   Observe: Read related code via tools  │
│   Plan: What evidence would confirm     │
│          or refute this issue?          │
│   Act: Invoke tools to gather evidence  │
│        (read callers, check imports,    │
│         trace data flow, verify tests)  │
│   Reason: Does evidence support the     │
│           issue? Strengthen or discard. │
└─────────────────────┬───────────────────┘
                      │
                      ▼
PASS 3: VERIFY
┌─────────────────────────────────────────┐
│ For each surviving candidate:           │
│   Challenge: Would a senior engineer    │
│   flag this? Is there context that      │
│   makes this intentional?              │
│   Decide: Produce final finding or      │
│   suppress with reasoning              │
│   Output: Structured finding with       │
│   evidence, explanation, recommendation │
└─────────────────────────────────────────┘
```

The Validator Agent (5) follows a different loop:

```
FOR EACH FINDING:
┌─────────────────────────────────────────┐
│ Read: Re-read the code referenced by    │
│       the finding (independent of the   │
│       detection agent's reading)        │
│ Challenge: Try to REFUTE the finding    │
│   - Is the claimed issue actually       │
│     present in the code?               │
│   - Is there surrounding context that   │
│     resolves the issue?                │
│   - Is the evidence cited accurate?     │
│ Compare: Does this finding overlap with │
│   another finding from a different      │
│   agent? If so, merge or deduplicate.  │
│ Decide: Assign validation status        │
│   confirmed / likely / uncertain /      │
│   suppressed                           │
└─────────────────────────────────────────┘
```

## 3.6 Validation Mechanisms

**Layer 1 — Agent self-verification (Pass 3)**:
Each detection agent challenges its own findings before reporting them. This catches obvious false positives but cannot catch correlated errors (the same model confirming its own hallucination).

**Layer 2 — Independent adversarial validation (Agent 5)**:
A separate agent with a different cognitive mode (skeptical) and ideally a different model challenges ALL findings from ALL agents. RevAgent ablation (Section 5.2) proved this is the single most impactful component. The 3+1 paper showed +10.3pp precision improvement from independent verification.

**Layer 3 — Algorithmic deduplication (Finding Manager)**:
Deterministic matching: same file + overlapping line range + similar title → merge. This catches cases where multiple agents flag the same issue with different wording.

**Layer 4 — Human review (Quality Gate override)**:
For enforced quality gates, findings that block merge require human review. The developer sees the finding with its full evidence chain and decides whether to resolve, suppress, or override.

## 3.7 Human Approval Checkpoints

| Checkpoint | When | What Requires Human Action |
|---|---|---|
| **Finding resolution** | After scan completes | Developer reviews each finding and decides to fix, suppress, or dismiss |
| **Quality gate override** | When gate blocks merge | Tech lead approves override with documented reason and expiry |
| **Suppression creation** | When a finding should be permanently suppressed | Security engineer or tech lead approves suppression with reason and expiry |
| **Gate mode promotion** | When moving from shadow → advisory → enforced | Engineering manager reviews finding quality metrics before promoting |
| **Agent graduation** | When enabling a new agent | Tech lead reviews agent output in shadow mode before activating |

## 3.8 Individual Agent Specifications

### Agent 1: Correctness Agent

| Field | Detail |
|---|---|
| **Objective** | Identify logic bugs, correctness errors, edge case failures, and error handling deficiencies in changed code |
| **Capabilities** | Execution path tracing, invariant checking, null/boundary analysis, error path verification, race condition detection |
| **Tools** | `read_file`, `grep`, `git_diff`, `list_directory`, `expand_context` |
| **Knowledge sources** | Project coding conventions (from config), language-specific idioms (bundled) |
| **Decision boundaries** | Produces findings only when evidence supports the issue through tool calls. Suppresses candidates that fail self-verification in Pass 3. Does NOT produce security, design, or cross-file findings — stays within its cognitive boundary. |
| **Interactions** | Receives: file content, diff, Tier 1 findings. Produces: correctness findings. No communication with other agents. |
| **Model** | Claude Sonnet (primary), Claude Haiku (fallback) |

### Agent 2: Security Agent

| Field | Detail |
|---|---|
| **Objective** | Validate SAST findings, detect security vulnerabilities missed by SAST, classify by CWE, provide remediation guidance |
| **Capabilities** | Taint path tracing (source → transformation → sink), SAST finding validation (true positive / false positive with reasoning), CWE hierarchical classification, exploitability assessment, remediation recommendation |
| **Tools** | `read_file`, `grep`, `git_diff`, `list_directory`, `expand_context` + structured SAST findings as input |
| **Knowledge sources** | SAST rules (CodeQL patterns, CWE mappings, severity, examples, remediation — bundled JSON), CWE taxonomy tree (bundled JSON) |
| **Decision boundaries** | Validates SAST findings with explicit reasoning. For true positives: provides CWE + remediation. For false positives: documents WHY it's safe. Own discoveries (beyond SAST) require strong evidence. Fail-open: if LLM fails, ALL SAST findings retained. |
| **Interactions** | Receives: file content, diff, SAST findings from Tier 1, semantic memory. Produces: security findings with CWE classification. No communication with other agents. |
| **Model** | Claude Sonnet (primary), Claude Haiku (fallback) |

### Agent 3: Design & Improvement Agent

| Field | Detail |
|---|---|
| **Objective** | Evaluate code structure, identify maintainability issues, and suggest concrete improvements |
| **Capabilities** | Structural evaluation (SOLID assessment, complexity analysis, coupling detection), naming and abstraction review, pattern identification and recommendation, test adequacy assessment, documentation completeness check |
| **Tools** | `read_file`, `grep`, `git_diff`, `list_directory`, `expand_context` |
| **Knowledge sources** | Design principles (SOLID, coupling/cohesion — bundled), project conventions (from config) |
| **Decision boundaries** | Produces improvement suggestions, not bug reports. Each suggestion must include: what to change, why it improves the code, and a concrete example. Does NOT produce correctness bugs or security vulnerabilities. |
| **Interactions** | Receives: file content, diff, Tier 1 findings (complexity, style). Produces: design/improvement findings. No communication with other agents. |
| **Model** | Claude Sonnet (primary), Claude Haiku (fallback) |

### Agent 4: Cross-File Analysis Agent

| Field | Detail |
|---|---|
| **Objective** | Detect consistency issues, broken contracts, and systemic patterns across module boundaries |
| **Capabilities** | Multi-file comparison (interfaces, validation patterns, error handling), interface contract verification, systemic pattern detection (same issue across N files), architectural consistency checking |
| **Tools** | `read_file`, `grep`, `git_diff`, `list_directory`, `expand_context` — same tools but used with multi-file scope |
| **Knowledge sources** | Module boundary definitions (derived from project structure), interface contracts (from type signatures and documentation) |
| **Decision boundaries** | Only runs when cross-file scope is warranted (audits, multi-module PRs). Produces cross-file findings that individual per-file agents cannot detect. Must provide cross-file evidence (referencing multiple files). |
| **Interactions** | Receives: file groups organized by module, findings from Agents 1-3 (to avoid re-discovering per-file issues). Produces: cross-file/systemic findings. Conditional execution. |
| **Model** | Claude Sonnet (primary), Claude Haiku (fallback) |
| **Execution condition** | Trigger is `audit` OR changed files span 3+ distinct modules |

### Agent 5: Finding Validator Agent

| Field | Detail |
|---|---|
| **Objective** | Adversarially challenge all findings, filter false positives, resolve duplicates, assign calibrated confidence |
| **Capabilities** | Independent code re-reading (verifies claims from other agents), adversarial challenge (tries to REFUTE each finding), semantic deduplication (identifies when different agents describe the same issue), confidence calibration (confirmed / likely / uncertain / suppressed) |
| **Tools** | `read_file`, `grep`, `expand_context` — re-reads code independently |
| **Knowledge sources** | Common false positive patterns (bundled), validation criteria per CWE category (bundled) |
| **Decision boundaries** | Can only VALIDATE, DOWNGRADE, or SUPPRESS findings — cannot produce NEW findings. Fail-open: if uncertain, retains the finding. Must document reasoning for every verdict. |
| **Interactions** | Receives: ALL findings from Agents 1-4 and Tier 1 tools. Produces: validation verdicts with reasoning. Runs AFTER all detection agents complete. |
| **Model** | Claude Opus (primary — different model from detection agents for diversity), Claude Sonnet (fallback). Model diversity prevents correlated errors (TAP paper: heterogeneous models +17% defect detection). |

---

# 4. Data Architecture

## 4.1 Database Design

**Primary storage: SQLite** (single-file, zero-config, embedded) for local/CLI usage.
**Production option: PostgreSQL** for team/CI environments requiring concurrent access.

The database stores scan history, finding lifecycle, and suppression state. It is NOT in the critical path — scans work without a database (history/trending unavailable, but scan completes).

### Schema

**Table: scans**
```
scan_id          TEXT PRIMARY KEY    -- QA-RPT-YYYY-MM-DD-<hex>
repository       TEXT NOT NULL
branch           TEXT
commit_sha       TEXT
trigger          TEXT                -- pr-push, commit, audit, ad-hoc, scheduled
tiers_executed   TEXT                -- JSON array [1,2,3]
finding_count    INTEGER
severity_counts  TEXT                -- JSON {critical:0, high:1, ...}
gate_status      TEXT                -- pass, advisory, fail
duration_seconds REAL
cost_usd         REAL
report_json_path TEXT
report_pdf_path  TEXT
created_at       TEXT                -- ISO 8601
config_hash      TEXT
```

**Table: findings**
```
finding_id       TEXT PRIMARY KEY
scan_id          TEXT NOT NULL REFERENCES scans(scan_id)
source           TEXT NOT NULL       -- agent name or tool name
tier             INTEGER
category         TEXT                -- correctness, security, design, consistency
severity         TEXT                -- critical, high, medium, low, info
confidence       TEXT                -- confirmed, likely, uncertain
classification   TEXT                -- introduced, modified, pre-existing
file_path        TEXT
start_line       INTEGER
end_line         INTEGER
title            TEXT
explanation      TEXT
recommendation   TEXT
cwe              TEXT                -- CWE-89, etc. (nullable)
validation_status TEXT               -- confirmed, likely, uncertain, suppressed
validation_reasoning TEXT
lifecycle_state  TEXT                -- open, resolved, suppressed
author_name      TEXT
author_email     TEXT
first_seen_at    TEXT
last_seen_at     TEXT
resolved_at      TEXT
```

**Table: suppressions**
```
suppression_id   TEXT PRIMARY KEY
pattern          TEXT NOT NULL       -- suppression key pattern
file_scope       TEXT                -- nullable (null = global)
reason           TEXT NOT NULL
approved_by      TEXT
approved_at      TEXT
expires_at       TEXT
finding_count    INTEGER DEFAULT 0   -- count of findings suppressed
```

**Table: audit_log**
```
log_id           TEXT PRIMARY KEY
scan_id          TEXT REFERENCES scans(scan_id)
agent_name       TEXT
model            TEXT
prompt_hash      TEXT
input_tokens     INTEGER
output_tokens    INTEGER
cost_usd         REAL
duration_ms      INTEGER
finding_ids      TEXT                -- JSON array of finding IDs produced
timestamp        TEXT
status           TEXT                -- success, error, timeout, circuit_breaker
```

**Table: gate_overrides**
```
override_id      TEXT PRIMARY KEY
scan_id          TEXT
approved_by      TEXT NOT NULL
reason           TEXT NOT NULL
expires_at       TEXT NOT NULL
created_at       TEXT
```

## 4.2 Data Ownership

| Data | Owner Component | Consumers |
|---|---|---|
| Scan metadata | Scan Orchestrator | Report Generator, Integration Layer, History API |
| Tier 1 findings | Tier 1 Tool Engine | Risk Scorer, Agent Review Engine, Validation Engine |
| Agent findings | Agentic Review Engine | Validation Engine |
| Validated findings | Validation Engine | Finding Management Pipeline |
| Processed findings | Finding Management Pipeline | Quality Gate, Report Generator, Integration Layer |
| Quality gate result | Quality Gate | Report Generator, Integration Layer |
| Report files | Report Generator | CLI output, Integration Layer |
| Audit log entries | LLM Client | Observability, Compliance |
| Configuration | Configuration Manager | All components (read-only) |

## 4.3 Storage Choices

| Data Type | Storage | Rationale |
|---|---|---|
| Scan results & findings | SQLite / PostgreSQL | Relational queries for history, trending, lifecycle |
| Report files (JSON, PDF) | Local filesystem | Simple, no database bloat, path stored in DB |
| Semantic memory (SAST rules, CWE) | Bundled JSON files | Read-only reference data, versioned with platform |
| Configuration | YAML file in repository | Repository-specific, version-controlled |
| Agent prompts | Text files in platform | Externalized for editability, versioned with platform |
| Audit log | Database table | Structured, queryable for compliance |
| Temporary clones | System temp directory | Auto-cleaned, no persistence needed |

## 4.4 Event Model

The platform uses a synchronous pipeline, not an event-driven architecture. However, the following events are emitted as progress callbacks and audit log entries:

| Event | When | Data |
|---|---|---|
| `scan.started` | Scan begins | scan_id, repo, trigger, tiers |
| `tier1.completed` | All Tier 1 tools finish | finding_count, duration |
| `agent.started` | Agent begins review of a file | agent_name, file_path |
| `agent.completed` | Agent finishes review | agent_name, file_path, finding_count, cost |
| `agent.failed` | Agent LLM call fails | agent_name, error, fallback_action |
| `validation.completed` | Validator finishes | validated_count, suppressed_count |
| `gate.evaluated` | Quality gate runs | status, severity_counts |
| `scan.completed` | Scan finishes | total_findings, gate_status, duration, cost |

These events are consumed by: progress callback (CLI display), audit log (database), and structured logging (JSON log files).

## 4.5 Caching Strategy

**No LLM response cache in v2**. Rationale:
- LLM responses depend on file content, which changes between scans
- Caching introduces staleness risk — a cached "no issues" response for a file that has changed is a false negative
- The risk scorer already prevents unnecessary LLM calls (low-risk files skip agent review)
- Tier 1 tool results are fast enough to not need caching

**Future consideration**: Cache Tier 1 tool results by file content hash for unchanged files in incremental scans. Only implement when performance data shows Tier 1 execution is a bottleneck.

## 4.6 Search and Indexing

**Finding search**: SQLite full-text search (FTS5) on `findings.title`, `findings.explanation`, `findings.file_path` for history queries.

**Trend queries**: Indexed on `scan_id`, `created_at`, `file_path`, `severity`, `lifecycle_state` for time-series aggregation.

## 4.7 Audit History

Every LLM API call is logged to the `audit_log` table with:
- Prompt hash (SHA-256 of the full prompt — allows correlation without storing sensitive code)
- Token counts (input, output)
- Cost in USD
- Model used
- Finding IDs produced from this call
- Status (success, error, timeout, circuit_breaker)

This provides:
- Cost accountability (per-scan, per-agent, per-model)
- Debugging (which prompt produced which finding)
- Compliance (audit trail of all AI decisions)
- Performance monitoring (latency per call)

---

# 5. Security Architecture

## 5.1 Authentication

**CLI usage**: No authentication required for local scans. The user running the CLI has filesystem access to the repository.

**CI/CD usage**: Authentication is handled by the CI/CD platform (GitHub Actions, GitLab CI). The QA platform receives the repository through the CI checkout step and requires tokens for external API access.

**API tokens for integrations**:
- `ANTHROPIC_API_KEY` — Claude API access
- `GITHUB_TOKEN` — PR comment posting, status checks
- `LINEAR_API_KEY` — Ticket creation
- `SLACK_WEBHOOK_URL` — Notification posting

All tokens are read from environment variables or `.qa-config.yml` (with environment variable interpolation: `${ENV_VAR}`). Tokens are never logged, never included in reports, never stored in the database.

## 5.2 Authorization

**Audit-only constraint**: The platform has NO write access to the repository under evaluation. This is enforced at multiple layers:

| Layer | Enforcement |
|---|---|
| **Architecture** | No write-capable tools exist in the agent tool set |
| **Tool interface** | `read_file`, `grep`, `expand_context` — all read-only by design |
| **Git operations** | Clone to temp directory; original repo untouched |
| **Agent prompts** | System prompts explicitly state "You identify and report. You do NOT modify code." |
| **Output schema** | Finding schema has `recommendation` (text), not `patch` (code) |
| **File system** | Reports written to output directory, never to the scanned repository |

**Quality gate override authorization**: Overrides require a named approver (`approved_by` field). The platform does not enforce WHO can approve (no role system in v2) — this is delegated to the team's existing approval process.

## 5.3 Tenant Isolation

**v2 scope**: Single-tenant. One repository per scan. No multi-tenant concerns.

**Future multi-tenant considerations**:
- Scans are stateless — no shared state between scans for different repositories
- Database can be partitioned by repository
- LLM API keys can be per-organization
- No cross-repository data leakage is possible because each scan operates on an independent clone

## 5.4 Secrets Management

| Secret | Storage | Access |
|---|---|---|
| LLM API key | Environment variable `ANTHROPIC_API_KEY` | LLM Client only |
| GitHub token | Environment variable `GITHUB_TOKEN` or CLI flag | GitHub Integration only |
| Linear API key | Environment variable `LINEAR_API_KEY` or config | Linear Integration only |
| Slack webhook | Environment variable or config | Slack Integration only |

**Secrets in scanned code**: The platform runs `gitleaks` (Tier 1 tool) to detect secrets in the scanned repository. Detected secrets are reported as findings but are NOT included verbatim in reports — the finding references the file and line number only.

**LLM prompt security**: Code sent to the LLM API is governed by the `privacy.ai_exclude_paths` configuration. Files matching excluded paths are not sent to any LLM — they receive Tier 1 analysis only.

## 5.5 Data Protection

**Code in transit**: All LLM API calls use HTTPS (TLS 1.2+). Code snippets sent to the API are limited to the file under review plus context gathered by agent tool calls.

**Code at rest**: The platform does not persistently store source code. Code snippets in findings (the `code_under_review` field) are stored in reports but can be excluded via `privacy.code_retention_days: 0`.

**Report protection**: Reports are written to the local filesystem. Access control is inherited from the filesystem permissions. Reports may contain finding details, code snippets, and author attribution — they should be treated as sensitive.

**Audit log protection**: The audit log stores prompt hashes (not full prompts) to enable correlation without storing sensitive code. Token counts and costs are stored in full.

## 5.6 Compliance Considerations

**Audit trail**: Every LLM decision is logged with prompt hash, model, tokens, cost, and finding IDs. This enables post-hoc review of AI decisions.

**Reproducibility**: Each report includes a reproducibility command (`qa run --repo ... --commit ... --branch ... --tiers ...`) and a config hash. Re-running the same command on the same commit with the same config produces comparable results (modulo LLM non-determinism at temperature=0).

**Data residency**: LLM API calls go to Anthropic's API endpoints. Organizations requiring data residency can use self-hosted models via compatible API endpoints (configured via `privacy.ai_review_mode`).

**No training data**: Code sent to Anthropic's API is not used for model training (per Anthropic's API terms). The platform does not fine-tune models.

---

# 6. Infrastructure Architecture

## 6.1 Deployment Model

**Primary deployment: CLI binary / pip package**

The platform is a Python CLI application installed via `pip install cortex`. It runs on the developer's machine or in CI/CD environments. No server infrastructure required for core functionality.

```
Developer machine:
  pip install cortex
  qa run --repo . --tiers 1,2 --report json,pdf

CI/CD environment:
  pip install cortex
  qa run --repo . --pr $PR_NUMBER --post-comment --report json
  exit $?  # exit code reflects quality gate
```

**Secondary deployment: Container image**

For CI/CD environments that prefer containers:

```
Docker image: cortex:latest
  Base: python:3.11-slim
  Includes: cortex + all pip-installable Tier 1 tools
  External binaries: gitleaks, hadolint, shellcheck, trivy (optional layer)
  Entrypoint: qa run
```

## 6.2 Cloud Architecture

The platform is designed to run ANYWHERE — developer laptop, CI runner, cloud VM, or container. It does not require cloud infrastructure.

**For teams wanting a hosted deployment**:

```
┌──────────────────────────────────────────────────┐
│                  CI/CD Runner                     │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │         QA Platform Container               │  │
│  │                                             │  │
│  │  qa run --repo $REPO --pr $PR_NUMBER       │  │
│  │  --post-comment --report json               │  │
│  │                                             │  │
│  │  Outputs:                                   │  │
│  │  - Reports → artifact storage               │  │
│  │  - PR comments → GitHub API                 │  │
│  │  - Tickets → Linear API                     │  │
│  │  - Exit code → CI gate                      │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  Environment variables:                          │
│  ANTHROPIC_API_KEY, GITHUB_TOKEN, LINEAR_API_KEY │
└──────────────────────────────────────────────────┘
         │              │              │
         ▼              ▼              ▼
   Claude API      GitHub API     Linear API
```

No persistent server. No database server (SQLite file). No message queue. No load balancer. The platform is a batch job that runs per trigger event.

## 6.3 Container Specification

```
FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y git shellcheck && rm -rf /var/lib/apt/lists/*

# Platform and pip-installable tools
RUN pip install cortex

# Optional: external binaries
# COPY --from=gitleaks /usr/bin/gitleaks /usr/local/bin/
# COPY --from=hadolint /bin/hadolint /usr/local/bin/
# COPY --from=trivy /usr/bin/trivy /usr/local/bin/

ENTRYPOINT ["qa"]
```

Image layers:
1. **Base**: Python 3.11 slim (~45MB)
2. **System tools**: git, shellcheck (~30MB)
3. **Platform + pip tools**: cortex, ruff, bandit, mypy, semgrep, radon, pip-audit, sqlfluff, checkov, pip-licenses (~200MB)
4. **Optional binaries**: gitleaks, hadolint, trivy, osv-scanner (~100MB)

Total: ~375MB (with optional binaries)

## 6.4 Kubernetes Considerations

For organizations running on Kubernetes:

**Job-based execution**: Each scan runs as a Kubernetes Job (not a long-running Deployment). Jobs are created by a webhook receiver or CronJob.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: qa-scan-${PR_NUMBER}-${COMMIT_SHA_SHORT}
spec:
  backoffLimit: 1
  activeDeadlineSeconds: 600
  template:
    spec:
      containers:
      - name: cortex
        image: cortex:latest
        command: ["qa", "run"]
        args: ["--repo", "$(REPO_URL)", "--pr", "$(PR_NUMBER)", "--post-comment"]
        env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: cortex-secrets
              key: anthropic-api-key
        - name: GITHUB_TOKEN
          valueFrom:
            secretKeyRef:
              name: cortex-secrets
              key: github-token
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2"
      restartPolicy: Never
```

**Webhook receiver** (for PR-triggered scans): A lightweight HTTP service that receives GitHub webhooks and creates Kubernetes Jobs. This is the ONLY persistent infrastructure component. It is stateless — it translates webhook payloads to Job specs.

**CronJob** (for scheduled scans):
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: qa-nightly-audit
spec:
  schedule: "0 2 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: cortex
            image: cortex:latest
            command: ["qa", "run"]
            args: ["--repo", "$(REPO_URL)", "--audit", "--report", "json,pdf"]
```

## 6.5 CI/CD Integration

**GitHub Actions**:
```yaml
name: QA Platform
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  qa-review:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
      with:
        fetch-depth: 0

    - name: Install QA Platform
      run: pip install cortex

    - name: Run QA Scan
      env:
        ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      run: |
        qa run --repo . \
          --pr ${{ github.event.pull_request.number }} \
          --vs ${{ github.base_ref }} \
          --post-comment \
          --report json \
          --tiers 1,2

    - name: Upload Report
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: qa-report
        path: .qa-reports/
```

## 6.6 Monitoring

| Metric | Source | Purpose |
|---|---|---|
| Scan duration | Scan orchestrator | Performance tracking, SLA monitoring |
| Scan cost (USD) | LLM client | Cost management, budget alerts |
| Finding count by severity | Finding manager | Quality trend tracking |
| False positive rate | Validator agent | Precision monitoring |
| Resolution rate | Finding lifecycle | Developer adoption metric |
| Agent failure rate | LLM client | Reliability monitoring |
| Tier 1 tool availability | Tool engine | Infrastructure health |
| Quality gate pass rate | Quality gate | Policy effectiveness |

**Implementation**: Metrics are emitted as structured JSON log entries. For production environments, these can be ingested by any log aggregation system (ELK, Datadog, Grafana Loki). No proprietary metrics SDK required.

## 6.7 Logging

**Format**: JSON structured logging with correlation ID per scan.

```json
{
  "timestamp": "2026-06-18T12:00:00Z",
  "level": "INFO",
  "scan_id": "QA-RPT-2026-06-18-a1b2c3",
  "component": "agentic_review_engine",
  "agent": "security",
  "event": "agent.completed",
  "file": "src/api/users.py",
  "finding_count": 3,
  "cost_usd": 0.0042,
  "duration_ms": 2340,
  "model": "claude-sonnet-4-20250514"
}
```

**Log levels**:
- `ERROR`: Component failure requiring attention (LLM circuit breaker open, report write failure)
- `WARNING`: Degraded operation (tool not available, file skipped, fallback model used)
- `INFO`: Normal operation milestones (scan started, tier completed, agent completed, report written)
- `DEBUG`: Detailed operation (tool execution details, prompt construction, finding details)

**Log destinations**: stdout (default for CLI and containers), file (configurable), syslog (configurable).

## 6.8 Alerting

For production CI/CD deployments, alert on:

| Alert | Condition | Severity | Action |
|---|---|---|---|
| LLM circuit breaker open | 5+ consecutive LLM failures | High | Check API key, check Anthropic status |
| Scan cost exceeds limit | Single scan > $10 (configurable) | Medium | Review scan scope, check for loops |
| Scan duration exceeds SLA | Single scan > 15 minutes | Medium | Check file count, check LLM latency |
| Quality gate failing consistently | 5+ consecutive gate failures on same repo | Low | Review findings, consider gate threshold adjustment |
| No Tier 1 tools available | All 27 tools report unavailable | High | Check container image, reinstall tools |

Alerts are emitted as structured log entries with `level: ERROR` and a machine-readable `alert` field. Integration with PagerDuty, OpsGenie, or Slack alerting is handled by the log aggregation system, not by the platform itself.

---

# Appendix: Architecture Decision Records

## ADR-01: CLI-First, No Server

**Decision**: The platform is a CLI application, not a web service.

**Rationale**: A scan is a bounded batch operation. It starts, processes, and finishes. There is no long-running state, no websocket connections, no real-time updates. A CLI application is simpler to deploy, test, debug, and operate than a web service. CI/CD integration works naturally through exit codes and artifact uploads.

**Consequence**: No REST API in v2. If a web UI or API is needed in the future, it can be built as a thin layer on top of the CLI — invoking `qa run` as a subprocess or importing the orchestrator directly.

## ADR-02: SQLite as Default Database

**Decision**: Use SQLite for finding persistence, scan history, and audit logs.

**Rationale**: SQLite requires zero configuration, no server process, and works everywhere Python runs. For the primary use case (CLI on developer machine or CI runner), SQLite is sufficient. PostgreSQL is supported as an alternative for team environments requiring concurrent access.

**Consequence**: No database server to manage. Limitations: single-writer concurrency (fine for per-scan access), no network access (fine for local/CI usage).

## ADR-03: Model Diversity for Validator Agent

**Decision**: The Finding Validator Agent should use a different model (Claude Opus) from the detection agents (Claude Sonnet).

**Rationale**: The TAP paper demonstrated that heterogeneous model pairs detect 17% more defects than homogeneous pairs. The 3+1 paper showed +10.3pp precision from using a different model for verification. Model diversity prevents correlated errors — if Sonnet hallucinates a finding, Opus is less likely to confirm the same hallucination.

**Consequence**: Higher per-finding cost for validation (Opus > Sonnet). Justified by precision improvement. Configurable — teams can set the same model for all agents if cost is a concern.

## ADR-04: No Agent-to-Agent Communication

**Decision**: Agents do not communicate with each other. Data flows through the pipeline only.

**Rationale**: Direct communication introduces coordination complexity, ordering dependencies, and distributed failure modes. Pipeline-mediated flow keeps agents independent and enables parallel execution. This is the pattern used by QASecClaw (Mission Orchestrator) and RADAR (funnel architecture).

**Consequence**: Agents cannot ask each other questions or build on each other's findings in real-time. Cross-agent insight happens in the Validator Agent (which sees all findings) and the Finding Manager (which deduplicates algorithmically).

## ADR-05: Fail-Open as Universal Safety Mode

**Decision**: Every fallible component defaults to retaining data on failure, not suppressing it.

**Rationale**: QASecClaw (Section VI.E): "If the LLM fails to return a valid response, QASecClaw retains all findings in the affected batch." RADAR (Section 2.4): "If any risk signal is detected, the diff is automatically disqualified from auto-acceptance." The cost of a false positive is developer annoyance. The cost of a false negative (suppressed real vulnerability) is a production incident.

**Consequence**: On LLM failure, the platform may over-report (showing unvalidated Tier 1 findings). This is preferable to silently hiding issues.
