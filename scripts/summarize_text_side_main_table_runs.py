#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ROOT = Path("/data/Zijian/goal/RecDemoRuns/main_table_text_side")
DEFAULT_OUTPUT_CSV = REPO_ROOT / "docs/reports/data/2026-07-01-text-side-main-table-run-status.csv"
DEFAULT_OUTPUT_MD = REPO_ROOT / "docs/reports/data/2026-07-01-text-side-main-table-run-status.md"
DEFAULT_DATASETS = ("Steam", "ML1M", "Beauty", "ATG")
DEFAULT_OUTPUT_BASENAME = "text-side-main-table-run-status"
STEP_PATTERN = re.compile(r"step:\s*(\d+),")
EARLY_STOP_WAIT_PATTERN = re.compile(r"EARLY_STOP_WAIT counter=(\d+)/(\d+)")
FINISH_MARKER = "FINISH dataset="
COMPLETION_MARKERS = (
    FINISH_MARKER,
    "EARLY_STOP_TRIGGERED",
    "BEST_RESULT step=",
)


def run_dir_for(run_root: Path, dataset: str) -> Path:
    return run_root / f"{dataset.lower()}_proposal_adaptive_mainpath"


def summary_path_for(run_root: Path, dataset: str) -> Path:
    return run_dir_for(run_root, dataset) / "checkpoints-meta" / dataset / "best_summary_proposal_adaptive.json"


def manifest_path_for(run_root: Path, dataset: str) -> Path:
    return run_dir_for(run_root, dataset) / "checkpoints-meta" / dataset / "frozen_run_manifest.json"


def log_path_for(run_root: Path, dataset: str) -> Path:
    return run_dir_for(run_root, dataset) / "logs" / f"{dataset.lower()}_proposal_adaptive_mainpath.log"


def parse_last_logged_step(log_path: Path) -> int | None:
    if not log_path.exists():
        return None
    last_step: int | None = None
    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = STEP_PATTERN.search(line)
        if match:
            last_step = int(match.group(1))
    return last_step


def parse_latest_early_stop_wait(log_path: Path) -> tuple[int | None, int | None]:
    if not log_path.exists():
        return None, None
    latest_counter: int | None = None
    latest_patience: int | None = None
    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = EARLY_STOP_WAIT_PATTERN.search(line)
        if match:
            latest_counter = int(match.group(1))
            latest_patience = int(match.group(2))
    return latest_counter, latest_patience


def has_completion_marker(log_path: Path) -> bool:
    if not log_path.exists():
        return False
    text = log_path.read_text(encoding="utf-8", errors="ignore")
    return any(marker in text for marker in COMPLETION_MARKERS)


def parse_summary(summary_path: Path) -> tuple[str, str]:
    if not summary_path.exists():
        return "", ""
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    return str(payload.get("best_step", "")), str(payload.get("best_metric", ""))


def scan_launcher_queues(run_root: Path) -> dict[str, str]:
    queued_by_dataset: dict[str, str] = {}
    for launcher in run_root.glob("*/run_batch.sh"):
        text = launcher.read_text(encoding="utf-8", errors="ignore")
        marker = 'export DATASETS_CSV="'
        for line in text.splitlines():
            if marker not in line:
                continue
            payload = line.split(marker, 1)[1].split('"', 1)[0]
            for dataset in payload.split(","):
                dataset = dataset.strip()
                if dataset:
                    queued_by_dataset[dataset] = launcher.parent.name
    return queued_by_dataset


def detect_status(summary_path: Path, log_path: Path, queue_launcher: str) -> str:
    if summary_path.exists() and (not log_path.exists() or has_completion_marker(log_path)):
        return "completed"
    if summary_path.exists() and log_path.exists():
        return "running"
    if log_path.exists():
        return "running"
    if queue_launcher:
        return "queued"
    return "not_started"


def detect_official_status(
    base_status: str,
    summary_exists: bool,
    manifest_exists: bool,
) -> str:
    if summary_exists and not manifest_exists:
        return "invalid_stale"
    return base_status


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


def build_rows(
    run_root: Path,
    datasets: list[str],
    beauty_summary_override: Path | None = None,
    official_mode: bool = False,
) -> list[dict[str, str]]:
    queue_map = scan_launcher_queues(run_root)
    rows: list[dict[str, str]] = []
    for dataset in datasets:
        run_dir = run_dir_for(run_root, dataset)
        summary_path = summary_path_for(run_root, dataset)
        summary_source = "run_dir"
        if (
            dataset == "Beauty"
            and not summary_path.exists()
            and beauty_summary_override is not None
            and beauty_summary_override.exists()
        ):
            summary_path = beauty_summary_override
            summary_source = "override"
        manifest_path = manifest_path_for(run_root, dataset)
        log_path = log_path_for(run_root, dataset)
        last_logged_step = parse_last_logged_step(log_path)
        early_stop_wait_counter, early_stop_wait_patience = parse_latest_early_stop_wait(log_path)
        best_step, best_metric = parse_summary(summary_path)
        queue_launcher = queue_map.get(dataset, "")
        summary_exists = summary_path.exists()
        manifest_exists = manifest_path.exists()
        base_status = detect_status(summary_path, log_path, queue_launcher)
        official_status = detect_official_status(
            base_status=base_status,
            summary_exists=summary_exists,
            manifest_exists=manifest_exists,
        )
        row_status = official_status if official_mode else base_status
        rows.append(
            {
                "dataset": dataset,
                "status": row_status,
                "official_status": official_status,
                "run_dir": str(run_dir),
                "summary_path": str(summary_path),
                "summary_exists": "yes" if summary_exists else "no",
                "summary_source": summary_source,
                "manifest_path": str(manifest_path),
                "manifest_exists": "yes" if manifest_exists else "no",
                "best_step": best_step,
                "best_metric": best_metric,
                "log_path": str(log_path),
                "log_exists": "yes" if log_path.exists() else "no",
                "last_logged_step": "" if last_logged_step is None else str(last_logged_step),
                "early_stop_wait_counter": "" if early_stop_wait_counter is None else str(early_stop_wait_counter),
                "early_stop_wait_patience": "" if early_stop_wait_patience is None else str(early_stop_wait_patience),
                "queue_launcher": queue_launcher,
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
        "summary_exists",
        "best_step",
        "best_metric",
        "last_logged_step",
        "early_stop_wait_counter",
        "early_stop_wait_patience",
        "queue_launcher",
    ]
    lines = [
        "# Text-side main-table run status",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row.get(header, "") for header in headers) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize text-side main-table run status.")
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--datasets", nargs="*", default=list(DEFAULT_DATASETS))
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--official-mode", action="store_true")
    parser.add_argument(
        "--beauty-summary-override",
        type=Path,
        default=None,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_csv, output_md = resolve_output_paths(
        output_csv=args.output_csv,
        output_md=args.output_md,
        output_dir=args.output_dir,
    )
    rows = build_rows(
        run_root=args.run_root,
        datasets=list(args.datasets),
        beauty_summary_override=args.beauty_summary_override,
        official_mode=args.official_mode,
    )
    write_csv(output_csv, rows)
    write_markdown(output_md, rows)
    print(f"WROTE {output_csv}")
    print(f"WROTE {output_md}")
    for row in rows:
        print(
            f"{row['dataset']} status={row['status']} "
            f"official={row['official_status']} "
            f"manifest={row['manifest_exists']} "
            f"summary={row['summary_exists']} "
            f"last_step={row['last_logged_step'] or 'na'} "
            f"queue={row['queue_launcher'] or 'na'}"
        )


if __name__ == "__main__":
    main()
