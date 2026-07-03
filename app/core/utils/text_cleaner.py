import re

def remove_doc_refs(text: str) -> str:
    # elimina cualquier contenido entre [ ... ]
    text = re.sub(r'\[[^\]]*\]', '', text)

    # normaliza SOLO espacios y tabs (no saltos de línea)
    text = re.sub(r'[ \t]{2,}', ' ', text)

    # limpia espacios al final de cada línea
    text = '\n'.join(line.rstrip() for line in text.splitlines())
    return text.strip()

import re

EMAIL_REGEX = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
URL_REGEX = r"https?://\S+|www\.\S+"
FILE_REGEX = (
    r"\b\S+\.(pdf|doc|docx|xls|xlsx|ppt|pptx|jpg|jpeg|png|gif|webp|"
    r"zip|rar|7z|txt|csv|mp4|mp3|mov|avi|heic|heif)\b"
)
PHONE_REGEX = r"\+?\d[\d\s().-]{6,}\d"

def get_text_for_language_detection(text: str) -> str:
    """
    Prepare a message for language detection.

    Removes elements that do not represent natural language:
    - Emails
    - URLs
    - File names
    - Phone numbers

    The returned text is intended ONLY for language detection.
    The original message must always be preserved for the LLM.
    """

    if not text:
        return ""

    # Remove emails
    text = re.sub(EMAIL_REGEX, " ", text, flags=re.IGNORECASE)

    # Remove URLs
    text = re.sub(URL_REGEX, " ", text, flags=re.IGNORECASE)

    # Remove file names
    text = re.sub(FILE_REGEX, " ", text, flags=re.IGNORECASE)

    # Remove phone numbers
    text = re.sub(PHONE_REGEX, " ", text)

    # Remove punctuation (keep accented characters)
    text = re.sub(r"[^\w\sÀ-ÿ]", " ", text)

    # Normalize spaces
    text = re.sub(r"\s+", " ", text).strip()

    return text
