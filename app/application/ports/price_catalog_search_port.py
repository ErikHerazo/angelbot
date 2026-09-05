from typing import Protocol

from app.domain.value_objects.procedure_price import ProcedureMatch


class PriceCatalogSearchPort(Protocol):
    async def search(self, query: str) -> list[ProcedureMatch]: ...
