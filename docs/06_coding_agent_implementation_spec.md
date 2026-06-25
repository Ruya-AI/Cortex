# Cortex QA Platform — Coding Agent Implementation Specification

**Document Type**: Implementation Manual for Autonomous Coding Agent
**Status**: Ready for Implementation
**Date**: 2026-06-18
**Input**: Engineering Planning (01), Architecture Design (02), Domain Design (03), Agentic Architecture (04), Implementation Roadmap (05)

**Purpose of this document**: Remove all ambiguity so that a coding agent can implement the system without guessing. Every decision is made. Every interface is defined. Every behavior is specified.

---

# 1. Repository Structure

## 1.1 Root Layout

```
cortex-v2/
├── src/
│   └── cortex_engine/
│       ├── __init__.py              # Package init, exports __version__
│       ├── core/                    # Core domain (Finding, schemas) — ZERO external deps
│       ├── agents/                  # Agent domain (interfaces + implementations)
│       ├── tools/                   # Tier 1 tool domain (interfaces + implementations)
│       ├── orchestration/           # Scan orchestrator, review engine, validation engine
│       ├── assessment/              # Quality gate, risk scorer
│       ├── reporting/               # Report generators (full + executive)
│       ├── integrations/            # GitHub, Linear, Slack
│       ├── infrastructure/          # Git ops, LLM client, config, persistence
│       ├── knowledge/               # Bundled knowledge files (SAST rules, CWE tree)
│       └── cli/                     # CLI entry point
├── prompts/                         # Externalized agent prompt files
│   ├── correctness_agent.txt
│   ├── security_agent.txt
│   ├── design_agent.txt
│   ├── cross_file_agent.txt
│   └── validator_agent.txt
├── tests/
│   ├── unit/                        # Unit tests (mirrors src/ structure)
│   ├── integration/                 # Integration tests (real tools, real git)
│   ├── fixtures/                    # Test fixture repositories and data
│   └── conftest.py                  # Shared pytest fixtures
├── pyproject.toml                   # Project metadata, dependencies, tool config
├── README.md
├── INSTALL.md
├── ARCHITECTURE.md
└── .qa-config.yml                   # Example configuration
```

## 1.2 Package Responsibilities

### `core/` — Core Domain (ZERO external dependencies)

```
core/
├── __init__.py
├── finding.py              # Finding entity, all value objects (Severity, Confidence, etc.)
├── schemas.py              # ScanRequest, ScanResult, RepositoryContext, ChangeSet, FileSet
├── finding_factory.py      # FindingFactory — create validated Finding instances
├── finding_deduplicator.py # Algorithmic deduplication
├── finding_clusterer.py    # Root-cause clustering
├── finding_ranker.py       # Priority ranking
├── finding_line_validator.py # Line number clamping
├── diff_classifier.py      # Introduced/modified/pre-existing classification
├── author_attributor.py    # Git blame attribution
├── snippet_extractor.py    # Code snippet extraction with control char sanitization
├── suppression.py          # Suppression rule matching and application
├── finding_manager.py      # Orchestrates all 8 finding processing steps
└── text_sanitizer.py       # Control character stripping for PDF output
```

**Rules for `core/`**:
- NO imports from any other `cortex_engine` package
- NO imports from external libraries (no anthropic, no httpx, no pydantic in entity definitions)
- Exception: Python stdlib only (dataclasses, enum, datetime, re, pathlib, hashlib)
- Pydantic is allowed ONLY in `schemas.py` for ScanRequest/ScanResult validation
- All types are plain Python: dataclasses, enums, NamedTuple, Protocol

### `agents/` — Agent Domain

```
agents/
├── __init__.py
├── base.py                 # ReviewAgent abstract interface (Protocol or ABC)
├── registry.py             # AgentRegistry — register/discover agents
├── tool_provider.py        # AgentToolProvider — read-only tools for agents
├── memory.py               # SemanticMemoryLoader — load knowledge documents
├── correctness.py          # CorrectnessAgent implementation
├── security.py             # SecurityAgent implementation
├── design.py               # DesignAgent implementation
├── cross_file.py           # CrossFileAgent implementation
└── validator.py            # ValidatorAgent implementation
```

**Rules for `agents/`**:
- Imports from `core/` (Finding, schemas): YES
- Imports from `infrastructure/` (LLMClient): via interface only (dependency injection)
- Each agent file contains ONE agent class
- Agent prompts are NOT in these files — they are loaded from `prompts/` directory

### `tools/` — Tier 1 Tool Domain

