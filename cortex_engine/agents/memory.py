from __future__ import annotations

import logging
from pathlib import Path

from cortex_engine.core.schemas import MemoryDocument

logger = logging.getLogger(__name__)

_KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"


class SemanticMemoryLoader:
    def load_sast_rules(self) -> MemoryDocument | None:
        return self._load_json("sast_rules.json", "sast_rules")

    def load_cwe_tree(self) -> MemoryDocument | None:
        return self._load_json("cwe_tree.json", "cwe_tree")

    def load_design_principles(self) -> MemoryDocument | None:
        return self._load_json("design_principles.json", "design_principles")

    def load_project_conventions(self, conventions_path: str | None, repo_path: Path | None = None) -> MemoryDocument | None:
        if not conventions_path or not repo_path:
            return None
        full_path = repo_path / conventions_path
        if not full_path.exists():
            return None
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
            return MemoryDocument(name="project_conventions", content=content, memory_type="semantic")
        except OSError:
            return None

    def _load_json(self, filename: str, name: str) -> MemoryDocument | None:
        path = _KNOWLEDGE_DIR / filename
        if not path.exists():
            logger.debug("Knowledge file not found: %s", path)
            return None
        try:
            content = path.read_text(encoding="utf-8")
            return MemoryDocument(name=name, content=content, memory_type="semantic")
        except OSError as e:
            logger.warning("Failed to load knowledge file %s: %s", filename, e)
            return None
