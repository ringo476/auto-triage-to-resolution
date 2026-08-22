from app.mcp_server.tools import mcp

if __name__ == "__main__":
    # Start the server using stdio transport (Standard Input/Output).
    # This is the most reliable method for local agent-to-server IPC communication.
    mcp.run()