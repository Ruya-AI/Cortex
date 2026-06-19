from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from qa_platform.core.schemas import RepositoryContext, ScanRequest
from qa_platform.infrastructure.git import GitOperations

logger = logging.getLogger(__name__)


class RepositoryResolver:
    """Resolve a ScanRequest.repo to a RepositoryContext.

    Handles both local paths and remote URLs (cloned to a temporary
    directory).
    """

    def resolve(self, request: ScanRequest) -> RepositoryContext:
        repo = request.repo
        if repo.startswith("http://") or repo.startswith("https://") or repo.startswith("git@"):
            return self._clone_remote(request)

        local_path = Path(repo).resolve()
        if not local_path.exists():
            raise ValueError(f"Repository path does not exist: {repo}")
        if not GitOperations.validate_repo(local_path):
            raise ValueError(f"Not a git repository: {repo}")

        if request.commit:
            # Note: we don't checkout -- we just record it. Audit-only.
            pass

        commit_info = GitOperations.get_commit_info(local_path)
        return RepositoryContext(
            local_path=local_path,
            branch=request.branch or GitOperations.get_current_branch(local_path),
            commit_sha=GitOperations.get_current_commit(local_path),
            commit_message=commit_info.get("message", "") if commit_info else "",
            remote_url=GitOperations.get_remote_url(local_path),
            is_temporary=False,
        )

    def _clone_remote(self, request: ScanRequest) -> RepositoryContext:
        target = Path(tempfile.mkdtemp(prefix="qa-platform-clone-"))
        try:
            result = GitOperations.clone_repo(
                request.repo,
                branch=request.branch,
                target_dir=target,
            )
            if result is None:
                shutil.rmtree(target, ignore_errors=True)
                raise ValueError(f"Failed to clone: {request.repo}")

            return RepositoryContext(
                local_path=target,
                branch=result.get("branch", ""),
                commit_sha=result.get("commit_sha", ""),
                remote_url=request.repo,
                is_temporary=True,
            )
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            raise

    def cleanup(self, context: RepositoryContext) -> None:
        """Remove temporary clone directory if applicable."""
        if context.is_temporary and context.local_path.exists():
            shutil.rmtree(context.local_path, ignore_errors=True)
            logger.info("Cleaned up temporary clone: %s", context.local_path)
