#!/usr/bin/env python3
import json
import os
from collections import Counter

attack_dir = os.path.join(os.path.dirname(__file__), "attacks")
total = 0
errors = []
all_ids = []

for fname in sorted(os.listdir(attack_dir)):
    if not fname.endswith(".json") or fname.startswith("_") or ".v1." in fname:
        continue
    path = os.path.join(attack_dir, fname)
    try:
        with open(path) as f:
            data = json.load(f)
        count = len(data.get("attacks", []))
        ids = [a["id"] for a in data.get("attacks", [])]
        all_ids.extend(ids)
        total += count
        print(f"  {fname}: {count} attacks — {ids}")
    except Exception as e:
        errors.append(f"{fname}: {e}")

print(f"\nTotal: {total} attacks across {len([f for f in os.listdir(attack_dir) if f.endswith('.json')])} files")
if errors:
    print(f"ERRORS: {errors}")
else:
    print("All JSON files valid ✓")

dupes = [id for id, c in Counter(all_ids).items() if c > 1]
if dupes:
    print(f"DUPLICATE IDs: {dupes}")
else:
    print(f"All {len(all_ids)} IDs unique ✓")
