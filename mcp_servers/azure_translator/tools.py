"""Registers Azure Translator tools onto the shared ClinyqMCP server.

Unlike `agb/azure_search` and `agb/zoho`, this module lives OUTSIDE any
client folder (Erik's call, 2026-09-15): Azure Translator is shared
ClinyQ-level infrastructure today, not a per-client resource -- there's
only one endpoint/key, read from global config, with no tenant dimension
anywhere in the legacy code this is ported from
(`app/services/cloud/azure/translate_text.py` /
`azure_language_detector.py`). No `tenant_id` parameter on either tool for
that reason -- add one later only if translation genuinely becomes
per-tenant (e.g. a client brings their own Translator resource).

Known pre-existing quirk, not fixed here: the actual Azure resource this
points at is named `agb-translator.cognitiveservices.azure.com` -- despite
being treated as "shared" in code, the resource itself is AGB-branded.
Onboarding a second tenant that needs its own Translator resource would
need this module to grow a tenant dimension then, not before.

Exposes 2 tools, `translate` and `detect_language`, both simple ports of
the legacy functions with the same safe-fallback behavior (translate
failure -> original text; detect failure -> None) so a transient Azure
Translator error degrades gracefully instead of blocking the caller.
"""

import os
import sys
import uuid

import httpx

_MCP_SERVERS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_REPO_ROOT = os.path.abspath(os.path.join(_MCP_SERVERS_DIR, ".."))
for _path in (_REPO_ROOT, _MCP_SERVERS_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(_REPO_ROOT, ".env"))

from app.core import constants

from clinyq_mcp import mcp

_API_KEY = os.getenv("AZURE_TRANSLATOR_API_KEY")


@mcp.tool
async def translate(text: str, to_lang: str, from_lang: str | None = None) -> str:
    """Translate `text` to `to_lang` via Azure Translator.

    Returns `text` unchanged if it's empty, if `from_lang` already equals
    `to_lang`, or if the Azure call fails for any reason -- callers should
    treat this as best-effort, not assume the result is always translated.
    """
    if not text:
        return text
    if from_lang and from_lang == to_lang:
        return text

    url = constants.AZURE_TRANSLATOR_ENDPOINT + constants.AZURE_TRANSLATOR_PATH
    headers = {
        "Ocp-Apim-Subscription-Key": _API_KEY,
        "Ocp-Apim-Subscription-Region": constants.AZURE_TRANSLATOR_LOCATION,
        "Content-type": "application/json",
        "X-ClientTraceId": str(uuid.uuid4()),
    }
    params = {"to": [to_lang]}
    if from_lang:
        params["from"] = from_lang

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(url, params=params, headers=headers, json=[{"text": text}])
            response.raise_for_status()
            return response.json()[0]["translations"][0]["text"]
    except Exception:
        return text


@mcp.tool
async def detect_language(text: str) -> str | None:
    """Detect the ISO 639-1 language code of `text` via Azure Translator.

    Returns None for blank input or if the Azure call fails for any reason.
    """
    if not text or not text.strip():
        return None

    url = constants.AZURE_DETECT_ENDPOINT + constants.AZURE_DETECT_PATH
    headers = {
        "Ocp-Apim-Subscription-Key": _API_KEY,
        "Ocp-Apim-Subscription-Region": constants.AZURE_DETECT_LOCATION,
        "Content-Type": "application/json",
        "X-ClientTraceId": str(uuid.uuid4()),
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(url, headers=headers, json=[{"text": text}])
            response.raise_for_status()
            data = response.json()
            if not data or "language" not in data[0]:
                return None
            return data[0]["language"].split("-")[0].lower()
    except Exception:
        return None
