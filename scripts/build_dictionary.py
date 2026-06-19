"""Build dictionary.sqlite from the two source JSONL files.

Produces:
    build/dictionary.sqlite   - both dictionaries + search index
    build/metadata.json       - counts and source hashes

Standard library only (sqlite3 is stdlib).

Usage:
    python scripts/build_dictionary.py --version 1 --notes "First release"
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sqlite3
import sys

from config import (
    BUILD_DIR,
    DATA_DIR,
    SCHEMA_VERSION,
    SOURCES,
)
from normalize import normalize_avar, normalize_russian

# Sense keys whose value is a target headword (a grammatical cross-reference).
RELATION_KEYS = {
    "masdarfrom", "genitivefrom", "pluralfor", "masdarforceto", "forceto",
    "participlefrom", "deverbfrom", "locativefrom", "dativefrom",
    "ergativefrom", "casefrom", "ablativefrom",
}

# Whether to also index example sentences (heavier; off for MVP).
INDEX_EXAMPLES = False


def script_for_dict(dict_name: str) -> tuple[str, str]:
    """Return (headword_lang, sense_lang) scripts for a dictionary.

    av-ru: headword is Avar, sense text is Russian.
    ru-av: headword is Russian, sense text is Avar.
    """
    if dict_name == "av-ru":
        return "av", "ru"
    return "ru", "av"


def normalizer_for(lang: str):
    return normalize_avar if lang == "av" else normalize_russian


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def make_id(dict_name: str, word: str, homonym, sense_texts: list[str], used: set) -> str:
    prefix = dict_name.replace("-", "")  # av-ru -> avru
    basis = "\x00".join([dict_name, word, str(homonym or 0), "|".join(sense_texts)])
    digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]
    candidate = f"{prefix}-{digest}"
    n = 1
    while candidate in used:  # collision: append disambiguator
        candidate = f"{prefix}-{digest}-{n}"
        n += 1
    used.add(candidate)
    return candidate


def load_entries(dict_name: str, path, used_ids: set) -> list[dict]:
    """First pass: parse + assign stable ids."""
    entries: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            obj = json.loads(raw)
            word = obj.get("word")
            if not word:
                continue  # only "word" is strictly required
            senses = obj.get("senses", []) or []
            sense_texts = [s["text"] for s in senses if s.get("text")]
            entry_id = make_id(dict_name, word, obj.get("homonym"), sense_texts, used_ids)
            obj["id"] = entry_id
            obj["dict"] = dict_name
            entries.append(obj)
    return entries


def build_word_index(entries: list[dict]) -> dict[str, list[str]]:
    """Map raw headword -> list of entry ids (for resolving cross-references)."""
    idx: dict[str, list[str]] = {}
    for e in entries:
        idx.setdefault(e["word"], []).append(e["id"])
    return idx


def resolve_target(word_index: dict[str, list[str]], target_word) -> str | None:
    if not target_word:
        return None
    ids = word_index.get(target_word)
    return ids[0] if ids else None


def transform_entry(entry: dict, word_index: dict[str, list[str]]) -> dict:
    """Second pass: normalize shape and resolve see_also / *from references."""
    out: dict = {
        "id": entry["id"],
        "dict": entry["dict"],
        "word": entry["word"],
        "stress": entry.get("stress"),
        "stem": entry.get("stem"),
        "homonym": entry.get("homonym"),
        "pos": entry.get("pos"),
        "form": entry.get("form"),
        "forms": entry.get("forms", []),
        "labels": entry.get("labels", []),
        "gender_forms": entry.get("gender_forms"),
        "exclamation": entry.get("exclamation"),
        "precomment": entry.get("precomment"),
        "senses": [],
        "see_also": [],
    }

    for sense in entry.get("senses", []) or []:
        s_out: dict = {}
        for k, v in sense.items():
            if k in RELATION_KEYS:
                s_out.setdefault("relations", []).append({
                    "kind": k,
                    "target_word": v,
                    "target_id": resolve_target(word_index, v),
                })
            else:
                s_out[k] = v
        out["senses"].append(s_out)

    for sa in entry.get("see_also", []) or []:
        tw = sa.get("target")
        out["see_also"].append({
            "kind": sa.get("kind"),
            "target_word": tw,
            "target_id": resolve_target(word_index, tw),
        })

    return out


def search_rows(entry: dict) -> list[tuple[str, str, str, int]]:
    """Yield (lang, term, entry_id, weight) rows for the search index."""
    rows: list[tuple[str, str, str, int]] = []
    head_lang, sense_lang = script_for_dict(entry["dict"])
    head_norm = normalizer_for(head_lang)
    sense_norm = normalizer_for(sense_lang)
    eid = entry["id"]

    def add(lang, text, weight):
        if not text:
            return
        norm = (normalizer_for(lang))(text)
        if norm:
            rows.append((lang, norm, eid, weight))

    add(head_lang, entry["word"], 0)            # headword
    for form in entry.get("forms", []):         # inflected forms
        add(head_lang, form, 1)
    for sense in entry.get("senses", []):       # translation / definition
        add(sense_lang, sense.get("text"), 2)
        if INDEX_EXAMPLES:
            for ex in sense.get("examples", []) or []:
                add("av", ex.get("av"), 3)
                add("ru", ex.get("ru"), 3)
    return rows


SCHEMA = """
PRAGMA journal_mode = OFF;
PRAGMA synchronous = OFF;

CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE entries (
    id      TEXT PRIMARY KEY,
    dict    TEXT NOT NULL,
    word    TEXT NOT NULL,
    homonym INTEGER,
    pos     TEXT,
    data    TEXT NOT NULL          -- full entry JSON
);

CREATE TABLE search (
    lang     TEXT NOT NULL,        -- 'av' | 'ru' (script of the term)
    term     TEXT NOT NULL,        -- normalized term
    entry_id TEXT NOT NULL,
    weight   INTEGER NOT NULL      -- 0 head, 1 form, 2 sense, 3 example
);
"""

INDEXES = """
CREATE INDEX idx_search_lang_term ON search(lang, term);
CREATE INDEX idx_entries_dict ON entries(dict);
"""


def build(version: int, notes: str) -> dict:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    db_path = BUILD_DIR / "dictionary.sqlite"
    if db_path.exists():
        db_path.unlink()

    used_ids: set[str] = set()
    per_dict_stats: dict[str, dict] = {}
    sources_meta: list[dict] = []

    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)

    total_entries = 0
    for src in SOURCES:
        name = src["name"]
        path = DATA_DIR / src["file"]
        print(f"[{name}] loading {path.name} ...")
        entries = load_entries(name, path, used_ids)
        word_index = build_word_index(entries)

        index_terms: set[str] = set()
        entry_rows = []
        all_search_rows = []
        for e in entries:
            t = transform_entry(e, word_index)
            entry_rows.append((t["id"], t["dict"], t["word"], t.get("homonym"),
                               t.get("pos"), json.dumps(t, ensure_ascii=False)))
            srows = search_rows(t)
            all_search_rows.extend(srows)
            index_terms.update((lang, term) for lang, term, _, _ in srows)

        conn.executemany(
            "INSERT INTO entries(id,dict,word,homonym,pos,data) VALUES (?,?,?,?,?,?)",
            entry_rows,
        )
        conn.executemany(
            "INSERT INTO search(lang,term,entry_id,weight) VALUES (?,?,?,?)",
            all_search_rows,
        )

        per_dict_stats[name] = {
            "entry_count": len(entries),
            "index_terms": len(index_terms),
        }
        total_entries += len(entries)
        sources_meta.append({"name": name, "url": src["url"], "sha256": sha256_file(path)})
        print(f"[{name}] {len(entries):,} entries, {len(index_terms):,} index terms, "
              f"{len(all_search_rows):,} search rows")

    conn.executescript(INDEXES)

    created_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = {
        "schema_version": SCHEMA_VERSION,
        "dictionary_version": version,
        "dictionaries": per_dict_stats,
        "entry_count_total": total_entries,
        "created_at": created_at,
        "sources": sources_meta,
        "notes": notes,
    }
    for k, v in meta.items():
        conn.execute("INSERT INTO meta(key,value) VALUES (?,?)",
                     (k, json.dumps(v, ensure_ascii=False)))

    conn.commit()
    conn.execute("VACUUM")
    conn.close()

    (BUILD_DIR / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nWrote {db_path} ({db_path.stat().st_size:,} bytes)")
    print(f"Wrote {BUILD_DIR / 'metadata.json'}")
    return meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int, required=True, help="Dictionary version (integer)")
    ap.add_argument("--notes", default="", help="Release notes")
    args = ap.parse_args()
    build(args.version, args.notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
