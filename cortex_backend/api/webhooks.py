from __future__ import annotations

import logging

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("/github")
async def github_webhook(request: Request):
    """Receive GitHub webhook events for automatic PR detection."""
    _body = await request.body()  # noqa: F841  — needed for signature verification

    # Verify signature if secret is configured
    # signature = request.headers.get("X-Hub-Signature-256", "")
    # if settings.github_webhook_secret:
    #     expected = "sha256=" + hmac.new(settings.github_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    #     if not hmac.compare_digest(signature, expected):
    #         raise HTTPException(status_code=401, detail="Invalid signature")

    event = request.headers.get("X-GitHub-Event", "")
    payload = await request.json()

    if event == "pull_request":
        action = payload.get("action", "")
        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {})

        logger.info(
            "GitHub webhook: PR #%s %s on %s/%s",
            pr.get("number"), action,
            repo.get("owner", {}).get("login", ""), repo.get("name", ""),
        )

        if action in ("opened", "synchronize", "reopened"):
            # In production: look up repo config, fetch PR details, optionally trigger QA
            return {
                "status": "received",
                "event": event,
                "action": action,
                "pr_number": pr.get("number"),
                "repo": repo.get("full_name"),
            }

    return {"status": "ignored", "event": event}
