#!/usr/bin/env python3
"""Build the dated provenance-limited CLOSE-10 ATG observed-spread package."""

from __future__ import annotations

import argparse
import base64
import csv
from datetime import datetime
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SEEDS = (100, 101, 102)
REMOTE_SNAPSHOT_SCHEMA_VERSION = "close10-atg-remote-snapshot-v1"
REPORT_SCHEMA_VERSION = "close10-atg-provenance-limited-v1"
DEFAULT_REPORTED_RUN_ROOT = "/data/Zijian/goal/RecDemoRuns/close10_atg_noise_floor"
DEFAULT_REPORTED_SESSION_LOG = (
    "/data/Zijian/goal/RecDemo_clean_closeout_chain/logs/close10_session.log"
)
DEFAULT_GATE1_REPORT = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "data"
    / "2026-07-06-gate1"
    / "sprint05_gate1_report.json"
)
DEFAULT_E0_REPORT = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "data"
    / "2026-07-10-evaluator-amendment"
    / "e0_evaluator_amendment.json"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "data"
    / "2026-07-10-close10-atg-noise-floor-provenance-limited"
)
OUTPUT_FILENAMES = (
    "close10_atg_provenance_limited_observations.csv",
    "close10_atg_provenance_limited_report.json",
    "close10_atg_provenance_limited_report.md",
    "close10_atg_provenance_limited_report_zh.md",
    "provenance_manifest.json",
    "capability_use_audit.md",
)
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
BEST_RESULT_RE = re.compile(
    r"BEST_RESULT step=(?P<step>\d+) metric=(?P<metric>[^ ]+) "
    r"value=(?P<value>[-+0-9.eE]+) summary=(?P<summary>\S+)"
)
PROHIBITED_CLAIM_PHRASES = (
    "significant",
    "stable",
    "statistically equivalent",
    "within noise",
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def format_number(value: float) -> str:
    return repr(float(value))


def expected_paths(run_root: str, seed: int) -> dict[str, str]:
    root = run_root.rstrip("/")
    run_dir = f"{root}/atg_core_seed{seed}"
    return {
        "run_dir": run_dir,
        "summary": f"{run_dir}/checkpoints-meta/ATG/best_summary_hybrid.json",
        "log": f"{run_dir}/logs/atg_core_seed{seed}.log",
        "manifest": f"{run_dir}/checkpoints-meta/ATG/frozen_run_manifest.json",
    }


def local_paths(local_run_root: Path, seed: int) -> dict[str, Path]:
    run_dir = Path(local_run_root) / f"atg_core_seed{seed}"
    return {
        "summary": run_dir / "checkpoints-meta" / "ATG" / "best_summary_hybrid.json",
        "log": run_dir / "logs" / f"atg_core_seed{seed}.log",
        "manifest": run_dir / "checkpoints-meta" / "ATG" / "frozen_run_manifest.json",
    }


def encoded_artifact(local_path: Path, reported_path: str) -> dict[str, Any]:
    local_path = Path(local_path)
    if not local_path.is_file():
        raise FileNotFoundError(local_path)
    raw = local_path.read_bytes()
    return {
        "path": reported_path,
        "sha256": sha256_bytes(raw),
        "size_bytes": len(raw),
        "content_b64": base64.b64encode(raw).decode("ascii"),
    }


def collect_local_snapshot(
    *,
    local_run_root: Path,
    reported_run_root: str,
    local_session_log: Path,
    reported_session_log: str,
    source_host: str,
    collected_at: str | None = None,
) -> dict[str, Any]:
    """Collect read-only local copies while preserving their remote source paths."""

    entries: list[dict[str, Any]] = []
    for seed in REQUIRED_SEEDS:
        local = local_paths(local_run_root, seed)
        reported = expected_paths(reported_run_root, seed)
        entries.append(
            {
                "seed": seed,
                "summary": encoded_artifact(local["summary"], reported["summary"]),
                "log": encoded_artifact(local["log"], reported["log"]),
                "manifest_path": reported["manifest"],
                "manifest_exists": local["manifest"].is_file(),
            }
        )
    return {
        "schema_version": REMOTE_SNAPSHOT_SCHEMA_VERSION,
        "collected_at": collected_at
        or datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_host": source_host,
        "run_root": reported_run_root.rstrip("/"),
        "policy": {
            "remote_read_only": True,
            "manifest_reconstructed": False,
        },
        "entries": entries,
        "session_log": encoded_artifact(local_session_log, reported_session_log),
    }


def decode_artifact(record: dict[str, Any], label: str) -> bytes:
    if not isinstance(record, dict):
        raise ValueError(f"artifact record required for {label}")
    source_path = record.get("path")
    if not isinstance(source_path, str) or not source_path:
        raise ValueError(f"source path required for {label}")
    digest = str(record.get("sha256", ""))
    if not HASH_RE.fullmatch(digest):
        raise ValueError(f"invalid SHA-256 for {label}")
    try:
        expected_size = int(record["size_bytes"])
        raw = base64.b64decode(record["content_b64"], validate=True)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"encoded content required for {label}") from exc
    if expected_size < 0 or len(raw) != expected_size:
        raise ValueError(f"size mismatch for {label}")
    if sha256_bytes(raw) != digest:
        raise ValueError(f"hash mismatch for {label}")
    return raw


