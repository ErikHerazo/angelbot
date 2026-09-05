from typing import Optional

from app.application.use_cases.acknowledge_file_upload import AcknowledgeFileUpload


class ZohoFileUploadAckHandler:
    """Formats AcknowledgeFileUpload's result as a Zoho SalesIQ webhook
    reply -- same response shape as the legacy message_handler.py file-upload
    branch (note: `"type": "text"` here, unlike ZohoGreetingTriggerHandler's
    envelope which omits `type` -- preserved as-is, not homogenized, to
    match exactly what each legacy branch actually sent)."""

    def __init__(self, *, use_case: AcknowledgeFileUpload, tenant_id: str):
        self._use_case = use_case
        self._tenant_id = tenant_id

    async def handle(self, *, session_id: str, visitor_language: Optional[str] = None) -> dict:
        message = await self._use_case.execute(
            tenant_id=self._tenant_id,
            session_id=session_id,
            visitor_language=visitor_language,
        )

        return {
            "action": "reply",
            "replies": [{"type": "text", "text": message}],
        }
