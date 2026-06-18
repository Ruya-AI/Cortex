from __future__ import annotations

import logging
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from qa_platform.core.finding import Finding

logger = logging.getLogger(__name__)


class Tier1Tool(ABC):
    name: str = "base"
    tier: int = 1

    @abstractmethod
    def is_available(self) -> bool:
        """Check if tool binary is installed."""

    @abstractmethod
    def is_applicable(self, file_path: str) -> bool:
        """Check if tool applies to this file type."""

    @abstractmethod
    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        """Run tool on file. MUST NOT modify files. Return findings."""

    def run_batch(self, file_paths: list[str], repo_path: Path) -> list[Finding]:
        applicable = [f for f in file_paths if self.is_applicable(f)]
        if not applicable:
            return []
        findings: list[Finding] = []
        for fp in applicable:
            try:
                file_findings = self.run(fp, repo_path)
                findings.extend(file_findings)
            except Exception as e:
                logger.warning("Tool %s failed on %s: %s", self.name, fp, e)
        return findings

    @staticmethod
    def _run_command(
        cmd: list[str], cwd: Path | None = None, timeout: int = 60,
    ) -> tuple[int, str, str]:
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                errors="replace",
            )
            return result.returncode, result.stdout, result.stderr
        except FileNotFoundError:
            return -1, "", f"Command not found: {cmd[0]}"
        except subprocess.TimeoutExpired:
            return -2, "", f"Command timed out after {timeout}s"

    @staticmethod
    def _check_binary(name: str) -> bool:
        try:
            subprocess.run(
                [name, "--version"],
                capture_output=True,
                timeout=10,
                errors="replace",
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
