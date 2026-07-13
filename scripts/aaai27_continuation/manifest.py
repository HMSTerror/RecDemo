from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scripts.aaai27_queue.models import QueueManifest
from scripts.aaai27_queue.validation import validate_manifest


DOMAINS = ("Steam", "ML1M", "Beauty", "ATG")
RISK14_ARMS = (
    "host",
    "text_anchor_only",
    "global_p",
    "dataset_gate_only",
    "full",
    "u_shuffle",
)
METHOD_GATE_ID = "continuation.method_pass_gate"
EVALUATOR_VERSION = "e0_full_tail_v2"
SELECTOR_VERSION = "validation-ndcg10-rowweighted-v1"


@dataclass(frozen=True)
class DatasetContract:
    dataset_dir: str
    config_sha256: str
    split_sha256: str
    text_bank_path: str
    embedding_path: str
    bank_sha256: str
    embedding_sha256: str
    null_curve_path: str
    null_curve_sha256: str
    phi_r: float
    adapter_authorized: bool = True


@dataclass(frozen=True)
class RiskCondition:
    rank: str
    dataset: str
    corruption_level: int
    selection_sha256: str


@dataclass(frozen=True)
class FrozenContinuationInputs:
    queue_id: str
    created_at: str
    queue_root: str
    source_root: str
    python_executable: str
    code_revision: str
    source_manifest_sha256: str
    ledger_path: str
    ledger_sha256: str
    datasets: dict[str, DatasetContract]
    high_risk_condition: RiskCondition
    low_risk_condition: RiskCondition
    e5_root: str
    gpu_ids: tuple[int, ...] = (0, 1)


def _run_rel(task_id: str) -> str:
    return "runs/" + task_id.removeprefix("continuation.").replace(".", "/")


def _base_task(
    inputs: FrozenContinuationInputs,
    *,
    task_id: str,
    ledger_id: str,
    kind: str,
    argv: list[str],
    cwd: str,
    run_dir: str,
    env: dict[str, str],
    dependencies: list[str],
    required_markers: list[str],
    success_artifacts: list[str],
    gpu_hours_low: float,
    gpu_hours_high: float,
    estimated_output_gib: float,
    seed: int | None,
    dataset: str | None,
    arm: str | None,
    model: str | None,
    config_sha256: str,
    split_sha256: str | None,
    bank_sha256: str | None,
    atomic_group: str | None,
    priority: int,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "task_id": task_id,
        "ledger_id": ledger_id,
        "phase": "continuation",
        "branch": "method_pass",
        "kind": kind,
        "argv": argv,
        "cwd": cwd,
        "env": env,
        "dependencies": dependencies,
        "required_markers": required_markers,
        "success_artifacts": success_artifacts,
        "failure_policy": "fail_closed",
        "max_attempts": 1,
        "gpu_slots": 1 if kind == "gpu" else 0,
        "gpu_hours_low": gpu_hours_low,
        "gpu_hours_high": gpu_hours_high,
        "estimated_output_gib": estimated_output_gib,
        "seed": seed,
        "dataset": dataset,
        "arm": arm,
        "model": model,
        "run_dir": run_dir,
        "code_revision": inputs.code_revision,
        "config_sha256": config_sha256,
        "split_sha256": split_sha256,
        "bank_sha256": bank_sha256,
        "evaluator_version": EVALUATOR_VERSION if dataset else None,
        "selector_version": SELECTOR_VERSION if dataset else None,
        "atomic_group": atomic_group,
        "priority": priority,
    }


def _method_gate(inputs: FrozenContinuationInputs) -> dict[str, Any]:
    run_dir = f"{inputs.queue_root}/gates/method_pass"
    return _base_task(
        inputs,
        task_id=METHOD_GATE_ID,
        ledger_id="RISK-08",
        kind="contract_gate",
        argv=[
            inputs.python_executable,
            f"{inputs.source_root}/scripts/aaai27_method_pass_continuation.py",
            "internal-method-gate",
            "--queue-root",
            inputs.queue_root,
        ],
        cwd=inputs.source_root,
        run_dir=run_dir,
        env={"PYTHONHASHSEED": "100"},
        dependencies=[],
        required_markers=[],
        success_artifacts=["state/method_pass_gate.json"],
        gpu_hours_low=0.0,
        gpu_hours_high=0.0,
        estimated_output_gib=0.001,
        seed=None,
        dataset=None,
        arm="method_pass_gate",
        model=None,
        config_sha256=inputs.source_manifest_sha256,
        split_sha256=None,
        bank_sha256=None,
        atomic_group=None,
        priority=0,
    )


