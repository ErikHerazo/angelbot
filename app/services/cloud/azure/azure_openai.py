import os
import json

from app.core import constants
from app.core.logging_config import logger

from app.services.cloud.azure import azure_tools
from app.services.cloud.azure.client import get_azure_openai_client
from app.services.cache.session_memory import SessionMemoryRedis

from app.core.utils.language_detector import detect_language
from app.core.utils.text_cleaner import remove_doc_refs
from app.core.utils.translate_text import translate_text
from app.services.cloud.azure.azure_search.query_service import AzureSearchQueryService

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
    
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME_MAIN")
    client = get_azure_openai_client()
    search_service = AzureSearchQueryService()

    # 🧠 Retrieve conversation history
    if channel == "flow":
        history=[]
    else:
        history = await session_memory.get_session(session_id)

    lang = detect_language(user_question)

    if lang is None:
        return "Lo siento, solo puedo comunicarme en inglés, español, ruso y catalán."
    translated_text = await translate_text(text=user_question,from_lang=lang, to_lang='es')
    
    chunks = await search_service.search_unstructured(translated_text)
    if not chunks:
        context = "No se encontró información relevante en la base de conocimiento."
    else:
        context = "\n\n".join(chunks)[:8000]

    print("========== CONTEXT ==========\n", context[:500])

    # Building the initial context
    if channel == "website":
        print(f"============ CHANNEL: {channel}")
        system_prompt = constants.WEBSITE_ASSISTANT_PROMPT.strip()
    elif channel == "whatsapp":
        print(f"============ CHANNEL: {channel}")
        system_prompt = constants.WHATSAPP_ASSISTANT_PROMPT.strip()
    elif channel == "instagram":
        print(f"============ CHANNEL: {channel}")
        system_prompt = constants.INSTAGRAM_ASSISTANT_PROMPT.strip()
    elif channel == "flow":
        print(f"============ CHANNEL: {channel}")
        system_prompt = constants.FLOW_FORM_ASSISTANT_PROMPT.strip()
    else:
        print(f"============ CHANNEL: {channel}")
        system_prompt = constants.WEBSITE_ASSISTANT_PROMPT.strip()

    system_prompt_with_context = f"""
    {system_prompt}

    Usa el siguiente contexto para responder la pregunta del usuario.
    Si la información no está en el contexto, responde de forma general y aclara que no está en la base de conocimiento.

    Contexto:
    {context}
    """
    messages = [{"role": "system", "content": system_prompt_with_context}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_question})

    question_length = len(user_question) if user_question else 0
    max_toks = (
        constants.OPENAI_MAX_TOKENS
        if question_length > 200
        else int(constants.OPENAI_MAX_TOKENS / 3)
    )
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
        )

    # 🌀 First call with retry
    response = await make_completion(messages, max_toks)
    response_message = response.choices[0].message

    # print(f"============ Respuesta inicial: ", response_message)

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
        # logger.info("ℹ️ No tool calls were detected in the initial response.")
        messages.append({
            "role": response_message.role,
            "content": response_message.content or "",
        })

    # 🚦 Avoid tool call loops: force textual response
    final_response = await make_completion(messages, max_toks, force_text=True)
    final_message = final_response.choices[0].message
        
    clean_content = remove_doc_refs(final_message.content)

    if channel != "flow":
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
    