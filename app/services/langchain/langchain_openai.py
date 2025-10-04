import os
import dotenv
import logging
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import MessagesPlaceholder
from app.services.langchain.tools import is_customer_service_available 
from app.core import constants 


dotenv.load_dotenv()

# =================================================================
# 💡 CORRECCIÓN 1: Configurar el logger de LangChain a DEBUG
# Esto es esencial para ver la comunicación interna del LLM y el Agente.
# =================================================================
logging.basicConfig(level=logging.INFO)
# Establecer el nivel DEBUG para las librerías de LangChain
logging.getLogger("langchain").setLevel(logging.DEBUG) 
logging.getLogger("langchain_core").setLevel(logging.DEBUG) 
logger = logging.getLogger(__name__)

# 🛠️ Lista de herramientas para el LLM
TOOLS = [is_customer_service_available]


async def query_langchain_with_search(user_question: str) -> str:
    # 1. Configuración y validación del entorno (Se mantiene)
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
    if not deployment:
        raise ValueError("Falta AZURE_OPENAI_DEPLOYMENT_NAME en variables de entorno")
    
    # 2. Inicialización de los LLM (Se mantiene la separación)
    
    # --- LLM para RAG (llm_rag): CON extra_body para Azure Search ---
    llm_agent = AzureChatOpenAI(
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
    # llm_agent = AzureChatOpenAI(
    #     azure_deployment=deployment,
    #     api_version=constants.AZURE_OPENAI_API_VERSION,
    #     temperature=constants.OPENAI_TEMPERATURE,
    #     max_tokens=constants.OPENAI_MAX_TOKENS,
    #     timeout=constants.OPENAI_TIMEOUT,
    #     max_retries=constants.OPENAI_MAX_RETRIES,
    # )
    
    # 3. Configuración del Prompt (Se mantiene con MessagesPlaceholder)
    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(constants.ASSISTANT_PROMPT),
        HumanMessagePromptTemplate.from_template("{input}"), 
        MessagesPlaceholder("agent_scratchpad"), 
    ])

    # 4. CREACIÓN DEL AGENTE Y EL EXECUTOR
    agent = create_tool_calling_agent(llm_agent, TOOLS, prompt)
    
    # 5. Configuración del Executor
    agent_executor = AgentExecutor(
        agent=agent, 
        tools=TOOLS, 
        # 💡 CORRECCIÓN 2: Volver a poner verbose=True para ver la traza de la cadena
        verbose=True 
    )
    
    # 6. Invocación Asíncrona
    response_dict = await agent_executor.ainvoke({"input": user_question})
    
    return response_dict["output"]