# Document 12: Coding Agent Instructions

**Cortex QA Platform**
**Date**: 2026-06-18

**Audience**: Autonomous coding agents (Claude, Copilot, or similar)

---

## CRITICAL RULES — Read Before Any Implementation

1. **NEVER write code that modifies the scanned repository.** All agent tools are read-only. All git operations use clones. Reports go to output directory only.

2. **`core/` has ZERO external dependencies.** Only Python stdlib (dataclasses, enum, datetime, re, pathlib). No pydantic, no anthropic, no httpx in `core/`. Exception: Pydantic allowed only in `infrastructure/config_schema.py`.

3. **Dependencies point inward.** `core/` imports from nothing. `infrastructure/` imports from `core/`. `orchestration/` imports from `core/`. Never the reverse.

4. **Every service receives dependencies via constructor.** No service creates its own dependencies. The CLI (`cli/run.py`) is the composition root.

5. **Fail-open on every LLM failure.** LLM fails → retain existing findings with `validation_status=UNVALIDATED`. Never suppress findings due to infrastructure failure.

6. **Agent prompts are in `prompts/*.txt`, not in Python files.** Load at runtime.

7. **Temperature = 0 for all LLM calls.** Hardcoded in LLM client. Not configurable.

---

## Repository Structure

Create this exact directory structure:

```
cortex_engine/
  __init__.py              → exports __version__
  core/
    __init__.py
    finding.py             → Finding dataclass + all enums/value objects
    schemas.py             → ScanRequest, ScanResult, RepositoryContext, ChangeSet, FileSet
    finding_factory.py     → FindingFactory
    finding_line_validator.py
    finding_deduplicator.py
    finding_clusterer.py
    finding_ranker.py
    diff_classifier.py
    author_attributor.py
    snippet_extractor.py
    suppression.py
    finding_manager.py     → orchestrates all 8 steps
    text_sanitizer.py
  agents/
    __init__.py
    base.py                → ReviewAgent ABC
    registry.py            → AgentRegistry
    tool_provider.py       → read-only tools
    memory.py              → SemanticMemoryLoader
    correctness.py
    security.py
    design.py
    cross_file.py
    validator.py
  tools/
    __init__.py
    base.py                → Tier1Tool ABC
    runner.py              → Tier1Runner
    [27 tool files]
  orchestration/
    __init__.py
    orchestrator.py
    review_engine.py
    validation_engine.py
    cost_tracker.py
  assessment/
    __init__.py
    quality_gate.py
    risk_scorer.py
    gate_override.py
  reporting/
    __init__.py
    report_generator.py
    executive_report.py
  integrations/
    __init__.py
    dispatcher.py
    github.py
    linear.py
    slack.py
  infrastructure/
    __init__.py
    git.py
    repository_resolver.py
    change_detector.py
    hygiene_checker.py
    llm_client.py
    config.py
    config_schema.py
    database.py
    finding_repository.py
    scan_repository.py
    audit_logger.py
  knowledge/
    sast_rules.json
    cwe_tree.json
    design_principles.json
  cli/
    __init__.py
    run.py
prompts/
  correctness_agent.txt
  security_agent.txt
  design_agent.txt
  cross_file_agent.txt
  validator_agent.txt
tests/
  unit/
  integration/
  fixtures/
  conftest.py
pyproject.toml
```

---

## Build Order (Execute Strictly in Sequence)

### Step 1: `core/finding.py`

Create these types using `dataclasses` and `enum` (stdlib only):

**Enums**: `Severity` (CRITICAL, HIGH, MEDIUM, LOW, INFO — must support comparison: CRITICAL > HIGH), `Confidence` (CONFIRMED, LIKELY, UNCERTAIN), `FindingCategory` (CORRECTNESS, SECURITY, DESIGN, CONSISTENCY, HYGIENE), `ValidationStatus` (CONFIRMED, LIKELY, UNCERTAIN, SUPPRESSED, UNVALIDATED), `Classification` (INTRODUCED, MODIFIED, PRE_EXISTING, UNCLASSIFIED), `LifecycleState` (OPEN, RESOLVED, SUPPRESSED)

**Dataclasses**: `Evidence` (tool_calls: list[str], code_references: list[str], metrics: dict), `AuthorAttribution` (name: str, email: str, github_username: str|None, attribution_source: str), `Finding` (all fields from Document 05 Section 2, with defaults: id="", cwe=None, author=None, validation_status=UNVALIDATED, lifecycle_state=OPEN)

**Test**: Create Finding instances. Verify Severity comparison. Verify default values.

### Step 2: `core/schemas.py`

Create `ScanRequest`, `ScanResult`, `RepositoryContext`, `ChangeSet`, `FileSet`, `FileChange`, `FileDiff`, `RiskAssessment`, `Tier1RunResult`, `AgentResult`, `AgentReviewResult`, `ValidationResult`, `ProcessedFindings`, `QualityGateResult` as dataclasses.

Use Pydantic ONLY for `ScanRequest` validation if needed. Everything else is plain dataclass.

