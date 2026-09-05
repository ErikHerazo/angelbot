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
- **Content filter fallback**: both completion calls are wrapped in `try/except BadRequestError`; if Azure's own content filter (`ResponsibleAIPolicyViolation`) blocks the request outright before any completion is generated (observed trigger: a minor + breast-related content in the same message — phrasing-sensitive, e.g. declarative "mi hija quiere un aumento de pecho" triggers it but the equivalent question doesn't, and not fully deterministic run-to-run), the pipeline returns `constants.CONTENT_FILTER_FALLBACK_MESSAGE` translated to the resolved language instead of propagating the error up to the generic English fallback in `process_zoho_message.py`.
- **Revision/reintervention pricing**: the LLM has a tool, `flag_revision_or_reintervention_price_request` (in `azure_tools.py`), that it must call *instead of* `procedures_and_treatments_price_list` when the user asks for the price of a revision/reintervention (i.e. already had the same procedure before). The price catalog only stores first-time prices, and prompt-only instructions telling the LLM not to reuse that price for revisions proved unreliable (confirmed via testing: the LLM kept quoting the first-time price regardless of how forcefully the instruction was worded) — so when this tool is called, `run_conversation_with_rag` short-circuits and returns `constants.REVISION_PRICE_FALLBACK_MESSAGE` (translated) directly, skipping the final LLM generation pass entirely so the wrong price can never leak through.
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

Redis-backed conversation history, keyed `session:{session_id}`, TTL 15 min (900s), capped at `MAX_HISTORY=6` messages in `process_zoho_message.py`. Redis connection differs by `APP_ENV` (`prod` uses Azure Redis Enterprise over `rediss://` with a separate password; otherwise local Docker Redis). A parallel `session:{id}:meta` key with independent read/write helpers exists for auxiliary metadata, refreshed alongside the main session TTL. Saving the turn to history is wrapped in try/except in `process_zoho_message.py` — a transient Redis failure logs and is swallowed rather than preventing `send_final_response` from delivering the already-generated answer. The initial history *read* in `run_conversation_with_rag` (`azure_openai.py`) is similarly wrapped in try/except — a transient Redis failure (observed in practice against the Standard-tier Azure Cache used in `prod`, unrelated to any code change — Azure-side metrics showed the cache itself healthy) falls back to an empty history instead of crashing the whole RAG call.

### Background jobs (Celery)

`app/tasks/celery.py` defines the Celery app (Redis broker/backend, SSL configured for Azure Redis in prod). The only real task, `run_search_indexer` (`app/tasks/tasks.py`), triggers the Azure AI Search indexer (`AzureSearchIndexerService`) after a new pricing/document file is uploaded to Blob Storage via `web/routes/upload_file.py` — this is how newly uploaded documents become searchable without a full redeploy.

### Multi-channel prompts

`core/constants.py` holds one full system prompt per channel (`WEBSITE_ASSISTANT_PROMPT`, `WHATSAPP_ASSISTANT_PROMPT`, `INSTAGRAM_ASSISTANT_PROMPT`, `FLOW_FORM_ASSISTANT_PROMPT`). They're near-duplicates by design (each channel has slightly different rules, e.g. Flow's prompt forbids asking the user follow-up questions since it's a one-shot form response) — when changing shared behavior (e.g. the language rule), update all four. Each prompt contains a `{reply_language}` placeholder filled via `.format()` in `azure_openai.py`; avoid introducing any other stray `{`/`}` in these strings or the `.format()` call will break.

