import logging

logger = logging.getLogger(__name__)


async def process_zoho_flow_lead(
    *,
    request_id: str,
    session_id: str,
    lead_data: dict,
    rag_runner=None,
):
    if rag_runner is None:
        from app.services.cloud.azure.azure_openai import run_conversation_with_rag
        rag_runner = run_conversation_with_rag
    try:
        # 1. Extraer campos
        first_name = lead_data.get("first_name", "")
        last_name = lead_data.get("last_name", "")
        lang = lead_data.get("lang", "es")

        motivo = lead_data.get("motivo_de_la_cita")
        interest = lead_data.get("interes_formulario")

        # 2. Intent principal
        intent_parts = [motivo, interest]
        intent = " | ".join(filter(None, intent_parts))

        if not intent:
            return {
                "success": False,
                "response": None,
                "intent": None,
                "entities": {
                    "first_name": first_name,
                    "last_name": last_name
                },
                "meta": {
                    "request_id": request_id,
                    "session_id": session_id,
                    "source": "zoho_flow"
                },
                "error": {
                    "code": "NO_INTENT",
                    "message": "No intent was found in the form"
                }
            }
        
        # 3. SOLO contexto, no instrucciones
        user_question = (
            f"Motivo de consulta del paciente: {intent}. "
            f"Idioma: {lang}."
        )

        # 4. Ejecutar RAG (aquí vive el prompt real)
        answer = await rag_runner(
            session_id=session_id,
            user_question=user_question,
            channel="flow",
            visitor_language=lang,
        )

        # 5. Retornar a Zoho Flow
        return {
            "success": True,
            "response": answer,
            "intent": {
                "reason": motivo,
                "interest": interest
            },
            "entities":{
                "first_name": first_name,
                "last_name": last_name,
                "lang": lang
            },
            "meta": {
                "request_id": request_id,
                "session_id": session_id,
                "source": "flow"
            },
            "error": None
        }

    except Exception:
        logger.exception(
            "Zoho Flow processing failed",
            extra={"request_id": request_id},
        )

        return {
            "success": False,
            "response": None,
            "intent": None,
            "entities": {},
            "meta": {
                "request_id": request_id,
                "session_id": session_id,
                "source": "zoho_flow"
            },
            "error": {
                "code": "PROCESSING_ERROR",
                "message": "An error occurred while processing the request."
            }
        }
    