import asyncio
import os
from typing import Awaitable, Callable, Dict, Optional, Tuple, TypeVar

from app.adapters.outbound.azure_openai.azure_openai_conversation_engine_adapter import (
    AzureOpenAIConversationEngineAdapter,
)
from app.adapters.outbound.claude_foundry.claude_foundry_conversation_engine_adapter import (
    ClaudeFoundryConversationEngineAdapter,
)
from app.adapters.outbound.redis.redis_conversation_history_adapter import (
    RedisConversationHistoryAdapter,
)
from app.adapters.outbound.reply_compression.llm_reply_compression_adapter import (
    LLMReplyCompressionAdapter,
)
from app.adapters.outbound.secrets.env_file_secrets_adapter import EnvFileSecretsAdapter
from app.adapters.outbound.tenant_config.filesystem_tenant_repository import (
    FilesystemTenantRepository,
)
from app.adapters.outbound.tenant_config.filesystem_zoho_config_repository import (
    FilesystemZohoConfigRepository,
)
from app.adapters.outbound.tenant_config.filesystem_business_hours_config_repository import (
    FilesystemBusinessHoursConfigRepository,
)
from app.adapters.outbound.clock.system_clock_adapter import SystemClockAdapter
from app.adapters.outbound.tenant_config.filesystem_price_catalog_config_repository import (
    FilesystemPriceCatalogConfigRepository,
)
from app.adapters.outbound.azure_search.azure_search_price_catalog_adapter import (
    AzureSearchPriceCatalogAdapter,
)
from app.adapters.outbound.tenant_config.filesystem_greeting_config_repository import (
    FilesystemGreetingConfigRepository,
)
from app.adapters.outbound.tenant_config.filesystem_continue_message_config_repository import (
    FilesystemContinueMessageConfigRepository,
)
from app.adapters.outbound.language.reply_language_resolver_adapter import (
    ReplyLanguageResolverAdapter,
)
from app.adapters.outbound.language.azure_translator_adapter import AzureTranslatorAdapter
from app.adapters.outbound.tenant_config.filesystem_file_upload_ack_config_repository import (
    FilesystemFileUploadAckConfigRepository,
)
from app.adapters.outbound.zoho.zoho_chat_platform_adapter import ZohoChatPlatformAdapter
from app.adapters.outbound.azure_blob.azure_blob_storage_adapter import AzureBlobStorageAdapter
from app.adapters.outbound.celery.celery_search_indexer_adapter import CelerySearchIndexerAdapter
from app.adapters.outbound.azure_search.azure_search_indexer_control_adapter import (
    AzureSearchIndexerControlAdapter,
)
from app.adapters.outbound.tenant_config.filesystem_search_indexer_config_repository import (
    FilesystemSearchIndexerConfigRepository,
)
from app.adapters.outbound.tenant_config.filesystem_prompt_config_repository import (
    FilesystemPromptConfigRepository,
)
from app.adapters.outbound.azure_openai.azure_openai_llm_adapter import AzureOpenAILLMAdapter
from app.adapters.outbound.claude_foundry.claude_foundry_llm_adapter import ClaudeFoundryLLMAdapter
from app.adapters.outbound.tenant_config.filesystem_claude_llm_config_repository import (
    FilesystemClaudeLLMConfigRepository,
)
from app.adapters.outbound.langgraph.langgraph_conversation_engine_adapter import (
    LangGraphConversationEngineAdapter,
)
from app.adapters.outbound.language.reply_language_enforcer_adapter import ReplyLanguageEnforcerAdapter
from app.adapters.outbound.mcp.mcp_http_client import McpHttpClient
from app.adapters.outbound.mcp.mcp_retrieval_tools_adapter import McpRetrievalToolsAdapter
from app.adapters.outbound.mcp.mcp_zoho_chat_platform_adapter import McpZohoChatPlatformAdapter
from app.adapters.outbound.tenant_config.filesystem_advisor_available_reply_config_repository import (
    FilesystemAdvisorAvailableReplyConfigRepository,
)
from app.adapters.outbound.tenant_config.filesystem_agenda_reply_config_repository import (
    FilesystemAgendaReplyConfigRepository,
)
from app.adapters.outbound.tenant_config.filesystem_flow_confirmation_reply_config_repository import (
    FilesystemFlowConfirmationReplyConfigRepository,
)
from app.adapters.outbound.tenant_config.filesystem_llm_config_repository import (
    FilesystemLLMConfigRepository,
)
from app.application.ports.chat_platform_port import ChatPlatformPort
from app.application.ports.conversation_engine_port import ConversationEnginePort
from app.application.ports.prompt_config_repository_port import PromptConfigRepositoryPort
from app.application.use_cases.conversation.graph import build_conversation_graph
from openai import AsyncAzureOpenAI
from app.application.use_cases.acknowledge_file_upload import AcknowledgeFileUpload
from app.application.use_cases.check_business_availability import CheckBusinessAvailability
from app.application.use_cases.handle_greeting_trigger import HandleGreetingTrigger
from app.application.use_cases.index_knowledge_document import IndexKnowledgeDocument
from app.application.use_cases.intercept_continuation_token import InterceptContinuationToken
from app.application.use_cases.lookup_procedure_price import LookupProcedurePrice
from app.application.use_cases.process_incoming_message import ProcessIncomingMessage
from app.application.use_cases.process_lead_submission import ProcessLeadSubmission
from app.application.use_cases.upload_knowledge_document import UploadKnowledgeDocument
from app.config import settings
from app.core.logging.structured_logger import get_logger

