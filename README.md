# QA Platform v2.0

**Automated Code Review and Analysis Platform**

An agentic QA platform that combines 27 deterministic static analysis tools with 5 specialized AI agents to identify issues, provide explanations, suggest improvements, and recommend fixes — across correctness, security, design, and cross-file consistency.

**This platform identifies, reports, and recommends. It does NOT modify code.**

---

## Platform Summary

| Metric | Value |
|---|---|
| **Architecture** | Pipeline-funnel with 3 tiers + validation layer |
| **Source files** | 86 Python files (9,445 LOC) |
| **Tier 1 tools** | 27 deterministic static analysis tools |
| **AI agents** | 5 specialized agents with distinct cognitive modes |
| **Knowledge bases** | 36 SAST rules, 27 CWE entries, SOLID design principles |
| **Agent prompts** | 5 externalized prompt files (editable without code changes) |
| **Integrations** | GitHub PR comments, Linear tickets, Slack notifications |
| **Persistence** | SQLite (5 tables: scans, findings, suppressions, audit_log, gate_overrides) |
| **Reports** | Full report (11 sections) + Executive summary (JSON + PDF) |
| **Constraint** | Audit-only — never modifies the scanned repository |

---

## Quick Start

```bash
# Install
pip install -e .

# Run Tier 1 scan (deterministic tools only — no API key needed)
qa run --repo . --tiers 1 --report json

# Run Tier 1 + 2 scan (includes AI agents — requires ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY="your-key"
qa run --repo . --tiers 1,2 --report json

# Full audit (all tiers, all files, cross-file analysis)
qa run --repo . --audit --report json,pdf

# PR review with GitHub comments
qa run --repo . --pr 42 --vs main --post-comment --github-token $GITHUB_TOKEN
```

---

## Architecture: Tiers and Layers

The platform uses a **pipeline-funnel architecture** where each stage progressively refines analysis. Broad deterministic scanning narrows to targeted agentic review, then adversarial validation filters noise.

```
INPUT: Repository + Trigger (PR / commit / audit)
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  TIER 1: Deterministic Analysis                         │
│                                                         │
│  27 static analysis tools (linters, SAST, type          │
│  checkers, complexity, dependency audit, secret scan)   │
│                                                         │
│  No LLM. No agents. Rule-based. Always runs.            │
│  Output: candidate findings in universal schema         │
└────────────────────┬────────────────────────────────────┘
                     │
               ┌─────▼─────┐
               │Risk Scorer │  Heuristic: which files need agent review?
               │(function)  │  High risk → agents. Low risk → Tier 1 only.
               └─────┬─────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  TIER 2: Per-File Agentic Review                        │
│                                                         │
│  3 agents run IN PARALLEL per file:                     │
│    Agent 1: Correctness  (constructive reasoning)       │
│    Agent 2: Security     (adversarial reasoning)        │
│    Agent 3: Design       (evaluative reasoning)         │
│                                                         │
│  Each agent: plans → explores → reasons → verifies      │
│  Uses tools: read_file, grep, expand_context            │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  TIER 3: Cross-File Agentic Analysis (conditional)      │
│                                                         │
│  Agent 4: Cross-File (comparative reasoning)            │
│  Runs on: full audits + multi-module PRs                │
│  Detects: inconsistencies, broken contracts, systemic   │
│  patterns across module boundaries                      │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  VALIDATION LAYER: Finding Validation                   │
│                                                         │
│  Agent 5: Validator (skeptical reasoning)               │
│  Adversarially challenges ALL findings from Tiers 1-3   │
│  Re-reads code independently. Tries to REFUTE.          │
│  Uses different model (Opus) for diversity.             │
│  Fail-open: uncertain → retain the finding.             │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  POST-PROCESSING (deterministic — no agents)            │
│                                                         │
│  Finding Manager: 8-step pipeline                       │
│    1. Line validation (clamp to file length)            │
│    2. Deduplication (same file + ±3 lines + similar)    │
│    3. Diff classification (introduced/modified/pre)     │
│    4. Author attribution (git blame → fallback chain)   │
│    5. Snippet extraction (3 lines context, sanitized)   │
│    6. Suppression (rule matching with expiry)            │
│    7. Clustering (group by root cause)                  │
│    8. Ranking (severity × confidence)                   │
│                                                         │
│  Quality Gate → Reports → Integrations                  │
└─────────────────────────────────────────────────────────┘
```

