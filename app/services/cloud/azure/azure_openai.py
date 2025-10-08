import os
from app.services.cloud.azure.client import get_azure_openai_client
from app.core import constants

def run_conversation_with_rag(user_question: str):
    # 1️⃣ Mensajes que se envían al modelo
    messages = [
        {"role": "system", "content": constants.ASSISTANT_PROMPT},
        {"role": "user", "content": user_question}
    ]

    # 2️⃣ Llamada al modelo con RAG
    client = get_azure_openai_client()
    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),  # deployment del modelo
        messages=messages,
        temperature=0,       # sin creatividad, respuestas directas
        max_tokens=500,      # límite de tokens
        extra_body={         # parámetros RAG
            "data_sources": [
                {
                    "type": "azure_search",  # usamos Cognitive Search
                    "parameters": {
                        "endpoint": os.environ["AZURE_AI_SEARCH_ENDPOINT"],  # URL del servicio de búsqueda
                        "index_name": os.environ["AZURE_AI_SEARCH_INDEX"],   # índice donde están los documentos
                        "query_type": "vector_semantic_hybrid",                     # búsqueda semántica con vectores
                        "semantic_configuration": "default",               # configuración semántica del índice
                        "fields_mapping": {
                            "content_fields": ["content"],                 # campo del contenido del documento
                            "title_field": "title"                        # campo del título
                        },
                        "authentication": {                               
                            "type": "api_key",
                            "key": os.environ["AZURE_AI_SEARCH_API_KEY"]
                        },
                        "embedding_dependency": {                           # cómo generar embeddings
                            "type": "deployment_name",
                            "deployment_name": os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"]
                        }
                    }
                }
            ]
        }
    )

    # 3️⃣ Devolvemos la respuesta y el contexto (citas)
    resp = response.choices[0].message
    return resp.content, resp.context
