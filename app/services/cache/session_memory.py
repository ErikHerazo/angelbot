import os
import json
import redis.asyncio as aioredis

class SessionMemoryRedis:
    def __init__(self):
        self.ttl = 900  # 15 minutos por sesión
        app_env = os.getenv("APP_ENV", "local").lower()

        if app_env == "prod":
            # Redis Enterprise en Azure con SSL y contraseña separada
            host = os.getenv("REDIS_HOST_PROD")
            port = os.getenv("REDIS_PORT_PROD")
            password = os.getenv("REDIS_PASSWORD_PROD")
            # rediss://<password>@<host>:<port>
            self.redis_url = f"rediss://:{password}@{host}:{port}"
            self.redis_kwargs = {"decode_responses": True}
        else:
            # Redis local (docker)
            self.redis_url = os.getenv("REDIS_URL_LOCAL", "redis://redis_local:6379")
            self.redis_kwargs = {"decode_responses": True}

        self.redis = None

    async def connect(self):
        if self.redis is None:
            self.redis = await aioredis.from_url(
                self.redis_url,
                **self.redis_kwargs
            )

    async def ensure_connected(self):
        if self.redis is None:
            await self.connect()

    async def get_session(self, session_id: str):
        await self.ensure_connected()
        data = await self.redis.get(f"session:{session_id}")
        return json.loads(data) if data else []

    async def save_session(self, session_id: str, history: list):
        await self.ensure_connected()
        await self.redis.setex(f"session:{session_id}", self.ttl, json.dumps(history))

    async def add_message(self, session_id: str, role: str, content: str):
        history = await self.get_session(session_id)
        history.append({"role": role, "content": content})
        await self.save_session(session_id, history)

    async def clear_session(self, session_id: str):
        await self.ensure_connected()
        await self.redis.delete(f"session:{session_id}")