### What Runs When

| Trigger | Tier 1 | Risk Score | Tier 2 | Tier 3 | Validation |
|---|---|---|---|---|---|
| `qa run --tiers 1` | All 27 tools | No | No | No | No |
| `qa run --tiers 1,2` | All 27 tools | Yes | Yes (high-risk) | No | Yes |
| `qa run --audit` | All 27 tools | No (all files) | Yes (all files) | Yes | Yes |
| `qa run --pr 42` | All 27 tools | Yes | Yes (high-risk) | If 3+ modules | Yes |

---

## AI Agents (5 Total)

Each agent is justified by a distinct **capability boundary** — a unique combination of cognitive mode, input scope, and knowledge requirement that no other agent covers.

### Agent 1: Correctness Agent

| Property | Value |
|---|---|
| **Tier** | 2 (per-file) |
| **Cognitive Mode** | Constructive: "Does this code work correctly?" |
| **Category** | Correctness |
| **What it finds** | Logic bugs, null/undefined handling, off-by-one errors, race conditions, resource leaks, error path failures, incorrect algorithms, missing edge cases |
| **How it works** | 3-pass review: Scan (identify candidates) → Investigate (gather evidence via tool calls) → Verify (challenge findings — suppress unsupported ones) |
| **Prompt** | `prompts/correctness_agent.txt` |
| **Model** | Claude Sonnet (primary), Claude Haiku (fallback) |

### Agent 2: Security Agent

| Property | Value |
|---|---|
| **Tier** | 2 (per-file) |
| **Cognitive Mode** | Adversarial: "How can this code be exploited?" |
| **Category** | Security |
| **What it finds** | SQL injection, XSS, command injection, auth bypass, data exposure, crypto weakness, SSRF, path traversal |
| **How it works** | Validates SAST findings (bandit, semgrep, gitleaks) as true/false positive with documented reasoning. Traces taint paths from source → transformation → sink. Classifies by CWE. |
| **Semantic Memory** | 36 SAST rules with CWE mappings + 27-entry CWE taxonomy tree |
| **Fail-Open** | If LLM fails, ALL SAST findings are retained unfiltered |
| **Prompt** | `prompts/security_agent.txt` |
| **Model** | Claude Sonnet (primary), Claude Haiku (fallback) |

### Agent 3: Design & Improvement Agent

| Property | Value |
|---|---|
| **Tier** | 2 (per-file) |
| **Cognitive Mode** | Evaluative: "How can this code be better?" |
| **Category** | Design |
| **What it finds** | SOLID violations, excessive complexity, poor abstractions, tight coupling, naming issues, test adequacy gaps, documentation gaps |
| **How it works** | Produces improvement suggestions (not bug reports). Each includes: WHAT to change, WHY it improves the code, concrete EXAMPLE. |
| **Semantic Memory** | SOLID principles with indicators and thresholds |
| **Prompt** | `prompts/design_agent.txt` |
| **Model** | Claude Sonnet (primary), Claude Haiku (fallback) |

### Agent 4: Cross-File Analysis Agent

| Property | Value |
|---|---|
| **Tier** | 3 (multi-file, conditional) |
| **Cognitive Mode** | Comparative: "Are these files consistent?" |
| **Category** | Consistency |
| **What it finds** | Inconsistent validation patterns, missing auth on some endpoints, interface mismatches, systemic code smells, broken contracts across modules |
| **How it works** | Receives groups of related files (e.g., all controllers). Compares patterns across them. Identifies deviations from the dominant pattern. |
| **When it runs** | Full audits OR PRs touching 3+ distinct modules |
| **Prompt** | `prompts/cross_file_agent.txt` |
| **Model** | Claude Sonnet (primary), Claude Haiku (fallback) |

