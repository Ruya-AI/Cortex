from __future__ import annotations

import logging
import os

from qa_platform.core.finding import (
    Confidence,
    FindingCategory,
    Finding,
    Severity,
)
from qa_platform.core.schemas import ChangeSet, FileSet, RepositoryContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Well-known binary extensions
# ---------------------------------------------------------------------------

BINARY_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pyc", ".pyo", ".exe", ".dll", ".so", ".dylib", ".o", ".a",
        ".lib", ".bin", ".dat", ".db", ".sqlite", ".sqlite3",
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
        ".woff", ".woff2", ".ttf", ".eot",
        ".mp3", ".mp4", ".avi", ".mov",
        ".zip", ".tar", ".gz", ".jar", ".war", ".class",
        ".pdf",
    }
)

# ---------------------------------------------------------------------------
# Paths that should be flagged during hygiene checks
# ---------------------------------------------------------------------------

FLAGGED_PATH_PATTERNS: list[str] = [
    "node_modules/",
    ".env",
    "__pycache__/",
    ".git/",
    ".DS_Store",
    "venv/",
    ".venv/",
    "dist/",
    "build/",
    ".egg-info/",
]


# ---------------------------------------------------------------------------
# FindingFactory -- lightweight helper for creating hygiene findings
# ---------------------------------------------------------------------------


class FindingFactory:
    """Create standardised Finding objects for hygiene issues."""

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


# ---------------------------------------------------------------------------
# HygieneChecker
# ---------------------------------------------------------------------------


class HygieneChecker:
    """Filter files into reviewable vs. skipped and flag hygiene issues.

    * Binary files: skip + flag.
    * Flagged text files (node_modules, .env, etc.): flag + still scan.
    * Large files (over config threshold): skip + flag.
    """

    def check(
        self,
        context: RepositoryContext,
        change_set: ChangeSet,
        config: dict,
    ) -> FileSet:
        """Classify every changed file and return a FileSet.

        Parameters
        ----------
        context:
            Repository metadata (provides ``local_path``).
        change_set:
            The set of files detected as changed.
        config:
            Dict with optional keys:
            - ``max_file_size_kb`` (int): threshold in KiB (default 10240).
            - ``extra_binary_extensions`` (list[str]): additional extensions
              to treat as binary.
        """
        FindingFactory.reset()

        max_size_kb: int = config.get("max_file_size_kb", 10240)
        extra_binary: set[str] = set(config.get("extra_binary_extensions", []))
        all_binary = BINARY_EXTENSIONS | extra_binary

        file_set = FileSet()

        for fc in change_set.changed_files:
            fp = fc.file_path
            ext = _file_extension(fp)

            # --- Binary? ------------------------------------------------
            if ext in all_binary:
                file_set.skipped_binary.append(fp)
                file_set.hygiene_findings.append(
                    FindingFactory.create(
                        file_path=fp,
                        title="Binary file in changeset",
                        explanation=f"Binary file ({ext}) skipped from review.",
                        severity=Severity.INFO,
                    )
                )
                continue

            # --- Large? -------------------------------------------------
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

            # --- Flagged path? ------------------------------------------
            is_flagged = _matches_flagged_pattern(fp)
            if is_flagged:
                file_set.flagged_files.append(fp)
                file_set.hygiene_findings.append(
                    FindingFactory.create(
                        file_path=fp,
                        title="File in flagged path",
                        explanation=(
                            f"File matches a flagged path pattern "
                            f"({is_flagged}). Included in review but flagged."
                        ),
                        severity=Severity.LOW,
                    )
                )
                # Flagged files are still reviewable
                file_set.reviewable_files.append(fp)
                continue

            # --- Normal reviewable file ---------------------------------
            file_set.reviewable_files.append(fp)

        return file_set


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _file_extension(path: str) -> str:
    """Return the lowercase file extension including the dot, e.g. '.py'."""
    _, ext = os.path.splitext(path)
    return ext.lower()


def _matches_flagged_pattern(path: str) -> str:
    """Return the matching pattern string if *path* matches, else ''."""
    for pattern in FLAGGED_PATH_PATTERNS:
        if pattern.endswith("/"):
            # Directory pattern -- check if any component matches
            if pattern.rstrip("/") in path.split("/"):
                return pattern
            # Also match if the path contains the pattern substring
            if pattern in path:
                return pattern
        else:
            # Exact filename or suffix
            basename = path.rsplit("/", 1)[-1] if "/" in path else path
            if pattern.startswith("*."):
                # Glob-style suffix
                if basename.endswith(pattern[1:]):
                    return pattern
            elif basename == pattern or path.endswith("/" + pattern):
                return pattern
            # Also match the pattern anywhere in the path
            if pattern in path:
                return pattern
    return ""