log = get_logger(__name__)

CHANNEL_CHARACTER_LIMITS = {"instagram": settings.INSTAGRAM_CHARACTER_LIMIT}
STATELESS_CHANNELS = {"flow"}
MAX_HISTORY = 6

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config", "tenants")

# Shared, cheap, tenant-agnostic-at-construction -- built once, reused for
# every tenant/turn (no I/O happens building it).
_check_business_availability = CheckBusinessAvailability(
    tenant_repository=FilesystemTenantRepository(config_dir=CONFIG_DIR),
    business_hours_config=FilesystemBusinessHoursConfigRepository(config_dir=CONFIG_DIR),
    clock=SystemClockAdapter(),
)
_prompt_config = FilesystemPromptConfigRepository(config_dir=CONFIG_DIR)
_llm_config_repository = FilesystemLLMConfigRepository(config_dir=CONFIG_DIR)
_claude_llm_config_repository = FilesystemClaudeLLMConfigRepository(config_dir=CONFIG_DIR)
_advisor_available_reply_config = FilesystemAdvisorAvailableReplyConfigRepository(config_dir=CONFIG_DIR)
_agenda_reply_config = FilesystemAgendaReplyConfigRepository(config_dir=CONFIG_DIR)
_flow_confirmation_reply_config = FilesystemFlowConfirmationReplyConfigRepository(config_dir=CONFIG_DIR)

# clinyq-mcp-* server locations -- shared infra, not tenant config (tenant_id
# is a per-call argument to each tool, not a URL difference), read from
# app/config/config.yaml's "mcp_servers" block. Both repos default to
# container port 8931 internally; if running more than one locally at once,
# remap host ports (see each repo's docker-compose.yml).
MCP_AZURE_SEARCH_URL = settings.MCP_AZURE_SEARCH_URL
MCP_ZOHO_URL = settings.MCP_ZOHO_URL

T = TypeVar("T")

_tenant_scoped_cache: Dict[Tuple[str, str], object] = {}
_tenant_scoped_cache_lock = asyncio.Lock()


async def _get_or_build_for_tenant(cache_key: str, tenant_id: str, builder: Callable[[], Awaitable[T]]) -> T:
    """Per-(cache_key, tenant_id) memoization for adapters whose construction
    does real I/O (secret/config fetches) -- without this, anything called
    once per conversation turn (like the RAG engine's tool wiring) would
    redo that I/O on every single message instead of once per tenant."""
    key = (cache_key, tenant_id)
    if key not in _tenant_scoped_cache:
        async with _tenant_scoped_cache_lock:
            if key not in _tenant_scoped_cache:
                with log.operation(cache_key=cache_key, tenant_id=tenant_id):
                    _tenant_scoped_cache[key] = await builder()
    else:
        log.debug("Tenant-scoped cache hit", cache_key=cache_key, tenant_id=tenant_id)
    return _tenant_scoped_cache[key]


