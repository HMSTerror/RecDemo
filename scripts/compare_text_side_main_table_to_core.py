#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATUS_CSV = REPO_ROOT / "docs/reports/data/2026-07-01-text-side-main-table-run-status.csv"
DEFAULT_OUTPUT_CSV = REPO_ROOT / "docs/reports/data/2026-07-01-text-side-vs-core-main-table.csv"
DEFAULT_OUTPUT_MD = REPO_ROOT / "docs/reports/data/2026-07-01-text-side-vs-core-main-table.md"
DEFAULT_OUTPUT_BASENAME = "text-side-vs-core-main-table"
DEFAULT_CORE_ROOT = Path("/data/Zijian/goal/RecDemo/checkpoints-meta")
CORE_SUMMARY_FILES = {
    "Steam": "best_summary_adaptive.json",
    "ML1M": "best_summary_hybrid.json",
    "Beauty": "best_summary_adaptive.json",
    "ATG": "best_summary_hybrid.json",
}
EVAL_STEP_PATTERN = re.compile(r"step:\s*(\d+),\s*evaluation_loss:")


def read_status_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_summary(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def metric(summary: dict | None, split: str, strength: str) -> float | None:
    if summary is None:
        return None
    return float(summary[split][strength]["ndcg"][2])


def parse_latest_live_eval(log_path: Path) -> dict | None:
    if not log_path.exists():
        return None

    def finalize(block: dict | None, latest_complete: dict | None) -> dict | None:
        if block is None:
            return latest_complete
        if "p2" in block["validation"] and "p2" in block["test"]:
            return block
        return latest_complete

    latest_complete: dict | None = None
    current_block: dict | None = None
    current_split = "validation"
    current_strength: str | None = None
    expect_ndcg_values = False

    for raw_line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        step_match = EVAL_STEP_PATTERN.search(line)
        if step_match:
            latest_complete = finalize(current_block, latest_complete)
            current_block = {
                "step": int(step_match.group(1)),
                "validation": {},
                "test": {},
            }
            current_split = "validation"
            current_strength = None
            expect_ndcg_values = False
            continue
        if current_block is None:
            continue
        if line == "test phase:":
            current_split = "test"
            current_strength = None
            expect_ndcg_values = False
            continue
        if line == "without personalzation strength":
            current_strength = "base"
            expect_ndcg_values = False
            continue
        if line.startswith("with personalzation strength "):
            strength_value = line.split()[-1]
            current_strength = {
                "2": "p2",
                "5": "p5",
                "10": "p10",
            }.get(strength_value)
            expect_ndcg_values = False
            continue
        if line.startswith("NDCG@5"):
            expect_ndcg_values = current_strength is not None
            continue
        if not expect_ndcg_values or current_strength is None:
            continue
        tokens = line.split()
        if len(tokens) != 4:
            continue
        try:
            values = [float(token) for token in tokens]
        except ValueError:
            continue
        current_block[current_split][current_strength] = {"ndcg10": values[1]}
        expect_ndcg_values = False

    return finalize(current_block, latest_complete)


def live_metric(live_eval: dict | None, split: str, strength: str) -> float | None:
    if live_eval is None:
        return None
    strength_block = live_eval.get(split, {}).get(strength)
    if strength_block is None:
        return None
    return float(strength_block["ndcg10"])


def fmt(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.15f}".rstrip("0").rstrip(".")


def delta(current: float | None, core: float | None) -> str:
    if current is None or core is None:
        return ""
    value = current - core
    return f"{value:.15f}".rstrip("0").rstrip(".")


def parse_delta(value: str) -> float | None:
    if not value:
        return None
    return float(value)


def expected_outcome_for(dataset: str) -> str:
    if dataset == "Steam":
        return "delta_test_p2_ndcg10 > 0"
    return "abs(delta_test_p2_ndcg10) < 0.01"


def prediction_outcome_for(dataset: str, delta_value: float | None) -> str:
    if delta_value is None:
        return "missing"
    if dataset == "Steam":
        return "hit" if delta_value > 0 else "miss"
    return "hit" if abs(delta_value) < 0.01 else "miss"


def reference_magnitude_outcome_for(dataset: str, delta_value: float | None) -> str:
    if dataset != "Steam":
        return ""
    if delta_value is None:
        return "missing"
    return "hit" if delta_value >= 0.003 else "miss"


def resolve_output_paths(
    output_csv: Path,
    output_md: Path,
    output_dir: Path | None,
) -> tuple[Path, Path]:
    if output_dir is None:
        return output_csv, output_md
    return (
        output_dir / f"{DEFAULT_OUTPUT_BASENAME}.csv",
        output_dir / f"{DEFAULT_OUTPUT_BASENAME}.md",
    )


def core_summary_path(core_root: Path, dataset: str) -> Path:
    summary_name = CORE_SUMMARY_FILES[dataset]
    return core_root / dataset / summary_name


def build_rows(status_rows: list[dict[str, str]], core_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for status_row in status_rows:
        dataset = status_row["dataset"]
        current_summary_path = Path(status_row["summary_path"])
        current_summary = load_summary(current_summary_path)
        log_path_value = status_row.get("log_path", "")
        current_log_path = Path(log_path_value) if log_path_value else Path()
        live_eval = parse_latest_live_eval(current_log_path) if log_path_value else None
        core_path = core_summary_path(core_root, dataset)
        core_summary = load_summary(core_path)

        current_val_p2 = metric(current_summary, "validation", "p2")
        current_test_p2 = metric(current_summary, "test", "p2")
        current_test_p5 = metric(current_summary, "test", "p5")
        current_test_p10 = metric(current_summary, "test", "p10")

        live_val_p2 = live_metric(live_eval, "validation", "p2")
        live_test_p2 = live_metric(live_eval, "test", "p2")
        live_test_p5 = live_metric(live_eval, "test", "p5")
        live_test_p10 = live_metric(live_eval, "test", "p10")

        core_val_p2 = metric(core_summary, "validation", "p2")
        core_test_p2 = metric(core_summary, "test", "p2")
        core_test_p5 = metric(core_summary, "test", "p5")
        core_test_p10 = metric(core_summary, "test", "p10")
        delta_val_p2 = delta(current_val_p2, core_val_p2)
        delta_test_p2 = delta(current_test_p2, core_test_p2)
        delta_test_p5 = delta(current_test_p5, core_test_p5)
        delta_test_p10 = delta(current_test_p10, core_test_p10)
        delta_test_p2_value = parse_delta(delta_test_p2)

        rows.append(
            {
                "dataset": dataset,
                "status": status_row["status"],
                "official_status": status_row.get("official_status", status_row["status"]),
                "manifest_path": status_row.get("manifest_path", ""),
                "manifest_exists": status_row.get("manifest_exists", "no"),
                "last_logged_step": status_row.get("last_logged_step", ""),
                "early_stop_wait_counter": status_row.get("early_stop_wait_counter", ""),
                "early_stop_wait_patience": status_row.get("early_stop_wait_patience", ""),
                "current_summary_path": str(current_summary_path),
                "current_best_step": "" if current_summary is None else str(current_summary["best_step"]),
                "current_best_metric": "" if current_summary is None else str(current_summary["best_metric"]),
                "current_val_p2_ndcg10": fmt(current_val_p2),
                "current_test_p2_ndcg10": fmt(current_test_p2),
                "current_test_p5_ndcg10": fmt(current_test_p5),
                "current_test_p10_ndcg10": fmt(current_test_p10),
                "live_eval_step": "" if live_eval is None else str(live_eval["step"]),
                "live_val_p2_ndcg10": fmt(live_val_p2),
                "live_test_p2_ndcg10": fmt(live_test_p2),
                "live_test_p5_ndcg10": fmt(live_test_p5),
                "live_test_p10_ndcg10": fmt(live_test_p10),
                "live_delta_val_p2_ndcg10": delta(live_val_p2, core_val_p2),
                "live_delta_test_p2_ndcg10": delta(live_test_p2, core_test_p2),
                "live_delta_test_p5_ndcg10": delta(live_test_p5, core_test_p5),
                "live_delta_test_p10_ndcg10": delta(live_test_p10, core_test_p10),
                "core_summary_path": str(core_path),
                "core_best_step": "" if core_summary is None else str(core_summary["best_step"]),
                "core_best_metric": "" if core_summary is None else str(core_summary["best_metric"]),
                "core_val_p2_ndcg10": fmt(core_val_p2),
                "core_test_p2_ndcg10": fmt(core_test_p2),
                "core_test_p5_ndcg10": fmt(core_test_p5),
                "core_test_p10_ndcg10": fmt(core_test_p10),
                "delta_val_p2_ndcg10": delta_val_p2,
                "delta_test_p2_ndcg10": delta_test_p2,
                "delta_test_p5_ndcg10": delta_test_p5,
                "delta_test_p10_ndcg10": delta_test_p10,
                "expected_outcome": expected_outcome_for(dataset),
                "prediction_outcome": prediction_outcome_for(dataset, delta_test_p2_value),
                "reference_magnitude_outcome": reference_magnitude_outcome_for(dataset, delta_test_p2_value),
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


def write_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "dataset",
        "status",
        "official_status",
        "manifest_exists",
        "current_best_step",
        "current_val_p2_ndcg10",
        "core_val_p2_ndcg10",
        "delta_val_p2_ndcg10",
        "live_eval_step",
        "live_test_p2_ndcg10",
        "live_delta_test_p2_ndcg10",
        "current_test_p2_ndcg10",
        "core_test_p2_ndcg10",
        "delta_test_p2_ndcg10",
        "expected_outcome",
        "prediction_outcome",
        "reference_magnitude_outcome",
    ]
    lines = [
        "# Text-side vs core main-table comparison",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row.get(header, "") for header in headers) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare text-side main-table runs against existing core anchors.")
    parser.add_argument("--status-csv", type=Path, default=DEFAULT_STATUS_CSV)
    parser.add_argument("--core-root", type=Path, default=DEFAULT_CORE_ROOT)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_csv, output_md = resolve_output_paths(
        output_csv=args.output_csv,
        output_md=args.output_md,
        output_dir=args.output_dir,
    )
    status_rows = read_status_rows(args.status_csv)
    rows = build_rows(status_rows, args.core_root)
    write_csv(output_csv, rows)
    write_markdown(output_md, rows)
    print(f"WROTE {output_csv}")
    print(f"WROTE {output_md}")
    for row in rows:
        print(
            f"{row['dataset']} status={row['status']} "
            f"delta_val_p2={row['delta_val_p2_ndcg10'] or 'na'} "
            f"delta_test_p2={row['delta_test_p2_ndcg10'] or 'na'}"
        )


if __name__ == "__main__":
    main()
