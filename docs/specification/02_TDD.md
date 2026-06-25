# Document 02: Technical Design Document (TDD)

**Cortex QA Platform**
**Date**: 2026-06-18

---

## 1. Design Philosophy

Three architectural patterns, each validated by research:

1. **Multi-stage funnel** (RADAR, Meta): Each stage progressively refines analysis. Broad deterministic scanning narrows to targeted agentic review, then adversarial validation filters noise.

2. **Deterministic-first, agentic-second** (SAST-Genius): Deterministic tools produce candidates with high recall. Agents provide contextual validation with high precision. The LLM never searches from scratch.

3. **Detector-validator chain** (AgenticSCR, FSE 2026): Detection agents produce findings. An independent validator adversarially challenges them. Separation prevents correlated errors.

## 2. System Type

- **CLI-first batch processor**: Receives scan request, executes pipeline, produces reports
- **Single-process**: Entire pipeline in one process per scan. No microservices, no message queues
- **Stateless between scans**: Each scan is independent. SQLite for history only (not critical path)

**Why not a server**: A scan is a bounded operation (start → process → finish). No long-running state, websockets, or real-time updates. CLI is simpler to deploy, test, and debug.

## 3. Pipeline Architecture

```
ScanRequest → Resolve Repo → Detect Changes → Hygiene Check
    → Tier 1 Tools (parallel) → Risk Score
    → Agent Review (parallel per file: Correctness + Security + Design)
    → Cross-File Analysis (conditional)
    → Finding Validation (batched)
    → Finding Management (dedup → classify → attribute → suppress → cluster → rank)
    → Quality Gate → Reports → Integrations → ScanResult
```

### Phase Execution Rules
- Phases execute strictly in order. No phase starts before predecessor completes.
- Within agent review, Agents 1-3 run in parallel per file (no data dependency).
- Cross-file analysis is conditional (audits + multi-module PRs only).
- Validator receives ALL findings from all prior phases.
- Post-processing is entirely deterministic.
- Cost tracked cumulatively. Cost limit skips remaining agent calls.

## 4. Communication Patterns

**Internal**: Synchronous in-process function calls. No serialization overhead.

**Agent communication**: Zero direct communication. Pipeline-mediated data flow only. Detection agents produce findings → pipeline aggregates → validator receives all findings. No agent reads another agent's output directly.

**External**: HTTPS to Claude API (retries + backoff), GitHub API, Linear GraphQL API, Slack webhook. Git via subprocess.

## 5. Key Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Architecture** | Pipeline-funnel, not microservices | Scan is bounded batch operation. Single process is simpler. |
| **Database** | SQLite (embedded) | Zero-config, no server, works everywhere. PostgreSQL optional for teams. |
| **Agent count** | 5 agents | Each justified by ≥2 capability boundaries (scope, cognitive mode, knowledge). |
| **Agent communication** | Zero (pipeline-mediated) | Eliminates coordination complexity, enables parallel execution. |
| **Model diversity** | Sonnet for detection, Opus for validation | Prevents correlated errors. TAP paper: +17% defect detection with heterogeneous models. |
| **Fail-open** | Universal | Cost of FP (developer annoyance) < cost of FN (missed vulnerability in production). |
| **Prompts** | Externalized files | Editable without code changes. Versioned like code. |
| **Core domain** | Zero external dependencies | Pure Python. Testable without infrastructure. Framework-agnostic. |

## 6. Error Handling Strategy

| Failure Type | Response |
|---|---|
| LLM API fails | Retry 3x with backoff → try fallback model → fail-open (retain Tier 1 findings) |
| Tool binary missing | Skip tool, log warning, continue with available tools |
| Git blame fails | Fall back to configurable default author |
| File read fails | Skip snippet, finding still reported |
| Report PDF fails | Write HTML instead |
| Integration fails | Log error, scan result still returned |
| Circuit breaker open | Skip remaining LLM calls, produce Tier 1-only report |

## 7. Cost Governance

- `--cost-limit <USD>` CLI flag enforced by orchestrator
- Risk scorer gates agent invocation (only high-risk files get agents)
- Per-agent cost tracking exposed in report metadata
- Circuit breaker prevents runaway cost from retries
- Model selection per agent (Sonnet for detection = cost-effective, Opus for validation = precision-critical)
