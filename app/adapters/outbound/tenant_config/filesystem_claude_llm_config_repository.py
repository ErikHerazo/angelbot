from app.adapters.outbound.tenant_config.tenant_config_file import read_tenant_config_block
from app.application.ports.claude_llm_config_repository_port import ClaudeLLMConfig


class FilesystemClaudeLLMConfigRepository:
    """Implements ClaudeLLMConfigRepositoryPort, reading the "claude" block
    from config/tenants/{tenant_id}/config.yaml. Non-secret only -- the
    Foundry API key goes through SecretsPort, same pattern as every other
    Azure config repo in this codebase."""

    def __init__(self, config_dir: str):
        self._config_dir = config_dir

    async def get_config(self, tenant_id: str) -> ClaudeLLMConfig:
        data = await read_tenant_config_block(self._config_dir, tenant_id, "claude")
        return ClaudeLLMConfig(**data)
