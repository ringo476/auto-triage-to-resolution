from pathlib import Path
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_ollama import ChatOllama
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from pydantic import BaseModel, Field, ValidationError

from app.ai.prompts import SANDBOX_HUMAN_TEMPLATE, TRIAGE_HUMAN_TEMPLATE
from app.ai.state import AgentState
from app.database import search_knowledge_base


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

def rag_node(state: AgentState) -> dict:
    """Retrieves relevant API schemas, docs, or past tickets from pgvector."""
    doc = state["raw_issue_description"]
    retrieved_docs = search_knowledge_base(doc)
    return {"rag_context": retrieved_docs}


async def repro_node(state: AgentState) -> dict:
    server_params = StdioServerParameters(
        command="docker",
        args=["run", "-i", "--rm", "--network=none", f"-v={state['target_repo_path']}:/app/workspace", "mcp-sandbox-image"]
    )
    async with stdio_client(server_params) as (read_stream, write_stream), \
            ClientSession(read_stream, write_stream) as session:
        await session.initialize()
        
        langchain_tools = await load_mcp_tools(session)
        llm = ChatOllama(model="qwen2.5-coder:7b", temperature=0)
        bind_llm = llm.bind_tools(langchain_tools)
        
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
        
        # 2. Create a list to track ONLY the new messages generated in this node
        new_messages_to_return = []
        
        max_turns = 5
        for turn in range(max_turns):
            # LLM reads the full history and makes a decision
            ai_response = await bind_llm.ainvoke(current_messages)
            
            # Append to our running execution lists
            current_messages.append(ai_response)
            new_messages_to_return.append(ai_response)
            
            # The Stopping Condition: If no tools are called, break the loop.
            if not ai_response.tool_calls:
                break
            
            # Execute the tools the LLM requested
            for tool_call in ai_response.tool_calls:
                selected_tool = next(t for t in langchain_tools if t.name == tool_call["name"])
                
                try:
                    tool_output = await selected_tool.ainvoke(tool_call["args"])
                except Exception as e:  # noqa: BLE001
                    tool_output = f"Tool Execution Error: {e!s}"
                
                tool_message = ToolMessage(
                    content=str(tool_output),
                    tool_call_id=tool_call["id"]
                )
                
                # Append the tool result so the LLM sees it on the next turn
                current_messages.append(tool_message)
                new_messages_to_return.append(tool_message)
        
        # Extract just the raw tool strings for the triage node to read easily
        execution_logs = "\n".join([m.content for m in new_messages_to_return if isinstance(m, ToolMessage)])
        
        # 3. PROPER PATTERN: Return BOTH the logs and the new message history
        return {
            "sandbox_execution_logs": execution_logs or "No logs produced.",
            "messages": new_messages_to_return  # LangGraph will now auto-append these globally!
        }


async def triage_node(state: AgentState) -> dict:
    """
    Evaluates execution logs and RAG context against triage_skill.md SOP
    to output a structured routing decision (USER_ERROR, AUTO_PR, or JIRA_TICKET).
    """
    llm = ChatOllama(model="qwen2.5-coder:7b", temperature=0)
    triage_skill_text = load_skill("triage_skill.md")
    
    triage_prompt = ChatPromptTemplate.from_messages([
        ("system", triage_skill_text),
        ("human", TRIAGE_HUMAN_TEMPLATE)
    ])
    
    structured_llm = llm.with_structured_output(TriageDecision)
    triage_chain = triage_prompt | structured_llm
    
    response = None
    last_error = None
    for _ in range(3):
        try:
            response = await triage_chain.ainvoke({
                "raw_issue_description": state["raw_issue_description"],
                "rag_context": state["rag_context"],
                "sandbox_execution_logs": state["sandbox_execution_logs"]
            })
            break
        except ValidationError as e:
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