### Agent 5: Finding Validator Agent

| Property | Value |
|---|---|
| **Tier** | Validation layer (runs after all detection agents) |
| **Cognitive Mode** | Skeptical: "Is this finding actually real?" |
| **Category** | Cross-cutting (validates ALL findings) |
| **What it does** | Adversarially challenges every finding. Re-reads referenced code independently. Tries to REFUTE each finding. Assigns confidence: confirmed / likely / uncertain / suppressed. Resolves semantic duplicates across agents. |
| **Fail-Open** | If uncertain, RETAINS the finding. If LLM fails, ALL findings marked UNVALIDATED (retained). |
| **Model Diversity** | Uses Claude Opus (different from detection agents) to prevent correlated errors |
| **Prompt** | `prompts/validator_agent.txt` |

### Why These 5 Agents

| Agent Pair | Why Separate |
|---|---|
| Correctness vs Security | Different cognitive modes (constructive vs adversarial), different knowledge bases. Mixing security rules with quality conventions degrades performance (AgenticSCR, FSE 2026). |
| Correctness vs Design | Different findings: execution tracing for bugs vs structural evaluation for improvements. RevAgent (2025) shows category-specific agents outperform general agents. |
| Cross-File vs Per-File | Different input scope (multi-file vs single-file). Per-file agents can't compare N files simultaneously. |
| Validator vs Detection | Independent verification prevents correlated errors. RevAgent ablation: critic = most impactful component. 3+1 paper: +10.3pp precision from independent verification. |

---

## Tier 1: Deterministic Tools (27 Total)

### Python Tools (pip-installable)

| # | Tool | Category | What It Detects |
|---|---|---|---|
| 1 | **ruff** | Correctness | Lint errors, unused imports, style violations |
| 2 | **bandit** | Security | Python security vulnerabilities |
| 3 | **mypy** | Correctness | Type errors, type safety violations |
| 4 | **semgrep** | Security | Multi-language pattern-based vulnerability detection |
| 5 | **radon** | Design | Cyclomatic complexity metrics |
| 6 | **pip-audit** | Security | Known CVEs in Python dependencies |
| 7 | **sqlfluff** | Correctness | SQL lint and formatting |
| 8 | **checkov** | Security | Infrastructure-as-Code security scanning |
| 9 | **pip-licenses** | Security | License compliance checking |

### External Binary Tools (install separately)

| # | Tool | Category | What It Detects |
|---|---|---|---|
| 10 | **gitleaks** | Security | Hardcoded secrets and API keys |
| 11 | **hadolint** | Security | Dockerfile best practice violations |
| 12 | **shellcheck** | Correctness | Shell script bugs and portability issues |
| 13 | **osv-scanner** | Security | Google vulnerability database scanning |
| 14 | **trivy** | Security | Container and dependency vulnerabilities |

### NPM Tools (install with npm -g)

| # | Tool | Category | What It Detects |
|---|---|---|---|
| 15 | **jscpd** | Design | Copy-paste / code duplication |
| 16 | **markdownlint** | Design | Markdown formatting issues |
| 17 | **prettier** | Design | Frontend code formatting |
| 18 | **stylelint** | Design | CSS/SCSS lint violations |

### Custom Analysis Tools (built-in, no external binary needed)

| # | Tool | Category | What It Detects |
|---|---|---|---|
| 19 | **security-patterns** | Security | eval(), exec(), shell=True, pickle.loads, hardcoded passwords |
| 20 | **complexity-analyzer** | Design | Functions with cyclomatic complexity > 10 |
| 21 | **dead-code** | Design | Defined but unused functions and classes |
| 22 | **interface-checker** | Correctness | Abstract method implementation gaps |
| 23 | **migration-checker** | Security | Unsafe migration patterns (raw SQL, missing rollback) |
| 24 | **call-graph** | Design | Circular import detection |
| 25 | **test-coverage-gap** | Design | Source files without corresponding test files |
| 26 | **version-drift** | Security | Unpinned dependency versions |
| 27 | **unused-module** | Design | Imported but unused modules |