def _build_conversation_history() -> RedisConversationHistoryAdapter:
    if os.getenv("APP_ENV", "local").lower() == "prod":
        host = os.getenv("REDIS_HOST_PROD")
        port = os.getenv("REDIS_PORT_PROD")
        password = os.getenv("REDIS_PASSWORD_PROD")
        redis_url = f"rediss://:{password}@{host}:{port}"
    else:
        redis_url = os.getenv("REDIS_URL_LOCAL", "redis://127.0.0.1:6379")
    return RedisConversationHistoryAdapter(redis_url=redis_url)


async def _build_zoho_chat_platform(tenant_id: str) -> ZohoChatPlatformAdapter:
    secrets = EnvFileSecretsAdapter()
    zoho_config_repository = FilesystemZohoConfigRepository(config_dir=CONFIG_DIR)

    access_token = await secrets.get_secret(f"zoho-access-token-{tenant_id}")
    zoho_config = await zoho_config_repository.get_config(tenant_id)

    return ZohoChatPlatformAdapter(
        access_token=access_token,
        server_uri=zoho_config.server_uri,
        screenname=zoho_config.screenname,
    )


async def get_cached_chat_platform(tenant_id: str) -> ZohoChatPlatformAdapter:
    return await _get_or_build_for_tenant(
        "chat_platform", tenant_id, lambda: _build_zoho_chat_platform(tenant_id)
    )


async def get_cached_lookup_procedure_price(tenant_id: str) -> LookupProcedurePrice:
    return await _get_or_build_for_tenant(
        "lookup_procedure_price", tenant_id, lambda: build_lookup_procedure_price(tenant_id)
    )


def build_claude_conversation_engine(
    conversation_history: "RedisConversationHistoryAdapter",
    *,
    check_business_availability: Optional[CheckBusinessAvailability] = None,
    get_lookup_procedure_price: Optional[Callable[[str], Awaitable[LookupProcedurePrice]]] = None,
) -> ClaudeFoundryConversationEngineAdapter:
    """Builds the Claude-via-Microsoft-Foundry alternative to
    AzureOpenAIConversationEngineAdapter -- see that adapter's docstring.
    Reads the same infra-level env vars as the Azure OpenAI client
    (client.py) and the main-index lookup (query_service.py) rather than
    per-tenant config files, matching existing precedent: none of those are
    tenant-scoped today either, in legacy or hexagonal code.

    `check_business_availability`/`get_lookup_procedure_price` wire the same
    2 tools as AzureOpenAIConversationEngineAdapter's `include_flag_tools=False`
    mode -- see ClaudeFoundryConversationEngineAdapter's docstring for why
    only these 2 (not the 3 flag tools) are connected on either engine for
    this comparison."""
    return ClaudeFoundryConversationEngineAdapter(
        conversation_history=conversation_history,
        prompt_config=_prompt_config,
        foundry_api_key=os.getenv("AZURE_FOUNDRY_CLAUDE_API_KEY"),
        foundry_endpoint=os.getenv(
            "AZURE_FOUNDRY_CLAUDE_ENDPOINT",
            "https://foundry-test-clinyq-resource.openai.azure.com/anthropic",
        ),
        deployment=os.getenv("AZURE_FOUNDRY_CLAUDE_DEPLOYMENT", "claude-sonnet-5-clinyq"),
        search_endpoint=os.getenv("AZURE_AI_SEARCH_ENDPOINT"),
        search_api_key=os.getenv("AZURE_AI_SEARCH_API_KEY"),
        main_search_index=os.getenv("AZURE_AI_SEARCH_INDEX"),
        price_search_index=os.getenv("AZURE_AI_SEARCH_PRICE_LIST_INDEX"),
        semantic_configuration=os.getenv("SEMANTIC_CONFIGURATION"),
        check_business_availability=check_business_availability or _check_business_availability,
        get_lookup_procedure_price=get_lookup_procedure_price or get_cached_lookup_procedure_price,
    )


