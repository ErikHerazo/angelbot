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
    history: list | None = None,
    tool_overrides: dict | None = None,
    base_prompt_override: str | None = None,
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
    # Si el caller ya trae el historial (ej. el adapter de ConversationEnginePort,
    # que lo obtiene vía ConversationHistoryPort), se usa tal cual. Si no, se
    # conserva el comportamiento legacy de leerlo aquí mismo -- necesario para
    # que el flujo de producción actual (que no pasa `history`) no cambie.
    if history is None:
        if channel == "flow":
            history = []
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
    # Si el caller ya trae el prompt (ej. el adapter de ConversationEnginePort,
    # que lo obtiene vía PromptConfigRepositoryPort), se usa tal cual. Si no,
    # se conserva el comportamiento legacy de leerlo desde constants.py.
    base_prompt = base_prompt_override if base_prompt_override is not None else get_base_prompt_by_channel(channel)
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

    # 📸 Copia de los mensajes ANTES de la ronda de tool-calls (sin ningún
    # resultado de precio todavía). Se usa más abajo si hay que cortar por
    # ambigüedad: permite una respuesta final generada por el LLM (para que
    # pueda sumar empatía si detecta angustia emocional) sin riesgo de que
    # filtre un precio, porque esos mensajes nunca llegan a este snapshot.
    pre_tool_messages = list(messages)

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
        emotional_distress_detected = False
        minor_safety_concern = False
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
                        # 🔀 Si hay un override hexagonal para esta tool (ver
                        # ConversationEnginePort/AzureOpenAIConversationEngineAdapter),
                        # se usa en vez del azure_tools.py legacy -- el resto
                        # de la lógica de este bloque no cambia porque ambos
                        # devuelven el mismo formato de JSON.
                        if tool_overrides and "is_customer_service_available" in tool_overrides:
                            function_response = await tool_overrides["is_customer_service_available"](
                                input=function_args.get("input")
                            )
                        else:
                            function_response = azure_tools.is_customer_service_available(
                                input=function_args.get("input")
                            )
                        # print(f"==========🔹 Respuesta is_customer_service_available:", function_response)
                    elif function_name == "procedures_and_treatments_price_list":
                        if tool_overrides and "procedures_and_treatments_price_list" in tool_overrides:
                            function_response = await tool_overrides["procedures_and_treatments_price_list"](
                                name_surgery_or_treatment=function_args.get("name_surgery_or_treatment"),
                            )
                        else:
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
                        if tool_overrides and "flag_revision_or_reintervention_price_request" in tool_overrides:
                            function_response = await tool_overrides["flag_revision_or_reintervention_price_request"](
                                input=function_args.get("input")
                            )
                        else:
                            function_response = azure_tools.flag_revision_or_reintervention_price_request(
                                input=function_args.get("input")
                            )
                    elif function_name == "flag_emotional_distress":
                        # 🔁 Señal del LLM: detectó angustia emocional/urgencia
                        # subjetiva (ver DISAMBIGUATION_RULES). El código toma
                        # el control desde aquí -- la regla #9 dice que esto
                        # tiene prioridad sobre cualquier respuesta comercial,
                        # así que se ignora cualquier resultado de precio que
                        # el LLM haya pedido en paralelo en el mismo turno.
                        emotional_distress_detected = True
                        if tool_overrides and "flag_emotional_distress" in tool_overrides:
                            function_response = await tool_overrides["flag_emotional_distress"](
                                input=function_args.get("input")
                            )
                        else:
                            function_response = azure_tools.flag_emotional_distress(
                                input=function_args.get("input")
                            )
                    elif function_name == "flag_minor_patient":
                        # 🔁 Señal del LLM: el paciente del que se habla es
                        # menor de 16 años (edad ya conocida) y pide precio o
                        # recomendación de un procedimiento estético. Tiene
                        # prioridad sobre TODO lo demás -- MINOR_SAFETY_RULE
                        # es una regla de seguridad global, no de
                        # desambiguación (ver PRIORIDAD en DISAMBIGUATION_RULES)
                        # -- así que se ignora cualquier resultado de precio
                        # que el LLM haya pedido en paralelo en el mismo turno.
                        minor_safety_concern = True
                        if tool_overrides and "flag_minor_patient" in tool_overrides:
                            function_response = await tool_overrides["flag_minor_patient"](
                                input=function_args.get("input")
                            )
                        else:
                            function_response = azure_tools.flag_minor_patient(
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

        if minor_safety_concern:
            # 🚧 Paciente menor de edad detectado (ver flag_minor_patient más
            # arriba): MINOR_SAFETY_RULE es una regla de seguridad global,
            # tiene prioridad sobre TODO -- angustia emocional, revisión,
            # ambigüedad de precio -- así que se ignora cualquier resultado
            # de precio/procedimiento que el LLM haya pedido en paralelo en
            # el mismo turno. Se genera la respuesta con MINOR_SAFETY_PROMPT
            # a partir de los mensajes de ANTES de la ronda de tool-calls
            # (pre_tool_messages, sin ningún precio en el contexto) y sin
            # data_sources, para que ni el grounding RAG ni un precio ya
            # obtenido puedan colarse por encima de estas instrucciones.
            minor_prompt = list(pre_tool_messages)
            minor_prompt.append({"role": "system", "content": constants.MINOR_SAFETY_PROMPT})
            try:
                minor_response = await make_completion(
                    minor_prompt, max_toks, force_text=True, use_data_sources=False
                )
                final_answer = remove_doc_refs(minor_response.choices[0].message.content)
            except Exception:
                logger.exception(
                    "No se pudo generar la respuesta de seguridad de menor con el LLM, se usa el mensaje fijo",
                    extra={"session_id": session_id},
                )
                final_answer = await translate_text(
                    text=constants.MINOR_SAFETY_FALLBACK_MESSAGE,
                    to_lang=reply_lang,
                    from_lang="es",
                )
        elif emotional_distress_detected:
            # 🚧 Angustia emocional detectada (ver flag_emotional_distress
            # más arriba): tiene prioridad sobre cualquier respuesta
            # comercial (regla #9), así que se ignora cualquier resultado de
            # precio/procedimiento que el LLM haya pedido en paralelo en el
            # mismo turno. Se genera la respuesta con EMOTIONAL_DISTRESS_PROMPT
            # a partir de los mensajes de ANTES de la ronda de tool-calls
            # (pre_tool_messages, sin ningún precio en el contexto) y sin
            # data_sources, para que ni el grounding RAG ni un precio ya
            # obtenido puedan colarse por encima de estas instrucciones.
            distress_prompt = list(pre_tool_messages)
            distress_prompt.append({"role": "system", "content": constants.EMOTIONAL_DISTRESS_PROMPT})
            try:
                distress_response = await make_completion(
                    distress_prompt, max_toks, force_text=True, use_data_sources=False
                )
                final_answer = remove_doc_refs(distress_response.choices[0].message.content)
            except Exception:
                logger.exception(
                    "No se pudo generar la respuesta de angustia emocional con el LLM, se usa el mensaje fijo",
                    extra={"session_id": session_id},
                )
                final_answer = await translate_text(
                    text=constants.EMOTIONAL_DISTRESS_FALLBACK_MESSAGE,
                    to_lang=reply_lang,
                    from_lang="es",
                )
        elif revision_price_requested:
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
            # arriba): NO se deja que el LLM vea el resultado real de la
            # tool (para que nunca pueda filtrar un precio), pero sí se le
            # pide que redacte la pregunta aclaratoria él mismo, a partir
            # de los mensajes de ANTES de la ronda de tool-calls
            # (pre_tool_messages) -- así puede sumar una frase de empatía
            # si el mensaje del paciente muestra angustia emocional, en vez
            # de una pregunta fija siempre neutra.
            clarification_prompt = list(pre_tool_messages)
            clarification_prompt.append({
                "role": "system",
                "content": (
                    f"CONTEXTO (no es un fallo ni falta de información): el paciente pidió precio de "
                    f"\"{ambiguous_procedure_name}\", y ese procedimiento SÍ existe y SÍ tiene precio en "
                    "la clínica, pero tiene varias variantes distintas en el catálogo (por ejemplo, "
                    "distintas zonas corporales) y todavía no se sabe cuál de ellas quiere el paciente. "
                    "NO digas que no tienes información, que no está disponible, ni que hay que agendar "
                    "una valoración para saber el precio -- el único motivo por el que no puedes dar el "
                    "precio ahora es que falta saber la variante, nada más. Ignora por completo cualquier "
                    "documento o contexto recuperado sobre este tema para esta respuesta -- no lo "
                    "necesitas, y no debe influir en si dices o no que falta información. "
                    "NO menciones ningún precio ni ninguna variante con su precio. "
                    "Si el mensaje del paciente muestra angustia emocional (ver la regla "
                    "correspondiente), reconócela brevemente primero, sin reforzar la urgencia ni "
                    "presentar un tratamiento como solución inmediata. "
                    f"Tu única tarea en esta respuesta es preguntar, de forma breve y concreta, a cuál "
                    f"variante de \"{ambiguous_procedure_name}\" se refiere el paciente (por ejemplo, si "
                    "es una zona corporal, pregunta la zona)."
                )
            })
            try:
                clarification_response = await make_completion(
                    clarification_prompt, max_toks, force_text=True, use_data_sources=False
                )
                final_answer = remove_doc_refs(clarification_response.choices[0].message.content)
            except Exception:
                logger.exception(
                    "No se pudo generar la pregunta aclaratoria con el LLM, se usa el mensaje fijo",
                    extra={"session_id": session_id},
                )
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
