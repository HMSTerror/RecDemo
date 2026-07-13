#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from scripts.aaai27_adapters.risk04_08 import QueueSafetyError, _validate_artifact_manifest
from scripts.aaai27_queue.models import QueueManifest, TaskRecord
from scripts.aaai27_queue.storage import load_json, sha256_file


ACTIVE_BRANCH = "e1_pass"
INACTIVE_BRANCH = "e1_fail_audit"
EXPECTED_ACTIVE_TASKS = 14
EXPECTED_TOTAL_TASKS = 22
EXPECTED_EVALUATOR = "e0_full_tail_v2"
EXPECTED_SELECTOR = "validation-ndcg10-rowweighted-v1"
ALLOWED_EXITS = {"risk_gated_method", "audit_only", "submission_stop"}


class EvidenceBuildError(RuntimeError):
    """The frozen r7 evidence contract is incomplete or contradictory."""


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _record_path(root: Path, task_id: str) -> Path:
    digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()
    return root / "state" / "tasks" / f"{digest}.json"


def _load_record(path: Path, task_id: str) -> TaskRecord:
    try:
        record = TaskRecord(**load_json(path))
    except (OSError, TypeError, ValueError) as exc:
        raise EvidenceBuildError(f"invalid task record for {task_id}: {path}") from exc
    if record.task_id != task_id:
        raise EvidenceBuildError(f"task record identity mismatch for {task_id}")
    return record


def _metric(summary: Mapping[str, Any], split: str, family: str) -> float:
    try:
        value = float(summary[split]["p5"][family][2])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise EvidenceBuildError(f"summary lacks {split} p5 {family}@10") from exc
    if not math.isfinite(value):
        raise EvidenceBuildError(f"summary contains nonfinite {split} p5 {family}@10")
    return value


def _read_summary(path: Path) -> tuple[dict[str, Any], dict[str, float | int]]:
    try:
        summary = load_json(path)
    except (OSError, ValueError) as exc:
        raise EvidenceBuildError(f"invalid best summary: {path}") from exc
    try:
        best_step = int(summary["best_step"])
        best_metric = float(summary["best_metric"])
    except (KeyError, TypeError, ValueError) as exc:
        raise EvidenceBuildError(f"best summary selector fields are invalid: {path}") from exc
    if best_step < 0 or not math.isfinite(best_metric):
        raise EvidenceBuildError(f"best summary selector fields are invalid: {path}")
    values: dict[str, float | int] = {
        "best_step": best_step,
        "validation_hr10": _metric(summary, "validation", "hr"),
        "validation_ndcg10": _metric(summary, "validation", "ndcg"),
        "test_hr10": _metric(summary, "test", "hr"),
        "test_ndcg10": _metric(summary, "test", "ndcg"),
    }
    if not math.isclose(best_metric, float(values["validation_ndcg10"]), rel_tol=0.0, abs_tol=1e-12):
        raise EvidenceBuildError(f"best_metric is not selected validation NDCG@10: {path}")
    return summary, values


def _validate_terminal(root: Path, queue_hash: str) -> tuple[str | None, dict[str, Any] | None]:
    marker_path = root / "markers" / "RISK-08_EXIT.json"
    terminal_path = root / "state" / "TERMINAL.json"
    if marker_path.exists() != terminal_path.exists():
        raise EvidenceBuildError("RISK-08 exit and TERMINAL.json must appear together")
    if not marker_path.exists():
        return None, None
    try:
        marker = load_json(marker_path)
        terminal = load_json(terminal_path)
    except (OSError, ValueError) as exc:
        raise EvidenceBuildError("invalid RISK-08 terminal evidence") from exc
    exit_value = marker.get("exit")
    if exit_value not in ALLOWED_EXITS:
        raise EvidenceBuildError(f"unknown RISK-08 exit: {exit_value!r}")
    if marker.get("queue_manifest_sha256") != queue_hash or marker.get("no_rescue") is not True:
        raise EvidenceBuildError("RISK-08 marker violates queue-hash/no-rescue contract")
    if (
        terminal.get("status") != "terminal"
        or terminal.get("outcome") != "risk08_exit"
        or terminal.get("no_rescue") is not True
        or terminal.get("risk08_exit") != exit_value
        or terminal.get("risk08_marker") != marker
    ):
        raise EvidenceBuildError("TERMINAL.json disagrees with RISK-08 exit")
    return str(exit_value), marker