```
tools/
├── __init__.py
├── base.py                 # Tier1Tool abstract interface
├── runner.py               # Tier1Runner — execute all tools
├── ruff_tool.py            # Ruff linter wrapper
├── bandit_tool.py          # Bandit security scanner wrapper
├── mypy_tool.py            # Mypy type checker wrapper
├── semgrep_tool.py         # Semgrep pattern scanner wrapper
├── radon_tool.py           # Radon complexity analyzer wrapper
├── pip_audit_tool.py       # pip-audit dependency scanner
├── gitleaks_tool.py        # Gitleaks secret scanner
├── hadolint_tool.py        # Hadolint Dockerfile linter
├── shellcheck_tool.py      # ShellCheck shell script analyzer
├── sqlfluff_tool.py        # SQLFluff SQL linter
├── checkov_tool.py         # Checkov IaC scanner
├── pip_licenses_tool.py    # License compliance checker
├── jscpd_tool.py           # Copy-paste detector
├── markdownlint_tool.py    # Markdown linter
├── prettier_tool.py        # Prettier formatting checker
├── stylelint_tool.py       # CSS/SCSS linter
├── osv_scanner_tool.py     # OSV vulnerability scanner
├── trivy_tool.py           # Trivy container scanner
├── complexity_tool.py      # Custom complexity analysis
├── security_patterns.py    # Custom regex-based security patterns
├── dead_code_tool.py       # Dead code detector
├── interface_checker.py    # Interface consistency checker
├── migration_checker.py    # Migration safety checker
├── call_graph_tool.py      # Call graph analyzer
├── test_coverage_gap.py    # Test coverage gap detector
├── version_drift_tool.py   # Version drift detector
├── unused_module_tool.py   # Unused module detector
└── codebase_map_tool.py    # Codebase structure mapper
```

**Rules for `tools/`**:
- Each tool file contains ONE tool class extending `Tier1Tool`
- All tools use `subprocess.run` for external binary execution
- All tools return `list[Finding]` using `FindingFactory`
- Tools NEVER modify files

### `orchestration/` — Application Layer

```
orchestration/
├── __init__.py
├── orchestrator.py         # ScanOrchestrator — main pipeline controller
├── review_engine.py        # AgenticReviewEngine — manage agent execution
├── validation_engine.py    # ValidationEngine — manage validator agent
└── cost_tracker.py         # CostTracker — track LLM spend
```

### `assessment/` — Assessment Domain

```
assessment/
├── __init__.py
├── quality_gate.py         # QualityGate — threshold evaluation
├── risk_scorer.py          # RiskScorer — per-file risk assessment
└── gate_override.py        # Override management
```

### `reporting/` — Reporting Domain

```
reporting/
├── __init__.py
├── report_generator.py     # Full report (11 sections, JSON + PDF)
└── executive_report.py     # Executive report (concise, actionable)
```

### `integrations/` — Integration Domain

```
integrations/
├── __init__.py
├── dispatcher.py           # IntegrationDispatcher — route to targets
├── github.py               # GitHub PR comments + status checks
├── linear.py               # Linear ticket creation
└── slack.py                # Slack webhook notification
```

### `infrastructure/` — Infrastructure Layer

```
infrastructure/
├── __init__.py
├── git.py                  # GitOperations — all git subprocess wrappers
├── repository_resolver.py  # GitRepositoryResolver — resolve paths/URLs
├── change_detector.py      # GitChangeDetector — diff parsing
├── hygiene_checker.py      # File hygiene checking
├── llm_client.py           # AnthropicLLMClient — API wrapper with circuit breaker
├── config.py               # YAMLConfigManager — load .qa-config.yml
├── config_schema.py        # Pydantic models for QAConfig
├── database.py             # SQLite setup and connection management
├── finding_repository.py   # SQLiteFindingRepository
├── scan_repository.py      # SQLiteScanRepository
└── audit_logger.py         # SQLiteAuditLogger
```

### `cli/` — Interface Layer

```
cli/
├── __init__.py
└── run.py                  # CLI entry point: `qa run` command
```

### `knowledge/` — Bundled Knowledge Files

```
knowledge/
├── sast_rules.json         # SAST patterns with CWE mappings
├── cwe_tree.json           # CWE taxonomy hierarchy
├── design_principles.json  # SOLID, patterns catalog
└── language_idioms/        # Per-language common pitfalls
    ├── python.json
    ├── javascript.json
    ├── typescript.json
    └── go.json
```

---

# 2. Development Conventions

## 2.1 Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Files | `snake_case.py` | `finding_manager.py` |
| Classes | `PascalCase` | `FindingManager` |
| Functions/methods | `snake_case` | `process_findings()` |
| Private methods | `_leading_underscore` | `_compute_risk_score()` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_TITLE_LENGTH = 120` |
| Enums | `PascalCase` class, `UPPER_SNAKE_CASE` members | `Severity.CRITICAL` |
| Type aliases | `PascalCase` | `FindingList = list[Finding]` |
| Test files | `test_<module>.py` | `test_finding_manager.py` |
| Test functions | `test_<what>_<condition>_<expected>` | `test_dedup_same_file_same_line_merges()` |

## 2.2 Coding Standards

**Python version**: 3.11+ (use `from __future__ import annotations` in every file)

**Imports**:
```python
from __future__ import annotations

# stdlib
import logging
from pathlib import Path

# third-party (infrastructure only)
import httpx

