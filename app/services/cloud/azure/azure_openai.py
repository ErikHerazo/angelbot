import os
import openai
import dotenv
from app.core import constants
# from app.services.langchain import tools


dotenv.load_dotenv()

def query_azure_openai_with_search(user_question: str) -> str:
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")

    client = openai.AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=constants.AZURE_OPENAI_API_VERSION,
    )

    # ======================== Functions ==================================
    import holidays
    from zoneinfo import ZoneInfo
    from datetime import datetime, time
    from langchain_core.tools import tool

    # Obtener hora actual de España
    def get_current_time_spain() -> datetime:
        madrid_tz = ZoneInfo("Europe/Madrid")
        return datetime.now(madrid_tz)

    @tool
    async def is_customer_service_available(input: str = "") -> bool:
        """
        Indica si el personal de servicio al cliente está disponible actualmente en España.
        
        Retorna True si estamos dentro del horario de atención, False si no.
        Horarios de atención:
        - Lunes a viernes: 08:00-12:00 y 14:00-18:00
        - Sábado: 08:00-12:00
        - Domingos y festivos: no disponible
        """
        now = get_current_time_spain()
        dia_semana = now.weekday()  # Lunes=0, Domingo=6

        # Lista de festivos en España
        es_holidays = holidays.Spain(years=now.year)

        # Si es domingo o festivo
        if dia_semana == 6 or now.date() in es_holidays:
            return False

        # Horario de lunes a viernes
        if 0 <= dia_semana <= 4:
            if time(8,0) <= now.time() <= time(12,0) or time(14,0) <= now.time() <= time(18,0):
                return True

        # Horario sábado
        if dia_semana == 5:
            if time(8,0) <= now.time() <= time(12,0):
                return True

        return False

    # =================== Define the functions for the model ==============================
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_current_weather",
                "description": "Get the current weather in a given location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city name, e.g. San Francisco",
                        },
                        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                    },
                    "required": ["location"],
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_current_time",
                "description": "Get the current time in a given location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city name, e.g. San Francisco",
                        },
                    },
                    "required": ["location"],
                },
            }
        }
    ]

    completion = client.chat.completions.create(
        model=deployment,
        messages=[{"role": "user", "content": user_question}],
        max_tokens=1024,
        temperature=0.0,
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
                            "title_field": "title",
                        },
                    },
                }
            ],
        },
    )

    return completion.choices[0].message.content
