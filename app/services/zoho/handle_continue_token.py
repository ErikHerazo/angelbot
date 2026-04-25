from app.core import constants


def handle_continue_token(
    user_question: str,
    channel: str,
) -> str | None:

    # 1. Si no es el token, no aplica
    if user_question != constants.CONTINUE_TOKEN:
        return None

    # 2. Caso especial: canal flow → respuesta vacía
    if channel == "flow":
        return ""

    # 3. Mensaje fijo en español
    return constants.RESPONSE_TO_THE_CONTINUE_TOKEN_MESSAGE
