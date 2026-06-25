# Cortex QA Platform — Engineering Planning Document

**Document Type**: Engineering Planning Foundation
**Status**: Planning — No Implementation
**Date**: 2026-06-18
**Author Role**: Principal Software Architect, AI Systems Architect, Product Engineering Lead

---

## 1. Product Vision

### 1.1 Problem Statement

Modern software development faces a widening gap between code production velocity and review capacity. At Meta, significant lines of code per human-landed diff grew by 105.9% year over year, with 80%+ of that increase attributed to AI-assisted coding, while the percentage of diffs reviewed within 24 hours declined (RADAR, Section 2.5). Human code review remains the primary quality gate, but it is constrained by reviewer availability, cognitive load, and inconsistent depth.

Existing automated approaches are fragmented:

- **Static analysis tools (SAST)** provide broad coverage but produce high false positive rates (Semgrep: 35.7% precision, SAST-Genius Table 1) that cause alert fatigue and developer distrust. "Developers often avoid static analysis tools when warnings are too noisy or difficult to act on" (QASecClaw, Section I, citing Johnson et al. ICSE 2013).
- **Standalone LLM-based review** can reason about code semantics but hallucinates vulnerabilities, misses subtle flows, and produces inconsistent judgments (QASecClaw, Section II.C). "Direct LLM-based vulnerability detection remains unreliable" (AgenticSCR, Section 2).
- **Single-model review tools** blur the diverse, issue-specific nature of code changes, producing generic, non-informative comments, especially in complex scenarios such as bug fixes (RevAgent, Section 1).

The QA Platform solves this by combining deterministic tools with specialized agentic AI in a structured pipeline — where tools cast a wide net and agents provide deep, contextual, evidence-based analysis that developers can trust and act on.

### 1.2 Target Users and Personas

**Persona 1: Software Developer (Primary)**
- Submits code via PRs or commits
- Receives QA findings as actionable review comments
- Needs: precise findings with clear explanations and concrete fix recommendations
- Pain point: noisy tools, false positives, vague "this might be a problem" comments
- Success signal: resolves findings without pushback — the ICSE 2025 study found 73.8% resolution rate when findings are precise and relevant

**Persona 2: Tech Lead / Engineering Manager**
- Reviews team code quality trends
- Uses QA reports to assess risk before releases
- Needs: executive summaries, severity distribution, quality gate decisions
- Pain point: no visibility into code quality across the team
- Success signal: can make release decisions based on QA gate results

**Persona 3: Security Engineer**
- Reviews security findings from the platform
- Validates critical vulnerability reports
- Needs: CWE-classified findings with taint path evidence and exploitability assessment
- Pain point: SAST tools produce hundreds of alerts, most are false positives
- Success signal: SAST false positive reduction >85% (SAST-Genius: 91%, QASecClaw: 88.6%)

**Persona 4: DevOps / Platform Engineer**
- Integrates the QA platform into CI/CD pipelines
- Configures triggers, thresholds, and quality gates
- Needs: CLI interface, configurable policies, webhook/API integration
- Pain point: tools that don't integrate with existing workflows
- Success signal: seamless integration, no pipeline disruption

### 1.3 Core Capabilities

1. **Deterministic Code Analysis**: 27+ static analysis tools running in check-only mode — linters, SAST scanners, type checkers, complexity analyzers, dependency auditors, secret scanners.

2. **Agentic Code Quality Review**: An autonomous agent that plans its review approach, navigates code via tools, traces execution paths, and produces findings about correctness, logic bugs, edge cases, and error handling — with explanations and fix recommendations.

3. **Agentic Security Review**: An autonomous agent with security-specific semantic memory (SAST rules, CWE taxonomy) that validates SAST findings, traces taint paths, classifies vulnerabilities by CWE, and provides remediation guidance — with fail-open safety.

4. **Agentic Design & Improvement Review**: An autonomous agent that evaluates code structure against design principles, identifies maintainability issues, and suggests concrete improvements — addressing the "suggest improvements" requirement distinct from bug detection.

5. **Agentic Cross-File Analysis**: An autonomous agent that compares code across module boundaries to detect systemic inconsistencies, broken contracts, and architectural pattern violations — operating on multi-file scope.

6. **Agentic Finding Validation**: An independent adversarial agent that challenges ALL findings from other agents, filters false positives, resolves semantic duplicates, and assigns calibrated confidence scores — the single most impactful component for precision and developer trust.

