import os
import json
from dotenv import load_dotenv
from app.core import constants
from app.core.logging_config import logger

from app.services.cloud.azure import azure_tools
from app.services.cache.session_memory import SessionMemoryRedis

from app.core.utils.language_detector import detect_language
from app.core.utils.text_cleaner import remove_doc_refs
from app.core.utils.translate_text import translate_text

from app.services.cloud.azure.make_completion import make_completion
from app.services.cloud.azure.token_utils import token_estimate
from app.core.utils.get_base_prompt_by_channel import get_base_prompt_by_channel


load_dotenv()

session_memory = SessionMemoryRedis()
MAX_HISTORY = 6

async def run_conversation_with_rag(session_id: str, user_question: str, channel: str="website"):
    """
    Execute a conversation with Azure OpenAI using RAG + parallel function calls.
    Compatible with the function calling pattern documented by Azure.
    """

    if user_question == constants.CONTINUE_TOKEN:
        if channel != "flow":
            return "Aquí sigo contigo 😊 ¿Quieres continuar con lo anterior o tienes otra duda?"
        return ""
    
    # 🧠 Retrieve conversation history
    if channel == "flow":
        history=[]
    else:
        history = await session_memory.get_session(session_id)

    lang = detect_language(user_question)
    
    if lang not in constants.MAP_ALLOWED_LANG:
        return "Lo siento, solo puedo comunicarme en inglés, español, ruso y catalán."
    
    prompt_user_lang = constants.MAP_ALLOWED_LANG[lang]
    rag_query = await translate_text(
        text=user_question,
        from_lang=lang,
        to_lang='es'
    )

    # Building the initial context
    base_prompt = get_base_prompt_by_channel(channel)
    system_prompt = base_prompt.format(original_lang=prompt_user_lang)
    
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
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
        print("============= LLAMANDO DE FUNCIONES ============================")
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
                elif function_name == "save_user":
                    function_response = azure_tools.save_user(
                        name=function_args.get("name"),
                        email=function_args.get("email"),
                    )
                elif function_name == "procedures_and_treatments_price_list":
                    function_response = azure_tools.procedures_and_treatments_price_list(
                        name_surgery_or_treatment=function_args.get("name_surgery_or_treatment"),
                    )
                    print(f"==========🔹 Respuesta de listado de precios:", function_response)
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

    # 🚦 Avoid tool call loops: force textual response
    final_response = await make_completion(messages, max_toks, force_text=True)
    final_message = final_response.choices[0].message
        
    clean_content = remove_doc_refs(final_message.content)
    final_answer = clean_content

    if lang != "es":
        final_answer = await translate_text(
            text=clean_content,
            from_lang="es",
            to_lang=lang
        )

    if channel != "flow":
        history.append({
            "role": "assistant",
            "content": final_answer
        })

        # keep only the last N messages
        if len(history) > MAX_HISTORY:
            history = history[-MAX_HISTORY:]

        await session_memory.connect()
        await session_memory.save_session(session_id, history)

    return final_answer