def _training_base(
    inputs: FrozenContinuationInputs,
    dataset: str,
    run_dir: str,
    graph_type: str,
) -> list[str]:
    contract = inputs.datasets[dataset]
    return [
        inputs.python_executable,
        f"{inputs.source_root}/single_train.py",
        f"work_dir={run_dir}",
        "cuda=0",
        "random_seed=100",
        f"training.data={dataset}",
        f"data.{dataset}.path={contract.dataset_dir}",
        f"graph.type={graph_type}",
        "graph.is_disliked_item=True",
        "model.hidden_size=256",
        "model.cond_dim=256",
        "loss_type=score_entropy",
    ]


def _wrapped_training(
    inputs: FrozenContinuationInputs,
    training_argv: list[str],
) -> list[str]:
    return [
        inputs.python_executable,
        f"{inputs.source_root}/scripts/run_aaai27_pilot_task.py",
        "--",
        *training_argv,
    ]


def _prefergrow_env(
    inputs: FrozenContinuationInputs,
    *,
    task_id: str,
    dataset: str,
    arm: str,
    run_dir: str,
    summary_relative: str,
    artifact_relative: str,
    evidence_conditioned: bool,
) -> dict[str, str]:
    contract = inputs.datasets[dataset]
    env = {
        "PYTHONHASHSEED": "100",
        "AAAI_DATASET": dataset,
        "AAAI_ARM": arm,
        "AAAI_TASK_ID": task_id,
        "AAAI_QUEUE_ROOT": inputs.queue_root,
        "AAAI_RUN_DIR": run_dir,
        "AAAI_QUEUE_MANIFEST_PATH": (
            f"{inputs.queue_root}/queue/queue_seed100_continuation.json"
        ),
        "AAAI_SUMMARY_RELATIVE": summary_relative,
        "AAAI_ARTIFACT_MANIFEST_RELATIVE": artifact_relative,
        "AAAI_CODE_REVISION": inputs.code_revision,
        "AAAI_CONFIG_SHA256": contract.config_sha256,
        "AAAI_SPLIT_SHA256": contract.split_sha256,
        "AAAI_EVALUATOR_VERSION": EVALUATOR_VERSION,
        "AAAI_SELECTOR_VERSION": SELECTOR_VERSION,
    }
    if evidence_conditioned:
        env.update(
            {
                "AAAI_BANK_SHA256": contract.bank_sha256,
                "AAAI_EMBEDDING_SHA256": contract.embedding_sha256,
                "AAAI_CURRENT_EMBEDDING_SHA256": contract.embedding_sha256,
                "AAAI_NULL_CURVE_REFERENCE_POLICY": "frozen_clean_calibration",
                "AAAI_NULL_CURVE_PATH": contract.null_curve_path,
                "AAAI_NULL_CURVE_SHA256": contract.null_curve_sha256,
                "AAAI_NULL_CURVE_SOURCE_BANK_SHA256": contract.bank_sha256,
                "AAAI_GATE_DATASET_SCALE": str(contract.phi_r),
            }
        )
    else:
        env["AAAI_NULL_CURVE_REFERENCE_POLICY"] = "not_applicable"
    return env


