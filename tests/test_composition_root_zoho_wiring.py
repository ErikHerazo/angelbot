from app.adapters.outbound.zoho.zoho_chat_platform_adapter import ZohoChatPlatformAdapter
from app.composition_root import build_process_incoming_message


async def test_builds_real_zoho_adapter_with_config_and_secret_when_not_overridden(monkeypatch):
    monkeypatch.setenv("ZOHO_ACCESS_TOKEN_AGB", "fake-token-value")

    async def fake_rag_runner(**kwargs):
        return "respuesta"

    async def fake_compress_fn(answer, original_question):
        return answer

    use_case = await build_process_incoming_message(
        "agb",
        rag_runner=fake_rag_runner,
        compress_fn=fake_compress_fn,
    )

    chat_platform = use_case._chat_platform

    assert isinstance(chat_platform, ZohoChatPlatformAdapter)
    assert chat_platform._server_uri == "salesiq.zoho.eu"
    assert chat_platform._screenname == "antiaginggroup"
    assert chat_platform._headers["Authorization"] == "Zoho-oauthtoken fake-token-value"
