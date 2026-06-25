# Cortex QA Platform

**Automated Code Review and Analysis Platform**

Cortex is an agentic QA platform that combines 27 deterministic static analysis tools with 5 specialized AI agents to identify issues, provide explanations, suggest improvements, and recommend fixes — across correctness, security, design, and cross-file consistency.

**Cortex identifies, reports, and recommends. It does NOT modify code.**

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

## Detailed Task Breakdown by Tier

### Tier 1 Tasks (Per File, No LLM)

Each Tier 1 tool performs these tasks on every applicable file:

| Step | Task | Description |
|---|---|---|
| 1 | Availability check | Verify tool binary is installed (`tool --version`) |
| 2 | Applicability check | Match file extension to tool's supported types |
| 3 | Execution | Run tool as subprocess with timeout (60s default) |
| 4 | Output parsing | Parse tool's JSON/text output into structured findings |
| 5 | Finding creation | Create Finding objects via FindingFactory with severity, category, evidence |
| 6 | Line validation | Clamp reported line numbers to actual file length |
| 7 | Error handling | On any failure, return empty list (never crash the pipeline) |

### Tier 2 Tasks (Per File, 3 Agents in Parallel)

Each Tier 2 agent performs these tasks on every high-risk file:

| Step | Task | Description |
|---|---|---|
| 1 | Prompt loading | Load system prompt from `prompts/{agent}_agent.txt` |
| 2 | Memory loading | Load semantic memory (SAST rules, CWE tree, conventions, design principles) |
| 3 | Context building | Assemble: file content + diff + Tier 1 findings for this file |
| 4 | **Pass 1 — SCAN** | Read code and identify candidate issues based on patterns and context |
| 5 | **Pass 2 — INVESTIGATE** | For each candidate, gather evidence via tool calls: `read_file` (open imported modules, callers), `grep` (find usage patterns), `expand_context` (surrounding code), `list_directory` (project structure) |
| 6 | **Pass 3 — VERIFY** | Challenge each surviving candidate: "Would a senior engineer flag this? Is there context that makes this intentional?" Suppress unsupported candidates with documented reasoning. |
| 7 | Output parsing | Parse LLM's structured JSON response into Finding objects |
| 8 | Result assembly | Return AgentResult with findings, tool call log, tokens, cost |

**Agent-specific tasks:**

| Agent | Specific Tasks Performed |
|---|---|
| **Correctness** | Trace execution paths step-by-step. Check null/undefined handling at every dereference. Verify error path cleanup (resources, connections). Detect off-by-one in loops and array access. Identify race conditions in shared mutable state. Verify algorithm correctness against intent. Check edge cases (empty input, max values, negative numbers). |
| **Security** | Receive SAST findings (bandit, semgrep, gitleaks) as primary input. For each SAST finding: trace taint path from source (user input) through transformations to sink (SQL, shell, file). Check if sanitization exists AND is sufficient for the specific attack vector. Classify confirmed vulnerabilities by CWE using taxonomy tree. Generate remediation steps from SAST rules knowledge. **Fail-open: if LLM fails, ALL SAST findings retained unfiltered with validation_status=UNVALIDATED.** |
| **Design** | Evaluate function/class structure against SOLID principles. Check parameter count (>5 = flag), method count (>10 = flag), nesting depth (>4 = flag), cyclomatic complexity (>10 = flag). Assess naming clarity (function=verb, class=noun, boolean=is/has/can). Check for tight coupling (import count, dependency directions). Verify test adequacy (corresponding test file exists, meaningful coverage). Identify documentation gaps on public APIs. Each suggestion includes: WHAT to change, WHY it improves the code, concrete EXAMPLE. |

### Tier 3 Tasks (Multi-File, Conditional)

The Cross-File Agent performs these tasks only during audits or multi-module PRs:

