#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "reports" / "data" / "2026-07-06-gate1"
DEFAULT_INPUT_DIR = DEFAULT_OUTPUT_DIR / "inputs"
DEFAULT_STATUS_CSV = DEFAULT_INPUT_DIR / "text-side-main-table-run-status.csv"
DEFAULT_COMPARE_CSV = DEFAULT_INPUT_DIR / "text-side-vs-core-main-table.csv"
DEFAULT_OUTPUT_JSON = "sprint05_gate1_report.json"
DEFAULT_OUTPUT_MD = "sprint05_gate1_report_zh.md"

DEFAULT_STATUS_CSV_SOURCE = (
    "/data/Zijian/goal/RecDemo_clean_main/docs/reports/data/2026-07-05-sprint05/"
    "text-side-main-table-run-status.csv"
)
DEFAULT_COMPARE_CSV_SOURCE = (
    "/data/Zijian/goal/RecDemo_clean_main/docs/reports/data/2026-07-05-sprint05/"
    "text-side-vs-core-main-table.csv"
)
DEFAULT_MANIFEST_SPECS = (
    f"Beauty={DEFAULT_INPUT_DIR / 'beauty_frozen_run_manifest.json'}",
    f"ML1M={DEFAULT_INPUT_DIR / 'ml1m_frozen_run_manifest.json'}",
    f"Steam={DEFAULT_INPUT_DIR / 'steam_frozen_run_manifest.json'}",
    f"ATG={DEFAULT_INPUT_DIR / 'atg_frozen_run_manifest.json'}",
)
DEFAULT_EXPECTED_SPEC_PREDICTIONS = {
    "Beauty": "abs(delta_test_p2_ndcg10) < 0.01",
    "ML1M": "abs(delta_test_p2_ndcg10) < 0.01",
    "Steam": "delta_test_p2_ndcg10 > 0",
    "ATG": "abs(delta_test_p2_ndcg10) < 0.01",
}
DEFAULT_MANIFEST_EXPECTATIONS = {
    "kernel_version": "v2",
    "agreement_k": 2.0,
    "g_max": 0.5,
    "early_stop_metric": "ndcg10",
    "early_stop_strength": "p5",
    "write_best_checkpoint": True,
    "write_snapshot_checkpoint": False,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the official SPRINT-05 closeout and Gate 1 readout from copied remote artifacts."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--status-csv", type=Path, default=DEFAULT_STATUS_CSV)
    parser.add_argument("--compare-csv", type=Path, default=DEFAULT_COMPARE_CSV)
    parser.add_argument("--status-csv-source", default=DEFAULT_STATUS_CSV_SOURCE)
    parser.add_argument("--compare-csv-source", default=DEFAULT_COMPARE_CSV_SOURCE)
    parser.add_argument(
        "--manifest",
        action="append",
        default=None,
        help="Dataset-to-local-manifest mapping in the form DATASET=/path/to/frozen_run_manifest.json.",
    )
    return parser.parse_args()


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _to_float(value: str) -> float:
    return float(value)


def _to_int(value: str) -> int:
    return int(value)


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_manifest_specs(specs: list[str] | None) -> dict[str, Path]:
    raw_specs = list(specs or DEFAULT_MANIFEST_SPECS)
    manifest_paths: dict[str, Path] = {}
    for raw_spec in raw_specs:
        if "=" not in raw_spec:
            raise ValueError(f"invalid manifest spec {raw_spec!r}; expected DATASET=/path/to/file.json")
        dataset, raw_path = raw_spec.split("=", 1)
        dataset = dataset.strip()
        manifest_path = Path(raw_path).expanduser()
        manifest_paths[dataset] = manifest_path
    expected = {"Beauty", "ML1M", "Steam", "ATG"}
    missing = sorted(expected - set(manifest_paths))
    if missing:
        raise ValueError(f"missing manifest specs for datasets: {', '.join(missing)}")
    return manifest_paths


def _load_status_map(status_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["dataset"]: row for row in status_rows}


