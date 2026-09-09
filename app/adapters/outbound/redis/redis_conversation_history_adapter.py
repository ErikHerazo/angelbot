import json

import redis.asyncio as aioredis

from app.core.logging.structured_logger import get_logger

log = get_logger(__name__)


class RedisConversationHistoryAdapter:
    """Implements ConversationHistoryPort. Connection details are injected —
    not read from env vars here — so swapping Redis providers later
    (see agb-redis-migration-planned memory) is a config change, not a rewrite."""

    def __init__(self, *, redis_url: str, ttl_seconds: int = 900):
        self._redis_url = redis_url
        self._ttl_seconds = ttl_seconds
        self._redis = None

    async def _client(self):
        if self._redis is None:
            self._redis = await aioredis.from_url(self._redis_url, decode_responses=True)
        return self._redis

    @staticmethod
    def _key(tenant_id: str, session_id: str) -> str:
        return f"session:{tenant_id}:{session_id}"

    async def get_history(self, tenant_id: str, session_id: str) -> list[dict]:
        with log.operation(tenant_id=tenant_id, session_id=session_id):
            redis = await self._client()
            data = await redis.get(self._key(tenant_id, session_id))
            history = json.loads(data) if data else []
            log.debug("History fetched", turns=len(history))
            return history

    async def append_turn(
        self,
        *,
        tenant_id: str,
        session_id: str,
        user_message: str,
        assistant_message: str,
        max_history: int,
    ) -> None:
        with log.operation(tenant_id=tenant_id, session_id=session_id, max_history=max_history):
            history = await self.get_history(tenant_id, session_id)
            history.append({"role": "user", "content": user_message})
            history.append({"role": "assistant", "content": assistant_message})

            if len(history) > max_history:
                log.debug("Truncating history to max_history", previous_turns=len(history))
                history = history[-max_history:]

            redis = await self._client()
            await redis.set(
                self._key(tenant_id, session_id),
                json.dumps(history),
                ex=self._ttl_seconds,
            )
