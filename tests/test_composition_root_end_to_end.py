import uuid

import pytest

from app.adapters.outbound.redis.redis_conversation_history_adapter import (
    RedisConversationHistoryAdapter,
)
from app.composition_root import build_process_incoming_message

REDIS_URL = "redis://127.0.0.1:6379"


class FakeChatPlatform:
    def __init__(self):
        self.progress_calls = []
        self.final_calls = []

    async def send_progress_update(self, request_id):
        self.progress_calls.append(request_id)

    async def send_final_response(self, request_id, answer_text):
        self.final_calls.append((request_id, answer_text))


@pytest.fixture(autouse=True)
async def cleanup_redis():
    yield
    adapter = RedisConversationHistoryAdapter(redis_url=REDIS_URL)
    redis = await adapter._client()
    await redis.flushdb()


async def test_process_incoming_message_wired_end_to_end_with_real_redis_and_tenant_config():
    """Only Zoho (network) and the RAG engine (real Azure OpenAI call, needs
    pyodbc locally) are faked. Tenant config (YAML file) and conversation
    history (real local Redis) are real, to prove the whole assembly -- and
    specifically the history-key fix from the ConversationEnginePort work --
    actually works together, not just each piece in isolation."""
    session_id = str(uuid.uuid4())
    chat_platform = FakeChatPlatform()
    captured_calls = []

    async def fake_rag_runner(**kwargs):
        captured_calls.append(kwargs)
        return f"respuesta {len(captured_calls)}"

    class UnusedLookupProcedurePrice:
        async def execute(self, tenant_id, name_surgery_or_treatment):
            raise AssertionError("fake_rag_runner never calls tool_overrides, this shouldn't run")

    async def fake_get_lookup_procedure_price(tenant_id):
        return UnusedLookupProcedurePrice()

    use_case = await build_process_incoming_message(
        "agb",
        chat_platform=chat_platform,
        rag_runner=fake_rag_runner,
        get_lookup_procedure_price=fake_get_lookup_procedure_price,
    )

    await use_case.execute(
        tenant_id="agb",
        request_id="req-1",
        session_id=session_id,
        user_question="hola",
        channel="website",
    )

    assert captured_calls[0]["history"] == []
    assert chat_platform.progress_calls == ["req-1"]
    assert chat_platform.final_calls[-1] == ("req-1", "respuesta 1")

    # Segundo turno: el historial debe venir de verdad desde Redis, con el
    # turno anterior -- esto es justo lo que se rompía antes del fix de
    # ConversationEnginePort (claves distintas para leer y escribir).
    await use_case.execute(
        tenant_id="agb",
        request_id="req-2",
        session_id=session_id,
        user_question="cuanto cuesta la rinoplastia",
        channel="website",
    )

    assert captured_calls[1]["history"] == [
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "respuesta 1"},
    ]
    assert chat_platform.final_calls[-1] == ("req-2", "respuesta 2")
