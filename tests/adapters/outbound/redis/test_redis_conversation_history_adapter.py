import uuid

import pytest

from app.adapters.outbound.redis.redis_conversation_history_adapter import (
    RedisConversationHistoryAdapter,
)

REDIS_URL = "redis://127.0.0.1:6379"


@pytest.fixture
async def adapter():
    instance = RedisConversationHistoryAdapter(redis_url=REDIS_URL, ttl_seconds=60)
    yield instance
    redis = await instance._client()
    await redis.flushdb()


async def test_get_history_is_empty_for_unknown_session(adapter):
    history = await adapter.get_history("agb", str(uuid.uuid4()))

    assert history == []


async def test_append_turn_then_get_history_round_trips(adapter):
    session_id = str(uuid.uuid4())

    await adapter.append_turn(
        tenant_id="agb",
        session_id=session_id,
        user_message="hola",
        assistant_message="hola, en que puedo ayudarte?",
        max_history=6,
    )

    history = await adapter.get_history("agb", session_id)

    assert history == [
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "hola, en que puedo ayudarte?"},
    ]


async def test_append_turn_truncates_to_max_history(adapter):
    session_id = str(uuid.uuid4())

    for i in range(4):
        await adapter.append_turn(
            tenant_id="agb",
            session_id=session_id,
            user_message=f"pregunta {i}",
            assistant_message=f"respuesta {i}",
            max_history=4,
        )

    history = await adapter.get_history("agb", session_id)

    assert len(history) == 4
    assert history[-1] == {"role": "assistant", "content": "respuesta 3"}


async def test_same_session_id_is_isolated_per_tenant(adapter):
    session_id = str(uuid.uuid4())

    await adapter.append_turn(
        tenant_id="agb",
        session_id=session_id,
        user_message="mensaje de agb",
        assistant_message="respuesta de agb",
        max_history=6,
    )

    other_tenant_history = await adapter.get_history("clienteb", session_id)

    assert other_tenant_history == []
