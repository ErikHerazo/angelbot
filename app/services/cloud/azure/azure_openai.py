import os
import json
import random
import asyncio
from azure.core.exceptions import HttpResponseError

from app.core import constants
from app.services.cloud.azure import azure_tools
from app.services.cloud.azure.client import get_azure_openai_client
from app.core.logging_config import logger

MAX_RETRIES = 5
BASE_DELAY = 1.0

async def call_with_retry(func, *args, **kwargs):
    """
    Wrapper con retry/backoff + jitter para manejar errores 429 o 503.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return await func(*args, **kwargs)

        except HttpResponseError as e:
            status = getattr(e.response, "status_code", None)
            retry_after = None

            if hasattr(e, "response") and hasattr(e.response, "headers"):
                retry_after = e.response.headers.get("retry-after")

            if status in [429, 503]:
                if retry_after:
                    delay = float(retry_after)
                else:
                    delay = BASE_DELAY * (2 ** (attempt - 1)) + random.uniform(0, 0.5)

                logger.warning(
                    f"⚠️ Rate limit ({status}) detectado. Reintento {attempt}/{MAX_RETRIES} "
                    f"en {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"❌ Error HTTP inesperado ({status}): {e}")
                raise e

        except Exception as e:
            logger.exception(f"💥 Excepción inesperada en intento {attempt}: {e}")
            await asyncio.sleep(BASE_DELAY * (2 ** (attempt - 1)))

    raise Exception("🚫 Excedido el número máximo de reintentos con Azure OpenAI.")


async def run_conversation_with_rag(user_question: str):
    messages = [
        {"role": "system", "content": constants.ASSISTANT_PROMPT},
        {"role": "user", "content": user_question},
    ]

    max_toks = 300 if len(user_question) > 200 else 150
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    client = get_azure_openai_client()

    async def make_completion(messages, max_toks):
        return await client.chat.completions.create(
            model=deployment,
            messages=messages,
            tools=azure_tools.tools,
            tool_choice="auto",
            temperature=0,
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
                                "deployment_name": os.environ[
                                    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
                                ],
                            },
                        },
                    }
                ]
            },
        )

    # 🌀 Primera llamada con retry
    response = await call_with_retry(make_completion, messages, max_toks)

    logger.info(f"📌 RESPONSE RAW: {response}")
    print("📌 RESPONSE RAW:", response)

    # ✅ Validación segura de choices y message
    if not response.choices or response.choices[0] is None:
        raise Exception(f"❌ Respuesta inválida de Azure OpenAI: {response}")

    response_message = response.choices[0].message
    if response_message is None:
        raise Exception(f"❌ response.choices[0].message es None: {response.choices[0]}")

    messages.append(
        {"role": response_message.role, "content": response_message.content or ""}
    )
    logger.info(f"🧠 Respuesta inicial: {response_message.content[:200] if response_message.content else '[None]'}...")

    # 🔧 Manejo seguro de tool calls
    if hasattr(response_message, "tool_calls") and response_message.tool_calls:
        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            arguments_str = tool_call.function.arguments or "{}"
            function_args = json.loads(arguments_str)
            logger.info(f"🔧 Tool call detectada: {function_name} | Args: {function_args}")

            if function_name == "is_customer_service_available":
                function_response = azure_tools.is_customer_service_available() or {"error": "tool returned None"}
            elif function_name == "save_user":
                function_response = azure_tools.save_user(
                    name=function_args.get("name"),
                    email=function_args.get("email"),
                ) or {"error": "tool returned None"}
            else:
                function_response = {"error": "Unknown function"}

            logger.info(f"✅ Resultado tool '{function_name}': {function_response}")
            messages.append({"role": "tool", "content": str(function_response)})
    else:
        logger.info("ℹ️ No hubo tool calls en la primera respuesta.")

    # 🧠 Segunda llamada (respuesta final)
    final_response = await call_with_retry(make_completion, messages, 500)

    logger.info(f"📌 RESPONSE RAW (final): {final_response}")
    print("📌 RESPONSE RAW (final):", final_response)

    # ✅ Validación segura de final_response
    final_message = final_response.choices[0].message if final_response.choices and final_response.choices[0] else None
    final_content = final_message.content if final_message and final_message.content else "[⚠️ No se generó respuesta de texto]"

    logger.info(f"✅ Respuesta final: {final_content[:250]}...")

    return final_content
