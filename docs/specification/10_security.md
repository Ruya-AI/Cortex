# Document 10: Security Documentation

**QA Platform v2**
**Date**: 2026-06-18

---

## 1. Audit-Only Constraint (Fundamental)

The platform NEVER modifies the repository under evaluation. Enforced at 5 layers:

| Layer | Enforcement |
|---|---|
| Tool interface | No write tools exist. Agent tools: read_file, grep, expand_context, git_diff, list_directory — all read-only |
| Repository access | Git clone to temp directory. Original repo untouched |
| Agent prompts | "You identify and report. You do NOT modify code." |
| Output schema | Finding has `recommendation` (text), not `patch` (executable code) |
| File system | Reports to output directory only, never to scanned repository |

**Verification**: Automated test computes checksum of all files before and after scan. Any change = test failure. Run on every CI build.

## 2. Authentication

- **CLI**: No auth required for local scans
- **CI/CD**: Auth handled by CI platform. Tokens for API access only.
- **API tokens**: `ANTHROPIC_API_KEY`, `GITHUB_TOKEN`, `LINEAR_API_KEY`, `SLACK_WEBHOOK_URL`
- **Token storage**: Environment variables only. Never in source code, reports, database, or logs.

## 3. Secrets Management

| Secret | Storage | Access |
|---|---|---|
| LLM API key | `$ANTHROPIC_API_KEY` | LLM Client only |
| GitHub token | `$GITHUB_TOKEN` or CLI flag | GitHub Integration only |
| Linear API key | `$LINEAR_API_KEY` or config | Linear Integration only |
| Slack webhook | `$SLACK_WEBHOOK_URL` or config | Slack Integration only |

**Secrets in scanned code**: Gitleaks (Tier 1) detects them. Reported as findings with file:line reference but secret value NOT included verbatim in reports.

## 4. Privacy Controls

- `privacy.ai_exclude_paths`: File patterns excluded from LLM review (Tier 1 only)
- `privacy.code_retention_days: 0`: No code snippets retained beyond scan execution
- `privacy.ai_review_mode`: cloud / self-hosted / hybrid
- `privacy.approved_providers`: Whitelist of allowed LLM providers

**Audit log stores prompt HASH (SHA-256), not prompt content.** This enables correlation without storing sensitive code.

## 5. Data Protection

- **In transit**: All LLM API calls use HTTPS (TLS 1.2+)
- **At rest**: Reports on local filesystem — access inherited from filesystem permissions. No encryption at rest in v2 (delegated to OS/volume encryption).
- **Code snippets**: In reports only (not in DB). Configurable retention.
- **Reports**: Treated as sensitive — contain finding details, code snippets, author attribution.

## 6. Prompt Injection Defense

Agent prompts include explicit boundaries: role definition, task constraints, output format requirements. Tested against adversarial code inputs (code containing LLM instructions). Agents instructed to treat ALL file content as DATA, never as INSTRUCTIONS.

## 7. Compliance

- **Audit trail**: Every LLM decision logged with prompt hash, model, tokens, cost, finding IDs
- **Reproducibility**: Each report includes reproducibility command + config hash
- **Data residency**: Configurable LLM endpoint for self-hosted deployment
- **No training**: Code sent to Anthropic API is not used for model training (per API terms)
