import regex


GRAPHEME_PATTERN = regex.compile(r"\X")

def count_visible_chars(text: str) -> int:
    if not text:
        return 0
    return len(GRAPHEME_PATTERN.findall(text))
