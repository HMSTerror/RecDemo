#!/usr/bin/env python3

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "reports" / "data" / "2026-07-02-gate0"
DEFAULT_INPUT_DIR = DEFAULT_OUTPUT_DIR / "aso_validation_inputs"
DEFAULT_STEP0_REPORT = DEFAULT_OUTPUT_DIR / "aso_step0_report.json"
DEFAULT_CORE_SUMMARY = DEFAULT_INPUT_DIR / "aso_core_best_summary_hybrid.json"
DEFAULT_RUN_SUMMARY = DEFAULT_INPUT_DIR / "aso_validation_best_summary_proposal_adaptive.json"
DEFAULT_RUN_MANIFEST = DEFAULT_INPUT_DIR / "aso_validation_frozen_run_manifest.json"
DEFAULT_OUTPUT_JSON = "aso_validation_report.json"
DEFAULT_OUTPUT_MD = "aso_validation_report.md"

DEFAULT_CORE_SUMMARY_SOURCE = "/data/Zijian/goal/RecDemo/checkpoints-meta/ASO/best_summary_hybrid.json"
DEFAULT_RUN_SUMMARY_SOURCE = (
    "/data/Zijian/goal/RecDemoRuns/main_table_text_side/aso_proposal_adaptive_mainpath/"
    "checkpoints-meta/ASO/best_summary_proposal_adaptive.json"
)
DEFAULT_RUN_MANIFEST_SOURCE = (
    "/data/Zijian/goal/RecDemoRuns/main_table_text_side/aso_proposal_adaptive_mainpath/"
    "checkpoints-meta/ASO/frozen_run_manifest.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the frozen ASO out-of-sample validation report from copied remote artifacts."
    )
    parser.add_argument("--step0-report", type=Path, default=DEFAULT_STEP0_REPORT)
    parser.add_argument("--core-summary", type=Path, default=DEFAULT_CORE_SUMMARY)
    parser.add_argument("--run-summary", type=Path, default=DEFAULT_RUN_SUMMARY)
    parser.add_argument("--run-manifest", type=Path, default=DEFAULT_RUN_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--core-summary-source", default=DEFAULT_CORE_SUMMARY_SOURCE)
    parser.add_argument("--run-summary-source", default=DEFAULT_RUN_SUMMARY_SOURCE)
    parser.add_argument("--run-manifest-source", default=DEFAULT_RUN_MANIFEST_SOURCE)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def metric(summary: dict[str, object], split: str, strength: str) -> float:
    return float(summary[split][strength]["ndcg"][2])


def build_summary_stats(
    payload: dict[str, object],
    *,
    local_path: Path,
    source_path: str,
) -> dict[str, object]:
    return {
        "local_path": str(local_path),
        "source_path": source_path,
        "sha256": sha256_file(local_path),
        "best_step": int(payload["best_step"]),
        "best_metric": float(payload["best_metric"]),
        "validation": {
            "p2_ndcg10": metric(payload, "validation", "p2"),
            "p5_ndcg10": metric(payload, "validation", "p5"),
            "p10_ndcg10": metric(payload, "validation", "p10"),
        },
        "test": {
            "p2_ndcg10": metric(payload, "test", "p2"),
            "p5_ndcg10": metric(payload, "test", "p5"),
            "p10_ndcg10": metric(payload, "test", "p10"),
        },
    }


def build_launch_checks(step0_report: dict[str, object], manifest_payload: dict[str, object]) -> list[dict[str, object]]:
    frozen_cfg = manifest_payload["frozen_config"]
    return [
        {
            "id": "dataset_matches_step0",
            "label": "Manifest dataset matches the frozen ASO step-0 report",
            "passed": str(manifest_payload["dataset"]) == str(step0_report["dataset"]) == "ASO",
            "detail": f"manifest={manifest_payload['dataset']} step0={step0_report['dataset']}",
        },
        {
            "id": "phi_positive_opened_run",
            "label": "The frozen rule opened the run because phi(U_ds) > 0",
            "passed": float(step0_report["phi_u_ds"]) > 0.0
            and str(step0_report["run_decision"]) == "launch_validation_run",
            "detail": (
                f"phi(U_ds)={float(step0_report['phi_u_ds']):.6f}; "
                f"run_decision={step0_report['run_decision']}"
            ),
        },
        {
            "id": "utility_artifact_matches_step0",
            "label": "Manifest utility artifact path matches the frozen step-0 source",
            "passed": str(manifest_payload["u_ds_artifact_path"]) == str(step0_report["utility_report_path"]),
            "detail": (
                f"manifest={manifest_payload['u_ds_artifact_path']} "
                f"step0={step0_report['utility_report_path']}"
            ),
        },
        {
            "id": "frozen_u_ds_matches_step0",
            "label": "Manifest U_ds / phi / hashes match the frozen step-0 decision",
            "passed": (
                float(manifest_payload["u_ds_popularity"]) == float(step0_report["u_ds_popularity"])
                and float(manifest_payload["phi_u_ds"]) == float(step0_report["phi_u_ds"])
                and str(manifest_payload["bank_hash"]) == str(step0_report["bank_hash"])
                and str(manifest_payload["split_hash"]) == str(step0_report["split_hash"])
            ),
            "detail": (
                f"u_ds={float(manifest_payload['u_ds_popularity']):.6f}/"
                f"{float(step0_report['u_ds_popularity']):.6f}; "
                f"phi={float(manifest_payload['phi_u_ds']):.6f}/"
                f"{float(step0_report['phi_u_ds']):.6f}"
            ),
        },
        {
            "id": "storage_policy_best_only",
            "label": "Frozen storage policy is best-checkpoint only",
            "passed": bool(frozen_cfg["write_best_checkpoint"]) and not bool(frozen_cfg["write_snapshot_checkpoint"]),
            "detail": (
                f"write_best_checkpoint={frozen_cfg['write_best_checkpoint']}; "
                f"write_snapshot_checkpoint={frozen_cfg['write_snapshot_checkpoint']}"
            ),
        },
        {
            "id": "early_stop_selector_matches_spec",
            "label": "Early-stop selector is ndcg10 at p5",
            "passed": str(frozen_cfg["early_stop_metric"]) == "ndcg10"
            and str(frozen_cfg["early_stop_strength"]) == "p5",
            "detail": (
                f"early_stop_metric={frozen_cfg['early_stop_metric']}; "
                f"early_stop_strength={frozen_cfg['early_stop_strength']}"
            ),
        },
    ]


def evaluate_prediction(prediction_tier: str, delta_test_p2_ndcg10: float) -> tuple[str, bool | None, str]:
    if prediction_tier == "phi_ge_0p5_positive":
        hit = delta_test_p2_ndcg10 > 0.0
        return "delta_test_p2_ndcg10 > 0", hit, "hit" if hit else "miss"
    if prediction_tier == "phi_eq_0_parity":
        hit = abs(delta_test_p2_ndcg10) < 0.01
        return "|delta_test_p2_ndcg10| < 0.01", hit, "hit" if hit else "miss"
    return (
        "small |delta_test_p2_ndcg10| (qualitative tier; no numeric threshold was frozen)",
        None,
        "qualitative_check_required",
    )


def build_report(
    *,
    step0_report_path: Path,
    core_summary_path: Path,
    run_summary_path: Path,
    run_manifest_path: Path,
    core_summary_source: str,
    run_summary_source: str,
    run_manifest_source: str,
) -> dict[str, object]:
    step0_report = load_json(step0_report_path)
    core_summary_payload = load_json(core_summary_path)
    run_summary_payload = load_json(run_summary_path)
    run_manifest_payload = load_json(run_manifest_path)

    if str(step0_report["dataset"]) != "ASO":
        raise ValueError(f"expected ASO step-0 report, got {step0_report['dataset']!r}")

    core_summary = build_summary_stats(
        core_summary_payload,
        local_path=core_summary_path,
        source_path=core_summary_source,
    )
    run_summary = build_summary_stats(
        run_summary_payload,
        local_path=run_summary_path,
        source_path=run_summary_source,
    )

    delta_val_p2 = run_summary["validation"]["p2_ndcg10"] - core_summary["validation"]["p2_ndcg10"]
    delta_test_p2 = run_summary["test"]["p2_ndcg10"] - core_summary["test"]["p2_ndcg10"]
    delta_test_p5 = run_summary["test"]["p5_ndcg10"] - core_summary["test"]["p5_ndcg10"]
    delta_test_p10 = run_summary["test"]["p10_ndcg10"] - core_summary["test"]["p10_ndcg10"]

    evaluation_rule, prediction_hit, prediction_outcome = evaluate_prediction(
        str(step0_report["prediction_tier"]),
        delta_test_p2,
    )
    launch_checks = build_launch_checks(step0_report, run_manifest_payload)
    all_launch_checks_passed = all(bool(check["passed"]) for check in launch_checks)

    if prediction_outcome == "hit":
        decision_summary = "The frozen ASO prediction hit: the observed delta matched the pre-registered tier."
    elif prediction_outcome == "miss":
        decision_summary = (
            "The frozen ASO prediction missed: phi(U_ds) opened the gate and predicted a positive "
            "delta, but the observed test p2 delta versus the frozen host is negative."
        )
    else:
        decision_summary = (
            "The frozen ASO prediction landed in the qualitative mid-tier, so the report records "
            "the actual delta without inventing a post-hoc numeric threshold."
        )

    return {
        "dataset": "ASO",
        "evaluated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scientific_role": step0_report["scientific_role"],
        "step0_report_path": str(step0_report_path),
        "step0_prediction_tier": step0_report["prediction_tier"],
        "pre_registered_prediction": step0_report["pre_registered_prediction"],
        "evaluation_rule": evaluation_rule,
        "prediction_hit": prediction_hit,
        "prediction_outcome": prediction_outcome,
        "decision_summary": decision_summary,
        "no_post_hoc_reframing": True,
        "core_summary": core_summary,
        "run_summary": run_summary,
        "run_manifest": {
            "local_path": str(run_manifest_path),
            "source_path": run_manifest_source,
            "sha256": sha256_file(run_manifest_path),
            "bank_hash": run_manifest_payload["bank_hash"],
            "split_hash": run_manifest_payload["split_hash"],
            "null_curve_hash": run_manifest_payload["null_curve_hash"],
            "u_ds_artifact_path": run_manifest_payload["u_ds_artifact_path"],
            "u_ds_artifact_hash": run_manifest_payload["u_ds_artifact_hash"],
            "u_ds_popularity": float(run_manifest_payload["u_ds_popularity"]),
            "phi_u_ds": float(run_manifest_payload["phi_u_ds"]),
            "random_seed": int(run_manifest_payload["random_seed"]),
            "dataset_dir": run_manifest_payload["dataset_dir"],
            "run_dir": run_manifest_payload["run_dir"],
            "frozen_config": run_manifest_payload["frozen_config"],
        },
        "launch_checks": launch_checks,
        "launch_checks_pass": all_launch_checks_passed,
        "actual_outcome": {
            "delta_val_p2_ndcg10": delta_val_p2,
            "delta_test_p2_ndcg10": delta_test_p2,
            "delta_test_p5_ndcg10": delta_test_p5,
            "delta_test_p10_ndcg10": delta_test_p10,
            "run_best_step": run_summary["best_step"],
            "run_best_metric": run_summary["best_metric"],
            "core_best_step": core_summary["best_step"],
            "core_best_metric": core_summary["best_metric"],
        },
    }


def write_report(report: dict[str, object], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / DEFAULT_OUTPUT_JSON
    md_path = output_dir / DEFAULT_OUTPUT_MD

    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    prediction_hit = report["prediction_hit"]
    if prediction_hit is True:
        prediction_status = "HIT"
    elif prediction_hit is False:
        prediction_status = "MISS"
    else:
        prediction_status = "QUALITATIVE"

    lines = [
        "# ASO Frozen Validation Report",
        "",
        f"- Dataset: `{report['dataset']}`",
        f"- Scientific role: `{report['scientific_role']}`",
        f"- Evaluated at: `{report['evaluated_at']}`",
        f"- Step-0 report: `{report['step0_report_path']}`",
        f"- Pre-registered prediction tier: `{report['step0_prediction_tier']}`",
        f"- Pre-registered prediction: `{report['pre_registered_prediction']}`",
        f"- Evaluation rule: `{report['evaluation_rule']}`",
        f"- Prediction outcome: `{prediction_status}`",
        "",
        "## Frozen Launch Checks",
        "",
    ]
    for check in report["launch_checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- `{status}` {check['label']}: {check['detail']}")

    lines.extend(
        [
            "",
            "## Artifact Sources",
            "",
            f"- Core summary copy: `{report['core_summary']['local_path']}`",
            f"- Core summary source: `{report['core_summary']['source_path']}`",
            f"- Core summary sha256: `{report['core_summary']['sha256']}`",
            f"- Run summary copy: `{report['run_summary']['local_path']}`",
            f"- Run summary source: `{report['run_summary']['source_path']}`",
            f"- Run summary sha256: `{report['run_summary']['sha256']}`",
            f"- Run manifest copy: `{report['run_manifest']['local_path']}`",
            f"- Run manifest source: `{report['run_manifest']['source_path']}`",
            f"- Run manifest sha256: `{report['run_manifest']['sha256']}`",
            "",
            "## Outcome vs Frozen Host",
            "",
            "| Metric | Frozen host | Frozen-gate ASO | Delta |",
            "| --- | ---: | ---: | ---: |",
            (
                "| Validation NDCG@10 (p2) | "
                f"{report['core_summary']['validation']['p2_ndcg10']:.6f} | "
                f"{report['run_summary']['validation']['p2_ndcg10']:.6f} | "
                f"{report['actual_outcome']['delta_val_p2_ndcg10']:.6f} |"
            ),
            (
                "| Test NDCG@10 (p2) | "
                f"{report['core_summary']['test']['p2_ndcg10']:.6f} | "
                f"{report['run_summary']['test']['p2_ndcg10']:.6f} | "
                f"{report['actual_outcome']['delta_test_p2_ndcg10']:.6f} |"
            ),
            (
                "| Test NDCG@10 (p5) | "
                f"{report['core_summary']['test']['p5_ndcg10']:.6f} | "
                f"{report['run_summary']['test']['p5_ndcg10']:.6f} | "
                f"{report['actual_outcome']['delta_test_p5_ndcg10']:.6f} |"
            ),
            (
                "| Test NDCG@10 (p10) | "
                f"{report['core_summary']['test']['p10_ndcg10']:.6f} | "
                f"{report['run_summary']['test']['p10_ndcg10']:.6f} | "
                f"{report['actual_outcome']['delta_test_p10_ndcg10']:.6f} |"
            ),
            "",
            "## Decision",
            "",
            f"- {report['decision_summary']}",
            "- This report records the frozen prediction exactly as specified. It does not change any threshold, tier, or launch rule after observing ASO.",
        ]
    )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> None:
    args = parse_args()
    report = build_report(
        step0_report_path=args.step0_report,
        core_summary_path=args.core_summary,
        run_summary_path=args.run_summary,
        run_manifest_path=args.run_manifest,
        core_summary_source=args.core_summary_source,
        run_summary_source=args.run_summary_source,
        run_manifest_source=args.run_manifest_source,
    )
    json_path, md_path = write_report(report, args.output_dir)
    print(f"WROTE {json_path}")
    print(f"WROTE {md_path}")


if __name__ == "__main__":
    main()
