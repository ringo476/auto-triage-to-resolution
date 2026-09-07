# SentinelOps AI

SentinelOps is an autonomous bug-triage and fix agent. It ingests a bug report (via API or Slack), retrieves relevant context from a knowledge base, reproduces the issue in a sandboxed container, and routes to one of three outcomes: open an automated fix PR on GitHub, file a Jira ticket, or reply to the reporter that it looks like user error.

## Architecture

A [LangGraph](https://github.com/langchain-ai/langgraph) state machine drives the pipeline:

1. **researcher** (`rag_node`) — embeds the bug report and retrieves similar past tickets/docs from a pgvector knowledge base.
2. **reproduce** (`repro_node`) — spins up a network-isolated Docker sandbox with the target repo mounted read/write, and lets an LLM (via MCP tools) attempt to reproduce the bug.
3. **decision** (`triage_node`) — an LLM evaluates the reproduction logs and RAG context against `triage_skill.md` and outputs a structured routing decision: `AUTO_PR`, `JIRA_TICKET`, or `USER_ERROR`.
4. Routing:
   - `AUTO_PR` → **fix** (`code_fix_node`): patches the code in the sandbox, commits, pushes, and opens a GitHub PR.
   - `JIRA_TICKET` → **jira** (`jira_node`): files a Jira ticket with the analysis.
   - `USER_ERROR` → **notify_user** (`slack_node`): replies in the originating Slack channel.

All sandbox code execution happens inside a throwaway `--network=none` Docker container via [MCP](https://modelcontextprotocol.io) tools (`app/mcp_server/tools.py`) — the LLM never touches the host directly.

## Setup

1. Copy `.env.example` to `.env` and fill in the values (GitHub is mandatory; Slack/Jira are optional and only needed for those routing paths).
2. Start Postgres+pgvector and the API:
   ```bash
   docker compose up
   ```
   Or run locally without Docker Compose (requires a running Postgres+pgvector instance and [Ollama](https://ollama.com) pulled with the models in `.env`):
   ```bash
   pip install -e ".[test]"
   uvicorn app.main:app --reload
   ```
3. Build the sandbox image the agent uses to reproduce/fix bugs:
   ```bash
   docker build -f Dockerfile.mcp -t mcp-sandbox-image .
   ```

## Triggering a run

```bash
curl -X POST http://localhost:8000/api/webhook/bug_report \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: $WEBHOOK_SECRET" \
  -d '{
    "ticket_id": "BUG-101",
    "target_repo_path": "/absolute/path/to/repo",
    "raw_issue_description": "Users get a 500 error when submitting an empty form.",
    "reporter_email": "someone@example.com"
  }'
```

`/api/webhook/bug_report` requires the `X-Webhook-Secret` header to match `WEBHOOK_SECRET` in `.env` — this endpoint mounts `target_repo_path` into a sandbox and lets an LLM read/write files there, so it must not be left open. `/api/webhook/slack` verifies Slack's request signature instead (`SLACK_SIGNING_SECRET`).

## Tests

```bash
pip install -e ".[test]"
pytest
```

Tests cover the graph's routing logic, MCP sandbox tool safety (path traversal, patch application), and webhook signature verification — they don't require Docker, Postgres, or Ollama to be running.

## Current scope / known limitations

- The Jira and Slack integrations are fully wired into the graph but need real credentials in `.env` to do anything (`JIRA_*`, `SLACK_*`).
- Running the API itself inside `docker-compose` works for the web server, but `repro_node`/`code_fix_node` shell out to `docker run` for the sandbox — if you containerize the API service, it needs access to the host's Docker socket (not wired up in `docker-compose.yaml` by default, since mounting `/var/run/docker.sock` grants the container host-level Docker control and is a deliberate tradeoff, not a default-on convenience).
- `is_reproducible` / `reproduction_command` are declared in `AgentState` for future use but no node currently populates them.
