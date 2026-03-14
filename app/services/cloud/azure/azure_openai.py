import os
import json

from app.core import constants
from app.core.logging_config import logger

from app.services.cloud.azure import azure_tools
from app.services.cloud.azure.client import get_azure_openai_client
from app.services.cache.session_memory import SessionMemoryRedis

from app.core.utils.language_detector import resolve_language
from app.core.utils.text_cleaner import remove_doc_refs
from app.core.utils import rag_validator

session_memory = SessionMemoryRedis()
MAX_HISTORY = 6

async def run_conversation_with_rag(session_id: str, user_question: str, channel: str="website"):
    """
    Execute a conversation with Azure OpenAI using RAG + parallel function calls.
    Compatible with the function calling pattern documented by Azure.
    """
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME_MAIN")
    client = get_azure_openai_client()

    # 🧠 Retrieve conversation history
    history = await session_memory.get_session(session_id)

    # 🌍 Resolve language (solo si no es CONTINUE_TOKEN)
    if user_question != constants.CONTINUE_TOKEN:
        lang = resolve_language(user_question)
    else:
        # Si es __CONTINUE__, mantener idioma actual
        lang = "es"

    logger.info(f"🌍 Idioma final de sesión: {lang}")

    # Building the initial context
    if channel == "website":
        print(f"============ CHANNEL: {channel}")
        system_prompt = constants.WEBSITE_ASSISTANT_PROMPT.strip()
    elif channel == "whatsapp":
        print(f"============ CHANNEL: {channel}")
        system_prompt = constants.WHATSAPP_ASSISTANT_PROMPT.strip()
    
    system_prompt = (
        f"REGLA CRITICA DE IDIOMA:\n"
        f"Debes responder exclusivamente en el idioma: {lang}.\n"
        f"No utilices otro idioma.\n"
        f"No expliques el idioma utilizado.\n\n"
        f"{system_prompt}"
    )

    messages = [{"role": "system", "content": system_prompt}]

    messages.extend(history)

    if user_question != constants.CONTINUE_TOKEN:
        messages.append({"role": "user", "content": user_question})

    question_length = len(user_question) if user_question else 0
    max_toks = (
        constants.OPENAI_MAX_TOKENS
        if question_length > 200
        else int(constants.OPENAI_MAX_TOKENS / 3)
    )
    print(f"========= ultimo paso antes de llamar a make_completions")
    async def make_completion(messages, max_toks, force_text=False):
        """
        Make a call to Azure OpenAI ChatCompletion.
        If `force_text=True`, force tool_choice='none' to prevent further tool calls.
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
                            "authentication": {
                                "type": "api_key",
                                "key": os.environ["AZURE_AI_SEARCH_API_KEY"],
                            },
                            "semantic_configuration": "rag-unstructured-data-semantic-configuration",
                            "fields_mapping": {
                                "content_fields": ["chunk"],
                                "title_field": "title"
                            },
                            "embedding_dependency": {
                                "type": "deployment_name",
                                "deployment_name": os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
                            },
                            "in_scope": True
                        },
                    },
                ]
            },
        )

    # 🌀 First call with retry
    response = await make_completion(messages, max_toks)
    response_message = response.choices[0].message


    print(f"============ response: ", response)
    print(f"============ response messages: ", response_message)

    # 🚀 Parallel call control (parallel tool calls)
    if response_message.tool_calls:
        # print("============= HAY LLAMADO DE FUNCIONES ============================")
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
                    print(f"==========🔹 Response from {function_name}:", function_response)
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
        logger.info("ℹ️ No tool calls were detected in the initial response.")
        messages.append({
            "role": response_message.role,
            "content": response_message.content or "",
        })

    # 🚦 Avoid tool call loops: force textual response
    final_response = await make_completion(messages, max_toks, force_text=True)
    final_message = final_response.choices[0].message
        
    # _, citations_count = rag_validator.extract_rag_answer(final_response)
    # print("========= Numero de citaciones: ", citations_count)
    # if not final_message or citations_count==0:
    #     logger.warning("⚠️ No se recuperaron documentos, se usará mensaje por defecto.")
    #     clean_content = "La informacion solicitada no se encuentra en los documentos de nuestra clinica. "
    # else:
    #     # Mantener tu limpieza normal de referencias
    clean_content = remove_doc_refs(final_message.content)

    # 💾 Save conversation in Redis (only the last N messages)
    if user_question != constants.CONTINUE_TOKEN:
        history.extend([
            {"role": "user", "content": user_question},
            {"role": "assistant", "content": clean_content}
        ])
    else:
        # Solo guardar la respuesta del assistant
        history.append({
            "role": "assistant",
            "content": clean_content
        })

    # keep only the last N messages
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]

    await session_memory.connect()
    await session_memory.save_session(session_id, history)

    return clean_content
