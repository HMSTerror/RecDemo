from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .common import atomic_write_json, stable_sha256


REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
TRACE_STEPS = (0, 1, 100, 1000)


def write_e1_gate_marker(output_dir: Path, trace: Mapping[str, Any], *, source_revision: str) -> dict[str, Any]:
    output_dir = Path(output_dir)
    if not REVISION_RE.fullmatch(source_revision):
        raise ValueError("source_revision must be a 40-character lowercase git revision")
    output_dir.mkdir(parents=True, exist_ok=True)
    pass_path = output_dir / "RISK-02_PASS.json"
    fail_path = output_dir / "RISK-02_FAIL.json"
    if pass_path.exists() or fail_path.exists():
        raise FileExistsError("RISK-02 already has a terminal marker")
    status = str(trace.get("status", "")).casefold()
    if status not in {"pass", "fail", "hard_stop"}:
        raise ValueError("trace status must be pass, fail, or hard_stop")
    first_divergence = trace.get("first_divergence")
    outcome = "pass" if status == "pass" and first_divergence in (None, {}) else "fail"
    marker = {
        "schema_version": 1,
        "risk_id": "RISK-02",
        "outcome": outcome,
        "random_seed": 100,
        "trace_steps": list(TRACE_STEPS),
        "fp32_tolerance": 1e-6,
        "source_revision": source_revision,
        "trace_sha256": stable_sha256(trace),
        "downstream_launch_authorized": outcome == "pass",
        "first_divergence": first_divergence,
    }
    atomic_write_json(pass_path if outcome == "pass" else fail_path, marker)
    return marker


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert one immutable E1 trace into exactly one RISK-02 gate marker.")
    parser.add_argument("--trace-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    trace = json.loads(args.trace_report.read_text(encoding="utf-8"))
    marker = write_e1_gate_marker(args.output_dir, trace, source_revision=args.source_revision)
    print(json.dumps(marker, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

