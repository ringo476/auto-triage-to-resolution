

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_openai import ChatOpenAI
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.ai.agents.nodes import load_skill
from app.ai.state import AgentState
from app.integrations.github import create_pull_request


async def code_fix_node(state: AgentState) -> dict:
    """
    Executes when triage_action == 'AUTO_PR'. Connects to MCP server tools
    (read_file, search_codebase, run_sandbox_script) to inspect codebase files,
    generate a patch, verify the fix in the sandbox, and open a GitHub PR.
    """
    server_params = StdioServerParameters(
        command="python3",
        args=["-m", "app.mcp_server.server"]
    )
    async with stdio_client(server_params) as (read_stream, write_stream), \
            ClientSession(read_stream, write_stream) as session:
        await session.initialize()
        
        langchain_tools = await load_mcp_tools(session)
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        bind_llm = llm.bind_tools(langchain_tools)
        
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
        
        max_turns = 5
        for turn in range(max_turns):
            ai_response = await bind_llm.ainvoke(new_messages)
            new_messages.append(ai_response)
            
            if not ai_response.tool_calls:
                break
            
            for tool_call in ai_response.tool_calls:
                selected_tool = next(t for t in langchain_tools if t.name == tool_call["name"])
                
                try:
                    tool_output = await selected_tool.ainvoke(tool_call["args"])
                except Exception as e:
                    tool_output = f"Tool Execution Error: {e!s}"
                
                new_messages.append(ToolMessage(
                    content=str(tool_output),
                    tool_call_id=tool_call["id"]
                ))
        
        proposed_fix_summary = new_messages[-1].content
        
        # Trigger GitHub API integration to open the PR automatically
        pr_url = await create_pull_request(
            title=f"fix: Automated resolution for issue - {state['raw_issue_description'][:50]}",
            body=(
                f"## Root Cause Analysis\n{state.get('root_cause_analysis', 'N/A')}\n\n"
                f"## Proposed Fix Summary\n{proposed_fix_summary}\n\n"
                f"## Sandbox Failure Logs\n```\n{state['sandbox_execution_logs']}\n```"
            )
        )
        
        return {
            "proposed_patch": proposed_fix_summary,
            "pull_request_url": pr_url,
            "messages":new_messages
            }