import os
import json
import redis
from datetime import timedelta

class SessionMemoryRedis:
    def __init__(self):
        app_env = os.getenv("APP_ENV", "local")

        if app_env == "prod":
            self.redis_host = os.getenv("REDIS_HOST_PROD")
            self.redis_port = int(os.getenv("REDIS_PORT_PROD", 6380))
            self.redis_password = os.getenv("REDIS_PASSWORD_PROD", None)
            self.redis_ssl = os.getenv("REDIS_SSL_PROD", "True") == "True"
        else:
            self.redis_host = os.getenv("REDIS_HOST_LOCAL")
            self.redis_port = int(os.getenv("REDIS_PORT_LOCAL", 6379))
            self.redis_password = os.getenv("REDIS_PASSWORD_LOCAL", None)
            self.redis_ssl = os.getenv("REDIS_SSL_LOCAL", "False") == "True"

        self.ttl = 900  # 15 minutos por sesión (ajustable)

        self.client = redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            password=self.redis_password,
            ssl=self.redis_ssl,
            decode_responses=True,
        )

    def add_message(self, session_id: str, role: str, content: str):
        """Agrega un mensaje al historial de la sesión."""
        key = f"session:{session_id}"
        session_data = self.get_session(session_id)
        session_data.append({"role": role, "content": content})
        self.client.setex(key, timedelta(seconds=self.ttl), json.dumps(session_data))

    def get_session(self, session_id: str):
        """Obtiene el contexto de la sesión."""
        key = f"session:{session_id}"
        data = self.client.get(key)
        if data:
            return json.loads(data)
        return []

    def clear_session(self, session_id: str):
        """Elimina el historial de la sesión."""
        key = f"session:{session_id}"
        self.client.delete(key)
