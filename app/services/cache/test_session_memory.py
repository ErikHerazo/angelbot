import asyncio
from app.services.cache.session_memory import SessionMemoryRedis

async def main():
    mem = SessionMemoryRedis()
    await mem.add_message("test123", "user", "Hola mundo")
    history = await mem.get_session("test123")
    print("Session history:", history)
    await mem.clear_session("test123")
    print("✅ Test completado")

if __name__ == "__main__":
    asyncio.run(main())
