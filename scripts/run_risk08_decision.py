from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.aaai27_adapters.risk04_08 import run_risk08_decision


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit one artifact-backed fail-closed RISK-08 exit marker.")
    parser.add_argument("--queue-dir", type=Path, required=True)
    parser.add_argument("--e1-marker-json", type=Path, required=True)
    parser.add_argument("--risk05-dir", type=Path, required=True)
    parser.add_argument("--pilot-report-json", type=Path, required=True)
    args = parser.parse_args()
    marker = run_risk08_decision(
        args.queue_dir,
        e1_marker_path=args.e1_marker_json,
        risk05_root=args.risk05_dir,
        pilot_report_path=args.pilot_report_json,
    )
    print(json.dumps(marker, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
