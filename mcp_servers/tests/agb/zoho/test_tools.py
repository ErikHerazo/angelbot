"""Tests for mcp_servers/agb/zoho/tools.py, registered onto ClinyqMCP.

No real network call to Zoho (these tools write to a live customer-service
system, not read-only like Azure Search -- never hit the real API in
automated tests). httpx.AsyncClient.post is monkeypatched; config
resolution (server_uri/screenname) DOES hit the real AGB YAML file under
app/config/tenants/agb/zoho.yaml.
"""

from unittest.mock import MagicMock, patch

import pytest

import main  # importing main registers agb's zoho tools onto main.mcp
from agb.zoho import tools


@pytest.fixture(autouse=True)
def _fake_secret(monkeypatch):
    monkeypatch.setenv("ZOHO_ACCESS_TOKEN_AGB", "fake-token")


def _mock_response(status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.raise_for_status = MagicMock()
    return response


async def test_both_tools_are_registered_on_the_shared_clinyqmcp_server():
    from fastmcp import Client

    async with Client(main.mcp) as client:
        names = {t.name for t in await client.list_tools()}

    assert {"send_progress_update", "send_final_response"} <= names


async def test_send_progress_update_uses_real_agb_config_and_correct_payload():
    captured = {}

    async def fake_post(self, url, json=None, headers=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return _mock_response()

    with patch("httpx.AsyncClient.post", new=fake_post):
        result = await tools.send_progress_update(tenant_id="agb", request_id="req-123")

    assert result == {"sent": True}
    assert captured["url"] == (
        "https://salesiq.zoho.eu/api/v2/antiaginggroup/callbacks/req-123/progress"
    )
    assert captured["json"] == {"text": "Just a few more seconds.."}
    assert captured["headers"]["Authorization"] == "Zoho-oauthtoken fake-token"


async def test_send_final_response_uses_real_agb_config_and_correct_payload():
    captured = {}

    async def fake_post(self, url, json=None, headers=None):
        captured["url"] = url
        captured["json"] = json
        return _mock_response()

    with patch("httpx.AsyncClient.post", new=fake_post):
        result = await tools.send_final_response(
            tenant_id="agb", request_id="req-456", answer_text="La respuesta final"
        )

    assert result == {"sent": True}
    assert captured["url"] == (
        "https://salesiq.zoho.eu/api/v2/antiaginggroup/callbacks/req-456/response"
    )
    assert captured["json"] == {
        "action": "reply",
        "replies": [{"text": "La respuesta final"}],
    }


async def test_send_progress_update_is_tenant_scoped_not_global():
    with patch("httpx.AsyncClient.post") as fake_post:
        with pytest.raises(FileNotFoundError):
            await tools.send_progress_update(tenant_id="a-tenant-with-no-config", request_id="x")
    fake_post.assert_not_called()
