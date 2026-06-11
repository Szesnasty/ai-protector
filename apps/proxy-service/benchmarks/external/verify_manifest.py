"""CLI: verify (or rebuild) the corpus integrity manifest.

python -m benchmarks.external.verify_manifest          # verify, exit 1 on mismatch
python -m benchmarks.external.verify_manifest --write   # rebuild manifest.json
"""

from __future__ import annotations

import argparse
import sys

from benchmarks.external.manifest import verify_manifest, write_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify or rebuild the corpus manifest")
    parser.add_argument("--write", action="store_true", help="Rebuild manifest.json from corpus/*.jsonl")
    args = parser.parse_args()

    if args.write:
        manifest = write_manifest()
        print(f"✓ manifest written: {manifest['total_count']} records across {len(manifest['sources'])} file(s)")
        return 0

    ok, problems = verify_manifest()
    if ok:
        print("✓ corpus integrity OK — all files match manifest sha256")
        return 0

    print("✗ corpus integrity FAILED:")
    for p in problems:
        print(f"  - {p}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
