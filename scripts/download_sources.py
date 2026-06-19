"""Download both source JSONL dictionaries into data/.

Usage:
    python scripts/download_sources.py

Standard library only.
"""

from __future__ import annotations

import sys
import urllib.request

from config import DATA_DIR, SOURCES


def download(url: str, dest) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": "avar-ios-pipeline"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    dest.write_bytes(data)
    return len(data)


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for src in SOURCES:
        dest = DATA_DIR / src["file"]
        print(f"Downloading {src['name']} from {src['url']} ...")
        size = download(src["url"], dest)
        n_lines = sum(1 for _ in dest.open("r", encoding="utf-8"))
        print(f"  saved {dest}  ({size:,} bytes, {n_lines:,} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
