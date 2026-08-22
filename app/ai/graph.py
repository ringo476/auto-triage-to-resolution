from langgraph.graph import END, START, StateGraph

from app.ai.agents.code_fix import code_fix_node
from app.ai.agents.nodes import rag_node, repro_node, triage_node
from app.ai.state import AgentState

workflow=StateGraph(AgentState)

def route_triage(state: AgentState) -> str:
    """Reads the decision from the triage_node and directs traffic."""
    action = state.get("triage_action")
    
    if action == "AUTO_PR":
        return "fix"               # Send to code_fix_node
    elif action == "JIRA_TICKET":
        return END                 # Or send to a "jira_node" if you build one
    elif action == "USER_ERROR":
        return END                 # Or send to a "slack_node" if you build one
    
    return END # Safety fallback

workflow.add_node(rag_node,"researcher")
workflow.add_node(repro_node,"reproduce")
workflow.add_node(triage_node,"decision")
workflow.add_node(code_fix_node,"fix")
workflow.add_edge(START,"researcher")
workflow.add_edge("researcher","reproduce")
workflow.add_edge("reproduce","decision")
workflow.add_conditional_edges("decision",route_triage)
workflow.add_edge("fix",END)

from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()
app_graph=workflow.compile(checkpointer=memory)