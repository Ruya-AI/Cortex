# Document 07: API Design Guidelines

**QA Platform v2**
**Date**: 2026-06-18

---

## 1. Internal Interface Contracts

The platform has no external REST API. All interfaces are internal Python abstractions.

### Universal Contract: Finding Schema

The Finding schema is the central data contract. Every component operates on it. Changes to this schema affect every component and must be versioned.

```
Finding:
  id: str                          # Assigned by FindingManager
  source: str                      # Producer name
  tier: int                        # 1, 2, or 3
  category: FindingCategory        # CORRECTNESS | SECURITY | DESIGN | CONSISTENCY | HYGIENE
  severity: Severity               # CRITICAL | HIGH | MEDIUM | LOW | INFO
  confidence: Confidence           # CONFIRMED | LIKELY | UNCERTAIN
  classification: Classification   # INTRODUCED | MODIFIED | PRE_EXISTING | UNCLASSIFIED
  file: str                        # Relative path
  start_line: int                  # 1-based, clamped
  end_line: int                    # >= start_line, clamped
  title: str                       # Max 120 chars
  explanation: str                 # Full text
  evidence: Evidence               # Supporting data
  recommendation: str              # Full text, never truncated
  cwe: str | None                  # Security findings only
  author: AuthorAttribution | None
  code_under_review: str           # Snippet with markers
  validation_status: ValidationStatus
  validation_reasoning: str
  suppression_key: str
  lifecycle_state: LifecycleState
  first_seen: datetime
  last_seen: datetime
  related_findings: list[str]
  root_cause_cluster: str | None
```

## 2. Tool Interface

```
Tier1Tool (abstract):
  name: str
  is_available() → bool
  is_applicable(file_path: str) → bool
  run(file_path: str, repo_path: Path) → list[Finding]
```

**Contract**: `run()` must return findings using `FindingFactory`. Must handle its own errors internally (return empty list on failure, never raise). Must not modify any file. Must respect timeout.

## 3. Agent Interface

```
ReviewAgent (abstract):
  name: str
  tier: int
  category: FindingCategory
  cognitive_mode: str

  review_file(context: FileReviewContext) → AgentResult
  review_file_group(context: FileGroupReviewContext) → AgentResult
  get_system_prompt() → str
  get_semantic_memory() → list[MemoryDocument]
```

**Contract**: `review_file()` must return `AgentResult` (never raise). On LLM failure, return AgentResult with empty findings and error message. Security Agent must retain SAST findings on failure.

## 4. Integration Interface

```
IntegrationTarget (abstract):
  is_configured() → bool
  dispatch(findings, gate_result, scan_metadata, config) → IntegrationResult
```

**Contract**: `dispatch()` must handle its own errors (never crash the pipeline). Return IntegrationResult with status and error details.

## 5. LLM Client Interface

```
LLMClient (abstract):
  call(system_prompt: str, user_message: str,
       output_schema: dict | None, model: str | None) → LLMResponse
  total_cost: float
  total_tokens: tuple[int, int]
  call_count: int
```

**Contract**: `call()` handles retry, backoff, fallback, and circuit breaker internally. Returns `LLMResponse` with `success=False` on exhausted retries (never raises). Tracks cost automatically.

## 6. Repository Interfaces

```
FindingRepository (abstract):
  save_findings(scan_id: str, findings: list[Finding]) → None
  get_findings_by_scan(scan_id: str) → list[Finding]
  get_findings_by_file(file_path: str, limit: int) → list[Finding]
  update_lifecycle_state(finding_id: str, state: LifecycleState) → None

ScanRepository (abstract):
  save_scan(scan: ScanRecord) → None
  get_scan(scan_id: str) → ScanRecord | None
  list_scans(repo: str, limit: int) → list[ScanRecord]
```

## 7. CLI Contract

```
qa run --repo <path|url>
       --branch <branch>
       --commit <sha>
       --pr <number|url>
       --vs <base_branch>
       --tiers <1,2,3>
       --agents <name,name>
       --audit
       --full
       --report <json,pdf>
       --output <dir>
       --post-comment
       --github-token <token>
       --cost-limit <usd>
       --dry-run
```

**Exit codes**: 0 = gate pass, 1 = gate fail, 2 = scan error

## 8. Output Contract: Reports

**Full report JSON**: Object with 11 keys matching FR-22: `report_metadata`, `repository_context`, `attribution`, `scope_summary`, `executive_summary`, `findings`, `finding_clusters`, `resolved_issues`, `positive_observations`, `suppressed_findings`, `appendix`

**Executive report JSON**: Object with: `report_id`, `risk`, `total`, `actionable`, `must_fix_count`, `should_fix_count`, `consider_count`, `noise_removed`, `items` (action items with full text), `categories`, `exclusion_reasons`
