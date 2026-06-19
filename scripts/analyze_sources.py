"""Analyze the source JSONL files: counts and field coverage.

Produces the numbers that quality gates (config.QUALITY_GATES) rely on, so run
this whenever the sources change to see whether thresholds need adjusting.

Usage:
    python scripts/analyze_sources.py

Standard library only.
"""

from __future__ import annotations

import json
import sys
from collections import Counter

from config import DATA_DIR, SOURCES


def analyze(path) -> dict:
    top_keys: Counter[str] = Counter()
    sense_keys: Counter[str] = Counter()
    example_keys: Counter[str] = Counter()
    see_kinds: Counter[str] = Counter()
    pos_vals: Counter[str] = Counter()
    n = 0
    empty_senses = 0
    senses_without_text = 0
    missing_word = 0

    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            obj = json.loads(raw)
            n += 1
            if not obj.get("word"):
                missing_word += 1
            for k in obj:
                top_keys[k] += 1
            senses = obj.get("senses", [])
            if not senses:
                empty_senses += 1
            for s in senses:
                for k in s:
                    sense_keys[k] += 1
                if "text" not in s:
                    senses_without_text += 1
                for ex in s.get("examples", []):
                    for k in ex:
                        example_keys[k] += 1
            for sa in obj.get("see_also", []):
                see_kinds[sa.get("kind")] += 1
            if "pos" in obj:
                pos_vals[obj["pos"]] += 1

    return {
        "entries": n,
        "missing_word": missing_word,
        "empty_senses": empty_senses,
        "senses_without_text": senses_without_text,
        "top_keys": dict(top_keys.most_common()),
        "sense_keys": dict(sense_keys.most_common()),
        "example_keys": dict(example_keys.most_common()),
        "see_kinds": dict(see_kinds.most_common()),
        "pos": dict(pos_vals.most_common(20)),
    }


def main() -> int:
    missing = [s for s in SOURCES if not (DATA_DIR / s["file"]).exists()]
    if missing:
        names = ", ".join(s["file"] for s in missing)
        print(f"ERROR: missing source files: {names}")
        print("Run: python scripts/download_sources.py")
        return 1

    for src in SOURCES:
        path = DATA_DIR / src["file"]
        stats = analyze(path)
        print(f"\n==== {src['name']}  ({stats['entries']:,} entries) ====")
        print(f"  missing word:          {stats['missing_word']:,}")
        print(f"  entries w/o senses:    {stats['empty_senses']:,}")
        print(f"  senses w/o text:       {stats['senses_without_text']:,}")
        print(f"  top-level keys:        {stats['top_keys']}")
        print(f"  sense keys:            {stats['sense_keys']}")
        print(f"  example keys:          {stats['example_keys']}")
        print(f"  see_also kinds:        {stats['see_kinds']}")
        if stats["pos"]:
            print(f"  pos values:            {stats['pos']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
