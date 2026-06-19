"""Tests for text normalization — especially palochka folding.

Run:
    python -m pytest tests/        (if pytest available)
    python tests/test_normalization.py   (plain stdlib runner below)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from normalize import PALOCHKA, fold_palochka, normalize_avar, normalize_russian


def test_palochka_variants_fold_to_canonical():
    # ӏ, Ӏ, 1, latin l, latin I, | all map to canonical palochka.
    for variant in ["магӏна", "магӀна", "маг1на", "магlна", "магIна", "маг|на"]:
        assert normalize_avar(variant) == "магӏна", variant


def test_fold_palochka_raw():
    assert fold_palochka("маг1на") == "маг" + PALOCHKA + "на"


def test_avar_lowercase_and_nfc():
    assert normalize_avar("  МагӀНА  ") == "магӏна"


def test_avar_keeps_digraphs_and_special_chars():
    # Digraphs and hard/soft signs must survive normalization.
    assert normalize_avar("къ лъ хъ гь цӀ чӀ") == "къ лъ хъ гь цӏ чӏ"


def test_russian_yo_folds_to_e():
    assert normalize_russian("ёлка") == "елка"
    assert normalize_russian("Берёза") == "береза"


def test_russian_whitespace_collapse():
    assert normalize_russian("  два   слова ") == "два слова"


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run())
