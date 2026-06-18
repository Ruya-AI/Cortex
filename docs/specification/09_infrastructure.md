# Document 09: Infrastructure Documentation

**QA Platform v2**
**Date**: 2026-06-18

---

## 1. Deployment Model

**Primary**: Python CLI installed via `pip install qa-platform`. Runs on developer machines and CI/CD runners. No server infrastructure.

**Secondary**: Docker container for CI/CD environments. Base: python:3.11-slim. Includes all pip tools and optional external binaries. ~375MB total.

## 2. Container Specification

```
Layer 1: python:3.11-slim (~45MB)
Layer 2: git, shellcheck (~30MB)
Layer 3: qa-platform + pip tools (ruff, bandit, mypy, semgrep, radon, etc.) (~200MB)
Layer 4: Optional binaries (gitleaks, hadolint, trivy, osv-scanner) (~100MB)
Entrypoint: qa
```

## 3. CI/CD Integration

### GitHub Actions
```yaml
name: QA Review
on:
  pull_request:
    types: [opened, synchronize]
jobs:
  qa:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
      with: { fetch-depth: 0 }
    - run: pip install qa-platform
    - run: qa run --repo . --pr ${{ github.event.pull_request.number }} --vs ${{ github.base_ref }} --post-comment --report json
      env:
        ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    - uses: actions/upload-artifact@v4
      if: always()
      with: { name: qa-report, path: .qa-reports/ }
```

### Kubernetes Job
Each scan runs as a K8s Job (not a Deployment). Jobs created by webhook receiver or CronJob. Resource limits: 512Mi request, 2Gi limit, 500m CPU request, 2 CPU limit. activeDeadlineSeconds: 600.

## 4. Monitoring

| Metric | Source | Purpose |
|---|---|---|
| Scan duration | Orchestrator | Performance SLA |
| Scan cost (USD) | CostTracker | Budget management |
| Finding count by severity | FindingManager | Quality trends |
| False positive rate | Validator | Precision monitoring |
| Agent failure rate | LLM Client | Reliability |
| Tool availability | Tier1Runner | Infrastructure health |
| Gate pass rate | QualityGate | Policy effectiveness |

Metrics emitted as structured JSON log entries. Ingestible by ELK, Datadog, Grafana Loki.

## 5. Logging

**Format**: JSON structured with correlation ID (scan_id).

```json
{"timestamp":"...","level":"INFO","scan_id":"QA-RPT-...","component":"review_engine","agent":"security","event":"agent.completed","finding_count":3,"cost_usd":0.004}
```

**Levels**: ERROR (failures needing attention), WARNING (degraded operation), INFO (milestones), DEBUG (detailed operation)

**Destinations**: stdout (default), file (configurable), syslog (configurable)

## 6. Alerting

| Condition | Severity | Action |
|---|---|---|
| Circuit breaker open (5+ LLM failures) | High | Check API key, Anthropic status |
| Scan cost > $10 | Medium | Review scope |
| Scan duration > 15 min | Medium | Check file count, LLM latency |
| All Tier 1 tools unavailable | High | Check container image |

Alerts via structured log entries with `level: ERROR` and `alert` field. PagerDuty/OpsGenie integration via log aggregation, not platform-native.
