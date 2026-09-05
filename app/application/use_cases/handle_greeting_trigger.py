from app.application.ports.greeting_config_repository_port import GreetingConfigRepositoryPort


class HandleGreetingTrigger:
    def __init__(self, *, greeting_config: GreetingConfigRepositoryPort):
        self._greeting_config = greeting_config

    async def execute(self, tenant_id: str) -> str:
        return await self._greeting_config.get_greeting(tenant_id)
