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
    if manifest.gpu_ids != (0, 1):
        raise ManifestError("queue must expose exactly GPU 0 and GPU 1")
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
    _validate_pilot_matrix(manifest.tasks)
    _validate_baseline_groups(manifest.tasks)
