from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class CostTracker:
    def __init__(self):
        self._records: list[dict] = []
        self._total_cost = 0.0

    def record(self, agent_name: str, model: str, input_tokens: int, output_tokens: int, cost: float) -> None:
        self._records.append({
            "agent": agent_name,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
        })
        self._total_cost += cost

    @property
    def total_cost(self) -> float:
        return self._total_cost

    def is_limit_reached(self, limit: float | None) -> bool:
        if limit is None:
            return False
        return self._total_cost >= limit

    def get_summary(self) -> dict:
        by_agent: dict[str, float] = {}
        by_model: dict[str, float] = {}
        for r in self._records:
            by_agent[r["agent"]] = by_agent.get(r["agent"], 0) + r["cost"]
            by_model[r["model"]] = by_model.get(r["model"], 0) + r["cost"]
        return {
            "total_cost": self._total_cost,
            "by_agent": by_agent,
            "by_model": by_model,
            "call_count": len(self._records),
        }
