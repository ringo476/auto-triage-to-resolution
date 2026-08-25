from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.ai.agents.code_fix import code_fix_node
from app.ai.agents.nodes import jira_node, rag_node, repro_node, slack_node, triage_node
from app.ai.state import AgentState

workflow = StateGraph(AgentState)


def route_triage(state: AgentState) -> str:
    """Reads the decision from the triage_node and directs traffic."""
    action = state.get("triage_action")

    if action == "AUTO_PR":
        return "fix"
    elif action == "JIRA_TICKET":
        return "jira"
    elif action == "USER_ERROR":
        return "notify_user"

    return END  # Safety fallback


workflow.add_node("researcher", rag_node)
workflow.add_node("reproduce", repro_node)
workflow.add_node("decision", triage_node)
workflow.add_node("fix", code_fix_node)
workflow.add_node("jira", jira_node)
workflow.add_node("notify_user", slack_node)

workflow.add_edge(START, "researcher")
workflow.add_edge("researcher", "reproduce")
workflow.add_edge("reproduce", "decision")
workflow.add_conditional_edges("decision", route_triage)
workflow.add_edge("fix", END)
workflow.add_edge("jira", END)
workflow.add_edge("notify_user", END)

memory = MemorySaver()
app_graph = workflow.compile(checkpointer=memory)
