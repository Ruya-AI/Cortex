from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class GitOperations:
    """Static helper methods for git operations.

    All methods use subprocess.run with capture_output=True, text=True,
    errors="replace".
    """

    @staticmethod
    def _run_git(
        args: list[str],
        cwd: Path | None = None,
        timeout: int = 300,
    ) -> str:
        """Run a git command and return stdout.

        On non-zero exit, logs at DEBUG (not warning). On timeout or
        FileNotFoundError, returns "".
        """
        cmd = ["git"] + args
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout,
            )
            if result.returncode != 0:
                logger.debug(
                    "git %s exited %d: %s",
                    " ".join(args),
                    result.returncode,
                    result.stderr.strip(),
                )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.debug("git %s timed out after %ds", " ".join(args), timeout)
            return ""
        except FileNotFoundError:
            logger.debug("git executable not found")
            return ""

    @staticmethod
    def validate_repo(path: Path) -> bool:
        """Return True if *path* is inside a git working tree."""
        output = GitOperations._run_git(
            ["rev-parse", "--is-inside-work-tree"],
            cwd=path,
        )
        return output.lower() == "true"

    @staticmethod
    def get_current_branch(repo_path: Path) -> str:
        """Return the current branch name (e.g. 'main')."""
        return GitOperations._run_git(
            ["rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
        )

    @staticmethod
    def get_current_commit(repo_path: Path) -> str:
        """Return the full SHA of HEAD."""
        return GitOperations._run_git(
            ["rev-parse", "HEAD"],
            cwd=repo_path,
        )

    @staticmethod
    def get_commit_info(
        repo_path: Path,
        commit_sha: str = "HEAD",
    ) -> dict | None:
        """Return commit metadata dict or None on failure.

        Keys: sha, author_name, author_email, timestamp, message.
        """
        output = GitOperations._run_git(
            ["log", "-1", "--format=%H%n%an%n%ae%n%aI%n%s", commit_sha],
            cwd=repo_path,
        )
        if not output:
            return None
        lines = output.split("\n")
        if len(lines) < 5:
            return None
        return {
            "sha": lines[0],
            "author_name": lines[1],
            "author_email": lines[2],
            "timestamp": lines[3],
            "message": lines[4],
        }

    @staticmethod
    def clone_repo(
        url: str,
        branch: str | None = None,
        depth: int | None = 50,
        target_dir: Path | None = None,
        timeout: int = 300,
    ) -> dict | None:
        """Clone a repository and return metadata dict, or None on failure.

        Returns dict with keys: path, branch, commit_sha.
        """
        args = ["clone"]
        if branch:
            args += ["--branch", branch]
        if depth is not None:
            args += ["--depth", str(depth)]
        args.append(url)
        if target_dir is not None:
            args.append(str(target_dir))

        GitOperations._run_git(args, timeout=timeout)
        # _run_git logs failures at DEBUG; check if target exists
        clone_path = target_dir if target_dir else Path(url.rstrip("/").split("/")[-1].removesuffix(".git"))
        if not clone_path.exists():
            return None

        current_branch = GitOperations.get_current_branch(clone_path)
        commit_sha = GitOperations.get_current_commit(clone_path)

        return {
            "path": clone_path,
            "branch": current_branch,
            "commit_sha": commit_sha,
        }

    @staticmethod
    def get_diff(
        repo_path: Path,
        base_branch: str | None = None,
        staged: bool = False,
    ) -> str:
        """Return raw diff text."""
        if base_branch:
            args = ["diff", f"{base_branch}...HEAD"]
        elif staged:
            args = ["diff", "--cached"]
        else:
            args = ["diff", "HEAD~1", "HEAD"]
        return GitOperations._run_git(args, cwd=repo_path)

    @staticmethod
    def get_changed_files(
        repo_path: Path,
        base_branch: str | None = None,
        staged: bool = False,
    ) -> list[str]:
        """Return a list of changed file paths."""
        if base_branch:
            args = ["diff", "--name-only", f"{base_branch}...HEAD"]
        elif staged:
            args = ["diff", "--name-only", "--cached"]
        else:
            args = ["diff", "--name-only", "HEAD~1", "HEAD"]
        output = GitOperations._run_git(args, cwd=repo_path)
        if not output:
            return []
        return [line for line in output.split("\n") if line]

    @staticmethod
    def get_blame(
        repo_path: Path,
        file_path: str,
        start_line: int,
        end_line: int,
    ) -> list[dict]:
        """Return porcelain blame data for the given line range.

        Each entry: {line, sha, author_name, author_email}.
        Returns [] on failure.
        """
        output = GitOperations._run_git(
            [
                "blame",
                "--porcelain",
                f"-L{start_line},{end_line}",
                "--",
                file_path,
            ],
            cwd=repo_path,
        )
        if not output:
            return []

        results: list[dict] = []
        current_sha = ""
        current_author = ""
        current_email = ""
        current_line = 0

        for raw_line in output.split("\n"):
            # Porcelain format: first line of each block is
            # <sha> <orig-line> <final-line> [<num-lines>]
            parts = raw_line.split()
            if len(parts) >= 3 and len(parts[0]) == 40:
                current_sha = parts[0]
                try:
                    current_line = int(parts[2])
                except ValueError:
                    current_line = 0
            elif raw_line.startswith("author "):
                current_author = raw_line[len("author "):]
            elif raw_line.startswith("author-mail "):
                current_email = raw_line[len("author-mail "):].strip("<>")
            elif raw_line.startswith("\t"):
                # Content line -- emit the record
                results.append(
                    {
                        "line": current_line,
                        "sha": current_sha,
                        "author_name": current_author,
                        "author_email": current_email,
                    }
                )

        return results

    @staticmethod
    def get_config(repo_path: Path, key: str) -> str:
        """Read a git config value. SILENT on failure -- no logging."""
        try:
            result = subprocess.run(
                ["git", "config", key],
                cwd=repo_path,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=30,
            )
            if result.returncode != 0:
                return ""
            return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""

    @staticmethod
    def get_remote_url(repo_path: Path) -> str:
        """Return the URL of the 'origin' remote."""
        return GitOperations._run_git(
            ["remote", "get-url", "origin"],
            cwd=repo_path,
        )
