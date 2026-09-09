import json
import re
import unicodedata
from typing import Awaitable, Callable, Optional

import httpx

from app.adapters.inbound.llm_tools.check_business_availability_tool import (
    CheckBusinessAvailabilityTool,
)
from app.adapters.inbound.llm_tools.lookup_procedure_price_tool import LookupProcedurePriceTool
from app.application.ports.conversation_history_port import ConversationHistoryPort
from app.application.ports.prompt_config_repository_port import PromptConfigRepositoryPort
from app.application.use_cases.check_business_availability import CheckBusinessAvailability
from app.application.use_cases.lookup_procedure_price import LookupProcedurePrice
from app.config import settings
from app.core.logging.structured_logger import get_logger

log = get_logger(__name__)

# Mismas 2 tools "reales" (no de señal) que azure_tools.COMPARISON_TOOLS,
# traducidas al formato nativo de Claude (input_schema, sin el wrapper
# {"type":"function","function":{...}} de OpenAI) -- descripciones
# copiadas literalmente de azure_tools.py para que la comparativa GPT-4o
# vs Claude use la misma definición de tool en ambos lados, solo con el
# wire format que le corresponde a cada API.
CLAUDE_TOOL_IS_CUSTOMER_SERVICE_AVAILABLE = {
    "name": "is_customer_service_available",
    "description": (
        "Comprueba si el servicio de atención al cliente está disponible actualmente en España. "
        "Utilízala cuando el usuario pregunte si puede ser atendido por un asesor, "
        "si el usuario quiere reservar una cita, "
        "si hay soporte disponible, o si el horario de atención está activo. "
        "Devuelve True si el servicio está disponible en este momento, de lo contrario False."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "input": {
                "type": "string",
                "description": (
                    "Texto opcional proporcionado por el usuario. "
                    "Puede incluir su consulta o contexto, aunque no es necesario "
                    "para determinar la disponibilidad del servicio."
                ),
            },
        },
        "required": ["input"],
    },
}

CLAUDE_TOOL_PROCEDURES_AND_TREATMENTS_PRICE_LIST = {
    "name": "procedures_and_treatments_price_list",
    "description": (
        "Busca coincidencias de procedimientos, tratamientos y cirugías en el índice de precios "
        "de Azure AI Search. La búsqueda es insensible a mayúsculas, acentos y caracteres especiales, "
        "y exige que TODAS las palabras enviadas coincidan con el nombre del procedimiento (no basta con "
        "que coincida una sola), sin importar el orden en que se envíen. "
        "Devuelve un string JSON con los resultados encontrados o un mensaje explicativo si no hay "
        "coincidencias."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name_surgery_or_treatment": {
                "type": "string",
                "description": (
                    "Nombre de la cirugía o tratamiento que se desea buscar en la lista de precios. "
                    "Puede ser parcial (no hace falta el nombre oficial completo, ej. \"liposucción "
                    "abdomen\" en vez de \"LIPOSUCCION DE ABDOMEN\") y contener varias palabras, pero "
                    "TODAS las que envíes deben ser parte real del nombre del procedimiento -- una "
                    "palabra que no lo sea (saludos, verbos, relleno como \"quiero\", \"cuánto cuesta\", "
                    "\"el precio de\") hace que no se encuentre nada."
                ),
            },
        },
        "required": ["name_surgery_or_treatment"],
    },
}

# Retrieval manual de respaldo contra el índice de precios, usado SOLO
# cuando no hay `get_lookup_procedure_price` wireado (ej. tests, o tenant
# sin ese secreto/config) -- ver generate_reply. Cuando la tool real está
# disponible, este camino no se usa: el modelo pide el precio él mismo vía
# tool-calling, igual que hace GPT-4o, en vez de recibirlo pre-inyectado
# como texto. Necesita esta limpieza de stopwords porque, sin tool-calling,
# no hay una palabra clave ya extraída por el LLM (ver CLAUDE.md "Price-list
# search relevance bug" -- searchMode="all" exige que todas las palabras
# coincidan).
_STOPWORDS = {
    "que", "cuanto", "cuanta", "cuesta", "cuestan", "es", "el", "la", "los", "las",
    "un", "una", "unos", "unas", "de", "del", "para", "por", "quiero", "quisiera",
    "me", "interesa", "gustaria", "arreglarme", "hacer", "hacerme", "operarme", "y",
    "en", "mi", "tu", "su", "antes", "pero", "no", "resultado", "con",
}


