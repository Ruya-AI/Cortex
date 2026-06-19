from __future__ import annotations

import html
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _e(v) -> str:
    if not v:
        return ""
    return html.escape(_CONTROL_CHARS.sub("", str(v)))


class ExecutiveReportResult:
    def __init__(self, data: dict, json_path: Path | None = None, pdf_path: Path | None = None):
        self.data = data
        self.json_path = json_path
        self.pdf_path = pdf_path


class ExecutiveReportGenerator:

    def generate(
        self,
        full_report: dict,
        output_dir: Path,
        file_stem: str,
        formats: list[str] | None = None,
    ) -> dict:
        formats = formats or ["json"]
        findings = full_report.get("findings", [])
        items = self._curate(findings)
        total = len(findings)
        actionable = len(items)

        # Risk computed from ALL findings (not just curated)
        risk = self._compute_risk(findings)

        categories, exclusion_reasons = self._summarize(findings, items)

        must_fix = [i for i in items if i["severity"] in ("critical", "high")]
        should_fix = [i for i in items if i["severity"] == "medium"]
        consider = [i for i in items if i["severity"] not in ("critical", "high", "medium")]

        data = {
            "report_id": full_report.get("report_metadata", {}).get("report_id", ""),
            "generated_at": full_report.get("report_metadata", {}).get("generated_at", ""),
            "repository": full_report.get("repository_context", {}).get("repository", ""),
            "branch": full_report.get("repository_context", {}).get("branch", ""),
            "commit": full_report.get("repository_context", {}).get("commit_sha", "")[:12],
            "risk": risk,
            "total": total,
            "actionable": actionable,
            "must_fix_count": len(must_fix),
            "should_fix_count": len(should_fix),
            "consider_count": len(consider),
            "noise_removed": f"{round((total - actionable) / max(total, 1) * 100)}%",
            "items": items[:20],
            "categories": categories,
            "exclusion_reasons": exclusion_reasons,
        }

        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = pdf_path = None

        if "json" in formats:
            json_path = output_dir / f"{file_stem}-executive.json"
            json_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

        if "pdf" in formats:
            pdf_path = output_dir / f"{file_stem}-executive.pdf"
            self._write_pdf(data, pdf_path)

        return {"data": data, "json_path": json_path, "pdf_path": pdf_path}

    def _compute_risk(self, findings: list[dict]) -> str:
        """Compute risk from ALL findings (not just curated)."""
        for f in findings:
            sev = self._normalize_severity(f.get("severity", "info"))
            if sev == "critical":
                return "CRITICAL"
        for f in findings:
            sev = self._normalize_severity(f.get("severity", "info"))
            if sev == "high":
                return "HIGH"
        for f in findings:
            sev = self._normalize_severity(f.get("severity", "info"))
            if sev == "medium":
                return "MEDIUM"
        return "CLEAN"

    def _normalize_severity(self, sev) -> str:
        if isinstance(sev, int):
            return {4: "critical", 3: "high", 2: "medium", 1: "low", 0: "info"}.get(sev, "info")
        return str(sev).lower()

    def _curate(self, findings: list[dict]) -> list[dict]:
        items = []
        for f in findings:
            sev = self._normalize_severity(f.get("severity", "info"))
            conf = f.get("confidence", "likely")
            if isinstance(conf, int):
                conf = {2: "confirmed", 1: "likely", 0: "uncertain"}.get(conf, "likely")
            classification = str(f.get("classification", "")).lower()

            if conf == "uncertain":
                continue
            if classification == "pre_existing" and sev != "critical":
                continue
            if sev in ("low", "info"):
                continue
            # A named source IS evidence -- don't filter out tool findings
            has_source = bool(f.get("source", ""))
            ev = f.get("evidence", {})
            if isinstance(ev, dict) and not ev.get("tool_calls") and not ev.get("code_references") and not has_source:
                continue

            cat = f.get("category", "unknown")
            if isinstance(cat, int):
                cat = str(cat)
            elif hasattr(cat, "value"):
                cat = cat.value

            items.append({
                "source": f.get("id", ""),
                "severity": sev,
                "category": cat,
                "file": f.get("file", ""),
                "line": f.get("start_line", 0),
                "issue": f.get("title", ""),
                "action": f.get("recommendation", ""),
            })
        return sorted(items, key=lambda x: {"critical": 0, "high": 1, "medium": 2}.get(x["severity"], 3))

    def _summarize(self, all_findings: list[dict], curated: list[dict]) -> tuple[list[dict], dict[str, int]]:
        cats: dict[str, dict] = {}
        for f in curated:
            cat = f.get("category", "unknown")
            if cat not in cats:
                cats[cat] = {"category": cat, "must_fix": 0, "should_fix": 0, "consider": 0, "total": 0}
            sev = f.get("severity", "")
            if sev in ("critical", "high"):
                cats[cat]["must_fix"] += 1
            elif sev == "medium":
                cats[cat]["should_fix"] += 1
            else:
                cats[cat]["consider"] += 1
            cats[cat]["total"] += 1

        reasons: dict[str, int] = {}
        for f in all_findings:
            sev = self._normalize_severity(f.get("severity", "info"))
            conf = f.get("confidence", "likely")
            if isinstance(conf, int):
                conf = {2: "confirmed", 1: "likely", 0: "uncertain"}.get(conf, "likely")
            classification = str(f.get("classification", "")).lower()

            # Check if this finding is in curated
            if any(
                c["file"] == f.get("file", "")
                and c["line"] == f.get("start_line", 0)
                and c["issue"] == f.get("title", "")
                for c in curated
            ):
                continue
            if conf == "uncertain":
                reasons["low confidence"] = reasons.get("low confidence", 0) + 1
            elif classification == "pre_existing" and sev != "critical":
                reasons["pre-existing, non-critical"] = reasons.get("pre-existing, non-critical", 0) + 1
            elif sev in ("low", "info"):
                reasons["low severity"] = reasons.get("low severity", 0) + 1
            else:
                reasons["no evidence"] = reasons.get("no evidence", 0) + 1

        return sorted(cats.values(), key=lambda x: -x["total"]), reasons

    def _write_pdf(self, data: dict, path: Path) -> None:
        risk = data.get("risk", "")
        rc = {"CRITICAL": "#c00", "HIGH": "#e65100", "MEDIUM": "#f9a825", "CLEAN": "#2e7d32"}.get(risk, "#666")
        sev_colors = {"critical": "#c00", "high": "#e65100", "medium": "#f9a825"}
        row_parts = []
        for idx, i in enumerate(data.get("items", []), 1):
            sc = sev_colors.get(i["severity"], "#666")
            row_parts.append(
                f'<tr><td style="text-align:center">{idx}</td>'
                f'<td style="color:{sc};font-weight:bold">{_e(i["severity"].upper())}</td>'
                f'<td>{_e(i.get("source", ""))}</td>'
                f'<td><code>{_e(i["file"])}:{i["line"]}</code></td>'
                f'<td>{_e(i["issue"])}</td><td>{_e(i["action"])}</td></tr>'
            )
        rows = "".join(row_parts) or '<tr><td colspan="6" style="text-align:center;color:green">Clean -- no actionable findings.</td></tr>'

        cat_rows = "".join(
            f'<tr><td>{_e(c["category"])}</td><td>{c["must_fix"]}</td><td>{c["should_fix"]}</td><td>{c["consider"]}</td><td><strong>{c["total"]}</strong></td></tr>'
            for c in data.get("categories", [])
        )

        excl = data.get("exclusion_reasons", {})
        excl_items = "".join(f"<li>{_e(r)}: {n}</li>" for r, n in sorted(excl.items(), key=lambda x: -x[1]))
        excluded_total = sum(excl.values())

        mf = data.get("must_fix_count", 0)
        sf = data.get("should_fix_count", 0)
        co = data.get("consider_count", 0)
        ac = data.get("actionable", 0)
        nr = data.get("noise_removed", "0%")

        h = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>QA Executive Report</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:850px;margin:0 auto;padding:20px;color:#333;font-size:13px}}
