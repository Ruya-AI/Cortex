from __future__ import annotations

import html
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cortex_engine.core.finding import (
    Finding,
    LifecycleState,
)
from cortex_engine.core.schemas import QualityGateResult, RepositoryContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

SEVERITY_COLORS: dict[str, str] = {
    "critical": "#dc3545",
    "high": "#fd7e14",
    "medium": "#ffc107",
    "low": "#28a745",
    "info": "#6c757d",
}

_SEVERITY_INT_TO_STR: dict[int, str] = {
    4: "critical",
    3: "high",
    2: "medium",
    1: "low",
    0: "info",
}

_CONFIDENCE_INT_TO_STR: dict[int, str] = {
    2: "confirmed",
    1: "likely",
    0: "uncertain",
}


def _e(value: Any) -> str:
    """Strip control characters then HTML-escape."""
    if value is None:
        return ""
    return html.escape(_CONTROL_CHARS.sub("", str(value)))


def _severity_str(val: Any) -> str:
    """Convert a severity value (int or string) to a lowercase name."""
    if isinstance(val, int):
        return _SEVERITY_INT_TO_STR.get(val, "info")
    return str(val).lower()


def _confidence_str(val: Any) -> str:
    """Convert a confidence value (int or string) to a lowercase name."""
    if isinstance(val, int):
        return _CONFIDENCE_INT_TO_STR.get(val, "uncertain")
    return str(val).lower()


def _assess_risk(findings: list[dict[str, Any]]) -> str:
    """Assess overall risk level from finding severity distribution."""
    severities = {_severity_str(f.get("severity", "info")) for f in findings}
    if "critical" in severities:
        return "CRITICAL"
    if "high" in severities:
        return "HIGH"
    if "medium" in severities:
        return "MEDIUM"
    if "low" in severities:
        return "LOW"
    return "CLEAN"


def _get_sub_dir(trigger: str, pr_number: int | None = None) -> str:
    """Determine report subdirectory based on trigger type."""
    trigger_lower = trigger.lower() if trigger else "adhoc"
    if trigger_lower in ("pr", "pull_request", "pull-request") and pr_number:
        return f"pr-{pr_number}"
    if trigger_lower in ("nightly", "scheduled"):
        return "nightly"
    if trigger_lower in ("push", "commit"):
        return "push"
    return "adhoc"


