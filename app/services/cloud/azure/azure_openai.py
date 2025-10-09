import os
import json
from app.core import constants
from app.services.cloud.azure.client import get_azure_openai_client
from app.services.cloud.azure import azure_tools


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
        tools=azure_tools.tools,
        tool_choice="auto",
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
    response_message = response.choices[0].message
    # Antes de agregar al mensaje
    messages.append({
        "role": response_message.role,
        "content": response_message.content or "",  # nunca None
    })

    print("Model's response:")  
    print(response_message)

    # Handle function calls
    if response_message.tool_calls:
        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            print(f"Function call: {function_name}")
            print(f"Function arguments: {function_args}")
            if function_name == "is_customer_service_available":
                function_response = azure_tools.is_customer_service_available()
            elif function_name == "save_user":
                function_response = azure_tools.save_user(
                    name=function_args.get("name"),
                    email=function_args.get("email"),
                )
            else:
                function_response = json.dumps({"error": "Unknown function"})
            
            messages.append({
                "role": "tool",
                "content": str(function_response),
            })
    else:
        print("No tool calls were made by the model.")  

    final_response = client.chat.completions.create(
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

    response_message = final_response.choices[0].message.content
    return response_message
