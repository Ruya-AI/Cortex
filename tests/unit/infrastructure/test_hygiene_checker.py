"""Tests for HygieneChecker — file filtering and skip tracking."""
from pathlib import Path

from cortex_engine.core.schemas import ChangeSet, FileSet, RepositoryContext, FileChange
from cortex_engine.infrastructure.hygiene_checker import (
    HygieneChecker,
    _matches_excluded_dir,
    _is_sensitive_file,
    _is_hidden_file,
    _is_hidden_allowed,
    EXCLUDED_DIRECTORIES,
    SENSITIVE_FILES,
)


def _make_changeset(paths: list[str]) -> ChangeSet:
    return ChangeSet(
        changed_files=[FileChange(file_path=p, is_new=False, is_deleted=False) for p in paths],
        is_full_scan=True,
    )


def _make_context(tmp_path: Path) -> RepositoryContext:
    return RepositoryContext(local_path=tmp_path, branch="main", commit_sha="abc123")


class TestExcludedDirMatching:
    def test_venv_excluded(self):
        assert _matches_excluded_dir(".venv/lib/site.py") == ".venv"

    def test_node_modules_excluded(self):
        assert _matches_excluded_dir("node_modules/lodash/index.js") == "node_modules"

    def test_pycache_excluded(self):
        assert _matches_excluded_dir("src/__pycache__/foo.pyc") == "__pycache__"

    def test_nested_excluded(self):
        assert _matches_excluded_dir("a/b/.venv/c.py") == ".venv"

    def test_normal_dir_not_excluded(self):
        assert _matches_excluded_dir("src/main.py") == ""

    def test_filename_not_excluded(self):
        assert _matches_excluded_dir("build_tool.py") == ""

    def test_egg_info(self):
        assert _matches_excluded_dir("foo.egg-info/PKG-INFO") == "foo.egg-info"

    def test_git_excluded(self):
        assert _matches_excluded_dir(".git/objects/abc") == ".git"


class TestSensitiveFile:
    def test_env_sensitive(self):
        assert _is_sensitive_file(".env") is True

    def test_env_local_sensitive(self):
        assert _is_sensitive_file("config/.env.local") is True

    def test_ds_store_sensitive(self):
        assert _is_sensitive_file(".DS_Store") is True

    def test_normal_not_sensitive(self):
        assert _is_sensitive_file("main.py") is False

    def test_env_example_not_sensitive(self):
        assert _is_sensitive_file(".env.example") is False


class TestHiddenFile:
    def test_dotfile_hidden(self):
        assert _is_hidden_file(".secret") is True

    def test_dotdir_hidden(self):
        assert _is_hidden_file(".config/settings.json") is True

    def test_normal_not_hidden(self):
        assert _is_hidden_file("src/main.py") is False

    def test_gitignore_allowed(self):
        assert _is_hidden_allowed(".gitignore") is True

    def test_github_dir_allowed(self):
        assert _is_hidden_allowed(".github/workflows/ci.yml") is True

    def test_random_dotfile_not_allowed(self):
        assert _is_hidden_allowed(".secret") is False


class TestHygieneChecker:
    def test_binary_skipped(self, tmp_path):
        cs = _make_changeset(["image.png", "main.py"])
        ctx = _make_context(tmp_path)
        (tmp_path / "main.py").write_text("x = 1")
        result = HygieneChecker().check(ctx, cs, {})
        assert "image.png" in result.skipped_binary
        assert "main.py" in result.reviewable_files
        assert len(result.reviewable_files) == 1

    def test_excluded_dir_skipped(self, tmp_path):
        cs = _make_changeset([".venv/lib/foo.py", "src/main.py"])
        ctx = _make_context(tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "src/main.py").write_text("x = 1")
        result = HygieneChecker().check(ctx, cs, {})
        assert ".venv/lib/foo.py" in result.skipped_excluded
        assert "src/main.py" in result.reviewable_files

    def test_sensitive_file_creates_finding(self, tmp_path):
        cs = _make_changeset([".env", "main.py"])
        ctx = _make_context(tmp_path)
        (tmp_path / "main.py").write_text("x = 1")
        result = HygieneChecker().check(ctx, cs, {})
        assert ".env" in result.skipped_excluded
        assert len(result.hygiene_findings) == 1
        assert "Sensitive" in result.hygiene_findings[0].title

    def test_skip_summary_populated(self, tmp_path):
        cs = _make_changeset([".venv/a.py", ".venv/b.py", "app.pyc", "main.py"])
        ctx = _make_context(tmp_path)
        (tmp_path / "main.py").write_text("x = 1")
        result = HygieneChecker().check(ctx, cs, {})
        assert result.skip_summary["total_skipped"] == 3
        assert result.skip_summary["counts"]["excluded_directory"] == 2
        assert result.skip_summary["counts"]["binary"] == 1
        assert result.skip_summary["reviewable_count"] == 1

    def test_no_findings_for_routine_skips(self, tmp_path):
        cs = _make_changeset([".venv/lib/a.py", ".venv/lib/b.py", "app.pyc"])
        ctx = _make_context(tmp_path)
        result = HygieneChecker().check(ctx, cs, {})
        assert len(result.hygiene_findings) == 0
        assert result.skip_summary["total_skipped"] == 3
