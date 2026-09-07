from pathlib import Path
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.ai.llm import get_chat_llm
from app.ai.mcp_runtime import run_tool_loop, sandbox_session
from app.ai.prompts import SANDBOX_HUMAN_TEMPLATE, TRIAGE_HUMAN_TEMPLATE
from app.ai.state import AgentState
from app.database import search_knowledge_base
from app.integrations.jira import create_jira_ticket
from app.integrations.slack import send_slack_message


# --- HELPER: Dynamic Skill Loader ---
def load_skill(skill_filename: str) -> str:
    """Reads the Markdown skill file from the skills directory at runtime."""
    skill_path = Path(__file__).parent / "skills" / skill_filename
    try:
        with open(skill_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"ERROR: Missing skill file {skill_filename}"


# --- PYDANTIC SCHEMAS ---
class TriageDecision(BaseModel):
    action: Literal["USER_ERROR", "AUTO_PR", "JIRA_TICKET"] = Field(
        description="The routing decision based on the logs and SOP rules."
    )
    analysis: str = Field(
        description="Technical breakdown explaining the root cause of the error."
    )


# --- LANGGRAPH NODES ---

async def rag_node(state: AgentState) -> dict:
    """Retrieves relevant API schemas, docs, or past tickets from pgvector."""
    doc = state["raw_issue_description"]
    retrieved_docs = await search_knowledge_base(doc)
    return {"rag_context": retrieved_docs}


async def repro_node(state: AgentState) -> dict:
    async with sandbox_session(state["target_repo_path"]) as tools:
        llm = get_chat_llm()
        bind_llm = llm.bind_tools(tools)

        repro_skill_text = load_skill("repro_skill.md")

        # 1. We read the existing global messages from the state (if any)
        # and append our System and Human prompts to start the context.
        current_messages = state.get("messages", []) + [
            SystemMessage(content=repro_skill_text),
            HumanMessage(content=SANDBOX_HUMAN_TEMPLATE.format(
                raw_issue_description=state["raw_issue_description"],
                rag_context=state["rag_context"]
            ))
        ]

        new_messages_to_return = await run_tool_loop(bind_llm, tools, current_messages)

        # Extract just the raw tool strings for the triage node to read easily
        execution_logs = "\n".join([m.content for m in new_messages_to_return if isinstance(m, ToolMessage)])

        # 2. PROPER PATTERN: Return BOTH the logs and the new message history
        return {
            "sandbox_execution_logs": execution_logs or "No logs produced.",
            "messages": new_messages_to_return  # LangGraph will now auto-append these globally!
        }


async def triage_node(state: AgentState) -> dict:
    """
    Evaluates execution logs and RAG context against triage_skill.md SOP
    to output a structured routing decision (USER_ERROR, AUTO_PR, or JIRA_TICKET).
    """
    llm = get_chat_llm()
    triage_skill_text = load_skill("triage_skill.md")

    triage_prompt = ChatPromptTemplate.from_messages([
        ("system", triage_skill_text),
        ("human", TRIAGE_HUMAN_TEMPLATE)
    ])

    structured_llm = llm.with_structured_output(TriageDecision)
    triage_chain = triage_prompt | structured_llm

    response = None
    last_error = None
    # Catches any failure mode of structured output (validation errors, parsing
    # errors, malformed tool-call responses), not just pydantic ValidationError.
    for _ in range(3):
        try:
            response = await triage_chain.ainvoke({
                "raw_issue_description": state["raw_issue_description"],
                "rag_context": state["rag_context"],
                "sandbox_execution_logs": state["sandbox_execution_logs"]
            })
            break
        except Exception as e:  # noqa: BLE001
            last_error = str(e)

    if not response:
        return {
            "triage_action": "USER_ERROR",
            "root_cause_analysis": f"Failed to parse LLM response. Error: {last_error}"
        }

    return {
        "triage_action": response.action,
        "root_cause_analysis": response.analysis
    }


async def jira_node(state: AgentState) -> dict:
    """Files a Jira ticket for issues that need human follow-up but aren't auto-fixable."""
    result = await create_jira_ticket(
        summary=f"[SentinelOps] {state['raw_issue_description'][:80]}",
        description=(
            f"Root Cause Analysis:\n{state.get('root_cause_analysis', 'N/A')}\n\n"
            f"Execution Logs:\n{state.get('sandbox_execution_logs', 'N/A')}"
        )
    )
    return {"jira_issue_key": result}


async def slack_node(state: AgentState) -> dict:
    """Notifies the reporter in Slack when triage decides the report is user error."""
    channel_id = state.get("slack_channel_id")
    if not channel_id:
        # Report didn't come in through Slack (e.g. the raw API), nowhere to reply.
        return {}

    message = (
        f"Hi, we looked into ticket `{state['ticket_id']}` — this looks like user error, not a bug.\n"
        f"Analysis: {state.get('root_cause_analysis', 'N/A')}"
    )
    await send_slack_message(channel_id=channel_id, text=message)
    return {}
