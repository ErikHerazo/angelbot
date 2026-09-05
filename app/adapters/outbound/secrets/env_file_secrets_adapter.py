import os


class EnvFileSecretsAdapter:
    async def get_secret(self, name: str) -> str:
        env_var_name = name.upper().replace("-", "_")
        value = os.getenv(env_var_name)

        if value is None:
            raise KeyError(f"Secret '{name}' (env var '{env_var_name}') not found")

        return value
