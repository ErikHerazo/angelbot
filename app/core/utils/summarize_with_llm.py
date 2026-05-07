import os
import logging

from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_openai import AzureChatOpenAI

from app.core import constants
from app.core.utils.count_visible_chars import count_visible_chars
from app.core.utils.enforce_output_language import enforce_same_language
from app.services.cloud.azure.azure_language_detector import detect_language_azure


load_dotenv()

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
char_limit = constants.INSTAGRAM_CHARACTER_LIMIT

AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_RESUMEN_KEY")
AZURE_OPENAI_ENDPOINT = constants.AZURE_OPENAI_SUMMARY_ENDPOINT
AZURE_OPENAI_DEPLOYMENT_NAME = constants.AZURE_OPENAI_SUMMARY_DEPLOYMENT_NAME
AZURE_OPENAI_API_VERSION = constants.AZURE_OPENAI_SUMMARY_VERSION


llm = AzureChatOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_API_KEY,
    azure_deployment=AZURE_OPENAI_DEPLOYMENT_NAME,
    api_version=AZURE_OPENAI_API_VERSION,
    temperature=0,
    max_retries=2,
)

# 🔥 PRIMER RESUMEN
initial_template = PromptTemplate(
    input_variables=[
        "input_text",
        "user_question",
        "char_limit",
        "lang",
    ],
    template="""
    Eres un especialista en resumir textos extensos de manera precisa y eficiente, tu tarea es analizar textos muy largos
    y extraer únicamente la información más importante y relevante para responder la pregunta del usuario.

    OBJETIVO:
    - Responder la pregunta usando SOLO información relevante del texto.
    - Extraer datos clave, contexto útil y detalles importantes.
    - Eliminar información irrelevante o repetitiva.
    - Priorizar contenido crítico relacionado directamente con la pregunta.

    REGLAS OBLIGATORIAS:
    - IMPORTANTE: Genera tu respuesta en el idioma {lang}.
    - Nunca traduzcas el texto de entrada(pregunta del usuario) a ningun idioma en especifico.
    - La cantidad maxima de caracteres de tu respuesta final debe ser SIEMPRE <={char_limit} incluyendo espacios.
    - Responde de manera clara, útil, directa y sin redundancias.
    - No expliques el proceso.
    - No inventes información.
    - No uses markdown, ni listas innecesarias, ni saltos de linea innecesaria.
    - Si debes sacrificar detalles para cumplir el límite, conserva lo más relevante para responder la pregunta.
    - Termina siempre con un afrase invitando a obtener mas informacion, si el usuario lo desea.

    Pregunta del usuario:
    {user_question}

    Texto:
    {input_text}

    Respuesta:
    """
)

# 🔥 REFINAMIENTO FUERTE
refine_template = PromptTemplate(
    input_variables=[
        "previous_answer",
        "current_length",
        "char_limit",
        "current_length_minus_limit",
        "lang",
    ],
    template="""
    Eres un especialista en resumir textos extensos de manera precisa y eficiente, tu tarea es analizar textos muy largos
    y extraer únicamente la información más importante y relevante. Pero desafortunadamente tu resumen anterior 
    estaba DEMASIADO LARGO y no cumplio con las reglas obligatorias establecidas, Por favor OPTIMIZA nuevamente 
    la respuesta anterior; con cada una de las reglas obligatorias establecidas.

    REGLAS OBLIGATORIAS:
    - IMPORTANTE: Genera tu nueva respuesta en el idioma {lang}.
    - Nunca traduzcas el texto de entrada(respuesta anterior) a ningun idioma en especifico.
    - La cantidad maxima de caracteres de tu respuesta final debe ser SIEMPRE <={char_limit} incluyendo espacios.
    - El texto de entrada(respuesta anterior) tiene {current_length} caracteres, debes reducir MINIMO {current_length_minus_limit} caracteres.
    - Conserva SOLO la información más importante.
    - Elimina detalles secundarios si es necesario para cumplir con el limite establecido.
    - No expliques el proceso.
    - No agregues información nueva o inventada.
    - No uses markdown, ni listas innecesarias, ni saltos de linea innecesaria.

    Texto actual:
    {previous_answer}

    Nueva respuesta optimizada:
    """
)

initial_chain = initial_template | llm
refine_chain = refine_template | llm


async def generate_compact_answer(
    answer: str,
    user_question: str,
) -> str:
    """
    Optimiza respuestas largas iterativamente hasta cumplir
    el límite de caracteres permitido.
    """
    lang = await detect_language_azure(user_question)
    logger.info(
        f"Executing summary deployment: "
        f"{AZURE_OPENAI_DEPLOYMENT_NAME}"
    )

    try:

        # 🔥 PRIMERA OPTIMIZACIÓN
        response = await initial_chain.ainvoke({
            "input_text": answer,
            "user_question": user_question,
            "char_limit": char_limit,
            "lang": lang,
        })

        optimized = response.content.strip()

        # 🔥 LIMPIEZA
        optimized = optimized.replace("**", "").replace("\n\n", "\n").strip()
        
        # 🔥 VALIDACIÓN DE IDIOMA (input = answer original del RAG)
        optimized = await enforce_same_language(
            input_text=answer,       # salida RAG
            output_text=optimized    # resumen inicial
        )

        current_length = count_visible_chars(optimized)

        logger.info(
            f"Initial optimized length: {current_length}"
        )

        retries = 0

        # 🔥 LOOP DE REFINAMIENTO
        while current_length > char_limit and retries < MAX_RETRIES:

            logger.warning(
                f"Summary exceeded limit "
                f"({current_length}/{char_limit}). "
                f"Refining attempt {retries + 1}"
            )

            previous_input_text = optimized

            refine_response = await refine_chain.ainvoke({
                "previous_answer": optimized,
                "current_length": current_length,
                "char_limit": char_limit,
                "current_length_minus_limit": (current_length - char_limit),
                "lang": lang,
            })

            optimized = refine_response.content.strip()

            # 🔥 LIMPIEZA
            optimized = optimized.replace("**", "").replace("\n\n", "\n").strip()

            # 🔥 VALIDACIÓN DE IDIOMA (input = resultado previo del pipeline)
            optimized = await enforce_same_language(
                input_text=previous_input_text,
                output_text=optimized
            )

            current_length = count_visible_chars(optimized)

            logger.info(
                f"Refined summary length: {current_length}"
            )

            retries += 1

        return optimized

    except Exception:
        logger.exception("Summary optimization failed")

        # fallback seguro
        return answer
    