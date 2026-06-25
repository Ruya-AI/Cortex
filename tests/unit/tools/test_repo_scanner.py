"""Tests for RepoScannerTool — repository-level scanning."""
from pathlib import Path
from unittest.mock import patch

from cortex_engine.tools.repo_scanner_tool import RepoScannerTool


class TestRepoScannerTool:
    def test_is_available(self):
        tool = RepoScannerTool()
        assert tool.is_available() is True
        assert tool.name == "repo-scanner"

    def test_is_applicable_returns_false(self):
        tool = RepoScannerTool()
        assert tool.is_applicable("any_file.py") is False

    def test_run_returns_empty(self):
        tool = RepoScannerTool()
        assert tool.run("file.py", Path(".")) == []

    def test_check_packages_detects_venv(self, tmp_path):
        tool = RepoScannerTool()
        tracked = [".venv/lib/a.py", ".venv/lib/b.py", ".venv/bin/python"]
        for f in tracked:
            p = tmp_path / f
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x")
        findings = tool._check_packages(tracked, tmp_path)
        assert len(findings) == 1
        assert ".venv/" in findings[0].title
        assert "3 files" in findings[0].title

    def test_check_sensitive_detects_env(self):
        tool = RepoScannerTool()
        findings = tool._check_sensitive([".env", "src/main.py"])
        assert len(findings) == 1
        assert ".env" in findings[0].title

    def test_check_sensitive_skips_package_dirs(self):
        tool = RepoScannerTool()
        findings = tool._check_sensitive([".venv/lib/cacert.pem", "src/main.py"])
        assert len(findings) == 0

    def test_check_large_files(self, tmp_path):
        tool = RepoScannerTool()
        large_file = tmp_path / "big.bin"
        large_file.write_bytes(b"x" * (2 * 1024 * 1024))
        findings = tool._check_large_files(["big.bin"], tmp_path)
        assert len(findings) == 1
        assert "Large file" in findings[0].title

    def test_check_large_skips_package_dirs(self, tmp_path):
        tool = RepoScannerTool()
        p = tmp_path / ".venv" / "big.so"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * (2 * 1024 * 1024))
        findings = tool._check_large_files([".venv/big.so"], tmp_path)
        assert len(findings) == 0

    def test_check_unnecessary_detects_log(self):
        tool = RepoScannerTool()
        findings = tool._check_unnecessary(["debug.log", "src/main.py"])
        assert len(findings) == 1
        assert "debug.log" in findings[0].title

    def test_check_hidden_files(self):
        tool = RepoScannerTool()
        findings = tool._check_hidden_files([".secret", ".gitignore", "src/main.py"])
        assert len(findings) == 1
        assert ".secret" in findings[0].title

    def test_run_batch_with_no_git(self, tmp_path):
        tool = RepoScannerTool()
        findings = tool.run_batch([], tmp_path)
        assert findings == []
