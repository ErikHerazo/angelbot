import asyncio
from app.services.cloud.azure.azure_openai import run_conversation_with_rag


async def main():
    session_id = "test-session-001"
    user_question = "Hola, ¿quién eres?"

    print("=== Ejecutando prueba con memoria de sesión (Redis) ===")
    response = await run_conversation_with_rag(session_id, user_question)
    print(f"💬 Respuesta: {response}")

    # Segunda interacción, para verificar persistencia de memoria
    user_question_2 = "¿Recuerdas lo que te pregunté antes?"
    response_2 = await run_conversation_with_rag(session_id, user_question_2)
    print(f"💬 Respuesta (2): {response_2}")

if __name__ == "__main__":
    asyncio.run(main())