7. **Intelligent Risk Scoring**: Heuristic-based risk assessment that determines which files require agent-level review, routing low-risk changes through deterministic tools only and high-risk changes through the full agentic pipeline.

8. **Quality Gate Evaluation**: Configurable threshold-based pass/fail decisions on finding severity and confidence, supporting graduated enforcement (shadow → advisory → enforced).

9. **Dual Report Generation**: Full detailed report (all findings, evidence, recommendations) and executive summary report (actionable, noise-free, categorized).

10. **Integration Layer**: GitHub PR comments, Linear ticket creation, Slack notifications, CI/CD webhook support.

### 1.4 Expected Workflows

**Workflow 1: PR Review (Primary)**
1. Developer opens or updates a PR
2. Platform triggers via webhook or CI
3. Tier 1 deterministic tools scan all changed files
4. Risk scorer evaluates each file — low-risk files get Tier 1 findings only
5. High-risk files are reviewed by Agent 1 (Correctness), Agent 2 (Security), Agent 3 (Design) in parallel
6. Agent 5 (Validator) challenges all findings, filters false positives, resolves duplicates
7. Finding Manager applies algorithmic dedup, clustering, prioritization
8. Quality gate evaluates findings against thresholds
9. Reports generated (full + executive)
10. Findings posted as PR comments (inline on file:line) and optionally as Linear tickets
11. Developer resolves findings; platform tracks resolution

**Workflow 2: Commit Scan**
1. Developer pushes a commit (not necessarily a PR)
2. Platform scans the commit diff
3. Tier 1 tools + risk scoring + agent review (same pipeline as PR review)
4. Findings stored in database for trend tracking
5. No PR comments (no PR context); findings available via CLI/API

**Workflow 3: Full Audit**
1. Triggered manually via CLI (`qa run --repo . --audit`) or on schedule
2. ALL files scanned (not just changed files)
3. Full Tier 1 scan
4. All files reviewed by Agents 1, 2, 3 (no risk scoring bypass)
5. Agent 4 (Cross-File) runs across module boundaries
6. Agent 5 (Validator) validates all findings
7. Comprehensive reports generated
8. Systemic patterns and architectural observations included

**Workflow 4: Pre-Commit Hook (Optional, Fast)**
1. Developer runs pre-commit hook
2. Subset of fast Tier 1 tools run on staged files
3. Critical findings shown in terminal
4. No agent review (latency constraint <10 seconds)
5. Full review happens on PR push

### 1.5 Success Criteria

| Metric | Target | Evidence Basis |
|---|---|---|
| Finding resolution rate | >70% | ICSE 2025: 73.8% with Qodo PR-Agent |
| False positive rate | <15% | SAST-Genius: 89.5% precision; QASecClaw: 95.1% precision |
| SAST false positive reduction | >85% | SAST-Genius: 91%; QASecClaw: 88.6% |
| Developer satisfaction | >3.5/5 | ICSE 2025: 3.46/5 average rating |
| PR cycle time impact | Neutral or improved | RADAR: 330% reduction in time-to-close |
| Quality gate accuracy | <5% incorrect blocks | Conservative thresholds, graduated enforcement |
| Agent finding precision | >80% | SAST-Genius: 89.5%; AgenticSCR: 85% fewer FP than static LLM |

---

## 2. Functional Requirements

### 2.1 User-Facing Features

**FR-01: CLI Interface**
- `qa run --repo <path|url>` — run a scan on a repository
- `--branch`, `--commit`, `--pr` — specify scan target
- `--audit` — full codebase audit mode
- `--tiers 1,2,3` — select analysis tiers
- `--report json,pdf` — output format
- `--cost-limit <usd>` — maximum LLM spend
- Progress feedback during scan execution
- Summary output on completion (finding count, severity distribution, gate result)

**FR-02: Configuration File (`.qa-config.yml`)**
- Repository-level configuration
- Trigger enablement and tier selection per trigger
- Agent-specific knowledge (coding conventions, security policies)
- Quality gate thresholds (graduated: shadow/advisory/enforced)
- Suppression rules with expiry and approval tracking
- Ignore rules (file patterns, binary extensions, max file size)
- Model selection and cost controls
- Integration credentials (Linear, GitHub, Slack)

