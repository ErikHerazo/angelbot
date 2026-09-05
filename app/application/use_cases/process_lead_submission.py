import logging
from dataclasses import dataclass
from typing import Optional

from app.application.ports.conversation_engine_port import ConversationEnginePort
from app.domain.value_objects.lead_submission import LeadSubmission

logger = logging.getLogger(__name__)


@dataclass
class LeadSubmissionResult:
    success: bool
    answer: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class ProcessLeadSubmission:
    def __init__(self, *, conversation_engine: ConversationEnginePort):
        self._conversation_engine = conversation_engine

    async def execute(
        self,
        *,
        tenant_id: str,
        session_id: str,
        lead: LeadSubmission,
    ) -> LeadSubmissionResult:
        if not lead.combined_intent:
            return LeadSubmissionResult(
                success=False,
                error_code="NO_INTENT",
                error_message="No intent was found in the form",
            )

        try:
            answer = await self._conversation_engine.generate_reply(
                tenant_id=tenant_id,
                session_id=session_id,
                user_question=lead.build_synthetic_question(),
                channel="flow",
                visitor_language=lead.lang,
            )
        except Exception:
            logger.exception("Zoho Flow processing failed", extra={"session_id": session_id})
            return LeadSubmissionResult(
                success=False,
                error_code="PROCESSING_ERROR",
                error_message="An error occurred while processing the request.",
            )

        return LeadSubmissionResult(success=True, answer=answer)
