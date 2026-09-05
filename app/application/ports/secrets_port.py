from typing import Protocol


class SecretsPort(Protocol):
    async def get_secret(self, name: str) -> str: ...