`MINOR_SAFETY_RULE` and `DISAMBIGUATION_RULES` (also in `constants.py`, business/legal-sourced) are injected via literal `<<TOKEN>>` placeholders + `.replace()` — deliberately not `.format()`, to avoid touching the `{reply_language}` mechanism — into `WEBSITE_ASSISTANT_PROMPT`/`WHATSAPP_ASSISTANT_PROMPT`/`INSTAGRAM_ASSISTANT_PROMPT` only; `FLOW_FORM_ASSISTANT_PROMPT` is deliberately excluded since its one-shot, no-follow-up-question constraint conflicts with disambiguation's "ask one clarifying question" behavior. `MINOR_SAFETY_RULE` tells the LLM not to lead with elective-surgery pricing/recommendations for patients under 16, while carving out congenital/functional cases (e.g. real gynecomastia) from being dismissed as purely cosmetic. `DISAMBIGUATION_RULES` maps ambiguous patient phrasing (e.g. "pecho", "piernas", "papada", "bolsas") to the right procedure per body area, asking one clarifying question only when genuinely ambiguous. **Ordering inside this block matters more than instruction wording**: testing found the LLM reliably ignored a correctly-worded rule sitting ~300 lines away from where the related term first appears in the document (the "aumento de pecho en hombres" disambiguation was consistently skipped in favor of the earlier, more prominent "aumento de pecho" → breast implants association), and reliably followed it once physically moved adjacent to that first mention — a "lost in the middle of a long prompt" effect, not a wording problem. The same effect blocked a prompt-only fix for revision/reintervention pricing (see RAG pipeline section above) no matter how the instruction was worded, which is why that specific case was moved to a code-level tool-call intercept instead of prompt text.

### Web/admin routes (`app/web/`)

