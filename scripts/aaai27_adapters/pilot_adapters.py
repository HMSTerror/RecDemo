from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .common import atomic_write_json, stable_sha256


DATASETS = ("Beauty", "Steam")
LEVELS = (0, 60, 100)


def _expected_pilot_ids(branch: str, include_full: bool) -> set[str]:
    expected: set[str] = set()
    for dataset in DATASETS:
        expected.add(f"pilot.{branch}.{dataset}.host")
        for level in LEVELS:
            expected.add(f"pilot.{branch}.{dataset}.anchor.c{level}")
            if include_full:
                expected.add(f"pilot.{branch}.{dataset}.full.c{level}")
    return expected


def _base_argv(protocol: dict[str, Any], dataset: str, dataset_cfg: dict[str, Any], run_dir: str, graph_type: str) -> list[str]:
    argv = [
        str(protocol["python_bin"]),
        str(protocol["single_train"]),
        f"work_dir={run_dir}",
        "cuda=0",
        "random_seed=100",
        f"training.data={dataset}",
        f"data.{dataset}.path={dataset_cfg['dataset_dir']}",
        f"graph.type={graph_type}",
        "graph.is_disliked_item=True",
        "model.hidden_size=256",
        "model.cond_dim=256",
        "loss_type=score_entropy",
    ]
    argv.extend(str(value) for value in protocol.get("training_overrides", []))
    return argv


def _task(
    *,
    protocol: dict[str, Any],
    dataset: str,
    dataset_cfg: dict[str, Any],
    branch: str,
    arm: str,
    run_rel: str,
    argv: list[str],
    bank_sha256: str | None,
    embedding_sha256: str | None,
    graph_type: str,
    priority: int,
) -> dict[str, Any]:
    task_id = f"pilot.{branch}.{dataset}.{'host' if arm == 'host' else 'anchor.c' + arm.rsplit('c', 1)[-1]}"
    if arm.startswith("text_anchor_only_c"):
        level = arm.rsplit("c", 1)[-1]
        task_id = f"pilot.{branch}.{dataset}.anchor.c{level}"
    if arm.startswith("risk_gated_full_c"):
        level = arm.rsplit("c", 1)[-1]
        task_id = f"pilot.{branch}.{dataset}.full.c{level}"
    run_dir = f"{protocol['run_root']}/{run_rel}"
    summary_name = "best_summary_hybrid.json" if graph_type == "hybrid" else "best_summary_proposal_adaptive.json"
    env = {
        "PYTHONHASHSEED": "100",
        "AAAI_DATASET": dataset,
        "AAAI_ARM": arm,
    }
    if bank_sha256 is not None:
        env["AAAI_BANK_SHA256"] = str(bank_sha256)
        if embedding_sha256 is None:
            raise ValueError("evidence-conditioned task lacks embedding SHA-256")
        env["AAAI_EMBEDDING_SHA256"] = str(embedding_sha256)
        env["AAAI_RISK05_PREREG_SHA256"] = str(
            protocol["risk05_preregistration_sha256"]
        )
    gate_scale_tokens = [
        token.split("=", 1)[1]
        for token in argv
        if token.startswith("text_side.gate_dataset_scale_override=")
    ]
    if gate_scale_tokens:
        env["AAAI_GATE_DATASET_SCALE"] = gate_scale_tokens[0]
    return {
        "schema_version": 1,
        "task_id": task_id,
        "ledger_id": "RISK-06" if dataset == "Beauty" else "RISK-07",
        "phase": "pilot",
        "branch": branch,
        "kind": "gpu",
        "argv": argv,
        "cwd": str(protocol["source_root"]),
        "env": env,
        "dependencies": [],
        "required_markers": ["markers/RISK-02_PASS.json" if branch == "e1_pass" else "markers/RISK-02_FAIL.json"],
        "success_artifacts": [f"{run_rel}/checkpoints-meta/{dataset}/{summary_name}"],
        "failure_policy": "fail_closed",
        "max_attempts": 1,
        "gpu_slots": 1,
        "gpu_hours_low": float(protocol["estimated_gpu_hours"]["low"]),
        "gpu_hours_high": float(protocol["estimated_gpu_hours"]["high"]),
        "estimated_output_gib": float(protocol["estimated_gpu_hours"]["output_gib"]),
        "seed": 100,
        "dataset": dataset,
        "arm": arm,
        "model": "PreferGrow",
        "run_dir": run_dir,
        "code_revision": str(protocol["code_revision"]),
        "config_sha256": str(dataset_cfg.get("config_sha256", protocol["config_sha256"])),
        "split_sha256": str(dataset_cfg["split_sha256"]),
        "bank_sha256": bank_sha256,
        "evaluator_version": "e0_full_tail_v2",
        "selector_version": "validation-ndcg10-rowweighted-v1",
        "atomic_group": f"{branch}.{dataset}",
        "priority": int(priority),
    }


