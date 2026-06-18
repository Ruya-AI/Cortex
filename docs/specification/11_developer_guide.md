# Document 11: Developer Implementation Guide

**QA Platform v2**
**Date**: 2026-06-18

---

## 1. Architecture Rules

1. **Dependencies point inward**: `core/` has zero external deps. Infrastructure implements core interfaces. Never import from outer layers into inner layers.
2. **No service creates its own dependencies**: Constructor injection everywhere. CLI is the composition root.
3. **No shared mutable state**: Each scan is independent. No globals. No singletons (except logger).
4. **Every external call has a timeout**: subprocess (60s), git clone (300s), LLM (120s), HTTP API (30s).
5. **Fail-open on LLM failure**: Retain findings, never suppress.

## 2. Coding Standards

- Python 3.11+, `from __future__ import annotations` in every file
- Type hints on ALL public method signatures
- No docstrings by default — clear names + types instead
- No comments unless WHY is non-obvious
- `ruff` for linting, zero warnings
- `pytest` for testing
- One class per file for domain entities

## 3. Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Files | snake_case | `finding_manager.py` |
| Classes | PascalCase | `FindingManager` |
| Methods | snake_case | `process_findings()` |
| Constants | UPPER_SNAKE | `MAX_TITLE_LENGTH` |
| Enums | PascalCase.UPPER_SNAKE | `Severity.CRITICAL` |
| Tests | test_what_condition_expected | `test_dedup_same_line_merges()` |

## 4. Implementation Order (20 Steps)

| Step | What | Key Files | Test |
|---|---|---|---|
| 1 | Core domain models | `core/finding.py`, `core/schemas.py` | Unit: types instantiate correctly |
| 2 | Configuration | `infrastructure/config_schema.py`, `infrastructure/config.py` | Unit: valid/invalid/missing config |
| 3 | Git operations | `infrastructure/git.py`, `repository_resolver.py`, `change_detector.py`, `hygiene_checker.py` | Integration: fixture repo |
| 4 | Finding processing | `core/finding_factory.py`, all 8 processing step files, `core/finding_manager.py` | Unit: each step independently |
| 5 | Tier 1 tool interface + 5 tools | `tools/base.py`, `tools/runner.py`, ruff/bandit/mypy/semgrep/radon | Integration: real tools |
| 6 | Risk scorer + quality gate | `assessment/risk_scorer.py`, `assessment/quality_gate.py` | Unit: scoring formula, gate modes |
| 7 | Report generators | `reporting/report_generator.py`, `reporting/executive_report.py` | Snapshot: fixed input → expected output |
| 8 | Scan orchestrator (Tier 1 only) | `orchestration/orchestrator.py` | Integration: end-to-end scan |
| 9 | CLI entry point | `cli/run.py` | Integration: CLI command produces output |
| 10 | Integrations | `integrations/dispatcher.py`, github/linear/slack | Unit: mock HTTP |
| 11 | Persistence | `infrastructure/database.py`, repositories, audit_logger | Unit: CRUD operations |
| 12 | Remaining 22 Tier 1 tools | One file per tool | Unit per tool |
| 13 | LLM client | `infrastructure/llm_client.py` | Unit: circuit breaker, fallback |
| 14 | Agent infrastructure | `agents/base.py`, registry, tool_provider, memory | Unit: registry, tools |
| 15 | Knowledge bases | `knowledge/sast_rules.json`, `knowledge/cwe_tree.json` | Validate JSON schema |
| 16 | Agent implementations | 5 agents + 5 prompts | Integration: fixture repos |
| 17 | Agentic engines | `orchestration/review_engine.py`, `orchestration/validation_engine.py` | Integration: real agents |
| 18 | Wire agents into orchestrator | Modify orchestrator for Tier 2+3 | Integration: full pipeline |
| 19 | Production hardening | Logging, benchmarks, fail-open tests, audit-only test | All verification suites |
| 20 | Packaging + documentation | pyproject.toml, Dockerfile, README, INSTALL, ARCHITECTURE | Packaging test |

## 5. Testing Strategy

| Type | Location | What | How |
|---|---|---|---|
| Unit | `tests/unit/` | Core logic (pure functions) | NO mocks for core. Real Finding instances. |
| Integration | `tests/integration/` | Tools, git, pipeline, reports | Fixture repos. Real tool binaries (skip if missing). |
| Agent | `tests/integration/agents/` | Agent quality | Real LLM (slow) + mock LLM (fast CI). Fixture repos with known issues. |
| Workflow | `tests/integration/workflows/` | End-to-end scenarios | Full pipeline: PR review, audit, cost limit, gate modes |

## 6. Common Mistakes to Avoid

1. **Importing core from infrastructure** → circular dependency
2. **Hardcoding prompts in Python** → prevents editing without code changes
3. **Bare except** → hides bugs
4. **Inconsistent line counting** → use splitlines() everywhere
5. **Modifying findings outside FindingManager** → inconsistent state
6. **Warning logs for expected conditions** → use debug level
7. **Truncating text in reports** → use word-wrap CSS
8. **Writing to scanned repo** → violates audit-only
9. **Prompt-wrapper agents** → must use tool-use protocol
10. **Suppressing on LLM failure** → must fail-open
11. **Same model for validator and detection** → must use different models
12. **Adding agents without capability boundary justification** → agent sprawl
13. **Making orchestrator an agent** → it's deterministic pipeline control
14. **Storing source code in database** → privacy risk
15. **Services creating own dependencies** → violates DI

## 7. Extension Points

| Extend | Mechanism | Implement |
|---|---|---|
| New Tier 1 tool | Tier1Tool interface | `is_available()`, `is_applicable()`, `run()` |
| New agent | ReviewAgent interface + AgentRegistry | `review_file()`, `get_system_prompt()`, `get_semantic_memory()` |
| New integration | IntegrationTarget interface | `is_configured()`, `dispatch()` |
| New report format | Add rendering method | `_render_<format>(report_data)` |
| Customize prompts | Edit text files | `prompts/*.txt` — no code changes |
| New knowledge | Add JSON file | Update SemanticMemoryLoader |