def _validate_manifest_contract(manifest: QueueManifest) -> tuple[list[Any], list[Any]]:
    if len(manifest.tasks) != EXPECTED_TOTAL_TASKS:
        raise EvidenceBuildError(f"r7 manifest must contain 22 tasks, found {len(manifest.tasks)}")
    active = [task for task in manifest.tasks if task.branch == ACTIVE_BRANCH]
    inactive = [task for task in manifest.tasks if task.branch == INACTIVE_BRANCH]
    if len(active) != EXPECTED_ACTIVE_TASKS or len(inactive) != 8:
        raise EvidenceBuildError(
            f"r7 branch matrix mismatch: active={len(active)} inactive={len(inactive)}"
        )
    expected_ids = set()
    for dataset in ("Beauty", "Steam"):
        expected_ids.add(f"pilot.e1_pass.{dataset}.host")
        for level in (0, 60, 100):
            expected_ids.add(f"pilot.e1_pass.{dataset}.anchor.c{level}")
            expected_ids.add(f"pilot.e1_pass.{dataset}.full.c{level}")
    if {task.task_id for task in active} != expected_ids:
        raise EvidenceBuildError("r7 active task identities do not match the frozen 14-task matrix")
    for task in active:
        if task.seed != 100:
            raise EvidenceBuildError(f"r7 task seed mismatch: {task.task_id}")
        if task.evaluator_version != EXPECTED_EVALUATOR:
            raise EvidenceBuildError(f"r7 evaluator mismatch: {task.task_id}")
        if task.selector_version != EXPECTED_SELECTOR:
            raise EvidenceBuildError(f"r7 selector mismatch: {task.task_id}")
        if len(task.success_artifacts) != 2:
            raise EvidenceBuildError(f"r7 success-artifact contract mismatch: {task.task_id}")
    return active, inactive


