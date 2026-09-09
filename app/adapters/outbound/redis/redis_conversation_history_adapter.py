import json

import redis.asyncio as aioredis
from redis.asyncio.cluster import RedisCluster

from app.core.logging.structured_logger import get_logger

log = get_logger(__name__)


class RedisConversationHistoryAdapter:
    """Implements ConversationHistoryPort. Connection details are injected —
    not read from env vars here — so swapping Redis providers later
    (see agb-redis-migration-planned memory) is a config change, not a rewrite.

    `cluster=True` connects via redis.asyncio.cluster.RedisCluster instead of
    the plain client -- needed for Azure Managed Redis, which defaults to the
    OSSCluster clustering policy (see agb-claude-migration memory, Redis
    migration section, 2026-09-09). Every key this adapter reads/writes is a
    single-key operation (no cross-slot multi-key commands), so no hash tags
    are needed for this to work under OSSCluster. Local/dev Redis
    (docker-compose, single node) stays non-cluster."""

    def __init__(self, *, redis_url: str, ttl_seconds: int = 900, cluster: bool = False):
        self._redis_url = redis_url
        self._ttl_seconds = ttl_seconds
        self._cluster = cluster
        self._redis = None

    async def _client(self):
        if self._redis is None:
            if self._cluster:
                # ssl_check_hostname=False: RedisCluster descubre los nodos
                # de cada shard vía CLUSTER SLOTS y Azure Managed Redis
                # devuelve sus IPs internas -- el certificado TLS solo es
                # válido para el hostname público, no para esas IPs, así que
                # la verificación de hostname falla aunque la conexión sea
                # legítima. TLS sigue activo (ssl_cert_reqs=None desactiva
                # solo la verificación del certificado, no el cifrado).
                # Workaround confirmado contra la instancia real de AGB
                # (2026-09-09) -- mismo patrón documentado para este
                # problema conocido de Azure Managed Redis + redis-py.
                self._redis = await RedisCluster.from_url(
                    self._redis_url,
                    decode_responses=True,
                    ssl_cert_reqs=None,
                    ssl_check_hostname=False,
                )
            else:
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
