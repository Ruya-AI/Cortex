from __future__ import annotations

import logging

from cortex_engine.agents.base import ReviewAgent

logger = logging.getLogger(__name__)


class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, ReviewAgent] = {}

    def register(self, agent: ReviewAgent) -> None:
        self._agents[agent.name] = agent
        logger.debug("Registered agent: %s (tier=%d)", agent.name, agent.tier)

    def get_agent(self, name: str) -> ReviewAgent | None:
        return self._agents.get(name)

    def get_agents_for_tier(self, tier: int) -> list[ReviewAgent]:
        return [a for a in self._agents.values() if a.tier == tier]

    def get_all_agents(self) -> list[ReviewAgent]:
        return list(self._agents.values())

    def get_agent_names(self) -> list[str]:
        return list(self._agents.keys())
