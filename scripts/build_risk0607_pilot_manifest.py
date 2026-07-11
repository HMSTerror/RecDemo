from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.aaai27_adapters.risk04_08 import build_risk0607_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a dated, controller-valid seed-100 RISK-06/RISK-07 pilot queue manifest.")
    parser.add_argument("--risk05-dir", type=Path, required=True)
    parser.add_argument("--e1-marker-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--protocol-json", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(args.protocol_json.read_text(encoding="utf-8"))
    manifest = build_risk0607_manifest(args.risk05_dir, args.e1_marker_json, args.output_dir, protocol)
    print(json.dumps({"queue_id": manifest["queue_id"], "task_count": len(manifest["tasks"]), "output_dir": str(args.output_dir)}, indent=2))


if __name__ == "__main__":
    main()
