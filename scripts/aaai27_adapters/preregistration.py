from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .common import atomic_write_json, stable_sha256


LEVELS = (0, 20, 40, 60, 80, 100)
PILOT_LEVELS = (0, 60, 100)


def _reject_validation_test_keys(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).casefold()
            if lowered in {"validation_metric", "test_metric", "validation_result", "test_result", "validation_ndcg10", "test_ndcg10"}:
                raise ValueError(f"validation/test metric cannot enter RISK-05 preregistration: {path}.{key}")
            _reject_validation_test_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_validation_test_keys(child, f"{path}[{index}]")


def _range_summary(clean: float, values: list[float], pooled_sd: float | None) -> dict[str, Any]:
    minimum = min(values)
    maximum = max(values)
    denominator = max(abs(clean), 1e-12)
    relative_range = abs(maximum - minimum) / denominator
    pooled = float(pooled_sd or 0.0)
    passed_relative = relative_range >= 0.20
    passed_sd = pooled >= 0.50
    return {
        "clean": float(clean),
        "minimum": float(minimum),
        "maximum": float(maximum),
        "relative_clean_range": float(relative_range),
        "pooled_sd": pooled,
        "passed_relative_range": passed_relative,
        "passed_pooled_sd": passed_sd,
        "passed": bool(passed_relative or passed_sd),
    }


def _phi_formula(primary: float, clean: float, maximum: float) -> float:
    denominator = maximum - clean
    if abs(denominator) <= 1e-12:
        return 1.0
    value = (maximum - primary) / denominator
    return float(max(0.0, min(1.0, value)))


def build_preregistration(
    preflight: dict[str, Any],
    output_dir: Path,
    *,
    generated_at: str | None = None,
    code_revision: str = "unbound-until-adapter-commit",
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"preregistration output directory already exists: {output_dir}")
    _reject_validation_test_keys(preflight)
    datasets = preflight.get("datasets")
    if not isinstance(datasets, dict) or set(datasets) != {"Beauty", "Steam"}:
        raise ValueError("RISK-05 preregistration requires exactly Beauty and Steam preflight rows")
    range_rows: dict[str, Any] = {}
    phi_rows: dict[str, Any] = {}
    for dataset in ("Beauty", "Steam"):
        row = datasets[dataset]
        if not isinstance(row, dict):
            raise ValueError(f"preflight row for {dataset} must be an object")
        levels = row.get("levels")
        if not isinstance(levels, list) or [int(level.get("level", -1)) for level in levels] != list(LEVELS):
            raise ValueError(f"{dataset} must contain exactly levels {LEVELS}")
        clean = float(row.get("clean_epe", levels[0].get("epe")))
        values = [float(level.get("epe")) for level in levels]
        pooled_sd = row.get("pooled_sd")
        range_rows[dataset] = _range_summary(clean, values, float(pooled_sd) if pooled_sd is not None else None)
        phi_rows[dataset] = {
            str(level): _phi_formula(float(level_value), clean, values[-1])
            for level, level_value in zip(LEVELS, values)
        }
    range_pass = any(bool(row["passed"]) for row in range_rows.values())
    generated_at = generated_at or datetime.now().astimezone().isoformat(timespec="seconds")
    frozen = {
        "levels": list(LEVELS),
        "pilot_levels": list(PILOT_LEVELS),
        "corruption_seed": 100,
        "risk_sampling_seed": 7,
        "primary_statistic": "EPE",
        "range_gate": {
            "relative_clean_range_min": 0.20,
            "pooled_sd_min": 0.50,
            "interpretation": "pilot is permitted only when at least one of Beauty or Steam has a preregistered primary-risk range pass; per-dataset outcomes remain visible",
        },
        "phi_R": {
            "formula": "clip((R_100 - R_D) / (R_100 - R_clean), 0, 1)",
            "monotonicity": "non-increasing in primary risk R_D",
            "uses_validation_or_test": False,
        },
        "pilot_predictions": {
            "phi_R_ge_0_5": "delta_test_ndcg10 > 0",
            "phi_R_between_0_and_0_5": "abs(delta_test_ndcg10) < 0.01 (descriptive tier)",
            "phi_R_eq_0": "abs(delta_test_ndcg10) < 0.01",
        },
        "thresholds": {
            "spearman_rho_max": -0.5,
            "adjacent_ndcg10_reversal_tolerance": 0.002,
            "worst_delta_improvement": 0.002,
        },
        "arm_count": {"e1_pass": 14, "e1_fail_audit": 8},
        "no_rescue": True,
        "no_second_seed": True,
        "evaluator_version": "e0_full_tail_v2",
        "selector_version": "validation-ndcg10-rowweighted-v1",
    }
    result: dict[str, Any] = {
        "schema_version": 1,
        "report_name": "AAAI-RISK-05 frozen prospective risk protocol",
        "generated_at": generated_at,
        "code_revision": code_revision,
        "range_gate": {"status": "pass" if range_pass else "stop", "datasets": range_rows},
        "phi_R": phi_rows,
        "frozen_thresholds": frozen["thresholds"],
        "frozen_protocol": frozen,
        "source_hashes": preflight.get("source_hashes", {}),
        "preflight_sha256": stable_sha256(preflight),
        "pilot_authorized": bool(range_pass),
        "downstream_training_authorized": False,
        "decision": "continue_to_pilot_after_E1_terminal" if range_pass else "no_go_stop_pilot",
    }
    result["artifact_sha256"] = stable_sha256(result)
    output_dir.mkdir(parents=True)
    atomic_write_json(output_dir / "risk_preregistration.json", result)
    atomic_write_json(
        output_dir / ("RISK-05_PASS.json" if range_pass else "RISK-05_STOP.json"),
        {
            "schema_version": 1,
            "risk_id": "RISK-05",
            "outcome": "pass" if range_pass else "stop",
            "pilot_authorized": bool(range_pass),
            "preregistration_sha256": stable_sha256(result),
            "preflight_sha256": result["preflight_sha256"],
            "generated_at": generated_at,
        },
    )
    markdown = [
        "# AAAI-RISK-05 frozen prospective risk protocol",
        "",
        f"Generated at: `{generated_at}`",
        f"Range gate: **{'PASS' if range_pass else 'STOP'}**",
        "",
        "This file is train-only. No validation/test metric was read while freezing the protocol.",
        "",
        "| Dataset | Relative clean range | Pooled SD | Dataset gate |",
        "|---|---:|---:|---|",
    ]
    for dataset in ("Beauty", "Steam"):
        row = range_rows[dataset]
        markdown.append(f"| {dataset} | {row['relative_clean_range']:.6g} | {row['pooled_sd']:.6g} | {'pass' if row['passed'] else 'fail'} |")
    markdown.extend(["", "Frozen phi_R: `clip((R_100 - R_D) / (R_100 - R_clean), 0, 1)`.", "", "No rescue tuning, extra seed, new metric, or changed threshold is authorized after this artifact.", ""])
    (output_dir / "risk_preregistration.md").write_text("\n".join(markdown), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze RISK-05 from a train-only preflight JSON.")
    parser.add_argument("--preflight-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--generated-at")
    parser.add_argument("--code-revision", default="unbound-until-adapter-commit")
    args = parser.parse_args()
    preflight = json.loads(args.preflight_json.read_text(encoding="utf-8"))
    result = build_preregistration(preflight, args.output_dir, generated_at=args.generated_at, code_revision=args.code_revision)
    print(json.dumps({"artifact_sha256": result["artifact_sha256"], "decision": result["decision"]}, indent=2))


if __name__ == "__main__":
    main()