async def _build_llm(tenant_id: str) -> AzureOpenAILLMAdapter:
    secrets = EnvFileSecretsAdapter()
    api_key = await secrets.get_secret(f"azure-openai-api-key-{tenant_id}")
    llm_config = await _llm_config_repository.get_config(tenant_id)

    client_kwargs = dict(azure_endpoint=llm_config.endpoint, api_key=api_key, api_version=llm_config.api_version)
    return AzureOpenAILLMAdapter(
        primary_client=AsyncAzureOpenAI(**client_kwargs),
        secondary_client=AsyncAzureOpenAI(**client_kwargs),
        deployment_primary=llm_config.deployment_primary,
        deployment_secondary=llm_config.deployment_secondary,
        temperature=llm_config.temperature,
        max_tokens=llm_config.max_tokens,
    )


async def _build_claude_llm(tenant_id: str) -> ClaudeFoundryLLMAdapter:
    secrets = EnvFileSecretsAdapter()
    api_key = await secrets.get_secret(f"azure-foundry-claude-api-key-{tenant_id}")
    claude_config = await _claude_llm_config_repository.get_config(tenant_id)

    return ClaudeFoundryLLMAdapter(
        api_key=api_key,
        endpoint=claude_config.endpoint,
        deployment=claude_config.deployment,
        max_tokens=claude_config.max_tokens,
    )


async def _build_conversation_graph_for_tenant(tenant_id: str):
    # Claude is the completions provider for this agent (Erik's call,
    # 2026-09-16) -- _build_llm/AzureOpenAILLMAdapter and the "llm" config
    # block are kept, not removed, since other engines in this codebase
    # (the legacy run_conversation_with_rag pipeline, and the GPT-4o side of
    # feature/switch-to-claude's comparison) still use Azure OpenAI directly.
    llm = await _build_claude_llm(tenant_id)
    conversation_history = _build_conversation_history()
    retrieval_tools = McpRetrievalToolsAdapter(
        mcp_client=McpHttpClient(base_url=MCP_AZURE_SEARCH_URL), tenant_id=tenant_id
    )

    return build_conversation_graph(
        llm=llm,
        conversation_history=conversation_history,
        reply_language_resolver=ReplyLanguageResolverAdapter(conversation_history=conversation_history),
        reply_language_enforcer=ReplyLanguageEnforcerAdapter(),
        translation=AzureTranslatorAdapter(),
        prompt_config=_prompt_config,
        retrieval_tools=retrieval_tools,
        check_business_availability=_check_business_availability,
        advisor_available_reply_config=_advisor_available_reply_config,
        agenda_reply_config=_agenda_reply_config,
        flow_confirmation_reply_config=_flow_confirmation_reply_config,
        max_history=MAX_HISTORY,
    )


async def get_cached_conversation_graph(tenant_id: str):
    return await _get_or_build_for_tenant(
        "langgraph_conversation_graph", tenant_id, lambda: _build_conversation_graph_for_tenant(tenant_id)
    )


def build_langgraph_conversation_engine(
    *, get_graph: Optional[Callable[[str], Awaitable[object]]] = None
) -> LangGraphConversationEngineAdapter:
    """The new agent: orchestrator + 4-branch StateGraph, completions via
    Claude (Sonnet 5, Microsoft Foundry -- see _build_claude_llm), tools
    wired via MCP to clinyq-mcp-azure-search, in place of
    run_conversation_with_rag's Azure 'on your data' + azure_tools.py tool
    loop. Not the default ConversationEnginePort yet -- pass this into
    build_process_incoming_message's `conversation_engine` override to try
    it (see app/test_langgraph_chat.py)."""
    return LangGraphConversationEngineAdapter(get_graph=get_graph or get_cached_conversation_graph)


async def get_cached_mcp_zoho_chat_platform(tenant_id: str) -> McpZohoChatPlatformAdapter:
    return await _get_or_build_for_tenant(
        "mcp_zoho_chat_platform",
        tenant_id,
        lambda: _build_mcp_zoho_chat_platform(tenant_id),
    )


async def _build_mcp_zoho_chat_platform(tenant_id: str) -> McpZohoChatPlatformAdapter:
    return McpZohoChatPlatformAdapter(mcp_client=McpHttpClient(base_url=MCP_ZOHO_URL), tenant_id=tenant_id)


