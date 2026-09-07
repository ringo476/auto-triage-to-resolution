import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.ai.agents.nodes import load_skill
from app.ai.llm import get_chat_llm
from app.ai.mcp_runtime import run_tool_loop, sandbox_session
from app.ai.state import AgentState
from app.config import settings
from app.integrations.github import commit_and_push_changes, create_pull_request

_SAFE_BRANCH_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_branch_suffix(ticket_id: str) -> str:
    """Sanitizes a caller-supplied ticket_id before it becomes part of a git
    branch name / shell argument — ticket_id comes straight from the webhook
    payload and could otherwise contain slashes, spaces, or `..`."""
    cleaned = _SAFE_BRANCH_CHARS.sub("-", ticket_id).strip("-")
    return cleaned or "unknown"


async def code_fix_node(state: AgentState) -> dict:
    """
    Executes when triage_action == 'AUTO_PR'. Connects to MCP server tools
    (read_file, search_codebase, run_sandbox_script) to inspect codebase files,
    generate a patch, verify the fix in the sandbox, then commits, pushes, and
    opens a GitHub PR against the target repo.
    """
    async with sandbox_session(state["target_repo_path"]) as tools:
        llm = get_chat_llm()
        bind_llm = llm.bind_tools(tools)

        code_fix_skill_text = load_skill("code_fix_skill.md")

        new_messages = [
            SystemMessage(content=code_fix_skill_text),
            HumanMessage(content=(
                f"Issue Description: {state['raw_issue_description']}\n"
                f"Root Cause Analysis: {state.get('root_cause_analysis', 'N/A')}\n"
                f"Stack Trace / Logs:\n{state['sandbox_execution_logs']}\n\n"
                "Inspect the codebase using tools, isolate the failing lines, generate "
                "the code patch, verify it in the sandbox, and summarize the PR payload."
            ))
        ]

        await run_tool_loop(bind_llm, tools, new_messages)

        # run_tool_loop can exit after max_turns while a tool call was still
        # pending, in which case the *last* message is a raw ToolMessage, not
        # the LLM's summary — walk back to find the last actual AI message.
        last_ai_message = next(
            (m for m in reversed(new_messages) if isinstance(m, AIMessage)), None
        )
        proposed_fix_summary = (
            last_ai_message.content if last_ai_message else "No summary produced (tool loop ended mid-call)."
        )

        branch_name = f"sentinelops/fix-{_safe_branch_suffix(state['ticket_id'])}"
        commit_message = f"fix: automated resolution for {state['ticket_id']}"

        pushed = await commit_and_push_changes(
            repo_path=state["target_repo_path"],
            branch_name=branch_name,
            commit_message=commit_message
        )

        if not pushed:
            return {
                "proposed_patch": proposed_fix_summary,
                "github_pr_url": None,
                "error_flag": True,
                "error_message": "Failed to commit/push the fix branch; PR was not created.",
                "messages": new_messages
            }

        pr_url = await create_pull_request(
            repo_name=settings.GITHUB_REPO,
            branch_name=branch_name,
            base_branch=settings.GITHUB_BASE_BRANCH,
            title=f"fix: Automated resolution for issue - {state['raw_issue_description'][:50]}",
            body=(
                f"## Root Cause Analysis\n{state.get('root_cause_analysis', 'N/A')}\n\n"
                f"## Proposed Fix Summary\n{proposed_fix_summary}\n\n"
                f"## Sandbox Failure Logs\n```\n{state['sandbox_execution_logs']}\n```"
            )
        )

        return {
            "proposed_patch": proposed_fix_summary,
            "github_pr_url": pr_url,
            "messages": new_messages
        }
