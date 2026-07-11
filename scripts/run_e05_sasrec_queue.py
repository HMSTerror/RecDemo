#!/usr/bin/env python3
"""Run a validated E5 SASRec manifest serially on GPU0, fail-closed."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATASETS = ("Steam", "ML1M", "Beauty", "ATG")


def canonical_hash(payload: Any) -> str:
    value = dict(payload)
    value.pop("manifest_sha256", None)
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("manifest_sha256") != canonical_hash(manifest):
        raise ValueError("E5 manifest self-hash mismatch")
    if manifest.get("gpu_ids") != [0] or manifest.get("seed_set") != [100]:
        raise ValueError("E5 manifest must be GPU0-only and seed100-only")
    if manifest.get("all_four_required") is not True or manifest.get("atomic_group") != "E05.SASRec.four-domain":
        raise ValueError("E5 manifest is not the approved four-domain atomic group")
    tasks = manifest.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 4:
        raise ValueError("E5 manifest must contain exactly four tasks")
    if {task.get("dataset") for task in tasks} != set(DATASETS):
        raise ValueError("E5 manifest dataset set is not Steam/ML1M/Beauty/ATG")
    for task in tasks:
        if task.get("seed") != 100 or task.get("gpu_slots") != 1 or task.get("failure_policy") != "fail_closed":
            raise ValueError(f"task contract mismatch: {task.get('task_id')}")
        if task.get("cwd") != task.get("run_dir"):
            raise ValueError(f"task cwd/run_dir mismatch: {task.get('task_id')}")
        run_dir = Path(task["run_dir"])
        if run_dir != Path(manifest["queue_root"]) / "runs" / "SASRec" / str(task["dataset"]):
            raise ValueError(f"task run_dir containment mismatch: {task.get('task_id')}")
        argv = task.get("argv", [])
        if "--startup-probe-only" in argv or "--seed" not in argv or "100" not in argv:
            raise ValueError(f"task contains an invalid scientific override: {task.get('task_id')}")
    return manifest


def query_gpu_processes() -> list[str]:
    try:
        devices = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,uuid", "--format=csv,noheader,nounits"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        gpu0_uuid = None
        for line in devices.stdout.splitlines():
            fields = [field.strip() for field in line.split(",")]
            if len(fields) >= 2 and fields[0] == "0":
                gpu0_uuid = fields[1]
                break
        if not gpu0_uuid:
            raise RuntimeError("GPU0 UUID was not reported")
        result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=gpu_uuid,pid", "--format=csv,noheader,nounits"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"cannot establish GPU occupancy safely: {exc}") from exc
    pids: list[str] = []
    for line in result.stdout.splitlines():
        fields = [field.strip() for field in line.split(",")]
        if len(fields) >= 2 and fields[0] == gpu0_uuid:
            pids.append(fields[1])
    return pids


def record_resource_snapshot(path: Path) -> None:
    try:
        result = subprocess.run(["nvidia-smi"], check=True, capture_output=True, text=True, timeout=15)
        path.write_text(result.stdout, encoding="utf-8")
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        path.write_text(f"nvidia-smi failed: {exc}\n", encoding="utf-8")


def run_queue(manifest_path: Path) -> dict[str, Any]:
    manifest = load_manifest(manifest_path.resolve())
    queue_root = Path(manifest["queue_root"]).resolve()
    if queue_root != manifest_path.resolve().parent:
        raise ValueError("manifest path must be directly inside queue_root")
    free_gib = shutil.disk_usage(queue_root.parent).free / (1024**3)
    if free_gib < float(manifest["min_free_disk_gib"]):
        raise RuntimeError(f"disk hard gate failed: {free_gib:.2f} GiB free")
    if query_gpu_processes():
        raise RuntimeError("GPU0 is occupied before E5 launch; fail closed")
    record_resource_snapshot(queue_root / "resources_before.txt")
    status: dict[str, Any] = {
        "schema_version": 1,
        "queue_id": manifest["queue_id"],
        "manifest_sha256": manifest["manifest_sha256"],
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "free_disk_gib_before": free_gib,
        "tasks": [],
    }
    write_json(queue_root / "queue_status.json", status)
    for task in sorted(manifest["tasks"], key=lambda row: DATASETS.index(row["dataset"])):
        dataset = task["dataset"]
        run_dir = Path(task["run_dir"])
        if run_dir.exists() and any(run_dir.iterdir()):
            raise RuntimeError(f"run directory is not empty: {run_dir}")
        run_dir.mkdir(parents=True, exist_ok=False)
        log_path = run_dir / "stdout.log"
        task_record: dict[str, Any] = {
            "task_id": task["task_id"],
            "dataset": dataset,
            "run_dir": str(run_dir),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
            "argv": task["argv"],
            "cwd": task["cwd"],
        }
        status["tasks"].append(task_record)
        write_json(queue_root / "queue_status.json", status)
        env = os.environ.copy()
        env.update(task["env"])
        env["CUDA_VISIBLE_DEVICES"] = "0"
        with log_path.open("w", encoding="utf-8") as log_handle:
            completed = subprocess.run(task["argv"], cwd=str(run_dir), env=env, stdout=log_handle, stderr=subprocess.STDOUT)
        task_record["returncode"] = int(completed.returncode)
        task_record["finished_at"] = datetime.now(timezone.utc).isoformat()
        if completed.returncode != 0:
            task_record["status"] = "failed"
            status["status"] = "failed_incomplete_atomic_group"
            status["stop_reason"] = f"{dataset} returncode={completed.returncode}; no retry and no favorable subset"
            write_json(queue_root / "queue_status.json", status)
            record_resource_snapshot(queue_root / "resources_after_failure.txt")
            return status
        required = [run_dir / name for name in task["success_artifacts"]]
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            task_record["status"] = "failed"
            task_record["missing_artifacts"] = missing
            status["status"] = "failed_incomplete_atomic_group"
            status["stop_reason"] = f"{dataset} missing artifacts; no retry and no favorable subset"
            write_json(queue_root / "queue_status.json", status)
            record_resource_snapshot(queue_root / "resources_after_failure.txt")
            return status
        task_record["status"] = "passed"
        status["last_completed_dataset"] = dataset
        write_json(queue_root / "queue_status.json", status)
        if query_gpu_processes():
            status["status"] = "failed_incomplete_atomic_group"
            status["stop_reason"] = f"GPU0 remained occupied after {dataset}; fail closed"
            write_json(queue_root / "queue_status.json", status)
            record_resource_snapshot(queue_root / "resources_after_failure.txt")
            return status
    status["status"] = "passed_four_domain_atomic_group"
    status["finished_at"] = datetime.now(timezone.utc).isoformat()
    status["free_disk_gib_after"] = shutil.disk_usage(queue_root.parent).free / (1024**3)
    record_resource_snapshot(queue_root / "resources_after.txt")
    write_json(queue_root / "queue_status.json", status)
    return status


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    return parser.parse_args(argv)


if __name__ == "__main__":
    result = run_queue(parse_args().manifest)
    print(json.dumps({"status": result["status"], "queue_id": result["queue_id"]}, sort_keys=True))
