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
        from app.services.chat.rag.run_conversation import run_conversation_with_rag
        rag_runner = run_conversation_with_rag
    try:
        # 1. Extraer campos
        first_name = lead_data.get("first_name", "")
        last_name = lead_data.get("last_name", "")
        lang = lead_data.get("lang", "es")

        motivo = lead_data.get("motivo_de_la_cita")
        interes = lead_data.get("interes_formulario")

        # 2. Intent principal
        intent_parts = [motivo, interes]
        intent = " | ".join(filter(None, intent_parts))

        if not intent:
            return {
                "status": "error",
                "message": "No intent was found in the form"
            }
        
        logger.info(
            "Processing Zoho Flow lead",
            extra={
                "request_id": request_id,
                "session_id": session_id,
                "intent": intent,
            },
        )

        # 3. SOLO contexto, no instrucciones
        user_question = (
            f"Motivo de consulta del paciente: {intent}. "
            f"Nombre del paciente: {first_name} {last_name}. "
            f"Idioma: {lang}."
        )

        # 4. Ejecutar RAG (aquí vive el prompt real)
        answer = await rag_runner(
            session_id=session_id,
            user_question=user_question,
            channel="flow",
        )

        # 5. Retornar a Zoho Flow
        return {
            "status": "success",
            "response": answer,
            "first_name": first_name,
            "last_name": last_name,
        }

    except Exception:
        logger.exception(
            "Zoho Flow processing failed",
            extra={"request_id": request_id},
        )

        return {
            "status": "error",
            "response": "An error occurred while processing the request."
        }
    