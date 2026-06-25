# Cortex QA Platform — Agentic Architecture Specification

**Document Type**: AI Agent System Design
**Status**: Design — No Implementation
**Date**: 2026-06-18
**Author Role**: AI Systems Architect
**Input**: Architecture Design (02), Domain Design (03), Research Papers (7)

---

# 1. Agent System Overview

## 1.1 Why Agents Are Needed

Deterministic static analysis tools (Tier 1) provide broad coverage but lack two capabilities that code quality demands:

**Contextual reasoning**: A SAST tool can flag `user_id` near a SQL query. Only an agent can trace the data flow, observe that `int(user_id)` casts the input to an integer, and conclude the SQL injection is unexploitable — a false positive. SAST-Genius (IEEE S&P 2025) demonstrated this raises precision from 35.7% to 89.5%.

**Autonomous investigation**: A linter reports high complexity at line 50. Only an agent can read the function, open its callers, check whether tests exist, trace error handling paths, and produce a finding that says: "This function has a resource leak on the error path at line 67 because the database connection opened at line 52 is not closed when the validation at line 58 raises ValueError." This requires multiple tool calls driven by observation — the agent decides what to investigate next based on what it discovers.

These two capabilities — reasoning about code semantics and autonomously navigating a codebase to gather evidence — define where agents provide value that deterministic tools and single-shot LLM calls cannot.

## 1.2 Where Agents Are NOT Needed

The platform deliberately restricts agentic behavior to tasks that require it:

| Task | Agentic? | Why |
|---|---|---|
| Running linters and SAST tools | No | Deterministic execution — no reasoning needed |
| Computing risk scores | No | Heuristic formula — pure computation |
| Deduplicating findings | No | Algorithmic matching — deterministic |
| Attributing authors via git blame | No | Data lookup — no judgment required |
| Evaluating quality gate thresholds | No | Boolean logic — no ambiguity |
| Generating reports | No | Template-driven transformation — no exploration |
| Posting PR comments | No | API call — no decision-making |
| Reviewing code for correctness | **Yes** | Requires execution tracing, tool-driven investigation |
| Validating SAST findings | **Yes** | Requires contextual reasoning about exploitability |
| Evaluating design quality | **Yes** | Requires structural judgment against principles |
| Comparing code across files | **Yes** | Requires holding multiple files in comparative context |
| Challenging findings adversarially | **Yes** | Requires independent skeptical reasoning |

## 1.3 Agent Responsibilities vs Pipeline Responsibilities

| Responsibility | Owner | Rationale |
|---|---|---|
| Decide WHAT to investigate in a file | Agent | Requires observation and planning |
| Decide WHICH tools to call | Agent | Driven by what agent observes |
| Decide WHETHER a finding is valid | Agent (Validator) | Requires adversarial reasoning |
| Decide WHICH files to scan | Pipeline (Orchestrator) | Deterministic — based on diff and risk score |
| Decide WHEN agents run | Pipeline (Orchestrator) | Deterministic — based on tier config |
| Decide HOW findings are ranked | Pipeline (Finding Manager) | Algorithmic — severity × confidence |
| Decide IF the gate passes | Pipeline (Quality Gate) | Threshold logic — no judgment |

## 1.4 Autonomous vs Controlled Actions

**Agents have autonomy over**:
- Tool invocation order and selection (which files to read, what to grep for)
- Investigation depth (how many tool calls to make per candidate issue)
- Finding production (whether observed code warrants a finding)
- Self-verification (whether to suppress a candidate in Pass 3)

