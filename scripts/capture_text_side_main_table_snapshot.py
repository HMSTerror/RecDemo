#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SUMMARIZE_PATH = REPO_ROOT / "scripts" / "summarize_text_side_main_table_runs.py"
COMPARE_PATH = REPO_ROOT / "scripts" / "compare_text_side_main_table_to_core.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


summarize = load_module("capture_snapshot_summarize", SUMMARIZE_PATH)
compare = load_module("capture_snapshot_compare", COMPARE_PATH)


def capture_snapshot(
    *,
    run_root: Path,
    output_dir: Path,
    datasets: list[str],
    official_mode: bool,
    official_repo_root: Path | None,
    beauty_summary_override: Path | None,
    core_root: Path,
) -> tuple[Path, Path]:
    status_csv, status_md = summarize.resolve_output_paths(
        output_csv=summarize.DEFAULT_OUTPUT_CSV,
        output_md=summarize.DEFAULT_OUTPUT_MD,
        output_dir=output_dir,
    )
    status_rows = summarize.build_rows(
        run_root=run_root,
        datasets=datasets,
        beauty_summary_override=beauty_summary_override,
        official_mode=official_mode,
        official_repo_root=official_repo_root,
    )
    summarize.write_csv(status_csv, status_rows)
    summarize.write_markdown(status_md, status_rows)

    compare_csv, compare_md = compare.resolve_output_paths(
        output_csv=compare.DEFAULT_OUTPUT_CSV,
        output_md=compare.DEFAULT_OUTPUT_MD,
        output_dir=output_dir,
    )
    compare_rows = compare.build_rows(status_rows, core_root)
    compare.write_csv(compare_csv, compare_rows)
    compare.write_markdown(compare_md, compare_rows)
    return status_csv, compare_csv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture a sequential text-side main-table status + compare snapshot."
    )
    parser.add_argument("--run-root", type=Path, default=summarize.DEFAULT_RUN_ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--datasets", nargs="*", default=list(summarize.DEFAULT_DATASETS))
    parser.add_argument("--official-mode", action="store_true")
    parser.add_argument("--official-repo-root", type=Path, default=None)
    parser.add_argument("--beauty-summary-override", type=Path, default=None)
    parser.add_argument("--core-root", type=Path, default=compare.DEFAULT_CORE_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    status_csv, compare_csv = capture_snapshot(
        run_root=args.run_root,
        output_dir=args.output_dir,
        datasets=list(args.datasets),
        official_mode=args.official_mode,
        official_repo_root=args.official_repo_root,
        beauty_summary_override=args.beauty_summary_override,
        core_root=args.core_root,
    )
    print(f"WROTE {status_csv}")
    print(f"WROTE {compare_csv}")


if __name__ == "__main__":
    main()