def _risk13_task(
    inputs: FrozenContinuationInputs,
    dataset: str,
    arm: str,
) -> dict[str, Any]:
    task_id = f"continuation.RISK-13.{dataset}.{arm}.seed100"
    relative = _run_rel(task_id)
    run_dir = f"{inputs.queue_root}/{relative}"
    evidence_conditioned = arm == "risk_gated_full"
    graph_type = "proposal_adaptive" if evidence_conditioned else "adaptive"
    training = _training_base(inputs, dataset, run_dir, graph_type)
    contract = inputs.datasets[dataset]
    if evidence_conditioned:
        training.extend(
            [
                "text_side.enabled=True",
                f"text_side.dataset_dir={contract.dataset_dir}",
                f"text_side.text_bank_path={contract.text_bank_path}",
                f"text_side.embeddings_path={contract.embedding_path}",
                f"text_side.agreement_null_curve_path={contract.null_curve_path}",
                "text_side.kernel_version=v2",
                "text_side.temperature=0.2",
                "text_side.g_max=0.5",
                "text_side.ablation_mode=none",
                "text_side.injection_mode=kernel",
                "text_side.require_gate_source=True",
                f"text_side.gate_dataset_scale_override={contract.phi_r}",
            ]
        )
    summary_name = (
        "best_summary_proposal_adaptive.json"
        if evidence_conditioned
        else "best_summary_adaptive.json"
    )
    summary_relative = f"{relative}/checkpoints-meta/{dataset}/{summary_name}"
    artifact_relative = f"{relative}/artifact_manifest.json"
    high = {"Steam": 4.0, "ML1M": 26.0, "Beauty": 1.0, "ATG": 4.0}[dataset]
    return _base_task(
        inputs,
        task_id=task_id,
        ledger_id="RISK-13",
        kind="gpu",
        argv=_wrapped_training(inputs, training),
        cwd=run_dir,
        run_dir=run_dir,
        env=_prefergrow_env(
            inputs,
            task_id=task_id,
            dataset=dataset,
            arm=arm,
            run_dir=run_dir,
            summary_relative=summary_relative,
            artifact_relative=artifact_relative,
            evidence_conditioned=evidence_conditioned,
        ),
        dependencies=[METHOD_GATE_ID],
        required_markers=[
            f"protocol/adapters/prefergrow/{dataset}/PASS.json"
        ],
        success_artifacts=[summary_relative, artifact_relative],
        gpu_hours_low=0.25 if dataset == "Beauty" else 1.0,
        gpu_hours_high=high,
        estimated_output_gib=0.5,
        seed=100,
        dataset=dataset,
        arm=arm,
        model="PreferGrow",
        config_sha256=contract.config_sha256,
        split_sha256=contract.split_sha256,
        bank_sha256=contract.bank_sha256 if evidence_conditioned else None,
        atomic_group=f"RISK-13.{dataset}.matched",
        priority=10,
    )


def _risk14_task(
    inputs: FrozenContinuationInputs,
    condition: RiskCondition,
    arm: str,
) -> dict[str, Any]:
    dataset = condition.dataset
    contract = inputs.datasets[dataset]
    task_id = (
        f"continuation.RISK-14.{condition.rank}.{dataset}."
        f"c{condition.corruption_level}.{arm}.seed100"
    )
    relative = _run_rel(task_id)
    run_dir = f"{inputs.queue_root}/{relative}"
    argv = [
        inputs.python_executable,
        f"{inputs.source_root}/scripts/run_prefergrow_risk14.py",
        "--dataset",
        dataset,
        "--arm",
        arm,
        "--condition-rank",
        condition.rank,
        "--corruption-level",
        str(condition.corruption_level),
        "--selection-sha256",
        condition.selection_sha256,
        "--seed",
        "100",
        "--run-dir",
        run_dir,
    ]
    return _base_task(
        inputs,
        task_id=task_id,
        ledger_id="RISK-14",
        kind="gpu",
        argv=argv,
        cwd=run_dir,
        run_dir=run_dir,
        env={
            "PYTHONHASHSEED": "100",
            "AAAI_RISK14_SELECTION_SHA256": condition.selection_sha256,
        },
        dependencies=[METHOD_GATE_ID],
        required_markers=["protocol/adapters/risk14/PASS.json"],
        success_artifacts=[f"{relative}/artifact_manifest.json"],
        gpu_hours_low=0.1,
        gpu_hours_high=1.0,
        estimated_output_gib=0.25,
        seed=100,
        dataset=dataset,
        arm=arm,
        model="PreferGrow",
        config_sha256=contract.config_sha256,
        split_sha256=contract.split_sha256,
        bank_sha256=contract.bank_sha256,
        atomic_group=f"RISK-14.{condition.rank}.{dataset}.c{condition.corruption_level}",
        priority=20,
    )


def _sasrec_reuse_task(
    inputs: FrozenContinuationInputs,
    dataset: str,
) -> dict[str, Any]:
    contract = inputs.datasets[dataset]
    task_id = f"continuation.RISK-10.SASRec.{dataset}.reuse_audit"
    relative = _run_rel(task_id)
    run_dir = f"{inputs.queue_root}/{relative}"
    return _base_task(
        inputs,
        task_id=task_id,
        ledger_id="RISK-10",
        kind="contract_gate",
        argv=[
            inputs.python_executable,
            f"{inputs.source_root}/scripts/audit_e05_sasrec_reuse.py",
            "--e5-root",
            inputs.e5_root,
            "--dataset",
            dataset,
            "--output-dir",
            run_dir,
        ],
        cwd=inputs.source_root,
        run_dir=run_dir,
        env={"PYTHONHASHSEED": "100"},
        dependencies=[METHOD_GATE_ID],
        required_markers=["protocol/adapters/sasrec/PASS.json"],
        success_artifacts=[f"{relative}/reuse_audit.json"],
        gpu_hours_low=0.0,
        gpu_hours_high=0.0,
        estimated_output_gib=0.001,
        seed=None,
        dataset=dataset,
        arm="reuse_audit",
        model="SASRec",
        config_sha256=contract.config_sha256,
        split_sha256=contract.split_sha256,
        bank_sha256=None,
        atomic_group="RISK-10.SASRec.four-domain",
        priority=30,
    )


