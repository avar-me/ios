"""Text normalization for search indexing and query handling.

The same functions must be used at BUILD time (to populate the index) and at
QUERY time (in the iOS app the equivalent logic lives in TextNormalizer.swift).
Keeping them identical is what makes search work.

Standard library only.
"""

from __future__ import annotations

import re
import unicodedata

# Canonical palochka (Cyrillic small letter palochka).
PALOCHKA = "ӏ"  # ӏ

# Everything users type instead of the palochka, folded to the canonical form.
#   Ӏ U+04C0 capital palochka
#   1       digit one
#   l U+006C latin small L
#   I U+0049 latin capital I
#   |       vertical bar
_PALOCHKA_VARIANTS = {
    "Ӏ": PALOCHKA,
    "1": PALOCHKA,
    "l": PALOCHKA,
    "I": PALOCHKA,
    "|": PALOCHKA,
}
_PALOCHKA_RE = re.compile("[" + "".join(map(re.escape, _PALOCHKA_VARIANTS)) + "]")

_WHITESPACE_RE = re.compile(r"\s+")


def _collapse_ws(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def fold_palochka(text: str) -> str:
    """Replace all palochka look-alikes with the canonical palochka."""
    return _PALOCHKA_RE.sub(lambda m: _PALOCHKA_VARIANTS[m.group()], text)


def normalize_avar(text: str) -> str:
    """Normalize Avar text for indexing/search.

    NFC -> fold palochka -> lowercase -> collapse whitespace.
    Does NOT strip diacritics or special characters.
    """
    text = unicodedata.normalize("NFC", text)
    text = fold_palochka(text)
    text = text.lower()
    return _collapse_ws(text)


def normalize_russian(text: str) -> str:
    """Normalize Russian text for indexing/search.

    NFC -> lowercase -> ё->е -> collapse whitespace.
    """
    text = unicodedata.normalize("NFC", text)
    text = text.lower()
    text = text.replace("ё", "е")  # ё -> е
    return _collapse_ws(text)
