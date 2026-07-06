#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
from datetime import date
import json
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ROOT = Path("/data/Zijian/goal/RecDemoRuns/main_table_text_side")
DEFAULT_CORE_ROOT = Path("/data/Zijian/goal/RecDemo/checkpoints-meta")
DEFAULT_OFFICIAL_REPO_ROOT = Path("/data/Zijian/goal/RecDemo_clean_main")
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "reports" / "data" / f"{date.today().isoformat()}-sprint07"
DEFAULT_DATASETS = ("Beauty", "Steam")
DEFAULT_ARMS = (
    ("full", "mainpath"),
    ("u_shuffle", "ablation_u_shuffle"),
    ("text_anchor_only", "ablation_text_anchor_only"),
    ("global_p", "ablation_global_p"),
)
CORE_SUMMARY_FILES = {
    "Steam": "best_summary_adaptive.json",
    "ML1M": "best_summary_hybrid.json",
    "Beauty": "best_summary_adaptive.json",
    "ATG": "best_summary_hybrid.json",
}
STEP_PATTERN = re.compile(r"step:\s*(\d+),")
COMPLETION_MARKERS = (
    "FINISH dataset=",
    "EARLY_STOP_TRIGGERED",
    "BEST_RESULT step=",
)


def run_dir_for(run_root: Path, dataset: str, variant: str) -> Path:
    return run_root / f"{dataset.lower()}_proposal_adaptive_{variant}"


def summary_path_for(run_root: Path, dataset: str, variant: str) -> Path:
    return run_dir_for(run_root, dataset, variant) / "checkpoints-meta" / dataset / "best_summary_proposal_adaptive.json"


def manifest_path_for(run_root: Path, dataset: str, variant: str) -> Path:
    return run_dir_for(run_root, dataset, variant) / "checkpoints-meta" / dataset / "frozen_run_manifest.json"


def log_path_for(run_root: Path, dataset: str, variant: str) -> Path:
    run_name = f"{dataset.lower()}_proposal_adaptive_{variant}"
    return run_dir_for(run_root, dataset, variant) / "logs" / f"{run_name}.log"


def core_summary_path(core_root: Path, dataset: str) -> Path:
    return core_root / dataset / CORE_SUMMARY_FILES[dataset]


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def metric(summary: dict | None, split: str, strength: str) -> float | None:
    if summary is None:
        return None
    return float(summary[split][strength]["ndcg"][2])


def fmt(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.15f}".rstrip("0").rstrip(".")


def delta(current: float | None, reference: float | None) -> float | None:
    if current is None or reference is None:
        return None
    return current - reference


def parse_manifest_repo_root(manifest: dict | None) -> str:
    if manifest is None:
        return ""
    provenance = manifest.get("provenance", {})
    if not isinstance(provenance, dict):
        return ""
    return str(provenance.get("repo_root", ""))


def parse_manifest_ablation_mode(manifest: dict | None) -> str:
    if manifest is None:
        return ""
    frozen_config = manifest.get("frozen_config", {})
    if not isinstance(frozen_config, dict):
        return ""
    return str(frozen_config.get("ablation_mode", ""))


def parse_manifest_phi_u_ds(manifest: dict | None) -> float | None:
    if manifest is None or "phi_u_ds" not in manifest:
        return None
    return float(manifest["phi_u_ds"])


def has_completion_marker(log_path: Path) -> bool:
    if not log_path.exists():
        return False
    text = log_path.read_text(encoding="utf-8", errors="ignore")
    return any(marker in text for marker in COMPLETION_MARKERS)


def parse_last_logged_step(log_path: Path) -> int | None:
    if not log_path.exists():
        return None
    last_step: int | None = None
    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = STEP_PATTERN.search(line)
        if match:
            last_step = int(match.group(1))
    return last_step


def official_status_for(
    *,
    summary_exists: bool,
    manifest_exists: bool,
    manifest_repo_root: str,
    official_repo_root: Path,
    log_path: Path,
) -> str:
    if not summary_exists:
        return "missing_summary"
    if not manifest_exists:
        return "invalid_stale"
    if manifest_repo_root != str(official_repo_root.resolve()):
        return "invalid_stale"
    if log_path.exists() and not has_completion_marker(log_path):
        return "running"
    return "completed"


def shuffle_verdict(current: float | None, full_value: float | None) -> str:
    if current is None or full_value is None:
        return ""
    return "degrades" if current < full_value else "not_degrade"


def core_equivalence_verdict(current: float | None, core_value: float | None) -> str:
    delta_value = delta(current, core_value)
    if delta_value is None:
        return ""
    return "close" if abs(delta_value) < 0.01 else "drift"


def visible_summary_field(status: str, value: float | None) -> float | None:
    if status != "completed":
        return None
    return value


