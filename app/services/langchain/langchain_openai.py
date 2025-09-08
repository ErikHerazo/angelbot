import os
import dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser


dotenv.load_dotenv()

prompt = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(
        """
Eres un asistente virtual de la clínica Antiaging Group Barcelona. 
Tu función es responder preguntas de clientes y pacientes utilizando toda la información disponible sobre la clínica, incluyendo pero no limitado a:
- Procedimientos y tratamientos.
- Precios de servicios y paquetes.
- Información sobre los médicos y especialistas.
- Horarios de atención.
- Políticas, recomendaciones.
- Servicios adicionales y cualquier otro dato relevante de la clínica.

Debes responder de manera profesional, clara y con un tono amable y cercano. 
No incluyas referencias ni nombres de documentos en tus respuestas. 
Responde en el mismo idioma en que se formula la pregunta.
Concéntrate únicamente en dar respuestas útiles, directas y comprensibles para los pacientes y clientes, usando toda la información disponible en los documentos.
"""
    ),
    HumanMessagePromptTemplate.from_template("{input}")
])

async def query_langchain_with_search(user_question: str) -> str:
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")

    llm = AzureChatOpenAI(
        azure_deployment=deployment,
        api_version="2025-01-01-preview",
        temperature=0.0,
        max_tokens=1024,
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
                        "query_type": "semantic",
                        "semantic_configuration": "default",
                        "top_n_documents": 5,
                        "in_scope": True,
                        "fields_mapping": {
                            "content_fields": ["content"],
                            "title_field": "title"
                        }
                    }
                }
            ],
        },
        timeout=None,
        max_retries=2,
    )

    chain = prompt | llm | StrOutputParser()

    response = await chain.ainvoke(
        {
            "input_language": "auto",
            "output_language": "auto",
            "input": user_question,
        }
    )

    return response
