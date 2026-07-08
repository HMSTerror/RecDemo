#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
from datetime import date
import json
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ROOT = Path("/data/Zijian/goal/RecDemoRuns/close02_ml1m_noise_floor")
DEFAULT_OFFICIAL_REPO_ROOT = Path("/data/Zijian/goal/RecDemo_clean_closeout_chain")
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "reports" / "data" / f"{date.today().isoformat()}-close02-ml1m-noise-floor"
DEFAULT_GATE1_REPORT = REPO_ROOT / "docs" / "reports" / "data" / "2026-07-06-gate1" / "sprint05_gate1_report.json"
DEFAULT_SEEDS = (100, 101, 102)
STEP_PATTERN = re.compile(r"step:\s*(\d+),")
COMPLETION_MARKERS = (
    "FINISH seed=",
    "EARLY_STOP_TRIGGERED",
    "BEST_RESULT step=",
)


def run_dir_for(run_root: Path, seed: int) -> Path:
    return run_root / f"ml1m_core_seed{seed}"


def summary_path_for(run_root: Path, seed: int) -> Path:
    return run_dir_for(run_root, seed) / "checkpoints-meta" / "ML1M" / "best_summary_hybrid.json"


def manifest_path_for(run_root: Path, seed: int) -> Path:
    return run_dir_for(run_root, seed) / "checkpoints-meta" / "ML1M" / "frozen_run_manifest.json"


def log_path_for(run_root: Path, seed: int) -> Path:
    return run_dir_for(run_root, seed) / "logs" / f"ml1m_core_seed{seed}.log"


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


def parse_manifest_repo_root(manifest: dict | None) -> str:
    if manifest is None:
        return ""
    provenance = manifest.get("provenance", {})
    if not isinstance(provenance, dict):
        return ""
    return str(provenance.get("repo_root", ""))


def parse_manifest_frozen_config(manifest: dict | None) -> dict:
    if manifest is None:
        return {}
    frozen = manifest.get("frozen_config", {})
    return frozen if isinstance(frozen, dict) else {}


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