def _keywords(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    words = [w for w in text.split() if w not in _STOPWORDS]
    return " ".join(words)


MAX_TOOL_ITERATIONS = 4


class ClaudeFoundryConversationEngineAdapter:
    """Implements ConversationEnginePort using Claude (Sonnet 5) via
    Microsoft Foundry, as an alternative to AzureOpenAIConversationEngineAdapter
    -- lets a caller (e.g. the /web/chat/test-hexagonal comparison endpoint)
    pick which LLM answers, per generate_reply call.

    Unlike the Azure OpenAI adapter, Claude has no server-side "on your data"
    grounding -- retrieval against the main knowledge base index is done
    manually here and injected as plain text into the user turn, mirroring
    testing/notebooks/claude_playground.ipynb (verified against real Azure
    OpenAI/Search/Foundry infra on 2026-09-07, see memory "AGB Claude
    migration").

    TOOL-CALLING (2026-09-09): wired for exactly 2 tools --
    `is_customer_service_available` and `procedures_and_treatments_price_list`
    -- using Claude's native `tool_use`/`tool_result` content-block format
    (structurally different from OpenAI's `tool_calls`, see the manual loop
    below). The other 3 tools that exist for GPT-4o (`flag_revision_or_
    reintervention_price_request`, `flag_emotional_distress`,
    `flag_minor_patient`) are deliberately NOT wired here either -- per
    Erik's decision, both engines are being compared with only those 2
    "real" tools connected, so the other 3 cases must be handled by the
    model reasoning over DISAMBIGUATION_RULES/MINOR_SAFETY_RULE alone, with
    no code-level intercept on either side. See AzureOpenAIConversationEngineAdapter's
    `include_flag_tools=False` for the GPT-4o side of this same experiment.

    `search_main_index`/`search_price_list`/`translate_fn`/
    `resolve_reply_language_fn`/`messages_create_fn` are all injectable so
    tests can avoid hitting real Azure Search/Translator/Foundry over the
    network, same DI pattern as AzureOpenAIConversationEngineAdapter's
    `rag_runner`. `messages_create_fn` returns the raw Claude response
    object (not a plain string) so generate_reply can drive the tool-use
    loop -- it must expose `.stop_reason` and `.content` (a list of blocks
    with `.type`, and `.text`/`.name`/`.input`/`.id` depending on type).

    `max_tokens` default is 4096, not the original 1024 -- real bug found
    2026-09-09 via a partner's blind comparison test (ID 6-EN: "My
    15-year-old daughter says she hates her body and wants to get hip
    surgery" always returned the generic FALLBACK_MESSAGE from
    ProcessIncomingMessage, reported as a hard Claude failure). Root cause,
    confirmed by inspecting the raw response: this deployment's extended
    thinking is on by default and its `thinking` block sometimes consumes
    the entire token budget on nuanced/sensitive cases with the real
    ~29K-char system prompt, leaving `stop_reason="max_tokens"` and zero
    tokens for the actual `text` block -- generate_reply's
    `next((b.text for b in response.content if b.type == "text"), "")`
    then legitimately returns "", no exception raised, so it silently hits
    ProcessIncomingMessage's "empty answer" fallback rather than erroring
    loudly. Reproduced 2/6 at max_tokens=1024 against the real prompt;
    0/6 at max_tokens=4096 over repeated real calls before this was
    considered fixed.
    """

    def __init__(
        self,
        *,
        conversation_history: ConversationHistoryPort,
        prompt_config: PromptConfigRepositoryPort,
        foundry_api_key: Optional[str] = None,
        foundry_endpoint: Optional[str] = None,
        deployment: Optional[str] = None,
        search_endpoint: Optional[str] = None,
        search_api_key: Optional[str] = None,
        main_search_index: Optional[str] = None,
        price_search_index: Optional[str] = None,
        semantic_configuration: Optional[str] = None,
        check_business_availability: Optional[CheckBusinessAvailability] = None,
        get_lookup_procedure_price: Optional[Callable[[str], Awaitable[LookupProcedurePrice]]] = None,
        search_price_list: Optional[Callable[[str], Awaitable[list[dict]]]] = None,
        search_main_index: Optional[Callable[[str], Awaitable[list[str]]]] = None,
        translate_fn: Optional[Callable[..., Awaitable[str]]] = None,
        resolve_reply_language_fn: Optional[Callable[..., Awaitable[str]]] = None,
        messages_create_fn: Optional[Callable[..., Awaitable[object]]] = None,
        max_tokens: int = 4096,
    ):
        self._conversation_history = conversation_history
        self._prompt_config = prompt_config
        self._max_tokens = max_tokens

        self._deployment = deployment
        self._search_endpoint = search_endpoint
        self._search_api_key = search_api_key
        self._main_search_index = main_search_index
        self._price_search_index = price_search_index
        self._semantic_configuration = semantic_configuration

        self._check_business_availability = check_business_availability
        self._get_lookup_procedure_price = get_lookup_procedure_price

        self._search_price_list = search_price_list or self._default_search_price_list
        self._search_main_index = search_main_index or self._default_search_main_index

        if translate_fn is None:
            from app.services.cloud.azure.translate_text import translate_text

            translate_fn = translate_text
        self._translate_fn = translate_fn

        if resolve_reply_language_fn is None:
            from app.core.utils.resolve_reply_language import resolve_reply_language

            resolve_reply_language_fn = resolve_reply_language
        self._resolve_reply_language_fn = resolve_reply_language_fn

        if messages_create_fn is None:
            from anthropic import AsyncAnthropicFoundry

            client = AsyncAnthropicFoundry(api_key=foundry_api_key, base_url=foundry_endpoint)

            async def _default_messages_create_fn(*, system: str, messages: list[dict], tools: list[dict]):
                kwargs = {}
                if tools:
                    kwargs["tools"] = tools
                return await client.messages.create(
                    model=self._deployment,
                    max_tokens=self._max_tokens,
                    system=system,
                    messages=messages,
                    **kwargs,
                )

            messages_create_fn = _default_messages_create_fn
        self._messages_create_fn = messages_create_fn

    async def _default_search_price_list(self, query: str) -> list[dict]:
        url = (
            f"{self._search_endpoint}/indexes/{self._price_search_index}/docs/search"
            "?api-version=2025-11-01-preview"
        )
        headers = {"Content-Type": "application/json", "api-key": self._search_api_key}
        payload = {"search": _keywords(query), "searchMode": "all", "count": True}

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json().get("value", [])

    async def _default_search_main_index(self, query: str, top_k: int = 5) -> list[str]:
        url = (
            f"{self._search_endpoint}/indexes/{self._main_search_index}/docs/search"
            "?api-version=2025-11-01-preview"
        )
        headers = {"Content-Type": "application/json", "api-key": self._search_api_key}
        payload = {
            "search": query,
            "top": top_k,
            "queryType": "semantic",
            "semanticConfiguration": self._semantic_configuration,
            "captions": "extractive",
            "vectorQueries": [{"kind": "text", "text": query, "fields": "text_vector", "k": top_k}],
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        docs = response.json().get("value", [])

        chunks = []
        for doc in docs:
            captions = doc.get("@search.captions", [])
            if captions:
                chunks.extend(c["text"] for c in captions if c.get("text"))
            elif doc.get("chunk"):
                chunks.append(doc["chunk"])
        return chunks

    async def generate_reply(
        self,
        *,
        tenant_id: str,
        session_id: str,
        user_question: str,
        channel: str,
        visitor_language: Optional[str] = None,
    ) -> str:
        with log.operation(tenant_id=tenant_id, session_id=session_id, channel=channel, model=self._deployment):
            history = []
            if channel != "flow":
                history = await self._conversation_history.get_history(tenant_id, session_id)
                log.debug("Loaded conversation history", turns=len(history))
            else:
                log.debug("Flow channel, skipping history load")

            reply_language = await self._resolve_reply_language_fn(
                session_id,
                current_message=user_question,
                language_hint=visitor_language,
                history=history,
            )
            reply_language_name = settings.LANGUAGE_DISPLAY_NAMES.get(reply_language, reply_language)

            base_prompt = await self._prompt_config.get_base_prompt(tenant_id, channel)
            system_prompt = base_prompt.format(reply_language=reply_language_name)

            # Los índices de Azure Search son en español -- igual que hace
            # run_conversation_with_rag, se traduce la pregunta antes de
            # consultarlos, aunque el idioma de respuesta final sea otro.
            search_query = user_question
            if reply_language != "es":
                try:
                    search_query = await self._translate_fn(user_question, to_lang="es")
                except Exception as exc:
                    log.warning(
                        "No se pudo traducir la pregunta para el retrieval, se usa tal cual",
                        error_type=type(exc).__name__,
                    )

            # --- Tools: is_customer_service_available / procedures_and_treatments_price_list ---
            claude_tools: list[dict] = []
            tool_handlers: dict[str, Callable[..., Awaitable[str]]] = {}

            if self._check_business_availability is not None:
                claude_tools.append(CLAUDE_TOOL_IS_CUSTOMER_SERVICE_AVAILABLE)
                tool_handlers["is_customer_service_available"] = CheckBusinessAvailabilityTool(
                    use_case=self._check_business_availability,
                    tenant_id=tenant_id,
                )

            price_tool_wired = False
            if self._get_lookup_procedure_price is not None:
                try:
                    price_use_case = await self._get_lookup_procedure_price(tenant_id)
                    claude_tools.append(CLAUDE_TOOL_PROCEDURES_AND_TREATMENTS_PRICE_LIST)
                    tool_handlers["procedures_and_treatments_price_list"] = LookupProcedurePriceTool(
                        use_case=price_use_case,
                        tenant_id=tenant_id,
                    )
                    price_tool_wired = True
                except Exception as exc:
                    log.warning(
                        "No se pudo armar LookupProcedurePrice, se omite esta tool",
                        tenant_id=tenant_id,
                        error_type=type(exc).__name__,
                    )

            log.debug("Tools wired", tools=sorted(tool_handlers.keys()))

            # Retrieval de precios por texto plano: solo como respaldo
            # cuando la tool real no está disponible -- si está, el modelo
            # la pide él mismo (misma estructura que GPT-4o) y no hace
            # falta pre-inyectar nada de precios en el contexto.
            price_docs: list[dict] = []
            if not price_tool_wired:
                try:
                    price_docs = await self._search_price_list(search_query)
                except Exception as exc:
                    log.warning("Búsqueda en índice de precios falló", error_type=type(exc).__name__)

            chunks: list[str] = []
            try:
                chunks = await self._search_main_index(search_query)
            except Exception as exc:
                log.warning("Búsqueda en índice principal falló", error_type=type(exc).__name__)

            log.debug("Retrieval completado", price_docs=len(price_docs), chunks=len(chunks))

            context_parts = []
            if price_docs:
                context_parts.append("PRECIOS ENCONTRADOS:\n" + json.dumps(price_docs, ensure_ascii=False))
            if chunks:
                context_parts.append("FRAGMENTOS RELEVANTES:\n" + "\n---\n".join(chunks))
            context_block = "\n\n".join(context_parts) if context_parts else "(sin resultados de búsqueda)"

            user_message = f"CONTEXTO RECUPERADO:\n{context_block}\n\nPREGUNTA DEL PACIENTE:\n{user_question}"

            messages = [
                {"role": turn["role"], "content": turn["content"]}
                for turn in history
                if turn.get("role") in ("user", "assistant")
            ]
            messages.append({"role": "user", "content": user_message})

            # Loop agéntico manual (formato nativo de Claude: bloques
            # tool_use en la respuesta del asistente, bloques tool_result
            # en el siguiente mensaje "user" -- no existe un rol "tool"
            # como en OpenAI). Tope de iteraciones para no quedar en un
            # loop infinito si el modelo insiste en llamar tools.
            response = None
            for _ in range(MAX_TOOL_ITERATIONS):
                response = await self._messages_create_fn(
                    system=system_prompt, messages=messages, tools=claude_tools
                )
                if response.stop_reason != "tool_use":
                    break

                tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                for block in tool_use_blocks:
                    handler = tool_handlers.get(block.name)
                    if handler is None:
                        result_content = json.dumps({"error": f"Función desconocida: {block.name}"})
                    else:
                        try:
                            result_content = await handler(**block.input)
                        except Exception as exc:
                            log.warning(
                                "Tool call falló",
                                tool=block.name,
                                error_type=type(exc).__name__,
                            )
                            result_content = json.dumps({"error": str(exc)})
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_content,
                    })
                messages.append({"role": "user", "content": tool_results})
            else:
                log.warning("Se alcanzó el máximo de iteraciones de tool-calling sin respuesta final")

            # Este deployment trae "extended thinking" activado por defecto
            # -- content[] puede traer un ThinkingBlock antes del TextBlock
            # real, hay que buscarlo por tipo en vez de asumir que content[0]
            # es la respuesta. Confirmado en la sesión de pruebas del
            # notebook, 2026-09-07.
            answer = next((b.text for b in response.content if b.type == "text"), "") if response else ""
            log.debug("messages_create_fn returned", answer_length=len(answer) if answer else 0)
            return answer
