# Document 01: Product Requirements Document (PRD)

**Cortex QA Platform**
**Date**: 2026-06-18

---

## 1. Problem Statement

Software development faces a widening gap between code production velocity and review capacity. At Meta, code per human-landed diff grew 105.9% YoY with 80%+ from AI-assisted coding, while review within 24 hours declined (RADAR). Existing solutions are fragmented: SAST tools have 35.7% precision causing alert fatigue (SAST-Genius), standalone LLMs hallucinate vulnerabilities (AgenticSCR), and single-model tools produce generic comments (RevAgent).

The QA Platform combines deterministic tools with specialized agentic AI in a structured pipeline — tools cast a wide net, agents provide deep contextual analysis that developers trust and act on.

## 2. Target Users

| Persona | Role | Primary Need |
|---|---|---|
| Software Developer | Submits code via PRs | Precise findings with explanations and fix recommendations |
| Tech Lead | Reviews team quality | Executive summaries, quality gate decisions |
| Security Engineer | Validates security findings | CWE-classified findings with taint path evidence |
| DevOps Engineer | Integrates into CI/CD | CLI interface, configurable policies, webhooks |

## 3. Core Capabilities

1. **Deterministic Code Analysis**: 27+ static analysis tools in check-only mode
2. **Agentic Correctness Review**: Autonomous agent tracing execution paths for logic bugs
3. **Agentic Security Review**: SAST validation with CWE classification and remediation
4. **Agentic Design Review**: Structural evaluation with improvement suggestions
5. **Agentic Cross-File Analysis**: Multi-file consistency and pattern detection
6. **Agentic Finding Validation**: Independent adversarial challenge of all findings
7. **Risk Scoring**: Heuristic gating to route files to appropriate analysis depth
8. **Quality Gate**: Graduated enforcement (shadow → advisory → enforced)
9. **Dual Reporting**: Full report + executive summary (JSON + PDF)
10. **Integrations**: GitHub PR comments, Linear tickets, Slack notifications

## 4. Workflows

**PR Review**: Push → Tier 1 tools → risk score → agent review (parallel) → validation → finding management → quality gate → reports → PR comments

**Full Audit**: CLI trigger → all files → all tiers → cross-file analysis → comprehensive report

**Pre-Commit**: Fast subset of Tier 1 tools only (<10 seconds)

## 5. Success Criteria

| Metric | Target | Evidence |
|---|---|---|
| Finding resolution rate | >70% | ICSE 2025: 73.8% |
| False positive rate | <15% | SAST-Genius: 89.5% precision |
| SAST FP reduction | >85% | SAST-Genius: 91%, QASecClaw: 88.6% |
| Developer satisfaction | >3.5/5 | ICSE 2025: 3.46/5 |
| Agent finding precision | >80% | AgenticSCR: 85% fewer FP |

## 6. Functional Requirements

### User-Facing Features (FR-01 to FR-06)
- CLI with all scan modes and configuration flags
- Repository-level `.qa-config.yml` configuration
- Structured finding presentation with evidence and recommendations
- Dual report generation (full + executive)
- Quality gate with graduated enforcement and override
- Scan history with trend tracking

### System Capabilities (FR-07 to FR-11)
- Local and remote repository scanning
- Diff-based change detection
- File hygiene (binary, large file, flagged file detection)
- Risk scoring for agent routing
- Author attribution via git blame

### AI/Agent Capabilities (FR-14 to FR-21)
- 5 agents: Correctness, Security, Design, Cross-File, Validator
- Three-pass review (scan → investigate → verify) per detection agent
- Semantic memory (SAST rules, CWE taxonomy, project conventions)
- Read-only tool access for autonomous code exploration
- Fail-open safety on all LLM failures
- Model diversity (Sonnet for detection, Opus for validation)

### Integration Requirements (FR-26 to FR-28)
- GitHub: PR comments (summary + inline), status check
- Linear: parent issue + sub-issues per finding
- Slack: webhook notification

## 7. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Scalability | 500K LOC repos, 200 files per PR, parallel agent execution |
| Reliability | Fail-open on LLM failures, Tier 1-only fallback, circuit breaker |
| Security | Audit-only (never modifies code), privacy exclusion paths, no secrets in reports |
| Performance | Tier 1: <60s for 100 files, Full pipeline: <5min for 10 files, Pre-commit: <10s |
| Observability | Structured JSON logging, per-agent cost tracking, audit trail |
| Maintainability | Externalized prompts, uniform tool interface, versioned config schema |
| Extensibility | Plugin architecture for tools, agents, integrations, report formats |

## 8. Product Boundaries

**Included**: Code review, issue detection, explanation, improvement suggestion, fix recommendation, quality gating, reporting, integrations

**Excluded**: Code modification, code generation, PR management, reviewer assignment, runtime analysis, IDE integration, model training

**Future**: IDE extensions, interactive review, fix suggestion agent, learning from resolution, custom rule creation, web dashboard
