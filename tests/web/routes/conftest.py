"""Importing anything under app.web.routes triggers app/web/routes/__init__.py,
which eagerly imports upload_file.py (constructs AzureBlobService() at
module load time -- needs a well-formed connection string) and chat_test.py
(transitively imports azure_tools.py -> services/db/connection.py -> pyodbc,
not installed locally). None of these are actually used by the route under
test here; this is pre-existing import-time coupling in that package, not
something this test suite fixes. Dummy values only -- nothing here is a
real credential.
"""
import os
import sys
import types

_pyodbc_stub = types.ModuleType("pyodbc")
_pyodbc_stub.Connection = object
sys.modules.setdefault("pyodbc", _pyodbc_stub)

os.environ.setdefault("AZURE_CLIENT_ID", "dummy")
os.environ.setdefault("AZURE_TENANT_ID", "dummy")
os.environ.setdefault("AZURE_AI_SEARCH_ENDPOINT", "https://dummy")
os.environ.setdefault("AZURE_AI_SEARCH_API_KEY", "dummy")
os.environ.setdefault("AZURE_AI_SEARCH_INDEXER", "dummy")
os.environ.setdefault("CELERY_BROKER_URL_LOCAL", "redis://localhost")
os.environ.setdefault("CELERY_RESULT_BACKEND_LOCAL", "redis://localhost")
os.environ.setdefault(
    "AZURE_STORAGE_CONNECTION_STRING",
    "DefaultEndpointsProtocol=https;AccountName=dummy;AccountKey=ZHVtbXk=;EndpointSuffix=core.windows.net",
)
