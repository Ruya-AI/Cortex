"""Code graph builder using Graphify (Tree-sitter based, no LLM cost).

Provides structural code analysis: call graphs, imports, dependencies.
Used by the orchestrator to enhance risk scoring and agent context.

Fully optional — returns None on any failure. Cortex continues without it.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_GRAPHIFY_AVAILABLE = False
try:
    from graphify.extract import extract as _extract
    from graphify.build import build as _build
    from graphify.affected import affected_nodes as _affected_nodes, load_graph as _load_graph
    from graphify.analyze import god_nodes as _god_nodes
    import networkx as nx
    _GRAPHIFY_AVAILABLE = True
except ImportError:
    nx = None


class CodeGraph:
    """Thin wrapper around Graphify with caching and fault tolerance."""

    @staticmethod
    def is_available() -> bool:
        return _GRAPHIFY_AVAILABLE

    @staticmethod
    def build(repo_path: Path, file_paths: list[str]) -> object | None:
        """Build code graph from source files using Tree-sitter (Pass 1 only).

        Returns a NetworkX graph or None on failure.
        No LLM calls — purely deterministic parsing.
        """
        if not _GRAPHIFY_AVAILABLE:
            return None

        try:
            abs_paths = [repo_path / fp for fp in file_paths if _is_code_file(fp)]
            if not abs_paths:
                return None

            existing = [p for p in abs_paths if p.exists()]
            if not existing:
                return None

            extractions = _extract(existing, cache_root=repo_path / ".cortex" / "graph_cache")
            graph = _build([extractions], directed=True)

            if graph.number_of_nodes() == 0:
                return None

            cache_path = repo_path / ".cortex" / "graph.json"
            CodeGraph.save(graph, cache_path)

            return graph
        except Exception as e:
            logger.warning("Code graph build failed (continuing without graph): %s", e)
            return None

    @staticmethod
    def load(repo_path: Path) -> object | None:
        """Load cached graph from .cortex/graph.json."""
        if not _GRAPHIFY_AVAILABLE:
            return None

        cache_path = repo_path / ".cortex" / "graph.json"
        if not cache_path.exists():
            return None

        try:
            return _load_graph(cache_path)
        except Exception as e:
            logger.warning("Failed to load cached graph: %s", e)
            return None

    @staticmethod
    def save(graph, path: Path) -> None:
        """Save graph to disk for reuse in PR/commit scans."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = nx.node_link_data(graph)
            path.write_text(json.dumps(data, default=str), encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to save graph cache: %s", e)

    @staticmethod
    def get_affected(graph, changed_files: list[str]) -> dict[str, list[dict]]:
        """Find nodes affected by changes to the given files.

        Returns {filename: [{node_id, depth, via_relation}]}.
        """
        if not _GRAPHIFY_AVAILABLE or graph is None:
            return {}

        result: dict[str, list[dict]] = {}
        try:
            file_nodes = {}
            for node_id, data in graph.nodes(data=True):
                label = data.get("label", node_id)
                for fp in changed_files:
                    stem = Path(fp).stem
                    if node_id.startswith(stem.replace("-", "_").replace(".", "_")):
                        file_nodes.setdefault(fp, []).append(node_id)

            for fp, nodes in file_nodes.items():
                affected = []
                for seed in nodes:
                    try:
                        hits = _affected_nodes(graph, seed, depth=2)
                        for h in hits:
                            affected.append({
                                "node_id": h.node_id,
                                "depth": h.depth,
                                "via_relation": h.via_relation,
                            })
                    except Exception:
                        pass
                if affected:
                    result[fp] = affected
        except Exception as e:
            logger.warning("Affected node analysis failed: %s", e)

        return result

    @staticmethod
    def get_god_nodes(graph, top_n: int = 10) -> list[dict]:
        """Get the most-connected nodes (highest degree centrality)."""
        if not _GRAPHIFY_AVAILABLE or graph is None:
            return []

        try:
            return _god_nodes(graph, top_n=top_n)
        except Exception:
            return []

    @staticmethod
    def get_summary(graph) -> dict:
        """Get a compact summary of the graph for scan metadata."""
        if graph is None:
            return {}
        try:
            gods = CodeGraph.get_god_nodes(graph, top_n=5)
            return {
                "nodes": graph.number_of_nodes(),
                "edges": graph.number_of_edges(),
                "god_nodes": [g.get("label", g.get("id", "")) for g in gods],
            }
        except Exception:
            return {}


_CODE_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".rb",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".swift", ".kt", ".scala",
    ".php", ".lua", ".sh", ".bash", ".sql", ".r", ".jl",
})


def _is_code_file(path: str) -> bool:
    return Path(path).suffix.lower() in _CODE_EXTENSIONS