Tools are auto-discovered at scan start. Missing tools are skipped gracefully — the platform works with whatever subset is installed.

---

## Installation

### Requirements

- **Python 3.11+** (required)
- **git** (required — for diff, blame, clone operations)
- **ANTHROPIC_API_KEY** (required for Tier 2+ agents; Tier 1 works without it)

### Install from Source

```bash
# Clone or navigate to the project
cd qa_platform_v2

# Install the platform with core dependencies
pip install -e .

# Install with development tools
pip install -e ".[dev]"

# Install pip-based Tier 1 tools
pip install -e ".[tier1]"
```

### Install External Binaries (Optional)

```bash
# Secret scanner
# Download from https://github.com/gitleaks/gitleaks/releases
# Or: brew install gitleaks

# Dockerfile linter
# Download from https://github.com/hadolint/hadolint/releases
# Or: brew install hadolint

# Shell script analyzer
sudo apt install shellcheck    # Debian/Ubuntu
# Or: brew install shellcheck

# Container vulnerability scanner
# Download from https://github.com/aquasecurity/trivy/releases
# Or: brew install trivy

# Google vulnerability database
# Download from https://github.com/google/osv-scanner/releases
```

### Install NPM Tools (Optional)

```bash
npm install -g jscpd markdownlint-cli prettier stylelint
```

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | For Tier 2+ | Claude API access for AI agents |
| `GITHUB_TOKEN` | For PR comments | GitHub API for posting PR review comments |
| `LINEAR_API_KEY` | For tickets | Linear API for creating issues |
| `LINEAR_TEAM_ID` | For tickets | Linear team to create issues in |
| `SLACK_WEBHOOK_URL` | For notifications | Slack incoming webhook URL |

---

## CLI Reference

```
qa run [OPTIONS]
```

| Flag | Default | Description |
|---|---|---|
| `--repo` | (required) | Local path or remote Git URL |
| `--branch` | current | Branch to scan |
| `--commit` | HEAD | Specific commit SHA to scan |
| `--vs` | None | Base branch for diff comparison |
| `--tiers` | `1,2` | Tiers to run: `1`, `1,2`, `1,2,3` |
| `--agents` | all | Specific agents: `correctness,security` |
| `--audit` | off | Full codebase audit (all tiers, all files) |
| `--full` | off | Scan all files (not just changed) |
| `--report` | `json` | Report formats: `json`, `pdf`, `json,pdf` |
| `--output` | `.qa-reports/` | Output directory for reports |
| `--pr` | None | PR number (enables PR-aware analysis) |
| `--post-comment` | off | Post findings as GitHub PR comments |
| `--github-token` | `$GITHUB_TOKEN` | Token for GitHub API access |
| `--cost-limit` | None | Maximum LLM spend in USD |
| `--dry-run` | off | Show configuration without scanning |
| `-v, --verbose` | off | Enable debug logging |
| `--version` | — | Show version and exit |

### Exit Codes

| Code | Meaning |
|---|---|
| 0 | Quality gate passed |
| 1 | Quality gate failed (findings exceed thresholds) |
| 2 | Scan execution error |

### Usage Examples

```bash
# Scan local repo with Tier 1 tools only
qa run --repo . --tiers 1 --report json

# Full audit with PDF report
qa run --repo . --audit --report json,pdf

# PR review with GitHub integration
qa run --repo . --pr 42 --vs main --post-comment --tiers 1,2

# Scan remote repository
qa run --repo https://github.com/org/project.git --branch main --tiers 1

# Scan with cost limit
qa run --repo . --tiers 1,2,3 --cost-limit 2.00

# Dry run (show config only)
qa run --repo . --audit --dry-run
```

---

## Configuration (.qa-config.yml)

Place a `.qa-config.yml` in the repository root. All sections are optional — defaults are used for anything not specified.

