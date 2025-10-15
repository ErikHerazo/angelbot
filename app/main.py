import logging
from fastapi import FastAPI
from app.api.routes import chat_router, upload_router, chat_zoho_router


app = FastAPI(
    title="Angel Bot API",
    description="""
    Microservicio FastAPI para orquestar servicios como LangChain, Azure OpenAI, y más.
    
    **Proyecto:** AnGelBot  
    **Desarrollador:** Erik Manuel Herazo Jiménez  
    **Correo:** erikherazojimenez@outlook.com  
    **Propósito:** Automatizar respuestas inteligentes a usuarios mediante múltiples integraciones.
    """,
    version="1.0.0"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("angelbot")

app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(chat_zoho_router, prefix="/api/chat", tags=["chat_zoho"])
app.include_router(upload_router, prefix="/api/upload", tags=["upload"])

@app.get("/")
def read_root():
    return {"Hello": "World"}
