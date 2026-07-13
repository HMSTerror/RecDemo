from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from scripts.aaai27_adapters.common import sha256_file, stable_sha256
from scripts.build_r7_paper_evidence import EvidenceBuildError, build_paper_evidence


DATASETS = ("Beauty", "Steam")
LEVELS = (0, 60, 100)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _task(branch: str, dataset: str, kind: str, level: int | None = None) -> dict:
    suffix = "host" if kind == "host" else f"{kind}.c{level}"
    task_id = f"pilot.{branch}.{dataset}.{suffix}"
    run_leaf = "host" if kind == "host" else f"{kind}_c{level}"
    arm = "host" if kind == "host" else (
        f"text_anchor_only_c{level}" if kind == "anchor" else f"risk_gated_full_c{level}"
    )
    run_rel = f"runs/{branch}/{dataset}/{run_leaf}"
    summary_name = "best_summary_adaptive.json" if kind == "host" else "best_summary_proposal_adaptive.json"
    summary_rel = f"{run_rel}/checkpoints-meta/{dataset}/{summary_name}"
    manifest_rel = f"{run_rel}/artifact_manifest.json"
    return {
        "schema_version": 1, "task_id": task_id, "ledger_id": "RISK-06",
        "phase": "pilot", "branch": branch, "kind": "gpu",
        "argv": ["python", "single_train.py"], "cwd": f"/srv/queue/{run_rel}",
        "env": {
            "PYTHONHASHSEED": "100", "AAAI_TASK_ID": task_id,
            "AAAI_NULL_CURVE_REFERENCE_POLICY": "not_applicable",
        },
        "dependencies": [], "required_markers": [],
        "success_artifacts": [summary_rel, manifest_rel],
        "failure_policy": "fail_closed", "max_attempts": 1, "gpu_slots": 1,
        "gpu_hours_low": 0.1, "gpu_hours_high": 1.0, "estimated_output_gib": 0.1,
        "seed": 100, "dataset": dataset, "arm": arm, "model": "PreferGrow",
        "run_dir": f"/srv/queue/{run_rel}", "code_revision": "a" * 40,
        "config_sha256": "b" * 64, "split_sha256": ("c" if dataset == "Beauty" else "d") * 64,
        "bank_sha256": None if kind == "host" else "e" * 64,
        "evaluator_version": "e0_full_tail_v2",
        "selector_version": "validation-ndcg10-rowweighted-v1",
        "atomic_group": f"{branch}.{dataset}", "priority": 0,
    }


def _manifest(root: Path) -> dict:
    active = []
    inactive = []
    for dataset in DATASETS:
        active.append(_task("e1_pass", dataset, "host"))
        inactive.append(_task("e1_fail_audit", dataset, "host"))
        for level in LEVELS:
            active.extend((_task("e1_pass", dataset, "anchor", level), _task("e1_pass", dataset, "full", level)))
            inactive.append(_task("e1_fail_audit", dataset, "anchor", level))
    return {
        "schema_version": 1, "queue_id": "r7-test", "created_at": "2026-07-13T00:00:00+08:00",
        "run_root": str(root), "source_root": "/srv/source", "source_manifest_sha256": "f" * 64,
        "ledger_path": "/srv/ledger.csv", "ledger_sha256": "1" * 64,
        "gpu_ids": [0, 1], "gpu_budget_hours": 168.0, "min_free_disk_gib": 40.0,
        "tasks": active + inactive,
    }


def _summary(value: float) -> dict:
    return {
        "metric_name": "ndcg10", "best_step": 1000, "best_metric": value,
        "validation": {"p5": {"hr": [0.1, 0.2, 0.3], "ndcg": [0.01, 0.02, value]}},
        "test": {"p5": {"hr": [0.11, 0.21, 0.31], "ndcg": [0.011, 0.021, value + 0.001]}},
    }


