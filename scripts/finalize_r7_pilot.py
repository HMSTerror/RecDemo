from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.aaai27_adapters.pilot_report import (
    finalize_artifact_derived_risk08,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build the immutable fourteen-artifact r7 pilot report and invoke "
            "the original fail-closed RISK-08 decision exactly once."
        )
    )
    parser.add_argument("--queue-dir", type=Path, required=True)
    parser.add_argument("--risk05-dir", type=Path, required=True)
    parser.add_argument("--risk-preflight-json", type=Path, required=True)
    parser.add_argument("--pilot-report-json", type=Path)
    args = parser.parse_args()
    marker = finalize_artifact_derived_risk08(
        args.queue_dir,
        risk05_root=args.risk05_dir,
        risk_preflight_path=args.risk_preflight_json,
        report_path=args.pilot_report_json,
    )
    print(json.dumps(marker, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
