import os
import json
import openai
import dotenv
from app.core import constants
# from app.services.langchain import tools


dotenv.load_dotenv()

base_url = os.environ.get("AZURE_OPENAI_ENDPOINT")
api_key = os.environ.get("AZURE_OPENAI_API_KEY")
deployment_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")

client = openai.AzureOpenAI(
    azure_endpoint=base_url,
    api_key=api_key,
    api_version="2024-11-20"
)

# ======================== Functions ==================================
import holidays
from zoneinfo import ZoneInfo
from datetime import datetime, time


# Obtener hora actual de España
def get_current_time_spain() -> datetime:
    madrid_tz = ZoneInfo("Europe/Madrid")
    return datetime.now(madrid_tz)

# def is_customer_service_available(input: str = "") -> bool:
#     """
#     Indica si el personal de servicio al cliente está disponible actualmente en España.
    
#     Retorna True si estamos dentro del horario de atención, False si no.
#     Horarios de atención:
#     - Lunes a viernes: 08:00-12:00 y 14:00-18:00
#     - Sábado: 08:00-12:00
#     - Domingos y festivos: no disponible
#     """
#     now = get_current_time_spain()
#     dia_semana = now.weekday()  # Lunes=0, Domingo=6

#     # Lista de festivos en España
#     es_holidays = holidays.Spain(years=now.year)

#     # Si es domingo o festivo
#     if dia_semana == 6 or now.date() in es_holidays:
#         return False

#     # Horario de lunes a viernes
#     if 0 <= dia_semana <= 4:
#         if time(8,0) <= now.time() <= time(12,0) or time(14,0) <= now.time() <= time(18,0):
#             return True

#     # Horario sábado
#     if dia_semana == 5:
#         if time(8,0) <= now.time() <= time(12,0):
#             return True

#     return False

def is_customer_service_available(input: str = "") -> bool:
    """
    Indica si el personal de servicio al cliente está disponible actualmente en España.
    
    Retorna True si estamos dentro del horario de atención, False si no.
    Horarios de atención:
    - Lunes a viernes: 08:00-12:00 y 14:00-18:00
    - Sábado: 08:00-12:00
    - Domingos y festivos: no disponible
    """
    return "No hay personal de atencion al cliente disponibles"
# ===============================================================================

def run_conversation(user_question: str) -> str:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "is_customer_service_available",
                "description": "Comprueba si el servicio de atención al cliente está disponible actualmente en España. "
                                "Utilízala cuando el usuario pregunte si puede ser atendido por un asesor, "
                                "si hay soporte disponible, o si el horario de atención está activo. "
                                "Devuelve True si el servicio está disponible en este momento, de lo contrario False.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "input": {
                            "type": "string",
                            "description": (
                                "Texto opcional proporcionado por el usuario. "
                                "Puede incluir su consulta o contexto, aunque no es necesario "
                                "para determinar la disponibilidad del servicio."
                            ),
                        },
                    },
                    "required": [],
                },
            }
        },
    ]

    messages = [{"role": "user", "content": user_question}]

    # First API call: Ask the model to use the function
    response = client.chat.completions.create(
        model=deployment_name,
        messages=messages,
        tools=tools,
        tool_choice="auto",
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
    )

    # Process the model's response
    response_message = response.choices[0].message
    messages.append(response_message)

    print("Model's response:")  
    print(response_message)  

    # Handle function calls
    if response_message.tool_calls:
        for tool_call in response_message.tool_calls:
            if tool_call.function.name == "is_customer_service_available":
                function_args = json.loads(tool_call.function.arguments)
                print(f"Function arguments: {function_args}")  
                time_response = is_customer_service_available(
                    input=function_args.get("input")
                )
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": "get_current_time",
                    "content": str(time_response),
                })
    else:
        print("No tool calls were made by the model.")  

    # Second API call: Get the final response from the model
    final_response = client.chat.completions.create(
        model=deployment_name,
        messages=messages,
    )

    return final_response.choices[0].message.content

# Run the conversation and print the result
print(run_conversation(user_question="necesito hablar con un asesor"))
