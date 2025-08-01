# from typing import Union
from fastapi import FastAPI


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

@app.get("/")
def read_root():
    return {"Hello": "World"}
