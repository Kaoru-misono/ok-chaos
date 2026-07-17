from __future__ import annotations

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")


def normalize_text(value: object) -> str:
    """Normalize OCR text while preserving meaningful punctuation."""
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(value))
    return _WHITESPACE.sub("", normalized).strip()


def text_matches(value: object, expected: object, *, exact: bool = False) -> bool:
    value_normalized = normalize_text(value)
    expected_normalized = normalize_text(expected)
    if not value_normalized or not expected_normalized:
        return False
    if exact:
        return value_normalized == expected_normalized
    return expected_normalized in value_normalized
