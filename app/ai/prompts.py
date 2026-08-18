"""
Static system instructions and XML data templates for LangGraph agents.
These constants enforce strict privilege separation between execution rules and user data.
"""

# ==========================================
# 1. THE CONTEXT RESEARCHER AGENT
# ==========================================

CONTEXT_HUMAN_TEMPLATE = """<bug_report>
{raw_issue_description}
</bug_report>"""


# ==========================================
# 2. THE SANDBOX EXECUTOR AGENT
# ==========================================

SANDBOX_HUMAN_TEMPLATE = """<bug_report>
{raw_issue_description}
</bug_report>

<api_documentation>
{rag_context}
</api_documentation>"""


# ==========================================
# 3. THE TRIAGE SUPERVISOR AGENT
# ==========================================

TRIAGE_HUMAN_TEMPLATE = """<bug_report>
{raw_issue_description}
</bug_report>

<api_documentation>
{rag_context}
</api_documentation>

<execution_logs>
{sandbox_execution_logs}
</execution_logs>"""