"""Repository-level scanner for committed packages, secrets, large files, and hidden files.

Runs once per scan at the repo level (overrides run_batch, not per-file run).
Detects files that should not be in version control.
"""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from qa_platform.core.finding import (
    Confidence,
    Finding,
    FindingCategory,
    Severity,
)
from qa_platform.core.finding_factory import FindingFactory
from qa_platform.tools.base import Tier1Tool

logger = logging.getLogger(__name__)

PACKAGE_DIRECTORIES = {
    ".venv", "venv", "node_modules", "vendor", "bower_components",
    "site-packages", "__pycache__", ".tox",
}

SENSITIVE_PATTERNS = {
    ".env", ".env.local", ".env.production", ".env.staging", ".env.development",
    ".env.test", ".env.example",
    "credentials.json", "service-account.json", "service_account.json",
    "wp-config.php",
}

SENSITIVE_EXTENSIONS = {
    ".pem", ".key", ".p12", ".pfx", ".jks", ".keystore",
    ".cert", ".crt", ".der",
}

SENSITIVE_NAMES = {
    "id_rsa", "id_ed25519", "id_ecdsa", "id_dsa",
    ".htpasswd", ".htaccess",
}

UNNECESSARY_EXTENSIONS = {
    ".log", ".bak", ".tmp", ".swp", ".swo", ".orig",
    ".sql", ".dump",
}

UNNECESSARY_NAMES = {
    "Thumbs.db", ".DS_Store", "desktop.ini",
    "npm-debug.log", "yarn-error.log", "yarn-debug.log",
}

HIDDEN_ALLOWLIST = {
    ".gitignore", ".gitattributes", ".gitmodules",
    ".github", ".gitlab-ci.yml", ".gitlab",
    ".dockerignore", ".docker", ".editorconfig",
    ".flake8", ".pylintrc", ".pre-commit-config.yaml",
    ".prettierrc", ".prettierignore", ".eslintrc",
    ".eslintrc.json", ".eslintrc.js", ".eslintignore",
    ".babelrc", ".browserslistrc", ".npmrc", ".yarnrc",
    ".python-version", ".node-version", ".nvmrc",
    ".ruby-version", ".tool-versions", ".coveragerc",
}

LARGE_FILE_THRESHOLD = 1024 * 1024


