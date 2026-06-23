from __future__ import annotations

import logging
import os
from pathlib import PurePosixPath

from qa_platform.core.finding import (
    Confidence,
    FindingCategory,
    Finding,
    Severity,
)
from qa_platform.core.schemas import ChangeSet, FileSet, RepositoryContext

logger = logging.getLogger(__name__)

BINARY_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pyc", ".pyo", ".exe", ".dll", ".so", ".dylib", ".o", ".a",
        ".lib", ".bin", ".dat", ".db", ".sqlite", ".sqlite3",
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
        ".woff", ".woff2", ".ttf", ".eot",
        ".mp3", ".mp4", ".avi", ".mov",
        ".zip", ".tar", ".gz", ".jar", ".war", ".class",
        ".pdf", ".whl", ".egg",
    }
)

EXCLUDED_DIRECTORIES: frozenset[str] = frozenset(
    {
        ".venv", "venv", "node_modules", "__pycache__", "dist", "build",
        ".egg-info", ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
        "vendor", "bower_components", ".git", "site-packages",
    }
)

SENSITIVE_FILES: frozenset[str] = frozenset(
    {
        ".env", ".env.local", ".env.production", ".env.staging",
        ".DS_Store", "Thumbs.db",
    }
)

HIDDEN_ALLOWLIST: frozenset[str] = frozenset(
    {
        ".gitignore", ".gitattributes", ".gitmodules",
        ".github", ".gitlab-ci.yml", ".gitlab",
        ".dockerignore", ".docker",
        ".editorconfig", ".flake8", ".pylintrc",
        ".pre-commit-config.yaml", ".pre-commit-hooks.yaml",
        ".prettierrc", ".prettierignore",
        ".eslintrc", ".eslintrc.json", ".eslintrc.js", ".eslintignore",
        ".babelrc", ".browserslistrc",
        ".npmrc", ".npmignore", ".yarnrc",
        ".python-version", ".node-version", ".nvmrc", ".ruby-version",
        ".tool-versions",
        ".coveragerc",
    }
)


class _FindingFactory:
    """Create standardised Finding objects for reportable hygiene issues."""

    _counter: int = 0

    @classmethod
    def _next_id(cls) -> str:
        cls._counter += 1
        return f"HYG-{cls._counter:04d}"

    @classmethod
    def reset(cls) -> None:
        cls._counter = 0

    @classmethod
    def create(
        cls,
        *,
        file_path: str,
        title: str,
        explanation: str,
        severity: Severity = Severity.LOW,
        confidence: Confidence = Confidence.CONFIRMED,
    ) -> Finding:
        return Finding(
            id=cls._next_id(),
            source="hygiene-checker",
            tier=0,
            category=FindingCategory.HYGIENE,
            severity=severity,
            confidence=confidence,
            file=file_path,
            title=title,
            explanation=explanation,
        )


class HygieneChecker:
    """Filter files into reviewable vs. skipped.

    Routine skips (binary, excluded dirs, hidden files) are tracked as
    counts in ``FileSet.skip_summary`` — NOT as individual Finding objects.

    Only actionable hygiene issues (sensitive files found in repo) produce
    Finding objects in ``FileSet.hygiene_findings``.
    """

    def check(
        self,
        context: RepositoryContext,
        change_set: ChangeSet,
        config: dict,
    ) -> FileSet:
        _FindingFactory.reset()

        max_size_kb: int = config.get("max_file_size_kb", 10240)
        extra_binary: set[str] = set(config.get("extra_binary_extensions", []))
        all_binary = BINARY_EXTENSIONS | extra_binary

        file_set = FileSet()
        skip_counts: dict[str, int] = {
            "binary": 0,
            "excluded_directory": 0,
            "sensitive_file": 0,
            "hidden_file": 0,
            "large_file": 0,
        }
        excluded_dirs_seen: dict[str, int] = {}

        for fc in change_set.changed_files:
            fp = fc.file_path
            ext = _file_extension(fp)

            # 1. Binary — skip, count only
            if ext in all_binary:
                file_set.skipped_binary.append(fp)
                skip_counts["binary"] += 1
                continue

            # 2. Excluded directory — skip, count by directory name
            excluded_dir = _matches_excluded_dir(fp)
            if excluded_dir:
                file_set.skipped_excluded.append(fp)
                skip_counts["excluded_directory"] += 1
                excluded_dirs_seen[excluded_dir] = excluded_dirs_seen.get(excluded_dir, 0) + 1
                continue

            # 3. Sensitive files — skip + create a reportable finding
            if _is_sensitive_file(fp):
                file_set.skipped_excluded.append(fp)
                skip_counts["sensitive_file"] += 1
                file_set.hygiene_findings.append(
                    _FindingFactory.create(
                        file_path=fp,
                        title=f"Sensitive file in repository: {_basename(fp)}",
                        explanation=(
                            f"'{_basename(fp)}' should not be in version control. "
                            f"It may contain secrets, credentials, or system artifacts."
                        ),
                        severity=Severity.MEDIUM,
                    )
                )
                continue

            # 4. Hidden files not in allowlist — skip, count only
            if _is_hidden_file(fp) and not _is_hidden_allowed(fp):
                file_set.skipped_hidden.append(fp)
                skip_counts["hidden_file"] += 1
                continue

            # 5. Large files — skip, count only
            abs_path = context.local_path / fp
            if abs_path.exists():
                try:
                    size_kb = os.path.getsize(abs_path) / 1024
                except OSError:
                    size_kb = 0.0
                if size_kb > max_size_kb:
                    file_set.skipped_large.append(fp)
                    skip_counts["large_file"] += 1
                    continue

            # 6. Normal reviewable file
            file_set.reviewable_files.append(fp)

        # Build skip summary for report metadata
        file_set.skip_summary = {
            "total_skipped": sum(skip_counts.values()),
            "counts": {k: v for k, v in skip_counts.items() if v > 0},
            "excluded_directories": {k: v for k, v in excluded_dirs_seen.items() if v > 0},
            "total_files_in_changeset": len(change_set.changed_files),
            "reviewable_count": len(file_set.reviewable_files),
        }

        total_skipped = sum(skip_counts.values())
        if total_skipped > 0:
            logger.info(
                "Hygiene: %d reviewable, %d skipped (binary=%d, excluded=%d, hidden=%d, large=%d, sensitive=%d)",
                len(file_set.reviewable_files),
                total_skipped,
                skip_counts["binary"],
                skip_counts["excluded_directory"],
                skip_counts["hidden_file"],
                skip_counts["large_file"],
                skip_counts["sensitive_file"],
            )

        return file_set


def _file_extension(path: str) -> str:
    _, ext = os.path.splitext(path)
    return ext.lower()


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1] if "/" in path else path


def _matches_excluded_dir(path: str) -> str:
    parts = PurePosixPath(path).parts
    for part in parts[:-1]:
        clean = part.rstrip("/")
        if clean in EXCLUDED_DIRECTORIES:
            return clean
        if clean.endswith(".egg-info"):
            return clean
    return ""


def _is_sensitive_file(path: str) -> bool:
    name = _basename(path)
    return name in SENSITIVE_FILES


def _is_hidden_file(path: str) -> bool:
    parts = PurePosixPath(path).parts
    for part in parts:
        if part.startswith(".") and part not in (".", ".."):
            return True
    return False


def _is_hidden_allowed(path: str) -> bool:
    parts = PurePosixPath(path).parts
    for part in parts:
        if part.startswith(".") and part in HIDDEN_ALLOWLIST:
            return True
    return False