Separate from the Zoho webhook API: `web/routes/home.py` serves a Jinja2 chat test page (currently broken — it renders `templates/home.html`, which doesn't exist in the repo; only `blob_upload.html` is present), `web/routes/upload_file.py` serves an admin UI + JSON endpoints for browsing Azure Blob containers/prefixes and uploading price-list/document files (validated in `web/utils/file_validators.py` against `constants.ALLOWED_EXTENSIONS`/`ALLOWED_MIME_TYPES`/`MAX_FILE_SIZE_MB`), which then triggers the Celery indexer task. `web/routes/chat_test.py` exposes `POST /web/chat/test`, which calls `run_conversation_with_rag` directly — bypassing Zoho's webhook/signature/payload shape entirely — gated behind a `CHAT_TEST_SECRET` env var (the router 404s if it's unset, and 401s if the request's `X-Test-Secret` header doesn't match), paired with a `CORSMiddleware` in `main.py` enabled only when that secret is set. This exists so an external static test console (see "Environments & test tooling" below) can call the RAG pipeline cross-origin without touching Zoho.

### Environments & test tooling

Two Azure Container Apps run in the `Angelbot_rg` resource group (subscription "AngelBot subscription"), both pulling from the `angelbotacr01` ACR:
- `angelbot-backend` (+ `celery-worker`) — production, serving real Zoho traffic. Deployed by versioning the image tag (e.g. `0.79.x` → `0.80.0`) and updating both apps' `--image`.
- `angelbot-backend-staging` — an isolated app (no celery worker of its own; it's not needed since this app only exercises the `/web/chat/test` chat path, not the indexer) created for testing prompt/behavior changes without touching production traffic. It reuses the same fixed image tag (`:staging`), which means `az containerapp update --image ...:staging` alone does **not** reliably pick up a freshly pushed image — Azure Container Apps needs `--revision-suffix <unique>` to force a new revision when the tag string doesn't change.
- A separate, external static page — a "Bot Test Console" (`index.html`, backend-URL/secret/channel fields, session management, `.md` transcript export) — lives in its own repo (`ErikHerazo/testing` on GitHub, published via GitHub Pages) rather than inside `AngelBotBackend`, since it's meant to be reused across future clients beyond AGB, not tied to this one codebase. It talks to whatever backend URL is configured in the viewer's browser (`localStorage`-persisted) — typically `angelbot-backend-staging`'s URL — via `/web/chat/test`.

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

## Hexagonal architecture migration (in progress, branch `feature/hexagonal-architecture-migration`)

Since 2026-09-05 this codebase is being incrementally migrated to **hexagonal architecture (ports & adapters)** with multi-tenant support, living alongside everything described above. **Everything in this section is additive**: nothing here is wired into `app/main.py` or live routing yet — the architecture described in the rest of this document is what actually serves Zoho traffic today. Treat this section as the map of a parallel, not-yet-cut-over implementation.

### Why

Two goals: (1) decouple business logic from Zoho/Azure/Redis specifics via ports/adapters, so swapping any of them (e.g. a client on WhatsApp instead of Zoho, or the planned Redis provider change) is an adapter swap, not a rewrite; (2) make the codebase genuinely multi-tenant — today everything is hardcoded to Antiaging Group Barcelona (AGB). This is separate from, but reconciled with, the earlier LangGraph/LangChain migration effort: when that happens (AI/conversation-generation only), it will become the adapter behind `ConversationEnginePort` below — no other port or use case changes for it.

### Folder structure

```
app/
  domain/              # entities/value objects — shared across all tenants, framework-free
    entities/tenant.py                    # Tenant (fiscal/business identity + subscription fields)
    value_objects/business_hours.py       # BusinessHoursWindow, BusinessHoursSchedule, is_within_business_hours (pure)
    value_objects/procedure_price.py      # ProcedureMatch, ProcedurePriceResult, normalize_search_text (pure)
  application/         # use cases + ports — shared across all tenants
    ports/             # Protocol interfaces implemented by adapters
    use_cases/
  adapters/
    inbound/           # things that drive the app: LLM tool wrappers, Zoho response formatters
      llm_tools/
      zoho/
    outbound/          # things the app drives: Zoho HTTP, Redis, Azure OpenAI/Search/Translator, config/secrets readers
  config/
    tenants/
      agb/             # AGB's config data files (see below) — one file per concern, not one big blob
  composition_root.py  # wires concrete adapters into use cases, per tenant
```

`adapters/in/`/`adapters/out/` would break (`in` is a reserved Python keyword) — always `inbound`/`outbound`.

### Use cases built so far

| Use case | File | Ports it depends on |
|---|---|---|
| `ProcessIncomingMessage` | `application/use_cases/process_incoming_message.py` | `ChatPlatformPort`, `ConversationEnginePort`, `ConversationHistoryPort`, `ReplyCompressionPort` |
| `CheckBusinessAvailability` | `application/use_cases/check_business_availability.py` | `TenantRepositoryPort`, `BusinessHoursConfigRepositoryPort`, `ClockPort` |
| `LookupProcedurePrice` | `application/use_cases/lookup_procedure_price.py` | `TenantRepositoryPort`, `PriceCatalogSearchPort` |
| `HandleGreetingTrigger` | `application/use_cases/handle_greeting_trigger.py` | `GreetingConfigRepositoryPort` |
| `InterceptContinuationToken` | `application/use_cases/intercept_continuation_token.py` | `ReplyLanguageResolverPort`, `TranslationPort`, `ContinueMessageConfigRepositoryPort` |
| `AcknowledgeFileUpload` | `application/use_cases/acknowledge_file_upload.py` | `ReplyLanguageResolverPort`, `TranslationPort`, `FileUploadAckConfigRepositoryPort` |
| `ProcessLeadSubmission` | `application/use_cases/process_lead_submission.py` | `ConversationEnginePort` (reused, no new port) |
| `UploadKnowledgeDocument` | `application/use_cases/upload_knowledge_document.py` | `BlobStoragePort`, `SearchIndexerTriggerPort` |
| `IndexKnowledgeDocument` | `application/use_cases/index_knowledge_document.py` | `SearchIndexerControlPort` (distinct from `SearchIndexerTriggerPort` — that one enqueues the Celery job, this one is what runs inside it) |

`flag_revision_or_reintervention_price_request` deliberately got **no** use case — it's a pure LLM signal with no business rule behind it (see `adapters/inbound/llm_tools/flag_revision_or_reintervention_price_request_tool.py`); the real behavior lives in `azure_openai.py`'s orchestration, not decomposed yet.

This covers the full original 14-item use-case list identified at the start of the migration. `flag_emotional_distress` and `flag_minor_patient` (`adapters/inbound/llm_tools/`) were added afterward, same pure-signal shape as `flag_revision_or_reintervention_price_request` — all 5 tools from `azure_tools.py` now have hexagonal equivalents. Not built, deliberately: `GenerateConversationalReply`'s internal decomposition (see below).

Every outbound adapter that's tenant-specific config (Zoho screenname/server_uri, business hours, price-catalog index, greeting text, continue-token message, file-upload ack message, search indexer name) reads from its own file under `config/tenants/{tenant_id}/` — one concern per file (`tenant.yaml`, `zoho.yaml`, `business_hours.yaml`, `price_catalog.yaml`, `search_indexer.yaml`, `greeting.txt`, `continue_message.txt`, `file_upload_ack_message.txt`), deliberately not consolidated into one config blob. Secrets (Zoho access token, Azure AI Search API key, Azure Blob connection string) go through `SecretsPort` (`EnvFileSecretsAdapter` today, keyed as `zoho-access-token-{tenant_id}` / `azure-search-api-key-{tenant_id}` / `azure-blob-connection-string-{tenant_id}`), never through the YAML files.

**Dead/broken legacy code found while porting** (flagged, left untouched — not asked to clean it up): `services/chat/zoho_flow_processor.py::process_flow_lead_async` is never called (the real path is `flow_handler.py::handle_flow_lead` → `process_zoho_flow_lead` directly) and calls that function with a `zoho_client` kwarg it doesn't accept — would `TypeError` if it ever ran. `web/utils/file_validators.py::sanitize_filename` is defined but never called either.

**Blocking-I/O fixes, three so far, two different techniques**: `LookupProcedurePrice`'s Azure Search call (`requests`→`httpx`, since `httpx` was already a dependency) vs. `UploadKnowledgeDocument`'s Azure Blob calls and `IndexKnowledgeDocument`'s Azure Search indexer calls (both wrapped in `asyncio.to_thread` instead, since their async SDK variants need `aiohttp`, confirmed not installed, and adding it just for this wasn't judged worth a new dependency).

`Tenant.country` is an ISO 3166-1 alpha-2 code (`"ES"`), not a display name — needed as-is by the `holidays` library in `CheckBusinessAvailability`.

### Composition root (`app/composition_root.py`)

One `build_<use_case>()` function per use case, assembling real adapters for a given `tenant_id`. Several accept override params (`chat_platform`, `rag_runner`, `compress_fn`) so tests can substitute fakes for the pieces that would otherwise hit real Zoho/Azure OpenAI over the network. `CONFIG_DIR` points at `app/config/tenants`.

### Production files touched (backward-compatible only)

Two existing production files got a minimal, additive change each — both needed because a use case built this session would otherwise read conversation history from a different Redis key than the tenant-scoped one (`session:{tenant_id}:{session_id}` vs. the legacy `session:{session_id}`), silently breaking multi-turn memory:
- `services/cloud/azure/azure_openai.py::run_conversation_with_rag` — added optional `history: list | None = None` param; `None` (every current call site) preserves the exact old self-fetch behavior. Later got a second, separate additive param on the same function: `tool_overrides: dict | None = None` (see "Sync/async bridge" below) — still `None` for every current call site, so still zero behavior change in production.
- `core/utils/resolve_reply_language.py::resolve_reply_language` — same `history` pattern, same reasoning.

No other production file has been modified. `app/main.py` and all live routing are untouched.

### Testing

No test suite existed before this migration. Added:
- `requirements-dev.txt` (`-r requirements.txt` + `pytest`, `pytest-asyncio`) — kept separate from `requirements.txt`, not installed in the production Docker image (`.dockerignore` excludes `tests/`, `pytest.ini`, `conftest.py`, `requirements-dev.txt`).
- `pytest.ini` (`asyncio_mode = auto`) + root `conftest.py` (empty — needed so `app/`, which has no `app/__init__.py`, resolves on `sys.path` during test collection).
- `tests/` mirrors `app/`'s structure. Ports are tested with small hand-written fakes (no mocking library needed — they're `Protocol`s). A few adapters are tested against real local infra instead of being faked: `RedisConversationHistoryAdapter` against the real local Redis container (`127.0.0.1:6379`), the `Filesystem*ConfigRepository` adapters against the real `config/tenants/agb/` files.
- Run: `.venv/bin/pytest tests/ -q`.
- Known gap: adapters wrapping real paid/networked services with no local equivalent (`ZohoChatPlatformAdapter`, `AzureSearchPriceCatalogAdapter`, `run_conversation_with_rag` itself) aren't exercised against the real service in the automated suite — correctness verified by inspection against the legacy implementation instead. `run_conversation_with_rag` additionally can't even be *imported* locally without stubbing `pyodbc` first (see "Prompt-tuning session status" below) — untouched pre-existing limitation.

### Sync/async bridge for the LLM tools (resolved for 3 of the 5 tools)

`run_conversation_with_rag`'s tool-dispatch loop now accepts an optional `tool_overrides: dict | None = None` param. All 5 tool branches (`is_customer_service_available`, `procedures_and_treatments_price_list`, `flag_revision_or_reintervention_price_request`, `flag_emotional_distress`, `flag_minor_patient`) check for an override before falling back to the legacy sync `azure_tools.X` function — every side effect that reads `function_response` or sets a flag afterward (`revision_price_requested`, `emotional_distress_detected`, `minor_safety_concern`, the price-ambiguity `len(results) > 1` check) is untouched, since both paths produce the same JSON shape.

`AzureOpenAIConversationEngineAdapter` builds `tool_overrides` fresh on every `generate_reply` call (binding that call's `tenant_id`). The 3 flag tools (`flag_revision_or_reintervention_price_request`, `flag_emotional_distress`, `flag_minor_patient`) need no dependencies and are always included unconditionally. `is_customer_service_available` and `procedures_and_treatments_price_list` are the only 2 actually gated behind optional constructor deps (`check_business_availability`, `get_lookup_procedure_price`), because they need tenant-bound state — `check_business_availability` is a plain shared instance (free to construct, no caching needed) while `get_lookup_procedure_price` is an async per-tenant factory (that use case's search adapter needs a secret + config fetch, so rebuilding it per *message* instead of per *tenant* would refetch both on every single chat turn).

**Per-tenant caching in the composition root**: `_get_or_build_for_tenant(cache_key, tenant_id, builder)` (dict + `asyncio.Lock`, double-checked locking) backs `get_cached_lookup_procedure_price` and `get_cached_chat_platform` — the latter fixing the exact same "rebuilt every message" issue that existed for `ZohoChatPlatformAdapter` in `build_process_incoming_message`, found and fixed at the same time. `build_process_incoming_message`/`build_process_lead_submission` both expose `check_business_availability`/`get_lookup_procedure_price` as overridable params (same reasoning as their other override params — lets tests avoid real secret fetches).

### Prompts and disambiguation/safety rules moved to per-tenant config

The 4 channel prompts (`WEBSITE_ASSISTANT_PROMPT`, `WHATSAPP_ASSISTANT_PROMPT`, `INSTAGRAM_ASSISTANT_PROMPT`, `FLOW_FORM_ASSISTANT_PROMPT`) and `MINOR_SAFETY_RULE`/`DISAMBIGUATION_RULES` now also live as data files under `config/tenants/agb/prompts/`, extracted verbatim from `constants.py`. **Split by file format, deliberately not uniform** (researched against 2026 community practice, not guessed):
- Channel prompts → **YAML** (`website.yaml`, `whatsapp.yaml`, `instagram.yaml`, `flow.yaml`, each a `template:` key) — engineering-owned prompt-engineering artifacts; YAML is the current production standard for prompt storage, and specifically what LangChain's native `load_prompt` expects, which matters given the planned LangChain/LangGraph migration of the RAG engine.
- The two rule blocks → **Markdown** (`minor_safety_rule.md`, `disambiguation_rules.md`) — business/legal-owned content (sourced externally as plain text today), where YAML's quoting/escaping rules would be a hazard for a non-technical editor; Markdown has none of that.

`FilesystemPromptConfigRepository` (`PromptConfigRepositoryPort`) reads the channel YAML plus both `.md` rule files and does the same `<<MINOR_SAFETY_RULE>>`/`<<DISAMBIGUATION_RULES>>` substitution `constants.py` does at import time — `{reply_language}` is left in place for `run_conversation_with_rag` to `.format()` per turn, same as today.

`run_conversation_with_rag` accepts an optional `base_prompt_override: str | None = None` (same additive pattern as `history`/`tool_overrides`) — `None` (every current call site) preserves the exact legacy `get_base_prompt_by_channel(channel)` behavior. `AzureOpenAIConversationEngineAdapter` fetches this fresh per call via an optional `prompt_config` dependency when given (not cached — it's a local file read, cheap enough to redo every turn, unlike the price-lookup tool's secret fetch).

**Known drift risk, deliberate and temporary**: `constants.py` still has the original strings (still what legacy code uses by default) — the new files are a second copy of the same ~45K characters of business/legal content. Editing one without the other silently desyncs them. Not resolved yet — Erik's rollout plan is to validate this in a test environment first; only after that does the config-file version become primary in prod, with `constants.py` kept as backup, so both copies are meant to coexist for now.

### `app/config/settings.py` — shared technical config

Closes the last of the 4 config/secrets/constants categories planned early in this migration. Holds values that are shared across all tenants and aren't secrets: `ALLOWED_EXTENSIONS`, `MAX_FILE_SIZE_MB`, `ALLOWED_MIME_TYPES`, `MIN_LANG_DETECTION_LEN`, `INSTAGRAM_CHARACTER_LIMIT`, `FALLBACK_MESSAGE`, `LANGUAGE_DISPLAY_NAMES` — each verified programmatically equal to its `constants.py` counterpart before being treated as migrated. `composition_root.py` reads from here now instead of `constants.py` (safe: it has no production callers yet). `constants.py` itself is untouched, same reasoning as the prompts (see above) — duplication is fine during the not-yet-cut-over window.

### Known gaps / not yet done

- **`GenerateConversationalReply` isn't decomposed.** `ConversationEnginePort`'s real implementation (`AzureOpenAIConversationEngineAdapter`) wraps the entire `run_conversation_with_rag` as one opaque unit rather than breaking its internals (prompt building, tool loop, language enforcement, content-filter fallback) into their own pieces. Deliberate, to avoid risking the carefully-tuned behavior documented below.
- **Legacy `SessionMemoryRedis` fallback paths.** Both production files touched above fall back to the old non-tenant-scoped Redis reads when no `history` is passed — true for every current caller. These fallback branches (and `SessionMemoryRedis` itself) become removable dead code once production is fully cut over to the new use cases.
- Redis is planned to move to a different provider later (unrelated to this migration, mentioned by Erik in passing) — `RedisConversationHistoryAdapter`'s connection is fully injected (`redis_url` param) specifically so that's a config change, not a rewrite, when it happens.

## Prompt-tuning session status (as of 2026-08-24)

Erik hand-wrote 12 manual test cases to validate `DISAMBIGUATION_RULES`/`MINOR_SAFETY_RULE` end to end. They were run locally against `run_conversation_with_rag` directly (bypassing Zoho/webhooks entirely) using the repo's `.venv` — importing `app.services.cloud.azure.azure_openai` requires stubbing `pyodbc` in `sys.modules` first (no `libodbc.so.2` installed locally, and it's only needed lazily by `azure_tools.ensure_users_table`, unrelated to chat), and real multi-turn/session tests need the local Docker Redis container reachable by overriding `REDIS_URL_LOCAL=redis://127.0.0.1:6379` before `SessionMemoryRedis()` is constructed (the default `redis_local` hostname only resolves inside docker-compose's network). `app.core.config` must **not** be imported for this (it hard-requires `AZURE_CLIENT_ID`/`AZURE_TENANT_ID`, not set in the local `.env`) — the RAG path doesn't need it.

**8/12 passed clean**: abdomen ambiguo, celulitis infecciosa, pérdida de peso general, piernas ambiguo, síndrome de Poland (determinista), and (after today's fixes) labios ambiguo + antecedente/revisión.

**Fixed today (commit `32e9de3`)**:
- **Antecedente de cirugía previa — insatisfacción sin verbo explícito**: added a "SEÑAL REFORZADA" block to `DISAMBIGUATION_RULES` so phrases like "no quedé contenta/satisfecha con el resultado" count as a prior-surgery signal on their own, without needing an explicit verb like "me operé". Verified in Spanish **and English** (confirms the pre-translation-to-Spanish step in `azure_openai.py` before the message ever reaches the LLM makes Spanish-only example phrases work across languages by construction).
- **Labios ambiguo → price given before disambiguation**: asking "quiero arreglarme los labios" (no zone) was quoting prices for *both* matching catalog procedures (aumento de labios vs. labioplastia) before asking which one. Fixed with a new general principle (`DISAMBIGUATION_RULES` "PRINCIPIOS GENERALES" #10, deliberately generalized beyond labios — applies to any term matching multiple catalog procedures): ask first, give price only after the patient clarifies. Verified with a real multi-turn conversation (Redis-backed): clarifying "zona íntima" correctly returns the labioplastia price (2.783€); clarifying "boca" correctly still withholds a price because that sub-answer itself has two distinct catalog products (relleno vs. Lip Lift) — left as-is per Erik, not considered a bug.

**Tried and explicitly reverted (Erik's call, not a dead end to avoid — revisit differently)**:
- **Liposucción sin zona**: "me interesa la lipo" (and similar) doesn't ask which body zone (there's no single-price "liposucción" item in the catalog, only 6 zone-specific ones) — reproducible 3/3, prompt-only instruction isn't reliable here (same "lost in the middle" pattern as the revision-pricing and pecho-en-hombres fixes). Two code fixes were built and verified working, then reverted at Erik's request: (1) a check inside `procedures_and_treatments_price_list` itself — rejected as "contaminating" a generic shared tool with one business case's logic; (2) a dedicated `flag_liposuction_without_zone` tool (same pattern as `flag_revision_or_reintervention_price_request`) plus a generalized `azure_tools.DETERMINISTIC_FALLBACK_TOOLS` registry in `azure_openai.py` (so future cases like this wouldn't need a new boolean flag + new `elif` branch each time) — this also worked (3/3) but was reverted anyway. **Erik's preferred direction instead: fix it at the data layer** — the price-list Azure AI Search index has a `synonyms` field per procedure (backed by a Solr-format synonym map, see next section); the plan is to edit that instead of adding application code. Not yet done.

**Diagnosed, not yet fixed**:
- **Nariz funcional ("...me cuesta respirar...") and pecho en hombres ("soy hombre y quiero operarme el pecho") both get blocked by Azure OpenAI's own content filter** (`BadRequestError`, `ResponsibleAIPolicyViolation`) before the model ever reasons about the disambiguation rules — confirmed reproducible 2/2 for each exact phrase, and confirmed via isolated probing (`extra_body.data_sources` off, `tools` toggled on/off) that **the trigger is specifically the presence of the `tools` parameter in the completion call** (categories: `self_harm`/medium for the nariz case, `sexual`/medium for the pecho case; the same messages pass cleanly with `tools` omitted). This means the pecho-en-hombres prompt reordering fix (see `DISAMBIGUATION_RULES` section above) is correct but never gets a chance to run for this exact phrasing in production. No fix implemented yet; the idea on the table is retrying once without `tools` when a content-filter `BadRequestError` is caught, before falling back to `CONTENT_FILTER_FALLBACK_MESSAGE`.
- **Angustia emocional**: the model does briefly acknowledge distress ("entiendo que te sientas así...") but then continues in the same turn into a normal procedure/price rundown instead of pausing on validation + recommending professional assessment first, as the rule intends. Reproducible 3/3 across phrasing variants. No fix attempted yet.
- **Price-list search relevance bug** (found incidentally, unrelated to the 12 cases): `procedures_and_treatments_price_list` (`azure_tools.py`) posts `{"search": query_str, "count": true}` to Azure AI Search with no `searchMode`, `top`, or `searchFields` — so for a query like "liposucción de abdomen" it returns **~40 barely-related results** (bótox, ginecomastia, etc.), not just the matching zone. Likely caused by the default `searchMode=any` (OR-matching, so common words/stopwords partially match almost everything) with no result cap and no `searchFields` restriction (so it searches every searchable field, including unrelated `metadata_storage_*` fields). The LLM, faced with that much noise, tends to avoid quoting the correct price even though it's in the results. Not investigated further; not fixed.

### Azure AI Search config notes (from live inspection, 2026-08-24)

Both the "on your data" RAG grounding (`AZURE_AI_SEARCH_INDEX`) and the price-list lookup (`AZURE_AI_SEARCH_PRICE_LIST_INDEX`, index name `rag-structured-data-3-large`) live on the **same** Azure AI Search service, `agb-search.search.windows.net` (== `AZURE_AI_SEARCH_ENDPOINT`) — inspected via `GET /indexes/{name}` and `GET /synonymmaps/{name}` with `AZURE_AI_SEARCH_API_KEY` (an admin key: it can read/write index and synonym-map config, not just query). The price-list index has no scoring profiles, default BM25 similarity, and one Solr-format synonym map (`sinonimos-agb-es`) attached — but only to the `procedure_id` field, not `procedure_name` or the index's own `synonyms` field, which is where the actual per-procedure synonym lists (e.g. "quitar rollitos, quitar michelines" → `liposuccion_de_flancos`) live as plain index data rather than as synonym-map entries.

### Next session: standalone MCP repo for Azure AI Search debugging

Plan (not started): a **new, separate git repo** (not inside `AngelBotBackend`) for MCP servers, first one wrapping this Azure AI Search service so it can be inspected/debugged directly (index defs, synonym maps, raw search queries with full control over `searchMode`/`top`/`searchFields` to reproduce the relevance bug above) instead of one-off `curl`/Python scripts. Decisions made so far:
- **Framework**: Python **FastMCP** (`pip install fastmcp`, the `gofastmcp.com` package — not the TypeScript `punkpeye/fastmcp`, which doesn't support the transport below).
- **Transport**: Streamable HTTP in **stateless mode** (`mcp.http_app(stateless_http=True)`), targeting the **2026-07-28 MCP spec** (still a release candidate as of this session) — no `initialize` handshake or `Mcp-Session-Id`, routing via `Mcp-Method`/`Mcp-Name` headers instead, which also makes it directly testable with plain HTTP POST requests from Postman (no session/cookie juggling), while still being callable by an LLM MCP client later.
- **Server-side auth to Azure Search**: still open — admin key (already in `.env`, needed anyway if a synonym-map-editing tool is added) vs. a read-only query key (safer if the MCP stays inspection-only). Erik hasn't decided.
- **MCP-server's own auth** (protecting the HTTP endpoint itself, separate from the Azure key): FastMCP supports `StaticTokenVerifier` (bearer token) for dev — not yet chosen/configured.
- **Scope of tools**: not finalized, but likely candidates: list/get index definitions, get/list synonym maps (+ maybe update, for the liposucción-sin-zona data-layer fix above), and a raw/parametrized search call.
- Caution for next session: **installing `fastmcp` must go in its own venv**, not the main `AngelBotBackend/.venv` — doing that once already upgraded `starlette` to 1.6.0 and broke the pin FastAPI needs (`starlette<0.48.0,>=0.40.0`), plus bumped `pyjwt` past what `redis-entraid` wants; had to be force-reinstalled back to the pinned versions. No MCP-related files or dependencies actually landed in this repo or its venv — clean as of this commit.
