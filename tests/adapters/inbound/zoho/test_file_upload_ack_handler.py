from app.adapters.inbound.zoho.file_upload_ack_handler import ZohoFileUploadAckHandler


class FakeUseCase:
    def __init__(self, message):
        self._message = message
        self.calls = []

    async def execute(self, *, tenant_id, session_id, visitor_language=None):
        self.calls.append((tenant_id, session_id, visitor_language))
        return self._message


async def test_formats_ack_as_zoho_reply_payload():
    handler = ZohoFileUploadAckHandler(use_case=FakeUseCase("listo"), tenant_id="agb")

    result = await handler.handle(session_id="sess-1", visitor_language="es")

    assert result == {"action": "reply", "replies": [{"type": "text", "text": "listo"}]}
