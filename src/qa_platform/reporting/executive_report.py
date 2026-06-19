from __future__ import annotations

import html
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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

_SEVERITY_RANK: dict[str, int] = {
    "critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0,
}

_RISK_COLORS: dict[str, str] = {
    "CRITICAL": "#c00",
    "HIGH": "#e65100",
    "MEDIUM": "#f9a825",
    "CLEAN": "#2e7d32",
}


def _e(value: Any) -> str:
    """Strip control characters then HTML-escape."""
    if value is None:
        return ""
    return html.escape(_CONTROL_CHARS.sub("", str(value)))


def _severity_str(val: Any) -> str:
    """Normalise a severity value (int or string) to lowercase name."""
    if isinstance(val, int):
        return {4: "critical", 3: "high", 2: "medium", 1: "low", 0: "info"}.get(val, "info")
    return str(val).lower()


def _confidence_str(val: Any) -> str:
    """Normalise a confidence value (int or string) to lowercase name."""
    if isinstance(val, int):
        return {2: "confirmed", 1: "likely", 0: "uncertain"}.get(val, "uncertain")
    return str(val).lower()


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class ExecutiveReportResult:
    """Return value from ExecutiveReportGenerator.generate()."""

    data: dict[str, Any] = field(default_factory=dict)
    json_path: Path | None = None
    pdf_path: Path | None = None