h1{{font-size:22px;color:#1a1a2e;border-bottom:3px solid #0f3460;padding-bottom:8px}}
h2{{font-size:15px;color:#0f3460;margin:20px 0 8px}}
.meta{{font-size:13px;margin:8px 0}}
.risk{{background:{rc};color:#fff;padding:12px 18px;border-radius:8px;margin:12px 0}}
.risk h2{{color:#fff;margin:0 0 4px;font-size:17px}}.risk p{{margin:0;font-size:13px}}
.stats{{display:flex;gap:12px;margin:12px 0;flex-wrap:wrap}}
.stat{{background:#f8f9fa;border:1px solid #dee2e6;border-radius:6px;padding:10px 16px;text-align:center;min-width:90px}}
.stat .num{{font-size:22px;font-weight:bold;color:#0f3460}}.stat .lbl{{font-size:10px;color:#6c757d;text-transform:uppercase}}
.noise-badge{{background:#e8f5e9;color:#2e7d32;padding:2px 8px;border-radius:4px;font-weight:600}}
table{{width:100%;border-collapse:collapse;margin:8px 0;table-layout:fixed}}
th,td{{padding:5px 8px;border:1px solid #dee2e6;text-align:left;font-size:12px;word-wrap:break-word}}
th{{background:#f1f3f5;font-weight:600}}
ul{{margin:4px 0;padding-left:20px;font-size:12px}}
.footer{{margin-top:25px;padding-top:8px;border-top:1px solid #ddd;font-size:10px;color:#999}}
</style></head><body>

<h1>QA Executive Report</h1>
<p class="meta"><strong>Repository:</strong> {_e(data.get('repository', ''))} &nbsp;|&nbsp;
<strong>Branch:</strong> {_e(data.get('branch', ''))} &nbsp;|&nbsp;
<strong>Commit:</strong> <code>{_e(data.get('commit', ''))}</code></p>

<div class="risk">
<h2>Risk Level: {_e(risk)}</h2>
<p>{ac} actionable findings out of {data.get('total', 0)} total.</p>
</div>

<div class="stats">
<div class="stat"><div class="num">{mf}</div><div class="lbl">Must Fix</div></div>
<div class="stat"><div class="num">{sf}</div><div class="lbl">Should Fix</div></div>
<div class="stat"><div class="num">{co}</div><div class="lbl">Consider</div></div>
<div class="stat"><div class="num">{ac}</div><div class="lbl">Actionable</div></div>
<div class="stat"><div class="num"><span class="noise-badge">{nr}</span></div><div class="lbl">Noise Removed</div></div>
</div>

<h2>Action Items</h2>
<table><colgroup><col style="width:4%"><col style="width:8%"><col style="width:10%"><col style="width:18%"><col style="width:25%"><col style="width:35%"></colgroup><tr><th>#</th><th>Severity</th><th>Source</th><th>Location</th><th>Finding</th><th>Action</th></tr>{rows}</table>

<h2>By Category</h2>
<table><tr><th>Category</th><th>Must Fix</th><th>Should Fix</th><th>Consider</th><th>Total</th></tr>{cat_rows}</table>

<h2>Noise Reduction</h2>
<p>Of {data.get('total', 0)} total findings in the full report, {excluded_total} were excluded from this executive summary:</p>
<ul>{excl_items}</ul>
<p>Full details available in the comprehensive report.</p>

<div class="footer">
Executive QA Report &mdash; {_e(data.get('report_id', ''))} &mdash; {_e(data.get('generated_at', ''))} &mdash; This platform identifies and reports. It does NOT modify code.
</div>

</body></html>"""
        try:
            from weasyprint import HTML
            HTML(string=h).write_pdf(str(path))
        except ImportError:
            path.with_suffix(".html").write_text(h, encoding="utf-8")
        except Exception as e:
            logger.error("PDF failed: %s", e)
