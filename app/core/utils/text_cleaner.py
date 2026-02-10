import re

def remove_doc_refs(text: str) -> str:
    # elimina cualquier contenido entre [ ... ]
    text = re.sub(r'\[[^\]]*\]', '', text)

    # normaliza SOLO espacios y tabs (no saltos de línea)
    text = re.sub(r'[ \t]{2,}', ' ', text)

    # limpia espacios al final de cada línea
    text = '\n'.join(line.rstrip() for line in text.splitlines())
    return text.strip()
