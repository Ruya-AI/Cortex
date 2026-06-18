from __future__ import annotations

import html
import json
import logging
import re
from pathlib import Path
from typing import Any

from qa_platform.core.finding import Finding
from qa_platform.core.schemas import QualityGateResult, RepositoryContext, FindingCluster
from qa_platform.core.text_sanitizer import sanitize

logger = logging.getLogger(__name__)

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

SEVERITY_COLORS: dict[str, str] = {
    "critical": "#dc3545",
    "high": "#fd7e14",
    "medium": "#ffc107",
    "low": "#28a745",
    "info": "#6c757d",
}


def _escape(value: Any) -> str:
    """Sanitize control characters then HTML-escape."""
    return html.escape(sanitize(str(value)))


class ReportGenerator:
    """Full 11-section QA report generator (JSON + PDF/HTML)."""

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

        if "json" in formats:
            json_path = output_dir / f"{file_stem}.json"
            json_path.write_text(json.dumps(report_data, indent=2, default=str), encoding="utf-8")
            result["json_path"] = json_path
            logger.info("JSON report written to %s", json_path)

        if "pdf" in formats:
            pdf_path = output_dir / f"{file_stem}.pdf"
            html_content = self._render_html(report_data)
            try:
                from weasyprint import HTML as WeasyprintHTML  # type: ignore[import-untyped]

                WeasyprintHTML(string=html_content).write_pdf(str(pdf_path))
                result["pdf_path"] = pdf_path
                logger.info("PDF report written to %s", pdf_path)
            except ImportError:
                html_path = output_dir / f"{file_stem}.html"
                html_path.write_text(html_content, encoding="utf-8")
                result["pdf_path"] = html_path
                logger.warning(
                    "WeasyPrint not available; HTML fallback written to %s", html_path,
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
        from qa_platform.core.finding import Severity, Confidence, Classification, LifecycleState

        # Partition findings
        active = [f for f in findings if f.lifecycle_state == LifecycleState.OPEN]
        suppressed = [f for f in findings if f.lifecycle_state == LifecycleState.SUPPRESSED]
        resolved = [f for f in findings if f.lifecycle_state == LifecycleState.RESOLVED]

        # Build finding clusters from active findings
        clusters_by_id: dict[str, list[str]] = {}
        for f in active:
            if f.root_cause_cluster:
                clusters_by_id.setdefault(f.root_cause_cluster, []).append(f.id)

        finding_clusters = [
            {"cluster_id": cid, "finding_ids": fids, "count": len(fids)}
            for cid, fids in clusters_by_id.items()
        ]

        # Positive observations
        positive_observations: list[str] = []
        if not any(f.severity >= Severity.HIGH for f in active):
            positive_observations.append("No high or critical severity issues found.")
        if not active:
            positive_observations.append("No active findings -- code looks clean.")

        return {
            "report_metadata": {
                "report_id": scan_metadata.get("report_id", ""),
                "trigger": scan_metadata.get("trigger", ""),
                "tiers": scan_metadata.get("tiers", []),
                "duration": scan_metadata.get("duration", 0.0),
                "cost": scan_metadata.get("cost", 0.0),
                "models_used": scan_metadata.get("models_used", []),
                "agents_used": scan_metadata.get("agents_used", []),
            },
            "repository_context": {
                "local_path": str(repo_context.local_path),
                "branch": repo_context.branch,
                "commit_sha": repo_context.commit_sha,
                "commit_message": repo_context.commit_message,
                "remote_url": repo_context.remote_url,
            },
            "attribution": {
                "authors": list(
                    {
                        f.author.name
                        for f in findings
                        if f.author and f.author.name
                    }
                ),
            },
            "scope_summary": {
                "total_files_reviewed": len({f.file for f in findings}),
                "total_findings": len(findings),
                "active_findings": len(active),
                "suppressed_findings": len(suppressed),
                "resolved_findings": len(resolved),
            },
            "executive_summary": {
                "quality_gate_status": gate_result.status,
                "quality_gate_mode": gate_result.mode,
                "quality_gate_reasoning": gate_result.reasoning,
                "severity_counts": gate_result.severity_counts,
                "blocking_findings": gate_result.blocking_findings,
            },
            "findings": [f.to_dict() for f in active],
            "finding_clusters": finding_clusters,
            "resolved_issues": [f.to_dict() for f in resolved],
            "positive_observations": positive_observations,
            "suppressed_findings": [f.to_dict() for f in suppressed],
            "appendix": {
                "config_snapshot": config,
            },
        }

    # ------------------------------------------------------------------
    # HTML / PDF rendering
    # ------------------------------------------------------------------

    def _render_html(self, report_data: dict[str, Any]) -> str:
        meta = report_data.get("report_metadata", {})
        repo = report_data.get("repository_context", {})
        exec_summary = report_data.get("executive_summary", {})
        scope = report_data.get("scope_summary", {})
        findings = report_data.get("findings", [])
        clusters = report_data.get("finding_clusters", [])
        resolved = report_data.get("resolved_issues", [])
        positive = report_data.get("positive_observations", [])
        suppressed = report_data.get("suppressed_findings", [])

        parts: list[str] = []
        parts.append(self._html_head(meta.get("report_id", "")))

        # 1. Report metadata table
        parts.append("<h2>Report Metadata</h2>")
        parts.append(self._meta_table(meta))

        # 2. Repository context
        parts.append("<h2>Repository Context</h2>")
        parts.append(self._meta_table(repo))

        # 3. Attribution
        attribution = report_data.get("attribution", {})
        authors = attribution.get("authors", [])
        if authors:
            parts.append("<h2>Attribution</h2>")
            parts.append("<p>" + ", ".join(_escape(a) for a in authors) + "</p>")

        # 4. Scope summary
        parts.append("<h2>Scope Summary</h2>")
        parts.append(self._meta_table(scope))

        # 5. Executive summary
        parts.append('<div class="executive-summary">')
        parts.append("<h2>Executive Summary</h2>")
        status = exec_summary.get("quality_gate_status", "pass")
        mode = exec_summary.get("quality_gate_mode", "shadow")
        reasoning = exec_summary.get("quality_gate_reasoning", "")
        parts.append(f"<p><strong>Gate status:</strong> {_escape(status)} ({_escape(mode)})</p>")
        parts.append(f"<p>{_escape(reasoning)}</p>")
        sev_counts = exec_summary.get("severity_counts", {})
        if sev_counts:
            badges = []
            for sev_name in ("critical", "high", "medium", "low", "info"):
                count = sev_counts.get(sev_name, 0)
                color = SEVERITY_COLORS.get(sev_name, "#6c757d")
                badges.append(
                    f'<span class="severity-badge" style="background:{color};">'
                    f"{_escape(sev_name.upper())}: {count}</span>"
                )
            parts.append("<p>" + " ".join(badges) + "</p>")
        parts.append("</div>")

        # 6. Findings
        parts.append("<h2>Findings</h2>")
        if findings:
            for f in findings:
                parts.append(self._render_finding_card(f))
        else:
            parts.append("<p>No active findings.</p>")

        # 7. Finding clusters
        if clusters:
            parts.append("<h2>Finding Clusters</h2>")
            for c in clusters:
                parts.append(
                    f"<p><strong>{_escape(c.get('cluster_id', ''))}</strong>: "
                    f"{c.get('count', 0)} findings "
                    f"({', '.join(_escape(fid) for fid in c.get('finding_ids', []))})</p>"
                )

        # 8. Resolved issues
        if resolved:
            parts.append("<h2>Resolved Issues</h2>")
            for r in resolved:
                parts.append(self._render_finding_card(r))

        # 9. Positive observations
        if positive:
            parts.append("<h2>Positive Observations</h2>")
            parts.append("<ul>")
            for obs in positive:
                parts.append(f"<li>{_escape(obs)}</li>")
            parts.append("</ul>")

        # 10. Suppressed findings
        if suppressed:
            parts.append("<h2>Suppressed Findings</h2>")
            parts.append(f"<p>{len(suppressed)} finding(s) suppressed.</p>")
            for s in suppressed:
                parts.append(self._render_finding_card(s))

        # 11. Appendix
        parts.append("<h2>Appendix</h2>")
        appendix = report_data.get("appendix", {})
        parts.append(f"<pre>{_escape(json.dumps(appendix, indent=2, default=str))}</pre>")

        parts.append("</body></html>")
        return "\n".join(parts)

    def _html_head(self, report_id: str) -> str:
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>QA Report {_escape(report_id)}</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
    max-width: 960px;
    margin: 2rem auto;
    padding: 0 1rem;
    color: #212529;
    line-height: 1.6;
  }}
  h1, h2 {{ color: #343a40; }}
  .meta-table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 1.5rem;
  }}
  .meta-table tr:nth-child(even) {{ background: #f8f9fa; }}
  .meta-table td, .meta-table th {{
    padding: 0.5rem 0.75rem;
    border: 1px solid #dee2e6;
    text-align: left;
  }}
  .meta-table th {{ background: #e9ecef; width: 30%; }}
  .executive-summary {{
    background: #f1f3f5;
    border-left: 4px solid #495057;
    padding: 1rem 1.5rem;
    margin: 1.5rem 0;
    border-radius: 4px;
  }}
  .severity-badge {{
    display: inline-block;
    color: #fff;
    padding: 0.2rem 0.6rem;
    border-radius: 3px;
    font-size: 0.85rem;
    font-weight: 600;
    margin-right: 0.4rem;
  }}
  .finding-card {{
    border: 1px solid #dee2e6;
    border-radius: 6px;
    margin: 1rem 0;
    padding: 1rem 1.25rem;
    border-left-width: 5px;
    border-left-style: solid;
  }}
  .finding-card h3 {{ margin-top: 0; }}
  .finding-card .detail {{ margin: 0.3rem 0; }}
  pre {{
    background: #f8f9fa;
    padding: 0.75rem 1rem;
    border-radius: 4px;
    overflow-x: auto;
    font-size: 0.9rem;
  }}
</style>
</head>
<body>
<h1>QA Report</h1>"""

    def _meta_table(self, data: dict[str, Any]) -> str:
        rows: list[str] = []
        for key, value in data.items():
            display_val = (
                json.dumps(value, default=str) if isinstance(value, (list, dict)) else str(value)
            )
            rows.append(
                f"<tr><th>{_escape(key)}</th><td>{_escape(display_val)}</td></tr>"
            )
        return f'<table class="meta-table">{"".join(rows)}</table>'

    def _render_finding_card(self, finding_dict: dict[str, Any]) -> str:
        severity = str(finding_dict.get("severity", "medium")).lower()
        color = SEVERITY_COLORS.get(severity, "#6c757d")
        title = finding_dict.get("title", "Untitled")
        fid = finding_dict.get("id", "")
        source = finding_dict.get("source", "")
        file_path = finding_dict.get("file", "")
        start_line = finding_dict.get("start_line", "")
        explanation = finding_dict.get("explanation", "")
        recommendation = finding_dict.get("recommendation", "")
        confidence = finding_dict.get("confidence", "")
        category = finding_dict.get("category", "")

        return f"""<div class="finding-card" style="border-left-color: {color};">
  <h3>
    <span class="severity-badge" style="background:{color};">{_escape(severity.upper())}</span>
    {_escape(title)}
  </h3>
  <p class="detail"><strong>ID:</strong> {_escape(fid)}</p>
  <p class="detail"><strong>Source:</strong> {_escape(source)} | <strong>Category:</strong> {_escape(category)}</p>
  <p class="detail"><strong>File:</strong> {_escape(file_path)}:{_escape(start_line)}</p>
  <p class="detail"><strong>Confidence:</strong> {_escape(confidence)}</p>
  <p class="detail"><strong>Explanation:</strong> {_escape(explanation)}</p>
  <p class="detail"><strong>Recommendation:</strong> {_escape(recommendation)}</p>
</div>"""
