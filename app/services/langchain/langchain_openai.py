import os
import dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.runnables import RunnablePassthrough
from langchain.prompts import MessagesPlaceholder # Se mantiene la importación corregida

# Importaciones existentes
from app.services.langchain.tools import is_customer_service_available 
from app.core import constants 


dotenv.load_dotenv()

# Configuración básica del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🛠️ Lista de herramientas para el LLM
TOOLS = [is_customer_service_available]


async def query_langchain_with_search(user_question: str) -> str:
    # 1. Configuración y validación del entorno (Se mantiene)
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
    if not deployment:
        raise ValueError("Falta AZURE_OPENAI_DEPLOYMENT_NAME en variables de entorno")
    
    # 2. Inicialización de los LLM (¡CORRECCIÓN CLAVE!)
    
    # --- LLM para RAG (llm_rag): CON extra_body para Azure Search ---
    # Este LLM tiene las capacidades de RAG.
    llm_rag = AzureChatOpenAI(
        azure_deployment=deployment,
        api_version=constants.AZURE_OPENAI_API_VERSION,
        temperature=constants.OPENAI_TEMPERATURE,
        max_tokens=constants.OPENAI_MAX_TOKENS,
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
                        "query_type": "vector_semantic_hybrid",
                        "semantic_configuration": "default",
                        "top_n_documents": 5,
                        "in_scope": True,
                        "fields_mapping": {
                            "content_fields": ["content"],
                            "title_field": "title"
                        },
                        "embedding_dependency": {
                            "type": "deployment_name",
                            "deployment_name": os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"]
                        }
                    }
                }
            ],
        },
        timeout=constants.OPENAI_TIMEOUT,
        max_retries=constants.OPENAI_MAX_RETRIES,
    )

    # --- LLM para el Agente (llm_agent): SIN extra_body ---
    # Este LLM se usa para el razonamiento y Tool Calling, evitando el error 400.
    llm_agent = AzureChatOpenAI(
        azure_deployment=deployment,
        api_version=constants.AZURE_OPENAI_API_VERSION,
        temperature=constants.OPENAI_TEMPERATURE,
        max_tokens=constants.OPENAI_MAX_TOKENS,
        # NO se incluye extra_body aquí
        timeout=constants.OPENAI_TIMEOUT,
        max_retries=constants.OPENAI_MAX_RETRIES,
    )
    
    # 3. Configuración del Prompt (Se mantiene con MessagesPlaceholder)
    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(constants.ASSISTANT_PROMPT),
        HumanMessagePromptTemplate.from_template("{input}"), 
        MessagesPlaceholder("agent_scratchpad"), 
    ])

    # 4. CREACIÓN DEL AGENTE Y EL EXECUTOR
    # Usamos el LLM limpio (llm_agent) para el razonamiento.
    agent = create_tool_calling_agent(llm_agent, TOOLS, prompt)
    
    # 5. EL PROBLEMA DE RAG Y AGENTE
    # Opción A (Recomendada para Tool Calling): Usar el Agente.
    # El LLM para RAG (llm_rag) queda sin usar para evitar el conflicto.
    # Esto funcionará 100% para la llamada a la herramienta, pero las respuestas RAG serán menos precisas.
    agent_executor = AgentExecutor(
        agent=agent, 
        tools=TOOLS, 
        verbose=False
    )
    
    # 6. Invocación Asíncrona
    response_dict = await agent_executor.ainvoke({"input": user_question})
    
    return response_dict["output"]