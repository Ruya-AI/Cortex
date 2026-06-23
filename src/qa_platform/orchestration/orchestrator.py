from __future__ import annotations

import logging
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from qa_platform.core.finding import Finding
from qa_platform.core.schemas import (
    ChangeSet, FileSet, ProcessedFindings, QualityGateResult,
    RiskAssessment, ScanRequest, ScanResult, Tier1RunResult,
)

logger = logging.getLogger(__name__)


class ScanOrchestrator:
    def __init__(
        self,
        repository_resolver=None,
        change_detector=None,
        hygiene_checker=None,
        tier1_runner=None,
        risk_scorer=None,
        review_engine=None,
        validation_engine=None,
        finding_manager=None,
        quality_gate=None,
        report_generator=None,
        executive_report_generator=None,
        integration_dispatcher=None,
        config_loader=None,
        scan_repository=None,
        finding_repository=None,
        db_connection=None,
    ):
        self._repo_resolver = repository_resolver
        self._change_detector = change_detector
        self._hygiene_checker = hygiene_checker
        self._tier1_runner = tier1_runner
        self._risk_scorer = risk_scorer
        self._review_engine = review_engine
        self._validation_engine = validation_engine
        self._finding_manager = finding_manager
        self._quality_gate = quality_gate
        self._report_generator = report_generator
        self._executive_report_generator = executive_report_generator
        self._integration_dispatcher = integration_dispatcher
        self._config_loader = config_loader
        self._scan_repo = scan_repository
        self._finding_repo = finding_repository
        self._db_conn = db_connection

    def scan(self, request: ScanRequest, progress: Callable[[str], None] | None = None) -> ScanResult:
        start = time.time()
        scan_id = f"QA-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
        errors: list[str] = []
        repo_context = None
        all_findings_backup: list = []

        def _progress(msg: str) -> None:
            if progress:
                progress(msg)

        try:
            # Phase 1: Load config
            _progress("Loading configuration...")
            config = {}
            if self._config_loader:
                try:
                    cfg_obj = self._config_loader(Path(request.repo) if not request.repo.startswith("http") else Path("."))
                    config = cfg_obj.model_dump() if hasattr(cfg_obj, "model_dump") else {}
                except Exception as e:
                    logger.warning("Config load failed, using defaults: %s", e)

            # Phase 2: Resolve repository
            _progress("Resolving repository...")
            if self._repo_resolver:
                repo_context = self._repo_resolver.resolve(request)
            else:
                repo_context_module = __import__("qa_platform.core.schemas", fromlist=["RepositoryContext"])
                RepositoryContext = repo_context_module.RepositoryContext
                repo_context = RepositoryContext(local_path=Path(request.repo).resolve())

            repo_path = repo_context.local_path

            # Phase 3: Detect changes
            _progress("Detecting changes...")
            change_set = ChangeSet(is_full_scan=request.full_scan)
            if self._change_detector:
                try:
                    change_set = self._change_detector.detect(repo_context, request)
                except Exception as e:
                    logger.warning("Change detection failed: %s", e)
                    errors.append(f"Change detection: {e}")

            # Phase 4: Hygiene check
            _progress("Checking file hygiene...")
            file_set = FileSet()
            if self._hygiene_checker:
                try:
                    file_set = self._hygiene_checker.check(repo_context, change_set, config)
                except Exception as e:
                    logger.warning("Hygiene check failed: %s", e)
                    # Fall back to changed files
                    file_set = FileSet(reviewable_files=[fc.file_path for fc in change_set.changed_files])

            if not file_set.reviewable_files:
                # If no reviewable files from hygiene, use changed files
                file_set.reviewable_files = [fc.file_path for fc in change_set.changed_files]

            # For full scan without change detection, list all files
            if request.full_scan and not file_set.reviewable_files:
                file_set.reviewable_files = self._list_all_files(repo_path)

            _progress(f"Found {len(file_set.reviewable_files)} reviewable files")

            # Phase 5: Tier 1 tools
            tier1_result = Tier1RunResult()
            if 1 in request.tiers and self._tier1_runner:
                _progress(f"Running Tier 1 tools on {len(file_set.reviewable_files)} files...")
                try:
                    tier1_result = self._tier1_runner.run(repo_path, file_set.reviewable_files, request.trigger)
                    _progress(f"  Tier 1 complete: {tier1_result.finding_count} findings from {len(tier1_result.tools_available)} tools")
                except Exception as e:
                    logger.error("Tier 1 failed: %s", e)
                    errors.append(f"Tier 1: {e}")

            # Phase 6: Risk scoring
            risk = RiskAssessment(high_risk_files=file_set.reviewable_files)
            if self._risk_scorer and not request.full_scan:
                _progress("Computing risk scores...")
                try:
                    risk = self._risk_scorer.score(file_set.reviewable_files, tier1_result, config)
                    _progress(f"  {len(risk.high_risk_files)} high-risk, {len(risk.low_risk_files)} low-risk")
                except Exception as e:
                    logger.warning("Risk scoring failed: %s", e)
                    risk = RiskAssessment(high_risk_files=file_set.reviewable_files)

            # Phase 7: Agent review
            all_findings: list[Finding] = list(tier1_result.findings) + list(file_set.hygiene_findings)
            agent_cost = 0.0

            if 2 in request.tiers and self._review_engine and risk.high_risk_files:
                _progress(f"Running agent review on {len(risk.high_risk_files)} high-risk files...")
                try:
                    agent_result = self._review_engine.run(
                        repo_path, risk.high_risk_files, tier1_result, config, request, progress
                    )
                    all_findings.extend(agent_result.findings)
                    agent_cost = agent_result.total_cost
                    errors.extend(agent_result.errors)
                    _progress(f"  Agent review complete: {len(agent_result.findings)} findings")
                except Exception as e:
                    logger.error("Agent review failed: %s", e)
                    errors.append(f"Agent review: {e}")

            all_findings_backup = list(all_findings)

            # Phase 8: Validation
            if self._validation_engine and any(f.tier >= 2 for f in all_findings):
                _progress("Validating findings...")
                try:
                    val_result = self._validation_engine.validate(all_findings, repo_path)
                    all_findings = val_result.validated_findings
                    _progress(f"  Validated: {len(val_result.validated_findings)}, suppressed: {val_result.suppressed_count}")
                except Exception as e:
                    logger.error("Validation failed: %s", e)
                    errors.append(f"Validation: {e}")

            # Phase 9: Finding management
            _progress(f"Processing {len(all_findings)} findings...")
            processed = ProcessedFindings(active_findings=all_findings)
            if self._finding_manager:
                try:
                    processed = self._finding_manager.process(
                        all_findings, repo_context, change_set, config, scan_id=scan_id
                    )
                    _progress(f"  {len(processed.active_findings)} active, {len(processed.suppressed_findings)} suppressed")
                except Exception as e:
                    logger.error("Finding management failed: %s", e)
                    errors.append(f"Finding management: {e}")
                    processed = ProcessedFindings(active_findings=all_findings)

            # Phase 10: Quality gate
            gate_result = QualityGateResult()
            if self._quality_gate:
                _progress("Evaluating quality gate...")
                try:
                    gate_result = self._quality_gate.evaluate(processed.active_findings, config)
                    _progress(f"  Gate: {gate_result.status.upper()} ({gate_result.reasoning})")
                except Exception as e:
                    logger.error("Quality gate failed: %s", e)

            all_findings_backup = list(all_findings)

            # Phase 11: Reports
            duration = round(time.time() - start, 2)
            output_dir = Path(request.output_path) if request.output_path else Path(".qa-reports")
            output_dir.mkdir(parents=True, exist_ok=True)
            file_stem = f"scan-{scan_id}"

            scan_metadata = {
                "report_id": scan_id,
                "trigger": request.trigger,
                "tiers": request.tiers,
                "duration": duration,
                "cost": agent_cost,
                "models_used": [],
                "agents_used": [],
                "pr_number": request.pr_number,
                "remote_url": repo_context.remote_url if repo_context else "",
                "commit_sha": repo_context.commit_sha if repo_context else "",
                "skip_summary": file_set.skip_summary if hasattr(file_set, 'skip_summary') else {},
            }

            json_path = None
            pdf_path = None
            exec_json_path = None
            exec_pdf_path = None

            if self._report_generator:
                _progress("Generating reports...")
                try:
                    report_result = self._report_generator.generate(
                        findings=processed.active_findings,
                        gate_result=gate_result,
                        repo_context=repo_context,
                        scan_metadata=scan_metadata,
                        config=config,
                        output_dir=output_dir,
                        file_stem=file_stem,
                        formats=request.report_formats,
                    )
                    json_path = report_result.get("json_path")
                    pdf_path = report_result.get("pdf_path")
                except Exception as e:
                    logger.error("Report generation failed: %s", e)
                    errors.append(f"Report generation: {e}")

            if self._executive_report_generator and report_result and report_result.get("report_data"):
                try:
                    exec_result = self._executive_report_generator.generate(
                        full_report=report_result["report_data"],
                        output_dir=output_dir,
                        file_stem=file_stem,
                        formats=request.report_formats,
                    )
                    exec_json_path = exec_result.get("json_path")
                    exec_pdf_path = exec_result.get("pdf_path")
                except Exception as e:
                    logger.error("Executive report failed: %s", e)

            # Phase 12: Integrations
            if request.post_comment and self._integration_dispatcher:
                _progress("Dispatching to integrations...")
                try:
                    self._integration_dispatcher.dispatch(
                        processed.active_findings, gate_result, scan_metadata, config
                    )
                except Exception as e:
                    logger.error("Integration dispatch failed: %s", e)
                    errors.append(f"Integrations: {e}")

            # Phase 13: Persist
            if self._scan_repo and self._db_conn:
                try:
                    from qa_platform.infrastructure.database import init_db
                    init_db(self._db_conn)
                    self._scan_repo.save_scan(self._db_conn, {
                        "scan_id": scan_id,
                        "repository": request.repo,
                        "branch": repo_context.branch if repo_context else "",
                        "commit_sha": repo_context.commit_sha if repo_context else "",
                        "trigger_type": request.trigger,
                        "tiers_executed": request.tiers,
                        "finding_count": len(processed.active_findings),
                        "severity_counts": gate_result.severity_counts,
                        "gate_status": gate_result.status,
                        "duration_seconds": duration,
                        "cost_usd": agent_cost,
                        "report_json_path": str(json_path) if json_path else "",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                    if self._finding_repo:
                        self._finding_repo.save_findings(self._db_conn, scan_id, processed.active_findings)
                    self._db_conn.commit()
                except Exception as e:
                    logger.debug("Persistence failed: %s", e)
                    try:
                        self._db_conn.rollback()
                    except Exception:
                        pass

            severity_counts = gate_result.severity_counts or {}

            return ScanResult(
                report_id=scan_id,
                finding_count=len(processed.active_findings),
                severity_counts=severity_counts,
                quality_gate_status=gate_result.status,
                execution_duration=duration,
                execution_cost=agent_cost,
                json_path=json_path,
                pdf_path=pdf_path,
                executive_json_path=exec_json_path,
                executive_pdf_path=exec_pdf_path,
                errors=errors,
            )

        except Exception as e:
            logger.error("Scan failed: %s", e)
            return ScanResult(
                report_id=scan_id,
                finding_count=len(all_findings_backup),
                severity_counts=self._count_severities(all_findings_backup),
                quality_gate_status="error",
                execution_duration=round(time.time() - start, 2),
                errors=[str(e)],
            )
        finally:
            # Phase 14: Cleanup
            if repo_context and repo_context.is_temporary:
                try:
                    if self._repo_resolver:
                        self._repo_resolver.cleanup(repo_context)
                    elif repo_context.local_path.exists():
                        shutil.rmtree(repo_context.local_path, ignore_errors=True)
                except Exception as cleanup_err:
                    logger.warning("Failed to clean up temp clone: %s", cleanup_err)

    def _count_severities(self, findings):
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for f in findings:
            sev_name = f.severity.name.lower() if hasattr(f.severity, 'name') else str(f.severity)
            counts[sev_name] = counts.get(sev_name, 0) + 1
        return counts

    def _list_all_files(self, repo_path: Path) -> list[str]:
        files = []
        try:
            for f in repo_path.rglob("*"):
                if f.is_file() and ".git" not in f.parts:
                    files.append(str(f.relative_to(repo_path)))
        except OSError:
            pass
        return files[:1000]  # Safety limit
