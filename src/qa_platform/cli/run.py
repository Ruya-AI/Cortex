from __future__ import annotations

import logging
import sys

import click

from qa_platform import __version__


@click.command()
@click.option("--repo", required=True, help="Local path or remote URL")
@click.option("--branch", default=None, help="Branch to scan")
@click.option("--commit", default=None, help="Specific commit SHA")
@click.option("--vs", "compare_to", default=None, help="Base branch for diff")
@click.option("--tiers", default="1,2", help="Tiers to run (e.g., 1,2,3)")
@click.option("--agents", default=None, help="Specific agents (comma-separated)")
@click.option("--audit", is_flag=True, help="Full codebase audit")
@click.option("--full", is_flag=True, help="Full scan (all files)")
@click.option("--report", default="json", help="Report formats: json,pdf")
@click.option("--output", default=None, help="Output directory")
@click.option("--pr", "pr_number", type=int, default=None, help="PR number")
@click.option("--post-comment", is_flag=True, help="Post to GitHub PR")
@click.option("--github-token", default=None, help="GitHub token")
@click.option("--cost-limit", type=float, default=None, help="Max LLM cost (USD)")
@click.option("--dry-run", is_flag=True, help="Show config only")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.version_option(version=__version__)
def main(
    repo, branch, commit, compare_to, tiers, agents, audit, full,
    report, output, pr_number, post_comment, github_token, cost_limit,
    dry_run, verbose,
):
    """QA Platform — Automated code review and analysis.

    Identifies issues, provides explanations, suggests improvements,
    and recommends fixes. Does NOT modify code.
    """
    # Configure logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # Parse options
    tier_list = [int(t.strip()) for t in tiers.split(",") if t.strip()]
    if audit:
        tier_list = [1, 2, 3]
        full = True
    format_list = [f.strip() for f in report.split(",")]

    from qa_platform.core.schemas import ScanRequest
    request = ScanRequest(
        repo=repo,
        branch=branch,
        commit=commit,
        compare_to=compare_to,
        tiers=tier_list,
        agents=[a.strip() for a in agents.split(",")] if agents else None,
        trigger="audit" if audit else ("pr-push" if pr_number else "ad-hoc"),
        report_formats=format_list,
        output_path=output,
        pr_number=pr_number,
        full_scan=full,
        cost_limit=cost_limit,
        post_comment=post_comment,
        github_token=github_token,
        dry_run=dry_run,
    )

    # Display header
    click.echo("=" * 60)
    click.echo("  QA Platform v2.0 — Code Review & Analysis")
    click.echo("  Identifies and reports. Does NOT modify code.")
    click.echo("=" * 60)
    click.echo()
    click.echo(f"  Repository:  {repo}")
    if branch:
        click.echo(f"  Branch:      {branch}")
    click.echo(f"  Tiers:       {tier_list}")
    click.echo(f"  Report:      {format_list}")
    click.echo(f"  Mode:        {'FULL AUDIT' if audit else 'full scan' if full else 'changed files'}")
    if cost_limit:
        click.echo(f"  Cost Limit:  ${cost_limit:.2f}")
    click.echo()

    if dry_run:
        click.echo("[DRY RUN] Configuration shown. No scan executed.")
        return

    # Build the system — composition root
    orchestrator = _build_orchestrator(request)

    def show_progress(msg: str) -> None:
        click.echo(f"  {msg}")

    # Execute scan
    try:
        result = orchestrator.scan(request, progress=show_progress)
    finally:
        # Ensure the database connection is closed
        if orchestrator._db_conn is not None:
            try:
                orchestrator._db_conn.close()
            except Exception:
                pass

    # Display results
    click.echo()
    click.echo("=" * 60)
    click.echo("  SCAN RESULTS")
    click.echo("=" * 60)
    click.echo(f"  Report ID:      {result.report_id}")
    click.echo(f"  Findings:       {result.finding_count}")
    click.echo(f"  Severity:       {result.severity_counts}")
    click.echo(f"  Quality Gate:   {result.quality_gate_status.upper()}")
    click.echo(f"  Duration:       {result.execution_duration:.1f}s")
    click.echo(f"  Cost:           ${result.execution_cost:.4f}")
    click.echo()

    if result.json_path:
        click.echo(f"  Report: {result.json_path}")
    if result.executive_json_path:
        click.echo(f"  Executive: {result.executive_json_path}")

    if result.errors:
        click.echo()
        click.echo("  Errors:")
        for err in result.errors:
            click.echo(f"    - {err}")

    click.echo()

    # Exit code reflects gate
    if result.quality_gate_status == "fail":
        sys.exit(1)
    elif result.quality_gate_status == "error":
        sys.exit(2)
    sys.exit(0)