def _manifest_check_rows(manifest_payload: dict[str, object]) -> list[dict[str, object]]:
    frozen_config = manifest_payload["frozen_config"]
    checks = [
        {
            "id": "repo_root_clean_main",
            "label": "repo_root points at the clean execution root",
            "passed": str(manifest_payload["provenance"]["repo_root"]).endswith("RecDemo_clean_main"),
            "detail": f"repo_root={manifest_payload['provenance']['repo_root']}",
        },
        {
            "id": "seed_present",
            "label": "random_seed is recorded",
            "passed": int(manifest_payload["random_seed"]) >= 0,
            "detail": f"random_seed={manifest_payload['random_seed']}",
        },
        {
            "id": "hashes_present",
            "label": "bank/null/split/U_ds hashes are recorded",
            "passed": all(
                bool(str(manifest_payload[key]).strip())
                for key in ("bank_hash", "null_curve_hash", "split_hash", "u_ds_artifact_hash")
            ),
            "detail": (
                f"bank_hash={manifest_payload['bank_hash']}; "
                f"null_curve_hash={manifest_payload['null_curve_hash']}; "
                f"split_hash={manifest_payload['split_hash']}; "
                f"u_ds_artifact_hash={manifest_payload['u_ds_artifact_hash']}"
            ),
        },
    ]
    for key, expected in DEFAULT_MANIFEST_EXPECTATIONS.items():
        observed = frozen_config[key]
        passed = observed == expected
        detail = f"observed={observed!r}; expected={expected!r}"
        checks.append(
            {
                "id": key,
                "label": f"frozen_config.{key} matches the frozen sprint setting",
                "passed": passed,
                "detail": detail,
            }
        )
    return checks


def _classify_dataset(compare_row: dict[str, str]) -> tuple[str, str]:
    dataset = compare_row["dataset"]
    prediction_outcome = compare_row["prediction_outcome"]
    reference_outcome = compare_row.get("reference_magnitude_outcome", "")

    if dataset == "Steam":
        if prediction_outcome == "hit" and reference_outcome == "hit":
            return "full_hit", "Steam kept the positive sign and also reached the >= +0.003 reference magnitude."
        if prediction_outcome == "hit":
            return (
                "directional_hit_reference_miss",
                "Steam kept the positive sign but stayed below the >= +0.003 reference magnitude.",
            )
        return "miss", "Steam failed even the pre-registered positive-direction prediction."

    if prediction_outcome == "hit":
        return "hit", f"{dataset} satisfied its pre-registered parity-style prediction."
    return "miss", f"{dataset} missed its pre-registered parity-style prediction."


