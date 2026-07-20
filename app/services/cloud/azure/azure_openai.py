import json
from dotenv import load_dotenv
from app.core import constants
from app.core.logging_config import logger

from app.services.cloud.azure import azure_tools
from app.services.cache.session_memory import SessionMemoryRedis

from app.core.utils.text_cleaner import remove_doc_refs
from app.services.cloud.azure.translate_text import translate_text
from app.core.utils.get_base_prompt_by_channel import get_base_prompt_by_channel
from app.core.utils.resolve_reply_language import resolve_reply_language
from app.core.utils.enforce_reply_language import enforce_reply_language

from app.services.cloud.azure.make_completion import make_completion
from app.services.cloud.azure.token_utils import token_estimate
from app.services.zoho.handle_continue_token import handle_continue_token


load_dotenv()

session_memory = SessionMemoryRedis()

async def run_conversation_with_rag(
    session_id: str,
    user_question: str,
    channel: str = "website",
    visitor_language: str | None = None,
):
    """
    Execute a conversation with Azure OpenAI using RAG + parallel function calls.
    Compatible with the function calling pattern documented by Azure.
    """

    response = await handle_continue_token(
        session_id=session_id,
        user_question=user_question,
        channel=channel,
        visitor_language=visitor_language,
    )

    if response is not None:
        return response

    print(f"🌐 User Question: {user_question}")
    # logger.info(f"SESSION RAG: {session_id}")

    # 🧠 Retrieve conversation history
    if channel == "flow":
        history=[]
    else:
        history = await session_memory.get_session(session_id)

    # 🔥 INYECTAR MENSAJE INICIAL (SOLO CHAT)
    if channel != "flow" and not history:
        history.append({
            "role": "assistant",
            "content": constants.INITIAL_ASSISTANT_MESSAGE
        })

    # logger.debug("History", extra={"history": history})

    # 🌐 El idioma de respuesta se resuelve por código (Azure Language
    # Detector sobre el mensaje/historial, con fallback al idioma declarado
    # por Zoho) y se inyecta como instrucción directa en el prompt; el LLM
    # ya no tiene que inferirlo por su cuenta (ver REGLA DE IDIOMA).
    # Para el canal "flow" el mensaje es un texto sintético en español
    # (plantilla de campos del formulario), así que no sirve para detectar
    # idioma: se confía directamente en el idioma declarado por el formulario.
    reply_lang = await resolve_reply_language(
        session_id=session_id,
        current_message=None if channel == "flow" else user_question,
        language_hint=visitor_language,
        use_history=(channel != "flow"),
    )
    reply_language_label = constants.LANGUAGE_DISPLAY_NAMES.get(reply_lang, reply_lang)

    # Solo traducimos la pregunta a español para la búsqueda en Azure AI
    # Search (el índice de documentos está en español).
    rag_query = await translate_text(
        text=user_question,
        to_lang='es'
    )

    # Building the initial context
    base_prompt = get_base_prompt_by_channel(channel)
    system_prompt = base_prompt.format(reply_language=reply_language_label)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({
        "role": "system",
        "content": (
            "Texto original del usuario en este turno (no es la consulta de búsqueda "
            "ni debes responder a este texto directamente, es solo para que verifiques "
            f"si pidió explícitamente cambiar de idioma): {user_question}"
        )
    })
    messages.append({"role": "user", "content": rag_query})

    question_tokens = token_estimate(text=rag_query, model=constants.OPENAI_BASE_MODEL_NAME)
    
    max_toks = (
        constants.OPENAI_MAX_TOKENS
        if question_tokens > 200
        else int(constants.OPENAI_MAX_TOKENS / 3)
    )

    # 🌀 First call with retry
    response = await make_completion(messages, max_toks)
    response_message = response.choices[0].message

    # 🚀 Parallel call control (parallel tool calls)
    if response_message.tool_calls:
        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            try:
                function_args = json.loads(tool_call.function.arguments)
            except Exception:
                logger.warning(f"⚠️ Invalid arguments for {function_name}: {tool_call.function.arguments}")
                continue

            logger.info(f"🧩 Tool Call: {function_name} | Args: {function_args}")

            # Execute corresponding function
            try:
                if function_name == "is_customer_service_available":
                    function_response = azure_tools.is_customer_service_available(
                        input=function_args.get("input")
                    )
                    # print(f"==========🔹 Respuesta is_customer_service_available:", function_response)
                elif function_name == "procedures_and_treatments_price_list":
                    function_response = azure_tools.procedures_and_treatments_price_list(
                        name_surgery_or_treatment=function_args.get("name_surgery_or_treatment"),
                    )
                    # print(f"==========🔹 Respuesta de listado de precios:", function_response)
                else:
                    function_response = json.dumps({"error": f"Función desconocida: {function_name}"})
                    
            except Exception as e:
                logger.exception(f"💥 Error executing function {function_name}: {e}")
                function_response = json.dumps({"error": str(e)})

            # Record tool response
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": function_response
            })

    else:
        messages.append({
            "role": response_message.role,
            "content": response_message.content or "",
        })

    # 🔁 Refuerzo de idioma: los resultados de herramientas suelen venir en
    # español y pueden hacer que el modelo ignore la instrucción de idioma
    # del system prompt inicial. Se repite justo antes de la generación
    # final, que es el punto donde realmente se decide el idioma de salida.
    messages.append({
        "role": "system",
        "content": (
            f"Recordatorio final: tu respuesta debe estar completamente en "
            f"{reply_language_label}, incluyendo cualquier precio, nombre de "
            f"tratamiento o dato que hayas obtenido de las herramientas. No "
            f"dejes ninguna parte de la respuesta en español a menos que "
            f"{reply_language_label} sea español."
        )
    })

    # 🚦 Avoid tool call loops: force textual response
    final_response = await make_completion(messages, max_toks, force_text=True)
    final_message = final_response.choices[0].message

    final_answer = remove_doc_refs(final_message.content)
    print(f"🗣️ Respuesta generada por el LLM (reply_lang esperado: {reply_lang}):\n{final_answer}")

    # 🛡️ Última barrera: si a pesar de todo el LLM respondió en un idioma
    # distinto al resuelto para este turno, se corrige por código en vez
    # de confiar en que el modelo lo haya hecho bien.
    final_answer = await enforce_reply_language(final_answer, reply_lang)
    print(f"✅ Respuesta final enviada al usuario:\n{final_answer}")

    return final_answer
