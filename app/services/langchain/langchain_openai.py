import os
import dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langdetect import detect


dotenv.load_dotenv()

LANG_MAP = {
  "en": "English",
  "it": "Italiano",
  "af": "Afrikaans",
  "es": "Español",
  "de": "Deutsch",
  "fr": "Français",
  "id": "Bahasa Indonesia",
  "ru": "Русский",
  "pl": "Polski",
  "uk": "Українська",
  "el": "Ελληνικά",
  "lv": "Latviešu",
  "zh": "中文",
  "ar": "العربية",
  "tr": "Türkçe",
  "ja": "日本語",
  "sw": "Kiswahili",
  "cy": "Cymraeg",
  "ko": "한국어",
  "is": "Íslenska",
  "bn": "বাংলা",
  "ur": "اردو",
  "ne": "नेपाली",
  "th": "ไทย",
  "pa": "ਪੰਜਾਬੀ",
  "mr": "मराठी",
  "te": "తెలుగు"
}


async def query_langchain_with_search(user_question: str) -> str:
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")

    # Detectar idioma y mapear a nombre completo
    detected_lang = detect(user_question)
    user_lang = LANG_MAP.get(detected_lang, "the same language as the question")
    
    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(
            """
            Eres un asistente virtual de la clínica Antiaging Group Barcelona.
            Debes responder SIEMPRE en {language}, que es el idioma en que se hizo la pregunta.
            
            Tu función es responder preguntas de clientes y pacientes utilizando toda la información disponible sobre la clínica, incluyendo pero no limitado a:
            - Procedimientos y tratamientos.
            - Precios de servicios y paquetes.
            - Información sobre los médicos y especialistas.
            - Horarios de atención.
            - Políticas, recomendaciones.
            - Servicios adicionales y cualquier otro dato relevante de la clínica.

            Reglas:
            - No incluyas referencias ni nombres de documentos en tus respuestas. 
            - Responde de manera profesional, clara y con un tono amable y cercano.
            - Concéntrate únicamente en dar respuestas útiles, directas y comprensibles.
            """
        ),
        HumanMessagePromptTemplate.from_template("{input}")
    ])

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

    response = await chain.ainvoke({
        "input": user_question,
        "language": user_lang
    })

    return response