**Agents do NOT have autonomy over**:
- Which files to review (orchestrator decides based on risk score)
- Which agents run (orchestrator decides based on tier configuration)
- Finding severity assignment (agents propose, but can't exceed the severity rubric)
- Quality gate decisions (deterministic threshold evaluation)
- Code modification (physically impossible — no write tools exist)

This boundary between agent autonomy and pipeline control follows the "safe autonomy" principle: agents reason freely within a bounded sandbox, but structural decisions (what runs, what blocks, what ships) are deterministic.

---

# 2. Agent Specifications

## 2.1 Agent 1: Correctness Agent

### Identity
| Field | Value |
|---|---|
| **Name** | `correctness` |
| **Mission** | Protect developers from shipping logic bugs, edge case failures, and error handling deficiencies by detecting issues that deterministic tools cannot find |
| **Primary Objective** | For each file under review, identify correctness issues through execution path tracing, produce findings with evidence gathered through autonomous code exploration, and recommend concrete fixes |

### Capabilities
1. **Execution path tracing**: Follow code logic step-by-step through branches, loops, and function calls to identify paths that produce incorrect results
2. **Null/boundary analysis**: Identify inputs that are unchecked (null, empty, negative, overflow) and trace what happens when they reach downstream code
3. **Error path verification**: Check that error conditions are handled correctly — resources cleaned up, errors propagated, fallbacks invoked
4. **Race condition detection**: Identify shared mutable state accessed without synchronization
5. **Type/contract verification**: Check that function contracts (preconditions, postconditions, invariants) are satisfied by callers and implementations

### Reasoning Responsibilities
The agent reasons in three passes:

**Pass 1 — Scan**: Read the file and diff. Identify candidate issues based on code patterns: unchecked returns, missing null guards, complex branching, error-prone operations (file I/O, parsing, casting).

**Pass 2 — Investigate**: For each candidate, gather evidence through tool calls:
- Read the called function to understand its contract
- Grep for other callers to see how they handle the same case
- Check if tests cover the edge case
- Read error handling code to verify cleanup

The agent decides which tools to call based on what each candidate requires. A null-handling candidate triggers reading the function that returns the potentially-null value. A resource leak candidate triggers tracing the resource lifecycle (open → use → close on all paths).

**Pass 3 — Verify**: Challenge each surviving candidate:
- "Is there a guard I missed earlier in the call chain?"
- "Is this intentional behavior documented in comments?"
- "Would a senior engineer on this team flag this, or is this an accepted pattern?"

Candidates that fail verification are suppressed with documented reasoning.

### Available Tools
| Tool | When Agent Uses It |
|---|---|
| `read_file(path, start?, end?)` | To read imported modules, callers, test files, configuration |
| `grep(pattern, path?, scope?)` | To find all callers of a function, all usages of a variable, all error handling patterns |
| `git_diff(file?)` | To understand what specifically changed (focus review on changes) |
| `expand_context(file, line, radius)` | To read surrounding code when investigating a specific line |
| `list_directory(path)` | To understand project structure when navigating to related files |

### Input Context
```
FileReviewContext:
  file_path: str              — Relative path of the file under review
  file_content: str           — Full content of the file
  diff_content: str | None    — Diff hunks for this file (None in audit mode)
  tier1_findings: Finding[]   — Tier 1 findings for this file (complexity, type errors, etc.)
  semantic_memory: MemoryDocument[] — Project coding conventions
  repository_path: Path       — Root path for tool invocations
```

### Output Format
```json
{
  "findings": [
    {
      "file": "src/api/users.py",
      "start_line": 42,
      "end_line": 48,
      "severity": "high",
      "title": "Unchecked null return from get_user() causes IndexError",
      "explanation": "get_user(user_id) returns None when user is not found (verified by reading src/db/queries.py:67). The caller at line 45 accesses result.name without null check. When user_id does not exist in the database, this raises AttributeError in production.",
      "evidence": {
        "tool_calls": [
          "read_file('src/db/queries.py', 60, 75) — confirmed get_user returns None on miss",
          "grep('get_user', scope='src/') — found 3 other callers, all check for None"
        ],
        "code_references": ["src/db/queries.py:67 — return None"]
      },
      "recommendation": "Add null check: if result is None: return Response(status=404, body={'error': 'User not found'})"
    }
  ]
}
```

### Memory Requirements

**Semantic memory** (loaded at agent start, read-only):
- Project coding conventions from `.qa-config.yml` knowledge_base
- Language-specific idioms and common pitfalls (bundled per language)

**Working memory** (maintained during review session):
- Current file content and diff
- Accumulated findings from current review
- Tool call results (expanded code, grep results)
- Maintained implicitly through LLM conversation context

**Episodic memory** (write-once, for audit trail):
- Complete reasoning trace and tool call history
- Persisted to audit log after agent completes

### Knowledge Sources
| Source | Content | Loading |
|---|---|---|
| Project conventions | Coding standards, naming patterns, error handling policy | From `.qa-config.yml` `knowledge_base.conventions_path` |
| Language idioms | Python: common pitfalls (mutable defaults, late binding). JS: async/await traps. Go: goroutine leaks. | Bundled JSON files per language |
| Tier 1 findings | Complexity scores, type checker errors, linter warnings for this file | Passed as structured input in FileReviewContext |

### Decision Process
```
FOR EACH candidate issue identified in Pass 1:

  1. EVIDENCE GATHERING (Pass 2):
     Does this candidate have supporting evidence?
     │
     ├─ YES: Tool calls confirmed the issue
     │       → Proceed to verification
     │
     └─ NO: Tool calls show the code is actually safe
            → SUPPRESS with reasoning: "Evidence shows [X] handles this case"

  2. VERIFICATION (Pass 3):
     Would a competent engineer consider this a real issue?
     │
     ├─ YES: Clear bug with concrete impact
     │       → PRODUCE finding with evidence + recommendation
     │
     ├─ UNCERTAIN: Might be intentional, unclear context
     │       → PRODUCE finding with confidence=UNCERTAIN, note ambiguity
     │
     └─ NO: Intentional pattern, acceptable tradeoff
            → SUPPRESS with reasoning: "Pattern is consistent with [X]"
```

### Failure Handling
| Failure | Response |
|---|---|
| LLM call fails (API error, timeout) | Return empty findings list. Tier 1 findings for this file are retained by the pipeline. Log error. |
| LLM returns malformed JSON | Retry once with explicit format instruction. If retry fails → return empty findings. |
| Tool call fails (file not found, grep error) | Agent continues with available information. Notes tool failure in reasoning. |
| Token budget exceeded | Agent produces findings from completed passes only. Notes incomplete review. |
| Circuit breaker open | Agent is skipped entirely. Tier 1 findings retained. |

### Human Escalation Rules
| Condition | Action |
|---|---|
| Agent identifies a critical-severity issue | Finding goes through normal pipeline. No special escalation — quality gate handles blocking. |
| Agent is uncertain about a finding | Produces finding with `confidence=UNCERTAIN`. Validator may upgrade or suppress. Developer makes final call. |
| Agent detects a pattern it can't classify | Produces finding with `severity=INFO` and explanation of what it observed. Developer evaluates. |

---

## 2.2 Agent 2: Security Agent

### Identity
| Field | Value |
|---|---|
| **Name** | `security` |
| **Mission** | Eliminate false positive noise from SAST tools while ensuring real vulnerabilities are identified, classified, and accompanied by remediation guidance |
| **Primary Objective** | Validate each SAST finding as true positive or false positive through taint path tracing and contextual analysis. For true positives: classify by CWE and provide remediation. For own discoveries beyond SAST: provide strong evidence. |

### Capabilities
1. **SAST finding validation**: Read a SAST finding, trace the data flow it describes, determine if the vulnerability is exploitable in context
2. **Taint path tracing**: Follow user-controlled input from source (request parameter, file read, environment variable) through transformations to sink (SQL query, file write, shell command, HTML output)
3. **Sanitization verification**: Check whether input passes through sanitization that neutralizes the specific attack vector (not just any sanitization — the RIGHT sanitization for the attack type)
4. **CWE classification**: Map confirmed vulnerabilities to the CWE taxonomy using hierarchical reasoning (from general category like "Improper Input Validation" to specific type like "SQL Injection")
5. **Remediation recommendation**: Suggest specific fixes using the vulnerability type's standard remediation (parameterized queries for SQLi, output encoding for XSS, etc.)

### Reasoning Responsibilities

The agent's reasoning follows the **adversarial cognitive mode**: "How could an attacker exploit this code?"

**For each SAST finding**:
1. Read the flagged code and understand what the SAST tool detected
2. Trace the data flow: Where does the input come from? What transformations does it undergo? Where does it end up?
3. Check for sanitization: Is there input validation, type casting, encoding, or parameterization between source and sink?
4. Assess exploitability: Given the actual data flow, can an attacker construct an input that reaches the sink in a dangerous form?
5. Verdict: True Positive (with CWE + remediation) or False Positive (with documented reasoning)

**Beyond SAST** (own discoveries):
The agent may identify security issues that SAST didn't flag — but only when the evidence is strong (observed in code through tool calls, not speculated). Examples: missing authentication decorators, hardcoded credentials, insecure default configurations.

### Available Tools
Same as Correctness Agent: `read_file`, `grep`, `git_diff`, `expand_context`, `list_directory`

Additionally receives: **Structured SAST findings** as part of input context (not as a tool, but as data).

### Input Context
```
FileReviewContext:
  file_path: str
  file_content: str
  diff_content: str | None
  tier1_findings: Finding[]   — SAST findings (bandit, semgrep, gitleaks) are the PRIMARY input
  semantic_memory: MemoryDocument[]  — SAST rules + CWE taxonomy
  repository_path: Path
```

### Output Format
```json
{
  "findings": [
    {
      "file": "src/api/users.py",
      "start_line": 67,
      "end_line": 67,
      "severity": "critical",
      "title": "SQL injection via unsanitized user input in query builder",
      "explanation": "User-controlled input from request.params['filter'] is concatenated directly into a SQL query string at line 67. No parameterization or sanitization is applied. Verified by reading the query builder at src/db/query_builder.py:23 which uses string formatting.",
      "evidence": {
        "tool_calls": [
          "read_file('src/db/query_builder.py', 20, 30) — confirmed string concatenation",
          "grep('sanitize', scope='src/api/') — no sanitization found in request path"
        ],
        "code_references": ["src/db/query_builder.py:23 — f\"SELECT * FROM {table} WHERE {filter_clause}\""]
      },
      "recommendation": "Replace string concatenation with parameterized query: cursor.execute('SELECT * FROM users WHERE ?', (filter_value,))",
      "cwe": "CWE-89"
    },
    {
      "file": "src/api/users.py",
      "start_line": 45,
      "end_line": 45,
      "severity": "info",
      "title": "SAST false positive: SQL injection mitigated by integer casting",
      "explanation": "Semgrep flagged user_id near a database query. However, user_id is cast to int() at line 43, which prevents SQL injection payload (requires string characters). The integer-only value cannot contain SQL syntax.",
      "validation_status": "suppressed",
      "validation_reasoning": "Type casting to int() provides implicit sanitization against SQL injection. The taint path passes through int() before reaching the query."
    }
  ]
}
```

### Memory Requirements

**Semantic memory** (critical — evidence shows +5.7% improvement from SAST rules, +4.5% from CWE tree):

**SAST Rules Document** — Structured JSON with:
```
[
  {
    "rule_id": "python.lang.security.audit.formatted-sql",
    "cwe_id": "CWE-89",
    "cwe_name": "SQL Injection",
    "severity": "critical",
    "description": "User input used in SQL string formatting",
    "vulnerable_example": "cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')",
    "secure_example": "cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
    "detection_indicators": ["string format", "f-string", "% operator", ".format()", "concatenation"],
    "remediation_steps": ["Use parameterized queries", "Use ORM query builder", "Validate input type"]
  }
]
```

**CWE Taxonomy Tree** — Hierarchical JSON:
```
{
  "CWE-20": {
    "name": "Improper Input Validation",
    "children": {
      "CWE-89": {"name": "SQL Injection", "parent": "CWE-20"},
      "CWE-79": {"name": "Cross-site Scripting", "parent": "CWE-20"},
      "CWE-78": {"name": "OS Command Injection", "parent": "CWE-20"}
    }
  }
}
```

### Decision Process
```
FOR EACH SAST finding in tier1_findings:

  1. UNDERSTAND: What did the SAST tool detect?
     Read the finding's rule, severity, and location.

  2. TRACE: Follow the data flow.
     → read_file() to see the source (where input comes from)
     → read_file() to see the sink (where input ends up)
     → grep() to find any sanitization between source and sink

  3. ASSESS EXPLOITABILITY:
     │
     ├─ Input reaches sink WITHOUT sanitization
     │   → TRUE POSITIVE
     │   → Classify by CWE using taxonomy tree
     │   → Generate remediation from SAST rules
     │
     ├─ Input is sanitized but sanitization is INSUFFICIENT for this attack type
     │   → TRUE POSITIVE (with explanation of why sanitization fails)
     │
     ├─ Input is sanitized CORRECTLY for this attack type
     │   → FALSE POSITIVE
     │   → Document: "[sanitization function] at line [X] neutralizes [attack type]"
     │
     └─ Data flow is unclear / cannot determine
            → RETAIN finding with confidence=UNCERTAIN
            (Fail-open: when in doubt, keep the finding)
```

### Failure Handling
| Failure | Response |
|---|---|
| LLM call fails | **ALL SAST findings for this file are returned as-is** with `validation_status=UNVALIDATED`. This is the critical fail-open behavior — the agent never silently suppresses SAST findings on failure. |
| Tool call fails | Agent continues with available information. Cannot verify → retains finding as UNCERTAIN. |
| CWE classification ambiguous | Uses the highest-level matching CWE category. Notes ambiguity. |

### Human Escalation Rules
| Condition | Action |
|---|---|
| Critical vulnerability confirmed | Finding enters normal pipeline. Quality gate handles blocking. If Linear integration enabled, ticket is auto-created. |
| Agent suppresses a SAST finding as FP | Suppression reasoning is documented in finding's `validation_reasoning`. Security engineer can audit suppression decisions via report. |
| Agent cannot determine exploitability | Finding retained with `confidence=UNCERTAIN`. Security engineer reviews in report. |

---

## 2.3 Agent 3: Design & Improvement Agent

### Identity
| Field | Value |
|---|---|
| **Name** | `design` |
| **Mission** | Help developers write better code by identifying structural improvements, maintainability issues, and design opportunities that go beyond "does it work" |
| **Primary Objective** | Evaluate code structure against engineering principles and produce concrete improvement suggestions with clear rationale and examples |

### Capabilities
1. **Structural assessment**: Evaluate function/class size, parameter count, nesting depth, responsibility count against established thresholds
2. **SOLID evaluation**: Check for single responsibility violations, interface segregation issues, dependency inversion opportunities
3. **Coupling analysis**: Identify tight coupling between modules, inappropriate dependencies, missing abstractions
4. **Naming assessment**: Evaluate whether names accurately describe behavior, follow conventions, and are consistent
5. **Test adequacy assessment**: Check if the changed code has corresponding tests, and whether those tests cover meaningful scenarios
6. **Documentation gap detection**: Identify public APIs, complex logic, or non-obvious behavior lacking documentation

### Reasoning Responsibilities

The agent operates in **evaluative mode**: "How can this code be better?"

This is fundamentally different from correctness (does it work?) and security (can it be exploited?). The design agent looks at structure, not behavior.

**Pass 1 — Structural scan**: Assess code structure metrics — function length, parameter count, nesting depth, import count, class method count. Identify areas that exceed reasonable thresholds.

**Pass 2 — Pattern assessment**: For each structural concern, investigate deeper:
- Is this function doing multiple things? (Read the function, identify distinct responsibilities)
- Is this class coupled to too many other classes? (Count imports, check dependency directions)
- Is this naming accurate? (Compare function name to what the function actually does)
- Are there tests? (Grep for test files, check coverage)

**Pass 3 — Improvement recommendation**: For each confirmed issue, produce a concrete suggestion:
- What exactly should change
- Why it improves the code (reduced complexity, better testability, clearer intent)
- What the improved structure looks like (brief example, not a full rewrite)

### Input Context
Same structure as Correctness Agent. Tier 1 findings of interest: complexity scores (radon), style warnings (ruff), documentation gaps.

### Output Format
```json
{
  "findings": [
    {
      "file": "src/api/users.py",
      "start_line": 15,
      "end_line": 89,
      "severity": "medium",
      "title": "Function handle_request has 3 responsibilities — split recommended",
      "explanation": "handle_request() performs input validation (lines 18-32), business logic (lines 34-65), and response formatting (lines 67-89). This violates single responsibility principle and makes the function difficult to test in isolation. Cyclomatic complexity is 7 (from Tier 1 radon analysis).",
      "evidence": {
        "tool_calls": [
          "grep('def test_handle_request', scope='tests/') — only 1 test found, covering happy path only"
        ],
        "code_references": ["Lines 18-32: validation block", "Lines 34-65: business logic block", "Lines 67-89: response formatting block"]
      },
      "recommendation": "Extract into three functions: validate_user_request(request) → validated_data, process_user_operation(validated_data) → result, format_user_response(result) → Response. Each function is independently testable and has cyclomatic complexity ≤ 3."
    }
  ]
}
```

### Knowledge Sources
| Source | Content |
|---|---|
| Design principles | SOLID principles with code examples, coupling/cohesion metrics, common refactoring patterns |
| Project conventions | Team-specific standards from `.qa-config.yml` knowledge_base |
| Tier 1 metrics | Complexity scores, function length, parameter counts |

### Decision Process
```
FOR EACH structural concern:

  1. Is this a genuine improvement or a style preference?
     │
     ├─ GENUINE: Reduces complexity, improves testability, prevents future bugs
     │   → PRODUCE finding with concrete improvement suggestion
     │
     └─ PREFERENCE: Cosmetic, subjective, no measurable impact
            → SUPPRESS — design agent does not produce stylistic nitpicks
```

### Failure Handling
Same as Correctness Agent. No special fail-open behavior (design findings are not safety-critical).

---

## 2.4 Agent 4: Cross-File Analysis Agent

### Identity
| Field | Value |
|---|---|
| **Name** | `cross_file` |
| **Mission** | Detect systemic issues that emerge from interactions between files — inconsistencies, broken contracts, and patterns that per-file agents cannot see |
| **Primary Objective** | Compare code across module boundaries to identify where files that should be consistent are not, where interface contracts are violated, and where a pattern repeated across N files has exceptions that may be bugs |

### Capabilities
1. **Consistency detection**: Compare implementations across similar files (all controllers, all services, all handlers) to find deviations from the dominant pattern
2. **Interface contract verification**: Check that function signatures, return types, and error handling match across callers and implementations
3. **Systemic pattern identification**: Detect when the same issue appears in multiple files, transforming N individual findings into one systemic recommendation
4. **Missing implementation detection**: Identify when most modules implement a required pattern (auth check, input validation, error handler) but some don't

### Reasoning Responsibilities

The agent operates in **comparative mode**: "Are these files consistent with each other?"

This requires holding patterns from multiple files in working memory simultaneously — a capability per-file agents don't have.

**Step 1 — Module mapping**: Identify the file group's purpose (e.g., "these are all REST controllers") and expected patterns (auth decorator, input validation, error handling, response format).

**Step 2 — Pattern extraction**: For each file in the group, extract how it implements each expected pattern. Build a comparison table.

**Step 3 — Deviation detection**: Identify files that deviate from the majority pattern. For each deviation, determine if it's intentional (documented, different purpose) or an oversight.

**Step 4 — Systemic finding production**: If the same issue appears in multiple files, produce one systemic finding with all affected files listed, rather than N individual findings.

### Input Context
```
FileGroupReviewContext:
  file_group: FileReviewContext[]  — 5-15 related files
  module_name: str                 — "controllers", "services", "handlers"
  per_file_findings: Finding[]     — Findings from Agents 1-3 (to avoid rediscovery)
```

### Output Format
```json
{
  "findings": [
    {
      "file": "src/api/",
      "start_line": 0,
      "end_line": 0,
      "severity": "high",
      "title": "Controller D lacks authentication — inconsistent with other controllers",
      "explanation": "Controllers A (users.py), B (orders.py), and C (products.py) all use @require_auth decorator. Controller D (payments.py) handles payment operations but has no authentication. This inconsistency creates a security gap where unauthenticated users can access payment endpoints.",
      "evidence": {
        "tool_calls": [
          "grep('@require_auth', scope='src/api/') — found in 3 of 4 controllers",
          "read_file('src/api/payments.py', 1, 20) — no auth decorator present"
        ],
        "code_references": [
          "src/api/users.py:12 — @require_auth",
          "src/api/orders.py:8 — @require_auth",
          "src/api/products.py:10 — @require_auth",
          "src/api/payments.py — MISSING"
        ]
      },
      "recommendation": "Add @require_auth decorator to all route functions in src/api/payments.py. Consider creating a base controller class that enforces authentication by default."
    }
  ]
}
```

### Execution Condition
This agent ONLY runs when:
- Trigger is `audit` (full codebase review), OR
- Changed files span 3+ distinct modules (detected by change detector)

It does NOT run on single-file PRs or simple changes — per-file agents with tool access handle those adequately.

### Decision Process
```
FOR EACH file group:

  1. EXTRACT patterns from each file
  2. IDENTIFY the dominant pattern (majority implementation)
  3. FOR EACH deviation from dominant pattern:
     │
     ├─ Deviation is documented or file has different purpose
     │   → SKIP — intentional difference
     │
     ├─ Deviation is in a security-relevant pattern (auth, validation)
     │   → PRODUCE finding with severity=HIGH
     │
     └─ Deviation is in a non-security pattern (error format, logging)
            → PRODUCE finding with severity=MEDIUM
```

### Failure Handling
Same as Correctness Agent. Cross-file findings are supplementary — their absence doesn't compromise the scan.

---

## 2.5 Agent 5: Finding Validator Agent

### Identity
| Field | Value |
|---|---|
| **Name** | `validator` |
| **Mission** | Protect developer trust by ensuring every finding that reaches a developer is real, unique, and properly calibrated — the single most impactful component for platform adoption |
| **Primary Objective** | Adversarially challenge every finding from all sources. Re-read the referenced code independently. Try to REFUTE each finding. Filter false positives. Resolve semantic duplicates across agents. Assign calibrated confidence scores. |

### Capabilities
1. **Independent code verification**: Re-read the code referenced by each finding, independent of the detection agent's reading, to verify that the claimed issue is actually present
2. **Adversarial challenge**: For each finding, construct the strongest possible argument that the finding is WRONG. Only findings that survive this challenge are confirmed.
3. **Semantic deduplication**: Detect when two agents describe the same underlying issue with different wording (Agent 1: "missing error handling" + Agent 2: "unvalidated input in error path") and merge them
4. **Confidence calibration**: Assign calibrated confidence scores based on evidence strength — not based on the detection agent's self-assessment
5. **Suppression documentation**: For every suppressed finding, document the specific reasoning so the decision is auditable

### Reasoning Responsibilities

The agent operates in **skeptical mode**: "Is this finding actually real?"

The default hypothesis for every finding is: **"This finding is wrong."** The validator must find evidence that the finding is correct to confirm it. This is the opposite of the detection agents, which look for evidence that something IS wrong.

**For each finding**:

1. **Re-read the code**: Use `read_file` to read the exact lines referenced by the finding. Do not trust the detection agent's description — verify directly.

2. **Challenge the claim**: "The finding says there's a null dereference at line 42. Let me read lines 38-50. Is there a null check I can find? Is the value actually nullable? Could this path be unreachable?"

3. **Check evidence accuracy**: "The finding says `get_user()` returns None. Let me read `get_user()` — does it actually return None, or does it raise an exception?"

4. **Compare with other findings**: "Agent 1 says 'poor error handling in parse_input' and Agent 2 says 'unvalidated user input in parse_input'. Are these the same issue? Let me read parse_input and determine: is the core problem error handling or input validation?"

5. **Assign verdict**:
   - **CONFIRMED**: Re-reading the code independently confirms the issue. Evidence is accurate.
   - **LIKELY**: The claim is plausible but I cannot fully verify (e.g., runtime behavior I can't statically determine).
   - **UNCERTAIN**: Evidence is ambiguous. Retaining the finding (fail-open) but flagging uncertainty.
   - **SUPPRESSED**: Re-reading the code shows the finding is wrong. Documenting why.

### Available Tools
| Tool | Purpose in Validation Context |
|---|---|
| `read_file(path, start?, end?)` | Re-read code independently to verify finding claims |
| `grep(pattern, scope?)` | Verify evidence claims ("the finding says no sanitization exists — let me grep to confirm") |
| `expand_context(file, line, radius)` | Check surrounding code for guards, checks, or context the detection agent may have missed |

### Input Context
```
ValidationContext:
  findings: Finding[]            — ALL findings from Agents 1-4 + Tier 1 tools
  repository_path: Path          — For independent code re-reading
  batch_size: int                — Findings processed per LLM call (default: 15)
```

### Output Format
```json
{
  "validations": [
    {
      "finding_id": "F-abc123-001",
      "validation_status": "confirmed",
      "confidence": "confirmed",
      "reasoning": "Re-read src/api/users.py:42-48. Confirmed: get_user() returns None on miss (verified at src/db/queries.py:67). No null check present between get_user() call and result.name access. Finding is valid.",
      "merged_with": null
    },
    {
      "finding_id": "F-abc123-007",
      "validation_status": "suppressed",
      "confidence": null,
      "reasoning": "Finding claims race condition at lines 78-92. Re-read the code: database lock acquired at line 72 (SELECT FOR UPDATE) serializes access to this code path. The lock prevents the concurrent modification the finding describes. False positive.",
      "merged_with": null
    },
    {
      "finding_id": "F-abc123-012",
      "validation_status": "confirmed",
      "confidence": "confirmed",
      "reasoning": "Agent 1 reported 'missing error handling in parse_input' and Agent 3 reported 'parse_input has no exception handling'. These describe the same issue. Merging into F-abc123-012 with combined evidence.",
      "merged_with": "F-abc123-015"
    }
  ]
}
```

### Memory Requirements

**Semantic memory**:
- Common false positive patterns (bundled) — patterns the validator has learned produce FPs (e.g., SAST flagging parameterized queries, type-cast values near SQL, auto-escaped template variables)
- Validation criteria per CWE category (bundled) — what constitutes a true positive for each vulnerability type

**Working memory**:
- Current batch of findings being validated
- Code snippets read during validation
- Cross-finding comparison results

### Model Selection
**Claude Opus** (primary) — Different model from detection agents (which use Sonnet). This model diversity is a deliberate architectural decision based on:
- TAP paper: heterogeneous model pairs detect 17% more defects than homogeneous pairs
- 3+1 paper: different model for verifier = +10.3pp precision
- Correlated error prevention: if Sonnet hallucinates a finding, Opus is less likely to confirm the same hallucination

Fallback: Claude Sonnet (if Opus unavailable — degraded but functional).

### Decision Process
```
FOR EACH finding in batch:

  1. RE-READ the code independently
     │
     ├─ Code matches finding's description
     │   │
     │   ├─ Evidence is accurate and sufficient
     │   │   → CONFIRMED (confidence = confirmed)
     │   │
     │   └─ Evidence is partially accurate
     │       → LIKELY (confidence = likely)
     │
     ├─ Code does NOT match finding's description
     │   → SUPPRESSED with reasoning
     │
     └─ Cannot access code or ambiguous
            → UNCERTAIN (retained, fail-open)

  2. CHECK for duplicates with other findings in batch
     │
     ├─ Same file, overlapping lines, same root cause
     │   → MERGE: keep the one with stronger evidence, add other's evidence
     │
     └─ Different file or different root cause
            → KEEP both as independent findings
```

### Failure Handling
| Failure | Response |
|---|---|
| LLM call fails for a batch | **ALL findings in the batch are marked UNVALIDATED and RETAINED**. This is the critical fail-open behavior. The validator never suppresses findings due to its own failure. |
| Tool call fails during validation | Validator notes it could not verify. Finding retained as UNCERTAIN. |
| Timeout on large batch | Reduce batch size and retry. If still failing, mark remaining as UNVALIDATED. |

### Human Escalation Rules
| Condition | Action |
|---|---|
| Validator suppresses a high/critical finding | Suppression reasoning is documented. Appears in report's "Suppressed Findings" section. Security engineer can review. |
| Validator cannot determine validity | Finding retained as UNCERTAIN. Developer reviews and decides. |
| Multiple agents produce conflicting findings for same code | Validator resolves the conflict and documents its reasoning. |

---

# 3. Agent Orchestration Model

## 3.1 Orchestration Pattern: Deterministic Pipeline with Agentic Steps

The orchestrator is NOT an agent. It is a deterministic pipeline controller that invokes agents at defined stages. This follows the RADAR architecture (Meta) where the pipeline controls sequencing and agents provide reasoning at specific stages.

```
ORCHESTRATOR (deterministic)
│
├── PHASE 1: Deterministic analysis (no agents)
│   Tier 1 tools → Risk scoring
│
├── PHASE 2: Detection (agents, parallel)
│   Agent 1 (Correctness) ─┐
│   Agent 2 (Security)     ─┼── per file, independent, parallel
│   Agent 3 (Design)       ─┘
│
├── PHASE 3: Cross-file (agent, conditional)
│   Agent 4 (Cross-File) ── per module group, sequential
│
├── PHASE 4: Validation (agent, sequential)
│   Agent 5 (Validator) ── all findings, batched
│
└── PHASE 5: Post-processing (no agents)
    Dedup → Classify → Attribute → Gate → Report
```

**Key orchestration rules**:
- Phases execute strictly in order. No phase starts before its predecessor completes.
- Within Phase 2, agents run in parallel per file (no data dependency between agents).
- Phase 3 is conditional — only runs on audits or multi-module PRs.
- Phase 4 receives ALL findings from all previous phases.
- Phase 5 is entirely deterministic — no LLM involvement.
- Cost tracking is cumulative. If cost limit is reached during any phase, remaining agent calls are skipped.

## 3.2 Multi-Agent Communication Protocol

**Protocol: Zero direct communication. Pipeline-mediated data flow only.**

```
Agent 1 ─produces→ Finding[]  ─┐
Agent 2 ─produces→ Finding[]  ─┤
Agent 3 ─produces→ Finding[]  ─┼─ aggregated by orchestrator ─→ Agent 5
Agent 4 ─produces→ Finding[]  ─┘
                                                                    │
                                                          Validated Finding[]
                                                                    │
                                                                    ▼
                                                        Finding Manager (deterministic)
```

**Rules**:
1. No agent reads another agent's output directly. The orchestrator collects findings and passes them to the validator.
2. No agent sends messages to another agent. There is no inter-agent messaging channel.
3. The validator receives findings with `source` field identifying which agent produced each one, but it treats all findings uniformly.
4. All agent outputs conform to the same Finding schema — this is the universal communication contract.

**Rationale** (from architecture spec ADR-04): Direct communication introduces coordination complexity, ordering dependencies, and distributed failure modes. Pipeline-mediated flow keeps agents independent and enables parallel execution.

## 3.3 Task Planning Lifecycle

**Who plans what**:

| Planning Decision | Owner | When |
|---|---|---|
| Which files to scan | Orchestrator | At scan start, from diff/audit mode |
| Which files get agent review | Risk Scorer | After Tier 1 completes |
| Which agents run | Orchestrator | From tier config and agent registry |
| How to review a file | Each agent | At agent invocation — agent plans its own approach |
| What to investigate deeper | Each agent | During review — agent decides based on observations |
| Which findings to validate | Validator | Receives all, prioritizes by severity × confidence |

**Agent-internal planning** (within each agent's review_file call):

```
1. PERCEIVE: Read the file, diff, and Tier 1 findings
2. PLAN: Determine what aspects need investigation
   - What does this code do? (API endpoint? Data model? Utility?)
   - What risks are relevant? (Based on code characteristics + Tier 1 findings)
   - What depth is warranted? (Simple change → quick scan. Complex logic → deep trace)
3. EXECUTE: Three-pass review (scan → investigate → verify)
4. OUTPUT: Structured findings
```

This planning is INTERNAL to the agent — the orchestrator doesn't see or control it. The agent decides HOW to review; the orchestrator decides WHAT to review.

## 3.4 Execution Lifecycle

```
AGENT LIFECYCLE (per file):

  ┌─────────────┐
  │   CREATED    │  Agent instantiated with config, memory, tools
  └──────┬──────┘
         │
  ┌──────▼──────┐
  │   LOADED     │  Semantic memory loaded, system prompt assembled
  └──────┬──────┘
         │
  ┌──────▼──────┐
  │  REVIEWING   │  Agent executes observation-action loop
  │              │  Tool calls happen here
  │              │  LLM calls happen here (1-3 per file)
  └──────┬──────┘
         │
    ┌────┴────┐
    │         │
  success   failure
    │         │
  ┌─▼──────┐ ┌▼──────────┐
  │COMPLETE│ │  FAILED    │
  │        │ │            │
  │Findings│ │Empty list  │
  │returned│ │Fail-open   │
  └────────┘ └────────────┘
```

**Constraints enforced during REVIEWING state**:
- Token budget: Agent cannot exceed configured max tokens per file
- Timeout: Agent cannot exceed configured max seconds per file
- Tool calls: Limited to read-only tools. No write operations possible.
- Output: Must conform to Finding schema. Malformed output → retry once → fail.

## 3.5 Evaluation and Verification

**Three layers of verification**:

| Layer | What | How | Evidence |
|---|---|---|---|
| **Layer 1: Self-verification** | Each detection agent challenges its own findings (Pass 3) | Agent asks: "Would a senior engineer flag this?" | Built into agent prompt structure |
| **Layer 2: Independent validation** | Validator Agent challenges ALL findings | Different model re-reads code, tries to refute | RevAgent ablation: critic = most impactful component. 3+1 paper: +10.3pp precision. |
| **Layer 3: Algorithmic dedup** | Finding Manager removes exact duplicates | Same file + overlapping lines + similar title → merge | Deterministic, no LLM |

**Why three layers**: Self-verification catches obvious false positives cheaply (same LLM call). Independent validation catches correlated errors (different model, different perspective). Algorithmic dedup catches exact matches (no LLM cost).

## 3.6 Feedback Loops

### Runtime Feedback (within a single scan)

**Finding → Validator → Confidence**: Detection agents produce findings with proposed severity. The Validator Agent independently assigns confidence. This creates a feedback signal: if the Validator consistently downgrades a detection agent's findings, it indicates the detection agent's precision needs improvement (via prompt tuning).

**Tier 1 → Agent**: SAST findings from Tier 1 flow into the Security Agent as structured input. The agent's validation results (TP/FP ratio) provide feedback on SAST tool precision — visible in the report's noise reduction section.

### Cross-Scan Feedback (across scans over time)

**Resolution tracking**: When developers mark findings as "Resolved" vs "Won't Fix," this creates a dataset of accepted vs rejected findings. Over time, this data can be used to:
- Identify agent prompts that produce consistently rejected findings → prompt refinement
- Identify finding categories with high "Won't Fix" rates → threshold adjustment
- Identify projects where certain agents are less useful → per-project agent configuration

**Quality gate calibration**: If the gate consistently fails and is overridden, the thresholds may be too strict. If the gate consistently passes but production incidents occur, thresholds may be too loose. Gate results over time inform threshold calibration.

### Metrics That Enable Feedback
| Metric | Source | Feedback To |
|---|---|---|
| Validation suppression rate per agent | Validator output | Agent prompt quality |
| "Won't Fix" rate per agent | Developer resolution labels | Agent precision |
| SAST TP/FP ratio | Security Agent output | SAST tool configuration |
| Gate override frequency | Gate override records | Threshold calibration |

## 3.7 Learning and Improvement Mechanisms

The platform does NOT use online learning (no model fine-tuning during operation). Improvement happens through structured, human-reviewed updates:

| Mechanism | How It Works | Who Owns It |
|---|---|---|
| **Prompt refinement** | Analyze validation suppression rates and "Won't Fix" data. Identify prompt weaknesses. Update prompt files in `prompts/` directory. | Platform maintainer |
| **Semantic memory updates** | Add new SAST rules, update CWE taxonomy, add project-specific conventions. Update knowledge files. | Security engineer / platform maintainer |
| **Threshold calibration** | Review quality gate metrics over time. Adjust thresholds in `.qa-config.yml`. | Engineering manager |
| **Agent graduation** | New agents start in shadow mode (findings logged but not reported). After reviewing shadow findings for precision, promote to advisory → enforced. | Tech lead |
| **Suppression rule learning** | When the Validator repeatedly suppresses findings matching a pattern, suggest a permanent suppression rule. | Platform maintainer + team approval |

**No automated prompt modification.** All prompt changes are versioned, reviewed, and deployed like code. The platform does not modify its own prompts based on feedback — a human reviews the data and makes the change.

---

# 4. Safety and Governance

## 4.1 Audit-Only Enforcement

The audit-only constraint (the platform NEVER modifies code) is enforced at 5 layers:

| Layer | Enforcement |
|---|---|
| **Tool interface** | No write tools exist. Agent tools are: read_file, grep, expand_context, git_diff, list_directory — all read-only. |
| **Repository access** | Git operations are read-only (clone, diff, blame, log). Clone is to a temp directory — original repo is never touched. |
| **Agent prompts** | System prompts state: "You identify, report, and recommend. You do NOT modify code." |
| **Output schema** | Finding has `recommendation` (text describing what to do), not `patch` (executable code change). |
| **Report delivery** | Reports are written to output directory. PR comments are review comments, not code change suggestions. |

## 4.2 Observable Execution

Every agent action is logged and auditable:

| What | Where Logged | Purpose |
|---|---|---|
| Every LLM API call | Audit log (prompt hash, tokens, cost, model) | Cost accountability, compliance |
| Every tool call by agent | AgentResult.tool_calls | Transparency — which files did the agent read? |
| Every finding produced | Finding with source attribution | Traceability — which agent found this? |
| Every validation decision | Finding.validation_status + reasoning | Accountability — why was this suppressed/confirmed? |
| Every suppression | Suppressed finding with reasoning | Review — was the suppression correct? |

## 4.3 Deterministic Boundaries

| Boundary | What's Inside (Deterministic) | What's Outside (Agent Autonomy) |
|---|---|---|
| File selection | Orchestrator selects files based on diff + risk score | — |
| Agent selection | Orchestrator selects agents based on tier config | — |
| — | — | How agent reviews a file (tool calls, investigation depth) |
| — | — | Whether agent produces a finding (agent judgment) |
| Finding schema | Fixed structure, validated on output | Finding content (explanation, evidence, recommendation) |
| Quality gate | Threshold evaluation, no LLM | — |
| Report structure | Template-driven, deterministic | — |

## 4.4 Cost Governance

| Control | Implementation |
|---|---|
| Per-scan cost limit | `--cost-limit <USD>` CLI flag. Orchestrator checks after each agent call. If limit reached, remaining agents skipped. |
| Per-agent cost tracking | LLM client tracks input/output tokens and cost per agent. Exposed in report metadata. |
| Model selection | Per-agent model configuration. Sonnet for detection (cost-effective), Opus for validation (precision-critical). |
| Risk-based routing | Risk scorer gates agent invocation. Only high-risk files get agent review. Low-risk files → Tier 1 only. |
| Circuit breaker | After 5 consecutive LLM failures, skip remaining calls. Prevents runaway cost from retries. |