def finite_metric(value: Any, label: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"numeric metric required for {label}") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"finite metric required for {label}")
    if not 0.0 <= parsed <= 1.0:
        raise ValueError(f"metric outside [0, 1] for {label}")
    return parsed


def read_ndcg10(summary: dict[str, Any], split: str, strength: str) -> float:
    try:
        value = summary[split][strength]["ndcg"][2]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"NDCG@10 missing for {split}/{strength}") from exc
    return finite_metric(value, f"{split}/{strength}/ndcg10")


def compact_artifact(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(record["path"]),
        "sha256": str(record["sha256"]),
        "size_bytes": int(record["size_bytes"]),
        "content_hash_verified": True,
    }


def normalize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot JSON object required")
    if snapshot.get("schema_version") != REMOTE_SNAPSHOT_SCHEMA_VERSION:
        raise ValueError("unsupported CLOSE-10 snapshot schema")
    policy = snapshot.get("policy")
    if not isinstance(policy, dict) or policy.get("remote_read_only") is not True:
        raise ValueError("remote read-only collection policy required")
    if policy.get("manifest_reconstructed") is not False:
        raise ValueError("retrospective manifest reconstruction is forbidden")

    run_root = str(snapshot.get("run_root", "")).rstrip("/")
    if not run_root:
        raise ValueError("run_root required")
    entries = snapshot.get("entries")
    if not isinstance(entries, list):
        raise ValueError("snapshot entries required")
    try:
        seeds = [int(entry["seed"]) for entry in entries]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("integer seed required for every entry") from exc
    if len(seeds) != len(REQUIRED_SEEDS) or sorted(seeds) != list(REQUIRED_SEEDS):
        raise ValueError(
            f"seed set mismatch: required={list(REQUIRED_SEEDS)} actual={sorted(seeds)}"
        )

    session_record = snapshot.get("session_log")
    session_raw = decode_artifact(session_record, "session log")
    session_text = session_raw.decode("utf-8", errors="replace")
    all_done_lines = [
        line.strip()
        for line in session_text.splitlines()
        if "ALL_SEEDS_DONE" in line
    ]
    if not all_done_lines:
        raise ValueError("session completion evidence ALL_SEEDS_DONE missing")

    observations: list[dict[str, Any]] = []
    for entry in sorted(entries, key=lambda item: int(item["seed"])):
        seed = int(entry["seed"])
        expected = expected_paths(run_root, seed)
        summary_record = entry.get("summary")
        log_record = entry.get("log")
        if not isinstance(summary_record, dict) or summary_record.get("path") != expected["summary"]:
            raise ValueError(f"summary path mismatch for seed {seed}")
        if not isinstance(log_record, dict) or log_record.get("path") != expected["log"]:
            raise ValueError(f"log path mismatch for seed {seed}")
        if entry.get("manifest_path") != expected["manifest"]:
            raise ValueError(f"manifest path mismatch for seed {seed}")
        if entry.get("manifest_exists") is not False:
            raise ValueError(
                f"manifest absence required for provenance-limited builder: seed {seed}"
            )

        summary_raw = decode_artifact(summary_record, f"seed {seed} summary")
        log_raw = decode_artifact(log_record, f"seed {seed} log")
        try:
            summary = json.loads(summary_raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"valid summary JSON required for seed {seed}") from exc
        if not isinstance(summary, dict):
            raise ValueError(f"summary JSON object required for seed {seed}")

        metric_name = str(summary.get("metric_name", ""))
        if metric_name != "ndcg10":
            raise ValueError(f"ndcg10 summary required for seed {seed}")
        try:
            best_step = int(summary["best_step"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"best_step required for seed {seed}") from exc
        best_metric = finite_metric(summary.get("best_metric"), f"seed {seed} best_metric")
        validation_p5 = read_ndcg10(summary, "validation", "p5")
        if abs(best_metric - validation_p5) > 1e-12:
            raise ValueError(f"best_metric does not bind validation p5 for seed {seed}")
        test_p2 = read_ndcg10(summary, "test", "p2")
        test_p5 = read_ndcg10(summary, "test", "p5")
        test_p10 = read_ndcg10(summary, "test", "p10")

        log_text = log_raw.decode("utf-8", errors="replace")
        terminal_lines = [
            line.strip()
            for line in log_text.splitlines()
            if "EARLY_STOP_TRIGGERED" in line or f"FINISH seed={seed}" in line
        ]
        best_matches = [
            (line.strip(), match)
            for line in log_text.splitlines()
            if (match := BEST_RESULT_RE.search(line)) is not None
        ]
        if not terminal_lines or not best_matches:
            raise ValueError(f"completion evidence missing for seed {seed}")
        best_result_line, best_match = best_matches[-1]
        if best_match.group("summary") != expected["summary"]:
            raise ValueError(f"BEST_RESULT does not bind summary for seed {seed}")
        if int(best_match.group("step")) != best_step:
            raise ValueError(f"BEST_RESULT step mismatch for seed {seed}")
        if best_match.group("metric") != metric_name:
            raise ValueError(f"BEST_RESULT metric mismatch for seed {seed}")
        if abs(float(best_match.group("value")) - best_metric) > 5e-7:
            raise ValueError(f"BEST_RESULT value mismatch for seed {seed}")

        observations.append(
            {
                "seed": seed,
                "run_dir": expected["run_dir"],
                "best_step": best_step,
                "best_metric": best_metric,
                "validation_p5_ndcg10": validation_p5,
                "test_p2_ndcg10": test_p2,
                "test_p5_ndcg10": test_p5,
                "test_p10_ndcg10": test_p10,
                "summary": compact_artifact(summary_record),
                "log": compact_artifact(log_record),
                "completion_marker_line": terminal_lines[-1],
                "best_result_line": best_result_line,
                "manifest_path": expected["manifest"],
                "manifest_exists": False,
                "manifest_reconstructed": False,
            }
        )

    return {
        "schema_version": REMOTE_SNAPSHOT_SCHEMA_VERSION,
        "collected_at": str(snapshot.get("collected_at", "")),
        "source_host": str(snapshot.get("source_host", "")),
        "run_root": run_root,
        "policy": {
            "remote_read_only": True,
            "manifest_reconstructed": False,
        },
        "observations": observations,
        "session_log": {
            **compact_artifact(session_record),
            "completion_marker_line": all_done_lines[-1],
        },
    }


def parse_gate1_atg(gate1: dict[str, Any]) -> dict[str, Any]:
    rows = gate1.get("datasets") if isinstance(gate1, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Gate-1 dataset rows required")
    matches = [row for row in rows if isinstance(row, dict) and row.get("dataset") == "ATG"]
    if len(matches) != 1:
        raise ValueError("exactly one Gate-1 ATG row required")
    signed_delta = float(matches[0].get("delta_test_p2_ndcg10"))
    if not math.isfinite(signed_delta):
        raise ValueError("finite Gate-1 ATG delta required")
    return {
        "signed_delta": signed_delta,
        "abs_gap": abs(signed_delta),
        "recorded_outcome": str(matches[0].get("dataset_verdict", "")),
    }


def parse_e0_corrected_atg(e0: dict[str, Any]) -> dict[str, Any]:
    try:
        row = e0["gate_reread"]["sprint05_preregistered_prediction_reread"]["ATG"]
        signed_delta = float(row["corrected_delta_test_p2_ndcg10"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("E0 corrected ATG delta required") from exc
    if not math.isfinite(signed_delta):
        raise ValueError("finite E0 corrected ATG delta required")
    return {
        "signed_delta": signed_delta,
        "abs_gap": abs(signed_delta),
        "recorded_outcome": str(row.get("corrected_outcome", "")),
        "gate_state": str(row.get("gate_state", "")),
    }


def gap_comparison(gap: dict[str, Any], spread: float) -> dict[str, Any]:
    abs_gap = float(gap["abs_gap"])
    if spread <= 0.0:
        ratio = math.inf
    else:
        ratio = abs_gap / spread
    return {
        **gap,
        "gap_to_observed_spread_ratio": ratio,
        "decision": (
            "outside_observed_spread"
            if abs_gap > spread
            else "not_outside_observed_spread"
        ),
    }


def build_report_payload(
    snapshot: dict[str, Any],
    gate1: dict[str, Any],
    e0: dict[str, Any],
) -> dict[str, Any]:
    normalized = normalize_snapshot(snapshot)
    observations = normalized["observations"]
    pairwise: list[dict[str, Any]] = []
    for first, second in itertools.combinations(observations, 2):
        pairwise.append(
            {
                "seed_a": first["seed"],
                "seed_b": second["seed"],
                "abs_test_p2_ndcg10_spread": abs(
                    float(first["test_p2_ndcg10"])
                    - float(second["test_p2_ndcg10"])
                ),
            }
        )
    max_spread = max(row["abs_test_p2_ndcg10_spread"] for row in pairwise)
    original = gap_comparison(parse_gate1_atg(gate1), max_spread)
    corrected = gap_comparison(parse_e0_corrected_atg(e0), max_spread)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_snapshot": {
            "schema_version": normalized["schema_version"],
            "collected_at": normalized["collected_at"],
            "source_host": normalized["source_host"],
            "run_root": normalized["run_root"],
            "remote_read_only": True,
            "session_log": normalized["session_log"],
        },
        "scope": {
            "label": "provenance-limited observed spread",
            "metric": "test-p2 NDCG@10",
            "completed_run_count": len(observations),
            "complete_configuration_parity_claimed": False,
            "population_variance_estimate": False,
            "training_seed_variance_estimate": False,
            "manifest_reconstructed": False,
        },
        "observations": observations,
        "observed_spread": {
            "pairwise": pairwise,
            "max_pairwise_test_p2_ndcg10": max_spread,
        },
        "gap_comparisons": {
            "original_gate1": original,
            "e0_corrected": corrected,
        },
        "limitations": [
            "All three run directories lack frozen_run_manifest.json.",
            "No manifest was reconstructed retrospectively.",
            "Complete configuration parity is not claimed.",
            "The three completed runs provide an observed spread, not a population-variance estimate.",
        ],
    }


def source_file_record(path: Path) -> dict[str, Any]:
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def render_chinese(report: dict[str, Any]) -> str:
    observations = report["observations"]
    spread = float(report["observed_spread"]["max_pairwise_test_p2_ndcg10"])
    original = report["gap_comparisons"]["original_gate1"]
    corrected = report["gap_comparisons"]["e0_corrected"]
    session_line = report["source_snapshot"]["session_log"]["completion_marker_line"]
    lines = [
        "# CLOSE-10 ATG provenance-limited observed spread 报告",
        "",
        f"_只读证据归档；采集主机 `{report['source_snapshot']['source_host']}`，日期 2026-07-10。_",
        "",
        "---",
        "",
        "## 📋 结论",
        "",
        "三次已完成的 ATG host 运行仅给出 provenance-limited observed spread，"
        "不是总体方差估计。三个运行目录均缺少 `frozen_run_manifest.json`，因此不声称"
        "完整配置一致性，也未事后重建任何 manifest。",
        "",
        f"最大成对 `test-p2 NDCG@10` observed spread 为 `{format_number(spread)}`。"
        f"原始 Gate-1 绝对 gap `{format_number(original['abs_gap'])}`（比值 "
        f"`{format_number(original['gap_to_observed_spread_ratio'])}`）与 E0 修正后绝对 gap "
        f"`{format_number(corrected['abs_gap'])}`（比值 "
        f"`{format_number(corrected['gap_to_observed_spread_ratio'])}`）均判为 "
        "`outside_observed_spread`。",
        "",
        "## 📊 单次运行观测",
        "",
        "| seed | best step | validation-p5 NDCG@10 | test-p2 NDCG@10 |",
        "| ---: | ---: | ---: | ---: |",
    ]
    for row in observations:
        lines.append(
            f"| {row['seed']} | {row['best_step']} | "
            f"{format_number(row['validation_p5_ndcg10'])} | "
            f"{format_number(row['test_p2_ndcg10'])} |"
        )
    lines.extend(
        [
            "",
            "## 🔎 独立 gap 对照",
            "",
            "| 读数版本 | 绝对 gap | gap / observed spread | 判定 |",
            "| --- | ---: | ---: | --- |",
            f"| 原始 Gate-1 | {format_number(original['abs_gap'])} | "
            f"{format_number(original['gap_to_observed_spread_ratio'])} | "
            f"`{original['decision']}` |",
            f"| E0 corrected | {format_number(corrected['abs_gap'])} | "
            f"{format_number(corrected['gap_to_observed_spread_ratio'])} | "
            f"`{corrected['decision']}` |",
            "",
            "两套 gap 分别从原始 Gate-1 报告与 E0 evaluator 修正案读取，未相互替代，也未改写冻结的 Table 2 数字。",
            "",
            "## 🔗 Provenance 边界",
            "",
            "| seed | summary SHA-256 | log SHA-256 | manifest |",
            "| ---: | --- | --- | --- |",
        ]
    )
    for row in observations:
        lines.append(
            f"| {row['seed']} | `{row['summary']['sha256']}` | "
            f"`{row['log']['sha256']}` | 缺失；未重建 |"
        )
    lines.extend(
        [
            "",
            "## 🧾 完成标记原文",
            "",
            "```text",
            *[row["completion_marker_line"] for row in observations],
            session_line,
            "```",
            "",
            "每条 `BEST_RESULT` 还必须在构建时绑定同 seed 的 summary 路径、best step 与 metric；"
            "任一摘要、日志、哈希、seed 或完成标记缺失都会使构建失败。",
            "",
        ]
    )
    return "\n".join(lines)


def render_english(report: dict[str, Any]) -> str:
    observations = report["observations"]
    spread = float(report["observed_spread"]["max_pairwise_test_p2_ndcg10"])
    original = report["gap_comparisons"]["original_gate1"]
    corrected = report["gap_comparisons"]["e0_corrected"]
    session_line = report["source_snapshot"]["session_log"]["completion_marker_line"]
    lines = [
        "# CLOSE-10 ATG provenance-limited observed spread report",
        "",
        f"_Read-only evidence archive collected from `{report['source_snapshot']['source_host']}` on 2026-07-10._",
        "",
        "---",
        "",
        "## 📋 Conclusion",
        "",
        "The three completed ATG host runs provide a provenance-limited observed spread, not an estimate "
        "of population variance. Their run directories lack `frozen_run_manifest.json`, so complete "
        "configuration parity is not claimed and no manifest was reconstructed retrospectively.",
        "",
        f"The maximum pairwise `test-p2 NDCG@10` observed spread is `{format_number(spread)}`. "
        f"The original Gate-1 absolute gap is `{format_number(original['abs_gap'])}` "
        f"(ratio `{format_number(original['gap_to_observed_spread_ratio'])}`), and the E0-corrected "
        f"absolute gap is `{format_number(corrected['abs_gap'])}` "
        f"(ratio `{format_number(corrected['gap_to_observed_spread_ratio'])}`). Both comparisons are "
        "recorded as `outside_observed_spread`.",
        "",
        "## 📊 Single-run observations",
        "",
        "| seed | best step | validation-p5 NDCG@10 | test-p2 NDCG@10 |",
        "| ---: | ---: | ---: | ---: |",
    ]
    for row in observations:
        lines.append(
            f"| {row['seed']} | {row['best_step']} | "
            f"{format_number(row['validation_p5_ndcg10'])} | "
            f"{format_number(row['test_p2_ndcg10'])} |"
        )
    lines.extend(
        [
            "",
            "## 🔎 Independent gap comparisons",
            "",
            "| Readout | Absolute gap | Gap / observed spread | Decision |",
            "| --- | ---: | ---: | --- |",
            f"| Original Gate-1 | {format_number(original['abs_gap'])} | "
            f"{format_number(original['gap_to_observed_spread_ratio'])} | "
            f"`{original['decision']}` |",
            f"| E0 corrected | {format_number(corrected['abs_gap'])} | "
            f"{format_number(corrected['gap_to_observed_spread_ratio'])} | "
            f"`{corrected['decision']}` |",
            "",
            "The two gaps are read independently from the original Gate-1 report and the E0 evaluator "
            "amendment. This package does not replace the frozen Table 2 metrics.",
            "",
            "## 🔗 Provenance boundary",
            "",
            "| seed | Summary SHA-256 | Log SHA-256 | Manifest |",
            "| ---: | --- | --- | --- |",
        ]
    )
    for row in observations:
        lines.append(
            f"| {row['seed']} | `{row['summary']['sha256']}` | "
            f"`{row['log']['sha256']}` | absent; not reconstructed |"
        )
    lines.extend(
        [
            "",
            "## 🧾 Completion-marker excerpts",
            "",
            "```text",
            *[row["completion_marker_line"] for row in observations],
            session_line,
            "```",
            "",
            "During construction, each `BEST_RESULT` line must also bind the same-seed summary path, "
            "best step, and metric. A missing summary, log, hash, seed, or completion marker causes the "
            "builder to fail closed.",
            "",
        ]
    )
    return "\n".join(lines)


def render_capability_audit(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# CLOSE-10 capability-use audit",
            "",
            "_Audit record for the 2026-07-10 provenance-limited ATG observed-spread package._",
            "",
            "---",
            "",
            "## 📋 Applied controls",
            "",
            "| Control | Application | Evidence |",
            "| --- | --- | --- |",
            "| Fast context | Located prior CLOSE-02/CLOSE-10 builders and tests | Repository search result |",
            "| Test-driven development | Added the contract tests before the builder | RED and GREEN test runs |",
            "| Markdown reporting | Used one H1, scoped H2 sections, compact tables, and text log excerpts | Two report files |",
            "| Verification before completion | Requires fresh tests, hash checks, wording scans, and path-level status | Verification transcript |",
            "",
            "## 🔎 Scope decisions",
            "",
            "No Mermaid diagram was added because the evidence relation is a direct three-observation comparison; "
            "the compact tables expose the complete relation without an additional visual layer.",
            "",
            "The report uses only completed CLOSE-10 summaries and logs, the original Gate-1 ATG gap, and the "
            "E0-corrected ATG gap. It does not modify the manuscript, the formal ledger, or remote run directories.",
            "",
            "## ⚠️ Remaining limitation",
            "",
            "All three run directories lack `frozen_run_manifest.json`. The package therefore reports only the "
            f"observed dispersion across {report['scope']['completed_run_count']} completed runs and preserves the "
            "configuration-parity limitation.",
            "",
        ]
    )


def write_csv(path: Path, observations: list[dict[str, Any]]) -> None:
    fieldnames = [
        "seed",
        "best_step",
        "best_metric",
        "validation_p5_ndcg10",
        "test_p2_ndcg10",
        "test_p5_ndcg10",
        "test_p10_ndcg10",
        "summary_path",
        "summary_sha256",
        "summary_size_bytes",
        "log_path",
        "log_sha256",
        "log_size_bytes",
        "completion_marker_line",
        "best_result_line",
        "manifest_path",
        "manifest_exists",
        "manifest_reconstructed",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in observations:
            writer.writerow(
                {
                    "seed": row["seed"],
                    "best_step": row["best_step"],
                    "best_metric": format_number(row["best_metric"]),
                    "validation_p5_ndcg10": format_number(row["validation_p5_ndcg10"]),
                    "test_p2_ndcg10": format_number(row["test_p2_ndcg10"]),
                    "test_p5_ndcg10": format_number(row["test_p5_ndcg10"]),
                    "test_p10_ndcg10": format_number(row["test_p10_ndcg10"]),
                    "summary_path": row["summary"]["path"],
                    "summary_sha256": row["summary"]["sha256"],
                    "summary_size_bytes": row["summary"]["size_bytes"],
                    "log_path": row["log"]["path"],
                    "log_sha256": row["log"]["sha256"],
                    "log_size_bytes": row["log"]["size_bytes"],
                    "completion_marker_line": row["completion_marker_line"],
                    "best_result_line": row["best_result_line"],
                    "manifest_path": row["manifest_path"],
                    "manifest_exists": str(row["manifest_exists"]).lower(),
                    "manifest_reconstructed": str(row["manifest_reconstructed"]).lower(),
                }
            )


def validate_claim_language(paths: list[Path]) -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths).lower()
    hits = [phrase for phrase in PROHIBITED_CLAIM_PHRASES if phrase in combined]
    if hits:
        raise ValueError(f"prohibited claim language detected: {hits}")


def write_raw_provenance(staging_dir: Path, snapshot: dict[str, Any]) -> None:
    entries = snapshot.get("entries")
    if not isinstance(entries, list):
        raise ValueError("snapshot entries required for provenance archive")
    by_seed = {int(entry["seed"]): entry for entry in entries}
    if set(by_seed) != set(REQUIRED_SEEDS):
        raise ValueError("seed set mismatch for provenance archive")

    for seed in REQUIRED_SEEDS:
        entry = by_seed[seed]
        seed_dir = staging_dir / "provenance" / f"seed{seed}"
        seed_dir.mkdir(parents=True, exist_ok=False)
        (seed_dir / "best_summary_hybrid.json").write_bytes(
            decode_artifact(entry["summary"], f"seed {seed} summary")
        )
        (seed_dir / f"atg_core_seed{seed}.log").write_bytes(
            decode_artifact(entry["log"], f"seed {seed} log")
        )

    session_dir = staging_dir / "provenance" / "session"
    session_dir.mkdir(parents=True, exist_ok=False)
    (session_dir / "close10_session.log").write_bytes(
        decode_artifact(snapshot["session_log"], "session log")
    )


def write_package_files(
    staging_dir: Path,
    report: dict[str, Any],
    provenance_manifest: dict[str, Any],
    snapshot: dict[str, Any],
) -> None:
    csv_path = staging_dir / "close10_atg_provenance_limited_observations.csv"
    json_path = staging_dir / "close10_atg_provenance_limited_report.json"
    english_path = staging_dir / "close10_atg_provenance_limited_report.md"
    chinese_path = staging_dir / "close10_atg_provenance_limited_report_zh.md"
    manifest_path = staging_dir / "provenance_manifest.json"
    audit_path = staging_dir / "capability_use_audit.md"

    write_csv(csv_path, report["observations"])
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    english_path.write_text(render_english(report), encoding="utf-8")
    chinese_path.write_text(render_chinese(report), encoding="utf-8")
    manifest_path.write_text(
        json.dumps(provenance_manifest, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    audit_path.write_text(render_capability_audit(report), encoding="utf-8")
    write_raw_provenance(staging_dir, snapshot)

    validate_claim_language(
        [csv_path, json_path, english_path, chinese_path, manifest_path, audit_path]
    )
    sum_lines = []
    for path in sorted(staging_dir.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            sum_lines.append(
                f"{sha256_file(path)}  {path.relative_to(staging_dir).as_posix()}"
            )
    (staging_dir / "SHA256SUMS").write_text(
        "\n".join(sum_lines) + "\n", encoding="utf-8"
    )


def publish_no_clobber(staging_dir: Path, output_dir: Path) -> None:
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite dated report: {output_dir}")
    os.rename(staging_dir, output_dir)


def load_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"valid JSON required: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def write_report(
    *,
    gate1_report_path: Path,
    e0_report_path: Path,
    output_dir: Path,
    snapshot_path: Path | None = None,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if (snapshot_path is None) == (snapshot is None):
        raise ValueError("provide exactly one of snapshot_path or snapshot")
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite dated report: {output_dir}")

    snapshot_record: dict[str, Any]
    if snapshot_path is not None:
        snapshot_payload = load_json_file(snapshot_path)
        snapshot_record = source_file_record(snapshot_path)
    else:
        snapshot_payload = snapshot
        snapshot_record = {
            "path": "in-memory snapshot collected from read-only local copies",
            "sha256": sha256_bytes(
                json.dumps(snapshot_payload, sort_keys=True).encode("utf-8")
            ),
            "size_bytes": len(json.dumps(snapshot_payload, sort_keys=True).encode("utf-8")),
        }
    gate1_payload = load_json_file(gate1_report_path)
    e0_payload = load_json_file(e0_report_path)
    report = build_report_payload(snapshot_payload, gate1_payload, e0_payload)
    source_records = {
        "collector_snapshot": snapshot_record,
        "original_gate1_report": source_file_record(gate1_report_path),
        "e0_evaluator_amendment": source_file_record(e0_report_path),
    }
    report["source_artifacts"] = source_records
    provenance_manifest = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "remote_read_only": True,
        "manifest_reconstructed": False,
        "source_artifacts": source_records,
        "remote_session_log": report["source_snapshot"]["session_log"],
        "remote_run_artifacts": [
            {
                "seed": row["seed"],
                "summary": row["summary"],
                "log": row["log"],
                "manifest_path": row["manifest_path"],
                "manifest_exists": False,
                "manifest_reconstructed": False,
            }
            for row in report["observations"]
        ],
    }

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(
            prefix=".close10-provenance-limited-staging-",
            dir=str(output_dir.parent),
        )
    )
    try:
        write_package_files(staging_dir, report, provenance_manifest, snapshot_payload)
        publish_no_clobber(staging_dir, output_dir)
    except Exception:
        resolved_parent = output_dir.parent.resolve()
        if staging_dir.exists() and staging_dir.resolve().parent == resolved_parent:
            shutil.rmtree(staging_dir)
        raise
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--snapshot-path", type=Path)
    source.add_argument("--local-run-root", type=Path)
    parser.add_argument("--local-session-log", type=Path)
    parser.add_argument("--reported-run-root", default=DEFAULT_REPORTED_RUN_ROOT)
    parser.add_argument("--reported-session-log", default=DEFAULT_REPORTED_SESSION_LOG)
    parser.add_argument("--source-host", default="l20")
    parser.add_argument("--collected-at")
    parser.add_argument("--gate1-report-path", type=Path, default=DEFAULT_GATE1_REPORT)
    parser.add_argument("--e0-report-path", type=Path, default=DEFAULT_E0_REPORT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.local_run_root is not None:
        if args.local_session_log is None:
            raise ValueError("--local-session-log is required with --local-run-root")
        snapshot = collect_local_snapshot(
            local_run_root=args.local_run_root,
            reported_run_root=args.reported_run_root,
            local_session_log=args.local_session_log,
            reported_session_log=args.reported_session_log,
            source_host=args.source_host,
            collected_at=args.collected_at,
        )
        report = write_report(
            snapshot=snapshot,
            gate1_report_path=args.gate1_report_path,
            e0_report_path=args.e0_report_path,
            output_dir=args.output_dir,
        )
    else:
        report = write_report(
            snapshot_path=args.snapshot_path,
            gate1_report_path=args.gate1_report_path,
            e0_report_path=args.e0_report_path,
            output_dir=args.output_dir,
        )
    print(
        "WROTE "
        f"{args.output_dir} seeds={len(report['observations'])} "
        f"max_spread={format_number(report['observed_spread']['max_pairwise_test_p2_ndcg10'])}"
    )


if __name__ == "__main__":
    main()
