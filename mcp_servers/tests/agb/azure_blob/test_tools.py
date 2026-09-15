"""Tests for mcp_servers/agb/azure_blob/tools.py, registered onto ClinyqMCP.

No real network call: BlobServiceClient / its container-listing and upload
calls are monkeypatched. This writes to a real customer's Blob Storage
account, so (like agb/zoho) it's never exercised against the real service
in the automated suite.
"""

import base64
from unittest.mock import MagicMock, patch

import pytest

import main  # importing main registers agb's azure_blob tools onto main.mcp
from agb.azure_blob import tools


@pytest.fixture(autouse=True)
def _fake_secret(monkeypatch):
    monkeypatch.setenv("AZURE_BLOB_CONNECTION_STRING_AGB", "fake-connection-string")


async def test_both_tools_are_registered_on_the_shared_clinyqmcp_server():
    from fastmcp import Client

    async with Client(main.mcp) as client:
        names = {t.name for t in await client.list_tools()}

    assert {"list_containers", "upload_document"} <= names


async def test_list_containers_returns_container_names():
    fake_container_a = MagicMock(name="a")
    fake_container_a.name = "documents"
    fake_container_b = MagicMock(name="b")
    fake_container_b.name = "price-lists"

    fake_client = MagicMock()
    fake_client.list_containers.return_value = [fake_container_a, fake_container_b]

    with patch(
        "azure.storage.blob.BlobServiceClient.from_connection_string", return_value=fake_client
    ):
        result = await tools.list_containers(tenant_id="agb")

    assert result == ["documents", "price-lists"]


async def test_upload_document_decodes_base64_and_normalizes_metadata():
    fake_blob_client = MagicMock()
    fake_client = MagicMock()
    fake_client.get_blob_client.return_value = fake_blob_client

    with patch(
        "azure.storage.blob.BlobServiceClient.from_connection_string", return_value=fake_client
    ):
        result = await tools.upload_document(
            tenant_id="agb",
            container_name="price-lists",
            blob_name="precios.csv",
            content_base64=base64.b64encode(b"raw file bytes").decode(),
            metadata={"Source File": "precios.csv"},
        )

    assert result == {"uploaded": True, "container_name": "price-lists", "blob_name": "precios.csv"}
    fake_client.get_blob_client.assert_called_once_with(container="price-lists", blob="precios.csv")
    args, kwargs = fake_blob_client.upload_blob.call_args
    assert args[0] == b"raw file bytes"
    assert kwargs["overwrite"] is True
    assert kwargs["metadata"] == {"source_file": "precios.csv"}


async def test_list_containers_is_tenant_scoped_not_global(monkeypatch):
    monkeypatch.delenv("AZURE_BLOB_CONNECTION_STRING_AGB", raising=False)
    with patch("azure.storage.blob.BlobServiceClient.from_connection_string") as fake_ctor:
        with pytest.raises(KeyError):
            await tools.list_containers(tenant_id="a-tenant-with-no-secret")
    fake_ctor.assert_not_called()