| Step | Task | Description |
|---|---|---|
| 1 | Module detection | Identify distinct modules from file paths (controllers, services, handlers) |
| 2 | File grouping | Group related files by module (e.g., all files in `src/api/`) |
| 3 | Pattern extraction | For each file in group, extract: validation strategy, auth mechanism, error handling, response format, naming conventions |
| 4 | Dominant pattern identification | Determine what the majority of files do for each concern |
| 5 | Deviation detection | Find files that deviate from the dominant pattern |
| 6 | Intentionality assessment | Determine if deviation is intentional (documented, different purpose) or oversight |
| 7 | Systemic finding production | If same issue in N files, produce ONE systemic finding with all affected files listed |
| 8 | Cross-file evidence | Every finding includes references to multiple files showing the inconsistency |

**What it detects:**
- Missing authentication on some endpoints when others have it
- Inconsistent input validation patterns across controllers
- Interface mismatches (function signature changed but callers not updated)
- Inconsistent error handling strategies across similar components
- Systemic code smells repeated across the codebase

### Validation Layer Tasks (All Findings, Sequential)

The Validator Agent performs these tasks on ALL findings from Tiers 1-3:

| Step | Task | Description |
|---|---|---|
| 1 | Batch preparation | Group findings into batches of 15 for efficient LLM processing |
| 2 | Independent code reading | Re-read the code referenced by each finding (independent of detection agent's reading) |
| 3 | Adversarial challenge | For each finding, construct the strongest argument that the finding is WRONG |
| 4 | Evidence verification | Check if the evidence cited in the finding (tool calls, code references) is accurate |
| 5 | Context checking | Look for surrounding context the detection agent may have missed (guards, checks, intentional patterns) |
| 6 | Verdict assignment | Assign: **confirmed** (independently verified), **likely** (plausible, cannot fully verify), **uncertain** (ambiguous — RETAIN), **suppressed** (finding is wrong, documented WHY) |
| 7 | Reasoning documentation | Document specific reasoning for every verdict (required, not optional) |
| 8 | Semantic deduplication | Detect when two agents describe the same issue with different wording — merge findings |
| 9 | Fail-open enforcement | If batch LLM call fails, ALL findings in that batch get validation_status=UNVALIDATED (retained, NOT suppressed) |

### Post-Processing Pipeline (9 Steps, Deterministic, Fixed Order)

Executed AFTER all agents complete. No LLM. Algorithmic. Order is invariant — never reordered.

| Step | Task | What It Does |
|---|---|---|
| 1 | **Line Validation** | Read each referenced file, count lines via `splitlines()`, clamp `start_line` and `end_line` to `[1, line_count]`. Cache file line counts to avoid re-reading. |
| 2 | **Deduplication** | Group findings by file. Within each group, check pairs: if lines overlap within ±3 AND (suppression_key matches OR title word overlap >80%) → merge. Keep finding with higher confidence. Merge evidence from duplicate into survivor. |
| 3 | **Diff Classification** | Build map of file → added/modified line numbers from ChangeSet. For each finding: if line range overlaps added lines → `INTRODUCED`. If overlaps any changed lines → `MODIFIED`. Otherwise → `PRE_EXISTING`. Full scans → `UNCLASSIFIED`. |
| 4 | **Author Attribution** | For each finding without an author: (1) Pre-commit trigger → git config user.name/email. (2) PR author + INTRODUCED classification → use PR author. (3) Otherwise → git blame on finding's line range. (4) Blame failure → configurable default author. Git config lookup is silent (no warning log). |
| 5 | **Snippet Extraction** | Read file, extract `start_line - 3` to `end_line + 3` lines. Format as `{line_num:4d} | {line_content}`. Mark flagged lines with ` ◄── FLAGGED`. Strip control characters from each line individually (split first, then clean — never clean whole file before splitting). |
| 6 | **Suppression** | Match each finding's `suppression_key` against configured suppression rules. Check `file_scope` (if set, finding's file must match glob). Check `expires` (skip expired rules). Matching findings → set `lifecycle_state=SUPPRESSED`, move to suppressed list. |
| 7 | **Clustering** | Group findings by `suppression_key` prefix (before last `-` segment). For groups with 2+ findings, create FindingCluster with cluster_id, root_cause, finding_ids, count. Update each finding's `root_cause_cluster` and `related_findings` fields. |
| 8 | **Ranking** | Sort findings by: severity descending (CRITICAL first) → confidence descending (CONFIRMED first) → classification (INTRODUCED → MODIFIED → PRE_EXISTING → UNCLASSIFIED) → file path alphabetically. |
| 9 | **ID Assignment** | Assign human-readable IDs: `F-{scan_id_short}-{sequence:03d}` (e.g., `F-abc123-001`). |

