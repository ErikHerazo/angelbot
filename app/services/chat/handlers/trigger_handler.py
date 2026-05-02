import logging

logger = logging.getLogger(__name__)

def handle_trigger():
    logger.info("Handling Zoho trigger event")

    return {
        "action": "reply",
        "replies": [
            {
                "text": (
                    "👋 Hola.. soy Aesthea, el asistente virtual de "
                    "Antiaging Group Barcelona, tu clínica de medicina y cirugía estética. "
                    "\nEstoy aquí para ayudarte y resolver tus dudas. 😊 "
                    "¿En qué puedo ayudarte hoy? "
                )
            }
        ]
    }
