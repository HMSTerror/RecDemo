from __future__ import annotations

from scripts.aaai27_continuation.manifest import (
    DatasetContract,
    FrozenContinuationInputs,
    RiskCondition,
    build_continuation_manifest,
)
from scripts.aaai27_queue.models import QueueManifest
import pytest

from scripts.aaai27_queue.validation import ManifestError, validate_manifest


DOMAINS = ("Steam", "ML1M", "Beauty", "ATG")


def _inputs() -> FrozenContinuationInputs:
    datasets = {
        dataset: DatasetContract(
            dataset_dir=f"/data/paper_raw_v1/{dataset}",
            config_sha256=(str(index + 1) * 64)[:64],
            split_sha256=(str(index + 5) * 64)[:64],
            text_bank_path=f"/data/banks/{dataset}/items.pkl",
            embedding_path=f"/data/banks/{dataset}/embeddings.pkl",
            bank_sha256=(chr(97 + index) * 64),
            embedding_sha256=(chr(101 + index) * 64),
            null_curve_path=f"/data/banks/{dataset}/null.json",
            null_curve_sha256=(chr(105 + index) * 64),
            phi_r=1.0,
        )
        for index, dataset in enumerate(DOMAINS)
    }
    return FrozenContinuationInputs(
        queue_id="aaai27-method-pass-continuation-test",
        created_at="2026-07-13T20:00:00+08:00",
        queue_root="/data/Zijian/goal/aaai27_queue/2026-07-13-method-pass-test",
        source_root="/data/Zijian/goal/RecDemo_aaai27_continuation_test",
        python_executable="/data/Zijian/goal/PreferGrow/.venv/bin/python3",
        code_revision="a" * 40,
        source_manifest_sha256="b" * 64,
        ledger_path="/data/Zijian/goal/RecDemo_aaai27_continuation_test/issues/2026-07-10_21-18-20-aaai27-evidence-risk-rescue.csv",
        ledger_sha256="c" * 64,
        datasets=datasets,
        high_risk_condition=RiskCondition(
            rank="high_risk",
            dataset="Steam",
            corruption_level=60,
            selection_sha256="d" * 64,
        ),
        low_risk_condition=RiskCondition(
            rank="low_risk",
            dataset="Beauty",
            corruption_level=0,
            selection_sha256="e" * 64,
        ),
        e5_root="/data/Zijian/goal/aaai27_queue/2026-07-12-e05-sasrec-seed100-gpu0-c5c9280",
        gpu_ids=(0, 1),
    )


def test_manifest_contains_exact_frozen_stage_d_matrix() -> None:
    raw = build_continuation_manifest(_inputs())
    manifest = QueueManifest.from_dict(raw)
    validate_manifest(manifest)
    assert len([task for task in manifest.tasks if task.ledger_id == "RISK-13"]) == 8
    assert len([task for task in manifest.tasks if task.ledger_id == "RISK-14"]) == 12
    assert len([task for task in manifest.tasks if task.ledger_id == "RISK-10"]) == 12
    assert len([task for task in manifest.tasks if task.ledger_id == "RISK-11"]) == 4
    assert len([task for task in manifest.tasks if task.task_id == "continuation.method_pass_gate"]) == 1
    assert {task.seed for task in manifest.tasks if task.kind == "gpu"} == {100}
    assert all(task.branch == "method_pass" for task in manifest.tasks)
    assert sum(task.gpu_hours_high for task in manifest.tasks) <= 168.0


def test_risk13_uses_real_wrapped_prefergrow_training_argv() -> None:
    manifest = QueueManifest.from_dict(build_continuation_manifest(_inputs()))
    task = next(
        task
        for task in manifest.tasks
        if task.ledger_id == "RISK-13" and task.dataset == "ML1M" and task.arm == "host"
    )
    assert task.argv[0].endswith("python3")
    assert task.argv[1].endswith("run_aaai27_pilot_task.py")
    separator = task.argv.index("--")
    training = task.argv[separator + 1 :]
    assert training[0].endswith("python3")
    assert training[1].endswith("single_train.py")
    assert "random_seed=100" in training
    assert "training.data=ML1M" in training
    assert f"work_dir={task.run_dir}" in training
    assert "graph.type=adaptive" in training
    assert task.required_markers == (
        "protocol/adapters/prefergrow/ML1M/PASS.json",
    )


def test_risk13_full_binds_final_v2_text_assets() -> None:
    manifest = QueueManifest.from_dict(build_continuation_manifest(_inputs()))
    task = next(
        task
        for task in manifest.tasks
        if task.ledger_id == "RISK-13" and task.dataset == "Steam" and task.arm == "risk_gated_full"
    )
    separator = task.argv.index("--")
    training = task.argv[separator + 1 :]
    assert "graph.type=proposal_adaptive" in training
    assert "text_side.enabled=True" in training
    assert "text_side.kernel_version=v2" in training
    assert "text_side.injection_mode=kernel" in training
    assert "text_side.ablation_mode=none" in training
    assert "text_side.gate_dataset_scale_override=1.0" in training
    assert task.bank_sha256 == "a" * 64


def test_unimplemented_models_and_risk14_are_adapter_gated() -> None:
    manifest = QueueManifest.from_dict(build_continuation_manifest(_inputs()))
    for task in manifest.tasks:
        if task.ledger_id == "RISK-14":
            assert task.required_markers == ("protocol/adapters/risk14/PASS.json",)
        if task.model in {"Caser", "GRURec", "DiffRec"}:
            assert task.required_markers == (
                f"protocol/adapters/{task.model.casefold()}/PASS.json",
            )


def test_sasrec_slots_are_zero_gpu_e5_reuse_audits() -> None:
    manifest = QueueManifest.from_dict(build_continuation_manifest(_inputs()))
    tasks = [task for task in manifest.tasks if task.model == "SASRec"]
    assert len(tasks) == 4
    assert all(task.kind == "contract_gate" and task.gpu_slots == 0 for task in tasks)
    assert all("audit_e05_sasrec_reuse.py" in task.argv[1] for task in tasks)
    assert {task.dataset for task in tasks} == set(DOMAINS)


def test_unsafe_continuation_marker_path_is_rejected() -> None:
    raw = build_continuation_manifest(_inputs())
    target = next(task for task in raw["tasks"] if task["ledger_id"] == "RISK-13")
    target["required_markers"] = ["../PASS.json"]
    with pytest.raises(ManifestError, match="unsafe required marker"):
        validate_manifest(QueueManifest.from_dict(raw))


def test_guarded_model_cannot_drop_its_adapter_marker() -> None:
    raw = build_continuation_manifest(_inputs())
    target = next(task for task in raw["tasks"] if task["model"] == "DiffRec")
    target["required_markers"] = []
    with pytest.raises(ManifestError, match="guarded model lacks adapter marker"):
        validate_manifest(QueueManifest.from_dict(raw))
