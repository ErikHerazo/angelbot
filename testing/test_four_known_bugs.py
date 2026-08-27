"""
Prueba manual (no pytest) que reproduce los 4 bugs diagnosticados en la
sesion de tuning de prompts (ver CLAUDE.md, "Diagnosticado, no arreglado"):

1. Liposuccion sin zona + precio directo -> el LLM llama a la tool de
   precios igual y muestra todas las zonas (o falla la busqueda), en vez
   de preguntar la zona antes.
2. Angustia emocional -> el modelo valida la emocion pero sigue con
   precio/procedimiento en el mismo turno.
3. Nariz funcional / pecho-en-hombres -> bloqueados por el content filter
   de Azure OpenAI antes de que el LLM razone sobre las reglas.
4. Bug de relevancia en busqueda de precios -> procedures_and_treatments_price_list
   sin searchMode/top/searchFields devuelve resultados poco relacionados.

Este script NO modifica nada, solo corre y reporta el estado actual
(baseline, tal como esta en el commit).

Ejecutar desde la raiz del proyecto:
    source .venv/bin/activate
    python3 testing/test_four_known_bugs.py
"""

import re
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

from app.services.cloud.azure.azure_openai import run_conversation_with_rag  # noqa: E402
from app.services.cloud.azure.azure_tools import procedures_and_treatments_price_list  # noqa: E402
from app.core import constants  # noqa: E402

PRICE_PATTERN = re.compile(r"\d[\d.,]*\s*(€|eur|euros)", re.IGNORECASE)


async def ask(question, channel="website"):
    sid = f"testing-{uuid.uuid4()}"
    try:
        return await run_conversation_with_rag(
            session_id=sid, user_question=question, channel=channel, visitor_language=None
        )
    except Exception as ex:
        return f"EXCEPCION: {type(ex).__name__}: {ex}"


async def bug1_liposuccion():
    print("\n" + "=" * 70)
    print("BUG 1: Liposuccion sin zona + precio directo")
    print("=" * 70)
    q = "¿Cuánto cuesta una liposucción?"
    fails = 0
    for i in range(3):
        a = await ask(q)
        gave_price = bool(PRICE_PATTERN.search(a))
        print(f"  run{i+1}: dio_precio_sin_preguntar_zona={gave_price}")
        if gave_price:
            fails += 1
    print(f"  -> falla {fails}/3 (se espera 3/3 o cercano)")
    return fails


async def bug2_angustia_emocional():
    print("\n" + "=" * 70)
    print("BUG 2: Angustia emocional -> sigue con precio/procedimiento igual")
    print("=" * 70)
    q = "Odio mi nariz, no lo soporto más, necesito arreglarlo ya, dime el precio"
    fails = 0
    for i in range(3):
        a = await ask(q)
        continues_commercial = bool(PRICE_PATTERN.search(a)) or "rinoplastia" in a.lower() or "rinomodelaci" in a.lower()
        print(f"  run{i+1}: {a[:150]}...")
        print(f"    -> sigue con info comercial en el mismo turno={continues_commercial}")
        if continues_commercial:
            fails += 1
    print(f"  -> falla {fails}/3 (se espera que NO debería seguir con precio/procedimiento)")
    return fails


async def bug3_content_filter():
    print("\n" + "=" * 70)
    print("BUG 3: Nariz funcional / pecho-en-hombres bloqueados por content filter")
    print("=" * 70)
    cases = [
        "Tengo el tabique desviado y me cuesta mucho respirar, quiero operarme",
        "Soy hombre y quiero operarme el pecho",
    ]
    fails = 0
    for q in cases:
        a = await ask(q)
        hit_fallback = "consulta@agb.cat" in a and "valoración directa y personalizada" in a
        print(f"  '{q}':")
        print(f"    -> {a[:200]}")
        print(f"    -> cayo en CONTENT_FILTER_FALLBACK_MESSAGE={hit_fallback}")
        if hit_fallback:
            fails += 1
    print(f"  -> {fails}/2 casos cayeron en el fallback de content filter (nunca llegan a razonar la desambiguación)")
    return fails


def bug4_price_search_relevance():
    print("\n" + "=" * 70)
    print("BUG 4: Relevancia de busqueda de precios (sin searchMode/top/searchFields)")
    print("=" * 70)
    result = procedures_and_treatments_price_list("liposucción de abdomen")
    import json
    data = json.loads(result)
    n = len(data.get("results", []))
    print(f"  Query: 'liposucción de abdomen' -> {n} resultados devueltos")
    names = [r.get("procedure_name", "") for r in data.get("results", [])][:10]
    for name in names:
        print(f"    - {name}")
    noisy = n > 5
    print(f"  -> demasiados resultados poco relacionados (>5)={noisy}")
    return noisy


async def main():
    b1 = await bug1_liposuccion()
    b2 = await bug2_angustia_emocional()
    b3 = await bug3_content_filter()
    b4 = bug4_price_search_relevance()

    print("\n" + "=" * 70)
    print("RESUMEN")
    print("=" * 70)
    print(f"[{'FALLA' if b1 > 0 else 'OK'}] Bug 1 - liposuccion sin zona ({b1}/3)")
    print(f"[{'FALLA' if b2 > 0 else 'OK'}] Bug 2 - angustia emocional ({b2}/3)")
    print(f"[{'FALLA' if b3 > 0 else 'OK'}] Bug 3 - content filter nariz/pecho ({b3}/2)")
    print(f"[{'FALLA' if b4 else 'OK'}] Bug 4 - relevancia busqueda precios")


if __name__ == "__main__":
    asyncio.run(main())