### Quality Gate Assessment

| Task | What It Does |
|---|---|
| Severity counting | Count findings by severity, filtered by minimum confidence threshold (configurable: confirmed, likely, or uncertain) |
| Threshold evaluation | Compare critical count against `max_critical` (default 0) and high count against `max_high` (default 0) |
| Mode application | **Shadow**: always PASS, log what would have happened. **Advisory**: return ADVISORY on breach (warns, doesn't block CI). **Enforced**: return FAIL on breach (exit code 1, blocks merge). |
| Override checking | Check for valid override (approved_by, reason, not expired) that would change FAIL to PASS |

### Report Generation

| Report | Tasks Performed |
|---|---|
| **Full Report (JSON + PDF)** | Build 11-section data structure → Serialize findings (convert IntEnum values to string names) → Write JSON with indent=2 → Render HTML template with severity-colored finding cards, meta tables, evidence sections, code snippets in `<pre>` tags, recommendation blocks → Sanitize control characters via `_e()` → Convert HTML to PDF via WeasyPrint (fallback to .html if unavailable) |
| **Executive Report (JSON + PDF)** | Curate findings (filter low-confidence, pre-existing non-critical, low/info severity, no-evidence) → Sort by severity → Build action items table (full text, no truncation) → Compute by-category summary (must_fix, should_fix, consider) → Calculate noise reduction stats (excluded count, exclusion reasons) → Determine risk level (CRITICAL/HIGH/MEDIUM/CLEAN) → Render HTML with risk badge, stats cards, tables with word-wrap → Convert to PDF |

### Integration Dispatch

| Integration | Tasks Performed |
|---|---|
| **GitHub** | Extract owner/repo from remote URL → POST summary comment to PR with finding count, severity distribution, gate status → POST inline review comments on specific file:line for top 15 findings (severity badge, explanation, recommendation) → POST commit status check (success/failure reflecting gate result) |
| **Linear** | Create parent issue: "QA Scan: {repo} ({count} findings)" → For each finding up to `max_issues_per_scan` (default 20): create sub-issue with title `[{severity}] {title}`, description with file:line + explanation + recommendation → Attempt developer assignment by email match via GraphQL API |
| **Slack** | Build summary message: finding count, severity distribution (critical/high/medium/low), quality gate status → POST to configured webhook URL → Handle errors gracefully (notification is non-critical) |

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

### Understanding the Executive Report

The executive report is a filtered, prioritized view of the full report. It takes all findings, removes low-value noise, and presents what remains as a ranked action list. Below is what each parameter means, how it is computed, and how to interpret it.

#### Report Identity

| Parameter | What It Contains | How to Use It |
|---|---|---|
| `report_id` | Unique scan identifier (e.g., `QA-RPT-2026-06-19-full`) | Reference this when discussing findings across teams. Links executive report to full report. |
| `generated_at` | ISO 8601 timestamp of when the scan ran | Confirms the report reflects the codebase at a specific point in time. |
| `repository` | Name of the scanned repository | Identifies which project this report covers. |
| `branch` | Branch that was scanned (e.g., `main`, `master`) | Confirms which branch was analyzed. |
| `commit` | First 12 characters of the commit SHA | Pinpoints the exact code version. Re-running on the same commit produces comparable results. |

#### Risk Assessment

| Parameter | Values | How It Is Computed | What It Means |
|---|---|---|---|
| `risk` | `CRITICAL`, `HIGH`, `MEDIUM`, `CLEAN` | Scans ALL findings in the full report (not just curated items). Returns the highest severity level found: any critical → CRITICAL, any high → HIGH, any medium → MEDIUM, otherwise → CLEAN. | The overall health indicator. CLEAN means no significant issues. HIGH means important issues exist that need engineering attention. CRITICAL means serious problems that should block release. |

#### Summary Counts

| Parameter | How It Is Computed | What It Means |
|---|---|---|
| `total` | Count of ALL findings in the full report | The raw number before any filtering. Represents everything the platform detected. |
| `actionable` | Count of findings that passed the curation filter | How many findings are worth developer attention. This is the working number. |
| `must_fix_count` | Count of curated findings with severity `critical` or `high` | Issues that need immediate attention. These represent real risks — potential bugs, architectural flaws, or security concerns. |
| `should_fix_count` | Count of curated findings with severity `medium` | Genuine issues to address in normal workflow. Type errors, moderate complexity, design improvements. |
| `consider_count` | Count of curated findings with severity `low` or `info` that survived curation | Minor items. In practice this is usually 0 because the curation filter removes low/info severity. |
| `noise_removed` | Percentage: `(total - actionable) / total × 100` | What fraction of findings were filtered out as low-value. A higher percentage means the raw scan was noisy and the curation removed more. A lower percentage means most findings were actionable. |

#### Action Items

Each item in the `items` array represents one finding that passed curation. Items are sorted by severity (critical first, then high, then medium). The list is capped at 20 items.

| Field | What It Contains | How to Use It |
|---|---|---|
| `source` | Finding ID from the full report (e.g., `F-QA-PLATF-001`) | Look up this ID in the full report for detailed evidence, code snippets, and explanation. |
| `severity` | `critical`, `high`, or `medium` | Determines priority. Fix critical/high first. |
| `category` | `correctness`, `security`, or `design` | Tells you what type of issue it is. Correctness = potential bugs. Security = potential vulnerabilities. Design = structural/maintainability problems. |
| `file` | File path where the issue was found | Navigate directly to this file in your editor. |
| `line` | Line number where the issue starts | Jump to the exact location in the file. |
| `issue` | Short description of what is wrong | Read this to understand the problem without opening the file. |
| `action` | Recommended fix | What the platform suggests you do about it. May be empty for AI agent findings where the explanation in the full report provides the guidance. |

#### By Category

The `categories` array groups findings by type so you can see patterns.

| Field | What It Means |
|---|---|
| `category` | The finding category: `correctness`, `security`, `design`, `consistency`, `hygiene` |
| `must_fix` | How many critical + high findings in this category |
| `should_fix` | How many medium findings in this category |
| `consider` | How many low/info findings in this category (usually 0 after curation) |
| `total` | Sum of must_fix + should_fix + consider |

If one category dominates (e.g., 40 out of 50 findings are `correctness`), it indicates a systemic gap in that area — the team may need focused effort on type safety, testing, or whichever area is flagged.

#### Noise Reduction

The `exclusion_reasons` dictionary explains why findings were removed from the executive report. Each key is a reason, and the value is the count of findings excluded for that reason.

| Exclusion Reason | What It Means | When It Applies |
|---|---|---|
| `low severity` | Finding had severity `low` or `info` — trivial issues not worth executive attention | Style nits, informational notes, minor suggestions |
| `low confidence` | Finding had confidence `uncertain` — insufficient evidence to act on | Possible false positives, ambiguous detections |
| `pre-existing, non-critical` | Finding existed before recent changes and is not critical — old debt, not new risk | Findings classified as `pre_existing` with severity below `critical` |
| `no evidence` | Finding had no tool attribution, no code references, and no source name | Findings that lack substantiation — no tool call or code reference to back them up |

#### Relationship Between Reports

The executive report is derived entirely from the full report. Nothing is added — only filtered.

| Aspect | Full Report | Executive Report |
|---|---|---|
| **Findings** | All findings with full evidence, code snippets, explanations | Top 20 curated findings with location and recommendation only |
| **Purpose** | Reference document — the developer fixing the code reads this | Decision document — the lead deciding what to prioritize reads this |
| **Size** | Can be hundreds of pages (PDF) or megabytes (JSON) | Fits on one screen. Typically 1-2 pages PDF, <10KB JSON |
| **Traceability** | Contains everything | Every `source` ID maps back to a finding in the full report |

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
cortex/
├── cortex_engine/                     # Independent QA execution engine
│   ├── api.py                         #   Public API: create_scan_request(), run_scan()
│   ├── cli/run.py                     #   Standalone CLI entry point
│   ├── core/                          #   Finding entity, schemas, processing pipeline
│   ├── agents/                        #   5 specialized AI agents + infrastructure
│   ├── tools/                         #   27 tool wrappers + base + runner + repo scanner
│   ├── orchestration/                 #   14-phase scan pipeline + engines
│   ├── assessment/                    #   Quality gate + risk scorer
│   ├── reporting/                     #   Full report + executive summary (PDF cap: 500 findings)
│   ├── integrations/                  #   GitHub, Linear, Slack, dispatcher
│   ├── infrastructure/                #   Git, LLM client, config, hygiene checker
│   └── knowledge/                     #   SAST rules, CWE tree, design principles
│
├── cortex_backend/                    # Backend service layer
│   ├── main.py                        #   FastAPI app, startup recovery, stale reaper
│   ├── api/                           #   11 API routers (execution, reports, admin, etc.)
│   ├── models/                        #   SQLAlchemy models (PostgreSQL)
│   ├── services/                      #   EngineBridge, analytics, GitHub, admin settings
│   └── tasks/                         #   Background runners (QA, PR fetch, Linear sync)
│
├── cortex_frontend/                   #   React + TypeScript web UI
│   └── src/
│       ├── pages/                     #   Dashboard, QA Execution, Reports, Rule Reference, Admin
│       ├── components/                #   MetricsCard, ErrorBanner
│       └── data/                      #   Rule reference (28 tools, CWE documentation)
│
├── deploy/                            #   Deployment infrastructure
│   ├── docker/                        #   Dockerfiles, Compose, Nginx
│   ├── scripts/                       #   start.sh, stop.sh, restart.sh, health.sh
│   ├── config/                        #   development/.env, production/.env
│   └── docs/                          #   DEPLOYMENT.md
│
├── tests/                             # 28 unit tests
└── pyproject.toml
```

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev,tier1,backend]"

# Run tests
PYTHONPATH=. pytest

# Lint
ruff check cortex_engine/ cortex_backend/ tests/

# Type check
mypy cortex_engine/core/

# Engine standalone (CLI)
PYTHONPATH=. python -m cortex_engine.cli.run --repo . --tiers 1 --dry-run

# Backend
PYTHONPATH=. uvicorn cortex_backend.main:app --port 8000

# Frontend
cd cortex_frontend && npm install && npm run build
```

### Adding a New Tier 1 Tool

1. Create `cortex_engine/tools/my_tool.py`
2. Extend `Tier1Tool` with `is_available()`, `is_applicable()`, `run()`
3. Use `FindingFactory.create_from_tool()` for findings
4. Register in `cortex_engine/cli/run.py` `_register_tools()`

### Adding a New Agent

1. Create `cortex_engine/agents/my_agent.py` extending `ReviewAgent`
2. Create `prompts/my_agent.txt` with system prompt
3. Register in `cortex_engine/cli/run.py` `_build_agent_infrastructure()`

---

*Cortex — Identifies, reports, and recommends. Does NOT modify code.*