**FR-03: Finding Presentation**
- Each finding includes: location (file:line), severity, confidence, category, source agent, explanation, evidence (tool calls/code references), recommendation
- Findings ordered by severity × confidence
- Code snippet context around each finding (3 lines above/below, flagged lines marked)
- Security findings include CWE classification and remediation steps

**FR-04: Report Generation**
- Full report: all findings, clusters, resolved issues, positive observations, suppressed findings, execution metadata, reproducibility command
- Executive report: actionable summary — risk level, must-fix/should-fix/consider counts, prioritized action items table, noise reduction summary

**FR-05: Quality Gate**
- Pass/fail/advisory decision based on finding severity counts and confidence thresholds
- Graduated enforcement: shadow (log only) → advisory (warn, don't block) → enforced (block merge)
- Per-agent graduation: new agents start in shadow mode
- Override mechanism with approval and expiry

**FR-06: Scan History**
- Persistent storage of scan results
- Trend tracking over time (finding count, severity distribution, resolution rate)
- Comparison between scans (new findings, resolved findings, persistent findings)

### 2.2 System Capabilities

**FR-07: Repository Resolution**
- Accept local paths and remote Git URLs
- Clone remote repos to temporary directory (shallow clone for efficiency)
- Branch/commit checkout support
- Automatic cleanup of temporary clones

**FR-08: Change Detection**
- Diff-based change detection (PR diff, commit diff, branch comparison)
- File-level and line-level change tracking
- Module/package detection for cross-file analysis scoping
- Generated code detection (marker-based and path-based)

**FR-09: File Hygiene**
- Binary file detection and skip (with flagging in report)
- Large file detection and skip (configurable threshold, default 10MB)
- Files that shouldn't be committed (node_modules, .env, __pycache__) — flag but still scan text files

**FR-10: Risk Scoring**
- Heuristic risk score per file: complexity × change size × SAST finding count × path sensitivity
- Configurable threshold for agent review bypass
- Low-risk files: Tier 1 findings only
- High-risk files: full agentic pipeline

**FR-11: Author Attribution**
- Git blame for per-finding author attribution
- PR author attribution for introduced findings
- Configurable default author when git config unavailable
- Attribution source tracking (git-blame, pr-author, commit-author)

### 2.3 Automation Workflows

**FR-12: Trigger System**
- PR push trigger (webhook or CI integration)
- Commit push trigger
- Scheduled/nightly trigger (cron-based)
- Ad-hoc manual trigger (CLI)
- Pre-commit hook trigger (fast mode, Tier 1 only)
- Each trigger configurable: which tiers, which agents, report formats

**FR-13: CI/CD Integration**
- GitHub Actions integration (workflow YAML)
- GitLab CI integration
- Generic webhook trigger
- Exit code reflects quality gate result (0 = pass, 1 = fail)
- Artifact upload for reports

### 2.4 AI/Agent Capabilities

**FR-14: Agent 1 — Correctness Agent**
- Plans review approach based on code characteristics (API endpoint, data model, utility function)
- Navigates code via tools: read_file, grep, git_diff, list_directory, expand_context
- Three-pass review: scan (identify candidates) → investigate (gather evidence via tool calls) → verify (challenge findings, suppress unsupported ones)
- Produces findings about: logic bugs, null handling, off-by-one, race conditions, resource leaks, error path failures, incorrect algorithms
- Each finding includes: execution trace evidence, explanation of why the bug occurs, concrete fix recommendation

**FR-15: Agent 2 — Security Agent**
- Receives Tier 1 SAST findings as structured input (not searching from scratch)
- Loads SAST rules as semantic memory (CodeQL patterns with CWE mappings, severity, vulnerable/secure code examples, remediation steps)
- Loads CWE taxonomy tree for hierarchical vulnerability classification
- Traces taint paths: source (user input) → transformation → sink (database, file, shell)
- Validates each SAST finding as true positive or false positive with reasoning
- For true positives: CWE classification, exploitability assessment, remediation steps
- For false positives: suppression with documented reasoning
- Fail-open safety: if LLM fails, ALL SAST findings retained unfiltered

**FR-16: Agent 3 — Design & Improvement Agent**
- Evaluates code structure against design principles (SOLID, coupling, cohesion, abstraction)
- Identifies maintainability issues: excessive complexity, poor naming, missing patterns, inconsistent error handling
- Produces improvement suggestions: concrete refactoring recommendations with expected benefit
- Checklist includes: test adequacy, documentation completeness, logging practices, API design
- Each suggestion includes: what to change, why it improves the code, example of the improved structure

**FR-17: Agent 4 — Cross-File Analysis Agent**
- Conditional execution: full audits and multi-module PRs only
- Examines module boundaries, interface contracts, cross-module consistency
- Detects: inconsistent validation patterns, missing authentication on some endpoints, interface mismatches, systemic code smells
- Compares implementations across similar files (all controllers, all services, all handlers)
- Produces systemic findings with cross-file evidence

**FR-18: Agent 5 — Finding Validator Agent**
- Receives ALL findings from Agents 1-4 and Tier 1 tools
- Re-reads referenced code to independently verify claims
- Adversarially challenges each finding: tries to REFUTE it
- Resolves semantic duplicates across agents (when two agents describe the same issue differently)
- Assigns final confidence scores: confirmed, likely, uncertain
- Fail-open: if uncertain, retains the finding rather than suppressing
- Should use a different model or prompt role than detection agents to prevent correlated errors

**FR-19: Agent Orchestration**
- Agents 1, 2, 3 run in parallel per file (independent, no data dependency)
- Agent 4 runs after Agents 1-3 when cross-file scope is active
- Agent 5 runs after all other agents complete
- Orchestration is deterministic (fixed pipeline), not agent-driven
- Cost tracking across all agent invocations
- Cost limit enforcement (skip remaining agents if limit reached)

**FR-20: Semantic Memory Management**
- SAST rules loaded into Security Agent's semantic memory
- CWE taxonomy tree loaded for hierarchical classification
- Project coding conventions loaded into Correctness and Design agents (from `.qa-config.yml` or project documentation)
- Memory is read-only — agents use it for reasoning, not for storage

**FR-21: LLM Configuration**
- Model selection per agent (e.g., Opus for validation, Sonnet for per-file review)
- Fallback chain: primary → secondary → skip (with finding retention)
- Temperature: 0 for deterministic output
- Structured JSON output with schema validation
- Retry with backoff on transient errors
- Circuit breaker on persistent failures

### 2.5 Reporting Requirements

**FR-22: Full Report Structure**
11 sections: report metadata, repository context, developer attribution, scope summary, executive summary, findings, finding clusters, resolved issues, positive observations, suppressed findings, appendix (tool call log, reproducibility command, config hash)

**FR-23: Executive Report Structure**
Risk level badge, must-fix/should-fix/consider counts with noise reduction percentage, action items table (severity, source, location, finding, action — full text, no truncation), by-category summary table, noise reduction explanation

**FR-24: Report Formats**
- JSON (machine-readable, primary format)
- PDF (human-readable, generated via HTML → WeasyPrint)
- Control characters stripped from all text entering PDF rendering

**FR-25: Finding Output Schema**
Each finding must include:
- `id`: unique identifier
- `source`: agent or tool that produced the finding
- `tier`: which analysis tier
- `category`: issue category (correctness, security, design, consistency)
- `severity`: critical | high | medium | low | info
- `confidence`: confirmed | likely | uncertain
- `classification`: introduced | modified | pre-existing (diff-awareness)
- `file`: file path
- `start_line`, `end_line`: location
- `author`: attributed author with source
- `title`: concise issue description (max 80 chars)
- `explanation`: detailed explanation with evidence
- `evidence`: tool calls, code references, metrics
- `recommendation`: concrete, actionable fix
- `cwe`: CWE identifier (security findings)
- `validation_status`: confirmed | likely | uncertain | suppressed (from Validator)
- `validation_reasoning`: Validator's reasoning for its verdict

### 2.6 Integration Requirements

**FR-26: GitHub Integration**
- PR summary comment with finding overview
- Inline review comments on specific file:line in the PR diff
- Status check (pass/fail) reflecting quality gate result

**FR-27: Linear Integration**
- One parent issue per scan
- Sub-issues per finding (severity, description, recommendation)
- Developer assignment by email match
- Configurable: max issues per scan, minimum severity for ticket creation

**FR-28: Slack Integration**
- Webhook notification on scan completion
- Summary message: finding count, severity distribution, gate result
- Configurable: notify on critical findings, gate failures, nightly completion

---

## 3. Non-Functional Requirements

### 3.1 Scalability

**NFR-01**: Support repositories up to 500K lines of code without degradation.

**NFR-02**: Support scanning up to 200 files per PR without timeout.

**NFR-03**: Agent execution must be parallelizable — Agents 1, 2, 3 run concurrently per file with no shared state.

**NFR-04**: Cost scales linearly with file count — no quadratic or exponential cost growth from agent interactions.

### 3.2 Reliability

**NFR-05**: Fail-open on LLM failures — if any agent fails, Tier 1 findings for affected files are retained unfiltered. No silent suppression of findings.

**NFR-06**: Graceful degradation — if all LLM calls fail, the platform produces a Tier 1-only report (deterministic tools always work).

**NFR-07**: Idempotent scans — running the same scan twice on the same commit produces consistent results (modulo LLM non-determinism, mitigated by temperature=0).

**NFR-08**: Agent circuit breaker — after N consecutive failures, skip remaining agent calls and proceed with available findings.

### 3.3 Security

**NFR-09**: The platform NEVER modifies the repository under evaluation. This is an audit-only system. This constraint must be enforced at every layer.

**NFR-10**: Code sent to LLM APIs must be governed by privacy configuration — sensitive paths can be excluded from AI review.

**NFR-11**: API keys and tokens stored as environment variables or encrypted configuration, never in source code or reports.

**NFR-12**: Audit log of all LLM API calls — prompt hash, token count, cost, timestamp, finding IDs produced.

### 3.4 Performance

**NFR-13**: Tier 1 scan of a 100-file PR completes in under 60 seconds.

**NFR-14**: Full agentic pipeline (Tier 1 + Tier 2 + Validation) for a 10-file PR completes in under 5 minutes.

**NFR-15**: Pre-commit hook execution under 10 seconds.

**NFR-16**: Report generation (JSON + PDF) under 10 seconds.

### 3.5 Observability

**NFR-17**: Structured logging (JSON format) for all pipeline stages with correlation IDs.

**NFR-18**: Cost tracking per scan, per agent, per model — exposed in report metadata.

**NFR-19**: Finding attribution to source agent — every finding traces back to which agent produced it and which tool calls supported it.

**NFR-20**: Validation decisions are transparent — every suppression or confidence assignment has documented reasoning.

### 3.6 Maintainability

**NFR-21**: Agent prompts are externalized (not hardcoded in agent logic) — editable without code changes.

**NFR-22**: Tool wrappers follow a uniform interface — adding a new Tier 1 tool requires implementing one class with `is_available`, `is_applicable`, and `run` methods.

**NFR-23**: Configuration schema is versioned and validated at load time (Pydantic schema with clear error messages).

### 3.7 Extensibility

**NFR-24**: New agents can be added without modifying existing agents or the orchestrator — plug-in architecture.

**NFR-25**: New Tier 1 tools can be added without modifying the tool runner — auto-discovery or registry pattern.

**NFR-26**: New report formats can be added without modifying the report generator — strategy/template pattern.

**NFR-27**: Integration layer supports adding new integrations (Jira, GitLab, etc.) without modifying the core pipeline.

---

## 4. Product Boundaries

### 4.1 What Is Included

- Automated code review: issue detection, explanation, and recommendation
- Security vulnerability validation with CWE classification
- Design and improvement suggestions
- Cross-file consistency analysis
- Independent finding validation with adversarial challenge
- Quality gate with graduated enforcement
- Dual report generation (full + executive)
- GitHub PR integration (comments + status check)
- Linear ticket creation
- CLI-first interface
- Repository-level configuration
- Diff-aware analysis (focus on changed code)
- Author attribution via git blame
- Finding lifecycle tracking (open → resolved)
- Suppression management with expiry

### 4.2 What Is Excluded

- **Code modification**: The platform does NOT fix, patch, or modify code. It identifies, reports, and recommends.
- **Code generation**: The platform does NOT generate code, tests, or documentation.
- **PR creation or management**: The platform reviews code, it doesn't manage the PR lifecycle.
- **Reviewer assignment**: The platform doesn't select or assign human reviewers.
- **Runtime analysis / dynamic testing**: No code execution, sandbox environments, or test running.
- **IDE integration**: CLI and CI/CD only in v2. IDE plugins are a future expansion.
- **Real-time / interactive review**: The platform produces a report per scan. It doesn't support interactive Q&A with developers during review.
- **Custom model training or fine-tuning**: Uses general-purpose LLMs with prompt engineering and semantic memory. No model training.

### 4.3 Future Expansion Areas

- IDE extensions (VS Code, JetBrains) for real-time review during development
- Interactive review: developer asks follow-up questions about findings
- Fix suggestion agent: generates concrete patches (not just textual recommendations)
- Learning from resolution: track which findings developers resolve vs dismiss, improve precision over time
- Custom rule creation: natural language → SAST rule translation (SAST-Genius Section II.E)
- Multi-repository analysis: cross-repo consistency for organizations with multiple repos
- Jira, GitLab, Bitbucket integrations
- Dashboard / web UI for trend visualization

---

## 5. Engineering Principles

### 5.1 Domain-Driven Design

The platform is organized around business domains, not technical layers:

- **Analysis Domain**: Tier 1 tools, agent execution, finding production
- **Validation Domain**: Finding validation, deduplication, confidence calibration
- **Assessment Domain**: Quality gate evaluation, risk scoring
- **Reporting Domain**: Report generation, finding presentation
- **Integration Domain**: GitHub, Linear, Slack, CI/CD interfaces
- **Configuration Domain**: Repository config, platform settings, suppression rules

Each domain has clear boundaries, its own internal model, and communicates with other domains through well-defined interfaces (finding schemas, report schemas).

### 5.2 Clean Architecture

- **Core**: Finding schema, agent interfaces, tool interfaces — no external dependencies
- **Application**: Orchestrator, pipeline stages, finding management — depends on core only
- **Infrastructure**: LLM clients, Git operations, file I/O, database — implements core interfaces
- **Interface**: CLI, webhook handlers, API endpoints — thin layer calling application services

Dependencies point inward. Infrastructure implements interfaces defined by the core. The orchestrator depends on agent interfaces, not concrete agent implementations.

### 5.3 Agentic AI Design Principles

**Principle 1: Agents demonstrate genuine autonomy.**
Each agent plans its review approach based on observations, decides which tools to invoke, and adapts its depth based on what it discovers. Agents are not prompt wrappers — they operate in observation-action loops.

**Principle 2: Agents are separated by capability boundaries, not by domain focus.**
Agent boundaries exist where two components differ in input scope (per-file vs multi-file), cognitive mode (constructive vs adversarial vs comparative vs skeptical), or knowledge requirements (conventions vs SAST rules vs CWE taxonomy). Domain focus alone (bugs vs security) is not sufficient — the cognitive mode and knowledge differences must also be present.

**Principle 3: Deterministic tools first, agents second.**
SAST tools cast the wide net (high recall). Agents provide contextual validation (high precision). The LLM never searches the codebase from scratch — it reviews candidate findings or focused code sections. This is the converging pattern from SAST-Genius, QASecClaw, and RADAR.

**Principle 4: Independent validation is mandatory.**
The Finding Validator Agent operates independently from detection agents — different cognitive mode (skeptical vs constructive), ideally different model. This prevents correlated errors and is the single most impactful component for precision (RevAgent ablation, 3+1 paper: +10.3pp).

**Principle 5: Fail-open safety.**
When any agent or LLM call fails, findings are retained, not suppressed. The platform's failure mode is "show more findings than necessary" — never "hide real issues due to infrastructure failure."

**Principle 6: Precision over recall.**
More agents or more aggressive analysis does NOT always improve quality. The ICSE 2025 study found 26.2% of automated comments were "Won't Fix" — false positives that erode trust. SmellBench found the most aggressive agent introduced 140 new code smells while fixing others. Every design decision prioritizes precision.

**Principle 7: Non-agentic components are not called agents.**
The orchestrator, risk scorer, finding manager, quality gate, and report generator are deterministic functions. They don't plan, explore, or adapt. Labeling them as agents would misrepresent the architecture.

### 5.4 Separation of Concerns

- Detection (Agents 1-4) is separated from validation (Agent 5)
- Analysis (agents + tools) is separated from assessment (quality gate)
- Finding production is separated from finding presentation (reports)
- Pipeline orchestration is separated from agent logic
- Configuration is separated from execution

### 5.5 Modularity

- Each agent is an independent module with its own prompt, knowledge, and tools
- Each Tier 1 tool is an independent module implementing a shared interface
- Each integration is an independent module
- Removing any single component doesn't break the pipeline — it degrades gracefully

### 5.6 Testability

- Agents can be tested independently with fixture files and expected findings
- Tier 1 tools can be tested with known-bad code samples
- The pipeline can be tested with mock agents that return predetermined findings
- Quality gate logic is pure function — testable without infrastructure
- Report generation is deterministic given fixed input — snapshot testable

### 5.7 Human-in-the-Loop

- Quality gate override requires human approval with documented reason and expiry
- Suppression rules require human approval and have mandatory expiry
- Finding resolution is tracked but always at the developer's discretion — the platform recommends, never forces
- Graduated gate enforcement allows teams to observe findings before blocking on them
- Executive report is designed for human decision-making, not automated consumption

---

## 6. System Decomposition

### 6.1 Core Domains

| Domain | Responsibility | Key Entities |
|---|---|---|
| **Analysis** | Produce findings from code | Finding, Tool, Agent, ToolResult, AgentResult |
| **Validation** | Validate and refine findings | ValidatedFinding, ValidationVerdict, ConfidenceScore |
| **Assessment** | Evaluate overall quality | QualityGateResult, RiskScore, SeverityDistribution |
| **Reporting** | Present findings to humans | Report, ExecutiveReport, FindingPresentation |
| **Integration** | Connect to external systems | PRComment, LinearIssue, SlackMessage, Webhook |
| **Configuration** | Define platform behavior | QAConfig, SuppressionRule, AgentConfig, TriggerConfig |
| **Repository** | Access and understand code | Repository, Diff, FileContent, BlameEntry, CommitInfo |

### 6.2 Subsystems

**Subsystem 1: Scan Orchestrator**
- Controls the end-to-end pipeline execution
- Manages stage transitions: Tier 1 → Risk Scoring → Agent Review → Validation → Post-processing
- Handles cost tracking and cost limit enforcement
- Provides progress callbacks
- Deterministic — no agentic behavior

**Subsystem 2: Tier 1 Tool Engine**
- Discovers and runs deterministic tools
- Uniform tool interface: `is_available()`, `is_applicable(file)`, `run(file, repo)`
- Line number validation on all tool output
- Batch execution with error isolation (one tool failure doesn't stop others)
- Tool result normalization into universal finding schema

**Subsystem 3: Agentic Review Engine**
- Manages agent lifecycle: instantiation, memory loading, execution, result collection
- Provides tool access to agents (read_file, grep, git_diff, expand_context, list_directory)
- Enforces agent constraints (read-only access, token budget, timeout)
- Collects structured output per agent
- Parallel execution of independent agents

**Subsystem 4: Finding Validation Engine**
- Hosts Agent 5 (Finding Validator)
- Feeds ALL findings from Tier 1 + Agents 1-4 to the validator
- Collects validation verdicts: confirmed, likely, uncertain, suppressed
- Applies fail-open: unvalidated findings default to "uncertain" (retained)

**Subsystem 5: Finding Management Pipeline**
- Deterministic post-processing: deduplication, clustering, ranking, suppression
- Diff-awareness classification (introduced, modified, pre-existing)
- Author attribution via git blame
- Code snippet extraction
- Finding lifecycle state management

**Subsystem 6: Quality Gate**
- Threshold evaluation against configured severity limits
- Graduated enforcement (shadow/advisory/enforced)
- Override management with approval and expiry
- Per-agent graduation (new agents in shadow mode)

**Subsystem 7: Report Generator**
- Template-driven output (JSON, PDF/HTML)
- Full report with all 11 sections
- Executive report with actionable summary
- Control character sanitization for PDF output
- PDF generation via WeasyPrint with HTML fallback

**Subsystem 8: Integration Layer**
- GitHub: PR comments (summary + inline), status check
- Linear: parent issue + sub-issues per finding
- Slack: webhook notification
- Generic webhook for CI/CD

**Subsystem 9: Repository Access Layer**
- Git operations (clone, diff, blame, log, branch resolution)
- File system access (read-only)
- Change detection and diff parsing
- Generated code detection
- Repository hygiene checking

**Subsystem 10: Configuration Manager**
- `.qa-config.yml` loading and validation (Pydantic schema)
- Default configuration for repositories without config files
- Environment variable resolution for secrets
- Configuration versioning

### 6.3 Major Workflows (Data Flow)

**Primary Data Flow:**

```
Repository
    │
    ▼
[Change Detection] → changed files list + diffs
    │
    ▼
[File Hygiene Check] → binary files flagged/skipped, large files flagged/skipped
    │
    ▼
[Tier 1 Tool Engine] → candidate findings (deterministic)
    │
    ▼
[Risk Scorer] → per-file risk scores
    │
    ├── low-risk files → findings pass directly to Finding Management
    │
    ▼
[Agentic Review Engine]
    ├── Agent 1 (Correctness) ──┐
    ├── Agent 2 (Security)   ───┤── per-file, parallel
    └── Agent 3 (Design)     ───┘
    │
    ├── [Agent 4 (Cross-File)] ← conditional: audits + multi-module PRs
    │
    ▼
[Finding Validation Engine]
    └── Agent 5 (Validator) → validated findings with confidence scores
    │
    ▼
[Finding Management Pipeline]
    ├── Deduplication
    ├── Clustering
    ├── Diff-awareness classification
    ├── Author attribution
    ├── Code snippet extraction
    ├── Suppression application
    └── Prioritization/ranking
    │
    ▼
[Quality Gate] → pass / advisory / fail
    │
    ▼
[Report Generator] → Full Report + Executive Report
    │
    ▼
[Integration Layer]
    ├── GitHub PR comments
    ├── Linear tickets
    └── Slack notification
```

### 6.4 Critical Technical Decisions

**CTD-01: Agent tool access model**
Agents interact with the codebase through a constrained set of tools (read_file, grep, git_diff, expand_context, list_directory). These tools are READ-ONLY. No agent has write access to the repository. This enforces the audit-only constraint at the tool level.

**CTD-02: Agent-to-agent communication**
Agents do NOT communicate with each other. They run independently. The only data flow between agents is through the pipeline: detection agents produce findings, the validator agent receives those findings. This eliminates coordination complexity and enables parallel execution.

**CTD-03: LLM model strategy**
- Detection agents (1-4): Claude Sonnet (balance of capability and cost for per-file work)
- Validator agent (5): Claude Opus or a different model family (diversity prevents correlated errors, supported by TAP paper: heterogeneous models +17% defect detection)
- Fallback chain per agent: primary model → secondary model → skip with finding retention
- Temperature: 0 for all agents (deterministic output)

**CTD-04: Semantic memory implementation**
- SAST rules and CWE taxonomy stored as structured JSON documents
- Loaded into agent context at invocation time (not fine-tuned into model weights)
- Read-only — agents query memory, they don't modify it
- Project-specific knowledge (coding conventions) loaded from configuration or project docs

**CTD-05: Finding schema as the universal contract**
The Finding schema is the central data contract of the entire system. Every component — tools, agents, finding manager, quality gate, report generator, integrations — operates on the same Finding structure. Changes to this schema affect every component and must be versioned.

**CTD-06: Fail-open as the default safety mode**
Every fallible component (LLM calls, tool execution, file I/O) defaults to fail-open: retain existing data rather than suppressing it. The platform may over-report on failure, but it never silently hides issues.

**CTD-07: Risk scoring as a cost control mechanism**
Not every file needs agent review. The risk scorer gates agent invocation based on file characteristics (complexity, change size, SAST finding count, path sensitivity). This makes LLM cost proportional to risk, not to diff size.

---

## Research Foundation

This planning document is grounded in evidence from the following peer-reviewed and validated research:

| Paper | Venue | Key Contribution to This Design |
|---|---|---|
| SAST-Genius (Agrawal & Ahi, 2025) | IEEE S&P 2025 | Two-stage SAST+LLM pipeline; 91% FP reduction; semantic memory for security; fail-open design |
| RADAR (Adams et al., 2026) | Meta Production (535K diffs) | Multi-stage funnel architecture; risk scoring as cost control; one LLM layer with gating; production validation |
| QASecClaw (Ameen et al., 2026) | arXiv (open-source) | Mission Orchestrator + pipeline agents; fail-open safety; 88.6% FP reduction; SAST as candidate generator |
| Automated CR in Practice (Cihan et al., 2024) | ICSE 2025 (SEIP) | 73.8% resolution rate; 26.2% false positive cost; precision > recall for trust; project-specific variability |
| AgenticSCR (Charoenwet et al., 2026) | FSE 2026 | Detector-validator chain; semantic memory (SAST rules +5.7%, CWE +4.5%); knowledge interference when mixing types; agentic tool use |
| RevAgent (Li et al., 2025) | arXiv (replication available) | Category-specific agents outperform general agent; critic agent = most impactful component; 5 categories + 1 critic |
| Rethinking Agentic CR (Kamalı et al., 2026) | TOSEM (submitted) / ICSE-JAWs 2026 | 5-stage lifecycle framework; reviewers as supervisory operators; specialized agents with human quality gates |