# ===================================================================
# ExecutiveReportGenerator
# ===================================================================


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
        risk_level = self._compute_risk_level(full_report_data.get("findings", []))

        # Noise reduction stats
        total = excluded_count + len(curated)
        noise_pct = round((excluded_count / total * 100), 1) if total else 0.0

        data: dict[str, Any] = {
            "risk_level": risk_level,
            "action_items": action_items,
            "category_summary": category_summary,
            "noise_reduction": {
                "total_findings": total,
                "included": len(curated),
                "excluded": excluded_count,
                "noise_percentage": noise_pct,
                "exclusion_reasons": exclusion_reasons,
            },
            "stats": {
                "must_fix": sum(
                    1 for ai in action_items
                    if ai.get("severity") in ("critical", "high")
                ),
                "should_fix": sum(
                    1 for ai in action_items if ai.get("severity") == "medium"
                ),
                "consider": sum(
                    1 for ai in action_items
                    if ai.get("severity") in ("low", "info")
                ),
                "actionable": len(action_items),
                "noise_removed": excluded_count,
            },
            "executive_summary": full_report_data.get("executive_summary", {}),
            "report_metadata": full_report_data.get("report_metadata", {}),
            "repository_context": full_report_data.get("repository_context", {}),
        }

        result: dict[str, Any] = {"data": data}

        # -- JSON output ---------------------------------------------------
        if "json" in formats:
            json_path = output_dir / f"{file_stem}-executive.json"
            json_path.write_text(
                json.dumps(data, indent=2, default=str), encoding="utf-8",
            )
            result["json_path"] = json_path
            logger.info("Executive JSON report written to %s", json_path)

        # -- PDF output (WeasyPrint with HTML fallback) --------------------
        if "pdf" in formats:
            pdf_path = output_dir / f"{file_stem}-executive.pdf"
            html_content = self._render_html(data)
            try:
                from weasyprint import HTML as WeasyprintHTML  # type: ignore[import-untyped]

                WeasyprintHTML(string=html_content).write_pdf(str(pdf_path))
                result["pdf_path"] = pdf_path
                logger.info("Executive PDF report written to %s", pdf_path)
            except ImportError:
                html_path = output_dir / f"{file_stem}-executive.html"
                html_path.write_text(html_content, encoding="utf-8")
                result["pdf_path"] = html_path
                logger.warning(
                    "WeasyPrint not available; HTML fallback written to %s",
                    html_path,
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
        - Pre-existing non-critical findings
        - Low/info severity
        - No evidence (empty tool_calls AND empty code_references)
        """
        kept: list[dict[str, Any]] = []
        excluded = 0
        reason_counts: dict[str, int] = {}

        for f in findings:
            confidence = _confidence_str(f.get("confidence", "likely"))
            severity = _severity_str(f.get("severity", "medium"))
            classification = str(f.get("classification", "unclassified")).lower()

            # Exclude uncertain confidence
            if confidence == "uncertain":
                excluded += 1
                reason_counts["low_confidence"] = reason_counts.get("low_confidence", 0) + 1
                continue

            # Exclude pre-existing non-critical
            if classification == "pre_existing" and severity != "critical":
                excluded += 1
                reason_counts["pre_existing_non_critical"] = (
                    reason_counts.get("pre_existing_non_critical", 0) + 1
                )
                continue

            # Exclude low/info severity
            if severity in ("low", "info"):
                excluded += 1
                reason_counts["low_severity"] = reason_counts.get("low_severity", 0) + 1
                continue

            # Exclude no-evidence findings — but a named source tool IS evidence
            has_source = bool(f.get("source", ""))
            evidence = f.get("evidence", {})
            tool_calls = evidence.get("tool_calls", []) if isinstance(evidence, dict) else []
            code_refs = evidence.get("code_references", []) if isinstance(evidence, dict) else []
            if not tool_calls and not code_refs and not has_source:
                excluded += 1
                reason_counts["no_evidence"] = reason_counts.get("no_evidence", 0) + 1
                continue

            kept.append(f)

        reasons: list[str] = []
        for reason, count in reason_counts.items():
            reasons.append(f"{reason}: {count}")

        return kept, excluded, reasons

    # ------------------------------------------------------------------
    # Action items
    # ------------------------------------------------------------------

    def _build_action_items(
        self, curated: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Build numbered action items sorted by severity descending."""
        items: list[dict[str, Any]] = []
        for idx, f in enumerate(curated, 1):
            severity = _severity_str(f.get("severity", "medium"))
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

    def _build_category_summary(
        self, curated: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Group curated findings by category with Must Fix / Should Fix / Consider counts."""
        by_category: dict[str, dict[str, int]] = {}
        for f in curated:
            cat = str(f.get("category", "uncategorised")).lower()
            severity = _severity_str(f.get("severity", "medium"))
            if cat not in by_category:
                by_category[cat] = {
                    "must_fix": 0, "should_fix": 0, "consider": 0, "total": 0,
                }
            by_category[cat]["total"] += 1
            if severity in ("critical", "high"):
                by_category[cat]["must_fix"] += 1
            elif severity == "medium":
                by_category[cat]["should_fix"] += 1
            else:
                by_category[cat]["consider"] += 1

        summary: list[dict[str, Any]] = []
        for cat, counts in sorted(by_category.items()):
            summary.append({"category": cat, **counts})
        return summary

    # ------------------------------------------------------------------
    # Risk level
    # ------------------------------------------------------------------

    def _compute_risk_level(self, curated: list[dict[str, Any]]) -> str:
        """Determine overall risk level from curated findings."""
        severities = {_severity_str(f.get("severity", "")) for f in curated}
        if "critical" in severities:
            return "CRITICAL"
        if "high" in severities:
            return "HIGH"
        if "medium" in severities:
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
        stats = data.get("stats", {})
        repo = data.get("repository_context", {})
        meta = data.get("report_metadata", {})

        risk_color = _RISK_COLORS.get(risk_level, "#2e7d32")

        parts: list[str] = []

        # -- HTML head + CSS -----------------------------------------------
        parts.append("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>QA Executive Report</title>
<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
    max-width: 960px;
    margin: 2rem auto;
    padding: 0 1rem;
    color: #212529;
    font-size: 13px;
    line-height: 1.5;
  }
  h1 { color: #1a1a2e; margin-bottom: 0.25rem; }
  h2 { color: #1a1a2e; margin-top: 1.5rem; }
  .subtitle { color: #666; font-size: 12px; margin-bottom: 1.5rem; }
  .risk {
    display: inline-block;
    color: #fff;
    padding: 0.5rem 1.2rem;
    border-radius: 4px;
    font-weight: 700;
    font-size: 1.1rem;
    margin: 0.5rem 0 1rem 0;
  }
  .stats {
    display: flex;
    flex-direction: row;
    gap: 0.75rem;
    margin: 1rem 0;
    flex-wrap: wrap;
  }
  .stat {
    border: 1px solid #dee2e6;
    border-radius: 6px;
    padding: 0.6rem 1rem;
    text-align: center;
    min-width: 90px;
    background: #fff;
  }
  .stat .num {
    font-size: 22px;
    font-weight: 700;
    display: block;
  }
  .stat .lbl {
    font-size: 10px;
    text-transform: uppercase;
    color: #666;
    display: block;
    margin-top: 2px;
  }
  .noise-badge {
    display: inline-block;
    background: #28a745;
    color: #fff;
    padding: 0.15rem 0.5rem;
    border-radius: 3px;
    font-size: 11px;
    font-weight: 600;
  }
  .severity-badge {
    display: inline-block;
    color: #fff;
    padding: 0.15rem 0.45rem;
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
    padding: 0.4rem 0.5rem;
    border: 1px solid #dee2e6;
    text-align: left;
    word-wrap: break-word;
    overflow-wrap: break-word;
  }
  .action-table thead th {
    background: #e9ecef;
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
  }
  .action-table tbody tr:nth-child(even) { background: #f8f9fa; }
  .meta-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 1.5rem;
  }
  .meta-table th, .meta-table td {
    padding: 0.4rem 0.6rem;
    border: 1px solid #dee2e6;
    text-align: left;
  }
  .meta-table thead th {
    background: #e9ecef;
    font-weight: 600;
  }
  .meta-table tbody tr:nth-child(even) { background: #f8f9fa; }
  .footer {
    margin-top: 2rem;
    padding-top: 0.75rem;
    border-top: 1px solid #dee2e6;
    color: #888;
    font-size: 11px;
  }
</style>
</head>
<body>
<h1>QA Executive Report</h1>""")

        # Repository / Branch / Commit line
        repo_name = repo.get("repository", "")
        branch = repo.get("branch", "")
        commit_sha = repo.get("commit_sha", "")
        short_sha = commit_sha[:8] if commit_sha else ""
        parts.append(
            f'<p class="subtitle">{_e(repo_name)} / {_e(branch)} / {_e(short_sha)}</p>'
        )

        # Risk level box
        parts.append(
            f'<div><span class="risk" style="background:{risk_color};">'
            f"Risk: {_e(risk_level)}</span></div>"
        )

        # Stats cards row
        must_fix = stats.get("must_fix", 0)
        should_fix = stats.get("should_fix", 0)
        consider = stats.get("consider", 0)
        actionable = stats.get("actionable", 0)
        noise_removed = stats.get("noise_removed", 0)

        parts.append('<div class="stats">')
        parts.append(
            f'<div class="stat"><span class="num" style="color:#dc3545;">'
            f"{must_fix}</span>"
            f'<span class="lbl">Must Fix</span></div>'
        )
        parts.append(
            f'<div class="stat"><span class="num" style="color:#fd7e14;">'
            f"{should_fix}</span>"
            f'<span class="lbl">Should Fix</span></div>'
        )
        parts.append(
            f'<div class="stat"><span class="num" style="color:#ffc107;">'
            f"{consider}</span>"
            f'<span class="lbl">Consider</span></div>'
        )
        parts.append(
            f'<div class="stat"><span class="num">{actionable}</span>'
            f'<span class="lbl">Actionable</span></div>'
        )
        parts.append(
            f'<div class="stat"><span class="num">{noise_removed}</span>'
            f'<span class="lbl">Noise Removed '
            f'<span class="noise-badge">{noise.get("noise_percentage", 0)}%</span>'
            f"</span></div>"
        )
        parts.append("</div>")  # end stats

        # Action Items table
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
                    f"{_e(sev.upper())}</span></td>"
                    f"<td>{_e(item.get('source', ''))}</td>"
                    f"<td>{_e(item.get('location', ''))}</td>"
                    f"<td>{_e(item.get('finding', ''))}</td>"
                    f"<td>{_e(item.get('action', ''))}</td>"
                    f"</tr>"
                )
            parts.append("</tbody></table>")
        else:
            parts.append("<p>No action items -- code looks clean.</p>")

        # By Category table (Must Fix / Should Fix / Consider / Total)
        parts.append("<h2>By Category</h2>")
        if category_summary:
            parts.append(
                '<table class="meta-table">'
                "<thead><tr>"
                "<th>Category</th><th>Must Fix</th><th>Should Fix</th>"
                "<th>Consider</th><th>Total</th>"
                "</tr></thead><tbody>"
            )
            for row in category_summary:
                parts.append(
                    f"<tr>"
                    f"<td>{_e(row.get('category', ''))}</td>"
                    f"<td>{row.get('must_fix', 0)}</td>"
                    f"<td>{row.get('should_fix', 0)}</td>"
                    f"<td>{row.get('consider', 0)}</td>"
                    f"<td>{row.get('total', 0)}</td>"
                    f"</tr>"
                )
            parts.append("</tbody></table>")
        else:
            parts.append("<p>No category data.</p>")

        # Noise Reduction section
        parts.append("<h2>Noise Reduction</h2>")
        parts.append(
            f"<p><strong>Total findings:</strong> {noise.get('total_findings', 0)} | "
            f"<strong>Actionable:</strong> {noise.get('included', 0)} | "
            f"<strong>Excluded:</strong> {noise.get('excluded', 0)} "
            f'<span class="noise-badge">{noise.get("noise_percentage", 0)}% noise</span></p>'
        )
        exclusion_reasons = noise.get("exclusion_reasons", [])
        if exclusion_reasons:
            parts.append("<ul>")
            for reason in exclusion_reasons:
                parts.append(f"<li>{_e(reason)}</li>")
            parts.append("</ul>")

        # Footer
        report_id = meta.get("report_id", "")
        generated_at = meta.get("generated_at", "")
        parts.append('<div class="footer">')
        parts.append(
            f"<p>Report ID: {_e(report_id)} | Generated: {_e(generated_at)}</p>"
        )
        parts.append(
            "<p>This report is generated for audit and informational purposes only. "
            "Findings are advisory and do not block merges.</p>"
        )
        parts.append("</div>")

        parts.append("</body></html>")
        return "\n".join(parts)