```yaml
version: "2.0"

# File filtering
ignore:
  max_file_size_kb: 10240           # Skip files larger than 10MB
  extra_binary_extensions: [".dat"] # Additional binary extensions

# Generated code handling
generated_code:
  paths: ["src/generated/", "**/auto_gen_*"]
  markers: ["@generated", "AUTO-GENERATED", "DO NOT EDIT"]
  behavior: skip                    # skip | warn-only | review-reduced

# Review behavior
review:
  pr_finding_limit: 15              # Max findings in PR comments
  severity_threshold: low           # Minimum severity for PR comments
  ensemble_passes: 1                # Independent review passes
  positive_feedback: true           # Include "good code" observations
  cross_file_correlation: true      # Enable cross-file analysis

# LLM model selection
models:
  code_review: claude-sonnet-4-20250514
  security_review: claude-sonnet-4-20250514
  architecture: claude-sonnet-4-20250514
  validator: claude-opus-4-20250514   # Different model for validation diversity

# Security context
security:
  data_classification: internal     # public | internal | confidential | restricted
  exposure_surface: internal-only   # internet-facing | internal-only | backend | library
  high_risk_paths: ["src/auth/", "src/payments/", "src/crypto/"]

# Privacy controls
privacy:
  ai_review_mode: cloud             # cloud | self-hosted
  ai_exclude_paths: ["secrets/", ".env"]  # Never send to LLM
  audit_log: true                   # Log all LLM calls

# Project knowledge (loaded into agent semantic memory)
knowledge_base:
  conventions_path: docs/conventions.md
  security_policies_path: docs/security-policy.md

# Quality gate
quality_gates:
  current_mode: shadow              # shadow | advisory | enforced
  thresholds:
    max_critical: 0
    max_high: 0
    required_confidence: likely     # confirmed | likely | uncertain

# Suppression rules
suppressions:
  default_expiry_days: 90
  entries:
    - pattern: "ruff-correctness"
      file_scope: "tests/"
      reason: "Test files use intentional patterns"
      approved_by: "tech-lead"
      expires: "2026-12-31"

# Cost controls
cost:
  max_per_pr: 1.00                  # USD per PR scan
  max_nightly: 10.00                # USD per nightly audit

# Integrations
integrations:
  linear:
    max_issues_per_scan: 20
    min_severity: medium
```

### Quality Gate Modes

| Mode | Behavior |
|---|---|
| `shadow` | Always passes. Logs what WOULD have happened. Use for initial rollout. |
| `advisory` | Returns advisory status on threshold breach. Does not block CI. |
| `enforced` | Returns failure (exit code 1) on threshold breach. Blocks merge. |

---

## Reports

### Full Report (11 sections)

Generated at `.qa-reports/scan-<id>.json` (and `.pdf` if requested):

1. **Report Metadata** — ID, timestamp, trigger, platform version, models used, duration, cost
2. **Repository Context** — Repo name, branch, commit, PR info
3. **Attribution** — Who authored the code under review
4. **Scope Summary** — Files analyzed, skipped, tiers executed, diff mode
5. **Executive Summary** — Verdict, quality gate status, severity distribution, risk level
6. **Findings** — All active findings with full evidence and recommendations
7. **Finding Clusters** — Groups of related findings by root cause
8. **Resolved Issues** — Previously reported issues now resolved
9. **Positive Observations** — Good patterns identified
10. **Suppressed Findings** — Findings matched by suppression rules
11. **Appendix** — Tool call log, reproducibility command, config hash

### Executive Report

Generated at `.qa-reports/scan-<id>-executive.json`:

- Risk level badge (CRITICAL / HIGH / MEDIUM / CLEAN)
- Must-fix / Should-fix / Consider counts
- Action items table (full text — no truncation)
- By-category summary
- Noise reduction metrics (how many findings filtered and why)

---

## Finding Schema

Every finding carries structured metadata:

| Field | Type | Description |
|---|---|---|
| `id` | string | `F-<scan_short>-<seq>` (e.g., `F-abc123-001`) |
| `source` | string | Tool or agent name that produced it |
| `tier` | int | 1 (tool), 2 (per-file agent), 3 (cross-file agent) |
| `category` | enum | correctness, security, design, consistency, hygiene |
| `severity` | enum | CRITICAL > HIGH > MEDIUM > LOW > INFO |
| `confidence` | enum | CONFIRMED (verified), LIKELY (not refuted), UNCERTAIN |
| `classification` | enum | introduced, modified, pre_existing, unclassified |
| `file` | string | Relative file path |
| `start_line` / `end_line` | int | 1-based line numbers (clamped to file length) |
| `title` | string | Concise description (max 120 chars) |
| `explanation` | string | Detailed explanation with evidence |
| `evidence` | object | Tool calls, code references, and metrics |
| `recommendation` | string | Concrete, actionable fix (full text) |
| `cwe` | string | CWE identifier for security findings (e.g., CWE-89) |
| `validation_status` | enum | confirmed, likely, uncertain, suppressed, unvalidated |
| `validation_reasoning` | string | Validator's reasoning for its verdict |
| `author` | object | Who introduced the code (git blame attribution) |

---

## Safety and Constraints

### Audit-Only Enforcement

The platform NEVER modifies the repository under evaluation. This is enforced at 5 layers:

| Layer | How |
|---|---|
| **Tool interface** | Agent tools are read-only: `read_file`, `grep`, `expand_context`. No write tools exist. |
| **Repository access** | Remote repos are cloned to temp directory. Original is never touched. |
| **Agent prompts** | "You identify and report. You do NOT modify code." |
| **Output schema** | Finding has `recommendation` (text), not `patch` (executable code). |
| **Report delivery** | Reports written to output directory, never to the scanned repository. |

### Fail-Open Safety

When any LLM call fails, findings are **retained, not suppressed**:

| Failure | Response |
|---|---|
| LLM API down | Tier 1 findings retained. Agent findings skipped. Report still generated. |
| Security Agent LLM fails | ALL SAST findings retained with `validation_status=UNVALIDATED` |
| Validator batch fails | ALL findings in batch marked UNVALIDATED and retained |
| Tool binary missing | Tool skipped. Other tools continue. |

### Cost Governance

| Control | How |
|---|---|
| `--cost-limit <USD>` | Orchestrator checks after each agent call. Stops when limit reached. |
| Risk scoring | Only high-risk files get agent review. Low-risk = Tier 1 only. |
| Per-agent tracking | Cost per agent/model exposed in report metadata. |
| Circuit breaker | 5 consecutive LLM failures → skip remaining calls. |

---

## Project Structure

