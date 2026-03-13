def extract_rag_answer(response):
    message = response.choices[0].message

    context = getattr(message, "context", {}) or {}
    citations = context.get("citations", [])

    if not citations:
        return (
            "Lo siento, no encontré esa información en nuestros documentos.",
            0
        )

    return message.content, len(citations)
