# Document 06: Class-Level Design Documentation

**QA Platform v2**
**Date**: 2026-06-18

---

## 1. Core Classes

### FindingFactory
- **Purpose**: Create validated Finding instances
- **Methods**: `create_from_tool(tool_name, file, start_line, end_line, severity, category, title, explanation, recommendation) → Finding` / `create_from_agent(agent_name, tier, category, ..., cwe?) → Finding`
- **Validation**: Clamps start_line ≥ 1, end_line ≥ start_line. Truncates title to 120 chars. Sets first_seen/last_seen to UTC now. Assigns suppression_key. Leaves id empty.
- **Dependencies**: `Finding` entity only (core)

### FindingManager
- **Purpose**: Execute all 8 processing steps in order
- **Method**: `process(findings, repo_context, change_set, config) → ProcessedFindings`
- **Step order** (invariant — never reorder): (1) LineValidator (2) Deduplicator (3) DiffClassifier (4) AuthorAttributor (5) SnippetExtractor (6) SuppressionApplicator (7) Clusterer (8) Ranker → assign IDs
- **Dependencies**: All 8 processing step classes
- **Pattern**: Pipeline

### QualityGate
- **Purpose**: Evaluate findings against thresholds
- **Method**: `evaluate(findings, config) → QualityGateResult`
- **Behavior**: Counts findings by severity (filtered by min confidence). Shadow mode → always pass (log only). Advisory → warn. Enforced → fail. Checks for valid override.
- **Dependencies**: None (pure function on in-memory data)
- **Pattern**: Strategy (gate mode determines behavior)

## 2. Infrastructure Classes

### AnthropicLLMClient
- **Purpose**: Managed Claude API interface with reliability
- **Method**: `call(system_prompt, user_message, output_schema?, model?) → LLMResponse`
- **Behavior**: Circuit breaker check → try primary model → retry 3x with backoff on transient failures → try fallback models → return failure if all exhausted. Tracks tokens/cost per call. Temperature=0.
- **State**: `_consecutive_failures`, `_total_cost`, `_total_tokens`, `_call_count`
- **Dependencies**: `anthropic` SDK
- **Pattern**: Circuit breaker + retry + fallback chain

### GitOperations
- **Purpose**: Git subprocess wrapper
- **Methods**: `clone()`, `diff()`, `blame()`, `log()`, `get_config()` (silent on failure), `get_current_branch()`, `get_current_commit()`
- **All methods**: `errors="replace"` for Unicode, configurable timeout
- **Dependencies**: `subprocess` (stdlib), `git` binary

### YAMLConfigManager
- **Method**: `load(repo_path) → QAConfig`
- **Behavior**: Read `.qa-config.yml`, validate with Pydantic, return defaults if absent, resolve `${ENV_VAR}` references
- **Dependencies**: `pyyaml`, `pydantic`

## 3. Agent Classes

### CorrectnessAgent (extends ReviewAgent)
- **Properties**: `name="correctness"`, `tier=2`, `category=CORRECTNESS`, `cognitive_mode="constructive"`
- **Method**: `review_file(context) → AgentResult`
- **Behavior**: Load prompt from file → load memory → build message with file+diff+findings → LLM call with tool-use → agent decides tools → parse structured output → return findings
- **Fail mode**: Empty findings, error logged

### SecurityAgent (extends ReviewAgent)
- **Properties**: `name="security"`, `tier=2`, `category=SECURITY`, `cognitive_mode="adversarial"`
- **Special**: Receives SAST findings as primary input. Validates each as TP/FP. Classifies by CWE.
- **Fail-open**: If LLM fails, ALL SAST findings returned as-is with status=UNVALIDATED
- **Memory**: SAST rules (+5.7%) + CWE tree (+4.5%)

### DesignAgent (extends ReviewAgent)
- **Properties**: `name="design"`, `tier=2`, `category=DESIGN`, `cognitive_mode="evaluative"`
- **Special**: Produces improvement suggestions, not bug reports. Each includes what/why/example.

### CrossFileAgent (extends ReviewAgent)
- **Properties**: `name="cross_file"`, `tier=3`, `category=CONSISTENCY`, `cognitive_mode="comparative"`
- **Method**: `review_file_group(context) → AgentResult`
- **Condition**: Only runs on audits or when changes span 3+ modules

### ValidatorAgent (extends ReviewAgent)
- **Properties**: `name="validator"`, `cognitive_mode="skeptical"`
- **Method**: `validate(findings, repo_context) → ValidationResult`
- **Behavior**: Batch findings (size 15) → for each: re-read code, try to REFUTE, assign verdict → resolve semantic duplicates → return validated findings
- **Model**: Opus (different from detection agents)
- **Fail-open**: All findings in failed batch marked UNVALIDATED, retained

## 4. Engine Classes

### AgenticReviewEngine
- **Method**: `run(repo_context, high_risk_files, tier1_result, config, request) → AgentReviewResult`
- **Behavior**: Get agents from registry → load memory → for each file: execute agents 1-3 in parallel → collect findings → if cross-file warranted: execute agent 4 → check cost limit per file → aggregate results
- **Dependencies**: AgentRegistry, AgentToolProvider, SemanticMemoryLoader, LLMClient, CostTracker

### ValidationEngine
- **Method**: `validate(all_findings, repo_context) → ValidationResult`
- **Behavior**: Batch findings by 15 → invoke ValidatorAgent per batch → collect verdicts → fail-open for failed batches
- **Dependencies**: ValidatorAgent, LLMClient (Opus)

## 5. Design Patterns Used

| Pattern | Class | Purpose |
|---|---|---|
| Pipeline | FindingManager, ScanOrchestrator | Sequential phase execution |
| Strategy | Tier1Tool, ReviewAgent, IntegrationTarget | Pluggable implementations |
| Registry | AgentRegistry | Decouple discovery from orchestration |
| Factory | FindingFactory | Validated entity creation |
| Circuit Breaker | AnthropicLLMClient | Prevent cascading LLM failures |
| Facade | ScanOrchestrator.scan() | Single entry point to complex subsystem |
| Repository | FindingRepository, ScanRepository | Abstract persistence |
| Dependency Injection | All services | Constructor injection, no self-creation |
| Template Method | Tier1Runner.run() | Skeleton with delegated tool-specific logic |
| Observer | IntegrationDispatcher | Notify multiple targets |
