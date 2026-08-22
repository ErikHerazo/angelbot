"""
Prueba manual (no pytest) del fallback para el bloqueo de Azure OpenAI por
filtro de contenido (ResponsibleAIPolicyViolation) cuando la conversacion
combina "menor de edad" + "pecho".

Requiere el .env real del proyecto (credenciales de Azure/Redis) y conexion
a internet. No se conecta a Zoho ni a Redis local de Docker: usa las mismas
credenciales que usaria el contenedor en produccion (APP_ENV=prod).

Ejecutar desde la raiz del proyecto:
    source .venv/bin/activate
    python3 testing/test_content_filter_fallback.py
"""

import sys
import types
import asyncio
import uuid
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 1) Cargar el .env real del proyecto ANTES de importar cualquier modulo de
#    la app. app/core/config.py apunta a la ruta fija "/app/.env" (solo
#    valida dentro de Docker) y no se toca aqui; los modulos que sí importa
#    run_conversation_with_rag (azure_openai.py, translate_text.py, etc.)
#    llaman load_dotenv() sin ruta, así que basta con haberlo cargado ya en
#    os.environ para que lo encuentren.
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

# 2) Este entorno local no tiene el driver de sistema unixODBC instalado
#    (libodbc.so.2), asi que app/services/db/connection.py (pyodbc) no
#    importa. Esa dependencia solo la usa azure_tools.ensure_users_table,
#    que no se ejecuta en el camino que estamos probando aqui - se stubea
#    el modulo para no requerir instalar paquetes de sistema.
_fake_connection = types.ModuleType("app.services.db.connection")
_fake_connection.get_connection = lambda *a, **kw: (_ for _ in ()).throw(
    RuntimeError("stub: no deberia llamarse en este test")
)
sys.modules["app.services.db.connection"] = _fake_connection

sys.path.insert(0, str(PROJECT_ROOT))

from app.core import constants  # noqa: E402
from app.services.cloud.azure.azure_openai import run_conversation_with_rag  # noqa: E402


CONTENT_FILTER_MARKER = "consulta@agb.cat"


async def run_case(label: str, user_question: str, channel: str = "website"):
    session_id = f"testing-{uuid.uuid4()}"
    print(f"\n{'=' * 70}\n{label}\nsession_id={session_id}\nmensaje: {user_question!r}\n{'-' * 70}")
    try:
        answer = await run_conversation_with_rag(
            session_id=session_id,
            user_question=user_question,
            channel=channel,
            visitor_language=None,
        )
    except Exception as ex:
        print(f"❌ EXCEPCION NO ATRAPADA: {type(ex).__name__}: {ex}")
        return None

    print(f"Respuesta:\n{answer}")
    return answer


async def main():
    results = {}

    results["control_pecho_adulto"] = await run_case(
        "CONTROL 1: pecho, sin menor (debe responder normal, sin fallback)",
        "Quiero un aumento de pecho, tengo 30 años",
    )

    results["control_menor_sin_pecho"] = await run_case(
        "CONTROL 2: menor, sin pecho (debe responder normal, sin fallback)",
        "Mi hija tiene 10 años y quiere estudiar medicina",
    )

    results["trigger_menor_pecho"] = await run_case(
        "CASO CRITICO: menor + pecho (antes rompia con content_filter; "
        "ahora debe devolver CONTENT_FILTER_FALLBACK_MESSAGE)",
        "Mi hija quiere hacerse un aumento de pecho",
    )

    print(f"\n{'=' * 70}\nRESUMEN\n{'=' * 70}")

    ok = True

    for key in ("control_pecho_adulto", "control_menor_sin_pecho"):
        answer = results[key]
        passed = bool(answer) and CONTENT_FILTER_MARKER not in answer
        ok &= passed
        print(f"[{'OK' if passed else 'FALLO'}] {key}: respuesta normal (sin marcador de fallback)")

    trigger_answer = results["trigger_menor_pecho"]
    trigger_passed = bool(trigger_answer) and CONTENT_FILTER_MARKER in trigger_answer
    ok &= trigger_passed
    print(f"[{'OK' if trigger_passed else 'FALLO'}] trigger_menor_pecho: devolvio el mensaje de fallback (no crasheo)")

    print("\nRESULTADO GLOBAL:", "✅ TODO OK" if ok else "❌ HAY FALLOS")
    return ok


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
