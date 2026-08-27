"""
Prueba manual (no pytest) para el bug de "liposuccion sin zona": el
usuario pide info/precio de liposuccion sin indicar la zona corporal, y el
bot debe preguntar la zona ANTES de dar precio o informacion especifica de
una zona (no hay un precio general de "liposuccion" en el catalogo, solo
precios por zona: abdomen, flancos, brazos, espalda, miembro inferior,
cervical/papada).

IMPORTANTE: run_conversation_with_rag() por si sola NO guarda el
historial de la conversacion en Redis -- eso lo hace la capa de arriba
(app/web/routes/chat_test.py o process_zoho_message.py). Para probar
flujos de varios turnos hay que replicar ese guardado aqui (ver
ask_and_save), si no cada "turno 2" se ejecuta sin memoria real del turno
anterior y los resultados no son representativos de una conversacion real.

Requiere el .env real del proyecto (credenciales de Azure/Redis) y conexion
a internet. Usa las mismas credenciales que usaria el contenedor en
produccion (APP_ENV=prod), igual que testing/test_content_filter_fallback.py.

Ejecutar desde la raiz del proyecto:
    source .venv/bin/activate
    python3 testing/test_liposuction_gate.py
"""

import re
import sys
import types
import asyncio
import uuid
import logging
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

_fake_connection = types.ModuleType("app.services.db.connection")
_fake_connection.get_connection = lambda *a, **kw: (_ for _ in ()).throw(
    RuntimeError("stub: no deberia llamarse en este test")
)
sys.modules["app.services.db.connection"] = _fake_connection

sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(message)s")

from app.services.cloud.azure.azure_openai import run_conversation_with_rag, session_memory  # noqa: E402

PRICE_PATTERN = re.compile(r"\d[\d.,]*\s*(€|eur|euros)", re.IGNORECASE)


async def ask_and_save(session_id: str, question: str, channel: str = "website"):
    """Replica el guardado de historial que hace chat_test.py, para que
    los turnos siguientes tengan memoria real de la conversacion."""
    answer = await run_conversation_with_rag(
        session_id=session_id, user_question=question, channel=channel, visitor_language=None
    )
    history = await session_memory.get_session(session_id)
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})
    await session_memory.save_session(session_id, history)
    return answer


async def main():
    print("\n=== TURNO 1 (sin zona) x3 ===")
    for i in range(3):
        sid = f"testing-{uuid.uuid4()}"
        a = await ask_and_save(sid, "¿Cuánto cuesta una liposucción?")
        no_price = not PRICE_PATTERN.search(a)
        print(f"  run{i+1}: sin_precio={no_price} -> {a[:120]}")

    print("\n=== CONTROL (zona en el mismo mensaje) x3 ===")
    for i in range(3):
        sid = f"testing-{uuid.uuid4()}"
        a = await ask_and_save(sid, "Quiero hacerme una liposucción de abdomen, cuánto cuesta")
        gave_price = bool(PRICE_PATTERN.search(a))
        print(f"  run{i+1}: dio_precio={gave_price} -> {a[:120]}")

    print("\n=== TURNO 2 (zona sola, con historial real) ===")
    for resp in ["abdomen", "de abdomen", "flancos", "brazos", "espalda", "la zona del abdomen"]:
        sid = f"testing-{uuid.uuid4()}"
        await ask_and_save(sid, "¿Cuánto cuesta una liposucción?")
        a2 = await ask_and_save(sid, resp)
        gave_price = bool(PRICE_PATTERN.search(a2))
        print(f"  respuesta={resp!r}: dio_precio={gave_price} -> {a2[:150]}")


if __name__ == "__main__":
    asyncio.run(main())