# internal
from cortex_engine.core.finding import Finding, Severity
```

Order: `__future__` → stdlib → third-party → internal. Separated by blank lines.

**Type hints**: Required on ALL public method signatures. Optional on private methods and local variables.

**Docstrings**: None. Use clear method names and type hints instead. Only add a docstring if the WHY is non-obvious — never explain WHAT the code does.

**Comments**: Default to writing none. Only add one when:
- A hidden constraint exists ("line numbers are 1-based because git blame uses 1-based")
- A workaround is in place ("jscpd v5 writes to temp dir instead of stdout")
- Behavior would surprise a reader

**Error handling**:
- Catch specific exceptions, never bare `except:`
- Log warnings for recoverable failures, let the caller handle the degradation
- Never catch and silently swallow — at minimum log at WARNING level

**Logging**:
```python
logger = logging.getLogger(__name__)
```
One logger per module. Use `__name__` — never hardcode logger names.

**No comments referencing tasks/PRs/issues**: Comments like "added for issue #123" or "handles the case from PR #42" rot. Put that in the commit message.

## 2.3 Architecture Rules

**Rule 1: Dependency direction is inward only**

```
cli/ → orchestration/ → core/
                      → agents/ (interfaces in core/)
                      → tools/ (interfaces in core/)
                      → assessment/
                      → reporting/
                      → integrations/

