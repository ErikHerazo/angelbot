"""Tests for mcp_servers/agb/azure_search/tools.py, registered onto ClinyqMCP.

Run with `mcp_servers/.venv/bin/python -m pytest` from inside `mcp_servers/`
(picks up mcp_servers/pytest.ini, which sets `pythonpath = .` so `clinyq_mcp`
and `agb.azure_search` resolve as top-level imports).

No real network call: httpx.AsyncClient.post is monkeypatched. Config
resolution (endpoint/index names) DOES hit the real AGB YAML files under
app/config/tenants/agb/ -- same "real local config, faked network" split
already used for the equivalent adapters in tests/adapters/outbound/
azure_search/ in the main app's suite.
"""

from unittest.mock import MagicMock, patch

import pytest

import main  # importing main registers agb's azure_search tools onto main.mcp
from agb.azure_search import tools


@pytest.fixture(autouse=True)
def _fake_secret(monkeypatch):
    monkeypatch.setenv("AZURE_SEARCH_API_KEY_AGB", "fake-key")


def _mock_response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=payload)
    return response


async def test_both_tools_are_registered_on_the_shared_clinyqmcp_server():
    from fastmcp import Client

    async with Client(main.mcp) as client:
        names = {t.name for t in await client.list_tools()}

    assert {"search_price_catalog", "search_knowledge_base"} <= names


async def test_search_price_catalog_uses_real_agb_config_and_maps_result():
    captured = {}

    async def fake_post(self, url, headers=None, json=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _mock_response(
            {"value": [{"procedure_name": "RINOSEPTOPLASTIA", "price_range_eur": "7500-8500"}]}
        )

    with patch("httpx.AsyncClient.post", new=fake_post):
        result = await tools.search_price_catalog(tenant_id="agb", query="rinoplastia")

    assert result == [{"procedure_name": "RINOSEPTOPLASTIA", "price_range_eur": "7500-8500"}]
    assert "agb-search.search.windows.net" in captured["url"]
    assert "rag-structured-data-3-large" in captured["url"]
    # No searchMode override -- Azure default ("any"), Erik's 2026-09-09 call.
    assert captured["json"] == {"search": "rinoplastia", "count": True}
    assert captured["headers"]["api-key"] == "fake-key"


async def test_search_price_catalog_is_tenant_scoped_not_global():
    with patch("httpx.AsyncClient.post") as fake_post:
        with pytest.raises(FileNotFoundError):
            await tools.search_price_catalog(tenant_id="a-tenant-with-no-config", query="x")
    fake_post.assert_not_called()


async def test_search_knowledge_base_prefers_captions_then_falls_back_to_chunk():
    async def fake_post(self, url, headers=None, json=None):
        assert json["queryType"] == "semantic"
        assert json["semanticConfiguration"]
        return _mock_response(
            {
                "value": [
                    {"@search.captions": [{"text": "caption text"}]},
                    {"chunk": "fallback chunk text"},
                    {},
                ]
            }
        )

    with patch("httpx.AsyncClient.post", new=fake_post):
        result = await tools.search_knowledge_base(tenant_id="agb", query="horario de atencion", top_k=2)

    assert result == ["caption text", "fallback chunk text"]
