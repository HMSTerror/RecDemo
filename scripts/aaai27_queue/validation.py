from __future__ import annotations

import posixpath
import re
from collections import defaultdict
from pathlib import PurePosixPath

from . import SCHEMA_VERSION
from .models import QueueManifest, TaskSpec


ALLOWED_LEDGER_IDS = {f"RISK-{index:02d}" for index in range(1, 15)}
ALLOWED_PHASES = {"preflight", "front_gate", "pilot", "decision", "continuation"}
ALLOWED_BRANCHES = {"common", "e1_pass", "e1_fail_audit", "method_pass"}
ALLOWED_KINDS = {"cpu", "gpu", "contract_gate"}
FOUR_DOMAINS = {"Steam", "ML1M", "Beauty", "ATG"}
CLASSIC_MODELS = {"SASRec", "Caser", "GRURec"}
RISK14_ARMS = {"host", "text_anchor_only", "global_p", "dataset_gate_only", "full", "u_shuffle"}
DESTRUCTIVE_TOKENS = {
    "--force",
    "--no-skip-existing",
    "rm",
    "rmdir",
    "remove-item",
    "del",
    "git-reset",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REVISION_RE = re.compile(r"^[0-9a-f]{7,64}$")


class ManifestError(ValueError):
    """Raised when a queue definition is unsafe or scientifically invalid."""


def _normalized_posix(path: str) -> PurePosixPath:
    if not isinstance(path, str) or not path.startswith("/"):
        raise ManifestError(f"path must be absolute POSIX: {path!r}")
    return PurePosixPath(posixpath.normpath(path))


def _inside(path: str, root: str) -> bool:
    candidate = _normalized_posix(path)
    parent = _normalized_posix(root)
    return candidate == parent or parent in candidate.parents


def _require_sha256(value: str | None, label: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ManifestError(f"{label} must be lowercase SHA-256")


def _validate_relative_artifact(path: str, task_id: str) -> None:
    relative = PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts or str(relative) in {"", "."}:
        raise ManifestError(f"{task_id}: success artifact must be a safe relative path")


def _validate_task(task: TaskSpec, manifest: QueueManifest) -> None:
    if task.schema_version != SCHEMA_VERSION:
        raise ManifestError(f"{task.task_id}: unsupported schema_version")
    if task.ledger_id not in ALLOWED_LEDGER_IDS or task.ledger_id == "RISK-12":
        raise ManifestError(f"{task.task_id}: RISK-12 and unknown ledger rows are disabled")
    if task.phase not in ALLOWED_PHASES or task.branch not in ALLOWED_BRANCHES:
        raise ManifestError(f"{task.task_id}: invalid phase or branch")
    if task.kind not in ALLOWED_KINDS:
        raise ManifestError(f"{task.task_id}: invalid task kind")
    if task.seed not in (None, 100):
        raise ManifestError(f"{task.task_id}: only seed 100 is permitted")
    if task.kind == "gpu" and task.seed != 100:
        raise ManifestError(f"{task.task_id}: GPU tasks require seed 100")
    if task.kind == "gpu" and _normalized_posix(task.cwd) != _normalized_posix(
        task.run_dir
    ):
        raise ManifestError(f"{task.task_id}: GPU task cwd must equal run_dir")
    model_name = (task.model or "").casefold()
    if model_name == "diffurec":
        raise ManifestError(f"{task.task_id}: DiffuRec is excluded")
    if model_name == "bert4rec":
        raise ManifestError(f"{task.task_id}: BERT4Rec is excluded")
    if task.max_attempts != 1:
        raise ManifestError(f"{task.task_id}: max_attempts must equal 1")
    if task.failure_policy != "fail_closed":
        raise ManifestError(f"{task.task_id}: failure policy must be fail_closed")
    if task.gpu_slots not in (0, 1) or (task.kind == "gpu") != (task.gpu_slots == 1):
        raise ManifestError(f"{task.task_id}: invalid gpu_slots for task kind")
    if not task.argv or any(not isinstance(item, str) or not item for item in task.argv):
        raise ManifestError(f"{task.task_id}: argv must be a nonempty string array")
    if any(
        item.lstrip("+").casefold().startswith("training.startup_probe_only=")
        for item in task.argv
    ):
        raise ManifestError(
            f"{task.task_id}: startup probe override is forbidden in scientific queue tasks"
        )
    hydra_work_dirs = [
        item.split("=", 1)[1]
        for item in task.argv
        if item.startswith("work_dir=")
    ]
    if hydra_work_dirs and (
        len(hydra_work_dirs) != 1 or hydra_work_dirs[0] != task.run_dir
    ):
        raise ManifestError(
            f"{task.task_id}: Hydra work_dir must equal task run_dir"
        )
    lowered = {item.strip().casefold() for item in task.argv}
    destructive = lowered & DESTRUCTIVE_TOKENS
    destructive.update(item for item in lowered if item.startswith("--force=") or item.startswith("--no-skip-existing="))
    if destructive:
        raise ManifestError(f"{task.task_id}: destructive argv token")
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in task.env.items()):
        raise ManifestError(f"{task.task_id}: env must map strings to strings")
    if {key.casefold() for key in task.env} & {"force", "skip_existing"}:
        raise ManifestError(f"{task.task_id}: overwrite environment is forbidden")
    if not _inside(task.run_dir, manifest.run_root):
        raise ManifestError(f"{task.task_id}: run_dir leaves queue root")
    if task.phase == "pilot":
        if len(task.argv) < 2:
            raise ManifestError(f"{task.task_id}: pilot argv lacks source entry")
        _normalized_posix(task.argv[0])
        if not _inside(task.argv[1], manifest.source_root):
            raise ManifestError(
                f"{task.task_id}: pilot source entry must be absolute and inside source_root"
            )
    if not _inside(task.cwd, manifest.source_root) and not _inside(task.cwd, manifest.run_root):
        raise ManifestError(f"{task.task_id}: cwd is outside source and queue roots")
    if task.gpu_hours_low < 0 or task.gpu_hours_high < task.gpu_hours_low:
        raise ManifestError(f"{task.task_id}: invalid GPU-hour estimate")
    if task.estimated_output_gib < 0 or task.priority < 0:
        raise ManifestError(f"{task.task_id}: invalid output or priority value")
    if REVISION_RE.fullmatch(task.code_revision) is None:
        raise ManifestError(f"{task.task_id}: invalid code revision")
    _require_sha256(task.config_sha256, f"{task.task_id} config_sha256")
    _require_sha256(task.split_sha256, f"{task.task_id} split_sha256", optional=True)
    _require_sha256(task.bank_sha256, f"{task.task_id} bank_sha256", optional=True)
    if not task.success_artifacts:
        raise ManifestError(f"{task.task_id}: success_artifacts cannot be empty")
    for artifact in task.success_artifacts:
        _validate_relative_artifact(artifact, task.task_id)


def _expected_pilot(branch: str, include_full: bool) -> set[tuple[str, str]]:
    expected: set[tuple[str, str]] = set()
    for dataset in ("Beauty", "Steam"):
        expected.add((dataset, "host"))
        for level in (0, 60, 100):
            expected.add((dataset, f"text_anchor_only_c{level}"))
            if include_full:
                expected.add((dataset, f"risk_gated_full_c{level}"))
    return expected


def _validate_pilot_matrix(tasks: tuple[TaskSpec, ...]) -> None:
    for branch, include_full in (("e1_pass", True), ("e1_fail_audit", False)):
        selected = [task for task in tasks if task.phase == "pilot" and task.branch == branch]
        actual = [(task.dataset or "", task.arm or "") for task in selected]
        expected = _expected_pilot(branch, include_full)
        if len(actual) != len(expected) or set(actual) != expected:
            raise ManifestError(f"{branch}: pilot matrix differs from frozen {len(expected)}-run design")
        for task in selected:
            expected_ledger = "RISK-06" if task.dataset == "Beauty" else "RISK-07"
            if task.ledger_id != expected_ledger:
                raise ManifestError(f"{task.task_id}: pilot ledger mismatch")
            graph_types = [
                token
                for token in task.argv
                if token.startswith("graph.type=")
            ]
            expected_graph_type = (
                "graph.type=adaptive"
                if task.arm == "host"
                else "graph.type=proposal_adaptive"
            )
            if graph_types != [expected_graph_type]:
                identity = (
                    "AdaptiveWise learned-proposal host"
                    if task.arm == "host"
                    else "ProposalAdaptiveWise evidence arm"
                )
                raise ManifestError(
                    f"{task.task_id}: pilot must use the {identity}"
                )
            summary_name = (
                "best_summary_adaptive.json"
                if task.arm == "host"
                else "best_summary_proposal_adaptive.json"
            )
            summary_suffix = (
                f"/checkpoints-meta/{task.dataset}/{summary_name}"
            )
            if (
                len(task.success_artifacts) != 2
                or not task.success_artifacts[0].endswith(summary_suffix)
                or not task.success_artifacts[1].endswith(
                    "/artifact_manifest.json"
                )
            ):
                raise ManifestError(
                    f"{task.task_id}: pilot success artifacts must be the "
                    f"selected {summary_name} and artifact_manifest.json"
                )


def _validate_baseline_groups(tasks: tuple[TaskSpec, ...]) -> None:
    grouped: dict[tuple[str, str], list[TaskSpec]] = defaultdict(list)
    for task in tasks:
        if task.ledger_id == "RISK-10" and task.model in CLASSIC_MODELS:
            grouped[(task.ledger_id, task.model)].append(task)
        if task.ledger_id == "RISK-11" and task.model == "DiffRec":
            grouped[(task.ledger_id, task.model)].append(task)
    for (_, model), members in grouped.items():
        datasets = {task.dataset or "" for task in members}
        if len(members) != 4 or datasets != FOUR_DOMAINS:
            raise ManifestError(f"{model}: baseline group must contain all four domains")
        groups = {task.atomic_group for task in members}
        if None in groups or len(groups) != 1:
            raise ManifestError(f"{model}: baseline group requires one atomic_group")


def _validate_continuation_matrix(tasks: tuple[TaskSpec, ...]) -> None:
    continuation = [task for task in tasks if task.phase == "continuation"]
    if not continuation:
        return
    if any(task.branch != "method_pass" for task in continuation):
        raise ManifestError("continuation tasks must use method_pass branch")

    gate_tasks = [
        task
        for task in continuation
        if task.task_id == "continuation.method_pass_gate" and task.kind == "contract_gate"
    ]
    if len(gate_tasks) != 1:
        raise ManifestError("continuation requires exactly one method-pass contract gate")
    gate_id = gate_tasks[0].task_id
    gpu_continuation = [task for task in continuation if task.kind == "gpu"]
    if any(gate_id not in task.dependencies for task in gpu_continuation):
        raise ManifestError("every continuation GPU task must depend on method-pass contract gate")

    r13 = [task for task in continuation if task.ledger_id == "RISK-13"]
    expected_r13 = {(dataset, arm) for dataset in FOUR_DOMAINS for arm in ("host", "risk_gated_full")}
    actual_r13 = {(task.dataset or "", task.arm or "") for task in r13}
    if len(r13) != 8 or actual_r13 != expected_r13:
        raise ManifestError("RISK-13 continuation matrix must contain eight host/full four-domain tasks")
    if any(task.model != "PreferGrow" for task in r13):
        raise ManifestError("RISK-13 continuation model must be PreferGrow")

    r14 = [task for task in continuation if task.ledger_id == "RISK-14"]
    if len(r14) != 12:
        raise ManifestError("RISK-14 continuation matrix must contain twelve controls")
    rank_arm_pairs: set[tuple[str, str]] = set()
    for task in r14:
        parts = task.task_id.split(".")
        if len(parts) < 6 or parts[2] not in {"high_risk", "low_risk"} or parts[5] not in RISK14_ARMS:
            raise ManifestError(f"{task.task_id}: malformed RISK-14 condition/control identity")
        rank_arm_pairs.add((parts[2], parts[5]))
        if task.model != "PreferGrow" or task.dataset not in FOUR_DOMAINS:
            raise ManifestError(f"{task.task_id}: RISK-14 identity mismatch")
    if rank_arm_pairs != {(rank, arm) for rank in ("high_risk", "low_risk") for arm in RISK14_ARMS}:
        raise ManifestError("RISK-14 must contain all six arms for high- and low-risk selections")

    r10 = [task for task in continuation if task.ledger_id == "RISK-10"]
    if len(r10) != 12 or {(task.model, task.dataset) for task in r10} != {
        (model, dataset) for model in CLASSIC_MODELS for dataset in FOUR_DOMAINS
    }:
        raise ManifestError("RISK-10 continuation matrix must contain SASRec/Caser/GRURec on all four domains")

    r11 = [task for task in continuation if task.ledger_id == "RISK-11"]
    if r11 and (len(r11) != 4 or {task.dataset for task in r11} != FOUR_DOMAINS or any(task.model != "DiffRec" for task in r11)):
        raise ManifestError("RISK-11 continuation must be an all-four DiffRec group")

    allowed = {"RISK-08", "RISK-10", "RISK-11", "RISK-13", "RISK-14"}
    unexpected = [task.task_id for task in continuation if task.ledger_id not in allowed]
    if unexpected:
        raise ManifestError(f"unexpected continuation ledger IDs: {unexpected}")


def _validate_dependencies(tasks: tuple[TaskSpec, ...]) -> None:
    graph = {task.task_id: set(task.dependencies) for task in tasks}
    known = set(graph)
    for task_id, dependencies in graph.items():
        missing = sorted(dependencies - known)
        if missing:
            raise ManifestError(f"{task_id}: unknown dependencies {missing}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visiting:
            raise ManifestError(f"dependency cycle involving {task_id}")
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in graph[task_id]:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in graph:
        visit(task_id)


def validate_manifest(manifest: QueueManifest) -> None:
    if manifest.schema_version != SCHEMA_VERSION:
        raise ManifestError("unsupported queue schema_version")
    if (
        not manifest.gpu_ids
        or len(manifest.gpu_ids) != len(set(manifest.gpu_ids))
        or any(type(gpu_id) is not int or gpu_id < 0 for gpu_id in manifest.gpu_ids)
    ):
        raise ManifestError(
            "queue gpu_ids must be a nonempty unique nonnegative integer allowlist"
        )
    if manifest.gpu_budget_hours != 168.0:
        raise ManifestError("queue must freeze exactly 168 GPU-hours")
    if manifest.min_free_disk_gib != 40.0:
        raise ManifestError("queue must freeze exactly 40 GiB")
    if not manifest.queue_id or not _inside(manifest.source_root, manifest.source_root):
        raise ManifestError("queue identity or source root is invalid")
    _normalized_posix(manifest.run_root)
    _require_sha256(manifest.source_manifest_sha256, "source_manifest_sha256")
    _require_sha256(manifest.ledger_sha256, "ledger_sha256")

    task_ids = [task.task_id for task in manifest.tasks]
    if len(task_ids) != len(set(task_ids)):
        raise ManifestError("duplicate task_id")
    for task in manifest.tasks:
        _validate_task(task, manifest)

    _validate_dependencies(manifest.tasks)
    if any(task.phase == "pilot" for task in manifest.tasks):
        _validate_pilot_matrix(manifest.tasks)
    _validate_baseline_groups(manifest.tasks)
    _validate_continuation_matrix(manifest.tasks)
    high_forecast = sum(task.gpu_hours_high for task in manifest.tasks if task.gpu_slots == 1)
    if high_forecast > manifest.gpu_budget_hours:
        raise ManifestError(f"GPU-hour high forecast exceeds {manifest.gpu_budget_hours:g}: {high_forecast:g}")
