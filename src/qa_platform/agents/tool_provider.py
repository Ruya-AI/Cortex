from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class AgentToolProvider:
    """Provides read-only tools for agents to explore code."""

    def __init__(self, repo_path: Path):
        self._repo_path = repo_path

    def read_file(self, path: str, start_line: int | None = None, end_line: int | None = None) -> str:
        full_path = self._repo_path / path
        if not full_path.exists() or not full_path.is_file():
            return f"[File not found: {path}]"
        try:
            content = full_path.read_text(errors="replace")
            lines = content.splitlines()
            if start_line is not None or end_line is not None:
                s = max(0, (start_line or 1) - 1)
                e = min(len(lines), end_line or len(lines))
                selected = lines[s:e]
                return "\n".join(f"{i+s+1:4d} | {line}" for i, line in enumerate(selected))
            return content
        except OSError as e:
            return f"[Error reading {path}: {e}]"

    def grep(self, pattern: str, path: str | None = None, scope: str | None = None) -> str:
        search_path = self._repo_path / (path or scope or ".")
        try:
            result = subprocess.run(
                ["grep", "-rn", "--include=*.py", "--include=*.js", "--include=*.ts",
                 "--include=*.go", "--include=*.java", "--include=*.rb",
                 "-l" if not path else "-n", pattern, str(search_path)],
                capture_output=True, text=True, timeout=30, errors="replace",
            )
            output = result.stdout.strip()
            if not output:
                return f"[No matches for '{pattern}']"
            # Limit output
            lines = output.splitlines()
            if len(lines) > 50:
                return "\n".join(lines[:50]) + f"\n[... {len(lines) - 50} more results]"
            return output
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return f"[grep failed for pattern '{pattern}']"

    def git_diff(self, file: str | None = None, base: str | None = None) -> str:
        cmd = ["git", "diff"]
        if base:
            cmd.append(base)
        cmd.extend(["--no-color", "--unified=3"])
        if file:
            cmd.extend(["--", file])
        try:
            result = subprocess.run(cmd, cwd=self._repo_path, capture_output=True,
                                    text=True, timeout=30, errors="replace")
            return result.stdout[:10000] if result.stdout else "[No diff]"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return "[git diff failed]"

    def expand_context(self, file: str, line: int, radius: int = 10) -> str:
        return self.read_file(file, start_line=max(1, line - radius), end_line=line + radius)

    def list_directory(self, path: str = ".") -> str:
        dir_path = self._repo_path / path
        if not dir_path.exists() or not dir_path.is_dir():
            return f"[Directory not found: {path}]"
        try:
            entries = sorted(dir_path.iterdir())
            lines = []
            for entry in entries[:100]:
                rel = entry.relative_to(self._repo_path)
                marker = "/" if entry.is_dir() else ""
                lines.append(f"  {rel}{marker}")
            if len(entries) > 100:
                lines.append(f"  [... {len(entries) - 100} more entries]")
            return "\n".join(lines)
        except OSError as e:
            return f"[Error listing {path}: {e}]"

    def get_tool_descriptions(self) -> list[dict]:
        """Return tool descriptions for LLM tool-use protocol."""
        return [
            {
                "name": "read_file",
                "description": "Read file content. Optionally specify start_line and end_line for a range.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative file path"},
                        "start_line": {"type": "integer", "description": "Start line (1-based, optional)"},
                        "end_line": {"type": "integer", "description": "End line (optional)"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "grep",
                "description": "Search for a pattern in the codebase. Returns matching lines.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "Search pattern (regex)"},
                        "scope": {"type": "string", "description": "Directory to search in (optional)"},
                    },
                    "required": ["pattern"],
                },
            },
            {
                "name": "expand_context",
                "description": "Read code around a specific line with surrounding context.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file": {"type": "string", "description": "File path"},
                        "line": {"type": "integer", "description": "Center line number"},
                        "radius": {"type": "integer", "description": "Lines above and below (default 10)"},
                    },
                    "required": ["file", "line"],
                },
            },
            {
                "name": "list_directory",
                "description": "List files and subdirectories in a directory.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path (default '.')"},
                    },
                    "required": [],
                },
            },
        ]

    def execute_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool by name with given arguments."""
        if tool_name == "read_file":
            return self.read_file(arguments["path"], arguments.get("start_line"), arguments.get("end_line"))
        elif tool_name == "grep":
            return self.grep(arguments["pattern"], scope=arguments.get("scope"))
        elif tool_name == "expand_context":
            return self.expand_context(arguments["file"], arguments["line"], arguments.get("radius", 10))
        elif tool_name == "list_directory":
            return self.list_directory(arguments.get("path", "."))
        else:
            return f"[Unknown tool: {tool_name}]"
