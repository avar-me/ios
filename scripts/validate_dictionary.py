"""Validate the built dictionary against quality gates before publishing.

Exits non-zero if any gate fails, so the CI build stops.

Usage:
    python scripts/validate_dictionary.py

Standard library only.
"""

from __future__ import annotations

import json
import sqlite3
import sys

from config import (
    BUILD_DIR,
    LATEST_JSON,
    MAX_RELATIVE_DROP,
    QUALITY_GATES,
)


def fail(msg: str, errors: list[str]) -> None:
    errors.append(msg)
    print(f"  FAIL: {msg}")


def main() -> int:
    db_path = BUILD_DIR / "dictionary.sqlite"
    meta_path = BUILD_DIR / "metadata.json"
    if not db_path.exists() or not meta_path.exists():
        print("ERROR: build artifacts missing. Run build_dictionary.py first.")
        return 1

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    errors: list[str] = []

    # --- Per-dictionary absolute gates ---
    print("Quality gates (absolute):")
    for name, gate in QUALITY_GATES.items():
        d = meta["dictionaries"].get(name)
        if not d:
            fail(f"{name}: missing from metadata", errors)
            continue
        if d["entry_count"] < gate["min_entries"]:
            fail(f"{name}: entry_count {d['entry_count']} < {gate['min_entries']}", errors)
        else:
            print(f"  OK: {name} entry_count={d['entry_count']:,} (>= {gate['min_entries']:,})")
        if d["index_terms"] < gate["min_index_terms"]:
            fail(f"{name}: index_terms {d['index_terms']} < {gate['min_index_terms']}", errors)
        else:
            print(f"  OK: {name} index_terms={d['index_terms']:,} (>= {gate['min_index_terms']:,})")

    # --- Relative drop vs. previously published release ---
    if LATEST_JSON.exists():
        print("Quality gates (relative vs. previous release):")
        try:
            prev = json.loads(LATEST_JSON.read_text(encoding="utf-8"))
            prev_dicts = prev.get("dictionaries", {})
        except (ValueError, OSError):
            prev_dicts = {}
        for name, d in meta["dictionaries"].items():
            old = prev_dicts.get(name, {}).get("entry_count")
            if old:
                floor = old * (1 - MAX_RELATIVE_DROP)
                if d["entry_count"] < floor:
                    fail(f"{name}: entry_count dropped {old} -> {d['entry_count']} "
                         f"(> {MAX_RELATIVE_DROP:.0%})", errors)
                else:
                    print(f"  OK: {name} {old:,} -> {d['entry_count']:,}")
    else:
        print("No previous latest.json — skipping relative gates (first release).")

    # --- Structural checks on the database ---
    print("Database checks:")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    for lang in ("av", "ru"):
        n = c.execute("SELECT COUNT(*) FROM search WHERE lang=?", (lang,)).fetchone()[0]
        if n == 0:
            fail(f"search index empty for lang={lang}", errors)
        else:
            print(f"  OK: search lang={lang} has {n:,} rows")

    n_entries = c.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    if n_entries != meta["entry_count_total"]:
        fail(f"entries table {n_entries} != metadata {meta['entry_count_total']}", errors)
    else:
        print(f"  OK: entries table has {n_entries:,} rows")

    # Sample query must return a result and parse as JSON.
    row = c.execute("SELECT data FROM entries LIMIT 1").fetchone()
    try:
        json.loads(row[0])
        print("  OK: sample entry parses as JSON")
    except (TypeError, ValueError):
        fail("sample entry does not parse as JSON", errors)
    conn.close()

    if errors:
        print(f"\nVALIDATION FAILED ({len(errors)} error(s)).")
        return 1
    print("\nVALIDATION PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
