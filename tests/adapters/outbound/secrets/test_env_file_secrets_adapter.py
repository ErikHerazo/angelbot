import pytest

from app.adapters.outbound.secrets.env_file_secrets_adapter import EnvFileSecretsAdapter


async def test_get_secret_reads_normalized_env_var(monkeypatch):
    monkeypatch.setenv("ZOHO_ACCESS_TOKEN_AGB", "secret-value")
    adapter = EnvFileSecretsAdapter()

    value = await adapter.get_secret("zoho-access-token-agb")

    assert value == "secret-value"


async def test_get_secret_raises_when_missing(monkeypatch):
    monkeypatch.delenv("SOME_MISSING_SECRET", raising=False)
    adapter = EnvFileSecretsAdapter()

    with pytest.raises(KeyError):
        await adapter.get_secret("some-missing-secret")