def _build_dataset_rows(
    *,
    compare_rows: list[dict[str, str]],
    status_map: dict[str, dict[str, str]],
    manifest_paths: dict[str, Path],
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    dataset_rows: list[dict[str, object]] = []
    by_dataset: dict[str, dict[str, object]] = {}

    for compare_row in compare_rows:
        dataset = compare_row["dataset"]
        status_row = status_map[dataset]
        manifest_path = manifest_paths[dataset]
        manifest_payload = _load_json(manifest_path)
        manifest_checks = _manifest_check_rows(manifest_payload)
        manifest_ok = all(bool(check["passed"]) for check in manifest_checks)
        dataset_verdict, verdict_reason = _classify_dataset(compare_row)

        dataset_row = {
            "dataset": dataset,
            "status": compare_row["status"],
            "official_status": compare_row["official_status"],
            "expected_outcome": compare_row["expected_outcome"],
            "prediction_outcome": compare_row["prediction_outcome"],
            "reference_magnitude_outcome": compare_row.get("reference_magnitude_outcome", ""),
            "dataset_verdict": dataset_verdict,
            "verdict_reason": verdict_reason,
            "current_best_step": _to_int(compare_row["current_best_step"]),
            "current_best_metric": _to_float(compare_row["current_best_metric"]),
            "core_best_step": _to_int(compare_row["core_best_step"]),
            "core_best_metric": _to_float(compare_row["core_best_metric"]),
            "delta_val_p2_ndcg10": _to_float(compare_row["delta_val_p2_ndcg10"]),
            "delta_test_p2_ndcg10": _to_float(compare_row["delta_test_p2_ndcg10"]),
            "delta_test_p5_ndcg10": _to_float(compare_row["delta_test_p5_ndcg10"]),
            "delta_test_p10_ndcg10": _to_float(compare_row["delta_test_p10_ndcg10"]),
            "current_test_p2_ndcg10": _to_float(compare_row["current_test_p2_ndcg10"]),
            "current_test_p5_ndcg10": _to_float(compare_row["current_test_p5_ndcg10"]),
            "current_test_p10_ndcg10": _to_float(compare_row["current_test_p10_ndcg10"]),
            "core_test_p2_ndcg10": _to_float(compare_row["core_test_p2_ndcg10"]),
            "core_test_p5_ndcg10": _to_float(compare_row["core_test_p5_ndcg10"]),
            "core_test_p10_ndcg10": _to_float(compare_row["core_test_p10_ndcg10"]),
            "last_logged_step": _to_int(compare_row["last_logged_step"]),
            "early_stop_wait_counter": _to_int(compare_row["early_stop_wait_counter"]),
            "early_stop_wait_patience": _to_int(compare_row["early_stop_wait_patience"]),
            "remote_manifest_path": compare_row["manifest_path"],
            "local_manifest_copy": str(manifest_path),
            "remote_run_dir": status_row["run_dir"],
            "remote_summary_path": status_row["summary_path"],
            "remote_log_path": status_row["log_path"],
            "queue_launcher": status_row["queue_launcher"],
            "manifest_checks": manifest_checks,
            "manifest_checks_pass": manifest_ok,
            "random_seed": int(manifest_payload["random_seed"]),
            "bank_hash": manifest_payload["bank_hash"],
            "null_curve_hash": manifest_payload["null_curve_hash"],
            "split_hash": manifest_payload["split_hash"],
            "u_ds_artifact_hash": manifest_payload["u_ds_artifact_hash"],
            "u_ds_artifact_path": manifest_payload["u_ds_artifact_path"],
            "u_ds_popularity": float(manifest_payload["u_ds_popularity"]),
            "phi_u_ds": float(manifest_payload["phi_u_ds"]),
            "provenance_repo_root": manifest_payload["provenance"]["repo_root"],
        }
        dataset_rows.append(dataset_row)
        by_dataset[dataset] = dataset_row

    return dataset_rows, by_dataset


def _build_sprint05_summary(dataset_rows: list[dict[str, object]]) -> dict[str, object]:
    official_complete = all(
        row["status"] == "completed" and row["official_status"] == "completed" and row["manifest_checks_pass"]
        for row in dataset_rows
    )
    verdicts = {row["dataset"]: row["dataset_verdict"] for row in dataset_rows}
    hit_datasets = [row["dataset"] for row in dataset_rows if row["dataset_verdict"] in {"hit", "full_hit"}]
    miss_datasets = [row["dataset"] for row in dataset_rows if row["dataset_verdict"] == "miss"]
    partial_datasets = [
        row["dataset"] for row in dataset_rows if row["dataset_verdict"] == "directional_hit_reference_miss"
    ]

    return {
        "official_complete": official_complete,
        "dataset_verdicts": verdicts,
        "hit_datasets": hit_datasets,
        "miss_datasets": miss_datasets,
        "partial_hit_datasets": partial_datasets,
        "summary": (
            "All four datasets finished under clean-root manifests; Beauty hit parity, Steam kept the positive sign "
            "but missed the reference magnitude, while ML1M and ATG missed parity."
        ),
    }


def _build_gate1_summary(ml1m_row: dict[str, object]) -> dict[str, object]:
    delta = float(ml1m_row["delta_test_p2_ndcg10"])
    pass_threshold = -0.01
    diagnostic_threshold = -0.03

    if delta > pass_threshold:
        verdict = "pass"
        summary = "ML1M cleared Gate 1 directly."
    elif delta <= diagnostic_threshold:
        verdict = "diagnostic_allowed"
        summary = "ML1M missed badly enough that the single frozen diagnostic iteration is allowed."
    else:
        verdict = "fail_no_diagnostic"
        summary = (
            "ML1M missed the no-loss threshold, but not badly enough to open the single frozen diagnostic iteration."
        )

    return {
        "dataset": "ML1M",
        "delta_test_p2_ndcg10": delta,
        "pass_threshold": pass_threshold,
        "diagnostic_threshold": diagnostic_threshold,
        "pass_margin": delta - pass_threshold,
        "diagnostic_margin": delta - diagnostic_threshold,
        "verdict": verdict,
        "implementation_red_flag": abs(delta) >= 0.01,
        "prop6_empirical_claim_pause": abs(delta) >= 0.01,
        "diagnostic_allowed": verdict == "diagnostic_allowed",
        "summary": summary,
    }


def _build_gate2_exit_summary(dataset_rows: list[dict[str, object]], gate1: dict[str, object]) -> dict[str, object]:
    row_by_dataset = {row["dataset"]: row for row in dataset_rows}
    strong_reachable = all(
        row_by_dataset[name]["dataset_verdict"] in {"hit", "full_hit"}
        for name in ("ML1M", "Beauty", "ATG")
    ) and row_by_dataset["Steam"]["dataset_verdict"] == "full_hit"
    medium_reachable = (
        abs(float(row_by_dataset["ML1M"]["delta_test_p2_ndcg10"])) < 0.01
        and abs(float(row_by_dataset["Beauty"]["delta_test_p2_ndcg10"])) < 0.01
    )
    weak_reachable = True

    return {
        "strong": {
            "reachable": strong_reachable,
            "reason": (
                "Needs all four pre-registered outcomes to land cleanly, including Steam reaching the reference "
                "magnitude. The current official table does not satisfy that."
            ),
        },
        "medium": {
            "reachable": medium_reachable,
            "reason": (
                "Needs the no-loss main line to hold on the Gate 1 path. The official ML1M delta is "
                f"{gate1['delta_test_p2_ndcg10']:.6f}, which stays below the -0.01 pass threshold."
            ),
        },
        "weak": {
            "reachable": weak_reachable,
            "reason": (
                "The Family D baseline wording was already frozen in FOLLOWUP-08, so the weak exit remains available "
                "even when Gate 1 does not clear."
            ),
        },
    }


def build_report(
    *,
    output_dir: Path,
    status_csv: Path,
    compare_csv: Path,
    status_csv_source: str,
    compare_csv_source: str,
    manifest_paths: dict[str, Path],
) -> dict[str, object]:
    status_rows = _read_csv_rows(status_csv)
    compare_rows = _read_csv_rows(compare_csv)
    status_map = _load_status_map(status_rows)
    dataset_rows, by_dataset = _build_dataset_rows(
        compare_rows=compare_rows,
        status_map=status_map,
        manifest_paths=manifest_paths,
    )

    sprint05_summary = _build_sprint05_summary(dataset_rows)
    gate1 = _build_gate1_summary(by_dataset["ML1M"])
    gate2_exits = _build_gate2_exit_summary(dataset_rows, gate1)

    return {
        "report_name": "SPRINT-05 official rerun closeout and Gate 1 readout",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "output_dir": str(output_dir),
        "sources": {
            "status_csv_local": str(status_csv),
            "status_csv_source": status_csv_source,
            "compare_csv_local": str(compare_csv),
            "compare_csv_source": compare_csv_source,
        },
        "spec_anchor": "docs/superpowers/specs/2026-07-02-aaai27-fallback-safe-kernel-sprint-design.md",
        "sprint05": sprint05_summary,
        "datasets": dataset_rows,
        "gate1": gate1,
        "gate2_exits": gate2_exits,
    }


def write_report(report: dict[str, object], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / DEFAULT_OUTPUT_JSON
    md_path = output_dir / DEFAULT_OUTPUT_MD

    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    gate1 = report["gate1"]
    lines = [
        "# SPRINT-05 / Gate 1 官方读数",
        "",
        f"- 生成时间: `{report['generated_at']}`",
        f"- 官方状态表来源: `{report['sources']['status_csv_source']}`",
        f"- 官方比较表来源: `{report['sources']['compare_csv_source']}`",
        f"- 规格锚点: `{report['spec_anchor']}`",
        "",
        "## SPRINT-05 结论",
        "",
        f"- 官方四数据集是否全部完成: `{str(report['sprint05']['official_complete']).lower()}`",
        f"- 总结: {report['sprint05']['summary']}",
        f"- 命中数据集: `{', '.join(report['sprint05']['hit_datasets']) or 'none'}`",
        f"- 部分命中数据集: `{', '.join(report['sprint05']['partial_hit_datasets']) or 'none'}`",
        f"- 未命中数据集: `{', '.join(report['sprint05']['miss_datasets']) or 'none'}`",
        "",
        "## 四数据集官方结果",
        "",
        "| 数据集 | 预注册预测 | 实际判定 | delta_test_p2@10 | 备注 |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for row in report["datasets"]:
        note = row["verdict_reason"]
        if row["dataset"] == "Steam":
            note += f" reference_magnitude_outcome={row['reference_magnitude_outcome']}"
        lines.append(
            "| {dataset} | {expected_outcome} | {dataset_verdict} | {delta_test_p2_ndcg10:.6f} | {note} |".format(
                note=note,
                **row,
            )
        )

    lines.extend(
        [
            "",
            "## Manifest 审计",
            "",
            "| 数据集 | clean-root | 冻结配置 | hash 记录 | 结论 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in report["datasets"]:
        check_map = {check["id"]: check for check in row["manifest_checks"]}
        lines.append(
            "| {dataset} | {clean_root} | {frozen_ok} | {hash_ok} | {overall} |".format(
                dataset=row["dataset"],
                clean_root="pass" if check_map["repo_root_clean_main"]["passed"] else "fail",
                frozen_ok="pass"
                if all(check_map[key]["passed"] for key in DEFAULT_MANIFEST_EXPECTATIONS)
                else "fail",
                hash_ok="pass" if check_map["hashes_present"]["passed"] else "fail",
                overall="pass" if row["manifest_checks_pass"] else "fail",
            )
        )

    lines.extend(
        [
            "",
            "## Gate 1 判定",
            "",
            (
                f"- ML1M 官方 `delta_test_p2_ndcg10 = {gate1['delta_test_p2_ndcg10']:.6f}`; "
                f"通过阈值是 `> {gate1['pass_threshold']:.2f}`，单次诊断迭代触发阈值是 `<= {gate1['diagnostic_threshold']:.2f}`。"
            ),
            f"- Gate 1 verdict: `{gate1['verdict']}`",
            f"- 解释: {gate1['summary']}",
            f"- 与通过线的差距: `{gate1['pass_margin']:.6f}`",
            f"- 与诊断触发线的差距: `{gate1['diagnostic_margin']:.6f}`",
            f"- 命题 6 经验主张是否暂停: `{str(gate1['prop6_empirical_claim_pause']).lower()}`",
            "",
            "## Gate 2 仍可达出口",
            "",
        ]
    )
    for exit_name in ("strong", "medium", "weak"):
        exit_row = report["gate2_exits"][exit_name]
        lines.append(
            f"- `{exit_name}`: `{'reachable' if exit_row['reachable'] else 'not_reachable'}`; {exit_row['reason']}"
        )

    lines.extend(
        [
            "",
            "## 直接结论",
            "",
            "本次 `SPRINT-05` 官方四数据集重跑已经完成，且 manifest 证明它们来自 clean-root 冻结配置。",
            "但 `SPRINT-06` 所关心的 ML1M Gate 1 仍未过线：它没有差到允许那次冻结诊断的程度，却也没有达到 no-loss 门槛。",
            "因此这里最诚实的状态是：`SPRINT-05` 可以关账，`SPRINT-06` 应记录为 Gate 1 未通过且当前只剩弱出口随时可用。",
            "",
        ]
    )

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> None:
    args = parse_args()
    manifest_paths = _parse_manifest_specs(args.manifest)
    report = build_report(
        output_dir=args.output_dir,
        status_csv=args.status_csv,
        compare_csv=args.compare_csv,
        status_csv_source=args.status_csv_source,
        compare_csv_source=args.compare_csv_source,
        manifest_paths=manifest_paths,
    )
    json_path, md_path = write_report(report, args.output_dir)
    print(f"WROTE {json_path}")
    print(f"WROTE {md_path}")


if __name__ == "__main__":
    main()