def _guarded_baseline_task(
    inputs: FrozenContinuationInputs,
    *,
    model: str,
    ledger_id: str,
    dataset: str,
    priority: int,
) -> dict[str, Any]:
    contract = inputs.datasets[dataset]
    task_id = f"continuation.{ledger_id}.{model}.{dataset}.seed100"
    relative = _run_rel(task_id)
    run_dir = f"{inputs.queue_root}/{relative}"
    high = 9.0 if model == "DiffRec" else 3.0
    return _base_task(
        inputs,
        task_id=task_id,
        ledger_id=ledger_id,
        kind="gpu",
        argv=[
            inputs.python_executable,
            f"{inputs.source_root}/scripts/run_{model.casefold()}_common_protocol.py",
            "--dataset",
            dataset,
            "--seed",
            "100",
            "--run-dir",
            run_dir,
        ],
        cwd=run_dir,
        run_dir=run_dir,
        env={"PYTHONHASHSEED": "100"},
        dependencies=[METHOD_GATE_ID],
        required_markers=[f"protocol/adapters/{model.casefold()}/PASS.json"],
        success_artifacts=[f"{relative}/artifact_manifest.json"],
        gpu_hours_low=1.0,
        gpu_hours_high=high,
        estimated_output_gib=0.5,
        seed=100,
        dataset=dataset,
        arm="author_default",
        model=model,
        config_sha256=contract.config_sha256,
        split_sha256=contract.split_sha256,
        bank_sha256=None,
        atomic_group=f"{ledger_id}.{model}.four-domain",
        priority=priority,
    )


def build_continuation_manifest(
    inputs: FrozenContinuationInputs,
) -> dict[str, Any]:
    if set(inputs.datasets) != set(DOMAINS):
        raise ValueError("continuation manifest requires exactly four domains")
    conditions = (inputs.high_risk_condition, inputs.low_risk_condition)
    if {condition.rank for condition in conditions} != {"high_risk", "low_risk"}:
        raise ValueError("RISK-14 conditions must be high_risk and low_risk")
    if any(condition.dataset not in DOMAINS for condition in conditions):
        raise ValueError("RISK-14 condition dataset is outside four-domain contract")
    tasks: list[dict[str, Any]] = [_method_gate(inputs)]
    for dataset in DOMAINS:
        for arm in ("host", "risk_gated_full"):
            tasks.append(_risk13_task(inputs, dataset, arm))
    for condition in conditions:
        for arm in RISK14_ARMS:
            tasks.append(_risk14_task(inputs, condition, arm))
    for dataset in DOMAINS:
        tasks.append(_sasrec_reuse_task(inputs, dataset))
    for model, priority in (("Caser", 31), ("GRURec", 32)):
        for dataset in DOMAINS:
            tasks.append(
                _guarded_baseline_task(
                    inputs,
                    model=model,
                    ledger_id="RISK-10",
                    dataset=dataset,
                    priority=priority,
                )
            )
    for dataset in DOMAINS:
        tasks.append(
            _guarded_baseline_task(
                inputs,
                model="DiffRec",
                ledger_id="RISK-11",
                dataset=dataset,
                priority=40,
            )
        )
    manifest = {
        "schema_version": 1,
        "queue_id": inputs.queue_id,
        "created_at": inputs.created_at,
        "run_root": inputs.queue_root,
        "source_root": inputs.source_root,
        "source_manifest_sha256": inputs.source_manifest_sha256,
        "ledger_path": inputs.ledger_path,
        "ledger_sha256": inputs.ledger_sha256,
        "gpu_ids": list(inputs.gpu_ids),
        "gpu_budget_hours": 168.0,
        "min_free_disk_gib": 40.0,
        "tasks": tasks,
    }
    validate_manifest(QueueManifest.from_dict(manifest))
    return manifest
