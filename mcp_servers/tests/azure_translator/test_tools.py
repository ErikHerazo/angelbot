"""Tests for mcp_servers/azure_translator/tools.py, registered onto ClinyqMCP.

No real network call: httpx.AsyncClient.post is monkeypatched. No tenant
config to fake here -- this module is intentionally not tenant-scoped
(shared ClinyQ infra), see tools.py's docstring.
"""

from unittest.mock import MagicMock, patch

import pytest

import main  # importing main registers azure_translator's tools onto main.mcp
from azure_translator import tools


def _mock_response(payload) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=payload)
    return response


async def test_both_tools_are_registered_on_the_shared_clinyqmcp_server():
    from fastmcp import Client

    async with Client(main.mcp) as client:
        names = {t.name for t in await client.list_tools()}

    assert {"translate", "detect_language"} <= names


async def test_translate_returns_translated_text():
    async def fake_post(self, url, params=None, headers=None, json=None):
        assert params["to"] == ["en"]
        return _mock_response([{"translations": [{"text": "Hello"}]}])

    with patch("httpx.AsyncClient.post", new=fake_post):
        result = await tools.translate("Hola", to_lang="en")

    assert result == "Hello"


async def test_translate_skips_call_when_same_language():
    with patch("httpx.AsyncClient.post") as fake_post:
        result = await tools.translate("Hola", to_lang="es", from_lang="es")

    assert result == "Hola"
    fake_post.assert_not_called()


async def test_translate_falls_back_to_original_text_on_error():
    async def fake_post(self, url, params=None, headers=None, json=None):
        raise httpx_error

    import httpx

    httpx_error = httpx.ConnectError("boom")

    with patch("httpx.AsyncClient.post", new=fake_post):
        result = await tools.translate("Hola", to_lang="en")

    assert result == "Hola"


async def test_detect_language_normalizes_region_suffix():
    async def fake_post(self, url, headers=None, json=None):
        return _mock_response([{"language": "es-ES"}])

    with patch("httpx.AsyncClient.post", new=fake_post):
        result = await tools.detect_language("Hola, ¿cómo estás?")

    assert result == "es"


async def test_detect_language_returns_none_for_blank_input():
    with patch("httpx.AsyncClient.post") as fake_post:
        result = await tools.detect_language("   ")

    assert result is None
    fake_post.assert_not_called()
