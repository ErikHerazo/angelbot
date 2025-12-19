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
                    "Antiaging Group Barcelona, tu clínica de medicina "
                    "y cirugía estética. Nuestro objetivo es que te sientas mejor."
                )
            }
        ]
    }