def build_paper_evidence(
    queue_root: Path | str,
    expected_manifest_sha256: str,
    output_dir: Path | str,
    *,
    allow_not_ready: bool = False,
) -> dict[str, Any]:
    root = Path(queue_root).resolve(strict=True)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    metrics_path = output / "r7_paper_metrics.csv"
    evidence_path = output / "r7_paper_evidence.json"
    for stale in (metrics_path, evidence_path):
        if stale.exists():
            stale.unlink()
    manifest_path = root / "queue" / "queue_seed100.json"
    if not manifest_path.is_file():
        raise EvidenceBuildError(f"queue manifest is missing: {manifest_path}")
    actual_hash = sha256_file(manifest_path)
    if actual_hash != expected_manifest_sha256:
        raise EvidenceBuildError(
            f"manifest SHA-256 mismatch: expected={expected_manifest_sha256} actual={actual_hash}"
        )
    try:
        manifest = QueueManifest.from_dict(load_json(manifest_path))
    except (OSError, TypeError, ValueError) as exc:
        raise EvidenceBuildError("invalid queue manifest") from exc
    active, inactive = _validate_manifest_contract(manifest)
    if Path(manifest.run_root).resolve(strict=False) != root:
        raise EvidenceBuildError("manifest run_root does not match queue root")
    inactive_records = [task.task_id for task in inactive if _record_path(root, task.task_id).exists()]
    if inactive_records:
        raise EvidenceBuildError(f"inactive branch has task records: {inactive_records}")
    records = {
        task.task_id: _load_record(_record_path(root, task.task_id), task.task_id)
        for task in active
        if _record_path(root, task.task_id).exists()
    }
    failed = sorted(task_id for task_id, record in records.items() if record.status not in {"passed", "running"})
    if failed:
        raise EvidenceBuildError(f"r7 contains failed/invalid task records: {failed}")
    passed = sum(record.status == "passed" for record in records.values())
    running = sum(record.status == "running" for record in records.values())
    exit_value, marker = _validate_terminal(root, actual_hash)
    status: dict[str, Any] = {
        "schema_version": 1,
        "state": "not_ready",
        "queue_root": str(root),
        "queue_manifest_sha256": actual_hash,
        "expected_active_tasks": EXPECTED_ACTIVE_TASKS,
        "passed_active_tasks": passed,
        "running_active_tasks": running,
        "missing_active_tasks": EXPECTED_ACTIVE_TASKS - len(records),
        "risk08_exit": exit_value,
        "paper_metrics_emitted": False,
        "single_seed": 100,
    }
    if exit_value is None:
        _write_json(output / "paper_evidence_status.json", status)
        if not allow_not_ready:
            raise EvidenceBuildError("r7 is not terminal; pass --allow-not-ready for status-only output")
        return status
    if passed != EXPECTED_ACTIVE_TASKS or running:
        raise EvidenceBuildError(
            f"terminal r7 lacks 14/14 passed tasks: passed={passed} running={running}"
        )
    if exit_value != "risk_gated_method":
        status["state"] = "preserve_only"
        _write_json(output / "paper_evidence_status.json", status)
        return status

    rows: list[dict[str, Any]] = []
    artifact_hashes: dict[str, str] = {}
    for task in sorted(active, key=lambda item: (str(item.dataset), str(item.arm))):
        task_log = root / "logs" / "tasks" / f"{task.task_id}.log"
        if not task_log.is_file() or task_log.stat().st_size <= 0:
            raise EvidenceBuildError(f"task log is missing or empty: {task.task_id}")
        for relative in task.success_artifacts:
            path = root / relative
            if not path.is_file() or path.stat().st_size <= 0:
                raise EvidenceBuildError(f"success artifact is missing or empty: {task.task_id}: {relative}")
        manifest_artifact = root / task.success_artifacts[1]
        try:
            artifact_hashes[task.task_id] = _validate_artifact_manifest(
                root, manifest_artifact, task.to_dict(), actual_hash
            )
        except (QueueSafetyError, OSError, ValueError) as exc:
            raise EvidenceBuildError(f"artifact contract failed for {task.task_id}: {exc}") from exc
        summary_path = root / task.success_artifacts[0]
        _, values = _read_summary(summary_path)
        interpretation = (
            "explicit_phi_R_0_sanity_check"
            if task.arm == "risk_gated_full_c100"
            else "single_run_observation"
        )
        rows.append({
            "dataset": task.dataset,
            "arm": task.arm,
            "seed": task.seed,
            "best_step": values["best_step"],
            "validation_hr10": values["validation_hr10"],
            "validation_ndcg10": values["validation_ndcg10"],
            "test_hr10": values["test_hr10"],
            "test_ndcg10": values["test_ndcg10"],
            "evaluator_version": task.evaluator_version,
            "selector_version": task.selector_version,
            "interpretation": interpretation,
            "summary_path": task.success_artifacts[0],
            "summary_sha256": sha256_file(summary_path),
            "artifact_manifest_path": task.success_artifacts[1],
            "artifact_manifest_sha256": artifact_hashes[task.task_id],
        })
    fieldnames = list(rows[0])
    temporary_csv = metrics_path.with_suffix(".csv.tmp")
    with temporary_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temporary_csv.replace(metrics_path)
    evidence = {
        "schema_version": 1,
        "status": "ready",
        "risk08_exit": exit_value,
        "no_rescue": marker.get("no_rescue") if marker else None,
        "queue_manifest_sha256": actual_hash,
        "task_count": len(rows),
        "metrics_csv": metrics_path.name,
        "metrics_csv_sha256": sha256_file(metrics_path),
        "artifact_manifest_sha256": artifact_hashes,
        "wording_boundary": "single-run observation; no significance, stability, or seed-variance claim",
    }
    _write_json(evidence_path, evidence)
    status.update({"state": "ready", "paper_metrics_emitted": True})
    _write_json(output / "paper_evidence_status.json", status)
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed read-only r7 paper evidence builder")
    parser.add_argument("--queue-root", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-not-ready", action="store_true")
    args = parser.parse_args()
    try:
        status = build_paper_evidence(
            args.queue_root,
            args.expected_manifest_sha256,
            args.output_dir,
            allow_not_ready=args.allow_not_ready,
        )
    except EvidenceBuildError as exc:
        parser.error(str(exc))
    print(json.dumps(status, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