### Step 3: `core/text_sanitizer.py`

One function: `sanitize(text: str) → str`. Regex: `re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")`. Preserves tab, newline, carriage return.

### Step 4: `infrastructure/config_schema.py` + `infrastructure/config.py`

Pydantic models for full QAConfig. `load_config(repo_path) → QAConfig`. Defaults when absent. Clear error messages on validation failure. `${ENV_VAR}` resolution.

### Step 5: `infrastructure/git.py`

All git subprocess wrappers. `errors="replace"` on every subprocess.run. `get_config()` is SILENT on failure (no warning log — returns empty string). All methods have timeout parameter.

### Step 6-8: Continue through remaining steps per Document 06 Section 3.

---

## Per-Module Behavior Specifications

### `core/finding_factory.py`

`create_from_tool(tool_name, file, start_line, end_line, severity, category, title, explanation, recommendation) → Finding`:
- `start_line = max(1, start_line)`
- `end_line = max(start_line, end_line)`
- `title = title[:120]`
- `suppression_key = f"{tool_name}-{category.value}"`
- `first_seen = last_seen = datetime.now(timezone.utc).isoformat()`
- `id = ""` (assigned later by FindingManager)
- Returns Finding instance

### `core/finding_manager.py`

`process(findings, repo_context, change_set, config) → ProcessedFindings`:
Execute in this EXACT order (never reorder):
1. `FindingLineValidator.validate(findings, repo_path)` — mutates in place
2. `findings = FindingDeduplicator.deduplicate(findings)` — returns new list
3. `DiffClassifier.classify(findings, change_set)` — mutates in place
4. `AuthorAttributor.attribute(findings, repo_context, config)` — mutates in place
5. `SnippetExtractor.extract(findings, repo_path)` — mutates in place
6. `active, suppressed = SuppressionApplicator.apply(findings, config)`
7. `clusters = FindingClusterer.cluster(active)`
8. `active = FindingRanker.rank(active)`
9. Assign IDs: `f"F-{scan_id_short}-{seq:03d}"`
10. Return `ProcessedFindings(active, suppressed, clusters, [], [])`

### `tools/base.py`

`_run_command(cmd, cwd, timeout=60) → tuple[int, str, str]`:
```
try:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return (result.returncode, result.stdout, result.stderr)
except FileNotFoundError:
    return (-1, "", f"Command not found: {cmd[0]}")
except subprocess.TimeoutExpired:
    return (-2, "", f"Command timed out after {timeout}s")
```

### `infrastructure/llm_client.py`

Circuit breaker states: CLOSED (normal, failures increment counter), OPEN (all calls fail immediately), HALF_OPEN (after 60s cooldown, one test call).

Threshold: 5 consecutive failures → OPEN. Success in HALF_OPEN → CLOSED. Failure in HALF_OPEN → OPEN.

Retry: 3 attempts with backoff (1s, 2s, 4s) on rate limit or timeout. Then try fallback models. Then return LLMResponse(success=False).

### `agents/validator.py`

`validate(findings, repo_context) → ValidationResult`:
1. Batch findings into groups of 15
2. For each batch: build prompt with findings, enable tool-use
3. Parse response: per-finding verdict (confirmed/likely/uncertain/suppressed) + reasoning
4. Resolve duplicates: if two findings have same file + overlapping lines + same root cause → merge
5. **On batch LLM failure: ALL findings in batch get validation_status=UNVALIDATED (retained, NOT suppressed)**
6. Return ValidationResult

### `orchestration/orchestrator.py`

`scan(request, progress=None) → ScanResult`:
Never raises. Catches all exceptions internally. Returns ScanResult with `errors` list on partial failure. Cleanup temp clones in `finally` block.

Phase sequence:
1. Load config
2. Resolve repository
3. Detect changes
4. Hygiene check
5. Tier 1 tools
6. Risk scoring
7. IF tiers include 2: agent review (Agents 1-3 parallel per high-risk file)
8. IF tiers include 3 AND (audit OR multi-module): Agent 4 cross-file
9. IF any agent ran: Agent 5 validation
10. Finding management (8 steps)
11. Quality gate
12. Reports
13. Integrations (if configured)
14. Persist to database (if available)
15. Cleanup
16. Return ScanResult

---

## What NOT To Do

- Do NOT import from `core/` into `infrastructure/` at module level creating circular deps
- Do NOT catch bare `except:` — always specify exception types
- Do NOT use `splitlines()` in some places and `\n.split()` in others — use `splitlines()` consistently
- Do NOT truncate text in reports — use CSS word-wrap for PDF
- Do NOT create agents that are just prompt wrappers — agents must use tool-use protocol
- Do NOT suppress findings on LLM failure — always fail-open
- Do NOT use the same LLM model for validator and detection agents
- Do NOT store source code in the database
- Do NOT create global mutable state
- Do NOT add web framework, message queue, or microservice infrastructure
- Do NOT write to the scanned repository under any circumstances
