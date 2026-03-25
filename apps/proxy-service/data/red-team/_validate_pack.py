#!/usr/bin/env python3
"""Validate pack manifest references match actual attack files."""

import json
import os

base = os.path.dirname(__file__)
attacks_dir = os.path.join(base, "attacks")
packs_dir = os.path.join(base, "packs")

# Build registry of all IDs per file
file_ids = {}
for fname in sorted(os.listdir(attacks_dir)):
    if not fname.endswith(".json") or fname.startswith("_"):
        continue
    with open(os.path.join(attacks_dir, fname)) as f:
        data = json.load(f)
    file_ids[fname] = {a["id"] for a in data["attacks"]}

# Validate each pack
for pname in sorted(os.listdir(packs_dir)):
    if not pname.endswith(".json"):
        continue
    with open(os.path.join(packs_dir, pname)) as f:
        pack = json.load(f)

    print(f"Pack: {pack['pack_id']} (v{pack['version']})")
    total = 0
    errors = []

    for cat in pack["categories"]:
        fname = cat["file"]
        if fname not in file_ids:
            errors.append(f"  File not found: {fname}")
            continue
        for aid in cat["attack_ids"]:
            if aid not in file_ids[fname]:
                errors.append(f"  ID {aid} not in {fname}")
            else:
                total += 1

    declared = pack.get("metadata", {}).get("total_attacks", "?")
    if errors:
        for e in errors:
            print(e)
    else:
        print(f"  All {total} attack IDs resolved ✓ (declared: {declared})")

    # Verify counts
    malicious = sum(len(c["attack_ids"]) for c in pack["categories"] if c["name"] != "Safe / Allow (False Positive)")
    safe = sum(len(c["attack_ids"]) for c in pack["categories"] if c["name"] == "Safe / Allow (False Positive)")
    print(f"  Malicious: {malicious}, Safe: {safe}")
