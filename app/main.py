import logging
from fastapi import FastAPI
from app.web.routes import home_router
from app.api.routes import chat_zoho_router
from app.web.routes import upload_file_router
from fastapi.staticfiles import StaticFiles
from app.core import constants
from app.core.config import Settings


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

# Static File
app.mount("/static", StaticFiles(directory=constants.WEB_DIR / "static"), name="static")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# Routers
# app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(chat_zoho_router, prefix="/api/chat", tags=["chat_zoho"])
app.include_router(home_router, prefix="/web/chat", tags=["frontend"])
app.include_router(upload_file_router, tags=["upload"])

@app.get("/")
def read_root():
    return {"Hello": "World"}