def _complete_task(root: Path, task: dict, queue_hash: str, value: float) -> None:
    summary_path = root / task["success_artifacts"][0]
    _write_json(summary_path, _summary(value))
    run_dir = root / Path(task["success_artifacts"][1]).parent
    run_log = run_dir / "single_train.log"
    run_log.write_text("training complete\n", encoding="utf-8")
    artifact = {
        "schema_version": 1, "task_id": task["task_id"], "status": "pass",
        "queue_manifest_sha256": queue_hash, "source_revision": task["code_revision"],
        "config_sha256": task["config_sha256"], "split_sha256": task["split_sha256"],
        "bank_sha256": task["bank_sha256"], "evaluator_version": task["evaluator_version"],
        "selector_version": task["selector_version"],
        "metrics_provenance": {"path": task["success_artifacts"][0], "sha256": sha256_file(summary_path)},
        "log_provenance": {
            "path": str(run_log.relative_to(root)).replace("\\", "/"),
            "sha256": sha256_file(run_log), "size_bytes": run_log.stat().st_size,
        },
        "null_curve_reference": {"policy": "not_applicable"},
        "gate_dataset_scale": None,
    }
    artifact["artifact_sha256"] = stable_sha256(artifact)
    _write_json(root / task["success_artifacts"][1], artifact)
    task_log = root / "logs" / "tasks" / f"{task['task_id']}.log"
    task_log.parent.mkdir(parents=True, exist_ok=True)
    task_log.write_text("wrapper complete\n", encoding="utf-8")
    record = {
        "task_id": task["task_id"], "status": "passed", "attempt": 1, "pid": 1,
        "process_start_time": "1", "gpu_id": 0, "started_at": "2026-07-13T00:00:00Z",
        "ended_at": "2026-07-13T00:01:00Z", "exit_code": 0, "gpu_seconds": 60.0, "reason": None,
    }
    digest = hashlib.sha256(task["task_id"].encode()).hexdigest()
    _write_json(root / "state" / "tasks" / f"{digest}.json", record)


def _layout(tmp_path: Path, *, terminal_exit: str | None = None) -> tuple[Path, str]:
    root = tmp_path / "queue"
    manifest = _manifest(root)
    manifest_path = root / "queue" / "queue_seed100.json"
    _write_json(manifest_path, manifest)
    queue_hash = sha256_file(manifest_path)
    if terminal_exit is not None:
        for index, task in enumerate(task for task in manifest["tasks"] if task["branch"] == "e1_pass"):
            _complete_task(root, task, queue_hash, 0.02 + index / 1000)
        marker = {
            "schema_version": 1, "risk_id": "RISK-08", "exit": terminal_exit,
            "queue_manifest_sha256": queue_hash, "no_rescue": True,
        }
        _write_json(root / "markers" / "RISK-08_EXIT.json", marker)
        _write_json(root / "state" / "TERMINAL.json", {
            "status": "terminal", "no_rescue": True, "outcome": "risk08_exit",
            "risk08_exit": terminal_exit, "risk08_marker": marker,
        })
    return root, queue_hash


def test_nonterminal_snapshot_emits_status_only(tmp_path: Path) -> None:
    root, queue_hash = _layout(tmp_path)
    output = tmp_path / "out"

    status = build_paper_evidence(root, queue_hash, output, allow_not_ready=True)

    assert status["state"] == "not_ready"
    assert (output / "paper_evidence_status.json").is_file()
    assert not (output / "r7_paper_metrics.csv").exists()
    assert not (output / "r7_paper_evidence.json").exists()


def test_authorized_terminal_emits_complete_atomic_table(tmp_path: Path) -> None:
    root, queue_hash = _layout(tmp_path, terminal_exit="risk_gated_method")
    output = tmp_path / "out"

    status = build_paper_evidence(root, queue_hash, output)

    assert status["state"] == "ready"
    rows = list(csv.DictReader((output / "r7_paper_metrics.csv").open(encoding="utf-8")))
    assert len(rows) == 14
    assert {row["dataset"] for row in rows} == {"Beauty", "Steam"}
    beauty = next(row for row in rows if row["dataset"] == "Beauty" and row["arm"] == "risk_gated_full_c0")
    assert beauty["validation_ndcg10"] and beauty["test_ndcg10"]
    c100 = [row for row in rows if row["arm"] == "risk_gated_full_c100"]
    assert all(row["interpretation"] == "explicit_phi_R_0_sanity_check" for row in c100)


@pytest.mark.parametrize("terminal_exit", ["audit_only", "submission_stop"])
def test_preserve_only_terminal_never_emits_performance_table(tmp_path: Path, terminal_exit: str) -> None:
    root, queue_hash = _layout(tmp_path, terminal_exit=terminal_exit)
    output = tmp_path / "out"

    status = build_paper_evidence(root, queue_hash, output)

    assert status["state"] == "preserve_only"
    assert not (output / "r7_paper_metrics.csv").exists()
    assert not (output / "r7_paper_evidence.json").exists()


def test_empty_task_log_fails_closed_without_partial_outputs(tmp_path: Path) -> None:
    root, queue_hash = _layout(tmp_path, terminal_exit="risk_gated_method")
    task_log = next((root / "logs" / "tasks").glob("*.log"))
    task_log.write_text("", encoding="utf-8")
    output = tmp_path / "out"

    with pytest.raises(EvidenceBuildError, match="task log"):
        build_paper_evidence(root, queue_hash, output)

    assert not (output / "r7_paper_metrics.csv").exists()
    assert not (output / "r7_paper_evidence.json").exists()
