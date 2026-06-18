from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from qa_platform.agents.base import ReviewAgent
from qa_platform.agents.registry import AgentRegistry
from qa_platform.agents.tool_provider import AgentToolProvider
from qa_platform.agents.memory import SemanticMemoryLoader
from qa_platform.core.finding import Finding
from qa_platform.core.schemas import (
    AgentReviewResult, AgentResult, FileReviewContext, FileGroupReviewContext,
    ScanRequest, Tier1RunResult, MemoryDocument,
)
from qa_platform.orchestration.cost_tracker import CostTracker

logger = logging.getLogger(__name__)


class AgenticReviewEngine:
    def __init__(
        self,
        agent_registry: AgentRegistry,
        tool_provider_factory=None,  # callable(repo_path) -> AgentToolProvider
        memory_loader: SemanticMemoryLoader | None = None,
        cost_tracker: CostTracker | None = None,
        max_parallel: int = 3,
    ):
        self._registry = agent_registry
        self._tool_provider_factory = tool_provider_factory
        self._memory_loader = memory_loader or SemanticMemoryLoader()
        self._cost_tracker = cost_tracker
        self._max_parallel = max_parallel

    def run(
        self,
        repo_path: Path,
        high_risk_files: list[str],
        tier1_result: Tier1RunResult,
        config: dict,
        request: ScanRequest,
        progress=None,
    ) -> AgentReviewResult:
        all_findings: list[Finding] = []
        agents_used: list[str] = []
        models_used: list[dict] = []
        total_cost = 0.0
        errors: list[str] = []

        # Get tier 2 agents
        tier2_agents = self._registry.get_agents_for_tier(2)
        if not tier2_agents:
            return AgentReviewResult(errors=["No tier 2 agents registered"])

        # Build tier1 findings index by file
        tier1_by_file: dict[str, list[Finding]] = {}
        for f in tier1_result.findings:
            tier1_by_file.setdefault(f.file, []).append(f)

        # Load semantic memory once
        memory_docs = self._load_memory(config, repo_path)

        # Review each high-risk file
        for file_path in high_risk_files:
            if progress:
                progress(f"  Agent review: {file_path}")

            if self._cost_tracker and self._cost_tracker.is_limit_reached(request.cost_limit):
                errors.append("Cost limit reached — remaining files skipped")
                break

            try:
                file_content = (repo_path / file_path).read_text(errors="replace")
            except OSError:
                continue

            # Build context
            context = FileReviewContext(
                file_path=file_path,
                file_content=file_content,
                diff_content=None,  # Could be enriched from ChangeSet
                tier1_findings=tier1_by_file.get(file_path, []),
                semantic_memory=memory_docs,
                repository_path=repo_path,
            )

            # Run tier 2 agents in parallel
            file_results = self._run_agents_parallel(tier2_agents, context)
            for result in file_results:
                all_findings.extend(result.findings)
                if result.agent_name not in agents_used:
                    agents_used.append(result.agent_name)
                total_cost += result.cost_usd
                if result.model_used:
                    models_used.append({"agent": result.agent_name, "model": result.model_used})
                errors.extend(result.errors)

                if self._cost_tracker:
                    self._cost_tracker.record(
                        result.agent_name, result.model_used,
                        result.input_tokens, result.output_tokens, result.cost_usd
                    )

        # Run tier 3 cross-file agent if applicable
        if 3 in request.tiers or request.trigger == "audit":
            tier3_agents = self._registry.get_agents_for_tier(3)
            if tier3_agents and len(high_risk_files) >= 3:
                if progress:
                    progress("  Running cross-file analysis...")
                for agent in tier3_agents:
                    try:
                        group_context = self._build_file_group_context(
                            high_risk_files[:20], repo_path, tier1_by_file, memory_docs
                        )
                        result = agent.review_file_group(group_context)
                        all_findings.extend(result.findings)
                        if result.agent_name not in agents_used:
                            agents_used.append(result.agent_name)
                        total_cost += result.cost_usd
                        errors.extend(result.errors)
                    except Exception as e:
                        logger.error("Cross-file agent %s failed: %s", agent.name, e)
                        errors.append(f"Cross-file agent {agent.name}: {e}")

        return AgentReviewResult(
            findings=all_findings,
            agents_used=agents_used,
            models_used=models_used,
            total_cost=total_cost,
            errors=errors,
        )

    def _run_agents_parallel(self, agents: list[ReviewAgent], context: FileReviewContext) -> list[AgentResult]:
        results = []
        with ThreadPoolExecutor(max_workers=self._max_parallel) as executor:
            futures = {executor.submit(self._safe_review, agent, context): agent for agent in agents}
            for future in as_completed(futures):
                results.append(future.result())
        return results

    def _safe_review(self, agent: ReviewAgent, context: FileReviewContext) -> AgentResult:
        try:
            return agent.review_file(context)
        except Exception as e:
            logger.error("Agent %s failed on %s: %s", agent.name, context.file_path, e)
            return AgentResult(agent_name=agent.name, errors=[str(e)])

    def _build_file_group_context(self, files, repo_path, tier1_by_file, memory_docs):
        file_contexts = []
        for fp in files:
            try:
                content = (repo_path / fp).read_text(errors="replace")
                file_contexts.append(FileReviewContext(
                    file_path=fp, file_content=content,
                    tier1_findings=tier1_by_file.get(fp, []),
                    semantic_memory=memory_docs, repository_path=repo_path,
                ))
            except OSError:
                continue
        return FileGroupReviewContext(file_group=file_contexts)

    def _load_memory(self, config: dict, repo_path: Path) -> list[MemoryDocument]:
        docs = []
        for loader_fn in [
            self._memory_loader.load_sast_rules,
            self._memory_loader.load_cwe_tree,
            self._memory_loader.load_design_principles,
        ]:
            doc = loader_fn()
            if doc:
                docs.append(doc)
        conv_path = config.get("knowledge_base", {}).get("conventions_path")
        if conv_path:
            doc = self._memory_loader.load_project_conventions(conv_path, repo_path)
            if doc:
                docs.append(doc)
        return docs