def status_for(
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


def visible_summary_field(status: str, value: float | None) -> float | None:
    if status != "completed":
        return None
    return value


def build_rows(
    *,
    run_root: Path,
    official_repo_root: Path,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for seed in seeds:
        summary_path = summary_path_for(run_root, seed)
        manifest_path = manifest_path_for(run_root, seed)
        log_path = log_path_for(run_root, seed)
        summary_payload = load_json(summary_path)
        manifest_payload = load_json(manifest_path)
        frozen_config = parse_manifest_frozen_config(manifest_payload)
        status = status_for(
            summary_exists=summary_path.exists(),
            manifest_exists=manifest_path.exists(),
            manifest_repo_root=parse_manifest_repo_root(manifest_payload),
            official_repo_root=official_repo_root,
            log_path=log_path,
        )
        rows.append(
            {
                "seed": str(seed),
                "run_dir": str(run_dir_for(run_root, seed)),
                "summary_path": str(summary_path),
                "manifest_path": str(manifest_path),
                "log_path": str(log_path),
                "status": status,
                "manifest_exists": "yes" if manifest_path.exists() else "no",
                "repo_root": parse_manifest_repo_root(manifest_payload),
                "manifest_random_seed": "" if manifest_payload is None else str(manifest_payload.get("random_seed", "")),
                "graph_type": str(frozen_config.get("graph_type", "")),
                "text_side_enabled": "" if "text_side_enabled" not in frozen_config else str(frozen_config.get("text_side_enabled")),
                "early_stop_metric": str(frozen_config.get("early_stop_metric", "")),
                "early_stop_strength": str(frozen_config.get("early_stop_strength", "")),
                "write_snapshot_checkpoint": "" if "write_snapshot_checkpoint" not in frozen_config else str(frozen_config.get("write_snapshot_checkpoint")),
                "write_best_checkpoint": "" if "write_best_checkpoint" not in frozen_config else str(frozen_config.get("write_best_checkpoint")),
                "last_logged_step": "" if parse_last_logged_step(log_path) is None else str(parse_last_logged_step(log_path)),
                "best_step": "" if status != "completed" or summary_payload is None else str(summary_payload.get("best_step", "")),
                "best_metric": "" if status != "completed" or summary_payload is None else str(summary_payload.get("best_metric", "")),
                "val_p5_ndcg10": fmt(visible_summary_field(status, metric(summary_payload, "validation", "p5"))),
                "test_p2_ndcg10": fmt(visible_summary_field(status, metric(summary_payload, "test", "p2"))),
                "test_p5_ndcg10": fmt(visible_summary_field(status, metric(summary_payload, "test", "p5"))),
                "test_p10_ndcg10": fmt(visible_summary_field(status, metric(summary_payload, "test", "p10"))),
            }
        )
    return rows


def build_pairwise_deltas(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    completed = [row for row in rows if row["status"] == "completed" and row["test_p2_ndcg10"]]
    result: list[dict[str, str]] = []
    for idx, first in enumerate(completed):
        for second in completed[idx + 1 :]:
            first_p2 = float(first["test_p2_ndcg10"])
            second_p2 = float(second["test_p2_ndcg10"])
            first_p5 = float(first["test_p5_ndcg10"])
            second_p5 = float(second["test_p5_ndcg10"])
            first_p10 = float(first["test_p10_ndcg10"])
            second_p10 = float(second["test_p10_ndcg10"])
            result.append(
                {
                    "seed_a": first["seed"],
                    "seed_b": second["seed"],
                    "abs_delta_test_p2_ndcg10": fmt(abs(first_p2 - second_p2)),
                    "abs_delta_test_p5_ndcg10": fmt(abs(first_p5 - second_p5)),
                    "abs_delta_test_p10_ndcg10": fmt(abs(first_p10 - second_p10)),
                }
            )
    return result


def build_noise_floor_summary(rows: list[dict[str, str]], pairwise: list[dict[str, str]]) -> dict[str, object]:
    completed = [row for row in rows if row["status"] == "completed"]
    max_p2 = max((float(row["abs_delta_test_p2_ndcg10"]) for row in pairwise), default=None)
    max_p5 = max((float(row["abs_delta_test_p5_ndcg10"]) for row in pairwise), default=None)
    max_p10 = max((float(row["abs_delta_test_p10_ndcg10"]) for row in pairwise), default=None)
    return {
        "completed_seed_count": len(completed),
        "expected_seed_count": len(rows),
        "max_pairwise_abs_delta_test_p2_ndcg10": max_p2,
        "max_pairwise_abs_delta_test_p5_ndcg10": max_p5,
        "max_pairwise_abs_delta_test_p10_ndcg10": max_p10,
    }


def read_gate1_ml1m_delta(gate1_report_path: Path) -> dict[str, object]:
    payload = load_json(gate1_report_path)
    if payload is None:
        return {}
    for row in payload.get("datasets", []):
        if str(row.get("dataset")) == "ML1M":
            delta = float(row["delta_test_p2_ndcg10"])
            return {
                "source_path": str(gate1_report_path),
                "delta_test_p2_ndcg10": delta,
                "abs_delta_test_p2_ndcg10": abs(delta),
                "dataset_verdict": str(row.get("dataset_verdict", "")),
            }
    return {}


def build_decision_line(noise_floor_summary: dict[str, object], gate1_context: dict[str, object]) -> dict[str, object]:
    max_pairwise = noise_floor_summary.get("max_pairwise_abs_delta_test_p2_ndcg10")
    gate1_abs = gate1_context.get("abs_delta_test_p2_ndcg10")
    if max_pairwise is None or gate1_abs is None:
        return {
            "decision_line": "",
            "reason": "insufficient_data",
        }
    if float(max_pairwise) >= float(gate1_abs):
        return {
            "decision_line": "within_noise_candidate",
            "reason": "measured_host_noise_floor_covers_gate1_ml1m_delta",
        }
    return {
        "decision_line": "outside_noise_red_flag",
        "reason": "gate1_ml1m_delta_exceeds_measured_host_noise_floor",
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError("rows must not be empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_markdown(
    rows: list[dict[str, str]],
    pairwise: list[dict[str, str]],
    noise_floor_summary: dict[str, object],
    gate1_context: dict[str, object],
    decision_line: dict[str, object],
) -> str:
    completed = noise_floor_summary["completed_seed_count"]
    expected = noise_floor_summary["expected_seed_count"]
    max_p2 = noise_floor_summary["max_pairwise_abs_delta_test_p2_ndcg10"]
    lines = [
        "# CLOSE-02 ML1M 宿主噪声地板",
        "",
        "## 当前状态",
        "",
        f"- 已完成种子数: {completed}/{expected}",
        f"- 远端执行根要求: `{DEFAULT_OFFICIAL_REPO_ROOT}`",
        f"- 最大成对 |delta test p2 NDCG@10|: {fmt(max_p2) if max_p2 is not None else '待更多 completed seeds'}",
    ]
    if gate1_context:
        lines.append(f"- Gate-1 ML1M 官方 delta_test_p2_ndcg10: {fmt(float(gate1_context['delta_test_p2_ndcg10']))}")
    if decision_line["decision_line"]:
        lines.append(f"- 决策线: `{decision_line['decision_line']}` ({decision_line['reason']})")

    lines.extend(
        [
            "",
            "## Per-seed",
            "",
            "| seed | status | best_step | val_p5_ndcg10 | test_p2_ndcg10 | test_p5_ndcg10 | test_p10_ndcg10 |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in rows:
        lines.append(
            "| {seed} | {status} | {best_step} | {val_p5_ndcg10} | {test_p2_ndcg10} | {test_p5_ndcg10} | {test_p10_ndcg10} |".format(
                **row
            )
        )

    lines.extend(
        [
            "",
            "## Pairwise",
            "",
        ]
    )
    if not pairwise:
        lines.append("- 需要至少两个 completed seeds 才能计算噪声地板。")
    else:
        lines.extend(
            [
                "| seed_a | seed_b | abs_delta_test_p2_ndcg10 | abs_delta_test_p5_ndcg10 | abs_delta_test_p10_ndcg10 |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for row in pairwise:
            lines.append(
                "| {seed_a} | {seed_b} | {abs_delta_test_p2_ndcg10} | {abs_delta_test_p5_ndcg10} | {abs_delta_test_p10_ndcg10} |".format(
                    **row
                )
            )
    return "\n".join(lines) + "\n"


def write_markdown(
    path: Path,
    rows: list[dict[str, str]],
    pairwise: list[dict[str, str]],
    noise_floor_summary: dict[str, object],
    gate1_context: dict[str, object],
    decision_line: dict[str, object],
) -> None:
    path.write_text(
        build_markdown(rows, pairwise, noise_floor_summary, gate1_context, decision_line),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the CLOSE-02 ML1M host-noise-floor dated report.")
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--official-repo-root", type=Path, default=DEFAULT_OFFICIAL_REPO_ROOT)
    parser.add_argument("--gate1-report-path", type=Path, default=DEFAULT_GATE1_REPORT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seeds", nargs="+", type=int, default=list(DEFAULT_SEEDS))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = build_rows(
        run_root=args.run_root,
        official_repo_root=args.official_repo_root,
        seeds=tuple(args.seeds),
    )
    pairwise = build_pairwise_deltas(rows)
    noise_floor_summary = build_noise_floor_summary(rows, pairwise)
    gate1_context = read_gate1_ml1m_delta(args.gate1_report_path)
    decision_line = build_decision_line(noise_floor_summary, gate1_context)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_csv = args.output_dir / "close02_ml1m_noise_floor_table.csv"
    output_json = args.output_dir / "close02_ml1m_noise_floor_report.json"
    output_md = args.output_dir / "close02_ml1m_noise_floor_report_zh.md"

    write_csv(output_csv, rows)
    output_json.write_text(
        json.dumps(
            {
                "run_root": str(args.run_root),
                "official_repo_root": str(args.official_repo_root),
                "rows": rows,
                "pairwise_abs_deltas": pairwise,
                "noise_floor_summary": noise_floor_summary,
                "gate1_context": gate1_context,
                "decision_line": decision_line,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    write_markdown(output_md, rows, pairwise, noise_floor_summary, gate1_context, decision_line)
    print(f"WROTE {output_csv}")
    print(f"WROTE {output_json}")
    print(f"WROTE {output_md}")


if __name__ == "__main__":
    main()
