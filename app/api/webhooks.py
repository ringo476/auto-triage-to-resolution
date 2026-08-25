import hashlib
import hmac
import random
import time

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

# Import your compiled LangGraph state machine
from app.ai.graph import app_graph
from app.config import settings

router = APIRouter()


# 1. Define the expected incoming JSON payload
class BugReportPayload(BaseModel):
    ticket_id: str = Field(..., description="The ID of the ticket (e.g., BUG-101)")
    target_repo_path: str = Field(..., description="Absolute path on the host to the external codebase being debugged")
    raw_issue_description: str = Field(..., description="The actual text of the bug report")
    reporter_email: str = Field(..., description="Email of the user or system reporting the bug")
    source_channel: str = Field(default="api", description="Where this came from (slack, datadog, etc.)")


@router.post("/webhook/bug_report")
async def trigger_bug_triage(payload: BugReportPayload, x_webhook_secret: str | None = Header(default=None)):
    """
    Receives a bug report and triggers the LangGraph AI workflow.
    Requires the shared-secret header (X-Webhook-Secret) to match WEBHOOK_SECRET,
    since this endpoint mounts `target_repo_path` into a sandbox container and
    lets an LLM read/write files there.
    """
    if not hmac.compare_digest(x_webhook_secret or "", settings.WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Missing or invalid X-Webhook-Secret header.")

    try:
        initial_state = {
            "ticket_id": payload.ticket_id,
            "target_repo_path": payload.target_repo_path,
            "raw_issue_description": payload.raw_issue_description,
            "reporter_email": payload.reporter_email,
            "source_channel": payload.source_channel,
            "slack_channel_id": None
        }
        final_state = await app_graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": payload.ticket_id}}
        )
        return {
            "status": "success",
            "ticket_id": final_state.get("ticket_id"),
            "triage_decision": final_state.get("triage_action"),
            "root_cause_analysis": final_state.get("root_cause_analysis", "N/A"),
            "pull_request_url": final_state.get("github_pr_url", "No PR generated")
        }
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Graph Execution Failed: {e!s}")


def _verify_slack_signature(body: bytes, timestamp: str | None, signature: str | None) -> bool:
    """Validates Slack's request signature per Slack's signing-secret scheme:
    https://api.slack.com/authentication/verifying-requests-from-slack
    """
    if not settings.SLACK_SIGNING_SECRET or not timestamp or not signature:
        return False

    try:
        # Reject requests older than 5 minutes to guard against replay attacks.
        if abs(time.time() - int(timestamp)) > 60 * 5:
            return False
    except ValueError:
        return False

    base_string = f"v0:{timestamp}:{body.decode('utf-8')}"
    computed_signature = "v0=" + hmac.new(
        settings.SLACK_SIGNING_SECRET.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(computed_signature, signature)


@router.post("/webhook/slack")
async def trigger_from_slack(
    request: Request,
    x_slack_request_timestamp: str | None = Header(default=None),
    x_slack_signature: str | None = Header(default=None),
):
    """
    Catches raw Slack Outgoing Webhook form data and triggers the AI pipeline.
    Verifies Slack's request signature before doing anything with the payload.
    """
    raw_body = await request.body()
    if not _verify_slack_signature(raw_body, x_slack_request_timestamp, x_slack_signature):
        raise HTTPException(status_code=401, detail="Invalid Slack request signature.")

    try:
        # Parse the application/x-www-form-urlencoded data from Slack
        form_data = await request.form()
        text = form_data.get("text", "No message provided")
        user_name = form_data.get("user_name", "unknown_user")
        channel_id = form_data.get("channel_id")

        # Generate a random ticket ID since this didn't come from Jira
        ticket_id = f"SLACK-{random.randint(1000, 9999)}"

        initial_state = {
            "ticket_id": ticket_id,
            "target_repo_path": settings.DEFAULT_TARGET_REPO,
            "raw_issue_description": text,
            "reporter_email": f"{user_name}@slack.local",
            "source_channel": "slack",
            "slack_channel_id": channel_id
        }

        final_state = await app_graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": ticket_id}}
        )

        return {
            "text": (
                f"✅ SentinelOps analyzed bug `{ticket_id}`: "
                f"{final_state.get('triage_action', 'unknown')}"
            )
        }

    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Slack Ingestion Failed: {e!s}")
