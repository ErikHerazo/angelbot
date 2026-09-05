import asyncio
import os
from typing import Awaitable, Callable, Dict, Optional, Tuple, TypeVar

from app.adapters.outbound.azure_openai.azure_openai_conversation_engine_adapter import (
    AzureOpenAIConversationEngineAdapter,
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
from app.application.ports.chat_platform_port import ChatPlatformPort
from app.application.ports.prompt_config_repository_port import PromptConfigRepositoryPort
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
                _tenant_scoped_cache[key] = await builder()
    return _tenant_scoped_cache[key]


def _build_conversation_history() -> RedisConversationHistoryAdapter:
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


async def build_process_incoming_message(
    tenant_id: str,
    *,
    chat_platform: Optional[ChatPlatformPort] = None,
    rag_runner: Optional[Callable] = None,
    compress_fn: Optional[Callable] = None,
    check_business_availability: Optional[CheckBusinessAvailability] = None,
    get_lookup_procedure_price: Optional[Callable[[str], Awaitable[LookupProcedurePrice]]] = None,
    prompt_config: Optional[PromptConfigRepositoryPort] = None,
) -> ProcessIncomingMessage:
    """Wires ProcessIncomingMessage with real adapters for the given tenant.

    `chat_platform`, `rag_runner`, `compress_fn`, `check_business_availability`,
    `get_lookup_procedure_price` and `prompt_config` can all be overridden
    (used by tests to avoid hitting real Zoho/Azure OpenAI/Azure Search over
    the network) -- when omitted, real adapters/functions are used, exactly
    as production would. `chat_platform` and the price-lookup tool (when not
    overridden) are both cached per tenant_id, since this builder runs once
    per incoming chat message.
    """
    tenant_repository = FilesystemTenantRepository(config_dir=CONFIG_DIR)
    tenant = await tenant_repository.get_tenant(tenant_id)  # validates config exists

    if chat_platform is None:
        chat_platform = await get_cached_chat_platform(tenant_id)

    conversation_history = _build_conversation_history()

    conversation_engine = AzureOpenAIConversationEngineAdapter(
        conversation_history=conversation_history,
        rag_runner=rag_runner,
        check_business_availability=check_business_availability or _check_business_availability,
        get_lookup_procedure_price=get_lookup_procedure_price or get_cached_lookup_procedure_price,
        prompt_config=prompt_config or _prompt_config,
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
