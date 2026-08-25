from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Shared state object flowing through the 
    LangGraph multi-agent pipeline.
    """
    # 1. Ingestion Data (From Webhook)
    ticket_id: str
    target_repo_path: str  # The absolute path to the external repo to debug on the host machine
    raw_issue_description: str
    reporter_email: str
    source_channel: str  # e.g., "slack", "zendesk"
    slack_channel_id: str | None  # Slack channel to reply into, if source_channel == "slack"

    # 2. Context Researcher Agent Outputs
    rag_context: str

    # 3. Diagnostic / Sandbox Executor Agent Outputs
    is_reproducible: bool
    reproduction_command: str | None
    sandbox_execution_logs: str

    # 4. Triage & Routing Decisions
    # Action options: "USER_ERROR", "JIRA_TICKET", "AUTO_PR"
    triage_action: str | None
    root_cause_analysis: str | None

    # 5. External System Results
    proposed_patch: str | None
    jira_issue_key: str | None
    github_issue_url: str | None
    github_pr_url: str | None

    # 6. LLM Conversation History & Traceability
    # `add_messages` automatically appends new messages rather than overwriting
    messages: Annotated[list[BaseMessage],add_messages]

    # 7. Error Handling
    error_flag: bool
    error_message: str | None