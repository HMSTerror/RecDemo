from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.aaai27_adapters.risk04_08 import build_risk05_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze the dated train-only RISK-05 preregistration.")
    parser.add_argument("--risk04-dir", type=Path, required=True)
    parser.add_argument("--preflight-json", type=Path, required=True)
    parser.add_argument("--e1-marker-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--generated-at")
    parser.add_argument("--code-revision")
    args = parser.parse_args()
    result = build_risk05_bundle(
        args.risk04_dir,
        args.preflight_json,
        args.e1_marker_json,
        args.output_dir,
        generated_at=args.generated_at,
        code_revision=args.code_revision,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