```
qa_platform_v2/
├── src/qa_platform/
│   ├── __init__.py                    # __version__ = "2.0.0"
│   ├── core/                          # 13 files — Finding entity, schemas, processing pipeline
│   │   ├── finding.py                 #   Finding dataclass + 6 enums
│   │   ├── schemas.py                 #   21 dataclass schemas
│   │   ├── finding_factory.py         #   Validated finding creation
│   │   ├── finding_manager.py         #   8-step processing pipeline orchestrator
│   │   ├── finding_line_validator.py   #   Clamp line numbers to file length
│   │   ├── finding_deduplicator.py    #   Same file + ±3 lines + similar title → merge
│   │   ├── finding_clusterer.py       #   Group by root cause
│   │   ├── finding_ranker.py          #   Sort by severity × confidence
│   │   ├── diff_classifier.py         #   introduced / modified / pre_existing
│   │   ├── author_attributor.py       #   Git blame → PR author → default
│   │   ├── snippet_extractor.py       #   Code context with markers
│   │   ├── suppression.py             #   Rule matching with expiry
│   │   └── text_sanitizer.py          #   Control character stripping
│   ├── agents/                        # 9 files — 5 agent implementations + infrastructure
│   │   ├── base.py                    #   ReviewAgent ABC
│   │   ├── correctness.py             #   Agent 1: constructive execution tracing
│   │   ├── security.py                #   Agent 2: adversarial SAST validation + CWE
│   │   ├── design.py                  #   Agent 3: evaluative structural assessment
│   │   ├── cross_file.py              #   Agent 4: comparative multi-file analysis
│   │   ├── validator.py               #   Agent 5: skeptical adversarial challenge
│   │   ├── registry.py                #   Agent discovery and registration
│   │   ├── tool_provider.py           #   Read-only tools for agent code exploration
│   │   └── memory.py                  #   Semantic memory loader (SAST rules, CWE, conventions)
│   ├── tools/                         # 29 files — 27 tool wrappers + base + runner
│   ├── orchestration/                 # 4 files — Pipeline controller + engines
│   │   ├── orchestrator.py            #   14-phase scan pipeline (never raises)
│   │   ├── review_engine.py           #   Parallel agent execution
│   │   ├── validation_engine.py       #   Batched validator with fail-open
│   │   └── cost_tracker.py            #   Per-agent LLM cost tracking
│   ├── assessment/                    # 3 files — Quality gate + risk scorer
│   ├── reporting/                     # 2 files — Full report + executive summary
│   ├── integrations/                  # 4 files — GitHub, Linear, Slack, dispatcher
│   ├── infrastructure/                # 11 files — Git, LLM client, config, persistence
│   │   ├── llm_client.py              #   Anthropic client with circuit breaker + retry + fallback
│   │   ├── git.py                     #   Git subprocess wrapper (all read-only)
│   │   ├── config.py                  #   YAML config loader with env var resolution
│   │   ├── config_schema.py           #   Pydantic models for .qa-config.yml
│   │   ├── database.py                #   SQLite schema (5 tables)
│   │   └── ...                        #   Repositories, audit logger, resolver, hygiene
│   ├── knowledge/                     # 3 JSON files — Bundled knowledge for agents
│   │   ├── sast_rules.json            #   36 SAST rules with CWE mappings
│   │   ├── cwe_tree.json              #   27-entry CWE taxonomy hierarchy
│   │   └── design_principles.json     #   SOLID principles + complexity thresholds
│   └── cli/
│       └── run.py                     #   CLI entry point (composition root)
├── prompts/                           # 5 externalized agent prompt files
│   ├── correctness_agent.txt
│   ├── security_agent.txt
│   ├── design_agent.txt
│   ├── cross_file_agent.txt
│   └── validator_agent.txt
├── tests/                             # 28 unit tests (all passing)
├── pyproject.toml
└── README.md
```

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=qa_platform --cov-report=term-missing

# Lint
ruff check src/ tests/

# Type check
mypy src/qa_platform/core/
```

### Adding a New Tier 1 Tool

1. Create `src/qa_platform/tools/my_tool.py`
2. Extend `Tier1Tool` with `is_available()`, `is_applicable()`, `run()`
3. Use `FindingFactory.create_from_tool()` for findings
4. Register in `cli/run.py` `_register_tools()`

### Adding a New Agent

1. Create `src/qa_platform/agents/my_agent.py` extending `ReviewAgent`
2. Create `prompts/my_agent.txt` with system prompt
3. Register in `cli/run.py` `_build_agent_infrastructure()`

### Customizing Agent Prompts

Edit files in `prompts/` directory directly — no code changes required. Prompts are loaded at runtime.

---

## Research Foundation

This platform's architecture is grounded in evidence from peer-reviewed research:

| Paper | Venue | Key Contribution |
|---|---|---|
| SAST-Genius | IEEE S&P 2025 | SAST+LLM hybrid: 91% false positive reduction, 89.5% precision |
| RADAR | Meta (535K diffs) | Multi-stage funnel, risk scoring, production-validated |
| QASecClaw | arXiv 2026 | Pipeline agents, fail-open safety, 88.6% FP reduction |
| Automated CR in Practice | ICSE 2025 | 73.8% resolution rate, precision > recall for trust |
| AgenticSCR | FSE 2026 | Detector-validator chain, semantic memory (+5.7%), agentic tool use |
| RevAgent | arXiv 2025 | Category-specific agents outperform general, critic = most impactful |
| Rethinking Agentic CR | TOSEM 2026 | 5-stage lifecycle, reviewers as supervisory operators |

---

*QA Platform v2.0 — Identifies, reports, and recommends. Does NOT modify code.*
