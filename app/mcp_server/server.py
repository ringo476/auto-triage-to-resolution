from mcp.server.fastmcp import FastMCP

from app.mcp_server.tools import execute_mock_request, read_server_logs

# 1. Initialize the FastMCP Server
# This creates the engine that will listen for tool calls from the LangGraph client.
mcp=FastMCP("TriageSandBox")

# 2. Register the Tools
# We pull the pure Python functions from tools.py and register them.
# FastMCP automatically reads their docstrings and type hints to generate 
# the JSON schema that OpenAI needs.
mcp.add_tool(execute_mock_request)
mcp.add_tool(read_server_logs)
# 3. The Execution Runner
if __name__=="__main__":
    # Start the server using stdio transport (Standard Input/Output).
    # This is the most reliable method for local agent-to-server IPC communication.
    mcp.run()