def build_pilot_manifest(protocol: dict[str, Any]) -> dict[str, Any]:
    if set(protocol.get("datasets", {})) != set(DATASETS):
        raise ValueError("pilot manifest requires exactly Beauty and Steam dataset specifications")
    tasks: list[dict[str, Any]] = []
    for branch, include_full in (("e1_pass", True), ("e1_fail_audit", False)):
        for dataset in DATASETS:
            dataset_cfg = protocol["datasets"][dataset]
            host_rel = f"runs/{branch}/{dataset}/host"
            host_argv = _base_argv(protocol, dataset, dataset_cfg, f"{protocol['run_root']}/{host_rel}", "hybrid")
            tasks.append(
                _task(
                    protocol=protocol,
                    dataset=dataset,
                    dataset_cfg=dataset_cfg,
                    branch=branch,
                    arm="host",
                    run_rel=host_rel,
                    argv=host_argv,
                    bank_sha256=None,
                    embedding_sha256=None,
                    graph_type="hybrid",
                    priority=0,
                )
            )
            for level in LEVELS:
                bank = dataset_cfg["banks"][str(level)]
                anchor_rel = f"runs/{branch}/{dataset}/anchor_c{level}"
                anchor_argv = _base_argv(
                    protocol,
                    dataset,
                    dataset_cfg,
                    f"{protocol['run_root']}/{anchor_rel}",
                    "proposal_adaptive",
                )
                anchor_argv.extend(
                    [
                        "text_side.enabled=True",
                        f"text_side.dataset_dir={dataset_cfg['dataset_dir']}",
                        f"text_side.text_bank_path={dataset_cfg['text_bank_path']}",
                        f"text_side.embeddings_path={bank['embedding_path']}",
                        f"text_side.agreement_null_curve_path={dataset_cfg['null_curve_path']}",
                        "text_side.kernel_version=v2",
                        "text_side.temperature=0.2",
                        "text_side.g_max=0.5",
                        "text_side.ablation_mode=text_anchor_only",
                        "text_side.injection_mode=kernel",
                        "text_side.require_gate_source=True",
                    ]
                )
                tasks.append(
                    _task(
                        protocol=protocol,
                        dataset=dataset,
                        dataset_cfg=dataset_cfg,
                        branch=branch,
                        arm=f"text_anchor_only_c{level}",
                        run_rel=anchor_rel,
                        argv=anchor_argv,
                        bank_sha256=str(bank["bank_sha256"]),
                        embedding_sha256=str(bank["embedding_sha256"]),
                        graph_type="proposal_adaptive",
                        priority=1,
                    )
                )
                if include_full:
                    full_rel = f"runs/{branch}/{dataset}/full_c{level}"
                    full_argv = list(anchor_argv)
                    full_run_dir = f"{protocol['run_root']}/{full_rel}"
                    full_argv = [
                        f"work_dir={full_run_dir}"
                        if token.startswith("work_dir=")
                        else token
                        for token in full_argv
                    ]
                    full_argv[full_argv.index("text_side.ablation_mode=text_anchor_only")] = "text_side.ablation_mode=none"
                    full_argv.append(
                        "text_side.gate_dataset_scale_override="
                        f"{float(bank['phi_R'])}"
                    )
                    tasks.append(
                        _task(
                            protocol=protocol,
                            dataset=dataset,
                            dataset_cfg=dataset_cfg,
                            branch=branch,
                            arm=f"risk_gated_full_c{level}",
                            run_rel=full_rel,
                            argv=full_argv,
                            bank_sha256=str(bank["bank_sha256"]),
                            embedding_sha256=str(bank["embedding_sha256"]),
                            graph_type="proposal_adaptive",
                            priority=1,
                        )
                    )
    manifest = {
        "schema_version": 1,
        "queue_id": str(protocol["queue_id"]),
        "created_at": str(protocol["created_at"]),
        "run_root": str(protocol["run_root"]),
        "source_root": str(protocol["source_root"]),
        "source_manifest_sha256": str(protocol["source_manifest_sha256"]),
        "ledger_path": str(protocol["ledger_path"]),
        "ledger_sha256": str(protocol["ledger_sha256"]),
        "gpu_ids": [0, 1],
        "gpu_budget_hours": 168.0,
        "min_free_disk_gib": 40.0,
        "tasks": tasks,
    }
    return manifest


