"""Package the built dictionary into a release ZIP + checksum.

Produces:
    public/releases/dictionary-v{N}.zip   (contains dictionary/metadata.json + dictionary/dictionary.sqlite)
    public/checksums/dictionary-v{N}.sha256

Standard library only.

Usage:
    python scripts/package_release.py --version 1
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile

from config import BUILD_DIR, CHECKSUMS_DIR, MIN_PACKAGE_SIZE_BYTES, RELEASES_DIR


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int, required=True)
    args = ap.parse_args()
    version = args.version

    db_path = BUILD_DIR / "dictionary.sqlite"
    meta_path = BUILD_DIR / "metadata.json"
    if not db_path.exists() or not meta_path.exists():
        print("ERROR: build artifacts missing. Run build_dictionary.py first.")
        return 1

    RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    CHECKSUMS_DIR.mkdir(parents=True, exist_ok=True)

    zip_path = RELEASES_DIR / f"dictionary-v{version}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.write(meta_path, "dictionary/metadata.json")
        zf.write(db_path, "dictionary/dictionary.sqlite")

    size = zip_path.stat().st_size
    if size < MIN_PACKAGE_SIZE_BYTES:
        print(f"ERROR: package too small ({size} bytes < {MIN_PACKAGE_SIZE_BYTES}).")
        return 1

    digest = sha256_file(zip_path)
    checksum_path = CHECKSUMS_DIR / f"dictionary-v{version}.sha256"
    checksum_path.write_text(f"{digest}  dictionary-v{version}.zip\n", encoding="utf-8")

    print(f"Wrote {zip_path} ({size:,} bytes)")
    print(f"  sha256: {digest}")
    print(f"Wrote {checksum_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