async def build_process_incoming_message(
    tenant_id: str,
    *,
    engine: str = "azure_openai",
    chat_platform: Optional[ChatPlatformPort] = None,
    rag_runner: Optional[Callable] = None,
    compress_fn: Optional[Callable] = None,
    check_business_availability: Optional[CheckBusinessAvailability] = None,
    get_lookup_procedure_price: Optional[Callable[[str], Awaitable[LookupProcedurePrice]]] = None,
    prompt_config: Optional[PromptConfigRepositoryPort] = None,
    conversation_engine: Optional[ConversationEnginePort] = None,
    include_flag_tools: bool = True,
) -> ProcessIncomingMessage:
    """Wires ProcessIncomingMessage with real adapters for the given tenant.

    `chat_platform`, `rag_runner`, `compress_fn`, `check_business_availability`,
    `get_lookup_procedure_price`, `prompt_config` and `conversation_engine`
    can all be overridden (used by tests to avoid hitting real
    Zoho/Azure OpenAI/Azure Search/Foundry over the network) -- when omitted,
    real adapters/functions are used, exactly as production would.
    `chat_platform` and the price-lookup tool (when not overridden) are both
    cached per tenant_id, since this builder runs once per incoming chat
    message.

    `engine` picks which ConversationEnginePort implementation to build --
    "azure_openai" (default, the real production path), "claude" (Claude
    Sonnet 5 via Microsoft Foundry, opaque engine -- see
    ClaudeFoundryConversationEngineAdapter's docstring) or "langgraph" (the
    new orchestrator + 4-branch agent, tools via MCP -- see
    build_langgraph_conversation_engine's docstring). Ignored when
    `conversation_engine` is passed directly -- that param replaces
    AzureOpenAIConversationEngineAdapter (or whichever engine `engine` would
    have built) entirely; `rag_runner`/`check_business_availability`/
    `get_lookup_procedure_price`/`prompt_config` are then ignored too, since
    they're that specific adapter's own construction params.

    `include_flag_tools` (azure_openai only, default True preserves prod
    behavior) -- False disconnects the 3 flag tools (revision/reintervention,
    emotional distress, minor patient), for the GPT-4o vs Claude comparison
    where both engines are wired with only `is_customer_service_available`/
    `procedures_and_treatments_price_list` (Claude never had the 3 flag
    tools to begin with, so this only matters for azure_openai).
    """
    with log.operation(tenant_id=tenant_id, engine=engine):
        tenant_repository = FilesystemTenantRepository(config_dir=CONFIG_DIR)
        await tenant_repository.get_tenant(tenant_id)  # validates config exists

        if chat_platform is None:
            chat_platform = await get_cached_chat_platform(tenant_id)

        conversation_history = _build_conversation_history()

        if conversation_engine is None:
            if engine == "claude":
                conversation_engine = build_claude_conversation_engine(
                    conversation_history,
                    check_business_availability=check_business_availability,
                    get_lookup_procedure_price=get_lookup_procedure_price,
                )
            elif engine == "azure_openai":
                conversation_engine = AzureOpenAIConversationEngineAdapter(
                    conversation_history=conversation_history,
                    rag_runner=rag_runner,
                    check_business_availability=check_business_availability or _check_business_availability,
                    get_lookup_procedure_price=get_lookup_procedure_price or get_cached_lookup_procedure_price,
                    prompt_config=prompt_config or _prompt_config,
                    include_flag_tools=include_flag_tools,
                )
            elif engine == "langgraph":
                conversation_engine = build_langgraph_conversation_engine()
            else:
                raise ValueError(
                    f"Unknown engine: {engine!r} (expected 'azure_openai', 'claude' or 'langgraph')"
                )

        reply_compressor = LLMReplyCompressionAdapter(compress_fn=compress_fn)

    return ProcessIncomingMessage(
        chat_platform=chat_platform,
        conversation_engine=conversation_engine,
        conversation_history=conversation_history,
        reply_compressor=reply_compressor,
        channel_character_limits=CHANNEL_CHARACTER_LIMITS,
        stateless_channels=STATELESS_CHANNELS,
        fallback_message=settings.FALLBACK_MESSAGE,
        max_history=MAX_HISTORY,
    )


def build_check_business_availability() -> CheckBusinessAvailability:
    return _check_business_availability