def build_rows(
    *,
    run_root: Path,
    core_root: Path,
    official_repo_root: Path,
    datasets: tuple[str, ...] = DEFAULT_DATASETS,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for dataset in datasets:
        core_summary = load_json(core_summary_path(core_root, dataset))
        core_test_p2 = metric(core_summary, "test", "p2")
        core_test_p5 = metric(core_summary, "test", "p5")
        core_test_p10 = metric(core_summary, "test", "p10")

        full_summary_path = summary_path_for(run_root, dataset, "mainpath")
        full_manifest_path = manifest_path_for(run_root, dataset, "mainpath")
        full_log_path = log_path_for(run_root, dataset, "mainpath")
        full_summary = load_json(full_summary_path)
        full_manifest = load_json(full_manifest_path)
        full_status = official_status_for(
            summary_exists=full_summary_path.exists(),
            manifest_exists=full_manifest_path.exists(),
            manifest_repo_root=parse_manifest_repo_root(full_manifest),
            official_repo_root=official_repo_root,
            log_path=full_log_path,
        )
        full_test_p2 = visible_summary_field(full_status, metric(full_summary, "test", "p2"))
        full_test_p5 = visible_summary_field(full_status, metric(full_summary, "test", "p5"))
        full_test_p10 = visible_summary_field(full_status, metric(full_summary, "test", "p10"))

        for arm, variant in DEFAULT_ARMS:
            run_dir = run_dir_for(run_root, dataset, variant)
            summary_path = summary_path_for(run_root, dataset, variant)
            manifest_path = manifest_path_for(run_root, dataset, variant)
            log_path = log_path_for(run_root, dataset, variant)
            summary_payload = load_json(summary_path)
            manifest_payload = load_json(manifest_path)
            manifest_repo_root = parse_manifest_repo_root(manifest_payload)
            manifest_ablation_mode = parse_manifest_ablation_mode(manifest_payload)
            phi_u_ds = parse_manifest_phi_u_ds(manifest_payload)
            status = official_status_for(
                summary_exists=summary_path.exists(),
                manifest_exists=manifest_path.exists(),
                manifest_repo_root=manifest_repo_root,
                official_repo_root=official_repo_root,
                log_path=log_path,
            )
            val_p5 = visible_summary_field(status, metric(summary_payload, "validation", "p5"))
            test_p2 = visible_summary_field(status, metric(summary_payload, "test", "p2"))
            test_p5 = visible_summary_field(status, metric(summary_payload, "test", "p5"))
            test_p10 = visible_summary_field(status, metric(summary_payload, "test", "p10"))
            rows.append(
                {
                    "dataset": dataset,
                    "arm": arm,
                    "variant": variant,
                    "run_dir": str(run_dir),
                    "summary_path": str(summary_path),
                    "manifest_path": str(manifest_path),
                    "log_path": str(log_path),
                    "status": status,
                    "manifest_exists": "yes" if manifest_path.exists() else "no",
                    "manifest_ablation_mode": manifest_ablation_mode,
                    "phi_u_ds": fmt(phi_u_ds),
                    "log_exists": "yes" if log_path.exists() else "no",
                    "last_logged_step": "" if parse_last_logged_step(log_path) is None else str(parse_last_logged_step(log_path)),
                    "best_step": "" if status != "completed" or summary_payload is None else str(summary_payload.get("best_step", "")),
                    "best_metric": "" if status != "completed" or summary_payload is None else str(summary_payload.get("best_metric", "")),
                    "val_p5_ndcg10": fmt(val_p5),
                    "test_p2_ndcg10": fmt(test_p2),
                    "test_p5_ndcg10": fmt(test_p5),
                    "test_p10_ndcg10": fmt(test_p10),
                    "delta_test_p2_vs_full": fmt(delta(test_p2, full_test_p2)),
                    "delta_test_p5_vs_full": fmt(delta(test_p5, full_test_p5)),
                    "delta_test_p10_vs_full": fmt(delta(test_p10, full_test_p10)),
                    "delta_test_p2_vs_core": fmt(delta(test_p2, core_test_p2)),
                    "delta_test_p5_vs_core": fmt(delta(test_p5, core_test_p5)),
                    "delta_test_p10_vs_core": fmt(delta(test_p10, core_test_p10)),
                    "u_shuffle_verdict_vs_full": shuffle_verdict(test_p2, full_test_p2) if arm == "u_shuffle" else "",
                    "global_p_core_equivalence": core_equivalence_verdict(test_p2, core_test_p2) if arm == "global_p" else "",
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError("rows must not be empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_markdown(rows: list[dict[str, str]]) -> str:
    lines = [
        "# SPRINT-07 v2 control arms",
        "",
        "## Table",
        "",
        "| dataset | arm | status | val_p5_ndcg10 | test_p2_ndcg10 | test_p5_ndcg10 | test_p10_ndcg10 | delta_test_p2_vs_full | delta_test_p2_vs_core | verdict |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        verdict = row["u_shuffle_verdict_vs_full"] or row["global_p_core_equivalence"]
        lines.append(
            "| {dataset} | {arm} | {status} | {val_p5_ndcg10} | {test_p2_ndcg10} | {test_p5_ndcg10} | {test_p10_ndcg10} | {delta_test_p2_vs_full} | {delta_test_p2_vs_core} | {verdict} |".format(
                **row,
                verdict=verdict,
            )
        )

    lines.extend(
        [
            "",
            "## Chinese Summary",
            "",
        ]
    )
    for dataset in DEFAULT_DATASETS:
        dataset_rows = [row for row in rows if row["dataset"] == dataset]
        full_row = next((row for row in dataset_rows if row["arm"] == "full"), None)
        shuffle_row = next((row for row in dataset_rows if row["arm"] == "u_shuffle"), None)
        anchor_row = next((row for row in dataset_rows if row["arm"] == "text_anchor_only"), None)
        global_row = next((row for row in dataset_rows if row["arm"] == "global_p"), None)
        lines.append(f"### {dataset}")
        if full_row is None:
            lines.append("- Missing full run.")
            lines.append("")
            continue
        if full_row["status"] == "completed":
            lines.append(
                f"- full: status={full_row['status']}, phi_u_ds={full_row['phi_u_ds'] or 'NA'}, val_p5={full_row['val_p5_ndcg10'] or 'NA'}, test_p2={full_row['test_p2_ndcg10'] or 'NA'}, test_p5={full_row['test_p5_ndcg10'] or 'NA'}, test_p10={full_row['test_p10_ndcg10'] or 'NA'}."
            )
        else:
            lines.append(
                f"- full: status={full_row['status']}, phi_u_ds={full_row['phi_u_ds'] or 'NA'}, provisional metrics hidden until completed, last_logged_step={full_row['last_logged_step'] or 'NA'}."
            )
        if shuffle_row is not None:
            if shuffle_row["status"] == "completed":
                lines.append(
                    f"- u_shuffle vs full: status={shuffle_row['status']}, verdict={shuffle_row['u_shuffle_verdict_vs_full'] or 'NA'}, delta_test_p2={shuffle_row['delta_test_p2_vs_full'] or 'NA'}."
                )
            else:
                lines.append(
                    f"- u_shuffle vs full: status={shuffle_row['status']}, provisional metrics hidden until completed, last_logged_step={shuffle_row['last_logged_step'] or 'NA'}."
                )
        if anchor_row is not None:
            if anchor_row["status"] == "completed":
                lines.append(
                    f"- text_anchor_only: status={anchor_row['status']}, delta_test_p2_vs_full={anchor_row['delta_test_p2_vs_full'] or 'NA'}, last_logged_step={anchor_row['last_logged_step'] or 'NA'}."
                )
            else:
                lines.append(
                    f"- text_anchor_only: status={anchor_row['status']}, provisional metrics hidden until completed, last_logged_step={anchor_row['last_logged_step'] or 'NA'}."
                )
        if global_row is not None:
            if global_row["status"] == "completed":
                lines.append(
                    f"- global_p vs core: status={global_row['status']}, phi_u_ds={global_row['phi_u_ds'] or 'NA'}, verdict={global_row['global_p_core_equivalence'] or 'NA'}, delta_test_p2_vs_core={global_row['delta_test_p2_vs_core'] or 'NA'}."
                )
            else:
                lines.append(
                    f"- global_p vs core: status={global_row['status']}, phi_u_ds={global_row['phi_u_ds'] or 'NA'}, provisional metrics hidden until completed, last_logged_step={global_row['last_logged_step'] or 'NA'}."
                )
        if (
            full_row is not None
            and global_row is not None
            and full_row["status"] == "completed"
            and global_row["status"] == "completed"
            and full_row["phi_u_ds"] == "0"
            and full_row["test_p2_ndcg10"]
            and global_row["test_p2_ndcg10"]
            and full_row["test_p2_ndcg10"] == global_row["test_p2_ndcg10"]
        ):
            lines.append("- observed full/global_p equality is consistent with phi_u_ds=0 shutting the dataset-level gate off.")
        lines.append("")
    return "\n".join(lines) + "\n"


def write_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_markdown(rows), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the SPRINT-07 Beauty/Steam control-arm report.")
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--core-root", type=Path, default=DEFAULT_CORE_ROOT)
    parser.add_argument("--official-repo-root", type=Path, default=DEFAULT_OFFICIAL_REPO_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = build_rows(
        run_root=args.run_root,
        core_root=args.core_root,
        official_repo_root=args.official_repo_root,
    )
    output_csv = args.output_dir / "sprint07_control_table.csv"
    output_md = args.output_dir / "sprint07_control_report_zh.md"
    write_csv(output_csv, rows)
    write_markdown(output_md, rows)
    print(f"WROTE {output_csv}")
    print(f"WROTE {output_md}")
    for row in rows:
        print(
            f"{row['dataset']} arm={row['arm']} status={row['status']} "
            f"test_p2={row['test_p2_ndcg10'] or 'NA'} delta_full={row['delta_test_p2_vs_full'] or 'NA'} "
            f"last_step={row['last_logged_step'] or 'NA'}"
        )


if __name__ == "__main__":
    main()
