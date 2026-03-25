#!/usr/bin/env python3
"""Validate v2 structural requirements for all attack files."""

import json
import os

base = os.path.join(os.path.dirname(__file__), "attacks")
V2_ATTACK_FIELDS = [
    "id",
    "title",
    "prompt",
    "tags",
    "severity",
    "expected_proxy_action",
    "expected_security_outcome",
    "supported_modes",
    "requires_proxy",
    "risk_surface",
    "breach_surface",
    "breach_class",
    "success_criteria",
    "detector",
    "description",
    "added",
]
V2_CONDITION_FIELDS = ["name", "apply_on", "type", "config", "confidence_class"]
VALID_SURFACES = {"user_input", "pipeline_result", "forwarded_request", "final_response"}
errors = []

for fname in sorted(os.listdir(base)):
    if not fname.endswith(".json") or fname.startswith("_") or ".v1." in fname:
        continue
    path = os.path.join(base, fname)
    with open(path) as f:
        data = json.load(f)

    # Check defaults block
    if "defaults" not in data:
        errors.append(f"{fname}: missing 'defaults' block")

    version = data.get("version", "0.0.0")
    if not version.startswith("2."):
        errors.append(f"{fname}: version is {version}, expected 2.x.x")

    for atk in data.get("attacks", []):
        aid = atk.get("id", "???")

        # Required fields
        for field in V2_ATTACK_FIELDS:
            if field not in atk:
                errors.append(f"{fname}/{aid}: missing field '{field}'")

        # Detector structure
        det = atk.get("detector", {})
        if "postconditions" not in det:
            errors.append(f"{fname}/{aid}: detector missing 'postconditions'")

        for section in ["preconditions", "postconditions"]:
            for i, cond in enumerate(det.get(section, [])):
                for field in V2_CONDITION_FIELDS:
                    if field not in cond:
                        errors.append(f"{fname}/{aid}/{section}[{i}]: missing '{field}'")
                surface = cond.get("apply_on")
                if surface and surface not in VALID_SURFACES:
                    errors.append(f"{fname}/{aid}/{section}[{i}]: invalid apply_on '{surface}'")

        # success_criteria must be a list
        sc = atk.get("success_criteria")
        if sc is not None and not isinstance(sc, list):
            errors.append(f"{fname}/{aid}: success_criteria must be a list")

        # risk_surface must be a list
        rs = atk.get("risk_surface")
        if rs is not None and not isinstance(rs, list):
            errors.append(f"{fname}/{aid}: risk_surface must be a list")

        # requires_proxy consistency
        if atk.get("requires_proxy") and "black_box" in atk.get("supported_modes", []):
            errors.append(f"{fname}/{aid}: requires_proxy=true but supports black_box")

if errors:
    print(f"STRUCTURAL ERRORS ({len(errors)}):")
    for e in errors:
        print(f"  ✗ {e}")
else:
    print("All v2 structural checks passed ✓")
    print("  - defaults block present in all files")
    print("  - all attacks have preconditions/postconditions with apply_on")
    print("  - success_criteria, risk_surface, breach_surface, requires_proxy present")
    print("  - no requires_proxy=true + black_box conflict")
