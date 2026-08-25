from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from app.ai.agents.nodes import load_skill
from app.ai.mcp_runtime import run_tool_loop, sandbox_session
from app.ai.state import AgentState
from app.config import settings
from app.integrations.github import commit_and_push_changes, create_pull_request


async def code_fix_node(state: AgentState) -> dict:
    """
    Executes when triage_action == 'AUTO_PR'. Connects to MCP server tools
    (read_file, search_codebase, run_sandbox_script) to inspect codebase files,
    generate a patch, verify the fix in the sandbox, then commits, pushes, and
    opens a GitHub PR against the target repo.
    """
    async with sandbox_session(state["target_repo_path"]) as tools:
        llm = ChatOllama(model=settings.OLLAMA_MODEL, temperature=0)
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

        proposed_fix_summary = new_messages[-1].content

        branch_name = f"sentinelops/fix-{state['ticket_id']}"
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
