# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

AngelBot Backend is a FastAPI microservice that powers a multilingual virtual assistant ("Aesthea") for Antiaging Group Barcelona, a cosmetic surgery clinic. It receives webhook events from Zoho SalesIQ (live chat) and Zoho Flow (web forms), runs a RAG pipeline against Azure OpenAI + Azure AI Search, and pushes the generated answer back to Zoho asynchronously.

## Commands

There is no test suite, linter, or build step configured (no pytest/ruff/black in `requirements.txt`, no CI config). Files named `test_*.py` under `app/services/**` are standalone manual scripts (no assertions/pytest fixtures) meant to be run directly to sanity-check a connection, e.g.:

```bash
python -m app.services.cache.test_session_memory
python -m app.services.db.test_connection
```

Run the app locally:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Run the full stack (API + Celery worker + Redis + ngrok tunnel) via Docker:

```bash
docker-compose up --build
```

Run the Celery worker standalone (needed for the Azure Search indexer task):

```bash
celery -A app.tasks.celery worker --loglevel=info
```

Config is loaded from `/app/.env` (hardcoded path in `app/core/config.py`, matches the Docker volume layout) — for local non-Docker runs, ensure a `.env` is reachable at that path or adjust it. `app/core/config.py` raises `RuntimeError` at import time if key Azure/Celery settings are missing, so the app won't start with an incomplete `.env`. See `.env.example` for a minimal set; the real `.env` (gitignored) additionally needs Redis, Zoho, SQL, and Storage credentials (search `os.getenv(` across `app/` for the full list).

## Architecture

### Request flow (webhook → LLM → async callback)

Zoho calls are fire-and-forget from Zoho's perspective: the webhook handler returns immediately (a "pending" payload) while the real work happens in a background asyncio task, and the final answer is POSTed back to Zoho's callback API once ready. This exists because RAG + tool-calling round trips can exceed Zoho's webhook timeout.

1. **`app/api/routes/chat_zoho.py`** — single `POST /api/chat/webhook` entrypoint for both Zoho products.
2. **`zoho_dispatcher.dispatch_zoho_webhook`** — identifies the source (`source_detector.detect_zoho_source`, based on headers like `x-siqsignature` vs `x-webhook-secret`), validates the webhook signature accordingly (`core/security.py`: RSA signature for SalesIQ, HMAC secret compare for Flow), then parses the raw Zoho JSON into a source-agnostic `ChatEvent` (`services/chat/models/event.py`) via `parsers/salesiq_parser.py` or `parsers/flow_parser.py`. This adapter layer is what decouples the rest of the pipeline from Zoho's payload shape.
3. **`chat_event_router.route_chat_event`** — dispatches by `event.event_type`: `"message"` → `handlers/message_handler.py`, `"trigger"` → `handlers/trigger_handler.py` (static greeting), `"lead"` → `handlers/flow_handler.py` (Zoho Flow form submissions).
4. **`message_handler.handle_message`** — for file uploads, replies synchronously with a translated ack; otherwise spawns `asyncio.create_task(process_message_async(...))` and immediately returns `constants.PENDING_PAYLOAD`.
5. **`zoho_message_processor.process_message_async` → `use_cases/process_zoho_message.py`** — sends a Zoho "progress" ping (to extend Zoho's timeout), calls the RAG runner, optionally compresses the answer for Instagram's character limit (`summarize_with_llm.generate_compact_answer`), appends the turn to Redis session history, then POSTs the final answer to Zoho via `ZohoClient.send_final_response`.
6. Zoho Flow leads go through the parallel path `zoho_flow_processor.py` → `use_cases/process_zoho_flow_lead.py`, which builds a synthetic user_question from form fields and returns a JSON result directly (no async callback, since Flow expects a synchronous response body).

### RAG pipeline (`services/cloud/azure/azure_openai.py::run_conversation_with_rag`)

- Loads Redis session history (skipped for `channel == "flow"`, which is stateless/one-shot).
- Resolves the **reply language deterministically by code**, not by LLM inference (see "Reply language resolution" below), then translates the user's question to Spanish (`translate_text`) purely to query the Spanish-language Azure AI Search index.
- Picks a system prompt by channel via `get_base_prompt_by_channel` (`website`/`whatsapp`/`instagram`/`flow`, all defined as large prompt strings in `core/constants.py`) and formats it with `{reply_language}` — the prompt's "REGLA DE IDIOMA" tells the LLM to write natively in that already-resolved language, not to infer it itself.
- Calls `make_completion.py`, which calls Azure OpenAI's chat completions with `tools=azure_tools.tools` and an `extra_body.data_sources` block wiring in Azure AI Search directly (Azure's "on your data" pattern) — so retrieval happens both via explicit tool calls (`is_customer_service_available`, `procedures_and_treatments_price_list`) and via the built-in data source grounding.
- **Failover**: `load_balancer.py` (`FailoverLoadBalancer`) wraps every completion call — on `RateLimitError`/timeout/connection/server errors it cools down the primary Azure OpenAI deployment (`client.py::primary_client`) for N seconds (from `Retry-After` if present) and retries on `secondary_client`.
- After tool calls resolve, the `{reply_language}` instruction is repeated as a fresh system message (tool results are often in Spanish and can otherwise crowd out the original instruction), then a second completion is forced with `tool_choice="none"` to get a final textual answer (avoids tool-call loops).
- The generated answer passes through `enforce_reply_language` as a last check before returning (see below).
- `constants.CONTINUE_TOKEN` is a special sentinel message (sent when the user clicks a "continue" card in SalesIQ) intercepted by `handle_continue_token.py` *before* hitting the LLM — it returns a fixed, translated message instead of a real completion.