infrastructure/ → core/ (implements core interfaces)
```

NEVER: `core/` imports from `agents/`, `tools/`, `orchestration/`, `infrastructure/`, `integrations/`, `reporting/`, or `cli/`.

**Rule 2: Interfaces in core, implementations in their package**

The `ReviewAgent` Protocol is defined in `agents/base.py` but depends ONLY on types from `core/`. The concrete agents (`CorrectnessAgent`, etc.) are in `agents/` and depend on `core/` + `infrastructure/` via dependency injection.

**Rule 3: No service creates its own dependencies**

Every service receives its dependencies through the constructor (dependency injection). The `ScanOrchestrator` receives `Tier1Runner`, `AgenticReviewEngine`, `QualityGate`, etc. — it does NOT instantiate them internally.

The CLI (`cli/run.py`) is the composition root — it creates all dependencies and wires them together.

**Rule 4: No shared mutable state between components**

Each scan runs independently. No global state. No singletons (except the logger). Components communicate through return values, not through shared objects.

**Rule 5: Every external call has a timeout**

Subprocess calls: timeout parameter (default 60s for tools, 300s for git clone).
HTTP calls: timeout parameter (default 30s for API calls).
LLM calls: timeout parameter (default 120s per call).

## 2.4 Dependency Rules

**Allowed external dependencies**:

| Package | Where Used | Purpose |
|---|---|---|
| `click` | `cli/` only | CLI framework |
| `pydantic` | `infrastructure/config_schema.py` only | Configuration validation |
| `pydantic-settings` | `infrastructure/config_schema.py` only | Environment variable resolution |
| `PyYAML` | `infrastructure/config.py` only | YAML parsing |
| `anthropic` | `infrastructure/llm_client.py` only | Claude API client |
| `httpx` | `integrations/` only | HTTP client for GitHub, Linear, Slack |
| `weasyprint` | `reporting/` only | PDF generation (optional) |
| `rich` | `cli/` only | Terminal output formatting |

**Forbidden dependencies**:
- No `langchain`, `llama_index`, or any agent framework — agents are implemented directly
- No `sqlalchemy` — use `sqlite3` stdlib directly
- No `celery`, `redis`, or any async job queue — synchronous pipeline
- No `flask`, `fastapi`, or any web framework — CLI only

---

# 3. Implementation Order

Execute these steps strictly in order. Each step produces testable output before the next step begins. Do NOT skip ahead.

## Step 1: Core Domain Models

**What to build**: All dataclasses, enums, and value objects in `core/`.

**Files to create**:
1. `core/__init__.py`
2. `core/finding.py` — Finding dataclass + Severity, Confidence, FindingCategory, ValidationStatus, Classification, LifecycleState, Evidence, AuthorAttribution enums/dataclasses
3. `core/schemas.py` — ScanRequest, ScanResult, RepositoryContext, ChangeSet, FileSet, FileChange, FileDiff, RiskAssessment dataclasses
4. `core/text_sanitizer.py` — `sanitize(text: str) → str` — strip control chars `[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]`

**Tests**: `tests/unit/core/test_finding.py`, `tests/unit/core/test_schemas.py`

**Verify**: All types instantiate correctly. Enums compare correctly. Severity ordering works.

## Step 2: Configuration

**What to build**: Configuration schema and loader.

**Files to create**:
1. `infrastructure/config_schema.py` — All Pydantic models for QAConfig (from architecture spec Section 2.13)
2. `infrastructure/config.py` — `load_config(repo_path: Path) → QAConfig` with YAML parsing, validation, defaults, env var resolution

**Tests**: `tests/unit/infrastructure/test_config.py` — valid config, missing config (defaults), invalid config (error messages), env var resolution

## Step 3: Git Operations

**What to build**: Git subprocess wrappers and repository access.

**Files to create**:
1. `infrastructure/git.py` — GitOperations: clone, diff, blame, log, get_config (silent on failure), get_current_branch, get_current_commit, get_remote_url. All methods use `errors="replace"`. All with timeout.
2. `infrastructure/repository_resolver.py` — Resolve local paths and remote URLs. Clone remote. Checkout branch/commit. Cleanup.
3. `infrastructure/change_detector.py` — Diff parsing. FileChange objects. Full-file listing for audit mode.
4. `infrastructure/hygiene_checker.py` — Binary detection, large file detection, flagged files, privacy exclusion.

**Tests**: Create a fixture git repository in `tests/fixtures/`. Test all git operations against it.

## Step 4: Finding Factory and Processing

**What to build**: Finding creation and all processing pipeline steps.

**Files to create**:
1. `core/finding_factory.py` — `create_from_tool()`, `create_from_agent()` with validation
2. `core/finding_line_validator.py` — Clamp line numbers to file length, cache file line counts
3. `core/finding_deduplicator.py` — Same file + overlapping lines + similar title → merge
4. `core/finding_clusterer.py` — Group by suppression_key prefix
5. `core/finding_ranker.py` — Sort by severity desc → confidence desc → classification → file
6. `core/diff_classifier.py` — Classify as introduced/modified/pre-existing from diff data
7. `core/author_attributor.py` — Git blame with fallback chain
8. `core/snippet_extractor.py` — Extract code context, strip control chars per line
9. `core/suppression.py` — Match suppression rules, check expiry/scope
10. `core/finding_manager.py` — Wire all 8 steps in order

**Tests**: Unit test each step independently. Integration test the full FindingManager pipeline.

## Step 5: Tier 1 Tool Interface and Initial Tools

**What to build**: Tool abstract interface, runner, and 5 initial tools.

**Files to create**:
1. `tools/base.py` — Tier1Tool ABC: `is_available()`, `is_applicable()`, `run()`, `_run_command()`, `_check_binary()`
2. `tools/runner.py` — Tier1Runner: discover, filter, execute, validate line numbers, aggregate
3. `tools/ruff_tool.py`
4. `tools/bandit_tool.py`
5. `tools/mypy_tool.py`
6. `tools/semgrep_tool.py`
7. `tools/radon_tool.py`

**Tests**: Unit test each tool with fixture code files. Integration test Tier1Runner with real tool binaries.

## Step 6: Risk Scorer and Quality Gate

**What to build**: Risk scoring and quality gate evaluation.

**Files to create**:
1. `assessment/risk_scorer.py` — Per-file score formula, threshold, file routing
2. `assessment/quality_gate.py` — Threshold evaluation, graduated enforcement (shadow/advisory/enforced)
3. `assessment/gate_override.py` — Override storage and validation

**Tests**: Unit test scorer with known files. Unit test gate with all three modes.

## Step 7: Report Generators

**What to build**: Full report and executive report generation.

**Files to create**:
1. `reporting/report_generator.py` — 11-section full report, JSON + HTML/PDF. TextSanitizer for PDF.
2. `reporting/executive_report.py` — Curated actionable report, action items table with full text, no truncation.

**Tests**: Snapshot tests — given fixed input findings, verify JSON output matches expected. Verify PDF generation doesn't crash (or HTML fallback works).

## Step 8: Scan Orchestrator (Tier 1 Only)

**What to build**: Pipeline orchestrator without agents.

**Files to create**:
1. `orchestration/orchestrator.py` — ScanOrchestrator: resolve → detect changes → hygiene → Tier 1 tools → risk score → finding management → quality gate → reports
2. `orchestration/cost_tracker.py` — CostTracker (initially just structure, used by agents later)

**Tests**: Integration test: `orchestrator.scan(ScanRequest(...))` against fixture repo → ScanResult with findings and reports.

## Step 9: CLI Entry Point

**What to build**: Working CLI command.

**Files to create**:
1. `cli/run.py` — Click command with all flags. Composition root: create all dependencies, wire them, call orchestrator. Progress output. Result summary.
2. `cli/__init__.py`

**Tests**: CLI integration test: `qa run --repo <fixture> --tiers 1 --report json` produces output.

## Step 10: Integration Layer

**What to build**: External service integrations.

**Files to create**:
1. `integrations/dispatcher.py` — IntegrationDispatcher, iterates targets
2. `integrations/github.py` — PR comments, inline comments, status check
3. `integrations/linear.py` — Parent issue + sub-issues
4. `integrations/slack.py` — Webhook notification

**Tests**: Unit test with mock HTTP responses.

## Step 11: Persistence

**What to build**: SQLite storage for scan history and audit.

**Files to create**:
1. `infrastructure/database.py` — SQLite init, table creation
2. `infrastructure/finding_repository.py` — Save/query findings
3. `infrastructure/scan_repository.py` — Save/query scans
4. `infrastructure/audit_logger.py` — LLM call audit log

**Tests**: Unit test CRUD operations.

## Step 12: Remaining Tier 1 Tools

**What to build**: All remaining 22 tool wrappers.

**Files to create**: One file per tool (listed in Section 1.2).

**Tests**: Unit test per tool with fixture files. Integration test tools that are installed.

## Step 13: LLM Client

**What to build**: Anthropic API client with reliability features.

**Files to create**:
1. `infrastructure/llm_client.py` — AnthropicLLMClient: call(), retry, backoff, circuit breaker, fallback chain, token/cost tracking, temperature=0, structured JSON output

**Tests**: Unit test with mock API responses. Test circuit breaker state transitions. Test fallback chain.

## Step 14: Agent Infrastructure

**What to build**: Agent interfaces, registry, tools, memory.

**Files to create**:
1. `agents/base.py` — ReviewAgent ABC/Protocol
2. `agents/registry.py` — AgentRegistry
3. `agents/tool_provider.py` — Read-only tools for agents
4. `agents/memory.py` — SemanticMemoryLoader

**Tests**: Unit test registry, tool provider, memory loader.

## Step 15: Knowledge Bases

**What to build**: SAST rules and CWE taxonomy data files.

**Files to create**:
1. `knowledge/sast_rules.json` — 30+ rules with CWE mappings, examples, remediation
2. `knowledge/cwe_tree.json` — Top 25 CWEs with hierarchy
3. `knowledge/design_principles.json` — SOLID principles with examples

**Tests**: Validate JSON schema. Verify all referenced CWEs exist in tree.

## Step 16: Agent Implementations

**What to build**: All 5 agents + their prompts.

**Files to create** (in this order):
1. `prompts/correctness_agent.txt` → `agents/correctness.py`
2. `prompts/security_agent.txt` → `agents/security.py`
3. `prompts/design_agent.txt` → `agents/design.py`
4. `prompts/cross_file_agent.txt` → `agents/cross_file.py`
5. `prompts/validator_agent.txt` → `agents/validator.py`

**Tests**: Test each agent against fixture repos with known issues. Test fail-open behavior.

## Step 17: Agentic Review Engine and Validation Engine

**What to build**: Agent execution management.

**Files to create**:
1. `orchestration/review_engine.py` — AgenticReviewEngine: parallel agent execution, cost limit checking
2. `orchestration/validation_engine.py` — ValidationEngine: batched validator execution, fail-open

**Tests**: Integration test with real agents on fixture repos.

## Step 18: Wire Agents into Orchestrator

**What to build**: Complete pipeline with agents.

**Modify**: `orchestration/orchestrator.py` — Add agent review and validation phases after risk scoring.

**Tests**: Full pipeline test: `orchestrator.scan(ScanRequest(tiers=[1,2]))` → ScanResult with both Tier 1 and agent findings.

## Step 19: Production Hardening

**What to build**: Performance, reliability, observability.

**Tasks**:
- Structured JSON logging throughout
- Benchmark tests for performance targets
- Fail-open verification tests
- Audit-only verification test
- Edge case tests

## Step 20: Packaging and Documentation

**What to build**: Distributable package and docs.

**Files to create**:
- `pyproject.toml` (complete with entry_points, dependencies)
- `Dockerfile`
- `README.md`, `INSTALL.md`, `ARCHITECTURE.md`

---

# 4. Module Specifications

## 4.1 `core/finding.py`

| Field | Detail |
|---|---|
| **Purpose** | Define the Finding entity and all associated value objects |
| **Inputs** | Constructor arguments for each dataclass |
| **Outputs** | Immutable data objects |
| **Interfaces** | None (this IS the interface — all other modules depend on it) |
| **Dependencies** | Python stdlib only: `dataclasses`, `enum`, `datetime` |
| **Expected behavior** | `Finding` is a frozen dataclass. All fields are typed. Severity enum supports comparison (`CRITICAL > HIGH`). Default values for optional fields (`cwe=None`, `author=None`, `validation_status=ValidationStatus.UNVALIDATED`). |

## 4.2 `core/finding_factory.py`

| Field | Detail |
|---|---|
| **Purpose** | Create validated Finding instances |
| **Inputs** | Tool/agent name, file, lines, severity, title, explanation, recommendation, optional CWE |
| **Outputs** | `Finding` instance |
| **Interfaces** | `create_from_tool(...)`, `create_from_agent(...)` |
| **Dependencies** | `core/finding.py` |
| **Expected behavior** | Clamps `start_line` to `max(1, start_line)`. Clamps `end_line` to `max(start_line, end_line)`. Truncates title to 120 chars. Sets `first_seen` and `last_seen` to current UTC time. Assigns `suppression_key = f"{source}-{category.value}"`. Leaves `id` empty (assigned by FindingManager later). |

## 4.3 `core/finding_manager.py`

| Field | Detail |
|---|---|
| **Purpose** | Execute all 8 finding processing steps in order |
| **Inputs** | `list[Finding]`, `RepositoryContext`, `ChangeSet`, `QAConfig` |
| **Outputs** | `ProcessedFindings` (active, suppressed, clusters, resolved_issues) |
| **Interfaces** | `process(findings, repo_context, change_set, config) → ProcessedFindings` |
| **Dependencies** | All 8 processing step classes from `core/` |
| **Expected behavior** | Executes in this EXACT order: (1) FindingLineValidator.validate, (2) FindingDeduplicator.deduplicate, (3) DiffClassifier.classify, (4) AuthorAttributor.attribute, (5) SnippetExtractor.extract, (6) SuppressionApplicator.apply, (7) FindingClusterer.cluster, (8) FindingRanker.rank. Then assigns finding IDs. Returns ProcessedFindings. |

## 4.4 `tools/base.py`

| Field | Detail |
|---|---|
| **Purpose** | Abstract interface for all Tier 1 tools |
| **Inputs** | File path, repository path |
| **Outputs** | `list[Finding]` |
| **Interfaces** | `is_available() → bool`, `is_applicable(file_path: str) → bool`, `run(file_path: str, repo_path: Path) → list[Finding]` |
| **Dependencies** | `core/finding.py`, `subprocess` (stdlib) |
| **Expected behavior** | `_run_command(cmd, cwd, timeout)` executes subprocess with capture_output=True, text=True, timeout. Returns `(returncode, stdout, stderr)`. On FileNotFoundError → returns `(-1, "", "Command not found")`. On TimeoutExpired → returns `(-2, "", "Timed out")`. `_check_binary(name)` runs `name --version` to test availability. |

## 4.5 `tools/runner.py`

| Field | Detail |
|---|---|
| **Purpose** | Execute all applicable Tier 1 tools across a file set |
| **Inputs** | `repo_path`, `file_paths`, `trigger` |
| **Outputs** | `Tier1RunResult` (findings, tool_summary, duration, tools_available, tools_skipped) |
| **Interfaces** | `run(repo_path, file_paths, trigger) → Tier1RunResult` |
| **Dependencies** | `tools/base.py`, all registered tools, `core/finding_line_validator.py` |
| **Expected behavior** | (1) Check `is_available()` for all registered tools — log skipped tools. (2) For each file, for each available tool: check `is_applicable(file)`. (3) Execute applicable tools with error isolation — one tool's failure doesn't stop others. (4) After each tool's run, validate line numbers with `FindingLineValidator._clamp_line_numbers()`. (5) Aggregate all findings. (6) Return Tier1RunResult. |

## 4.6 `infrastructure/llm_client.py`

| Field | Detail |
|---|---|
| **Purpose** | Managed interface to Claude API with reliability |
| **Inputs** | System prompt, user message, output schema, model name |
| **Outputs** | `LLMResponse` (content, model, tokens, cost, success, error) |
| **Interfaces** | `call(system_prompt, user_message, output_schema?, model?) → LLMResponse` |
| **Dependencies** | `anthropic` SDK |
| **Expected behavior** | (1) Check circuit breaker — if open, return failure immediately. (2) Try primary model. (3) On rate limit: retry with exponential backoff (1s, 2s, 4s), max 3 retries. (4) On timeout: retry once. (5) On invalid response: retry once with explicit format instruction. (6) On all retries exhausted: try next model in fallback chain. (7) On all models exhausted: increment circuit breaker counter, return failure. (8) On success: reset circuit breaker counter. Track tokens and cost. (9) Circuit breaker opens after 5 consecutive failures. Cooldown: 60 seconds. |

## 4.7 `agents/correctness.py`

| Field | Detail |
|---|---|
| **Purpose** | Detect logic bugs through autonomous code exploration |
| **Inputs** | `FileReviewContext` (file content, diff, Tier 1 findings, semantic memory) |
| **Outputs** | `AgentResult` (findings, tool_calls, model, tokens, cost) |
| **Interfaces** | `review_file(context) → AgentResult` |
| **Dependencies** | `agents/base.py`, `infrastructure/llm_client.py` (injected), `agents/tool_provider.py` (injected) |
| **Expected behavior** | (1) Load system prompt from `prompts/correctness_agent.txt`. (2) Load semantic memory via `SemanticMemoryLoader`. (3) Build user message with file content + diff + Tier 1 findings. (4) Send to LLM with tool-use enabled. (5) Agent makes tool calls (read_file, grep, etc.) — execute via AgentToolProvider, return results to LLM. (6) Repeat tool-use loop until agent produces final output. (7) Parse JSON output into `list[Finding]`. (8) Return AgentResult. On any failure → return AgentResult with empty findings and error message. |

## 4.8 `agents/validator.py`

| Field | Detail |
|---|---|
| **Purpose** | Adversarially challenge findings, filter false positives, assign confidence |
| **Inputs** | All findings from all sources, repository path |
| **Outputs** | `ValidationResult` (validated findings with confidence scores, suppressed findings with reasoning) |
| **Interfaces** | `validate(findings, repo_context) → ValidationResult` |
| **Dependencies** | `agents/base.py`, `infrastructure/llm_client.py` (injected, preferably Opus model) |
| **Expected behavior** | (1) Batch findings into groups of 15. (2) For each batch: build prompt with findings + instruction to REFUTE each one. (3) Enable tool-use so validator can re-read code. (4) Parse validation verdicts: confirmed/likely/uncertain/suppressed with reasoning per finding. (5) Resolve semantic duplicates (merge findings that describe the same issue). (6) On batch LLM failure → ALL findings in batch marked UNVALIDATED and RETAINED (fail-open). (7) Return ValidationResult. |

## 4.9 `orchestration/orchestrator.py`

| Field | Detail |
|---|---|
| **Purpose** | Execute the complete scan pipeline |
| **Inputs** | `ScanRequest` |
| **Outputs** | `ScanResult` |
| **Interfaces** | `scan(request, progress?) → ScanResult` |
| **Dependencies** | All pipeline components (injected via constructor) |
| **Expected behavior** | Execute phases in order (see Step 8 and Step 18). Never raises — catches all exceptions internally and returns ScanResult with errors list. Cleanup temporary clones in finally block. Track cost throughout. Enforce cost limit. Emit progress callbacks if provided. |

---

# 5. Testing Strategy

## 5.1 Unit Tests

**Location**: `tests/unit/` — mirrors `cortex_engine/` structure.

**What to unit test**:
- Every method in `core/` — these are pure functions with no I/O
- Configuration validation (valid, invalid, defaults)
- Risk scoring formula
- Quality gate evaluation (all three modes)
- Finding deduplication edge cases
- Suppression rule matching

**How to unit test**:
- NO mocks for core domain tests — use real Finding instances
- NO external dependencies (no git, no LLM, no network)
- Use `pytest` with simple assert statements
- Test edge cases: empty lists, None values, maximum lengths, out-of-range values

**Test naming**: `test_<method>_<scenario>_<expected_result>()`

```
test_dedup_same_file_same_line_same_title_merges()
test_dedup_same_file_different_line_keeps_both()
test_gate_enforced_mode_critical_finding_fails()
test_gate_shadow_mode_critical_finding_passes()
test_risk_score_auth_path_always_high()
```

## 5.2 Integration Tests

**Location**: `tests/integration/`

**What to integration test**:
- Tier 1 tools against real binaries (skip if binary not installed)
- Git operations against a fixture repository
- Full pipeline: ScanOrchestrator.scan() with real tools on a fixture repo
- Report generation with real findings → verify JSON structure and PDF output
- Database operations (SQLite CRUD)

**Fixture repository**: `tests/fixtures/sample_repo/` — a small Python project with:
- Known bugs (null dereference, missing error handling)
- Known security issues (SQL concatenation, missing auth)
- Known design issues (large function, many parameters)
- Known good code (for testing that agents don't produce false positives)
- `.qa-config.yml` with test configuration

## 5.3 Agent Tests

**Location**: `tests/integration/agents/`

**What to test**:
- Each agent against the fixture repository with known issues
- Agent produces findings for known bugs (true positive verification)
- Agent does NOT produce findings for known-good code (false positive verification)
- Agent fail-open: mock LLM failure → verify empty findings returned (not crash)
- Security Agent fail-open: mock LLM failure → verify ALL SAST findings retained
- Validator Agent: given known TP and FP findings → verify correct validation

**How to test agents**:
- Use real LLM calls for quality verification (mark as slow tests, skip in fast CI)
- Use mock LLM responses for structural verification (always runs in CI)
- Track finding quality over time: maintain a labeled dataset of expected findings per fixture

## 5.4 Workflow Tests

**Location**: `tests/integration/workflows/`

**What to test**:
- PR review workflow end-to-end: scan request → findings → reports → gate decision
- Audit workflow: full scan → cross-file findings → comprehensive report
- Cost limit enforcement: set low limit → verify agents stop when limit reached
- Quality gate modes: shadow → advisory → enforced behavior verification
- Integration dispatch: mock GitHub/Linear/Slack APIs → verify correct payloads

---

# 6. Common Mistakes to Avoid

| # | Mistake | Why It's Wrong | What to Do Instead |
|---|---|---|---|
| 1 | **Importing from `core/` into `infrastructure/` at module level and vice versa** | Creates circular dependency | `core/` NEVER imports from any other cortex_engine package. `infrastructure/` imports from `core/`. |
| 2 | **Hardcoding agent prompts in Python files** | Prevents editing prompts without code changes | Load prompts from `prompts/*.txt` files at runtime |
| 3 | **Catching bare `except:` in tool wrappers** | Hides bugs, makes debugging impossible | Catch `(subprocess.TimeoutExpired, FileNotFoundError, OSError)` specifically |
| 4 | **Using `splitlines()` inconsistently for line counting** | Python's `splitlines()` treats `\x0b`, `\x0c` as line breaks — different from tool line counting | Use `splitlines()` consistently across ALL line-counting code (finding_line_validator, snippet_extractor, author_attributor) |
| 5 | **Modifying findings after creation without going through FindingManager** | Produces inconsistent state — findings with unvalidated line numbers, missing authors | All finding mutations happen in FindingManager.process() in the defined order |
| 6 | **Logging warnings for expected conditions** | `get_git_config` failing is expected in temporary clones — warning log is noise | Use `logger.debug()` for expected conditions. Reserve `logger.warning()` for degraded operations. |
| 7 | **Truncating text in reports** | Truncated recommendations are useless to developers | Never truncate finding titles, explanations, or recommendations in reports. Use word-wrap CSS for PDF. |
| 8 | **Writing to the scanned repository** | Violates the audit-only constraint — the platform's fundamental safety property | Write ONLY to: output directory (reports), temp directory (clones), database file (history). NEVER write to the repository under evaluation. |
| 9 | **Creating agents that are just prompt wrappers** | Violates agentic design principles — an agent must plan, use tools, and adapt | Agents must use tool-use protocol: LLM decides which tools to call based on observations. Not a single prompt→response call. |
| 10 | **Suppressing findings on LLM failure** | Silent suppression hides real issues | Fail-open: on ANY failure, retain existing findings with `validation_status=UNVALIDATED` |
| 11 | **Using the same LLM model for validator and detection agents** | Correlated errors — same model confirms its own hallucinations | Use different models: Sonnet for detection, Opus for validation. Configurable via config. |
| 12 | **Adding agents without clear capability boundary justification** | Leads to agent sprawl, duplicate findings, wasted LLM cost | Each agent must differ from ALL others on ≥2 of: input scope, cognitive mode, knowledge requirement, output type |
| 13 | **Making the orchestrator an agent** | The orchestrator is deterministic pipeline control — it doesn't plan, explore, or adapt | Orchestrator is a function. Agents are agents. Don't conflate them. |
| 14 | **Storing source code in the database** | Privacy risk, storage bloat | Store finding metadata only. Code snippets in `code_under_review` field are transient (in reports, not DB). |
| 15 | **Creating services that instantiate their own dependencies** | Prevents testing, violates dependency inversion | All dependencies injected via constructor. CLI is the composition root. |

---

# 7. Implementation Constraints

## 7.1 Hard Constraints (Non-Negotiable)

| # | Constraint | Enforcement |
|---|---|---|
| C1 | **Audit-only**: The platform NEVER modifies the repository under evaluation | No write tools in agent tool set. Clone-based isolation. Automated test verifies zero files modified. |
| C2 | **Fail-open**: LLM failures retain findings, never suppress them | Every LLM call site has fail-open handling. Security Agent retains ALL SAST findings on failure. Validator marks unprocessed findings as UNVALIDATED. |
| C3 | **Core has zero external dependencies** | `core/` uses Python stdlib only. Pydantic allowed only in `infrastructure/config_schema.py`. |
| C4 | **Dependencies point inward** | `core/` imports nothing from other cortex_engine packages. Verified by import linter. |
| C5 | **Agent prompts are externalized** | Loaded from `prompts/*.txt` at runtime. Never hardcoded in Python. |
| C6 | **Every subprocess call has a timeout** | Default 60s for tools, 300s for git clone, 120s for LLM. No subprocess call without `timeout=` parameter. |
| C7 | **Temperature = 0 for all LLM calls** | Deterministic output. Set in LLM client, not configurable per agent. |

## 7.2 Soft Constraints (Preferred, May Be Relaxed With Justification)

| # | Constraint | Rationale |
|---|---|---|
| S1 | No docstrings — use clear names and types instead | Reduces maintenance burden of outdated docstrings |
| S2 | No comments unless WHY is non-obvious | Code should be self-explanatory |
| S3 | One class per file for domain entities | Keeps files focused and easy to navigate |
| S4 | Test coverage >80% for core domain | Core logic must be thoroughly tested |
| S5 | Max function complexity: 10 (cyclomatic) | Functions above 10 should be split |

## 7.3 Technology Constraints

| Constraint | Value |
|---|---|
| Python version | 3.11+ |
| LLM provider | Anthropic Claude (Sonnet for detection, Opus for validation) |
| Database | SQLite (stdlib `sqlite3`) — no ORM |
| CLI framework | Click |
| HTTP client | httpx |
| PDF generation | WeasyPrint (optional, HTML fallback) |
| Configuration | YAML + Pydantic validation |
| Testing | pytest |
| Linting | ruff |
| Package format | pyproject.toml (PEP 621) |

## 7.4 What NOT to Build

| Do NOT Build | Why |
|---|---|
| Web UI or dashboard | CLI-first. Web UI is a future expansion. |
| REST API server | No long-running server. Batch processing only. |
| Agent-to-agent communication | Agents are independent. Data flows through pipeline only. |
| Custom model fine-tuning | Use general-purpose models with prompt engineering + semantic memory. |
| IDE plugin | CLI and CI/CD only. IDE integration is future expansion. |
| Automated prompt modification | All prompt changes are human-reviewed and deployed like code. |
| Caching layer for LLM responses | Risk of stale cache (changed files get cached "no issues"). Risk scorer already prevents unnecessary LLM calls. |
| Microservices or message queues | Single process per scan. No distributed systems. |
