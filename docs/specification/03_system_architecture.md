# Document 03: System Architecture Document

**QA Platform v2**
**Date**: 2026-06-18

---

## 1. Layered Architecture

```
INTERFACE LAYER     CLI, CI/CD Webhook
       │
APPLICATION LAYER   ScanOrchestrator, AgenticReviewEngine, ValidationEngine
       │
CORE LAYER          Finding, Schemas, FindingManager, QualityGate, RiskScorer
       │
INFRASTRUCTURE      LLMClient, GitOps, Config, Database, Integrations
```

**Dependency rule**: Dependencies point inward. Infrastructure implements Core interfaces. Application orchestrates Core logic. Interface calls Application.

## 2. Component Inventory

| Component | Type | Layer | Purpose |
|---|---|---|---|
| ScanOrchestrator | Deterministic | Application | Pipeline control, phase sequencing |
| Tier1Runner | Deterministic | Application | Execute 27 static analysis tools |
| RiskScorer | Deterministic | Core | Per-file risk assessment for agent routing |
| AgenticReviewEngine | Agentic | Application | Manage agent lifecycle and parallel execution |
| ValidationEngine | Agentic | Application | Manage validator agent execution |
| FindingManager | Deterministic | Core | 8-step finding post-processing |
| QualityGate | Deterministic | Core | Threshold evaluation |
| ReportGenerator | Deterministic | Application | Full + executive report output |
| IntegrationDispatcher | Deterministic | Application | Route to GitHub, Linear, Slack |
| AnthropicLLMClient | Infrastructure | Infrastructure | Claude API with circuit breaker |
| GitOperations | Infrastructure | Infrastructure | Git subprocess wrapper |
| ConfigManager | Infrastructure | Infrastructure | YAML config loading and validation |
| SQLite repositories | Infrastructure | Infrastructure | Finding and scan persistence |

## 3. Data Flow

```
ScanRequest
  → RepositoryContext (local_path, branch, commit, is_temporary)
    → ChangeSet (changed_files with diffs, modules)
      → FileSet (reviewable, skipped, hygiene_findings)
        → Tier1Findings[] + RiskScores
          → AgentFindings[] (from 4 detection agents)
            → ValidatedFindings[] (from validator agent)
              → ProcessedFindings (deduped, classified, attributed, ranked)
                → QualityGateResult (pass/advisory/fail)
                  → Reports (JSON + PDF) + Integrations
                    → ScanResult
```

## 4. External Dependencies

| Dependency | Required | Failure Impact |
|---|---|---|
| Claude API (Anthropic) | For Tier 2+ | Graceful degradation to Tier 1-only |
| Git binary | Yes | Cannot scan |
| Python 3.11+ | Yes | Cannot run |
| Tier 1 tool binaries | Per tool | Missing tools skipped |
| GitHub API | Optional | PR comments skipped |
| Linear API | Optional | Tickets skipped |
| WeasyPrint | Optional | Falls back to HTML |
| SQLite | Optional | History unavailable |

## 5. Runtime Behavior

**Concurrency model**: Single process, multiple threads for agent parallelism. Agents 1-3 execute concurrently per file via thread pool (configurable max_parallel, default 3). Agent 4 sequential after 1-3. Agent 5 sequential after all detection.

**Memory model**: No shared mutable state. Each agent receives immutable context. Findings are collected into a list by the orchestrator after all agents complete.

**Cleanup**: Temporary clones deleted in finally block. Database connections closed on completion. No resource leaks on any exit path.
