"""
Prueba deterministica (no depende de si Azure decide o no filtrar el
contenido esta vez) del manejo de errores content_filter en
azure_openai.py::run_conversation_with_rag.

En testing/test_content_filter_fallback.py (prueba en vivo) se vio que el
filtro de Azure NO es determinista: la misma pregunta ("Mi hija quiere
hacerse un aumento de pecho") a veces lo dispara y a veces no - cuando no
lo dispara, el LLM ya maneja bien el caso solo con las reglas del prompt
(ver resultado de esa prueba). Este script fuerza el error exacto que se
vio en produccion (capturado el 2026-08-22) para verificar que, CUANDO
Azure SI bloquea, el codigo de app/services/cloud/azure/azure_openai.py
lo atrapa y responde con CONTENT_FILTER_FALLBACK_MESSAGE en vez de
propagar la excepcion (que antes caia en el fallback generico en ingles
de process_zoho_message.py).

Ejecutar desde la raiz del proyecto:
    source .venv/bin/activate
    python3 testing/test_content_filter_mock.py
"""

import sys
import types
import asyncio
import uuid
from pathlib import Path
from unittest.mock import patch

import httpx
from dotenv import load_dotenv
from openai import BadRequestError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

_fake_connection = types.ModuleType("app.services.db.connection")
_fake_connection.get_connection = lambda *a, **kw: (_ for _ in ()).throw(
    RuntimeError("stub: no deberia llamarse en este test")
)
sys.modules["app.services.db.connection"] = _fake_connection

sys.path.insert(0, str(PROJECT_ROOT))

from app.core import constants  # noqa: E402
import app.services.cloud.azure.azure_openai as azure_openai_module  # noqa: E402


# Cuerpo real capturado en el log de produccion el 2026-08-22 cuando Azure
# bloqueo la pregunta "Mi hija quiere hacerse un aumento de pecho".
REAL_AZURE_CONTENT_FILTER_BODY = {
    "error": {
        "requestid": "548c3fa2-4468-440e-b33f-bf89bdd6c787",
        "code": 400,
        "message": {
            "error": {
                "message": (
                    "The response was filtered due to the prompt triggering "
                    "Azure OpenAI's content management policy."
                ),
                "type": None,
                "param": "prompt",
                "code": "content_filter",
                "status": 400,
                "innererror": {
                    "code": "ResponsibleAIPolicyViolation",
                    "content_filter_result": {
                        "hate": {"filtered": False, "severity": "safe"},
                        "jailbreak": {"detected": False, "filtered": False},
                        "self_harm": {"filtered": False, "severity": "safe"},
                        "sexual": {"filtered": True, "severity": "high"},
                        "violence": {"filtered": False, "severity": "safe"},
                    },
                },
            }
        },
    }
}


def make_fake_content_filter_error() -> BadRequestError:
    fake_request = httpx.Request("POST", "https://azure-openai-angelbot-main.openai.azure.com/fake")
    fake_response = httpx.Response(400, request=fake_request, json=REAL_AZURE_CONTENT_FILTER_BODY)
    return BadRequestError(
        message=str(REAL_AZURE_CONTENT_FILTER_BODY),
        response=fake_response,
        body=REAL_AZURE_CONTENT_FILTER_BODY,
    )


async def run_case(user_question: str, visitor_language: str | None, label: str) -> bool:
    session_id = f"testing-mock-{uuid.uuid4()}"
    fake_error = make_fake_content_filter_error()

    print(f"\n{'=' * 70}\n{label}\n{'-' * 70}")

    with patch.object(azure_openai_module, "make_completion", side_effect=fake_error):
        try:
            answer = await azure_openai_module.run_conversation_with_rag(
                session_id=session_id,
                user_question=user_question,
                channel="website",
                visitor_language=visitor_language,
            )
        except Exception as ex:
            print(f"❌ FALLO: la excepcion se propago en vez de ser atrapada: {type(ex).__name__}: {ex}")
            return False

    print(f"Respuesta devuelta:\n{answer}\n")

    # En español debe coincidir exactamente (translate_text no traduce si
    # from_lang == to_lang); en otro idioma solo verificamos que ya NO esté
    # en español (traducción real ocurrió) y conserve el contacto de la
    # clínica intacto (la regla del prompt exige no alterar el email/link).
    expected = constants.CONTENT_FILTER_FALLBACK_MESSAGE
    if visitor_language in (None, "es"):
        passed = answer.strip() == expected.strip()
    else:
        passed = (
            bool(answer)
            and answer.strip() != expected.strip()
            and "consulta@agb.cat" in answer
            and "agendar-cita" in answer
        )

    print("✅ OK" if passed else "❌ FALLO", "-", label)
    return passed


async def main() -> bool:
    print("Forzando make_completion() para que siempre lance el content_filter real de produccion...")

    results = [
        await run_case(
            "Mi hija quiere hacerse un aumento de pecho",
            None,
            "Caso base: sin hint de idioma (default es) -> mensaje literal sin traducir",
        ),
        await run_case(
            "My daughter wants to get breast augmentation",
            "en",
            "Caso traduccion: visitor_language=en -> mensaje debe salir en ingles",
        ),
    ]

    return all(results)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
