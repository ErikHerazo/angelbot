from app.adapters.outbound.tenant_config.tenant_config_file import read_tenant_config_block
from app.application.ports.llm_config_repository_port import LLMConfig


class FilesystemLLMConfigRepository:
    """Implements LLMConfigRepositoryPort, reading the "llm" block from
    config/tenants/{tenant_id}/config.yaml. Non-secret only (endpoint/
    deployments/generation params) -- the API key goes through SecretsPort,
    same pattern as every other Azure config repo in this codebase."""

    def __init__(self, config_dir: str):
        self._config_dir = config_dir

    async def get_config(self, tenant_id: str) -> LLMConfig:
        data = await read_tenant_config_block(self._config_dir, tenant_id, "llm")
        return LLMConfig(**data)