class RepoScannerTool(Tier1Tool):
    """Detect committed packages, secrets, large files, and hidden files."""

    name: str = "repo-scanner"

    def is_available(self) -> bool:
        return True

    def is_applicable(self, file_path: str) -> bool:
        return False

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        return []

    def run_batch(self, file_paths: list[str], repo_path: Path) -> list[Finding]:
        tracked = self._git_ls_files(repo_path)
        if not tracked:
            return []

        findings: list[Finding] = []
        findings.extend(self._check_packages(tracked, repo_path))
        findings.extend(self._check_sensitive(tracked))
        findings.extend(self._check_large_files(tracked, repo_path))
        findings.extend(self._check_hidden_files(tracked))
        findings.extend(self._check_unnecessary(tracked))
        return findings

    @staticmethod
    def _git_ls_files(repo_path: Path) -> list[str]:
        try:
            result = subprocess.run(
                ["git", "ls-files"],
                cwd=str(repo_path),
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                return [f for f in result.stdout.strip().split("\n") if f]
        except Exception as e:
            logger.warning("repo-scanner: git ls-files failed: %s", e)
        return []

    def _check_packages(self, tracked: list[str], repo_path: Path) -> list[Finding]:
        findings: list[Finding] = []
        dir_counts: dict[str, list[str]] = {}

        for fp in tracked:
            parts = Path(fp).parts
            for part in parts[:-1]:
                if part in PACKAGE_DIRECTORIES:
                    dir_counts.setdefault(part, []).append(fp)
                    break

        for dirname, files in dir_counts.items():
            total_size = 0
            for fp in files[:100]:
                try:
                    total_size += os.path.getsize(repo_path / fp)
                except OSError:
                    pass
            if len(files) > 100:
                total_size = int(total_size * len(files) / 100)

            size_mb = total_size / (1024 * 1024)
            findings.append(FindingFactory.create_from_tool(
                tool_name=self.name,
                file=dirname + "/",
                start_line=1,
                end_line=1,
                severity=Severity.CRITICAL,
                category=FindingCategory.HYGIENE,
                title=f"Package directory '{dirname}/' committed to repository ({len(files)} files, {size_mb:.1f} MB)",
                explanation=(
                    f"The directory '{dirname}/' contains {len(files)} tracked files "
                    f"totaling approximately {size_mb:.1f} MB. Package and dependency "
                    f"directories should not be committed to version control. They "
                    f"bloat the repository, slow clones, and may contain vulnerable "
                    f"transitive dependencies. Use .gitignore and install from "
                    f"requirements.txt / package.json instead."
                ),
                recommendation=(
                    f"Run: git rm -r --cached {dirname}/\n"
                    f"Add '{dirname}/' to .gitignore if not already present.\n"
                    f"Commit the removal and .gitignore change."
                ),
                confidence=Confidence.CONFIRMED,
            ))

        return findings

    def _check_sensitive(self, tracked: list[str]) -> list[Finding]:
        findings: list[Finding] = []

        for fp in tracked:
            name = Path(fp).name
            ext = Path(fp).suffix.lower()

            reason = ""
            if name in SENSITIVE_PATTERNS:
                reason = f"'{name}' may contain secrets, API keys, or database credentials"
            elif ext in SENSITIVE_EXTENSIONS:
                reason = f"'{ext}' files typically contain private keys or certificates"
            elif name in SENSITIVE_NAMES:
                reason = f"'{name}' is a private key or sensitive authentication file"

            if reason:
                findings.append(FindingFactory.create_from_tool(
                    tool_name=self.name,
                    file=fp,
                    start_line=1,
                    end_line=1,
                    severity=Severity.CRITICAL,
                    category=FindingCategory.SECURITY,
                    title=f"Sensitive file tracked in repository: {name}",
                    explanation=(
                        f"The file '{fp}' is tracked by git. {reason}. "
                        f"Committing sensitive files exposes credentials in git "
                        f"history even after deletion. Anyone with repo access "
                        f"can retrieve them."
                    ),
                    recommendation=(
                        f"1. Remove from tracking: git rm --cached {fp}\n"
                        f"2. Add to .gitignore: echo '{name}' >> .gitignore\n"
                        f"3. Rotate any exposed credentials immediately.\n"
                        f"4. Consider using git-filter-repo to purge from history."
                    ),
                    confidence=Confidence.CONFIRMED,
                ))

        return findings

    def _check_large_files(self, tracked: list[str], repo_path: Path) -> list[Finding]:
        findings: list[Finding] = []

        for fp in tracked:
            try:
                size = os.path.getsize(repo_path / fp)
            except OSError:
                continue

            if size > LARGE_FILE_THRESHOLD:
                size_mb = size / (1024 * 1024)
                ext = Path(fp).suffix.lower()
                findings.append(FindingFactory.create_from_tool(
                    tool_name=self.name,
                    file=fp,
                    start_line=1,
                    end_line=1,
                    severity=Severity.HIGH,
                    category=FindingCategory.HYGIENE,
                    title=f"Large file tracked: {Path(fp).name} ({size_mb:.1f} MB)",
                    explanation=(
                        f"The file '{fp}' is {size_mb:.1f} MB. Large files in git "
                        f"permanently bloat the repository size since git stores "
                        f"the full content of every version. This slows clones "
                        f"and increases storage costs."
                    ),
                    recommendation=(
                        f"Consider using Git LFS for large files, or remove from "
                        f"tracking if the file is generated/downloadable: "
                        f"git rm --cached {fp}"
                    ),
                    confidence=Confidence.CONFIRMED,
                ))

        return findings

    def _check_hidden_files(self, tracked: list[str]) -> list[Finding]:
        findings: list[Finding] = []
        seen_dirs: set[str] = set()

        for fp in tracked:
            parts = Path(fp).parts
            for part in parts:
                if not part.startswith("."):
                    continue
                if part in (".", ".."):
                    continue
                if part in HIDDEN_ALLOWLIST:
                    continue
                if part in PACKAGE_DIRECTORIES:
                    break
                if part in seen_dirs:
                    break

                seen_dirs.add(part)
                is_dir = part != parts[-1]

                if is_dir:
                    count = sum(1 for f in tracked if f"/{part}/" in f or f.startswith(f"{part}/"))
                    findings.append(FindingFactory.create_from_tool(
                        tool_name=self.name,
                        file=f"{part}/",
                        start_line=1,
                        end_line=1,
                        severity=Severity.LOW,
                        category=FindingCategory.HYGIENE,
                        title=f"Hidden directory '{part}/' tracked ({count} files)",
                        explanation=(
                            f"Hidden directory '{part}/' contains {count} tracked files. "
                            f"Hidden directories often contain tool caches, IDE settings, "
                            f"or local configuration that should not be shared."
                        ),
                        recommendation=f"Review if '{part}/' should be in .gitignore.",
                        confidence=Confidence.LIKELY,
                    ))
                else:
                    findings.append(FindingFactory.create_from_tool(
                        tool_name=self.name,
                        file=fp,
                        start_line=1,
                        end_line=1,
                        severity=Severity.LOW,
                        category=FindingCategory.HYGIENE,
                        title=f"Hidden file tracked: {part}",
                        explanation=(
                            f"Hidden file '{fp}' is tracked by git. Hidden files "
                            f"(starting with '.') are typically local configuration "
                            f"and may not belong in the repository."
                        ),
                        recommendation=f"Review if '{part}' should be in .gitignore.",
                        confidence=Confidence.LIKELY,
                    ))
                break

        return findings

    def _check_unnecessary(self, tracked: list[str]) -> list[Finding]:
        findings: list[Finding] = []

        for fp in tracked:
            name = Path(fp).name
            ext = Path(fp).suffix.lower()

            reason = ""
            if name in UNNECESSARY_NAMES:
                reason = f"'{name}' is an OS/tool artifact"
            elif ext in UNNECESSARY_EXTENSIONS:
                reason = f"'{ext}' files are typically temporary, backup, or generated"

            if reason:
                findings.append(FindingFactory.create_from_tool(
                    tool_name=self.name,
                    file=fp,
                    start_line=1,
                    end_line=1,
                    severity=Severity.MEDIUM,
                    category=FindingCategory.HYGIENE,
                    title=f"Unnecessary file tracked: {name}",
                    explanation=(
                        f"The file '{fp}' is tracked by git. {reason}. "
                        f"These files add noise to the repository and should "
                        f"typically be excluded via .gitignore."
                    ),
                    recommendation=(
                        f"Remove from tracking: git rm --cached {fp}\n"
                        f"Add to .gitignore if applicable."
                    ),
                    confidence=Confidence.LIKELY,
                ))

        return findings
