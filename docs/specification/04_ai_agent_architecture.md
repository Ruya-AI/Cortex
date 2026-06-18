# Document 04: AI Agent Architecture Document

**QA Platform v2**
**Date**: 2026-06-18

---

## 1. Why Agents

Agents are needed where deterministic tools fail: **contextual reasoning** (understanding that `int(user_id)` prevents SQL injection) and **autonomous investigation** (following data flows across files, checking callers, verifying test coverage). These require planning, tool use, and adaptive reasoning — properties tools and single-shot LLM calls lack.

Agents are NOT needed for: running linters, computing risk scores, deduplicating findings, generating reports, posting PR comments. These are deterministic operations with no ambiguity.

## 2. Agent Inventory

| Agent | Cognitive Mode | Scope | Knowledge | Justified By |
|---|---|---|---|---|
| **Correctness** | Constructive: "Does this work?" | Per-file | Project conventions | Execution tracing requires deep investigation |
| **Security** | Adversarial: "How to exploit?" | Per-file + SAST | SAST rules + CWE tree | AgenticSCR: +5.7% from security memory, knowledge interference when mixed with quality |
| **Design** | Evaluative: "How to improve?" | Per-file | Design principles | Different findings than correctness (structure vs behavior), RevAgent: category-specific agents outperform general |
| **Cross-File** | Comparative: "Are these consistent?" | Multi-file | Module boundaries | Per-file agents can't compare N files simultaneously |
| **Validator** | Skeptical: "Is this finding real?" | All findings | FP patterns | RevAgent: critic = most impactful component. 3+1 paper: +10.3pp precision |

## 3. Agent Behavioral Contract

Every detection agent (1-4) follows a three-pass observation-action loop:

**Pass 1 (Scan)**: Read file + diff. Identify candidate issues. Initial tool calls for context.

**Pass 2 (Investigate)**: For each candidate, gather evidence via tool calls (read callers, trace flows, check tests). Strengthen or discard candidates based on evidence.

**Pass 3 (Verify)**: Challenge surviving candidates. "Would a senior engineer flag this?" Suppress unsupported candidates with documented reasoning.

The Validator Agent (5) follows a different loop: for each finding, re-read the code independently, try to REFUTE the finding, assign confidence verdict.

## 4. Tool Access

All agents share 5 read-only tools:

| Tool | Purpose |
|---|---|
| `read_file(path, start?, end?)` | Read file content |
| `grep(pattern, path?, scope?)` | Search for patterns |
| `git_diff(file?, base?)` | View diff |
| `expand_context(file, line, radius)` | Read surrounding code |
| `list_directory(path)` | Explore project structure |

**Constraint**: No write tools exist. Agents physically cannot modify the repository.

**Tool invocation is agent-directed**: The agent decides which tools to call and when, based on its observations. This is the core agentic property — not a predetermined sequence.

## 5. Memory Model

**Semantic memory** (long-term, read-only, loaded at agent start):
- Security Agent: SAST rules (+5.7% improvement) + CWE taxonomy (+4.5%)
- Correctness Agent: Project conventions
- Design Agent: SOLID principles, patterns catalog
- Validator Agent: Common false positive patterns

**Working memory** (transient, per review session):
- File content, tool call results, accumulated findings
- Maintained through LLM conversation context
- Discarded after agent completes

**Episodic memory** (write-once, audit trail):
- Reasoning traces and tool call history
- Stored in audit log for debugging

## 6. Orchestration Model

**Pattern**: Deterministic pipeline with agentic steps. The orchestrator is NOT an agent.

```
Orchestrator (deterministic) controls:
  Phase 2: Agents 1-3 in parallel per file
  Phase 3: Agent 4 conditional
  Phase 4: Agent 5 sequential on all findings
```

**Communication protocol**: Zero direct agent-to-agent communication. Data flows through pipeline only. Detection agents produce findings → orchestrator aggregates → validator receives all.

## 7. Model Strategy

| Agent | Primary | Fallback | Rationale |
|---|---|---|---|
| Correctness | Claude Sonnet | Claude Haiku | Cost-effective for per-file work |
| Security | Claude Sonnet | Claude Haiku | Same |
| Design | Claude Sonnet | Claude Haiku | Same |
| Cross-File | Claude Sonnet | Claude Haiku | Same |
| **Validator** | **Claude Opus** | Claude Sonnet | **Different model prevents correlated errors** (TAP: +17%) |

## 8. Safety Mechanisms

| Mechanism | What It Prevents |
|---|---|
| Fail-open on LLM failure | Silent suppression of real issues |
| Security Agent fail-open | ALL SAST findings retained when LLM fails |
| Validator fail-open | Unvalidated findings marked UNCERTAIN, retained |
| Read-only tools | Agent modification of repository |
| Circuit breaker | Runaway LLM cost from retries |
| Cost limit | Budget overrun |
| Audit log | Unaccountable AI decisions |

## 9. Feedback and Improvement

**Runtime**: Validator suppression rate per agent → signals prompt quality. SAST TP/FP ratio → signals tool configuration.

**Cross-scan**: Developer resolution labels ("Resolved" vs "Won't Fix") → prompt refinement data. Gate override frequency → threshold calibration.

**No automated learning**: All prompt changes are human-reviewed and deployed like code. The platform does not modify its own prompts.
