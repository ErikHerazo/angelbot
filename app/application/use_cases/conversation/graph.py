from langgraph.graph import END, StateGraph

from app.application.ports.advisor_available_reply_config_repository_port import (
    AdvisorAvailableReplyConfigRepositoryPort,
)
from app.application.ports.agenda_reply_config_repository_port import AgendaReplyConfigRepositoryPort
from app.application.ports.conversation_history_port import ConversationHistoryPort
from app.application.ports.flow_confirmation_reply_config_repository_port import (
    FlowConfirmationReplyConfigRepositoryPort,
)
from app.application.ports.llm_port import LLMPort
from app.application.ports.minor_patient_deferral_config_repository_port import (
    MinorPatientDeferralConfigRepositoryPort,
)
from app.application.ports.pectus_poland_disambiguation_config_repository_port import (
    PectusPolandDisambiguationConfigRepositoryPort,
)
from app.application.ports.prompt_config_repository_port import PromptConfigRepositoryPort
from app.application.ports.reply_language_enforcer_port import ReplyLanguageEnforcerPort
from app.application.ports.reply_language_resolver_port import ReplyLanguageResolverPort
from app.application.ports.retrieval_tools_provider_port import RetrievalToolsProviderPort
from app.application.ports.translation_port import TranslationPort
from app.application.use_cases.check_business_availability import CheckBusinessAvailability
from app.application.use_cases.conversation.agents.agenda_agent import make_agenda_agent_node
from app.application.use_cases.conversation.agents.direct_agent import make_direct_agent_node
from app.application.use_cases.conversation.agents.flow_agent import make_flow_agent_node
from app.application.use_cases.conversation.agents.retrieval_agent import (
    make_execute_tools_node,
    make_generate_final_node,
    make_generate_with_tools_node,
    make_translate_query_node,
    route_after_generate,
    use_existing_answer_node,
)
from app.application.use_cases.conversation.nodes import (
    make_enforce_language_node,
    make_load_history_node,
    make_resolve_language_node,
)
from app.application.use_cases.conversation.minor_patient_guard import (
    make_minor_patient_guard_node,
    route_after_minor_patient_guard,
)
from app.application.use_cases.conversation.orchestrator import make_orchestrator_node, route_after_orchestrator
from app.application.use_cases.conversation.pectus_poland_guard import (
    make_pectus_poland_guard_node,
    route_after_pectus_poland_guard,
)
from app.application.use_cases.conversation.state import ConversationState


def build_conversation_graph(
    *,
    llm: LLMPort,
    conversation_history: ConversationHistoryPort,
    reply_language_resolver: ReplyLanguageResolverPort,
    reply_language_enforcer: ReplyLanguageEnforcerPort,
    translation: TranslationPort,
    prompt_config: PromptConfigRepositoryPort,
    retrieval_tools: RetrievalToolsProviderPort,
    check_business_availability: CheckBusinessAvailability,
    advisor_available_reply_config: AdvisorAvailableReplyConfigRepositoryPort,
    agenda_reply_config: AgendaReplyConfigRepositoryPort,
    flow_confirmation_reply_config: FlowConfirmationReplyConfigRepositoryPort,
    pectus_poland_disambiguation_config: PectusPolandDisambiguationConfigRepositoryPort,
    minor_patient_deferral_config: MinorPatientDeferralConfigRepositoryPort,
    max_history: int,
):
    """Builds the orchestrator + 4-branch conversation StateGraph (retrieval /
    agenda / direct-to-advisor / flow), matching the shape of Erik's Confluence
    architecture diagram. Low-level StateGraph API deliberately, not a
    prebuilt agent -- see CLAUDE.md's LangGraph migration notes for why."""
    graph = StateGraph(ConversationState)

    graph.add_node("load_history", make_load_history_node(conversation_history, max_history=max_history))
    graph.add_node("resolve_language", make_resolve_language_node(reply_language_resolver))
    graph.add_node(
        "orchestrator",
        make_orchestrator_node(llm=llm, check_business_availability=check_business_availability),
    )
    graph.add_node("translate_query", make_translate_query_node(translation))
    graph.add_node(
        "minor_patient_guard", make_minor_patient_guard_node(minor_patient_deferral_config)
    )
    graph.add_node(
        "pectus_poland_guard", make_pectus_poland_guard_node(pectus_poland_disambiguation_config)
    )
    graph.add_node(
        "generate_with_tools",
        make_generate_with_tools_node(llm=llm, prompt_config=prompt_config, retrieval_tools=retrieval_tools),
    )
    graph.add_node("execute_tools", make_execute_tools_node(retrieval_tools))
    graph.add_node("generate_final", make_generate_final_node(llm=llm, retrieval_tools=retrieval_tools))
    graph.add_node("use_existing_answer", use_existing_answer_node)
    graph.add_node("agenda_agent", make_agenda_agent_node(agenda_reply_config))
    graph.add_node("direct_agent", make_direct_agent_node(advisor_available_reply_config))
    graph.add_node(
        "flow_agent", make_flow_agent_node(llm=llm, flow_confirmation_reply_config=flow_confirmation_reply_config)
    )
    graph.add_node("enforce_language", make_enforce_language_node(reply_language_enforcer))

    graph.set_entry_point("load_history")
    graph.add_edge("load_history", "resolve_language")
    graph.add_edge("resolve_language", "orchestrator")
    graph.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        {"retrieval": "translate_query", "agenda": "agenda_agent", "direct": "direct_agent", "flow": "flow_agent"},
    )
    graph.add_edge("translate_query", "minor_patient_guard")
    graph.add_conditional_edges(
        "minor_patient_guard",
        route_after_minor_patient_guard,
        {"enforce_language": "enforce_language", "pectus_poland_guard": "pectus_poland_guard"},
    )
    graph.add_conditional_edges(
        "pectus_poland_guard",
        route_after_pectus_poland_guard,
        {"enforce_language": "enforce_language", "generate_with_tools": "generate_with_tools"},
    )
    graph.add_conditional_edges(
        "generate_with_tools",
        route_after_generate,
        {
            "execute_tools": "execute_tools",
            "generate_final": "generate_final",
            "use_existing_answer": "use_existing_answer",
        },
    )
    graph.add_edge("execute_tools", "generate_with_tools")
    graph.add_edge("generate_final", "enforce_language")
    graph.add_edge("use_existing_answer", "enforce_language")
    graph.add_edge("agenda_agent", "enforce_language")
    graph.add_edge("direct_agent", "enforce_language")
    graph.add_edge("flow_agent", "enforce_language")
    graph.add_edge("enforce_language", END)

    return graph.compile()
