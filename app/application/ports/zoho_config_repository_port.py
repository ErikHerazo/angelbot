from dataclasses import dataclass
from typing import Protocol


@dataclass
class ZohoConnectionConfig:
    server_uri: str
    screenname: str


class ZohoConfigRepositoryPort(Protocol):
    async def get_config(self, tenant_id: str) -> ZohoConnectionConfig: ...
