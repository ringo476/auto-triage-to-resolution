from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Import your compiled LangGraph state machine
from app.ai.graph import app_graph

router = APIRouter()

# 1. Define the expected incoming JSON payload
class BugReportPayload(BaseModel):
    ticket_id: str = Field(..., description="The ID of the ticket (e.g., BUG-101)")
    target_repo_path: str = Field(..., description="Absolute path on the host to the external codebase being debugged")
    raw_issue_description: str = Field(..., description="The actual text of the bug report")
    reporter_email: str = Field(..., description="Email of the user or system reporting the bug")
    source_channel: str = Field(default="api", description="Where this came from (slack, datadog, etc.)")

@router.post("/webhook/bug_report")
async def trigger_bug_triage(payload:BugReportPayload):
    """
    Receives a bug report and triggers the LangGraph AI workflow.
    """
    try:
        initial_state={
            "ticket_id":payload.ticket_id,
            "target_repo_path":payload.target_repo_path,
            "raw_issue_description":payload.raw_issue_description,
            "reporter_email":payload.reporter_email,
            "source_channel":payload.source_channel
        }
        final_state=await app_graph.ainvoke(initial_state)
        return {
            "status": "success",
            "ticket_id": final_state.get("ticket_id"),
            "triage_decision": final_state.get("triage_action"),
            "root_cause_analysis": final_state.get("root_cause_analysis", "N/A"),
            "pull_request_url": final_state.get("github_pr_url", "No PR generated")
        }
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500,detail=f"Graph Execution Failed: {e!s}")