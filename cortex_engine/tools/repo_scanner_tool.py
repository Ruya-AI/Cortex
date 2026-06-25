"""Repository-level scanner using Trivy for vulnerabilities, secrets, and
misconfigurations, plus built-in checks for committed packages, large files,
and hidden files.

Runs once per scan at the repo level (overrides run_batch).
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

from cortex_engine.core.finding import (
    Confidence,
    Finding,
    FindingCategory,
    Severity,
)
from cortex_engine.core.finding_factory import FindingFactory
from cortex_engine.tools.base import Tier1Tool

logger = logging.getLogger(__name__)

_TRIVY_SEV_MAP = {
    "CRITICAL": Severity.CRITICAL,
    "HIGH": Severity.HIGH,
    "MEDIUM": Severity.MEDIUM,
    "LOW": Severity.LOW,
    "UNKNOWN": Severity.MEDIUM,
}

PACKAGE_DIRECTORIES = {
    ".venv", "venv", "node_modules", "vendor", "bower_components",
    "site-packages", "__pycache__", ".tox",
}

SENSITIVE_PATTERNS = {
    ".env", ".env.local", ".env.production", ".env.staging",
    ".env.development", ".env.test",
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
    """Detect vulnerabilities, secrets, misconfigurations, committed packages,
    large files, and hidden files using Trivy + built-in checks."""

    name: str = "repo-scanner"

    def is_available(self) -> bool:
        return True

    def is_applicable(self, file_path: str) -> bool:
        return False

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        return []

    def run_batch(self, file_paths: list[str], repo_path: Path) -> list[Finding]:
        findings: list[Finding] = []

        # Trivy scan (vulnerabilities, secrets, misconfigurations)
        findings.extend(self._run_trivy(repo_path))

        # Built-in git-level checks
        tracked = self._git_ls_files(repo_path)
        if tracked:
            findings.extend(self._check_packages(tracked, repo_path))
            findings.extend(self._check_sensitive(tracked))
            findings.extend(self._check_large_files(tracked, repo_path))
            findings.extend(self._check_hidden_files(tracked))
            findings.extend(self._check_unnecessary(tracked))

        return findings

    # ------------------------------------------------------------------
    # Trivy integration
    # ------------------------------------------------------------------

    def _run_trivy(self, repo_path: Path) -> list[Finding]:
        if not self._check_binary("trivy"):
            logger.info("repo-scanner: trivy not installed, skipping vulnerability/secret/misconfig scan")
            return []

        try:
            result = subprocess.run(
                [
                    "trivy", "fs",
                    "--scanners", "vuln,secret,misconfig",
                    "--format", "json",
                    "--quiet",
                    "--skip-db-update",
                    str(repo_path),
                ],
                capture_output=True, text=True, timeout=120,
                cwd=str(repo_path),
            )
        except subprocess.TimeoutExpired:
            logger.warning("repo-scanner: trivy timed out after 300s")
            return []
        except Exception as e:
            logger.warning("repo-scanner: trivy failed: %s", e)
            return []

        if not result.stdout.strip():
            return []

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            logger.warning("repo-scanner: failed to parse trivy JSON output")
            return []

        findings: list[Finding] = []

        for scan_result in data.get("Results", []):
            target = scan_result.get("Target", "")

            # Vulnerabilities
            for vuln in scan_result.get("Vulnerabilities", []):
                findings.append(self._vuln_to_finding(vuln, target))

            # Secrets
            for secret in scan_result.get("Secrets", []):
                findings.append(self._secret_to_finding(secret, target))

            # Misconfigurations
            for misconf in scan_result.get("Misconfigurations", []):
                findings.append(self._misconf_to_finding(misconf, target))

        return findings

    def _vuln_to_finding(self, vuln: dict, target: str) -> Finding:
        vuln_id = vuln.get("VulnerabilityID", "UNKNOWN")
        pkg = vuln.get("PkgName", "unknown")
        installed = vuln.get("InstalledVersion", "?")
        fixed = vuln.get("FixedVersion", "")
        sev_str = vuln.get("Severity", "UNKNOWN").upper()
        severity = _TRIVY_SEV_MAP.get(sev_str, Severity.MEDIUM)
        title_text = vuln.get("Title", "")
        description = vuln.get("Description", "")
        primary_url = vuln.get("PrimaryURL", "")

        recommendation = f"Update '{pkg}' from {installed} to fix {vuln_id}."
        if fixed:
            recommendation = f"Update '{pkg}' from {installed} to {fixed}."

        return FindingFactory.create_from_tool(
            tool_name=self.name,
            file=target,
            start_line=1,
            end_line=1,
            severity=severity,
            category=FindingCategory.SECURITY,
            title=f"[{vuln_id}] {title_text or pkg} (pkg: {pkg}@{installed})",
            explanation=(
                f"{description[:500]}\n\n"
                f"Package: {pkg}@{installed}\n"
                f"Vulnerability: {vuln_id}\n"
                f"{f'Reference: {primary_url}' if primary_url else ''}"
            ).strip(),
            recommendation=recommendation,
            confidence=Confidence.CONFIRMED,
        )

    def _secret_to_finding(self, secret: dict, target: str) -> Finding:
        rule_id = secret.get("RuleID", "unknown")
        title = secret.get("Title", "Secret detected")
        sev_str = secret.get("Severity", "HIGH").upper()
        severity = _TRIVY_SEV_MAP.get(sev_str, Severity.HIGH)
        start_line = secret.get("StartLine", 1)
        end_line = secret.get("EndLine", start_line)
        category = secret.get("Category", "")
        match = secret.get("Match", "")

        return FindingFactory.create_from_tool(
            tool_name=self.name,
            file=target,
            start_line=start_line,
            end_line=end_line,
            severity=severity,
            category=FindingCategory.SECURITY,
            title=f"Secret detected: {title} [{rule_id}]",
            explanation=(
                f"Trivy detected a potential secret or credential.\n"
                f"Rule: {rule_id}\n"
                f"Category: {category}\n"
                f"Match: {match[:100]}{'...' if len(match) > 100 else ''}"
            ),
            recommendation=(
                "1. Remove the secret from the source code.\n"
                "2. Use environment variables or a secrets manager.\n"
                "3. Rotate the exposed credential immediately.\n"
                "4. Consider using git-filter-repo to purge from history."
            ),
            confidence=Confidence.CONFIRMED,
        )

    def _misconf_to_finding(self, misconf: dict, target: str) -> Finding:
        avd_id = misconf.get("AVDID", misconf.get("ID", ""))
        title = misconf.get("Title", "Misconfiguration")
        description = misconf.get("Description", "")
        resolution = misconf.get("Resolution", "")
        sev_str = misconf.get("Severity", "MEDIUM").upper()
        severity = _TRIVY_SEV_MAP.get(sev_str, Severity.MEDIUM)
        start_line = misconf.get("CauseMetadata", {}).get("StartLine", 1)
        end_line = misconf.get("CauseMetadata", {}).get("EndLine", start_line)

        return FindingFactory.create_from_tool(
            tool_name=self.name,
            file=target,
            start_line=start_line,
            end_line=end_line,
            severity=severity,
            category=FindingCategory.SECURITY,
            title=f"[{avd_id}] {title}",
            explanation=description[:1000],
            recommendation=resolution or "Review and fix the misconfiguration.",
            confidence=Confidence.CONFIRMED,
        )

    # ------------------------------------------------------------------
    # Built-in git-level checks
    # ------------------------------------------------------------------

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

    @staticmethod
    def _in_package_dir(fp: str) -> bool:
        parts = Path(fp).parts
        return any(part in PACKAGE_DIRECTORIES for part in parts[:-1])

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
                start_line=1, end_line=1,
                severity=Severity.CRITICAL,
                category=FindingCategory.HYGIENE,
                title=f"Package directory '{dirname}/' committed ({len(files)} files, {size_mb:.1f} MB)",
                explanation=(
                    f"'{dirname}/' contains {len(files)} tracked files (~{size_mb:.1f} MB). "
                    f"Package directories should not be committed — they bloat the repo, "
                    f"slow clones, and may contain vulnerable transitive dependencies."
                ),
                recommendation=(
                    f"git rm -r --cached {dirname}/\n"
                    f"Add '{dirname}/' to .gitignore."
                ),
                confidence=Confidence.CONFIRMED,
            ))

        return findings

    def _check_sensitive(self, tracked: list[str]) -> list[Finding]:
        findings: list[Finding] = []
        for fp in tracked:
            if self._in_package_dir(fp):
                continue
            name = Path(fp).name
            ext = Path(fp).suffix.lower()
            reason = ""
            if name in SENSITIVE_PATTERNS:
                reason = f"may contain secrets, API keys, or credentials"
            elif ext in SENSITIVE_EXTENSIONS:
                reason = f"typically contains private keys or certificates"
            elif name in SENSITIVE_NAMES:
                reason = f"is a private key or authentication file"
            if reason:
                findings.append(FindingFactory.create_from_tool(
                    tool_name=self.name, file=fp, start_line=1, end_line=1,
                    severity=Severity.CRITICAL, category=FindingCategory.SECURITY,
                    title=f"Sensitive file tracked: {name}",
                    explanation=f"'{fp}' {reason}. Committing exposes credentials in git history.",
                    recommendation=f"git rm --cached {fp}\nAdd '{name}' to .gitignore.\nRotate exposed credentials.",
                    confidence=Confidence.CONFIRMED,
                ))
        return findings

    def _check_large_files(self, tracked: list[str], repo_path: Path) -> list[Finding]:
        findings: list[Finding] = []
        for fp in tracked:
            if self._in_package_dir(fp):
                continue
            try:
                size = os.path.getsize(repo_path / fp)
            except OSError:
                continue
            if size > LARGE_FILE_THRESHOLD:
                size_mb = size / (1024 * 1024)
                findings.append(FindingFactory.create_from_tool(
                    tool_name=self.name, file=fp, start_line=1, end_line=1,
                    severity=Severity.HIGH, category=FindingCategory.HYGIENE,
                    title=f"Large file tracked: {Path(fp).name} ({size_mb:.1f} MB)",
                    explanation=f"'{fp}' is {size_mb:.1f} MB. Large files permanently bloat the repo.",
                    recommendation=f"Use Git LFS or remove: git rm --cached {fp}",
                    confidence=Confidence.CONFIRMED,
                ))
        return findings

    def _check_hidden_files(self, tracked: list[str]) -> list[Finding]:
        findings: list[Finding] = []
        seen_dirs: set[str] = set()
        for fp in tracked:
            parts = Path(fp).parts
            for part in parts:
                if not part.startswith(".") or part in (".", ".."):
                    continue
                if part in HIDDEN_ALLOWLIST or part in PACKAGE_DIRECTORIES or part in seen_dirs:
                    break
                seen_dirs.add(part)
                is_dir = part != parts[-1]
                if is_dir:
                    count = sum(1 for f in tracked if f"/{part}/" in f or f.startswith(f"{part}/"))
                    findings.append(FindingFactory.create_from_tool(
                        tool_name=self.name, file=f"{part}/", start_line=1, end_line=1,
                        severity=Severity.LOW, category=FindingCategory.HYGIENE,
                        title=f"Hidden directory '{part}/' tracked ({count} files)",
                        explanation=f"Hidden directory may contain tool caches or local config.",
                        recommendation=f"Review if '{part}/' should be in .gitignore.",
                        confidence=Confidence.LIKELY,
                    ))
                else:
                    findings.append(FindingFactory.create_from_tool(
                        tool_name=self.name, file=fp, start_line=1, end_line=1,
                        severity=Severity.LOW, category=FindingCategory.HYGIENE,
                        title=f"Hidden file tracked: {part}",
                        explanation=f"Hidden file '{fp}' may not belong in the repository.",
                        recommendation=f"Review if '{part}' should be in .gitignore.",
                        confidence=Confidence.LIKELY,
                    ))
                break
        return findings

    def _check_unnecessary(self, tracked: list[str]) -> list[Finding]:
        findings: list[Finding] = []
        for fp in tracked:
            if self._in_package_dir(fp):
                continue
            name = Path(fp).name
            ext = Path(fp).suffix.lower()
            reason = ""
            if name in UNNECESSARY_NAMES:
                reason = f"OS/tool artifact"
            elif ext in UNNECESSARY_EXTENSIONS:
                reason = f"temporary, backup, or generated file"
            if reason:
                findings.append(FindingFactory.create_from_tool(
                    tool_name=self.name, file=fp, start_line=1, end_line=1,
                    severity=Severity.MEDIUM, category=FindingCategory.HYGIENE,
                    title=f"Unnecessary file tracked: {name}",
                    explanation=f"'{fp}' is a {reason} and should not be in version control.",
                    recommendation=f"git rm --cached {fp}\nAdd to .gitignore.",
                    confidence=Confidence.LIKELY,
                ))
        return findings
