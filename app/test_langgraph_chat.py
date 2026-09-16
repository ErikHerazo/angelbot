"""
Script manual (no es pytest, mismo estilo que app/test_hexagonal_chat.py) para
chatear de verdad contra el nuevo agente LangGraph (orchestrator + 4 ramas:
retrieval/agenda/direct/flow), sin pasar por Zoho -- las respuestas se
imprimen en consola.

A diferencia de app/test_hexagonal_chat.py, este usa LangGraphConversationEngineAdapter
en vez de AzureOpenAIConversationEngineAdapter -- los completions corren contra
Claude (Sonnet 5 vía Microsoft Foundry) en vez de Azure OpenAI, y la búsqueda de
precios/base de conocimiento pasa por clinyq-mcp-azure-search (HTTP), no por
run_conversation_with_rag.

Uso:
    python -m app.test_langgraph_chat

Requisitos:
- Redis local corriendo (REDIS_URL_LOCAL, default redis://127.0.0.1:6379).
- clinyq-mcp-azure-search corriendo y accesible en MCP_AZURE_SEARCH_URL
  (default http://localhost:8931/mcp) -- ver ~/Documentos/clinyq-workspace/clinyq-mcp-azure-search,
  `docker compose up -d --build`.
- Un .env real en la raíz del repo con AZURE_FOUNDRY_CLAUDE_API_KEY_AGB, AZURE_TRANSLATOR_*
  (se carga solo, vía load_dotenv() dentro de los módulos que se importan).

`pyodbc` se stubea igual que en test_hexagonal_chat.py (no relacionado con el chat).

Escribe "salir" para terminar.
"""
import asyncio
import sys
import types
import uuid

_pyodbc_stub = types.ModuleType("pyodbc")
_pyodbc_stub.Connection = object
sys.modules.setdefault("pyodbc", _pyodbc_stub)

from app.composition_root import build_langgraph_conversation_engine, build_process_incoming_message
from app.core.logging.structured_logger import get_logger

log = get_logger(__name__)

TENANT_ID = "agb"


class ConsoleChatPlatform:
    async def send_progress_update(self, request_id: str) -> None:
        with log.operation(request_id=request_id):
            print("... generando respuesta (langgraph) ...")

    async def send_final_response(self, request_id: str, answer_text: str) -> None:
        with log.operation(request_id=request_id, answer_length=len(answer_text)):
            print(f"\nAesthea (langgraph): {answer_text}\n")


async def main():
    session_id = str(uuid.uuid4())
    print(f"Sesión: {session_id} (tenant: {TENANT_ID}, engine: langgraph) -- escribe 'salir' para terminar\n")

    use_case = await build_process_incoming_message(
        TENANT_ID,
        chat_platform=ConsoleChatPlatform(),
        conversation_engine=build_langgraph_conversation_engine(),
    )

    while True:
        user_question = input("Tú: ").strip()
        if user_question.lower() in {"salir", "exit", "quit"}:
            break
        if not user_question:
            continue

        await use_case.execute(
            tenant_id=TENANT_ID,
            request_id=str(uuid.uuid4()),
            session_id=session_id,
            user_question=user_question,
            channel="website",
        )


if __name__ == "__main__":
    asyncio.run(main())
