import re
import unicodedata
from dataclasses import dataclass


@dataclass
class ProcedureMatch:
    procedure_name: str
    price_range: str


@dataclass
class ProcedurePriceResult:
    procedure_name: str
    price_range: str
    currency: str


def normalize_search_text(text: str) -> str:
    """Pure text normalization for catalog search: lowercase, strips
    accents/diacritics, drops non-alphanumeric characters, collapses
    whitespace. No I/O, no dependency on any search backend."""
    if not text:
        return ""

    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text
