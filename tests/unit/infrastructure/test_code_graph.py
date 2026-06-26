"""Tests for CodeGraph — Graphify wrapper."""
from pathlib import Path

from cortex_engine.infrastructure.code_graph import CodeGraph, _is_code_file


class TestCodeGraphAvailability:
    def test_is_available(self):
        assert CodeGraph.is_available() is True

    def test_is_code_file(self):
        assert _is_code_file("main.py") is True
        assert _is_code_file("app.js") is True
        assert _is_code_file("lib.rs") is True
        assert _is_code_file("README.md") is False
        assert _is_code_file("image.png") is False

    def test_build_empty_returns_none(self, tmp_path):
        result = CodeGraph.build(tmp_path, [])
        assert result is None

    def test_build_no_code_files(self, tmp_path):
        (tmp_path / "readme.md").write_text("# Hello")
        result = CodeGraph.build(tmp_path, ["readme.md"])
        assert result is None

    def test_build_simple_python(self, tmp_path):
        (tmp_path / "main.py").write_text("def hello():\n    return 'world'\n")
        (tmp_path / "utils.py").write_text("def add(a, b):\n    return a + b\n")
        result = CodeGraph.build(tmp_path, ["main.py", "utils.py"])
        assert result is not None
        assert result.number_of_nodes() > 0

    def test_load_nonexistent_returns_none(self, tmp_path):
        result = CodeGraph.load(tmp_path)
        assert result is None

    def test_get_summary_none_graph(self):
        assert CodeGraph.get_summary(None) == {}

    def test_get_god_nodes_none_graph(self):
        assert CodeGraph.get_god_nodes(None) == []

    def test_get_affected_none_graph(self):
        assert CodeGraph.get_affected(None, ["file.py"]) == {}

    def test_build_and_cache(self, tmp_path):
        (tmp_path / "app.py").write_text("def run():\n    pass\n")
        graph = CodeGraph.build(tmp_path, ["app.py"])
        assert graph is not None
        cache = tmp_path / ".cortex" / "graph.json"
        assert cache.exists()

    def test_get_summary_with_graph(self, tmp_path):
        (tmp_path / "main.py").write_text("from utils import helper\ndef run():\n    helper()\n")
        (tmp_path / "utils.py").write_text("def helper():\n    return 1\n")
        graph = CodeGraph.build(tmp_path, ["main.py", "utils.py"])
        summary = CodeGraph.get_summary(graph)
        assert "nodes" in summary
        assert "edges" in summary
        assert summary["nodes"] > 0
