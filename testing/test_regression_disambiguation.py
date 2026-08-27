"""
Regresion manual (no pytest) de los casos de DISAMBIGUATION_RULES /
MINOR_SAFETY_RULE que ya se habian validado en sesiones anteriores, para
confirmar que los cambios de hoy (searchMode=all, corte de ambiguedad,
REGLA DE PRECIOS reforzada) no rompieron ningun comportamiento previamente
correcto.

IMPORTANTE: run_conversation_with_rag() por si sola NO guarda el
historial de la conversacion en Redis -- eso lo hace la capa de arriba
(app/web/routes/chat_test.py o process_zoho_message.py). Los casos
multi-turno (labios, revision) usan ask_and_save() para replicar ese
guardado, si no el turno 2 se ejecuta sin memoria real del turno anterior.

Casos cubiertos (de los 8/12 + 2 arreglados que ya pasaban limpio):
- abdomen ambiguo
- celulitis infecciosa
- perdida de peso general
- piernas ambiguo
- sindrome de Poland (determinista)
- labios ambiguo (multi-turno: zona intima -> precio)
- antecedente/revision sin verbo explicito (multi-turno, con precio -> fallback deterministico)

No cubre pecho-en-hombres ni nariz funcional (bloqueados por el content
filter de Azure, bug distinto) ni el bug de relevancia de busqueda de
precios (ya atacado hoy via searchMode=all, cubierto por test_liposuction_gate.py).

Ejecutar desde la raiz del proyecto:
    source .venv/bin/activate
    python3 testing/test_regression_disambiguation.py
"""

import sys
import types
import asyncio
import uuid
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

from app.services.cloud.azure.azure_openai import run_conversation_with_rag, session_memory  # noqa: E402

REVISION_FALLBACK_MARKER = "segunda intervención o revisión, el precio no"


async def ask_and_save(session_id: str, question: str, channel: str = "website"):
    """Replica el guardado de historial que hace chat_test.py."""
    print(f"  > {question!r}")
    try:
        answer = await run_conversation_with_rag(
            session_id=session_id, user_question=question, channel=channel, visitor_language=None
        )
    except Exception as ex:
        print(f"  EXCEPCION NO ATRAPADA: {type(ex).__name__}: {ex}")
        return None
    print(f"  < {answer}\n")
    history = await session_memory.get_session(session_id)
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})
    await session_memory.save_session(session_id, history)
    return answer


async def case_abdomen():
    print("\n=== ABDOMEN AMBIGUO ===")
    sid = f"testing-{uuid.uuid4()}"
    answer = await ask_and_save(sid, "quiero quitar barriga") or ""
    ok = "?" in answer
    return ok, answer


async def case_celulitis_infecciosa():
    print("\n=== CELULITIS INFECCIOSA ===")
    sid = f"testing-{uuid.uuid4()}"
    answer = await ask_and_save(
        sid,
        "Tengo celulitis infecciosa en la pierna, con fiebre y la piel enrojecida e hinchada",
    ) or ""
    low = answer.lower()
    ok = ("médico" in low or "medico" in low or "urgencias" in low)
    ok = ok and "radiofrecuencia" not in low and "accent" not in low
    return ok, answer


async def case_perdida_peso():
    print("\n=== PERDIDA DE PESO GENERAL ===")
    sid = f"testing-{uuid.uuid4()}"
    answer = await ask_and_save(sid, "Quiero perder peso, en general, no es una zona concreta") or ""
    low = answer.lower()
    ok = "liposucción" not in low and "abdominoplastia" not in low
    return ok, answer


async def case_piernas():
    print("\n=== PIERNAS AMBIGUO ===")
    sid = f"testing-{uuid.uuid4()}"
    answer = await ask_and_save(sid, "quiero arreglarme las piernas") or ""
    ok = "?" in answer
    return ok, answer


async def case_poland():
    print("\n=== SINDROME DE POLAND (DETERMINISTA) ===")
    sid = f"testing-{uuid.uuid4()}"
    answer = await ask_and_save(
        sid,
        "Desde que nací tengo un lado del pecho menos desarrollado, me falta el pectoral de ese lado",
    ) or ""
    low = answer.lower()
    ok = "poland" in low
    return ok, answer


async def case_labios_multiturno():
    print("\n=== LABIOS AMBIGUO (multi-turno: zona intima -> precio) ===")
    sid = f"testing-{uuid.uuid4()}"
    a1 = await ask_and_save(sid, "quiero arreglarme los labios") or ""
    ok1 = "€" not in a1 and "eur" not in a1.lower() and "?" in a1
    a2 = await ask_and_save(sid, "la zona íntima, cuánto cuesta") or ""
    ok2 = "€" in a2 or "eur" in a2.lower()
    return (ok1 and ok2), f"[turno1]\n{a1}\n\n[turno2]\n{a2}"


async def case_revision_sin_verbo():
    print("\n=== ANTECEDENTE/REVISION SIN VERBO EXPLICITO + PRECIO ===")
    sid = f"testing-{uuid.uuid4()}"
    a1 = await ask_and_save(
        sid,
        "No quedé nada contenta con el resultado de mi cirugía de nariz, me gustaría corregirlo",
    ) or ""
    a2 = await ask_and_save(sid, "¿Cuánto costaría corregirlo?") or ""
    ok = REVISION_FALLBACK_MARKER in a2
    return ok, f"[turno1]\n{a1}\n\n[turno2]\n{a2}"


async def main():
    cases = [
        ("abdomen_ambiguo", case_abdomen),
        ("celulitis_infecciosa", case_celulitis_infecciosa),
        ("perdida_de_peso", case_perdida_peso),
        ("piernas_ambiguo", case_piernas),
        ("sindrome_de_poland", case_poland),
        ("labios_multiturno", case_labios_multiturno),
        ("revision_sin_verbo", case_revision_sin_verbo),
    ]

    results = {}
    for name, fn in cases:
        ok, _ = await fn()
        results[name] = ok

    print(f"\n{'=' * 70}\nRESUMEN REGRESION\n{'=' * 70}")
    all_ok = True
    for name, ok in results.items():
        all_ok &= ok
        print(f"[{'OK' if ok else 'FALLO'}] {name}")

    print("\nRESULTADO GLOBAL:", "TODO OK" if all_ok else "HAY FALLOS")
    return all_ok


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
