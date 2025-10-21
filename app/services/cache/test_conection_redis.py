import asyncio
import redis.asyncio as aioredis
import os

# Configuración desde variables de entorno o directamente
REDIS_HOST = os.getenv("REDIS_HOST", "angelbot-rm-we.westeurope.redisenterprise.cache.azure.net")
REDIS_PORT = int(os.getenv("REDIS_PORT", "10000"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "kkgA37xJonxnEGIEpMZfQugpcGywnp0gjAzCaMGmixg=")
REDIS_USE_SSL = os.getenv("REDIS_USE_SSL", "true").lower() == "true"

async def test_connection():
    print(f"Conectando a Redis Enterprise ({'SSL' if REDIS_USE_SSL else 'sin SSL'})...")

    redis = aioredis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        ssl=REDIS_USE_SSL,
        decode_responses=True
    )

    try:
        pong = await redis.ping()
        if pong:
            print("✅ Conexión exitosa: PONG recibido.")
        else:
            print("⚠️ No se recibió PONG, algo anda mal.")
    except Exception as e:
        print("❌ Error de conexión:", e)
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(test_connection())
