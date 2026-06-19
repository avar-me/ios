"""Shared configuration for the Avar dictionary build pipeline.

No external dependencies — standard library only (Python 3.12).
"""

from __future__ import annotations

from pathlib import Path

# --- Source dictionaries (two independent dictionaries, not mirrors) ---------

SOURCES: list[dict[str, str]] = [
    {
        "name": "av-ru",  # Avar -> Russian headwords
        "url": "https://sources.avar.me/data/av-ru.jsonl",
        "file": "av-ru.jsonl",
    },
    {
        "name": "ru-av",  # Russian -> Avar headwords
        "url": "https://sources.avar.me/data/ru-av.jsonl",
        "file": "ru-av.jsonl",
    },
]

# --- Repository paths --------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"          # raw downloaded JSONL (git-ignored)
BUILD_DIR = ROOT / "build"        # intermediate build artifacts (git-ignored)
PUBLIC_DIR = ROOT / "public"      # served by GitHub Pages as ios.avar.me
RELEASES_DIR = PUBLIC_DIR / "releases"
CHECKSUMS_DIR = PUBLIC_DIR / "checksums"
LATEST_JSON = PUBLIC_DIR / "latest.json"

# --- Schema / endpoint -------------------------------------------------------

SCHEMA_VERSION = 1
SITE_BASE_URL = "https://ios.avar.me"

# Minimum iOS app version able to read this dictionary schema.
MIN_APP_VERSION = "1.0.0"

# --- Quality gates (per dictionary) ------------------------------------------
# Real counts at time of writing: av-ru 22855, ru-av 38874.
# Absolute floors sit a little below current numbers.

QUALITY_GATES: dict[str, dict[str, int]] = {
    "av-ru": {"min_entries": 22000, "min_index_terms": 20000},
    "ru-av": {"min_entries": 37000, "min_index_terms": 30000},
}

# A drop larger than this fraction vs. the previous release fails the build.
MAX_RELATIVE_DROP = 0.05

# Minimum acceptable package size (sanity check against an empty archive).
MIN_PACKAGE_SIZE_BYTES = 1_000_000