### Reply language resolution

The bot used to let the LLM infer the reply language from conversation history via prompt instructions alone; this proved unreliable in production (short first messages like "hi" defaulted to Spanish, and the LLM would sometimes keep answering in Spanish right after a tool call returned Spanish-language price data, even with an explicit "respond in X" instruction in context). It's now resolved deterministically by code before the LLM ever runs:

- `core/utils/resolve_reply_language.py::resolve_reply_language` — priority order: (1) Azure Translator `/detect` (`azure_language_detector.py`) on the current message if it has enough signal (`constants.MIN_LANG_DETECTION_LEN`), (2) the same detector on accumulated session history, (3) a `visitor_language` hint, (4) Spanish default. For `channel == "flow"` detection is skipped entirely (the message is a synthetic Spanish-templated string built from form fields) and the form's own declared `lang` field is trusted directly as the hint.
- The `visitor_language` hint is threaded from the top of the request: SalesIQ sends a visitor browser-locale field (`salesiq_parser.py` → `event.metadata["language"]`) through `message_handler.py` → `zoho_message_processor.py` → `process_zoho_message.py` → `run_conversation_with_rag`; Zoho Flow's declared `lang` form field is passed the same way from `process_zoho_flow_lead.py`.
- The resolved code is mapped to a display name via `constants.LANGUAGE_DISPLAY_NAMES` (~26 languages, falls back to the raw ISO code for anything else) and injected into the prompt.
- `core/utils/enforce_reply_language.py::enforce_reply_language` — a final safety net run on the LLM's actual output: detects its real language via Azure and, if it doesn't match the resolved one, translates it with `translate_text` before returning. Keeps the guarantee even if the LLM ignores the prompt instruction.
- The same resolver (with `use_history=True`, no current message) also backs the two non-LLM fixed messages that need a language: the file-upload ack in `message_handler.py` and the continue-token reply in `handle_continue_token.py`.

### Session memory (`services/cache/session_memory.py`)

