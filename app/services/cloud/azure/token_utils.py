import tiktoken


def token_estimate(text: str, model: str) -> int:
    if not text:
        return 0

    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        # fallback por si el modelo no está mapeado
        enc = tiktoken.get_encoding("cl100k_base")

    return len(enc.encode(text))
