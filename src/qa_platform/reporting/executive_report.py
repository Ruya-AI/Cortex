from __future__ import annotations

import html
import json
import logging
from pathlib import Path
from typing import Any

from qa_platform.core.text_sanitizer import sanitize

logger = logging.getLogger(__name__)

SEVERITY_COLORS: dict[str, str] = {
    "critical": "#dc3545",
    "high": "#fd7e14",
    "medium": "#ffc107",
    "low": "#28a745",
    "info": "#6c757d",
}

_SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


def _escape(value: Any) -> str:
    """Sanitize control characters then HTML-escape."""
    return html.escape(sanitize(str(value)))


class ExecutiveReportGenerator:
    """Curated executive report -- high-signal action items only."""

    def generate(
        self,
        full_report_data: dict[str, Any],
        output_dir: Path,
        file_stem: str,
        formats: list[str],
    ) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)

        curated, excluded_count, exclusion_reasons = self._curate(
            full_report_data.get("findings", []),
        )

        action_items = self._build_action_items(curated)
        category_summary = self._build_category_summary(curated)
        risk_level = self._compute_risk_level(curated)

        data: dict[str, Any] = {
            "risk_level": risk_level,
            "action_items": action_items,
            "category_summary": category_summary,
            "noise_reduction": {
                "total_findings": excluded_count + len(curated),
                "included": len(curated),
                "excluded": excluded_count,
                "exclusion_reasons": exclusion_reasons,
            },
            "executive_summary": full_report_data.get("executive_summary", {}),
            "report_metadata": full_report_data.get("report_metadata", {}),
        }

        result: dict[str, Any] = {"data": data}

        if "json" in formats:
            json_path = output_dir / f"{file_stem}.json"
            json_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            result["json_path"] = json_path
            logger.info("Executive JSON report written to %s", json_path)

        if "pdf" in formats:
            pdf_path = output_dir / f"{file_stem}.pdf"
            html_content = self._render_html(data)
            try:
                from weasyprint import HTML as WeasyprintHTML  # type: ignore[import-untyped]

                WeasyprintHTML(string=html_content).write_pdf(str(pdf_path))
                result["pdf_path"] = pdf_path
                logger.info("Executive PDF report written to %s", pdf_path)
            except ImportError:
                html_path = output_dir / f"{file_stem}.html"
                html_path.write_text(html_content, encoding="utf-8")
                result["pdf_path"] = html_path
                logger.warning(
                    "WeasyPrint not available; HTML fallback written to %s", html_path,
                )

        return result

    # ------------------------------------------------------------------
    # Curation -- filter noise
    # ------------------------------------------------------------------

    def _curate(
        self,
        findings: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], int, list[str]]:
        """Filter out low-signal findings.

        Exclusion criteria:
        - Low confidence (uncertain)
        - Low/info severity
        - Pre-existing non-critical findings
        """
        kept: list[dict[str, Any]] = []
        excluded = 0
        reasons: list[str] = []
        reason_counts: dict[str, int] = {}

        for f in findings:
            confidence = str(f.get("confidence", "likely")).lower()
            severity = str(f.get("severity", "medium")).lower()
            classification = str(f.get("classification", "unclassified")).lower()

            # Exclude uncertain confidence
            if confidence == "uncertain" or confidence == "0":
                excluded += 1
                reason_counts["low_confidence"] = reason_counts.get("low_confidence", 0) + 1
                continue

            # Exclude low/info severity
            if severity in ("low", "info", "0", "1"):
                excluded += 1
                reason_counts["low_severity"] = reason_counts.get("low_severity", 0) + 1
                continue

            # Exclude pre-existing non-critical
            if classification == "pre_existing" and severity not in ("critical", "4"):
                excluded += 1
                reason_counts["pre_existing_non_critical"] = (
                    reason_counts.get("pre_existing_non_critical", 0) + 1
                )
                continue

            kept.append(f)

        for reason, count in reason_counts.items():
            reasons.append(f"{reason}: {count}")

        return kept, excluded, reasons

    # ------------------------------------------------------------------
    # Action items
    # ------------------------------------------------------------------

    def _build_action_items(self, curated: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for idx, f in enumerate(curated, 1):
            severity = str(f.get("severity", "medium")).lower()
            source = str(f.get("source", ""))
            file_path = str(f.get("file", ""))
            start_line = f.get("start_line", "")
            location = f"{file_path}:{start_line}" if start_line else file_path
            title = str(f.get("title", ""))
            recommendation = str(f.get("recommendation", ""))

            items.append({
                "number": idx,
                "severity": severity,
                "source": source,
                "location": location,
                "finding": title,
                "action": recommendation,
            })

        # Sort by severity descending
        items.sort(key=lambda x: _SEVERITY_RANK.get(x["severity"], 0), reverse=True)
        # Re-number after sort
        for idx, item in enumerate(items, 1):
            item["number"] = idx

        return items

    # ------------------------------------------------------------------
    # Category summary
    # ------------------------------------------------------------------

    def _build_category_summary(self, curated: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_category: dict[str, dict[str, int]] = {}
        for f in curated:
            cat = str(f.get("category", "uncategorised")).lower()
            severity = str(f.get("severity", "medium")).lower()
            if cat not in by_category:
                by_category[cat] = {"total": 0, "critical": 0, "high": 0, "medium": 0}
            by_category[cat]["total"] += 1
            if severity in by_category[cat]:
                by_category[cat][severity] += 1

        summary: list[dict[str, Any]] = []
        for cat, counts in sorted(by_category.items()):
            summary.append({"category": cat, **counts})
        return summary

    # ------------------------------------------------------------------
    # Risk level
    # ------------------------------------------------------------------

    def _compute_risk_level(self, curated: list[dict[str, Any]]) -> str:
        severities = {str(f.get("severity", "")).lower() for f in curated}
        if "critical" in severities or "4" in severities:
            return "CRITICAL"
        if "high" in severities or "3" in severities:
            return "HIGH"
        if "medium" in severities or "2" in severities:
            return "MEDIUM"
        return "CLEAN"

    # ------------------------------------------------------------------
    # HTML rendering
    # ------------------------------------------------------------------

    def _render_html(self, data: dict[str, Any]) -> str:
        risk_level = data.get("risk_level", "CLEAN")
        action_items = data.get("action_items", [])
        category_summary = data.get("category_summary", [])
        noise = data.get("noise_reduction", {})

        risk_color = SEVERITY_COLORS.get(risk_level.lower(), "#28a745")

        parts: list[str] = []
        parts.append(self._html_head())

        # Risk level header
        parts.append(
            f'<div class="risk-header" style="border-left-color: {risk_color};">'
            f"<h2>Risk Level: "
            f'<span style="color: {risk_color};">{_escape(risk_level)}</span>'
            f"</h2></div>"
        )

        # Action items table
        parts.append("<h2>Action Items</h2>")
        if action_items:
            parts.append("""<table class="action-table">
<colgroup>
  <col style="width: 4%;">
  <col style="width: 8%;">
  <col style="width: 10%;">
  <col style="width: 18%;">
  <col style="width: 25%;">
  <col style="width: 35%;">
</colgroup>
<thead>
  <tr><th>#</th><th>Severity</th><th>Source</th><th>Location</th><th>Finding</th><th>Action</th></tr>
</thead>
<tbody>""")
            for item in action_items:
                sev = item.get("severity", "medium")
                color = SEVERITY_COLORS.get(sev, "#6c757d")
                parts.append(
                    f"<tr>"
                    f"<td>{item.get('number', '')}</td>"
                    f'<td><span class="severity-badge" style="background:{color};">'
                    f"{_escape(sev.upper())}</span></td>"
                    f"<td>{_escape(item.get('source', ''))}</td>"
                    f"<td>{_escape(item.get('location', ''))}</td>"
                    f"<td>{_escape(item.get('finding', ''))}</td>"
                    f"<td>{_escape(item.get('action', ''))}</td>"
                    f"</tr>"
                )
            parts.append("</tbody></table>")
        else:
            parts.append("<p>No action items.</p>")

        # Category summary table
        parts.append("<h2>By Category</h2>")
        if category_summary:
            parts.append(
                '<table class="meta-table">'
                "<thead><tr><th>Category</th><th>Total</th>"
                "<th>Critical</th><th>High</th><th>Medium</th></tr></thead><tbody>"
            )
            for row in category_summary:
                parts.append(
                    f"<tr>"
                    f"<td>{_escape(row.get('category', ''))}</td>"
                    f"<td>{row.get('total', 0)}</td>"
                    f"<td>{row.get('critical', 0)}</td>"
                    f"<td>{row.get('high', 0)}</td>"
                    f"<td>{row.get('medium', 0)}</td>"
                    f"</tr>"
                )
            parts.append("</tbody></table>")

        # Noise reduction
        parts.append("<h2>Noise Reduction</h2>")
        parts.append(
            f"<p><strong>Total findings:</strong> {noise.get('total_findings', 0)} | "
            f"<strong>Included:</strong> {noise.get('included', 0)} | "
            f"<strong>Excluded:</strong> {noise.get('excluded', 0)}</p>"
        )
        exclusion_reasons = noise.get("exclusion_reasons", [])
        if exclusion_reasons:
            parts.append("<ul>")
            for reason in exclusion_reasons:
                parts.append(f"<li>{_escape(reason)}</li>")
            parts.append("</ul>")

        parts.append("</body></html>")
        return "\n".join(parts)

    def _html_head(self) -> str:
        return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Executive QA Report</title>
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
  h1, h2 { color: #343a40; }
  .risk-header {
    border-left: 5px solid;
    padding: 0.5rem 1rem;
    margin: 1rem 0;
    background: #f8f9fa;
    border-radius: 4px;
  }
  .severity-badge {
    display: inline-block;
    color: #fff;
    padding: 0.2rem 0.5rem;
    border-radius: 3px;
    font-size: 0.8rem;
    font-weight: 600;
  }
  .action-table {
    width: 100%;
    table-layout: fixed;
    border-collapse: collapse;
    margin-bottom: 1.5rem;
  }
  .action-table th, .action-table td {
    padding: 0.5rem 0.6rem;
    border: 1px solid #dee2e6;
    text-align: left;
    word-wrap: break-word;
    overflow-wrap: break-word;
  }
  .action-table thead th {
    background: #e9ecef;
    font-weight: 600;
  }
  .action-table tbody tr:nth-child(even) { background: #f8f9fa; }
  .meta-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 1.5rem;
  }
  .meta-table th, .meta-table td {
    padding: 0.5rem 0.75rem;
    border: 1px solid #dee2e6;
    text-align: left;
  }
  .meta-table thead th { background: #e9ecef; }
  .meta-table tbody tr:nth-child(even) { background: #f8f9fa; }
  pre {
    background: #f8f9fa;
    padding: 0.75rem 1rem;
    border-radius: 4px;
    overflow-x: auto;
    font-size: 0.9rem;
  }
</style>
</head>
<body>
<h1>Executive QA Report</h1>"""
