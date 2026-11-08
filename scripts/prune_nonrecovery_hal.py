#!/usr/bin/env python3
"""Exclude unrelated phone vendor HAL imports from a recovery-only build graph.

Requirements: TWRP is a standalone recovery for Amlogic SM1, not OnePlus or
Motorola Android system_server. Modify only three exact static_libs in the
Omni Android 9 services.core.unboosted Android.bp, not Java sources or TWRP.
Ambiguities: source revision compatibility and system_server targets remain
unverified; if an unrelated service is actually built, normal javac must fail.
Research: prefer upstream's recovery-focused source policy if one exists.
Risks: incorrectly weakening a full ROM build; this script MUST NEVER be used
for normal Android or LineageOS builds and is scoped to nonrelease TWRP jobs.
Verification: exact AST-like module boundary, zero/duplicate guard, unit tests,
Soong graph validation and final recovery image component inventory.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

MODULE = 'name: "services.core.unboosted"'
HALS = (
    '"vendor.oneplus.fingerprint.extension-V1.0-java",',
    '"vendor.oneplus.hardware.display-V1.0-java",',
    '"motorola.hardware.health-V1.0-java",',
)


def prune(path: Path) -> int:
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing original Omni services/core/Android.bp")
    before = path.read_text(encoding="utf-8")
    # This is deliberately not a blanket search-and-replace across Android.bp.
    if before.count(MODULE) != 1:
        raise ValueError("Expected one services.core.unboosted module definition")
    beginning = before.index(MODULE)
    boundary = before.index("\n}\n", beginning) + len("\n}\n")
    module = before[beginning:boundary]
    for hal in HALS:
        if module.count(hal) != 1 or before.count(hal) != 1:
            raise ValueError(f"Unexpected Android.bp phone HAL occurrence: {hal}")
    for hal in HALS:
        module = module.replace("        " + hal + "\n", "", 1)
        if hal in module:
            raise ValueError("Unable to remove exact obsolete reference")
    after = before[:beginning] + module + before[boundary:]
    if after == before:
        raise ValueError("No build-graph changes made")
    path.write_text(after, encoding="utf-8")
    return len(HALS)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("services_core_android_bp", type=Path)
    args = parser.parse_args()
    try:
        count = prune(args.services_core_android_bp)
    except (ValueError, OSError) as exc:
        print(f"Non-target HAL selection rejected: {exc}", file=sys.stderr)
        return 1
    print(
        f"Removed {count} unrelated OnePlus/Motorola static dependencies "
        "from a non-target Android system service. No fake modules were created."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
