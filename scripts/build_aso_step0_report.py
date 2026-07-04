#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_OUTPUT_DIR = Path("docs") / "reports" / "data" / "2026-07-02-gate0"
DEFAULT_UTILITY_REPORT = DEFAULT_OUTPUT_DIR / "aso_step0_utility" / "gate0_text_utility_report.json"
DEFAULT_DATASET = "ASO"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the spec-8.4 ASO step-0 frozen decision report from a single-dataset utility artifact."
    )
    parser.add_argument("--utility-report", type=Path, default=DEFAULT_UTILITY_REPORT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    return parser.parse_args()


def load_dataset_row(utility_report_path: Path, dataset_name: str) -> tuple[dict[str, object], dict[str, object]]:
    payload = json.loads(utility_report_path.read_text(encoding="utf-8"))
    dataset_row = next(
        (row for row in payload.get("datasets", []) if str(row.get("dataset")) == dataset_name),
        None,
    )
    if dataset_row is None:
        raise ValueError(f"dataset {dataset_name!r} missing from utility report {utility_report_path}")
    return payload, dataset_row


def prediction_tier(phi_u_ds: float) -> tuple[str, str, str]:
    if phi_u_ds >= 0.5:
        return (
            "phi_ge_0p5_positive",
            "delta_test_p2_ndcg10 > 0",
            "launch_validation_run",
        )
    if phi_u_ds > 0.0:
        return (
            "phi_between_0_and_0p5_small_abs_delta",
            "small |delta_test_p2_ndcg10|",
            "launch_validation_run",
        )
    return (
        "phi_eq_0_parity",
        "|delta_test_p2_ndcg10| < 0.01",
        "no_run_record_only",
    )


def build_report(utility_report_path: Path, dataset_name: str) -> dict[str, object]:
    payload, dataset_row = load_dataset_row(utility_report_path, dataset_name)
    phi_u_ds = float(dataset_row["phi_u_ds"])
    tier, prediction, run_decision = prediction_tier(phi_u_ds)

    return {
        "dataset": dataset_name,
        "utility_report_path": str(utility_report_path),
        "protocol": payload.get("protocol", {}),
        "u_ds_popularity": float(dataset_row["u_ds_popularity"]),
        "phi_u_ds": phi_u_ds,
        "bank_hash": str(dataset_row["bank_hash"]),
        "split_hash": str(dataset_row["split_hash"]),
        "prediction_tier": tier,
        "pre_registered_prediction": prediction,
        "run_decision": run_decision,
        "frozen_rules": {
            "rule_1": "phi >= 0.5 => predict delta_test_p2_ndcg10 > 0; 0 < phi < 0.5 => predict small |delta|; phi = 0 => predict |delta| < 0.01",
            "rule_2": "phi > 0 => ASO enters the validation-run set; phi = 0 => default no-run and record only as the fifth inversion statistic",
            "rule_3": "ASO is a pure out-of-sample prediction point because no first-generation result existed when the prediction was frozen",
            "rule_4": "No threshold, prediction, or launch-rule change is permitted after observing U_ds(ASO)",
        },
        "scientific_role": "pure_out_of_sample_prediction_point",
    }


def write_report(report: dict[str, object], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "aso_step0_report.json"
    md_path = output_dir / "aso_step0_report.md"

    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# ASO Step-0 Frozen Decision",
        "",
        f"- Dataset: `{report['dataset']}`",
        f"- Utility artifact: `{report['utility_report_path']}`",
        f"- `U_ds(popularity)`: `{report['u_ds_popularity']}`",
        f"- `phi(U_ds)`: `{report['phi_u_ds']}`",
        f"- Prediction tier: `{report['prediction_tier']}`",
        f"- Pre-registered prediction: `{report['pre_registered_prediction']}`",
        f"- Run decision: `{report['run_decision']}`",
        f"- Bank hash: `{report['bank_hash']}`",
        f"- Split hash: `{report['split_hash']}`",
        "",
        "## Frozen Rules",
        "",
        f"1. {report['frozen_rules']['rule_1']}",
        f"2. {report['frozen_rules']['rule_2']}",
        f"3. {report['frozen_rules']['rule_3']}",
        f"4. {report['frozen_rules']['rule_4']}",
        "",
        "## Interpretation",
        "",
        f"- Scientific role: `{report['scientific_role']}`",
        "- This report is a frozen readout of the existing utility artifact. It does not alter any threshold or parameter.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> None:
    args = parse_args()
    report = build_report(args.utility_report, args.dataset)
    json_path, md_path = write_report(report, args.output_dir)
    print(f"WROTE {json_path}")
    print(f"WROTE {md_path}")


if __name__ == "__main__":
    main()
