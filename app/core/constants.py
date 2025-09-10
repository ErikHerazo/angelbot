# Language codes mapped to full names.
# Used to make sure the assistant replies in the same language as the user
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

# Base system prompt for the assistant.
# {language} is replaced with the detected user language.
ASSISTANT_PROMPT = """
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

# Azure OpenAI settings
AZURE_OPENAI_API_VERSION = "2025-01-01-preview"
OPENAI_TEMPERATURE = 0.0
OPENAI_MAX_TOKENS = 1024
OPENAI_TIMEOUT = None
OPENAI_MAX_RETRIES = 2