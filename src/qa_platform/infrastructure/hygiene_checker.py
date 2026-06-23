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
        ".coveragerc", ".flake8",
    }
)


class FindingFactory:
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
    """Filter files into reviewable vs. skipped and flag hygiene issues.

    Exclusion priority:
    1. Binary files → skip
    2. Files in excluded directories (.venv, node_modules, etc.) → skip
    3. Sensitive files (.env, .DS_Store) → skip
    4. Hidden files (dotfiles not in allowlist) → skip
    5. Large files → skip
    6. Everything else → reviewable
    """

    def check(
        self,
        context: RepositoryContext,
        change_set: ChangeSet,
        config: dict,
    ) -> FileSet:
        FindingFactory.reset()

        max_size_kb: int = config.get("max_file_size_kb", 10240)
        extra_binary: set[str] = set(config.get("extra_binary_extensions", []))
        all_binary = BINARY_EXTENSIONS | extra_binary

        file_set = FileSet()

        for fc in change_set.changed_files:
            fp = fc.file_path
            ext = _file_extension(fp)

            # 1. Binary
            if ext in all_binary:
                file_set.skipped_binary.append(fp)
                file_set.hygiene_findings.append(
                    FindingFactory.create(
                        file_path=fp,
                        title="Binary file skipped",
                        explanation=f"Binary file ({ext}) excluded from review.",
                        severity=Severity.INFO,
                    )
                )
                continue

            # 2. Excluded directory
            excluded_dir = _matches_excluded_dir(fp)
            if excluded_dir:
                file_set.skipped_excluded.append(fp)
                file_set.hygiene_findings.append(
                    FindingFactory.create(
                        file_path=fp,
                        title=f"File in excluded directory ({excluded_dir}/)",
                        explanation=(
                            f"File is inside '{excluded_dir}/' which contains "
                            f"packages, generated code, or cache. Excluded from "
                            f"review to avoid scanning third-party code."
                        ),
                        severity=Severity.INFO,
                    )
                )
                continue

            # 3. Sensitive files
            if _is_sensitive_file(fp):
                file_set.skipped_excluded.append(fp)
                file_set.hygiene_findings.append(
                    FindingFactory.create(
                        file_path=fp,
                        title="Sensitive file skipped",
                        explanation=(
                            f"File '{_basename(fp)}' is a sensitive or system "
                            f"file that should not be in version control. "
                            f"Skipped from review."
                        ),
                        severity=Severity.MEDIUM,
                    )
                )
                continue

            # 4. Hidden files not in allowlist
            if _is_hidden_file(fp) and not _is_hidden_allowed(fp):
                file_set.skipped_hidden.append(fp)
                file_set.hygiene_findings.append(
                    FindingFactory.create(
                        file_path=fp,
                        title="Hidden file skipped",
                        explanation=(
                            f"Hidden file '{_basename(fp)}' (starts with '.') "
                            f"skipped from review. Hidden files are excluded by "
                            f"default unless explicitly allowlisted."
                        ),
                        severity=Severity.INFO,
                    )
                )
                continue

            # 5. Large files
            abs_path = context.local_path / fp
            if abs_path.exists():
                try:
                    size_kb = os.path.getsize(abs_path) / 1024
                except OSError:
                    size_kb = 0.0
                if size_kb > max_size_kb:
                    file_set.skipped_large.append(fp)
                    file_set.hygiene_findings.append(
                        FindingFactory.create(
                            file_path=fp,
                            title="File exceeds size threshold",
                            explanation=(
                                f"File is {size_kb:.0f} KiB, exceeding the "
                                f"{max_size_kb} KiB limit. Skipped from review."
                            ),
                            severity=Severity.INFO,
                        )
                    )
                    continue

            # 6. Normal reviewable file
            file_set.reviewable_files.append(fp)

        skipped_total = (
            len(file_set.skipped_binary)
            + len(file_set.skipped_large)
            + len(file_set.skipped_excluded)
            + len(file_set.skipped_hidden)
        )
        if skipped_total > 0:
            logger.info(
                "Hygiene: %d reviewable, %d skipped (binary=%d, excluded=%d, hidden=%d, large=%d)",
                len(file_set.reviewable_files),
                skipped_total,
                len(file_set.skipped_binary),
                len(file_set.skipped_excluded),
                len(file_set.skipped_hidden),
                len(file_set.skipped_large),
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
        if part.startswith("."):
            if part in HIDDEN_ALLOWLIST:
                return True
            if any(part.startswith(a.rstrip("/")) for a in HIDDEN_ALLOWLIST if a.endswith("/")):
                return True
    return False
