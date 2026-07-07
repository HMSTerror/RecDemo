#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
from datetime import date
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORE_ROOT = Path("/data/Zijian/goal/RecDemo/checkpoints-meta")
DEFAULT_OURS_RUN_ROOT = Path("/data/Zijian/goal/RecDemoRuns/main_table_text_side")
DEFAULT_BASELINE_RUN_ROOT = Path("/data/Zijian/goal/RecDemoRuns/close04_diffurec")
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "reports" / "data" / f"{date.today().isoformat()}-close04-diffurec"
DEFAULT_DATASETS = ("Steam", "ML1M", "Beauty", "ATG")

CORE_SUMMARY_FILES = {
    "Steam": "best_summary_adaptive.json",
    "ML1M": "best_summary_hybrid.json",
    "Beauty": "best_summary_adaptive.json",
    "ATG": "best_summary_hybrid.json",
}


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def fmt(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.15f}".rstrip("0").rstrip(".")


def delta(current: float | None, reference: float | None) -> float | None:
    if current is None or reference is None:
        return None
    return current - reference


def core_summary_path(core_root: Path, dataset: str) -> Path:
    return core_root / dataset / CORE_SUMMARY_FILES[dataset]


def ours_summary_path(ours_run_root: Path, dataset: str) -> Path:
    return (
        ours_run_root
        / f"{dataset.lower()}_proposal_adaptive_mainpath"
        / "checkpoints-meta"
        / dataset
        / "best_summary_proposal_adaptive.json"
    )


def baseline_summary_path(baseline_run_root: Path, dataset: str, baseline_method: str, baseline_seed: int) -> Path:
    return (
        baseline_run_root
        / f"{dataset.lower()}_{baseline_method.lower()}_seed{baseline_seed}"
        / "checkpoints-meta"
        / dataset
        / f"best_summary_{baseline_method.lower()}.json"
    )


def read_host_metric(summary: dict | None, metric_name: str) -> float | None:
    if summary is None:
        return None
    metric_group = "hr" if metric_name.startswith("HR") else "ndcg"
    metric_index = 2
    return float(summary["test"]["p2"][metric_group][metric_index])


def read_baseline_metric(summary: dict | None, metric_name: str) -> float | None:
    if summary is None:
        return None
    return float(summary["test"][metric_name])


def read_baseline_selector_metric(summary: dict | None) -> str:
    if summary is None:
        return ""
    selector = summary.get("selector", {})
    return str(selector.get("metric", ""))


def read_baseline_best_epoch(summary: dict | None) -> int | None:
    if summary is None:
        return None
    selector = summary.get("selector", {})
    value = selector.get("best_epoch")
    return None if value is None else int(value)


def build_rows(
    *,
    core_root: Path,
    ours_run_root: Path,
    baseline_run_root: Path,
    datasets: tuple[str, ...] = DEFAULT_DATASETS,
    baseline_method: str = "DiffuRec",
    baseline_seed: int = 100,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for dataset in datasets:
        core_path = core_summary_path(core_root, dataset)
        ours_path = ours_summary_path(ours_run_root, dataset)
        baseline_path = baseline_summary_path(baseline_run_root, dataset, baseline_method, baseline_seed)
        core_summary = load_json(core_path)
        ours_summary = load_json(ours_path)
        baseline_summary = load_json(baseline_path)

        host_hr10 = read_host_metric(core_summary, "HR@10")
        host_ndcg10 = read_host_metric(core_summary, "NDCG@10")
        ours_hr10 = read_host_metric(ours_summary, "HR@10")
        ours_ndcg10 = read_host_metric(ours_summary, "NDCG@10")
        baseline_hr10 = read_baseline_metric(baseline_summary, "HR@10")
        baseline_ndcg10 = read_baseline_metric(baseline_summary, "NDCG@10")

        rows.append(
            {
                "dataset": dataset,
                "baseline_method": baseline_method,
                "baseline_seed": str(baseline_seed),
                "baseline_summary_path": str(baseline_path),
                "core_summary_path": str(core_path),
                "ours_summary_path": str(ours_path),
                "baseline_selector_metric": read_baseline_selector_metric(baseline_summary),
                "baseline_best_epoch": "" if read_baseline_best_epoch(baseline_summary) is None else str(read_baseline_best_epoch(baseline_summary)),
                "baseline_test_hr10": fmt(baseline_hr10),
                "baseline_test_ndcg10": fmt(baseline_ndcg10),
                "host_test_hr10": fmt(host_hr10),
                "host_test_ndcg10": fmt(host_ndcg10),
                "ours_test_hr10": fmt(ours_hr10),
                "ours_test_ndcg10": fmt(ours_ndcg10),
                "delta_baseline_vs_host_hr10": fmt(delta(baseline_hr10, host_hr10)),
                "delta_baseline_vs_host_ndcg10": fmt(delta(baseline_ndcg10, host_ndcg10)),
                "delta_baseline_vs_ours_hr10": fmt(delta(baseline_hr10, ours_hr10)),
                "delta_baseline_vs_ours_ndcg10": fmt(delta(baseline_ndcg10, ours_ndcg10)),
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


def build_markdown(rows: list[dict[str, str]], baseline_method: str) -> str:
    lines = [
        f"# CLOSE-04 {baseline_method} Table",
        "",
        "| Dataset | Baseline HR@10 | Baseline NDCG@10 | Host HR@10 | Host NDCG@10 | Ours HR@10 | Ours NDCG@10 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {dataset} | {baseline_test_hr10} | {baseline_test_ndcg10} | {host_test_hr10} | {host_test_ndcg10} | {ours_test_hr10} | {ours_test_ndcg10} |".format(
                **row
            )
        )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CLOSE-04 external baseline comparison table.")
    parser.add_argument("--core-root", type=Path, default=DEFAULT_CORE_ROOT)
    parser.add_argument("--ours-run-root", type=Path, default=DEFAULT_OURS_RUN_ROOT)
    parser.add_argument("--baseline-run-root", type=Path, default=DEFAULT_BASELINE_RUN_ROOT)
    parser.add_argument("--baseline-method", default="DiffuRec")
    parser.add_argument("--baseline-seed", type=int, default=100)
    parser.add_argument("--datasets", nargs="+", default=list(DEFAULT_DATASETS))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = build_rows(
        core_root=args.core_root,
        ours_run_root=args.ours_run_root,
        baseline_run_root=args.baseline_run_root,
        datasets=tuple(args.datasets),
        baseline_method=args.baseline_method,
        baseline_seed=args.baseline_seed,
    )
    csv_path = args.output_dir / f"close04_{args.baseline_method.lower()}_comparison.csv"
    md_path = args.output_dir / f"close04_{args.baseline_method.lower()}_comparison.md"
    write_csv(csv_path, rows)
    md_path.write_text(build_markdown(rows, args.baseline_method), encoding="utf-8")
    print(json.dumps({"csv_path": str(csv_path), "md_path": str(md_path)}, indent=2))


if __name__ == "__main__":
    main()
