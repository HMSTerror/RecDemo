from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.aaai27_adapters.risk04_08 import build_risk04_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an immutable dated RISK-04 corruption-bank bundle.")
    parser.add_argument("--config-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--generated-at")
    args = parser.parse_args()
    config = json.loads(args.config_json.read_text(encoding="utf-8"))
    report = build_risk04_bundle(config, args.output_dir, generated_at=args.generated_at)
    print(json.dumps({"risk04_bundle_sha256": report["artifact_sha256"], "output_dir": str(args.output_dir)}, indent=2))


if __name__ == "__main__":
    main()