Redis-backed conversation history, keyed `session:{session_id}`, TTL 15 min (900s), capped at `MAX_HISTORY=6` messages in `process_zoho_message.py`. Redis connection differs by `APP_ENV` (`prod` uses Azure Redis Enterprise over `rediss://` with a separate password; otherwise local Docker Redis). A parallel `session:{id}:meta` key with independent read/write helpers exists for auxiliary metadata, refreshed alongside the main session TTL. Saving the turn to history is wrapped in try/except in `process_zoho_message.py` — a transient Redis failure logs and is swallowed rather than preventing `send_final_response` from delivering the already-generated answer.

### Background jobs (Celery)

`app/tasks/celery.py` defines the Celery app (Redis broker/backend, SSL configured for Azure Redis in prod). The only real task, `run_search_indexer` (`app/tasks/tasks.py`), triggers the Azure AI Search indexer (`AzureSearchIndexerService`) after a new pricing/document file is uploaded to Blob Storage via `web/routes/upload_file.py` — this is how newly uploaded documents become searchable without a full redeploy.

### Multi-channel prompts

`core/constants.py` holds one full system prompt per channel (`WEBSITE_ASSISTANT_PROMPT`, `WHATSAPP_ASSISTANT_PROMPT`, `INSTAGRAM_ASSISTANT_PROMPT`, `FLOW_FORM_ASSISTANT_PROMPT`). They're near-duplicates by design (each channel has slightly different rules, e.g. Flow's prompt forbids asking the user follow-up questions since it's a one-shot form response) — when changing shared behavior (e.g. the language rule), update all four. Each prompt contains a `{reply_language}` placeholder filled via `.format()` in `azure_openai.py`; avoid introducing any other stray `{`/`}` in these strings or the `.format()` call will break.

### Web/admin routes (`app/web/`)

Separate from the Zoho webhook API: `web/routes/home.py` serves a Jinja2 chat test page, `web/routes/upload_file.py` serves an admin UI + JSON endpoints for browsing Azure Blob containers/prefixes and uploading price-list/document files (validated in `web/utils/file_validators.py` against `constants.ALLOWED_EXTENSIONS`/`ALLOWED_MIME_TYPES`/`MAX_FILE_SIZE_MB`), which then triggers the Celery indexer task.

### Azure integrations map

- `services/cloud/azure/client.py` — primary/secondary `AsyncAzureOpenAI` clients (chat completions).
- `services/cloud/azure/make_completion.py` / `load_balancer.py` — completion call + failover, described above.
- `services/cloud/azure/azure_search/query_service.py` — hybrid semantic search helper (currently unused directly by the RAG flow, which instead uses the `data_sources` grounding in `make_completion.py`).
- `services/cloud/azure/azure_search/indexer_service.py` — indexer status/run control, used by the Celery task.
- `services/cloud/azure/azure_blob.py` — blob CRUD + the price-list CSV reader.
- `services/cloud/azure/azure_tools.py` — LLM tool implementations: business-hours check (`is_customer_service_available`, Europe/Madrid timezone + `holidays.Spain`) and price-list lookup (queries a *separate* Azure AI Search index, `AZURE_AI_SEARCH_PRICE_LIST_INDEX`, hitting `agb-search.search.windows.net` directly rather than through `query_service.py`).
- `services/cloud/azure/translate_text.py` / `azure_language_detector.py` — Azure Translator text API wrappers.
- `services/db/connection.py` — pyodbc connection to Azure SQL (used to lazily create a `users` table in `azure_tools.ensure_users_table`; not central to the main chat flow).

### Zoho integration map

- `services/zoho/client.py::ZohoClient` — posts progress/final-response callbacks back to Zoho SalesIQ's REST API (`ZOHOSALESIQ_SERVER_URI`/`SCREENNAME` in constants).
- `services/zoho/handle_continue_token.py` — intercepts the "continue" sentinel described above.
- Webhook auth is source-specific: SalesIQ uses RSA-SHA256 signature verification against a public key in `SIGNATURE_WEBHOOK_ZOHOSALESIQ` (and re-injects the consumed request body so downstream `request.json()`-style parsing still works); Flow uses a shared-secret HMAC comparison (`FLOW_WEBHOOK_SECRET`).
