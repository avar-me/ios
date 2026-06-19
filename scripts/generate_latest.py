"""Generate public/latest.json pointing to the freshly packaged release.

Run AFTER package_release.py.

Usage:
    python scripts/generate_latest.py --version 1 --notes "First release"

Standard library only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys

from config import (
    BUILD_DIR,
    LATEST_JSON,
    MIN_APP_VERSION,
    RELEASES_DIR,
    SCHEMA_VERSION,
    SITE_BASE_URL,
)


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int, required=True)
    ap.add_argument("--notes", default="")
    args = ap.parse_args()
    version = args.version

    meta_path = BUILD_DIR / "metadata.json"
    zip_path = RELEASES_DIR / f"dictionary-v{version}.zip"
    if not meta_path.exists() or not zip_path.exists():
        print("ERROR: run build_dictionary.py and package_release.py first.")
        return 1

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    created_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    build_id = created_at.replace(":", "-")

    latest = {
        "schema_version": SCHEMA_VERSION,
        "dictionary_version": version,
        "build_id": build_id,
        "sources": meta["sources"],
        "dictionaries": meta["dictionaries"],
        "entry_count_total": meta["entry_count_total"],
        "package_url": f"{SITE_BASE_URL}/releases/dictionary-v{version}.zip",
        "package_sha256": sha256_file(zip_path),
        "package_size_bytes": zip_path.stat().st_size,
        "created_at": created_at,
        "min_app_version": MIN_APP_VERSION,
        "notes": args.notes or meta.get("notes", ""),
    }

    LATEST_JSON.write_text(
        json.dumps(latest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {LATEST_JSON}")
    print(json.dumps(latest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
