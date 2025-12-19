import logging

logger = logging.getLogger(__name__)

FALLBACK_MESSAGE = (
    "⚠️ Your request could not be processed at this time. " 
    "Please try again."
)

async def process_zoho_message(
    *,
    zoho_client,
    request_id: str,
    session_id: str,
    user_question: str,
    rag_runner,
):
    logger.info(
        "Processing Zoho message",
        extra={
            "request_id": request_id,
            "session_id": session_id,
        },
    )

    # 1) Send progress
    await zoho_client.send_progress_update(request_id=request_id)

    # 2) Generate answer (RAG)
    try:
        answer = await rag_runner(session_id, user_question)
    except Exception:
        logger.exception("RAG failed", extra={"request_id": request_id})
    
        # 3) Send final response
        await zoho_client.send_final_response(
            request_id=request_id,
            answer_text=FALLBACK_MESSAGE,
        )
        return
     
    await zoho_client.send_final_response(
        request_id=request_id,
        answer_text=answer,
    )

    logger.info(
        "Zoho response completed",
        extra={"request_id": request_id},
    )
