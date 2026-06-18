# QA Platform v2 — Implementation Roadmap

**Document Type**: Phased Engineering Execution Plan
**Status**: Planning — No Implementation
**Date**: 2026-06-18
**Author Role**: VP of Engineering
**Input**: Engineering Planning (01), Architecture Design (02), Domain Design (03), Agentic Architecture (04)

---

# Roadmap Summary

| Phase | Focus | Key Deliverable |
|---|---|---|
| **Phase 1** | Foundation | Working CLI that scans a local repo with Tier 1 tools and produces a JSON report |
| **Phase 2** | Core Platform | Complete deterministic pipeline: Tier 1 tools + risk scoring + finding management + quality gate + dual reports + GitHub/Linear integration |
| **Phase 3** | AI Capabilities | All 5 agents operational: Correctness, Security, Design, Cross-File, Validator — with semantic memory, tool access, and fail-open safety |
| **Phase 4** | Production Readiness | Hardened for CI/CD deployment: performance, reliability, observability, security, container image, documentation |

**Critical path**: Phase 1 → Phase 2 → Phase 3 → Phase 4 (strictly sequential — each phase depends on the prior phase's deliverables).

**Constraint**: Audit-only enforcement must be verified at every phase. No phase is complete until the audit-only property is confirmed.

---

# Phase 1: Foundation

## Objectives

Establish the project skeleton, core domain models, repository access layer, and a minimal working CLI that demonstrates the end-to-end pipeline from "scan request" to "JSON report" — using only deterministic tools, no AI.

This phase proves the architecture works before introducing AI complexity.

## Tasks

### 1.1 Project Setup

| Task | Description | Output |
|---|---|---|
| **1.1.1** Initialize Python project | Python 3.11+, `pyproject.toml`, src layout (`src/qa_platform/`), `ruff` for linting, `pytest` for testing | Project skeleton with CI-ready structure |
| **1.1.2** Define package structure | Directories matching domain decomposition: `core/` (Finding, schemas), `agents/` (interfaces), `tools/` (Tier 1), `orchestration/`, `assessment/`, `reporting/`, `integrations/`, `infrastructure/` (git, llm, config, persistence) | Directory tree matching architecture spec Section 2 |
| **1.1.3** Set up development tooling | ruff config, pytest config, pre-commit hooks (ruff check), Makefile with `lint`, `test`, `typecheck` targets | Development environment reproducible from README |
| **1.1.4** Create `.qa-config.yml` schema | Pydantic models for full configuration schema (from architecture spec Section 2.13). All fields with defaults. Validation with clear error messages. | `QAConfig` Pydantic model, passes validation tests |

### 1.2 Core Domain Models

| Task | Description | Output |
|---|---|---|
| **1.2.1** Implement Finding entity | All fields from domain spec: id, source, tier, category, severity, confidence, classification, file, lines, title, explanation, evidence, recommendation, cwe, author, validation_status, lifecycle_state. Value objects: Severity, Confidence, FindingCategory, ValidationStatus, Classification, Evidence, AuthorAttribution. | `Finding` dataclass + value object enums, unit tested |
| **1.2.2** Implement ScanRequest / ScanResult | Value objects from orchestration domain spec. ScanRequest with all CLI flags. ScanResult with all output fields. | Dataclasses, unit tested |
| **1.2.3** Implement FindingFactory | `create_from_tool()` and `create_from_agent()` methods with validation: line number clamping, title length, enum validation. | Factory class, unit tested with edge cases |
| **1.2.4** Implement RepositoryContext, ChangeSet, FileSet | Value objects for pipeline data flow between stages. | Dataclasses, unit tested |

### 1.3 Repository Access Layer

| Task | Description | Output |
|---|---|---|
| **1.3.1** Implement GitOperations | Subprocess wrapper for git: `clone`, `diff`, `blame`, `log`, `get_config`, `get_current_branch`, `get_current_commit`, `get_remote_url`. All methods use `errors="replace"` for Unicode. `get_config` is silent on failure (no warning log). | Git wrapper, tested against a real git repo fixture |
| **1.3.2** Implement GitRepositoryResolver | Resolve local paths and remote URLs. Clone remote repos to temp dir. Checkout specific branch/commit. Cleanup in finally block. | Repository resolver, tested with local path and mock remote |
| **1.3.3** Implement GitChangeDetector | Diff-based change detection. Parse diff hunks into FileChange objects with line-level tracking. Full-file listing for audit mode. | Change detector, tested with fixture diffs |
| **1.3.4** Implement HygieneChecker | Binary detection (extension + content sniff), large file detection (configurable threshold), flagged file detection (node_modules, .env, __pycache__), privacy exclusion. | Hygiene checker, tested with fixture files |

### 1.4 Tier 1 Tool Interface

| Task | Description | Output |
|---|---|---|
| **1.4.1** Define Tier1Tool abstract interface | `is_available()`, `is_applicable(file)`, `run(file, repo)` methods. `_run_command()` helper with timeout. `_check_binary()` helper. | Abstract base class |
| **1.4.2** Implement Tier1Runner | Discover available tools, filter applicable per file, execute with error isolation, validate line numbers on output, aggregate results. | Runner class, tested with mock tools |
| **1.4.3** Implement 5 initial tools | ruff (Python linter), bandit (Python security), mypy (Python types), radon (complexity), semgrep (multi-language patterns). Each implements Tier1Tool interface. | 5 tool wrappers, integration tested against real tool binaries |

### 1.5 Minimal Pipeline

| Task | Description | Output |
|---|---|---|
| **1.5.1** Implement ScanOrchestrator skeleton | Phase 1-2 only: resolve repo → detect changes → hygiene check → run Tier 1 tools → basic finding management → produce result. No risk scoring, no agents, no quality gate. | Orchestrator that produces findings from Tier 1 tools |
| **1.5.2** Implement basic FindingManager | Line number validation only. No dedup, clustering, or ranking yet. | Minimal finding post-processing |
| **1.5.3** Implement JSON ReportGenerator | Produce a JSON file with report_metadata, repository_context, findings, and scope_summary sections. Minimal — just enough to verify the pipeline works end-to-end. | JSON report from a scan |
| **1.5.4** Implement CLI entry point | `qa run --repo <path> --tiers 1 --report json` command. Progress output to terminal. Result summary on completion. | Working CLI command |

### 1.6 Configuration

| Task | Description | Output |
|---|---|---|
| **1.6.1** Implement ConfigManager | Load `.qa-config.yml` from repo root. Validate with Pydantic. Return defaults when absent. Resolve `${ENV_VAR}` references. | Config loader, tested with valid/invalid/missing configs |

## Dependencies

- Python 3.11+ installed
- Git binary installed
- At least one Tier 1 tool binary installed (ruff is sufficient for initial testing)

## Engineering Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Tier 1 tool output parsing breaks across tool versions | Medium | Low | Pin tool versions in tests. Parse defensively — malformed output → empty findings, not crash. |
| Git operations fail on edge cases (shallow clones, detached HEAD, submodules) | Medium | Medium | Test with diverse repo fixtures. Handle all git errors gracefully with meaningful messages. |
| Pydantic schema is too rigid for real configs | Low | Medium | Use Optional fields with defaults everywhere. Validate permissively — warn on unknown fields, don't reject. |

## Acceptance Criteria

1. `qa run --repo <local-python-repo> --tiers 1 --report json` produces a valid JSON report with findings from ruff, bandit, mypy, radon, and semgrep.
2. All findings have valid line numbers (clamped to file length).
3. Binary files and large files are skipped with hygiene findings in the report.
4. The scan completes without modifying any file in the scanned repository (audit-only verified).
5. The scan handles missing tools gracefully — tools that aren't installed are skipped with a log message.
6. All unit tests pass. All integration tests pass against a fixture repository.
7. `ruff check` produces zero warnings on the platform source code.

## Expected Outputs

- Working CLI: `qa run --repo . --tiers 1 --report json`
- JSON report with Tier 1 findings
- 5 Tier 1 tool wrappers
- Core domain models (Finding, ScanRequest, ScanResult, etc.)
- Git operations layer
- Configuration loader
- Project with test suite

---

# Phase 2: Core Platform

## Objectives

Build the complete deterministic pipeline: all Tier 1 tools, risk scoring, full finding management (dedup, clustering, classification, attribution, suppression), quality gate with graduated enforcement, dual report generation (full + executive), and external integrations (GitHub, Linear, Slack).

At the end of this phase, the platform is fully functional for Tier 1-only scans with complete reporting and integration — everything except AI agents.

## Tasks

### 2.1 Complete Tier 1 Tool Suite

| Task | Description | Output |
|---|---|---|
| **2.1.1** Implement remaining pip-installable tools | pip-audit (dependencies), sqlfluff (SQL), checkov (IaC), pip-licenses (license compliance) | 4 additional tool wrappers |
| **2.1.2** Implement external binary tools | gitleaks (secrets), hadolint (Dockerfile), shellcheck (shell scripts), osv-scanner (Google vuln DB), trivy (container scanning) | 5 additional tool wrappers |
| **2.1.3** Implement npm-based tools | jscpd (copy-paste detection), markdownlint (Markdown), prettier (formatting check), stylelint (CSS) | 4 additional tool wrappers |
| **2.1.4** Implement custom analysis tools | complexity analyzer (radon wrapper with thresholds), security patterns (regex-based detection for common patterns), dead code detector, interface checker, migration checker, call graph analyzer, test coverage gap detector, version drift detector, unused module detector, codebase map generator | 10 additional tool wrappers |
| **2.1.5** Tool auto-discovery | Tier1Runner discovers all available tools at scan start. Log which tools are available vs skipped. | Dynamic tool discovery, no hardcoded tool list |

### 2.2 Risk Scoring

| Task | Description | Output |
|---|---|---|
| **2.2.1** Implement RiskScorer | Per-file score: `complexity × change_size × sast_count × path_sensitivity`. Configurable threshold. Path sensitivity map (auth/ → high, test/ → low). Output: high-risk and low-risk file lists. | Risk scorer, tested with diverse file sets |
| **2.2.2** Wire into orchestrator | After Tier 1 completes, score files and partition into high-risk (future agent review) and low-risk (Tier 1 only). For now, both get Tier 1 only — agent review comes in Phase 3. | Orchestrator uses risk scores for file routing |

### 2.3 Finding Management Pipeline

| Task | Description | Output |
|---|---|---|
| **2.3.1** Implement FindingDeduplicator | Match: same file + overlapping lines (±3) + similar title (suppression_key match or >0.8 similarity). Keep highest-confidence finding. Merge evidence from duplicates. | Deduplicator, tested with duplicate and near-duplicate findings |
| **2.3.2** Implement FindingClusterer | Group by suppression_key prefix + file proximity. Assign cluster_id and root_cause. | Clusterer, tested with clusterable findings |
| **2.3.3** Implement DiffClassifier | Classify findings as introduced/modified/pre-existing based on diff line ranges. | Classifier, tested with fixture diffs |
| **2.3.4** Implement AuthorAttributor | Git blame for per-finding attribution. Fallback chain: git blame → PR author → git config user → configurable default. Silent on git config failure. | Attributor, tested with blame fixtures |
| **2.3.5** Implement SnippetExtractor | Read file, extract lines around finding (3 above, 3 below), mark flagged lines. Strip control characters from each line. Handle missing files and out-of-range lines. | Snippet extractor, tested with edge cases |
| **2.3.6** Implement SuppressionApplicator | Match finding suppression_key against configured rules. Check file scope, expiry, approval. Return active and suppressed lists. | Suppression logic, tested with rule matching |
| **2.3.7** Implement FindingRanker | Sort: severity desc → confidence desc → classification (introduced first) → file path. | Ranker, tested with diverse findings |
| **2.3.8** Implement FindingLineValidator | Clamp all finding line numbers to actual file length. Cache file line counts per file. | Line validator, tested with out-of-range findings |
| **2.3.9** Assemble FindingManager | Wire all 8 steps into FindingManager.process(). Execute in order: validate → dedup → classify → attribute → extract → suppress → cluster → rank → assign IDs. | Complete finding management pipeline |

### 2.4 Quality Gate

| Task | Description | Output |
|---|---|---|
| **2.4.1** Implement QualityGate | Count findings by severity (filtered by minimum confidence). Compare against thresholds. Graduated enforcement: shadow/advisory/enforced. | Quality gate, tested with all three modes |
| **2.4.2** Implement gate override support | Override storage (in-memory or SQLite). Override validation (approved_by, reason, expiry). Override expiry checking. | Override mechanism |
| **2.4.3** Implement per-agent graduation | New agents start in shadow mode. Findings from shadow agents are logged but don't affect gate. Configurable promotion per agent. | Agent graduation logic |

### 2.5 Report Generation

| Task | Description | Output |
|---|---|---|
| **2.5.1** Implement full ReportGenerator | All 11 sections: metadata, repo context, attribution, scope, executive summary, findings, clusters, resolved issues, positive observations, suppressed findings, appendix. JSON output. | Complete JSON report |
| **2.5.2** Implement HTML/PDF rendering | HTML template with CSS styling. WeasyPrint conversion. Fallback to HTML if WeasyPrint unavailable. Control character sanitization via TextSanitizer. | PDF report (or HTML fallback) |
| **2.5.3** Implement ExecutiveReportGenerator | Curation logic (filter low-confidence, low-severity, pre-existing non-critical). Action items table with full text (no truncation). Column widths with word-wrap. By-category summary. Noise reduction section. | Executive report (JSON + PDF) |

### 2.6 External Integrations

| Task | Description | Output |
|---|---|---|
| **2.6.1** Implement IntegrationDispatcher | Registry of IntegrationTarget implementations. Iterate configured targets. Error isolation per target. | Dispatcher, tested with mock targets |
| **2.6.2** Implement GitHubIntegration | PR summary comment. Inline review comments on file:line in diff. Commit status check (pass/fail). Uses httpx for API calls. | GitHub integration, tested with mock API |
| **2.6.3** Implement LinearIntegration | One parent issue per scan. Sub-issues per finding (up to configurable max). Developer assignment by email match. GraphQL API via httpx. | Linear integration, tested with mock API |
| **2.6.4** Implement SlackIntegration | Webhook POST with scan summary. Configurable notification triggers. | Slack integration, tested with mock webhook |

### 2.7 Persistence

| Task | Description | Output |
|---|---|---|
| **2.7.1** Implement SQLite database schema | Tables: scans, findings, suppressions, audit_log, gate_overrides. Init on first use. | Database initialization and migrations |
| **2.7.2** Implement SQLiteFindingRepository | Save and query findings. History lookup by suppression_key. Lifecycle state updates. | Finding persistence |
| **2.7.3** Implement SQLiteScanRepository | Save scan metadata. List scans by repo. | Scan history |

### 2.8 CLI Completion

| Task | Description | Output |
|---|---|---|
| **2.8.1** Add all CLI flags | `--branch`, `--commit`, `--pr`, `--vs`, `--audit`, `--agents`, `--report`, `--output`, `--full`, `--dry-run`, `--cost-estimate`, `--post-comment`, `--github-token`, `--cost-limit` | Complete CLI interface |
| **2.8.2** Add progress feedback | Step-by-step progress messages during scan. Tier completion, file counts, finding counts. | User-facing progress during scans |
| **2.8.3** Add scan result summary | On completion: report ID, finding count, severity distribution, gate status, duration, cost, report paths. | Terminal output summary |

## Dependencies

- Phase 1 complete
- Tier 1 tool binaries installed (graceful skip for missing ones)
- GitHub token for GitHub integration testing
- Linear API key for Linear integration testing

## Engineering Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Finding deduplication produces false merges | Medium | Medium | Conservative matching (high similarity threshold). Test with known-distinct similar findings. Err on side of keeping both. |
| Quality gate blocks legitimate PRs | Medium | High | Start in shadow mode. Collect data before enabling enforced mode. Graduated promotion. |
| Integration rate limits from GitHub/Linear | Low | Low | Implement rate limit handling with backoff. Cap inline comments per PR. |
| PDF generation fails on special characters | Medium | Low | TextSanitizer strips control characters. HTML fallback if WeasyPrint fails. Already solved in Phase 1 architecture. |

## Acceptance Criteria

1. `qa run --repo <local-repo> --tiers 1 --report json,pdf` produces both full and executive reports.
2. Findings are deduplicated, clustered, classified, attributed, and ranked correctly.
3. Quality gate evaluates correctly in shadow, advisory, and enforced modes.
4. `qa run --repo . --pr 42 --post-comment` posts inline comments on a real GitHub PR.
5. Linear ticket creation works with real Linear API.
6. Scan history is persisted and queryable.
7. All 27 Tier 1 tools are implemented (skipping gracefully when binary not installed).
8. Executive report has full action text (no truncation), proper column widths.
9. Audit-only constraint verified: no file in the scanned repository is modified.
10. All tests pass. Test coverage >80% for core domain logic.

## Expected Outputs

- Complete Tier 1 scanning with 27 tools
- Risk scoring per file
- Full finding management pipeline (8 processing steps)
- Quality gate with graduated enforcement
- Dual report generation (full + executive, JSON + PDF)
- GitHub PR comments + status checks
- Linear ticket creation
- Slack notifications
- Scan history persistence
- Complete CLI with all flags

---

# Phase 3: AI Capabilities

## Objectives

Implement all 5 agents with their agentic properties: autonomous tool use, semantic memory, three-pass review structure, fail-open safety, and independent validation. Wire agents into the orchestrator pipeline. Enable full Tier 2 and Tier 3 scans.

This is the most complex phase. Agents are the core differentiator of the platform.

## Tasks

### 3.1 LLM Infrastructure

| Task | Description | Output |
|---|---|---|
| **3.1.1** Implement LLMClient interface | Abstract interface: `call(system_prompt, user_message, output_schema, model) → LLMResponse`. Response includes: content, model, tokens, cost, success, error. | Interface definition |
| **3.1.2** Implement AnthropicLLMClient | Anthropic SDK integration. Structured JSON output with schema validation. Retry with exponential backoff (max 3). Temperature=0. Token/cost tracking per call. | Working LLM client, tested with real API |
| **3.1.3** Implement circuit breaker | 3 states: Closed (normal), Open (failed — skip all calls), Half-Open (testing). Threshold: 5 consecutive failures → Open. Cooldown: 60 seconds. | Circuit breaker, unit tested with failure sequences |
| **3.1.4** Implement model fallback chain | Per-agent model config: primary → secondary → skip. On primary failure, try secondary. On all failure, return failure (fail-open handled by caller). | Fallback logic, tested with mock failures |
| **3.1.5** Implement cost tracking | CostTracker: record per call (agent, model, tokens, cost). Running total. Limit checking. Summary by agent and model. | Cost tracker, unit tested |

### 3.2 Agent Infrastructure

| Task | Description | Output |
|---|---|---|
| **3.2.1** Implement ReviewAgent abstract interface | Abstract class with: `review_file()`, `review_file_group()`, `get_system_prompt()`, `get_semantic_memory()`. Properties: name, tier, category, cognitive_mode. | Agent interface |
| **3.2.2** Implement AgentRegistry | Register/discover agents. Query by name, tier, or all. Plugin-style: agents register at startup. | Registry, tested |
| **3.2.3** Implement AgentToolProvider | Read-only tools: `read_file`, `grep`, `git_diff`, `expand_context`, `list_directory`. All read-only — no write methods exist. Wrapped for agent invocation via LLM tool-use protocol. | Tool provider, tested |
| **3.2.4** Implement SemanticMemoryLoader | Load SAST rules from bundled JSON. Load CWE taxonomy tree from bundled JSON. Load project conventions from config. Load design principles from bundled file. | Memory loader, tested |
| **3.2.5** Create SAST rules knowledge base | Curate CodeQL patterns with CWE mappings, severity, vulnerable/secure examples, remediation steps. Cover: injection (SQLi, XSS, command), auth, crypto, path traversal, data exposure. | `knowledge/sast_rules.json` — structured SAST rules |
| **3.2.6** Create CWE taxonomy knowledge base | Hierarchical CWE tree with: ID, name, parent, description, detection indicators, remediation guidance. Cover top 25 CWEs. | `knowledge/cwe_tree.json` — CWE taxonomy |

### 3.3 Agent Implementations

| Task | Description | Output |
|---|---|---|
| **3.3.1** Implement CorrectnessAgent | System prompt for constructive execution tracing. Three-pass structure (scan → investigate → verify). Tool-use for code navigation. Structured JSON output matching Finding schema. | Working correctness agent, tested against fixture repos |
| **3.3.2** Write correctness agent prompt | Externalized prompt file: `prompts/correctness_agent.txt`. Role, workflow (3 passes), tool descriptions, output format, verification instructions. | Prompt file |
| **3.3.3** Implement SecurityAgent | System prompt for adversarial taint tracing. SAST finding validation (TP/FP with reasoning). CWE classification using taxonomy. Remediation from SAST rules. Fail-open: retain all SAST findings on LLM failure. | Working security agent, tested with SAST findings |
| **3.3.4** Write security agent prompt | Externalized prompt: `prompts/security_agent.txt`. Adversarial role, SAST validation workflow, taint tracing instructions, CWE classification process, fail-open directive. | Prompt file |
| **3.3.5** Implement DesignAgent | System prompt for evaluative structural assessment. SOLID evaluation, complexity assessment, naming review, test adequacy. Improvement suggestions with rationale and examples. | Working design agent, tested against fixture repos |
| **3.3.6** Write design agent prompt | Externalized prompt: `prompts/design_agent.txt`. Evaluative role, structural assessment checklist, improvement suggestion format. | Prompt file |
| **3.3.7** Implement CrossFileAgent | System prompt for comparative multi-file analysis. Module boundary detection. Pattern comparison across file groups. Consistency and contract checking. Conditional execution. | Working cross-file agent, tested with multi-file fixtures |
| **3.3.8** Write cross-file agent prompt | Externalized prompt: `prompts/cross_file_agent.txt`. Comparative role, consistency checklist, systemic finding format. | Prompt file |
| **3.3.9** Implement ValidatorAgent | System prompt for skeptical adversarial challenge. Independent code re-reading. Finding-by-finding validation with reasoning. Semantic dedup across agents. Confidence calibration. Fail-open on LLM failure. | Working validator agent, tested with known TP and FP findings |
| **3.3.10** Write validator agent prompt | Externalized prompt: `prompts/validator_agent.txt`. Skeptical role, refutation workflow, evidence checking process, dedup instructions, fail-open directive. | Prompt file |

### 3.4 Agentic Review Engine

| Task | Description | Output |
|---|---|---|
| **3.4.1** Implement AgenticReviewEngine | Query agent registry for applicable agents. Build FileReviewContext per file. Execute Agents 1-3 in parallel per file. Execute Agent 4 conditionally. Collect findings. Handle per-agent failures (fail-open). Check cost limit after each file. | Review engine, tested with mock agents and real agents |
| **3.4.2** Implement ValidationEngine | Batch findings (default batch size 15). Invoke ValidatorAgent per batch. Collect validation verdicts. Apply fail-open for failed batches (mark UNVALIDATED, retain). | Validation engine, tested with diverse finding sets |
| **3.4.3** Wire into ScanOrchestrator | After Tier 1 + risk scoring: run agentic review engine on high-risk files. After agents: run validation engine on all findings. Pass validated findings to finding management pipeline. | Complete Tier 2 + validation pipeline |

### 3.5 Model Configuration

| Task | Description | Output |
|---|---|---|
| **3.5.1** Configure model assignments | Detection agents (1-4): Claude Sonnet. Validator agent (5): Claude Opus. Fallback chain per agent. Configurable via `.qa-config.yml`. | Model configuration in config schema |
| **3.5.2** Implement per-agent LLM client instances | Separate LLM client instances for detection vs validation (different model config). Shared cost tracking. | Per-agent model routing |

### 3.6 Audit Log

| Task | Description | Output |
|---|---|---|
| **3.6.1** Implement SQLiteAuditLogger | Log every LLM call: scan_id, agent_name, model, prompt_hash (SHA-256), input_tokens, output_tokens, cost, finding_ids, timestamp, status. | Audit logger, queryable |
| **3.6.2** Wire into LLM client | Every `call()` produces an audit log entry. Success and failure both logged. | Automatic audit logging |

## Dependencies

- Phase 2 complete (full deterministic pipeline working)
- Anthropic API key with access to Claude Sonnet and Claude Opus
- SAST rules and CWE knowledge bases created (Task 3.2.5, 3.2.6)

## Engineering Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Agent prompts produce low-quality findings on first attempt | High | High | Iterative prompt development. Test against diverse codebases. Start agents in shadow mode. Use validator to catch low-quality findings. |
| LLM API costs exceed budget during development | Medium | Medium | Use `--cost-limit` flag during testing. Track costs in real-time via CostTracker. Use Haiku for development iterations, Sonnet for quality testing. |
| Agent tool-use protocol doesn't work reliably | Medium | High | Use Anthropic's native tool-use API (structured, schema-validated). Validate tool call responses. Handle malformed tool calls gracefully. |
| Semantic memory (SAST rules) doesn't fit in context window | Low | High | Measure token count of knowledge bases. If too large, implement retrieval: load only rules relevant to the file's language and detected SAST findings. |
| Model diversity causes inconsistent behavior between detection and validation | Medium | Medium | Model diversity is intentional (prevents correlated errors). Accept that validation may disagree with detection — that's the point. Document model-specific behaviors in agent prompts. |

## Acceptance Criteria

1. `qa run --repo <python-repo> --tiers 1,2 --report json` produces findings from both Tier 1 tools and AI agents.
2. Correctness Agent identifies logic bugs that no Tier 1 tool catches (tested with planted bugs in fixture repo).
3. Security Agent validates SAST findings — correctly classifying known true positives and known false positives (tested with OWASP-style test cases).
4. Design Agent produces improvement suggestions that are concrete and actionable (human evaluation on 3 real repositories).
5. Cross-File Agent detects consistency issues across module boundaries (tested with planted inconsistencies).
6. Validator Agent reduces false positives — measured by comparing finding quality before and after validation on a labeled dataset.
7. Fail-open works: when LLM API is unreachable, the scan produces a Tier 1-only report without crashing.
8. Fail-open for Security Agent: when LLM fails, ALL SAST findings are retained in the report.
9. Cost tracking is accurate — per-agent cost matches Anthropic API billing.
10. Audit log captures every LLM call with prompt hash, tokens, cost, and finding IDs.
11. All agent prompts are externalized in `prompts/` directory — editable without code changes.
12. Audit-only constraint verified: agents cannot write to the repository (no write tools exist).

## Expected Outputs

- 5 working agents (Correctness, Security, Design, Cross-File, Validator)
- 5 externalized agent prompts
- SAST rules knowledge base (30+ rules with CWE mappings)
- CWE taxonomy knowledge base (top 25 CWEs)
- Agentic review engine with parallel execution
- Validation engine with batched processing
- LLM client with circuit breaker, retry, fallback
- Per-agent model configuration
- Cost tracking and audit logging
- Complete Tier 1 + Tier 2 + Tier 3 + Validation pipeline

---

# Phase 4: Production Readiness

## Objectives

Harden the platform for production CI/CD deployment: performance optimization, reliability testing, security review, observability instrumentation, container image, documentation, and release packaging.

## Tasks

### 4.1 Performance

| Task | Description | Output |
|---|---|---|
| **4.1.1** Benchmark Tier 1 scan performance | Target: 100-file PR in under 60 seconds. Profile tool execution. Identify bottlenecks. | Benchmark results, optimization if needed |
| **4.1.2** Benchmark agentic review performance | Target: 10-file PR (full pipeline) in under 5 minutes. Profile LLM call latency. Measure parallel execution efficiency. | Benchmark results |
| **4.1.3** Optimize agent context size | Measure token consumption per agent. Optimize file content inclusion (diff-centric, not full file for large files). Ensure semantic memory fits in context. | Token optimization, measured improvement |
| **4.1.4** Implement pre-commit fast mode | Subset of fast Tier 1 tools only (ruff, bandit — no semgrep, no mypy). Target: under 10 seconds. Exit on first critical finding. | Pre-commit hook command |

### 4.2 Reliability

| Task | Description | Output |
|---|---|---|
| **4.2.1** Stress test with large repositories | Test with repos of 100K+, 250K+, 500K+ lines of code. Verify memory usage, timeout handling, and finding management at scale. | Stress test results, fixes for discovered issues |
| **4.2.2** Test fail-open behavior end-to-end | Simulate LLM API downtime, tool binary crashes, git failures, disk full conditions. Verify the platform degrades gracefully in each case. | Failure scenario test suite |
| **4.2.3** Test edge cases in finding management | Empty repos, repos with no changes, binary-only repos, repos with 1000+ findings, deeply nested directories, Unicode filenames. | Edge case test suite |
| **4.2.4** Implement idempotency verification | Run the same scan twice on the same commit. Verify consistent finding count and severity distribution (modulo LLM non-determinism at temperature=0). | Idempotency test |

### 4.3 Security

| Task | Description | Output |
|---|---|---|
| **4.3.1** Audit-only verification | Automated test: scan a repo, verify zero files modified (checksum comparison before/after). Run on every CI build. | Audit-only verification test |
| **4.3.2** Secrets handling review | Verify API keys are never logged, never in reports, never in database. Verify `privacy.ai_exclude_paths` works — excluded files never reach LLM. | Security audit checklist |
| **4.3.3** Prompt injection review | Test agent prompts against adversarial code inputs (code that contains instructions to the LLM). Verify agents don't follow in-code instructions. | Prompt injection test cases |

### 4.4 Observability

| Task | Description | Output |
|---|---|---|
| **4.4.1** Implement structured logging | JSON format for all log entries. Correlation ID (scan_id) on every log. Component name. Event type. | Structured logging throughout |
| **4.4.2** Implement metrics emission | Scan duration, scan cost, finding counts, agent failure rate, tool availability, gate pass rate — emitted as structured log entries. | Metrics in log output |
| **4.4.3** Verify audit trail completeness | Every LLM call logged. Every finding traceable to source agent. Every validation decision documented. Every suppression has reasoning. | Audit trail verification test |

### 4.5 Container and Deployment

| Task | Description | Output |
|---|---|---|
| **4.5.1** Create Dockerfile | Multi-stage build. Python 3.11 slim base. All pip tools. Optional external binaries layer. Entrypoint: `qa`. | `Dockerfile` |
| **4.5.2** Create GitHub Actions workflow example | Reusable workflow YAML. Checkout → install → run scan → post comments → upload report artifact. | `.github/workflows/qa-review.yml` example |
| **4.5.3** Create Kubernetes Job spec example | Job template for K8s-based execution. Secret references. Resource limits. | `k8s/qa-scan-job.yaml` example |
| **4.5.4** Create pip package | `pyproject.toml` with all dependencies. CLI entry point. PyPI-ready packaging. | `pip install qa-platform` works |

### 4.6 Documentation

| Task | Description | Output |
|---|---|---|
| **4.6.1** Write README | Project overview, installation, quick start, configuration reference, CLI reference. | `README.md` |
| **4.6.2** Write INSTALL guide | Detailed installation: Python, pip tools, external binaries, npm tools. Per-OS instructions. | `INSTALL.md` |
| **4.6.3** Write ARCHITECTURE guide | System overview, component diagram, data flow, agent descriptions, extension points. | `ARCHITECTURE.md` |
| **4.6.4** Write configuration reference | Every `.qa-config.yml` field with description, type, default, and example. | Configuration documentation |
| **4.6.5** Write agent tuning guide | How to modify agent prompts, add semantic memory, adjust thresholds, graduate agents. | Agent tuning documentation |

## Dependencies

- Phase 3 complete (all agents working)
- Access to large real-world repositories for stress testing
- Container runtime (Docker) for image building
- PyPI account for package publishing (or private registry)

## Engineering Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Performance doesn't meet targets on large repos | Medium | Medium | Profile and optimize. Limit concurrent LLM calls. Implement file-level timeout. Accept slower scans for large audits. |
| Prompt injection through adversarial code | Low | High | Test with known prompt injection patterns. Harden agent prompts with explicit boundaries. Monitor for anomalous agent behavior. |
| Container image too large | Low | Low | Multi-stage build. Separate layers for required vs optional tools. Slim base image. |

## Acceptance Criteria

1. Tier 1 scan of 100 files completes in under 60 seconds.
2. Full agentic pipeline for 10 files completes in under 5 minutes.
3. Pre-commit hook completes in under 10 seconds.
4. Platform handles 500K-line repository without crash or timeout.
5. Fail-open works for every failure scenario (LLM down, tool crash, disk full, git error).
6. Audit-only verified: automated test confirms zero files modified in scanned repo.
7. Secrets never appear in logs or reports (verified by grep).
8. Privacy exclusion prevents specified paths from reaching LLM API.
9. Structured logs with correlation IDs produced for every scan.
10. Docker image builds and runs successfully.
11. `pip install qa-platform && qa run --repo . --tiers 1 --report json` works from a clean install.
12. README, INSTALL, and ARCHITECTURE docs are complete and accurate.

## Expected Outputs

- Performance benchmarks and optimizations
- Fail-open verification test suite
- Edge case test suite
- Security audit (audit-only, secrets, prompt injection)
- Structured logging and metrics
- Docker image
- GitHub Actions workflow example
- Kubernetes Job spec example
- pip package
- Complete documentation (README, INSTALL, ARCHITECTURE, config reference, agent tuning guide)

---

# Phase Dependencies

```
Phase 1: Foundation
    │
    │  Delivers: core models, git layer, 5 Tier 1 tools, minimal CLI, JSON report
    │
    ▼
Phase 2: Core Platform
    │
    │  Delivers: 27 tools, risk scoring, finding pipeline, quality gate,
    │           dual reports, integrations, persistence
    │
    ▼
Phase 3: AI Capabilities
    │
    │  Delivers: 5 agents, semantic memory, validation, LLM client,
    │           audit logging, complete Tier 1+2+3 pipeline
    │
    ▼
Phase 4: Production Readiness
    │
    │  Delivers: performance, reliability, security, observability,
    │           container, package, documentation
    │
    ▼
    RELEASE
```

---

# Risk Register (Cross-Phase)

| # | Risk | Phase | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|---|
| R1 | Agent prompt quality requires multiple iterations | 3 | High | High | Budget for 3-5 prompt iterations per agent. Use shadow mode for initial rollout. Use validator to catch low-quality findings. | AI Systems Architect |
| R2 | LLM API costs exceed projections | 3-4 | Medium | Medium | Cost limit enforcement. Risk-based routing. Model selection per agent (Sonnet for detection, Opus only for validation). Benchmark cost per scan before rollout. | VP Engineering |
| R3 | Developer trust erodes due to false positives | 3-4 | Medium | High | Validator agent is the primary mitigation. Target <15% FP rate. Start in shadow mode. Collect resolution rate data before enforcing quality gate. | Product Engineering Lead |
| R4 | Audit-only constraint violated by a bug | 1-4 | Low | Critical | Automated verification test on every CI build. No write tools in agent interface. Clone-based isolation for remote repos. | Chief Architect |
| R5 | Tier 1 tool binaries unavailable in CI environment | 2-4 | Medium | Low | Graceful degradation — missing tools are skipped. Docker image includes all tools. Document minimum tool requirements. | DevOps |
| R6 | Context window limits prevent effective agent review of large files | 3 | Medium | Medium | Diff-centric perception (focus on changes). File chunking for files >500 lines. Prioritize high-risk code sections. | AI Systems Architect |
