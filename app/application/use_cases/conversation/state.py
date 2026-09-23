from typing import Optional, TypedDict


class ConversationState(TypedDict, total=False):
    # Input, set once when the graph is invoked.
    tenant_id: str
    session_id: str
    channel: str
    user_question: str
    visitor_language: Optional[str]

    # Set by load_history_node.
    history: list[dict]

    # Set by resolve_language_node.
    reply_language: str

    # Set by orchestrator_node.
    route: str  # "retrieval" | "agenda" | "direct" | "flow"

    # Used by retrieval_agent's tool-calling loop.
    translated_query: str
    messages: list[dict]
    tool_call_count: int

    # Set by pectus_poland_guard_node.
    pectus_poland_guard_triggered: bool

    # Set by minor_patient_guard_node.
    minor_patient_guard_triggered: bool

    # Output.
    final_answer: str
