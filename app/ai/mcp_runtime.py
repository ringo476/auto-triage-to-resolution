"""
Shared MCP sandbox session + tool-calling loop, used by both the sandbox
executor (repro_node) and the code-fix agent (code_fix_node) so the two
don't duplicate the same docker/session/tool-loop bookkeeping.
"""
from contextlib import asynccontextmanager

from langchain_core.messages import BaseMessage, ToolMessage
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


@asynccontextmanager
async def sandbox_session(target_repo_path: str):
    """Opens a throwaway, network-isolated docker container running the MCP
    sandbox server, with the target repo mounted read/write at /app/workspace.
    Yields the langchain-adapted tool list for the duration of the session.
    """
    server_params = StdioServerParameters(
        command="docker",
        args=["run", "-i", "--rm", "--network=none", f"-v={target_repo_path}:/app/workspace", "mcp-sandbox-image"]
    )
    async with stdio_client(server_params) as (read_stream, write_stream), \
            ClientSession(read_stream, write_stream) as session:
        await session.initialize()
        tools = await load_mcp_tools(session)
        yield tools


async def run_tool_loop(bind_llm, tools, messages: list[BaseMessage], max_turns: int = 5) -> list[BaseMessage]:
    """Drives an LLM-with-tools conversation until it stops requesting tool
    calls (or max_turns is hit). Mutates `messages` in place and also returns
    just the new messages generated during this call, for callers that need
    to report only what happened in this step.
    """
    new_messages: list[BaseMessage] = []

    for _ in range(max_turns):
        ai_response = await bind_llm.ainvoke(messages)
        messages.append(ai_response)
        new_messages.append(ai_response)

        if not ai_response.tool_calls:
            break

        for tool_call in ai_response.tool_calls:
            selected_tool = next((t for t in tools if t.name == tool_call["name"]), None)

            if selected_tool is None:
                tool_output = f"Tool Execution Error: unknown tool '{tool_call['name']}'"
            else:
                try:
                    tool_output = await selected_tool.ainvoke(tool_call["args"])
                except Exception as e:  # noqa: BLE001
                    tool_output = f"Tool Execution Error: {e!s}"

            tool_message = ToolMessage(content=str(tool_output), tool_call_id=tool_call["id"])
            messages.append(tool_message)
            new_messages.append(tool_message)

    return new_messages