async def build_lookup_procedure_price(tenant_id: str) -> LookupProcedurePrice:
    secrets = EnvFileSecretsAdapter()
    price_catalog_config_repository = FilesystemPriceCatalogConfigRepository(config_dir=CONFIG_DIR)

    api_key = await secrets.get_secret(f"azure-search-api-key-{tenant_id}")
    price_catalog_config = await price_catalog_config_repository.get_config(tenant_id)

    price_catalog_search = AzureSearchPriceCatalogAdapter(
        search_endpoint=price_catalog_config.search_endpoint,
        index_name=price_catalog_config.index_name,
        api_key=api_key,
    )

    return LookupProcedurePrice(
        tenant_repository=FilesystemTenantRepository(config_dir=CONFIG_DIR),
        price_catalog_search=price_catalog_search,
    )


def build_handle_greeting_trigger() -> HandleGreetingTrigger:
    return HandleGreetingTrigger(
        greeting_config=FilesystemGreetingConfigRepository(config_dir=CONFIG_DIR),
    )


def build_intercept_continuation_token() -> InterceptContinuationToken:
    return InterceptContinuationToken(
        reply_language_resolver=ReplyLanguageResolverAdapter(
            conversation_history=_build_conversation_history(),
        ),
        translator=AzureTranslatorAdapter(),
        continue_message_config=FilesystemContinueMessageConfigRepository(config_dir=CONFIG_DIR),
    )


def build_acknowledge_file_upload() -> AcknowledgeFileUpload:
    return AcknowledgeFileUpload(
        reply_language_resolver=ReplyLanguageResolverAdapter(
            conversation_history=_build_conversation_history(),
        ),
        translator=AzureTranslatorAdapter(),
        file_upload_ack_config=FilesystemFileUploadAckConfigRepository(config_dir=CONFIG_DIR),
    )


def build_process_lead_submission(
    *,
    rag_runner: Optional[Callable] = None,
    check_business_availability: Optional[CheckBusinessAvailability] = None,
    get_lookup_procedure_price: Optional[Callable[[str], Awaitable[LookupProcedurePrice]]] = None,
    prompt_config: Optional[PromptConfigRepositoryPort] = None,
) -> ProcessLeadSubmission:
    conversation_engine = AzureOpenAIConversationEngineAdapter(
        conversation_history=_build_conversation_history(),
        rag_runner=rag_runner,
        check_business_availability=check_business_availability or _check_business_availability,
        get_lookup_procedure_price=get_lookup_procedure_price or get_cached_lookup_procedure_price,
        prompt_config=prompt_config or _prompt_config,
    )

    return ProcessLeadSubmission(conversation_engine=conversation_engine)


async def build_upload_knowledge_document(
    tenant_id: str,
    *,
    search_indexer_trigger_fn: Optional[Callable] = None,
) -> UploadKnowledgeDocument:
    secrets = EnvFileSecretsAdapter()
    connection_string = await secrets.get_secret(f"azure-blob-connection-string-{tenant_id}")

    return UploadKnowledgeDocument(
        blob_storage=AzureBlobStorageAdapter(connection_string=connection_string),
        search_indexer=CelerySearchIndexerAdapter(trigger_fn=search_indexer_trigger_fn),
        allowed_extensions=settings.ALLOWED_EXTENSIONS,
        allowed_mime_types=settings.ALLOWED_MIME_TYPES,
        max_size_bytes=settings.MAX_FILE_SIZE_MB * 1024 * 1024,
    )


async def build_index_knowledge_document(tenant_id: str) -> IndexKnowledgeDocument:
    secrets = EnvFileSecretsAdapter()
    search_indexer_config_repository = FilesystemSearchIndexerConfigRepository(config_dir=CONFIG_DIR)

    api_key = await secrets.get_secret(f"azure-search-api-key-{tenant_id}")
    search_indexer_config = await search_indexer_config_repository.get_config(tenant_id)

    search_indexer = AzureSearchIndexerControlAdapter(
        endpoint=search_indexer_config.search_endpoint,
        api_key=api_key,
        indexer_name=search_indexer_config.indexer_name,
    )

    return IndexKnowledgeDocument(search_indexer=search_indexer)
