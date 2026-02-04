import re

def remove_doc_refs(text: str) -> str:
    # elimina [docN]
    text = re.sub(r'\[doc\d+\]', '', text)

    # normaliza SOLO espacios (no saltos de línea)
    text = re.sub(r'[ \t]{2,}', ' ', text)

    # limpia líneas individuales
    text = '\n'.join(line.rstrip() for line in text.splitlines())
    return text.strip()
