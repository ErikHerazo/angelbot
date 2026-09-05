# AngelBot Backend

Microservicio FastAPI que impulsa **Aesthea**, el asistente virtual multilingüe de Antiaging Group Barcelona (clínica de medicina y cirugía estética). Recibe webhooks de Zoho SalesIQ (chat en vivo) y Zoho Flow (formularios web), ejecuta un pipeline RAG contra Azure OpenAI + Azure AI Search, y envía la respuesta generada de vuelta a Zoho de forma asíncrona.

## Arquitectura, en breve

1. **Webhook único** (`POST /api/chat/webhook`) recibe eventos de ambos productos de Zoho, valida la firma según el origen (RSA para SalesIQ, HMAC para Flow), y los normaliza a un modelo `ChatEvent` común.
2. **Procesamiento asíncrono**: para mensajes de chat, la API responde de inmediato con un payload "pending" mientras el trabajo real corre en background (RAG + tool calling puede exceder el timeout del webhook de Zoho), y el resultado final se envía por un callback POST a la API de Zoho.
3. **RAG**: cada turno se resuelve contra Azure OpenAI (con tool calling y grounding directo sobre un índice de Azure AI Search) para responder dudas sobre tratamientos, precios y disponibilidad.
4. **Idioma de respuesta determinista**: el idioma en el que responde el bot se detecta por código (Azure Translator), no lo infiere el LLM — con una capa de refuerzo y una red de seguridad final que corrige la respuesta si el modelo se desvía. Ver detalle en `CLAUDE.md`.
5. **Memoria de sesión** en Redis (TTL 15 min) para mantener contexto de conversación por sesión.
6. **Indexación de precios**: los documentos de precios se suben vía un panel admin (Blob Storage) y disparan un job de Celery que reindexa Azure AI Search.

Para el mapa completo de módulos, flujo de datos exacto y decisiones de diseño, ver [`CLAUDE.md`](./CLAUDE.md).

> **En progreso**: migración a arquitectura hexagonal (ports & adapters) con soporte multi-tenant, en la rama `feature/hexagonal-architecture-migration`. Es aditiva — nada de esto reemplaza todavía el flujo descrito arriba, que sigue siendo el que atiende tráfico real. Detalle completo en la sección "Hexagonal architecture migration" de `CLAUDE.md`.

## Requisitos

- Python 3.13
- Docker + Docker Compose (recomendado para correr el stack completo)
- Cuentas/recursos de Azure: OpenAI, AI Search, Translator, Blob Storage, SQL (opcional)
- Redis (local vía Docker, o Azure Redis Enterprise en producción)
- Credenciales de Zoho SalesIQ y Zoho Flow

## Configuración

La app carga variables de entorno desde `/app/.env` (ruta fija en `app/core/config.py`, pensada para el layout del volumen de Docker). Para correr localmente sin Docker, asegúrate de que un `.env` sea accesible en esa ruta, o ajusta `config.py`.

```bash
cp .env.example .env
# completa las credenciales de Azure, Redis, Zoho y SQL
```

`.env.example` trae un set mínimo; el `.env` real (gitignored) necesita además credenciales de Redis, Zoho, SQL Server y Blob Storage — revisa `os.getenv(` en `app/` para el listado completo. Si falta alguna variable crítica de Azure/Celery, `config.py` lanza un `RuntimeError` al arrancar.

## Correr en local (sin Docker)

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Correr el stack completo (API + Celery + Redis + ngrok)

```bash
docker-compose up --build
```

Esto levanta:
- `app` — la API FastAPI (puerto 8000)
- `celery-worker` — worker de Celery (necesario para el job de reindexado de Azure Search)
- `redis` — Redis local (puerto 6379)
- `ngrok` — túnel para exponer el webhook a Zoho durante desarrollo

Para correr el worker de Celery solo:

```bash
celery -A app.tasks.celery worker --loglevel=info
```

## Tests

No hay linter ni build step configurado. Los archivos `test_*.py` bajo `app/services/**` son scripts manuales (sin asserts/pytest) para verificar una conexión puntual, pensados para correrse directamente:

```bash
python -m app.services.cache.test_session_memory
python -m app.services.db.test_connection
python -m app.test_hexagonal_chat  # chatea en la terminal contra el pipeline hexagonal nuevo, sin Zoho
```

Para el código nuevo de la migración a arquitectura hexagonal (`app/domain/`, `app/application/`, `app/adapters/`) sí hay una suite real con `pytest`:

```bash
pip install -r requirements-dev.txt
pytest tests/ -q
```

Algunos tests usan el Redis local real (`127.0.0.1:6379`, levantado vía `docker-compose up redis` o similar) en vez de mocks. `requirements-dev.txt` se mantiene fuera de la imagen Docker de producción (ver `.dockerignore`).

## Estructura del proyecto

```
app/
├── api/routes/        # Endpoint del webhook de Zoho
├── core/               # Config, constantes (prompts por canal), utilidades compartidas
├── services/
│   ├── chat/           # Parsers, router de eventos, handlers, casos de uso
│   ├── cloud/azure/     # Azure OpenAI, AI Search, Translator, Blob Storage
│   ├── cache/           # Memoria de sesión en Redis
│   ├── db/              # Conexión a Azure SQL
│   └── zoho/            # Cliente de Zoho SalesIQ
├── tasks/               # Celery app y tasks (reindexado de Azure Search)
├── web/                 # UI de administración (upload de precios) y página de prueba de chat
├── main.py              # Entry point de FastAPI (todo lo de arriba es lo que este archivo usa hoy)
│
│   # --- migración a hexagonal, en progreso, aditiva, aún no usada por main.py ---
├── domain/              # Entidades y value objects — puros, sin dependencias de infraestructura
├── application/         # Casos de uso + puertos (interfaces)
├── adapters/
│   ├── inbound/         # Tools del LLM, formatters de respuesta de Zoho
│   └── outbound/        # Implementaciones concretas: Zoho, Redis, Azure OpenAI/Search/Translator
├── config/tenants/agb/  # Config de AGB por archivo (fiscal, Zoho, horarios, precios, textos fijos)
└── composition_root.py  # Arma los casos de uso con adapters reales, por tenant
```

Detalle de qué existe hoy en cada carpeta nueva, con qué puertos y con qué queda pendiente: sección "Hexagonal architecture migration" en [`CLAUDE.md`](./CLAUDE.md).

## Licencia

Propietario — uso interno de Antiaging Group Barcelona.
