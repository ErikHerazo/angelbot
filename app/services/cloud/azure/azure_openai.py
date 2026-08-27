import json
from dotenv import load_dotenv
from openai import BadRequestError
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
        try:
            history = await session_memory.get_session(session_id)
        except Exception:
            # Un fallo transitorio de Redis no debe tumbar la conversación:
            # se continúa sin historial previo en vez de propagar el error.
            logger.exception(
                "No se pudo leer el historial de sesión, se continúa sin él",
                extra={"session_id": session_id},
            )
            history = []

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

    try:
        # 🌀 First call with retry
        response = await make_completion(messages, max_toks)
        response_message = response.choices[0].message

        # 🚀 Parallel call control (parallel tool calls)
        revision_price_requested = False
        ambiguous_procedure_name = None
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
                        # 🚧 Si la búsqueda de precios devolvió más de un
                        # resultado, el término es ambiguo (ej. "liposucción"
                        # sin zona): el código corta el flujo aquí en vez de
                        # dejar que el LLM elija o muestre uno o varios
                        # precios (ya se probó que no es confiable), y
                        # responde con una pregunta aclaratoria fija.
                        try:
                            parsed_response = json.loads(function_response)
                            if len(parsed_response.get("results", [])) > 1:
                                ambiguous_procedure_name = function_args.get("name_surgery_or_treatment")
                        except Exception:
                            pass
                    elif function_name == "flag_revision_or_reintervention_price_request":
                        # 🔁 Señal del LLM: ya identificó que es una revisión/
                        # reintervención con pregunta de precio. El código toma
                        # el control desde aquí en vez de dejar que el LLM
                        # improvise un precio (ver REVISION_PRICE_FALLBACK_MESSAGE).
                        revision_price_requested = True
                        function_response = azure_tools.flag_revision_or_reintervention_price_request(
                            input=function_args.get("input")
                        )
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

        if revision_price_requested:
            # 🚧 Caso de reintervención/revisión con pregunta de precio: el
            # catálogo solo tiene el precio de la cirugía de primera vez, que
            # no aplica aquí. En vez de confiar en que el LLM lo recuerde en
            # la generación final (ya se probó que no es confiable), se
            # responde de forma determinista, sin volver a llamar al LLM.
            final_answer = await translate_text(
                text=constants.REVISION_PRICE_FALLBACK_MESSAGE,
                to_lang=reply_lang,
                from_lang="es",
            )
        elif ambiguous_procedure_name:
            # 🚧 Término ambiguo con varias variantes de catálogo (ver más
            # arriba): se corta el flujo con una pregunta fija en vez de
            # dejar que el LLM decida qué precio(s) mostrar.
            final_answer = await translate_text(
                text=(
                    f"Existen varios tratamientos relacionados con {ambiguous_procedure_name}. "
                    "¿Podrías indicarme cuál te interesa exactamente?"
                ),
                to_lang=reply_lang,
                from_lang="es",
            )
        else:
            # 🔁 Refuerzo de idioma: los resultados de herramientas suelen venir
            # en español y pueden hacer que el modelo ignore la instrucción de
            # idioma del system prompt inicial. Se repite justo antes de la
            # generación final, que es el punto donde realmente se decide el
            # idioma de salida.
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

    except BadRequestError as ex:
        error_str = str(ex)
        if "content_filter" not in error_str and "ResponsibleAIPolicyViolation" not in error_str:
            raise

        # 🚧 Azure bloqueó la solicitud por su filtro de contenido antes de
        # generar una respuesta (ej. combinaciones sensibles como menor de
        # edad + procedimiento de pecho). En vez de dejar que esto caiga en
        # el fallback genérico en inglés de process_zoho_message.py, se
        # responde con un mensaje apropiado, traducido al idioma resuelto.
        logger.warning(
            "🚧 Azure content filter blocked the request",
            extra={"session_id": session_id, "error": error_str},
        )
        final_answer = await translate_text(
            text=constants.CONTENT_FILTER_FALLBACK_MESSAGE,
            to_lang=reply_lang,
            from_lang="es",
        )

    print(f"🗣️ Respuesta generada por el LLM (reply_lang esperado: {reply_lang}):\n{final_answer}")

    # 🛡️ Última barrera: si a pesar de todo el LLM respondió en un idioma
    # distinto al resuelto para este turno, se corrige por código en vez
    # de confiar en que el modelo lo haya hecho bien.
    final_answer = await enforce_reply_language(final_answer, reply_lang)
    print(f"✅ Respuesta final enviada al usuario:\n{final_answer}")

    return final_answer
