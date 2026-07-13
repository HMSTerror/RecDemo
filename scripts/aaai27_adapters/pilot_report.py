from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.aaai27_queue.models import QueueManifest
from scripts.aaai27_queue.validation import ManifestError, validate_manifest

from .common import atomic_write_json, sha256_file, stable_sha256
from .pilot_task_wrapper import (
    PilotWrapperError,
    _metric_at_10,
    _validate_selected_summary,
)
from .risk04_08 import (
    DATASETS,
    PILOT_LEVELS,
    QueueSafetyError,
    _load_object,
    _payload_hash,
    _resolve_below,
    _validate_artifact_manifest,
    _validate_e1_marker,
    run_risk08_decision,
)


class PilotReportError(RuntimeError):
    """Raised when the frozen r7 pilot evidence cannot be replayed safely."""


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PilotReportError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise PilotReportError(f"{label} must be finite")
    return result


def _rankdata(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        average_rank = ((cursor + 1) + end) / 2.0
        for position in range(cursor, end):
            ranks[order[position]] = average_rank
        cursor = end
    return ranks


def _spearman(values_x: Sequence[float], values_y: Sequence[float]) -> float | None:
    if len(values_x) != len(values_y) or len(values_x) < 2:
        raise PilotReportError("Spearman inputs must have equal length of at least two")
    ranks_x = _rankdata(values_x)
    ranks_y = _rankdata(values_y)
    mean_x = sum(ranks_x) / len(ranks_x)
    mean_y = sum(ranks_y) / len(ranks_y)
    centered_x = [value - mean_x for value in ranks_x]
    centered_y = [value - mean_y for value in ranks_y]
    denominator = math.sqrt(
        sum(value * value for value in centered_x)
        * sum(value * value for value in centered_y)
    )
    if denominator == 0.0:
        return None
    return sum(x * y for x, y in zip(centered_x, centered_y)) / denominator


def _validated_risk05(
    risk05_root: Path,
    *,
    e1_marker_path: Path,
    risk_preflight_path: Path,
) -> tuple[dict[str, Any], str, dict[str, Any], str]:
    risk05_root = Path(risk05_root)
    metadata = _load_object(risk05_root / "risk05_bundle.json", "RISK-05 bundle")
    if (
        metadata.get("artifact_sha256") != _payload_hash(metadata)
        or metadata.get("pilot_authorized") is not True
    ):
        raise PilotReportError("RISK-05 bundle is not an authorized immutable pilot freeze")
    marker_relative = metadata.get("risk05_marker")
    if not isinstance(marker_relative, str) or not marker_relative:
        raise PilotReportError("RISK-05 bundle does not identify its terminal marker")
    marker_path = risk05_root / marker_relative
    marker = _load_object(marker_path, "RISK-05 marker")
    if marker.get("outcome") != "pass" or marker.get("artifact_sha256") != _payload_hash(
        marker
    ):
        raise PilotReportError("RISK-05 terminal marker is not a valid pass")
    prereg_path = risk05_root / "protocol" / "risk05_preregistration.json"
    prereg = _load_object(prereg_path, "RISK-05 preregistration")
    prereg_hash = stable_sha256(prereg)
    if (
        metadata.get("risk05_preregistration_sha256") != prereg_hash
        or marker.get("preregistration_sha256") != prereg_hash
    ):
        raise PilotReportError("RISK-05 preregistration hash mismatch")
    e1_hash = sha256_file(e1_marker_path)
    if (
        metadata.get("e1_marker_sha256") != e1_hash
        or marker.get("e1_marker_sha256") != e1_hash
        or prereg.get("bindings", {}).get("e1_marker_sha256") != e1_hash
    ):
        raise PilotReportError("RISK-05/E1 marker binding mismatch")
    risk_preflight_path = Path(risk_preflight_path)
    expected_preflight_hash = prereg.get("bindings", {}).get(
        "preflight_report_sha256"
    )
    if (
        not risk_preflight_path.is_file()
        or not isinstance(expected_preflight_hash, str)
        or sha256_file(risk_preflight_path) != expected_preflight_hash
    ):
        raise PilotReportError("RISK-03 preflight file hash does not match RISK-05")
    preflight = _load_object(risk_preflight_path, "RISK-03 preflight")
    if (
        preflight.get("artifact_sha256") != _payload_hash(preflight)
        or preflight.get("protocol", {}).get("split") != "train-only"
    ):
        raise PilotReportError("RISK-03 preflight identity or train-only scope mismatch")
    return prereg, prereg_hash, preflight, sha256_file(prereg_path)


def _frozen_inputs(
    prereg: Mapping[str, Any], preflight: Mapping[str, Any]
) -> tuple[dict[str, dict[int, float]], dict[str, dict[int, float]], dict[str, float]]:
    protocol = prereg.get("frozen_protocol")
    thresholds = prereg.get("frozen_thresholds")
    phi_rows = prereg.get("phi_R")
    if not isinstance(protocol, Mapping) or not isinstance(thresholds, Mapping):
        raise PilotReportError("RISK-05 lacks its frozen protocol or thresholds")
    if protocol.get("primary_statistic") != "EPE":
        raise PilotReportError("RISK-05 primary statistic is not frozen EPE")
    if protocol.get("pilot_levels") != list(PILOT_LEVELS):
        raise PilotReportError("RISK-05 pilot levels differ from 0/60/100")
    if protocol.get("arm_count", {}).get("e1_pass") != 14:
        raise PilotReportError("RISK-05 E1-pass arm count is not fourteen")
    if protocol.get("no_rescue") is not True or protocol.get("no_second_seed") is not True:
        raise PilotReportError("RISK-05 no-rescue/no-second-seed freeze is absent")
    threshold_values = {
        "spearman_rho_max": _finite_number(
            thresholds.get("spearman_rho_max"), "spearman_rho_max"
        ),
        "adjacent_ndcg10_reversal_tolerance": _finite_number(
            thresholds.get("adjacent_ndcg10_reversal_tolerance"),
            "adjacent_ndcg10_reversal_tolerance",
        ),
        "worst_delta_improvement": _finite_number(
            thresholds.get("worst_delta_improvement"),
            "worst_delta_improvement",
        ),
    }
    if not isinstance(phi_rows, Mapping) or set(phi_rows) != set(DATASETS):
        raise PilotReportError("RISK-05 phi_R map does not contain Beauty and Steam")
    if set(preflight.get("datasets", {})) != set(DATASETS):
        raise PilotReportError("RISK-03 preflight does not contain Beauty and Steam")
    epe: dict[str, dict[int, float]] = {}
    phi: dict[str, dict[int, float]] = {}
    prereg_sources = prereg.get("source_hashes")
    if not isinstance(prereg_sources, Mapping):
        raise PilotReportError("RISK-05 preregistration lacks source hashes")
    for dataset in DATASETS:
        dataset_preflight = preflight["datasets"][dataset]
        levels = dataset_preflight.get("levels")
        if not isinstance(levels, list):
            raise PilotReportError(f"RISK-03 preflight lacks level rows for {dataset}")
        indexed = {
            int(row.get("level", -1)): row
            for row in levels
            if isinstance(row, Mapping)
        }
        source_banks = dataset_preflight.get("source_hashes", {}).get("banks")
        frozen_banks = prereg_sources.get(dataset, {}).get("banks")
        if not isinstance(source_banks, Mapping) or not isinstance(
            frozen_banks, Mapping
        ):
            raise PilotReportError(f"frozen bank hashes are missing for {dataset}")
        epe[dataset] = {}
        phi[dataset] = {}
        for level in PILOT_LEVELS:
            if level not in indexed:
                raise PilotReportError(f"RISK-03 preflight lacks {dataset} c{level}")
            source_bank = str(source_banks.get(str(level), ""))
            frozen_bank = str(frozen_banks.get(str(level), ""))
            if not source_bank or source_bank != frozen_bank:
                raise PilotReportError(
                    f"RISK-03/RISK-05 bank hash mismatch for {dataset} c{level}"
                )
            epe[dataset][level] = _finite_number(
                indexed[level].get("epe"), f"{dataset} c{level} EPE"
            )
            phi_value = _finite_number(
                phi_rows.get(dataset, {}).get(str(level)),
                f"{dataset} c{level} phi_R",
            )
            if not 0.0 <= phi_value <= 1.0:
                raise PilotReportError(f"{dataset} c{level} phi_R is outside [0,1]")
            phi[dataset][level] = phi_value
    return epe, phi, threshold_values


def _selected_metrics(summary: Mapping[str, Any]) -> dict[str, int | float]:
    return {
        "best_step": int(summary["best_step"]),
        "validation_hr10": _metric_at_10(summary, "validation", "hr"),
        "validation_ndcg10": _metric_at_10(summary, "validation", "ndcg"),
        "test_hr10": _metric_at_10(summary, "test", "hr"),
        "test_ndcg10": _metric_at_10(summary, "test", "ndcg"),
    }


def _same_selected_metrics(
    artifact_metrics: Any, summary_metrics: Mapping[str, int | float], task_id: str
) -> None:
    if not isinstance(artifact_metrics, Mapping) or set(artifact_metrics) != set(
        summary_metrics
    ):
        raise PilotReportError(f"selected-metric schema mismatch for {task_id}")
    for key, expected in summary_metrics.items():
        observed = artifact_metrics.get(key)
        if key == "best_step":
            if isinstance(observed, bool) or observed != expected:
                raise PilotReportError(f"selected best_step mismatch for {task_id}")
            continue
        if _finite_number(observed, f"{task_id} {key}") != expected:
            raise PilotReportError(f"selected metric mismatch for {task_id}: {key}")


def _kernel_identity(task: Mapping[str, Any]) -> str:
    argv = task.get("argv")
    if not isinstance(argv, list):
        raise PilotReportError(f"task argv is missing: {task.get('task_id')}")
    if task.get("arm") == "host":
        if argv.count("graph.type=adaptive") != 1:
            raise PilotReportError(f"host is not learned AdaptiveWise: {task.get('task_id')}")
        return "learned_adaptive_v2_host"
    versions = [
        token.split("=", 1)[1]
        for token in argv
        if isinstance(token, str) and token.startswith("text_side.kernel_version=")
    ]
    if versions != ["v2"]:
        raise PilotReportError(f"evidence arm is not bound to kernel v2: {task.get('task_id')}")
    return "v2"


def _result_key(task: Mapping[str, Any]) -> tuple[str, int | None]:
    arm = str(task.get("arm", ""))
    if arm == "host":
        return "host", None
    try:
        level = int(arm.rsplit("c", 1)[1])
    except (IndexError, ValueError) as exc:
        raise PilotReportError(f"unrecognized pilot arm: {arm}") from exc
    if arm.startswith("text_anchor_only_c"):
        return f"anchor_c{level}", level
    if arm.startswith("risk_gated_full_c"):
        return f"full_c{level}", level
    raise PilotReportError(f"unrecognized pilot arm: {arm}")


def _full_predictions(
    results: Mapping[str, Any], phi: Mapping[str, Mapping[int, float]]
) -> dict[str, Any]:
    points: list[dict[str, Any]] = []
    for dataset in DATASETS:
        for level in PILOT_LEVELS:
            scale = phi[dataset][level]
            delta = results[dataset][f"full_c{level}"]["host_relative_deltas"][
                "test_ndcg10"
            ]
            if scale >= 0.5:
                rule = "delta_test_ndcg10 > 0"
                passed = delta > 0.0
            elif scale > 0.0:
                rule = "abs(delta_test_ndcg10) < 0.01"
                passed = abs(delta) < 0.01
            else:
                rule = "abs(delta_test_ndcg10) < 0.01"
                passed = abs(delta) < 0.01
            points.append(
                {
                    "dataset": dataset,
                    "level": level,
                    "phi_R": scale,
                    "rule": rule,
                    "test_delta_ndcg10": delta,
                    "passed": bool(passed),
                }
            )
    return {"passed": all(point["passed"] for point in points), "points": points}


def _anchor_ordering(
    results: Mapping[str, Any],
    epe: Mapping[str, Mapping[int, float]],
    tolerance: float,
) -> dict[str, Any]:
    datasets: dict[str, Any] = {}
    for dataset in DATASETS:
        ordered_levels = sorted(PILOT_LEVELS, key=lambda level: epe[dataset][level], reverse=True)
        adjacent: list[dict[str, Any]] = []
        for higher_epe_level, lower_epe_level in zip(
            ordered_levels, ordered_levels[1:]
        ):
            higher_delta = results[dataset][f"anchor_c{higher_epe_level}"][
                "host_relative_deltas"
            ]["test_ndcg10"]
            lower_delta = results[dataset][f"anchor_c{lower_epe_level}"][
                "host_relative_deltas"
            ]["test_ndcg10"]
            reversal = max(0.0, higher_delta - lower_delta)
            adjacent.append(
                {
                    "higher_epe_level": higher_epe_level,
                    "lower_epe_level": lower_epe_level,
                    "higher_epe": epe[dataset][higher_epe_level],
                    "lower_epe": epe[dataset][lower_epe_level],
                    "higher_epe_anchor_delta": higher_delta,
                    "lower_epe_anchor_delta": lower_delta,
                    "opposite_reversal": reversal,
                    "tolerance": tolerance,
                    "passed": reversal <= tolerance,
                }
            )
        datasets[dataset] = {
            "ordered_levels_by_descending_epe": ordered_levels,
            "adjacent_checks": adjacent,
            "passed": all(row["passed"] for row in adjacent),
        }
    return {
        "passed": any(row["passed"] for row in datasets.values()),
        "required_dataset_count": 1,
        "datasets": datasets,
    }


def _association(
    results: Mapping[str, Any],
    epe: Mapping[str, Mapping[int, float]],
    threshold: float,
) -> dict[str, Any]:
    points: list[dict[str, Any]] = []
    for dataset in DATASETS:
        for level in PILOT_LEVELS:
            points.append(
                {
                    "dataset": dataset,
                    "level": level,
                    "epe": epe[dataset][level],
                    "anchor_test_delta_ndcg10": results[dataset][
                        f"anchor_c{level}"
                    ]["host_relative_deltas"]["test_ndcg10"],
                }
            )
    rho = _spearman(
        [point["epe"] for point in points],
        [point["anchor_test_delta_ndcg10"] for point in points],
    )
    return {
        "point_count": len(points),
        "rho": rho,
        "threshold_max": threshold,
        "passed": rho is not None and rho <= threshold,
        "points": points,
        "interpretation": "descriptive six-point association; not a significance test",
    }


def _worst_anchor_improvement(
    results: Mapping[str, Any], threshold: float
) -> dict[str, Any]:
    points: list[tuple[float, str, int]] = []
    for dataset in DATASETS:
        for level in PILOT_LEVELS:
            delta = results[dataset][f"anchor_c{level}"]["host_relative_deltas"][
                "test_ndcg10"
            ]
            points.append((delta, dataset, level))
    anchor_delta, dataset, level = min(points, key=lambda row: row[0])
    full_delta = results[dataset][f"full_c{level}"]["host_relative_deltas"][
        "test_ndcg10"
    ]
    absolute_improvement = full_delta - anchor_delta
    passed_absolute = absolute_improvement >= threshold
    passed_halving = anchor_delta < 0.0 and abs(full_delta) <= abs(anchor_delta) / 2.0
    return {
        "dataset": dataset,
        "level": level,
        "anchor_test_delta_ndcg10": anchor_delta,
        "full_test_delta_ndcg10": full_delta,
        "absolute_improvement": absolute_improvement,
        "required_absolute_improvement": threshold,
        "negative_magnitude_ratio": (
            abs(full_delta) / abs(anchor_delta) if anchor_delta < 0.0 else None
        ),
        "passed_absolute_improvement": passed_absolute,
        "passed_negative_magnitude_halving": passed_halving,
        "passed": bool(passed_absolute or passed_halving),
    }


def build_artifact_derived_pilot_report(
    queue_root: Path,
    *,
    risk05_root: Path,
    risk_preflight_path: Path,
) -> dict[str, Any]:
    """Replay the frozen fourteen-task r7 contract from same-root artifacts."""

    queue_root = Path(queue_root).resolve()
    queue_manifest_path = queue_root / "queue" / "queue_seed100.json"
    try:
        manifest_raw = _load_object(queue_manifest_path, "r7 queue manifest")
        manifest = QueueManifest.from_dict(manifest_raw)
        validate_manifest(manifest)
    except (QueueSafetyError, ManifestError, ValueError) as exc:
        raise PilotReportError(f"r7 queue manifest validation failed: {exc}") from exc
    e1_candidates = [
        queue_root / "markers" / name
        for name in ("RISK-02_PASS.json", "RISK-02_FAIL.json")
        if (queue_root / "markers" / name).is_file()
    ]
    if len(e1_candidates) != 1:
        raise PilotReportError("r7 queue must contain exactly one terminal E1 marker")
    try:
        e1 = _validate_e1_marker(e1_candidates[0])
    except QueueSafetyError as exc:
        raise PilotReportError(f"E1 marker validation failed: {exc}") from exc
    if e1["outcome"] != "pass":
        raise PilotReportError("r7 fourteen-task report requires the terminal E1-pass branch")
    try:
        prereg, prereg_hash, preflight, prereg_file_hash = _validated_risk05(
            Path(risk05_root),
            e1_marker_path=e1_candidates[0],
            risk_preflight_path=Path(risk_preflight_path),
        )
    except (QueueSafetyError, OSError, ValueError) as exc:
        if isinstance(exc, PilotReportError):
            raise
        raise PilotReportError(f"frozen input validation failed: {exc}") from exc
    queue_prereg_path = queue_root / "protocol" / "risk05_preregistration.json"
    if (
        not queue_prereg_path.is_file()
        or stable_sha256(_load_object(queue_prereg_path, "queue RISK-05 preregistration"))
        != prereg_hash
    ):
        raise PilotReportError("queue-local RISK-05 preregistration does not match the freeze")
    epe, phi, thresholds = _frozen_inputs(prereg, preflight)
    active_tasks = [
        task.to_dict()
        for task in manifest.tasks
        if task.phase == "pilot" and task.branch == "e1_pass"
    ]
    if len(active_tasks) != 14:
        raise PilotReportError("r7 report requires exactly fourteen E1-pass pilot tasks")
    active_tasks.sort(key=lambda task: str(task["task_id"]))
    missing = [
        str(task["task_id"])
        for task in active_tasks
        if not (queue_root / str(task["success_artifacts"][1])).is_file()
    ]
    if missing:
        raise PilotReportError(
            "missing artifact manifests for frozen tasks: " + ", ".join(missing)
        )
    queue_hash = sha256_file(queue_manifest_path)
    frozen_protocol = prereg["frozen_protocol"]
    evaluator = str(frozen_protocol.get("evaluator_version", ""))
    selector = str(frozen_protocol.get("selector_version", ""))
    results: dict[str, dict[str, Any]] = {dataset: {} for dataset in DATASETS}
    artifact_paths: dict[str, str] = {}
    artifact_hashes: dict[str, str] = {}
    for task in active_tasks:
        task_id = str(task["task_id"])
        artifact_relative = str(task["success_artifacts"][1])
        artifact_path = _resolve_below(
            queue_root, artifact_relative, f"artifact path for {task_id}"
        )
        try:
            artifact_hashes[task_id] = _validate_artifact_manifest(
                queue_root, artifact_path, task, queue_hash
            )
        except (QueueSafetyError, OSError, ValueError) as exc:
            raise PilotReportError(
                f"artifact provenance validation failed for {task_id}: {exc}"
            ) from exc
        artifact = _load_object(artifact_path, f"artifact manifest for {task_id}")
        summary_path = _resolve_below(
            queue_root,
            str(task["success_artifacts"][0]),
            f"selected summary for {task_id}",
        )
        try:
            summary = _validate_selected_summary(summary_path)
            summary_metrics = _selected_metrics(summary)
        except (PilotWrapperError, OSError, ValueError) as exc:
            raise PilotReportError(
                f"selected summary validation failed for {task_id}: {exc}"
            ) from exc
        _same_selected_metrics(
            artifact.get("selected_metrics"), summary_metrics, task_id
        )
        if task.get("evaluator_version") != evaluator or task.get(
            "selector_version"
        ) != selector:
            raise PilotReportError(f"selector/evaluator mismatch for {task_id}")
        result_key, level = _result_key(task)
        row: dict[str, Any] = {
            "task_id": task_id,
            "artifact_manifest": artifact_relative,
            "artifact_manifest_sha256": artifact_hashes[task_id],
            "selected_summary": str(task["success_artifacts"][0]),
            "selected_summary_sha256": sha256_file(summary_path),
            "selected_metrics": summary_metrics,
            "kernel_version": _kernel_identity(task),
            "bank_sha256": task.get("bank_sha256"),
        }
        if level is not None:
            dataset = str(task["dataset"])
            if task.get("bank_sha256") != prereg["source_hashes"][dataset][
                "banks"
            ][str(level)]:
                raise PilotReportError(f"task bank differs from RISK-05: {task_id}")
            if task.get("env", {}).get("AAAI_RISK05_PREREG_SHA256") != prereg_hash:
                raise PilotReportError(f"task preregistration hash mismatch: {task_id}")
            gate = _finite_number(
                artifact.get("gate_dataset_scale"), f"{task_id} gate scale"
            )
            expected_gate = 1.0 if result_key.startswith("anchor_") else phi[dataset][level]
            if gate != expected_gate:
                raise PilotReportError(f"task gate scale mismatch: {task_id}")
            row.update({"level": level, "epe": epe[dataset][level], "phi_R": phi[dataset][level]})
        dataset = str(task["dataset"])
        if result_key in results[dataset]:
            raise PilotReportError(f"duplicate result arm: {dataset} {result_key}")
        results[dataset][result_key] = row
        artifact_paths[task_id] = artifact_relative
    for dataset in DATASETS:
        expected_keys = {"host"} | {
            f"{kind}_c{level}"
            for kind in ("anchor", "full")
            for level in PILOT_LEVELS
        }
        if set(results[dataset]) != expected_keys:
            raise PilotReportError(f"incomplete result matrix for {dataset}")
        host_metrics = results[dataset]["host"]["selected_metrics"]
        for key, row in results[dataset].items():
            if key == "host":
                continue
            row["host_relative_deltas"] = {
                metric: row["selected_metrics"][metric] - host_metrics[metric]
                for metric in (
                    "validation_hr10",
                    "validation_ndcg10",
                    "test_hr10",
                    "test_ndcg10",
                )
            }
    full_predictions = _full_predictions(results, phi)
    anchor_ordering = _anchor_ordering(
        results,
        epe,
        thresholds["adjacent_ndcg10_reversal_tolerance"],
    )
    association = _association(
        results, epe, thresholds["spearman_rho_max"]
    )
    worst = _worst_anchor_improvement(
        results, thresholds["worst_delta_improvement"]
    )
    checks = {
        "artifact_task_ids": sorted(artifact_paths),
        "provenance": {
            "passed": True,
            "queue_manifest_sha256": queue_hash,
            "risk05_preregistration_sha256": prereg_hash,
            "risk_preflight_sha256": sha256_file(risk_preflight_path),
            "artifact_manifest_sha256": artifact_hashes,
            "evaluator_version": evaluator,
            "selector_version": selector,
            "evidence_kernel_version": "v2",
        },
        "full_predictions": full_predictions,
        "anchor_response_ordering": anchor_ordering,
        "spearman_association": association,
        "worst_anchor_improvement": worst,
    }
    failure_reasons = [
        name
        for name, passed in (
            ("full_predictions", full_predictions["passed"]),
            ("anchor_response_ordering", anchor_ordering["passed"]),
            ("spearman_association", association["passed"]),
            ("worst_anchor_improvement", worst["passed"]),
        )
        if not passed
    ]
    report: dict[str, Any] = {
        "schema_version": 1,
        "report_name": "AAAI-27 r7 fourteen-artifact frozen pilot report",
        "branch": "e1_pass",
        "completed_task_ids": sorted(artifact_paths),
        "artifact_manifests": artifact_paths,
        "decision_source": "artifact_metrics",
        "phenomenon_pass": not failure_reasons,
        "failure_reasons": failure_reasons,
        "phenomenon_checks": checks,
        "frozen_inputs": {
            "primary_statistic": "EPE",
            "epe": {
                dataset: {str(level): epe[dataset][level] for level in PILOT_LEVELS}
                for dataset in DATASETS
            },
            "phi_R": {
                dataset: {str(level): phi[dataset][level] for level in PILOT_LEVELS}
                for dataset in DATASETS
            },
            "thresholds": thresholds,
        },
        "results": results,
        "source_provenance": {
            "queue_manifest": queue_manifest_path.relative_to(queue_root).as_posix(),
            "queue_manifest_sha256": queue_hash,
            "risk05_preregistration_path": str(
                Path(risk05_root) / "protocol" / "risk05_preregistration.json"
            ),
            "risk05_preregistration_file_sha256": prereg_file_hash,
            "risk05_preregistration_payload_sha256": prereg_hash,
            "risk_preflight_path": str(Path(risk_preflight_path)),
            "risk_preflight_sha256": sha256_file(risk_preflight_path),
            "e1_marker": e1_candidates[0].relative_to(queue_root).as_posix(),
            "e1_marker_sha256": sha256_file(e1_candidates[0]),
        },
        "single_seed_observation": True,
        "no_rescue": True,
    }
    report["artifact_sha256"] = _payload_hash(report)
    return report


def finalize_artifact_derived_risk08(
    queue_root: Path,
    *,
    risk05_root: Path,
    risk_preflight_path: Path,
    report_path: Path | None = None,
) -> dict[str, Any]:
    """Write one immutable artifact-derived report and call original RISK-08 once."""

    queue_root = Path(queue_root).resolve()
    output_path = (
        Path(report_path)
        if report_path is not None
        else queue_root / "reports" / "pilot_report.json"
    ).resolve()
    if output_path == queue_root or queue_root not in output_path.parents:
        raise PilotReportError("pilot report must remain inside the dated queue root")
    report = build_artifact_derived_pilot_report(
        queue_root,
        risk05_root=Path(risk05_root),
        risk_preflight_path=Path(risk_preflight_path),
    )
    atomic_write_json(output_path, report)
    return run_risk08_decision(
        queue_root,
        e1_marker_path=queue_root / "markers" / "RISK-02_PASS.json",
        risk05_root=Path(risk05_root),
        pilot_report_path=output_path,
    )
