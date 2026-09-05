"""
Script manual (no es pytest, mismo estilo que app/services/**/test_*.py) para
chatear de verdad contra el pipeline hexagonal nuevo (ProcessIncomingMessage),
sin pasar por Zoho -- las respuestas se imprimen en consola en vez de mandarse
a un callback.

Uso:
    python -m app.test_hexagonal_chat

Requisitos:
- Redis local corriendo (REDIS_URL_LOCAL, default redis://127.0.0.1:6379).
- Un .env real en la raíz del repo con credenciales de Azure OpenAI/Translator
  (se carga solo, vía load_dotenv() dentro de los módulos que se importan).
- Opcional: agrega `AZURE_SEARCH_API_KEY_AGB` a tu .env (mismo valor que
  `AZURE_AI_SEARCH_API_KEY`) para que la tool de precios hexagonal
  (LookupProcedurePrice) funcione. Si no la agregas, cada mensaje va a caer
  al fallback_message -- eso es el manejo de errores de ProcessIncomingMessage
  funcionando como se diseñó, no un bug del script.

`pyodbc` se stubea en sys.modules porque no está instalado localmente y solo
lo necesita, de forma perezosa, azure_tools.ensure_users_table (no relacionado
con el chat) -- mismo truco documentado en la sección "Prompt-tuning session
status" de CLAUDE.md.

Escribe "salir" para terminar.
"""
import asyncio
import sys
import types
import uuid

_pyodbc_stub = types.ModuleType("pyodbc")
_pyodbc_stub.Connection = object  # solo se usa como type hint en services/db/connection.py
sys.modules.setdefault("pyodbc", _pyodbc_stub)

from app.composition_root import build_process_incoming_message
from app.core.logging.structured_logger import get_logger

log = get_logger(__name__)

TENANT_ID = "agb"


class ConsoleChatPlatform:
    async def send_progress_update(self, request_id: str) -> None:
        with log.operation(request_id=request_id):
            print("... generando respuesta ...")

    async def send_final_response(self, request_id: str, answer_text: str) -> None:
        with log.operation(request_id=request_id, answer_length=len(answer_text)):
            print(f"\nAesthea: {answer_text}\n")


async def main():
    session_id = str(uuid.uuid4())
    print(f"Sesión: {session_id} (tenant: {TENANT_ID}) -- escribe 'salir' para terminar\n")

    use_case = await build_process_incoming_message(
        TENANT_ID,
        chat_platform=ConsoleChatPlatform(),
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
