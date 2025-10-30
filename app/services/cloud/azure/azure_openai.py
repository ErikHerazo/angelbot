import os
import json
import random
import asyncio
from azure.core.exceptions import HttpResponseError

from app.core import constants
from app.services.cloud.azure import azure_tools
from app.services.cloud.azure.client import get_azure_openai_client
from app.core.logging_config import logger

from app.services.cache.session_memory import SessionMemoryRedis

session_memory = SessionMemoryRedis()
MAX_HISTORY = 6

async def call_with_retry(func, *args, **kwargs):
    """
    Wrapper con retry/backoff + jitter para manejar errores 429 o 503.
    """
    for attempt in range(1, constants.OPENAI_MAX_RETRIES + 1):
        try:
            return await func(*args, **kwargs)

        except HttpResponseError as e:
            status = getattr(e.response, "status_code", None)
            retry_after = None

            if hasattr(e, "response") and hasattr(e.response, "headers"):
                retry_after = e.response.headers.get("retry-after")

            if status in [429, 503]:
                delay = float(retry_after) if retry_after else (1.0 * (2 ** (attempt - 1)) + random.uniform(0, 0.5))
                logger.warning(f"⚠️ Rate limit ({status}) detectado. Reintento {attempt}/{constants.OPENAI_MAX_RETRIES} en {delay:.2f}s...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"❌ Error HTTP inesperado ({status}): {e}")
                raise e

        except Exception as e:
            logger.exception(f"💥 Excepción inesperada en intento {attempt}: {e}")
            await asyncio.sleep(1.0 * (2 ** (attempt - 1)))

    raise Exception("🚫 Excedido el número máximo de reintentos con Azure OpenAI.")

async def run_conversation_with_rag(session_id: str, user_question: str):
    """
    Ejecuta una conversación con Azure OpenAI usando RAG + llamadas a funciones paralelas.
    Compatible con el patrón de function calling documentado por Azure.
    """
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    client = get_azure_openai_client()

    # 🧠 Recuperar historial de conversación desde Redis
    history = await session_memory.get_session(session_id)
    # logger.info(f"📝 Historial recuperado desde Redis: {history}")
    if not history:
        history = []

    # Construir el contexto inicial
    messages = [{"role": "system", "content": constants.ASSISTANT_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_question})

    max_toks = constants.OPENAI_MAX_TOKENS if len(user_question) > 200 else int(constants.OPENAI_MAX_TOKENS / 3)

    async def make_completion(messages, max_toks, force_text=False):
        """
        Realiza una llamada a Azure OpenAI ChatCompletion.
        Si `force_text=True`, se fuerza tool_choice='none' para evitar más tool calls.
        """
        return await client.chat.completions.create(
            model=deployment_name,
            messages=messages,
            tools=azure_tools.tools,
            tool_choice="none" if force_text else "auto",
            temperature=constants.OPENAI_TEMPERATURE,
            max_tokens=max_toks,
            extra_body={
                "data_sources": [
                    {
                        "type": "azure_search",
                        "parameters": {
                            "endpoint": os.environ["AZURE_AI_SEARCH_ENDPOINT"],
                            "index_name": os.environ["AZURE_AI_SEARCH_INDEX"],
                            "query_type": "vector_semantic_hybrid",
                            "semantic_configuration": "default",
                            "fields_mapping": {
                                "content_fields": ["content"],
                                "title_field": "title",
                            },
                            "authentication": {
                                "type": "api_key",
                                "key": os.environ["AZURE_AI_SEARCH_API_KEY"],
                            },
                            "embedding_dependency": {
                                "type": "deployment_name",
                                "deployment_name": os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
                            },
                        },
                    },
                ]
            },
        )

    # 🌀 Primera llamada con retry
    response = await call_with_retry(make_completion, messages, max_toks)
    response_message = response.choices[0].message
    logger.info(f"📌 RESPONSE RAW: {response_message}")

    messages.append({
        "role": response_message.role,
        "content": response_message.content or "",
    })

    # logger.info("🧠 Respuesta inicial recibida.")

    # 🚀 Manejo de llamadas paralelas (parallel tool calls)
    if response_message.tool_calls:
        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            try:
                function_args = json.loads(tool_call.function.arguments)
            except Exception:
                logger.warning(f"⚠️ Argumentos inválidos para {function_name}: {tool_call.function.arguments}")
                continue

            logger.info(f"🧩 Tool Call: {function_name} | Args: {function_args}")

            # Ejecutar función correspondiente
            try:
                if function_name == "is_customer_service_available":
                    function_response = azure_tools.is_customer_service_available(
                        input=function_args.get("input")
                    )
                elif function_name == "save_user":
                    function_response = azure_tools.save_user(
                        name=function_args.get("name"),
                        email=function_args.get("email"),
                    )
                elif function_name == "procedures_and_treatments_price_list":
                    function_response = azure_tools.procedures_and_treatments_price_list(
                        name_surgery_or_treatment=function_args.get("name_surgery_or_treatment"),
                    )
                else:
                    function_response = json.dumps({"error": f"Función desconocida: {function_name}"})

            except Exception as e:
                logger.exception(f"💥 Error ejecutando función {function_name}: {e}")
                function_response = json.dumps({"error": str(e)})

            # Registrar respuesta del tool
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": function_response
            })

    else:
        logger.info("ℹ️ No se detectaron tool calls en la respuesta inicial.")
        pass

    # 🚦 Evitar loops de tool calls: fuerza respuesta textual
    final_response = await call_with_retry(make_completion, messages, max_toks, force_text=True)
    final_message = final_response.choices[0].message

    # ✅ Validar respuesta final
    if not final_message.content:
        logger.warning("⚠️ El modelo devolvió content=None. Detalles:")
        logger.warning(final_message)
        return "⚠️ No se pudo generar una respuesta válida en este momento. Intenta nuevamente."
    
    # 💾 Guardar conversación en Redis (solo últimos N mensajes)
    history.extend([
        {"role": "user", "content": user_question},
        {"role": "assistant", "content": final_message.content}
    ])

    # mantener sólo los últimos N mensajes
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]

    await session_memory.connect()
    await session_memory.save_session(session_id, history)

    logger.info(f"💬 ================ Respuesta final: {final_message.content}")
    return final_message.content