def _build_orchestrator(request):
    """Composition root — create and wire all dependencies."""
    from qa_platform.infrastructure.config import load_config
    from qa_platform.infrastructure.repository_resolver import RepositoryResolver
    from qa_platform.infrastructure.change_detector import ChangeDetector
    from qa_platform.infrastructure.hygiene_checker import HygieneChecker
    from qa_platform.infrastructure.git import GitOperations

    from qa_platform.tools.runner import Tier1Runner
    from qa_platform.assessment.risk_scorer import RiskScorer
    from qa_platform.assessment.quality_gate import QualityGate
    from qa_platform.reporting.report_generator import ReportGenerator
    from qa_platform.reporting.executive_report import ExecutiveReportGenerator
    from qa_platform.integrations.dispatcher import IntegrationDispatcher
    from qa_platform.core.finding_manager import FindingManager

    from qa_platform.orchestration.orchestrator import ScanOrchestrator
    from qa_platform.orchestration.cost_tracker import CostTracker

    # Tier 1 tools
    tier1_runner = Tier1Runner()
    _register_tools(tier1_runner)

    # Finding manager with git blame injection
    finding_manager = FindingManager(
        blame_fn=GitOperations.get_blame,
        git_config_fn=GitOperations.get_config,
    )

    # Agent infrastructure (only if tier 2+ requested)
    review_engine = None
    validation_engine = None
    cost_tracker = CostTracker()

    if any(t >= 2 for t in request.tiers):
        review_engine, validation_engine = _build_agent_infrastructure(request, cost_tracker)

    # Integrations
    dispatcher = IntegrationDispatcher()
    if request.post_comment:
        from qa_platform.integrations.github import GitHubIntegration
        dispatcher.register(GitHubIntegration(token=request.github_token))

    # Database (optional)
    db_conn = None
    scan_repo = None
    finding_repo = None
    try:
        from qa_platform.infrastructure.database import get_connection, init_db
        from qa_platform.infrastructure.scan_repository import SQLiteScanRepository
        from qa_platform.infrastructure.finding_repository import SQLiteFindingRepository
        db_conn = get_connection()
        init_db(db_conn)
        scan_repo = SQLiteScanRepository()
        finding_repo = SQLiteFindingRepository()
    except Exception:
        pass

    return ScanOrchestrator(
        repository_resolver=RepositoryResolver(),
        change_detector=ChangeDetector(),
        hygiene_checker=HygieneChecker(),
        tier1_runner=tier1_runner,
        risk_scorer=RiskScorer(),
        review_engine=review_engine,
        validation_engine=validation_engine,
        finding_manager=finding_manager,
        quality_gate=QualityGate(),
        report_generator=ReportGenerator(),
        executive_report_generator=ExecutiveReportGenerator(),
        integration_dispatcher=dispatcher,
        config_loader=load_config,
        scan_repository=scan_repo,
        finding_repository=finding_repo,
        db_connection=db_conn,
    )