def write_risk08_exit(output_root: Path, *, e1_marker: dict[str, Any], pilot_report: dict[str, Any]) -> dict[str, Any]:
    outcome = str(e1_marker.get("outcome", ""))
    if outcome not in {"pass", "fail"}:
        raise ValueError("RISK-08 requires a terminal E1 pass/fail outcome")
    branch = str(pilot_report.get("branch", ""))
    completed = pilot_report.get("completed_task_ids")
    if not isinstance(completed, list) or len(completed) != len(set(completed)):
        raise ValueError("RISK-08 pilot report must list unique completed task IDs")
    expected = _expected_pilot_ids(branch, include_full=(branch == "e1_pass"))
    if set(completed) != expected:
        raise ValueError("RISK-08 pilot report does not contain the complete frozen branch matrix")
    if outcome == "fail" and branch != "e1_fail_audit":
        raise ValueError("E1 fail can only produce the e1_fail_audit branch")
    if outcome == "pass" and branch != "e1_pass":
        raise ValueError("E1 pass can only produce the e1_pass branch")
    phenomenon_pass = pilot_report.get("phenomenon_pass")
    if not isinstance(phenomenon_pass, bool):
        raise ValueError("RISK-08 requires a frozen boolean phenomenon_pass decision")
    if outcome == "pass" and phenomenon_pass:
        exit_value = "risk_gated_method"
    elif outcome == "fail" and phenomenon_pass:
        exit_value = "audit_only"
    else:
        exit_value = "submission_stop"
    marker = {
        "schema_version": 1,
        "risk_id": "RISK-08",
        "exit": exit_value,
        "e1_outcome": outcome,
        "pilot_branch": branch,
        "pilot_report_sha256": stable_sha256(pilot_report),
        "e1_marker_sha256": str(e1_marker.get("marker_sha256", "")),
        "phenomenon_pass": phenomenon_pass,
        "no_rescue": True,
        "single_seed_observation": True,
    }
    marker["artifact_sha256"] = stable_sha256(marker)
    root = Path(output_root)
    atomic_write_json(root / "markers" / "RISK-08_EXIT.json", marker)
    return marker


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the frozen pilot manifest or emit the RISK-08 exit marker.")
    parser.add_argument("--protocol-json", type=Path)
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument("--risk08-root", type=Path)
    parser.add_argument("--e1-marker-json", type=Path)
    parser.add_argument("--pilot-report-json", type=Path)
    args = parser.parse_args()
    if args.protocol_json and args.manifest_output:
        manifest = build_pilot_manifest(json.loads(args.protocol_json.read_text(encoding="utf-8")))
        atomic_write_json(args.manifest_output, manifest)
        print(json.dumps({"task_count": len(manifest["tasks"]), "manifest_sha256": stable_sha256(manifest)}, indent=2))
        return
    if args.risk08_root and args.e1_marker_json and args.pilot_report_json:
        marker = write_risk08_exit(
            args.risk08_root,
            e1_marker=json.loads(args.e1_marker_json.read_text(encoding="utf-8")),
            pilot_report=json.loads(args.pilot_report_json.read_text(encoding="utf-8")),
        )
        print(json.dumps(marker, indent=2))
        return
    raise SystemExit("provide either --protocol-json/--manifest-output or the RISK-08 arguments")


if __name__ == "__main__":
    main()