def _get_file_stem(
    trigger: str,
    report_id: str,
    pr_number: int | None = None,
) -> str:
    """Build a descriptive file stem for the report."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    trigger_lower = trigger.lower() if trigger else "adhoc"
    if trigger_lower in ("pr", "pull_request", "pull-request") and pr_number:
        return f"qa-pr{pr_number}-{ts}"
    if trigger_lower in ("nightly", "scheduled"):
        return f"qa-nightly-{ts}"
    return f"qa-{ts}-{report_id[:8]}"


def _normalise_finding_dict(fd: dict[str, Any]) -> dict[str, Any]:
    """Normalise enum integer values in a finding dict to string names.

    ``Finding.to_dict()`` serialises ``Severity`` / ``Confidence`` /
    ``Classification`` via ``.value`` which yields *integers* for IntEnum
    members and *strings* for str-Enum members.  The report templates
    expect human-readable lowercase names everywhere, so this helper
    patches the dict in-place and returns it.
    """
    fd["severity"] = _severity_str(fd.get("severity", "info"))
    fd["confidence"] = _confidence_str(fd.get("confidence", "uncertain"))
    # Classification, FindingCategory, LifecycleState, ValidationStatus are
    # str-enums so .value already produces a string -- just lower-case.
    for key in ("classification", "category", "lifecycle_state", "validation_status"):
        val = fd.get(key)
        if val is not None:
            fd[key] = str(val).lower()
    return fd


# ===================================================================
# ReportGenerator
# ===================================================================


class ReportGenerator:
    """Full 11-section QA Assessment report generator (JSON + PDF/HTML)."""

    def generate(
        self,
        findings: list[Finding],
        gate_result: QualityGateResult,
        repo_context: RepositoryContext,
        scan_metadata: dict,
        config: dict,
        output_dir: Path,
        file_stem: str,
        formats: list[str],
    ) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)

        report_data = self._build_report_data(
            findings, gate_result, repo_context, scan_metadata, config,
        )

        result: dict[str, Any] = {"report_data": report_data}

        # -- JSON output ---------------------------------------------------
        if "json" in formats:
            json_path = output_dir / f"{file_stem}.json"
            json_path.write_text(
                json.dumps(report_data, indent=2, default=str), encoding="utf-8",
            )
            result["json_path"] = json_path
            logger.info("JSON report written to %s", json_path)

        # -- PDF output (WeasyPrint with HTML fallback) --------------------
        if "pdf" in formats:
            pdf_path = output_dir / f"{file_stem}.pdf"

            pdf_data = report_data
            total_findings = len(report_data.get("findings", []))
            max_pdf_findings = 500
            if total_findings > max_pdf_findings:
                logger.warning(
                    "PDF capped at %d findings (total: %d) to prevent OOM",
                    max_pdf_findings, total_findings,
                )
                pdf_data = {**report_data, "findings": report_data["findings"][:max_pdf_findings]}

            html_content = self._render_html(pdf_data)
            try:
                from weasyprint import HTML as WeasyprintHTML  # type: ignore[import-untyped]

                WeasyprintHTML(string=html_content).write_pdf(str(pdf_path))
                result["pdf_path"] = pdf_path
                logger.info("PDF report written to %s (%d findings)", pdf_path, min(total_findings, max_pdf_findings))
            except ImportError:
                html_path = output_dir / f"{file_stem}.html"
                html_path.write_text(html_content, encoding="utf-8")
                result["pdf_path"] = html_path
                logger.warning(
                    "WeasyPrint not available; HTML fallback written to %s",
                    html_path,
                )
            except MemoryError:
                html_path = output_dir / f"{file_stem}.html"
                html_path.write_text(html_content, encoding="utf-8")
                result["pdf_path"] = html_path
                logger.error(
                    "WeasyPrint OOM with %d findings; HTML fallback written to %s",
                    min(total_findings, max_pdf_findings), html_path,
                )

        return result

    # ------------------------------------------------------------------
    # Report data assembly (11 sections)
    # ------------------------------------------------------------------

    def _build_report_data(
        self,
        findings: list[Finding],
        gate_result: QualityGateResult,
        repo_context: RepositoryContext,
        scan_metadata: dict,
        config: dict,
    ) -> dict[str, Any]:
        # Partition findings by lifecycle state
        active = [f for f in findings if f.lifecycle_state == LifecycleState.OPEN]
        suppressed = [f for f in findings if f.lifecycle_state == LifecycleState.SUPPRESSED]
        resolved = [f for f in findings if f.lifecycle_state == LifecycleState.RESOLVED]

        # Convert to dicts with normalised enum strings
        active_dicts = [_normalise_finding_dict(f.to_dict()) for f in active]
        suppressed_dicts = [_normalise_finding_dict(f.to_dict()) for f in suppressed]
        resolved_dicts = [_normalise_finding_dict(f.to_dict()) for f in resolved]

        # Severity counts from active findings
        severity_counts: dict[str, int] = {
            "critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0,
        }
        category_counts: dict[str, int] = {}
        classification_counts: dict[str, int] = {}
        for fd in active_dicts:
            sev = fd.get("severity", "info")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            cat = fd.get("category", "uncategorised")
            category_counts[cat] = category_counts.get(cat, 0) + 1
            cls = fd.get("classification", "unclassified")
            classification_counts[cls] = classification_counts.get(cls, 0) + 1

        # Build finding clusters from root_cause_cluster
        clusters_by_id: dict[str, list[str]] = {}
        for fd in active_dicts:
            cluster_key = fd.get("root_cause_cluster")
            if cluster_key:
                clusters_by_id.setdefault(cluster_key, []).append(fd.get("id", ""))
        finding_clusters = [
            {"cluster_id": cid, "finding_ids": fids, "count": len(fids)}
            for cid, fids in clusters_by_id.items()
        ]

        # Positive observations
        positive_observations: list[str] = []
        if not any(fd.get("severity") in ("critical", "high") for fd in active_dicts):
            positive_observations.append("No high or critical severity issues found.")
        if not active_dicts:
            positive_observations.append("No active findings -- code looks clean.")

        # Risk level
        risk_level = _assess_risk(active_dicts)

        # Verdict
        if gate_result.status == "fail":
            verdict = "Quality gate FAILED -- blocking issues found."
        elif active_dicts:
            verdict = f"Quality gate passed with {len(active_dicts)} finding(s)."
        else:
            verdict = "Quality gate passed -- no findings."

        # Collect unique commit authors
        commit_author: dict[str, str] = {}
        for f in findings:
            if f.author:
                commit_author = {
                    "name": f.author.name,
                    "email": f.author.email,
                    "github_username": f.author.github_username or "",
                }
                break  # use first available author

        # Extract metadata values
        report_id = scan_metadata.get("report_id", str(uuid.uuid4())[:12])
        trigger = scan_metadata.get("trigger", "ad-hoc")
        pr_number = scan_metadata.get("pr_number")
        generated_at = datetime.now(timezone.utc).isoformat()

        # Extract repository info
        repo_name = ""
        repo_url = ""
        if repo_context:
            repo_url = repo_context.remote_url
            repo_name = Path(repo_context.local_path).name if repo_context.local_path else ""

        # Scope summary
        all_files = {f.file for f in findings if f.file}
        skip_summary = scan_metadata.get("skip_summary", {})

        return {
            "report_metadata": {
                "report_id": report_id,
                "generated_at": generated_at,
                "trigger": trigger,
                "platform_version": "2.0.0",
                "models_used": scan_metadata.get("models_used", []),
                "execution_duration_seconds": scan_metadata.get("duration", 0.0),
                "execution_cost_usd": scan_metadata.get("cost", 0.0),
                "previous_report_id": scan_metadata.get("previous_report_id"),
            },
            "repository_context": {
                "repository": repo_name,
                "repository_url": repo_url,
                "branch": repo_context.branch if repo_context else "",
                "compare_to": scan_metadata.get("compare_to", ""),
                "commit_sha": repo_context.commit_sha if repo_context else "",
                "commit_message": repo_context.commit_message if repo_context else "",
                "commit_timestamp": scan_metadata.get("commit_timestamp", ""),
                "pr_number": pr_number,
                "pr_title": scan_metadata.get("pr_title", ""),
                "pr_url": scan_metadata.get("pr_url", ""),
            },
            "attribution": {
                "commit_author": commit_author,
            },
            "scope_summary": {
                "total_files": len(all_files),
                "files_analyzed": len(all_files),
                "files_skipped": skip_summary.get("total_skipped", 0),
                "skip_reasons": skip_summary.get("counts", {}),
                "excluded_directories": skip_summary.get("excluded_directories", {}),
                "total_files_in_changeset": skip_summary.get("total_files_in_changeset", len(all_files)),
                "modules_covered": scan_metadata.get("modules_covered", []),
                "tiers_executed": scan_metadata.get("tiers", []),
                "agents_used": scan_metadata.get("agents_used", []),
                "diff_mode": scan_metadata.get("diff_mode", False),
                "changed_files": scan_metadata.get("changed_files", []),
                "lines_changed": scan_metadata.get("lines_changed", 0),
            },
            "executive_summary": {
                "verdict": verdict,
                "quality_gate_status": gate_result.status,
                "finding_counts_by_severity": severity_counts,
                "finding_counts_by_category": category_counts,
                "finding_counts_by_classification": classification_counts,
                "resolved_count": len(resolved_dicts),
                "positive_observations_count": len(positive_observations),
                "risk_level": risk_level,
                "comparison_vs_previous": scan_metadata.get("comparison_vs_previous"),
            },
            "findings": active_dicts,
            "finding_clusters": finding_clusters,
            "resolved_issues": resolved_dicts,
            "positive_observations": positive_observations,
            "suppressed_findings": suppressed_dicts,
            "appendix": {
                "files_scanned": sorted(all_files),
                "files_skipped_detail": [],
                "tier1_results": scan_metadata.get("tier1_results"),
                "agent_config": config.get("agents") if isinstance(config, dict) else None,
                "config_hash": scan_metadata.get("config_hash", ""),
                "reproducibility_command": scan_metadata.get("reproducibility_command", ""),
            },
        }

    # ------------------------------------------------------------------
    # HTML / PDF rendering
    # ------------------------------------------------------------------

    def _render_html(self, report_data: dict[str, Any]) -> str:
        meta = report_data.get("report_metadata", {})
        repo = report_data.get("repository_context", {})
        attribution = report_data.get("attribution", {})
        scope = report_data.get("scope_summary", {})
        exec_summary = report_data.get("executive_summary", {})
        findings = report_data.get("findings", [])
        clusters = report_data.get("finding_clusters", [])
        resolved = report_data.get("resolved_issues", [])
        positive = report_data.get("positive_observations", [])
        suppressed = report_data.get("suppressed_findings", [])

        parts: list[str] = []

        # -- HTML head + CSS -----------------------------------------------
        report_id = meta.get("report_id", "")
        parts.append("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>QA Assessment Report</title>
<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
    max-width: 960px;
    margin: 2rem auto;
    padding: 0 1rem;
    color: #212529;
    line-height: 1.6;
  }
  h1, h2 { color: #1a1a2e; }
  .meta-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 1.5rem;
  }
  .meta-table tr:nth-child(even) { background: #f8f9fa; }
  .meta-table td, .meta-table th {
    padding: 0.5rem 0.75rem;
    border: 1px solid #dee2e6;
    text-align: left;
  }
  .meta-table th { background: #e9ecef; width: 200px; }
  .summary-box {
    background: #e8f4fd;
    border-left: 4px solid #0f3460;
    padding: 1rem 1.5rem;
    margin: 1.5rem 0;
    border-radius: 4px;
  }
  .risk-badge {
    display: inline-block;
    color: #fff;
    padding: 0.3rem 0.8rem;
    border-radius: 4px;
    font-weight: 700;
    font-size: 0.95rem;
    margin-left: 0.5rem;
  }
  .severity-badge {
    display: inline-block;
    color: #fff;
    padding: 0.2rem 0.6rem;
    border-radius: 3px;
    font-size: 0.85rem;
    font-weight: 600;
    margin-right: 0.4rem;
  }
  .finding {
    border: 1px solid #dee2e6;
    border-radius: 8px;
    margin: 1rem 0;
    padding: 1rem 1.25rem;
    border-left-width: 5px;
    border-left-style: solid;
  }
  .finding-header {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin-bottom: 0.5rem;
  }
  .finding-header h3 { margin: 0; }
  .finding .detail { margin: 0.3rem 0; }
  .evidence {
    background: #f8f9fa;
    padding: 0.75rem 1rem;
    border-radius: 4px;
    margin: 0.5rem 0;
  }
  .recommendation pre {
    background: #f0f0f0;
    padding: 0.75rem 1rem;
    border-radius: 4px;
    overflow-x: auto;
    font-size: 0.9rem;
    white-space: pre-wrap;
    word-wrap: break-word;
  }
  pre {
    background: #f8f9fa;
    padding: 0.75rem 1rem;
    border-radius: 4px;
    overflow-x: auto;
    font-size: 0.9rem;
    white-space: pre-wrap;
    word-wrap: break-word;
  }
  .footer {
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid #dee2e6;
    color: #888;
    font-size: 0.85rem;
  }
</style>
</head>
<body>
<h1>QA Assessment Report</h1>""")

        # -- 1. Report Metadata -------------------------------------------
        parts.append("<h2>1. Report Metadata</h2>")
        parts.append(self._meta_table(meta))

        # -- 2. Repository Context ----------------------------------------
        parts.append("<h2>2. Repository Context</h2>")
        parts.append(self._meta_table(repo))

        # -- 3. Developer/User Attribution --------------------------------
        parts.append("<h2>3. Developer/User Attribution</h2>")
        author = attribution.get("commit_author", {})
        if author:
            parts.append(self._meta_table(author))
        else:
            parts.append("<p>No attribution data available.</p>")

        # -- 4. Scope Summary ---------------------------------------------
        parts.append("<h2>4. Scope Summary</h2>")
        parts.append(self._meta_table(scope))

        # -- 5. Executive Summary -----------------------------------------
        parts.append("<h2>5. Executive Summary</h2>")
        verdict = exec_summary.get("verdict", "")
        gate_status = exec_summary.get("quality_gate_status", "pass")
        risk_level = exec_summary.get("risk_level", "CLEAN")
        risk_color = SEVERITY_COLORS.get(risk_level.lower(), "#28a745")

        parts.append('<div class="summary-box">')
        parts.append(f"<p><strong>Verdict:</strong> {_e(verdict)}</p>")
        parts.append(
            f"<p><strong>Quality Gate:</strong> {_e(gate_status.upper())}"
            f'<span class="risk-badge" style="background:{risk_color};">'
            f"{_e(risk_level)}</span></p>"
        )

        # Severity count badges
        sev_counts = exec_summary.get("finding_counts_by_severity", {})
        if sev_counts:
            badges = []
            for sev_name in ("critical", "high", "medium", "low", "info"):
                count = sev_counts.get(sev_name, 0)
                color = SEVERITY_COLORS.get(sev_name, "#6c757d")
                badges.append(
                    f'<span class="severity-badge" style="background:{color};">'
                    f"{_e(sev_name.upper())}: {count}</span>"
                )
            parts.append("<p>" + " ".join(badges) + "</p>")

        parts.append("</div>")  # end summary-box

        # -- 6. Findings --------------------------------------------------
        parts.append("<h2>6. Findings</h2>")
        if findings:
            for fd in findings:
                parts.append(self._render_finding_card(fd))
        else:
            parts.append("<p>No active findings.</p>")

        # -- 7. Finding Clusters ------------------------------------------
        parts.append("<h2>7. Finding Clusters</h2>")
        if clusters:
            for c in clusters:
                parts.append(
                    f"<p><strong>{_e(c.get('cluster_id', ''))}</strong>: "
                    f"{c.get('count', 0)} findings "
                    f"({', '.join(_e(fid) for fid in c.get('finding_ids', []))})</p>"
                )
        else:
            parts.append("<p>No clusters detected.</p>")

        # -- 8. Resolved Issues -------------------------------------------
        parts.append("<h2>8. Resolved Issues</h2>")
        if resolved:
            for rd in resolved:
                parts.append(self._render_finding_card(rd))
        else:
            parts.append("<p>No resolved issues.</p>")

        # -- 9. Positive Observations -------------------------------------
        parts.append("<h2>9. Positive Observations</h2>")
        if positive:
            parts.append("<ul>")
            for obs in positive:
                parts.append(f"<li>{_e(obs)}</li>")
            parts.append("</ul>")
        else:
            parts.append("<p>No positive observations recorded.</p>")

        # -- 10. Suppressed Findings --------------------------------------
        parts.append("<h2>10. Suppressed Findings</h2>")
        if suppressed:
            parts.append(f"<p>{len(suppressed)} finding(s) suppressed.</p>")
            for sd in suppressed:
                parts.append(self._render_finding_card(sd))
        else:
            parts.append("<p>No suppressed findings.</p>")

        # -- Footer -------------------------------------------------------
        parts.append('<div class="footer">')
        parts.append(
            f"<p>Report ID: {_e(report_id)} | "
            f"Generated: {_e(meta.get('generated_at', ''))} | "
            f"Platform v{_e(meta.get('platform_version', ''))}</p>"
        )
        parts.append(
            "<p>This report is generated for audit and informational purposes only. "
            "It does not constitute a guarantee of code correctness.</p>"
        )
        parts.append("</div>")

        parts.append("</body></html>")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _meta_table(self, data: dict[str, Any]) -> str:
        """Render a key-value dict as an HTML table with 200px first column."""
        rows: list[str] = []
        for key, value in data.items():
            display_val = (
                json.dumps(value, default=str)
                if isinstance(value, (list, dict))
                else str(value) if value is not None else ""
            )
            rows.append(
                f"<tr><th>{_e(key)}</th><td>{_e(display_val)}</td></tr>"
            )
        return f'<table class="meta-table">{"".join(rows)}</table>'

    def _render_finding_card(self, fd: dict[str, Any]) -> str:
        """Render a single finding dict as an HTML card."""
        severity = _severity_str(fd.get("severity", "info"))
        color = SEVERITY_COLORS.get(severity, "#6c757d")
        confidence = _confidence_str(fd.get("confidence", "uncertain"))
        classification = fd.get("classification", "unclassified")
        category = fd.get("category", "")
        title = fd.get("title", "Untitled")
        fid = fd.get("id", "")
        file_path = fd.get("file", "")
        start_line = fd.get("start_line", "")
        explanation = fd.get("explanation", "")
        recommendation = fd.get("recommendation", "")
        code_under_review = fd.get("code_under_review", "")
        cwe = fd.get("cwe")
        related = fd.get("related_findings", [])
        cluster = fd.get("root_cause_cluster")

        # Author attribution
        author = fd.get("author")
        author_str = ""
        if author and isinstance(author, dict):
            name = author.get("name", "")
            email = author.get("email", "")
            author_str = f"{name} &lt;{_e(email)}&gt;" if email else _e(name)

        # Evidence
        evidence = fd.get("evidence", {})
        tool_calls = evidence.get("tool_calls", []) if isinstance(evidence, dict) else []
        code_refs = evidence.get("code_references", []) if isinstance(evidence, dict) else []

        parts: list[str] = []
        parts.append(f'<div class="finding" style="border-left-color: {color};">')

        # Finding header: id, severity, confidence, classification badges
        parts.append('<div class="finding-header">')
        parts.append(
            f'<span class="severity-badge" style="background:#6c757d;">{_e(fid)}</span>'
        )
        parts.append(
            f'<span class="severity-badge" style="background:{color};">'
            f"{_e(severity.upper())}</span>"
        )
        conf_color = "#28a745" if confidence == "confirmed" else (
            "#ffc107" if confidence == "likely" else "#dc3545"
        )
        parts.append(
            f'<span class="severity-badge" style="background:{conf_color};">'
            f"{_e(confidence.upper())}</span>"
        )
        if classification and classification != "unclassified":
            parts.append(
                f'<span class="severity-badge" style="background:#0f3460;">'
                f"{_e(classification.upper())}</span>"
            )
        parts.append("</div>")  # end finding-header

        # Title
        parts.append(f"<h3>{_e(title)}</h3>")

        # File:line
        if file_path:
            loc = f"{file_path}:{start_line}" if start_line else file_path
            parts.append(f'<p class="detail"><strong>File:</strong> {_e(loc)}</p>')

        # Category
        if category:
            parts.append(f'<p class="detail"><strong>Category:</strong> {_e(category)}</p>')

        # Author
        if author_str:
            parts.append(f'<p class="detail"><strong>Author:</strong> {author_str}</p>')

        # Attribution source
        if author and isinstance(author, dict):
            attr_source = author.get("attribution_source", "")
            if attr_source:
                parts.append(
                    f'<p class="detail"><strong>Attribution:</strong> {_e(attr_source)}</p>'
                )

        # Code under review
        if code_under_review:
            parts.append(
                f'<p class="detail"><strong>Code under review:</strong></p>'
                f"<pre>{_e(code_under_review)}</pre>"
            )

        # Explanation
        if explanation:
            parts.append(f'<p class="detail"><strong>Explanation:</strong> {_e(explanation)}</p>')

        # Evidence
        if tool_calls or code_refs:
            parts.append('<div class="evidence">')
            parts.append("<strong>Evidence:</strong>")
            if tool_calls:
                parts.append("<p>Tool calls:</p><ul>")
                for tc in tool_calls:
                    parts.append(f"<li>{_e(tc)}</li>")
                parts.append("</ul>")
            if code_refs:
                parts.append("<p>Code references:</p><ul>")
                for cr in code_refs:
                    parts.append(f"<li>{_e(cr)}</li>")
                parts.append("</ul>")
            parts.append("</div>")  # end evidence

        # Recommendation
        if recommendation:
            parts.append('<div class="recommendation">')
            parts.append("<strong>Recommendation:</strong>")
            parts.append(f"<pre>{_e(recommendation)}</pre>")
            parts.append("</div>")

        # CWE
        if cwe:
            parts.append(f'<p class="detail"><strong>CWE:</strong> {_e(cwe)}</p>')

        # Related findings
        if related:
            parts.append(
                f'<p class="detail"><strong>Related findings:</strong> '
                f"{', '.join(_e(r) for r in related)}</p>"
            )

        # Cluster
        if cluster:
            parts.append(
                f'<p class="detail"><strong>Cluster:</strong> {_e(cluster)}</p>'
            )

        parts.append("</div>")  # end finding card
        return "\n".join(parts)
