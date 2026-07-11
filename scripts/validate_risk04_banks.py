from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.aaai27_adapters.risk04_08 import validate_risk04_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate an immutable dated RISK-04 corruption-bank bundle.")
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--allow-severe-gate-pending", action="store_true")
    args = parser.parse_args()
    report = validate_risk04_bundle(args.bundle_dir, require_severe_gate=not args.allow_severe_gate_pending)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
