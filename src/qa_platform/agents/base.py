from __future__ import annotations

from abc import ABC, abstractmethod

from qa_platform.core.finding import FindingCategory
from qa_platform.core.schemas import AgentResult, FileReviewContext, FileGroupReviewContext, MemoryDocument


class ReviewAgent(ABC):
    name: str = "base"
    tier: int = 2
    category: FindingCategory = FindingCategory.CORRECTNESS
    cognitive_mode: str = "constructive"

    @abstractmethod
    def review_file(self, context: FileReviewContext) -> AgentResult:
        """Review a single file. Must return AgentResult, never raise."""

    def review_file_group(self, context: FileGroupReviewContext) -> AgentResult:
        """Review multiple files for cross-file analysis. Override in Agent 4."""
        raise NotImplementedError(f"{self.name} does not support file group review")

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return system prompt loaded from external file."""

    def get_semantic_memory(self) -> list[MemoryDocument]:
        """Return semantic memory documents. Override to provide knowledge."""
        return []