def _register_tools(runner):
    """Register all available Tier 1 tools."""
    tool_classes = []
    try:
        from qa_platform.tools.ruff_tool import RuffTool
        tool_classes.append(RuffTool)
    except ImportError:
        pass
    try:
        from qa_platform.tools.bandit_tool import BanditTool
        tool_classes.append(BanditTool)
    except ImportError:
        pass
    try:
        from qa_platform.tools.mypy_tool import MypyTool
        tool_classes.append(MypyTool)
    except ImportError:
        pass
    try:
        from qa_platform.tools.semgrep_tool import SemgrepTool
        tool_classes.append(SemgrepTool)
    except ImportError:
        pass
    try:
        from qa_platform.tools.radon_tool import RadonTool
        tool_classes.append(RadonTool)
    except ImportError:
        pass
    try:
        from qa_platform.tools.security_patterns import SecurityPatternsTool
        tool_classes.append(SecurityPatternsTool)
    except ImportError:
        pass
    try:
        from qa_platform.tools.complexity_tool import ComplexityTool
        tool_classes.append(ComplexityTool)
    except ImportError:
        pass
    try:
        from qa_platform.tools.shellcheck_tool import ShellcheckTool
        tool_classes.append(ShellcheckTool)
    except ImportError:
        pass
    try:
        from qa_platform.tools.gitleaks_tool import GitleaksTool
        tool_classes.append(GitleaksTool)
    except ImportError:
        pass

    # Register remaining tools that may exist
    optional_tools = [
        "pip_audit_tool.PipAuditTool",
        "hadolint_tool.HadolintTool",
        "sqlfluff_tool.SqlfluffTool",
        "checkov_tool.CheckovTool",
        "pip_licenses_tool.PipLicensesTool",
        "jscpd_tool.JscpdTool",
        "markdownlint_tool.MarkdownlintTool",
        "prettier_tool.PrettierTool",
        "stylelint_tool.StylelintTool",
        "osv_scanner_tool.OsvScannerTool",
        "trivy_tool.TrivyTool",
        "dead_code_tool.DeadCodeTool",
        "interface_checker.InterfaceCheckerTool",
        "migration_checker.MigrationCheckerTool",
        "call_graph_tool.CallGraphTool",
        "test_coverage_gap.TestCoverageGapTool",
        "version_drift_tool.VersionDriftTool",
        "unused_module_tool.UnusedModuleTool",
    ]
    for tool_ref in optional_tools:
        module_name, class_name = tool_ref.rsplit(".", 1)
        try:
            mod = __import__(f"qa_platform.tools.{module_name}", fromlist=[class_name])
            tool_class = getattr(mod, class_name)
            if tool_class not in tool_classes:
                tool_classes.append(tool_class)
        except (ImportError, AttributeError):
            pass

    for cls in tool_classes:
        try:
            runner.register(cls())
        except Exception:
            pass


def _build_agent_infrastructure(request, cost_tracker):
    """Build agent review and validation engines."""
    from qa_platform.agents.registry import AgentRegistry
    from qa_platform.agents.memory import SemanticMemoryLoader
    from qa_platform.orchestration.review_engine import AgenticReviewEngine
    from qa_platform.orchestration.validation_engine import ValidationEngine

    registry = AgentRegistry()
    memory_loader = SemanticMemoryLoader()

    # Try to create LLM client
    import os
    primary_model = os.environ.get("QA_LLM_PRIMARY_MODEL", "claude-opus-4-6")
    fallback_model = os.environ.get("QA_LLM_FALLBACK_MODEL", "claude-sonnet-4-6")
    max_retries = int(os.environ.get("QA_LLM_MAX_RETRIES", "3"))

    llm_client = None
    validator_llm_client = None
    try:
        from qa_platform.infrastructure.llm_client import AnthropicLLMClient
        llm_client = AnthropicLLMClient(
            primary_model=primary_model,
            fallback_models=[fallback_model] if fallback_model else [],
            max_retries=max_retries,
        )
        validator_llm_client = AnthropicLLMClient(
            primary_model=primary_model,
            fallback_models=[fallback_model] if fallback_model else [],
            max_retries=max_retries,
        )
    except Exception as e:
        logging.getLogger(__name__).warning("LLM client init failed: %s", e)

    # Register agents
    try:
        from qa_platform.agents.correctness import CorrectnessAgent
        registry.register(CorrectnessAgent(llm_client=llm_client, memory_loader=memory_loader))
    except ImportError:
        pass
    try:
        from qa_platform.agents.security import SecurityAgent
        registry.register(SecurityAgent(llm_client=llm_client, memory_loader=memory_loader))
    except ImportError:
        pass
    try:
        from qa_platform.agents.design import DesignAgent
        registry.register(DesignAgent(llm_client=llm_client, memory_loader=memory_loader))
    except ImportError:
        pass
    try:
        from qa_platform.agents.cross_file import CrossFileAgent
        registry.register(CrossFileAgent(llm_client=llm_client, memory_loader=memory_loader))
    except ImportError:
        pass

    review_engine = AgenticReviewEngine(
        agent_registry=registry,
        memory_loader=memory_loader,
        cost_tracker=cost_tracker,
    )

    # Validator
    validator_agent = None
    try:
        from qa_platform.agents.validator import ValidatorAgent
        validator_agent = ValidatorAgent(llm_client=validator_llm_client or llm_client)
    except ImportError:
        pass

    validation_engine = ValidationEngine(validator_agent=validator_agent)

    return review_engine, validation_engine


if __name__ == "__main__":
    main()
