from app.core import constants

def welcome_message():
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
        ],
    }

def pending_message(text=constants.MESSAGE_OF_PROGRESS):
    return {
        "action": "pending",
        "replies": [text],
    }
