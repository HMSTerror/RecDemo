from __future__ import annotations

from typing import Any


DEFAULT_RUN_ROOT = "/srv/queue"


def make_task(**overrides: Any) -> dict[str, Any]:
    task_id = str(overrides.get("task_id", "RISK-01.lock"))
    payload: dict[str, Any] = {
        "schema_version": 1,
        "task_id": task_id,
        "ledger_id": "RISK-01",
        "phase": "front_gate",
        "branch": "common",
        "kind": "gpu",
        "argv": ["/opt/venv/bin/python", "scripts/fake_adapter.py", "--seed", "100"],
        "cwd": "/srv/bundle/source",
        "env": {"PYTHONHASHSEED": "100"},
        "dependencies": [],
        "required_markers": [],
        "success_artifacts": [f"manifests/{task_id}.json"],
        "failure_policy": "fail_closed",
        "max_attempts": 1,
        "gpu_slots": 1,
        "gpu_hours_low": 0.1,
        "gpu_hours_high": 1.0,
        "estimated_output_gib": 0.1,
        "seed": 100,
        "dataset": "Beauty",
        "arm": "host",
        "model": "PreferGrow",
        "run_dir": f"{DEFAULT_RUN_ROOT}/runs/{task_id}",
        "code_revision": "a" * 40,
        "config_sha256": "b" * 64,
        "split_sha256": "c" * 64,
        "bank_sha256": None,
        "evaluator_version": "evaluator-tailfix-v1",
        "selector_version": "validation-ndcg10-p5-v1",
        "atomic_group": None,
        "priority": 0,
    }
    payload.update(overrides)
    return payload


def make_manifest(tasks: list[dict[str, Any]], **overrides: Any) -> dict[str, Any]:
    run_root = str(overrides.get("run_root", DEFAULT_RUN_ROOT))
    normalized: list[dict[str, Any]] = []
    for source in tasks:
        task = dict(source)
        if str(task["run_dir"]).startswith(f"{DEFAULT_RUN_ROOT}/runs/"):
            task["run_dir"] = f"{run_root}/runs/{task['task_id']}"
        normalized.append(task)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "queue_id": "aaai27-seed100-test",
        "created_at": "2026-07-10T22:00:00+08:00",
        "run_root": run_root,
        "source_root": "/srv/bundle/source",
        "source_manifest_sha256": "d" * 64,
        "ledger_path": "/srv/bundle/issues/2026-07-10_21-18-20-aaai27-evidence-risk-rescue.csv",
        "ledger_sha256": "e" * 64,
        "gpu_ids": [0, 1],
        "gpu_budget_hours": 168.0,
        "min_free_disk_gib": 40.0,
        "tasks": normalized,
    }
    payload.update(overrides)
    return payload
