from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

from scripts.aaai27_adapters.common import sha256_file, stable_sha256
from scripts.aaai27_adapters.risk04_08 import (
    QueueSafetyError,
    build_risk04_bundle,
    build_risk05_bundle,
    build_risk0607_manifest,
    run_risk08_decision,
    validate_risk04_bundle,
)
from scripts.aaai27_queue.models import QueueManifest
from scripts.aaai27_queue.validation import validate_manifest


class Risk0408QueueSafeAdapterTests(unittest.TestCase):
    def _null_curves(self, root: Path) -> dict[str, dict[str, str]]:
        curves: dict[str, dict[str, str]] = {}
        for dataset in ("Beauty", "Steam"):
            path = root / f"{dataset}_agreement_null_curves.json"
            path.write_text(
                json.dumps({"dataset": dataset, "reference": "clean"}),
                encoding="utf-8",
            )
            curves[dataset] = {
                "path": path.resolve().as_posix(),
                "sha256": sha256_file(path),
            }
        return curves

    def test_cli_wrappers_are_directly_invokable(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for name in (
            "build_risk04_corruption_banks.py",
            "validate_risk04_banks.py",
            "build_risk05_preregistration.py",
            "build_risk0607_pilot_manifest.py",
            "run_risk08_decision.py",
        ):
            completed = subprocess.run(
                [sys.executable, str(root / "scripts" / name), "--help"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)

    def _inputs(self, root: Path) -> dict[str, object]:
        datasets: dict[str, object] = {}
        for dataset in ("Beauty", "Steam"):
            clean = root / f"{dataset}_clean_embeddings.npy"
            np.save(clean, (np.arange(48, dtype=np.float32).reshape(12, 4) + 1.0) / 10.0)
            transitions = root / f"{dataset}_train_transitions.jsonl"
            with transitions.open("w", encoding="utf-8") as handle:
                for index in range(30):
                    handle.write(
                        json.dumps(
                            {
                                "row_id": f"{dataset}-{index}",
                                "user_id": index % 5,
                                "target_item_id": index % 12,
                                "history_item_ids": [index % 12],
                            }
                        )
                        + "\n"
                    )
            datasets[dataset] = {
                "clean_embeddings_path": str(clean),
                "train_transitions_path": str(transitions),
                "split_sha256": sha256_file(transitions),
            }
        return {
            "schema_version": 1,
            "datasets": datasets,
            "strata_count": 3,
            "corruption_seed": 100,
            "severe_gate": {"clean_mean_gate": 0.50, "steam_c60_mean_gate": 0.35},
            "code_revision": "a" * 40,
        }

    def _preflight(self, root: Path, risk04: dict[str, object]) -> Path:
        levels = [
            {"level": 0, "epe": 0.0},
            {"level": 20, "epe": 0.1},
            {"level": 40, "epe": 0.3},
            {"level": 60, "epe": 0.8, "mean_gate": 0.35},
            {"level": 80, "epe": 1.2},
            {"level": 100, "epe": 1.8},
        ]
        report = {
            "schema_version": 1,
            "report_name": "synthetic train-only preflight fixture",
            "protocol": {"split": "train-only", "corruption_seed": 100},
            "datasets": {
                dataset: {
                    "clean_epe": 0.0,
                    "levels": [dict(row, mean_gate=(0.5 if row["level"] == 0 else row.get("mean_gate"))) for row in levels],
                    "source_hashes": {
                        **risk04["datasets"][dataset]["source_hashes"],
                        "banks": {
                            str(level): risk04["datasets"][dataset]["banks"][str(level)]["bank_sha256"]
                            for level in (0, 20, 40, 60, 80, 100)
                        },
                    },
                }
                for dataset in ("Beauty", "Steam")
            },
            "source_hashes": {dataset: risk04["datasets"][dataset]["source_hashes"] for dataset in ("Beauty", "Steam")},
        }
        report["artifact_sha256"] = stable_sha256(report)
        path = root / "risk_preflight_report.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return path

    def _risk05_template(self, root: Path, risk04: dict[str, object], preflight: Path) -> tuple[Path, Path]:
        e1 = root / "RISK-02_PASS.json"
        e1.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "risk_id": "RISK-02",
                    "outcome": "pass",
                    "random_seed": 100,
                    "trace_steps": [0, 1, 100, 1000],
                    "source_revision": "b" * 40,
                    "trace_sha256": "c" * 64,
                }
            ),
            encoding="utf-8",
        )
        return e1, preflight

    def test_dated_risk04_bundle_validates_and_existing_root_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self._inputs(root)
            output = root / "risk04-2026-07-11"
            report = build_risk04_bundle(config, output, generated_at="2026-07-11T08:00:00+08:00")
            self.assertEqual("pass", report["severe_gate"]["status"])
            validated = validate_risk04_bundle(output, require_severe_gate=True)
            self.assertEqual("pass", validated["status"])
            self.assertEqual(6, len(report["datasets"]["Beauty"]["banks"]))
            with self.assertRaises(FileExistsError):
                build_risk04_bundle(config, output, generated_at="2026-07-11T08:01:00+08:00")

    def test_steam_severe_gate_failure_is_terminal_and_never_authorizes_training(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self._inputs(root)
            config["severe_gate"] = {"clean_mean_gate": 0.50, "steam_c60_mean_gate": 0.46}
            output = root / "risk04-stop-2026-07-11"
            report = build_risk04_bundle(config, output, generated_at="2026-07-11T08:05:00+08:00")
            self.assertEqual("stop", report["severe_gate"]["status"])
            self.assertFalse(report["training_start_authorized"])
            self.assertTrue((output / "RISK-04_STOP.json").exists())
            with self.assertRaises(QueueSafetyError):
                validate_risk04_bundle(output, require_severe_gate=True)

    def test_risk05_and_risk0607_bind_hashes_and_validate_both_branches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self._inputs(root)
            risk04_root = root / "risk04-2026-07-11"
            risk04 = build_risk04_bundle(config, risk04_root, generated_at="2026-07-11T08:00:00+08:00")
            preflight = self._preflight(root, risk04)
            e1, preflight = self._risk05_template(root, risk04, preflight)
            risk05_root = root / "risk05-2026-07-11"
            risk05 = build_risk05_bundle(
                risk04_root,
                preflight,
                e1,
                risk05_root,
                generated_at="2026-07-11T08:10:00+08:00",
            )
            self.assertTrue(risk05["preregistration_sha256"])
            queue_root = root / "queue-2026-07-11"
            null_curves = self._null_curves(root)
            risk04_runtime_root = risk04_root.resolve().as_posix()
            if not risk04_runtime_root.startswith("/"):
                risk04_runtime_root = "/srv/aaai27/risk04-2026-07-11"
            protocol = {
                "queue_id": "aaai27-risk0408-test",
                "created_at": "2026-07-11T08:20:00+08:00",
                "queue_root_posix": "/srv/aaai27/queue/2026-07-11",
                "run_root_posix": "/srv/aaai27/queue/2026-07-11",
                "source_root_posix": "/srv/aaai27/source",
                "gpu_ids": [0, 1],
                "source_manifest_sha256": "d" * 64,
                "ledger_path_posix": "/srv/aaai27/ledger.csv",
                "ledger_sha256": "e" * 64,
                "code_revision": "f" * 40,
                "config_sha256": "1" * 64,
                "python_bin": "/srv/aaai27/source/.venv/bin/python",
                "single_train": "/srv/aaai27/source/single_train.py",
                "risk04_root_posix": risk04_runtime_root,
                "training_overrides": ["training.n_iters=10"],
                "estimated_gpu_hours": {"low": 0.5, "high": 1.0, "output_gib": 0.2},
                "datasets": {
                    dataset: {
                        "dataset_dir": f"/srv/data/{dataset}",
                        "text_bank_path": f"/srv/data/{dataset}/text_bank.csv",
                        "null_curve_path": null_curves[dataset]["path"],
                        "null_curve_sha256": null_curves[dataset]["sha256"],
                        "config_sha256": "2" * 64,
                    }
                    for dataset in ("Beauty", "Steam")
                },
            }
            manifest = build_risk0607_manifest(risk05_root, e1, queue_root, protocol)
            wrong_gpu_protocol = dict(protocol)
            wrong_gpu_protocol["gpu_ids"] = [1]
            with self.assertRaisesRegex(QueueSafetyError, "explicitly equal"):
                build_risk0607_manifest(
                    risk05_root,
                    e1,
                    root / "queue-wrong-gpu-2026-07-11",
                    wrong_gpu_protocol,
                )
            decoded = QueueManifest.from_dict(manifest)
            validate_manifest(decoded)
            self.assertEqual(22, len(decoded.tasks))
            self.assertEqual((0, 1), decoded.gpu_ids)
            self.assertEqual(14, sum(task.branch == "e1_pass" for task in decoded.tasks))
            self.assertEqual(8, sum(task.branch == "e1_fail_audit" for task in decoded.tasks))
            self.assertTrue((queue_root / "queue" / "queue_seed100.json").exists())

            prereg = json.loads(
                (queue_root / "protocol" / "risk05_preregistration.json").read_text(
                    encoding="utf-8"
                )
            )
            prereg_sha256 = stable_sha256(prereg)
            for task in manifest["tasks"]:
                self.assertTrue(
                    task["run_dir"].startswith(
                        "/srv/aaai27/queue/2026-07-11/runs/"
                    ),
                    task["task_id"],
                )
                self.assertNotIn("/runs/runs/", task["run_dir"])
                self.assertEqual(task["run_dir"], task["cwd"], task["task_id"])
                work_dirs = [
                    token.split("=", 1)[1]
                    for token in task["argv"]
                    if token.startswith("work_dir=")
                ]
                self.assertEqual([task["run_dir"]], work_dirs, task["task_id"])
                if task["arm"] == "host":
                    self.assertIn(
                        "graph.type=adaptive",
                        task["argv"],
                        task["task_id"],
                    )
                    self.assertEqual(
                        [
                            f"runs/{task['branch']}/{task['dataset']}/host/"
                            f"checkpoints-meta/{task['dataset']}/best_summary_adaptive.json",
                            f"runs/{task['branch']}/{task['dataset']}/host/"
                            "artifact_manifest.json",
                        ],
                        task["success_artifacts"],
                        task["task_id"],
                    )
                    continue
                level = task["arm"].rsplit("c", 1)[-1]
                expected_embedding = (
                    f"{risk04_runtime_root}/banks/{task['dataset']}/"
                    f"level-{int(level):03d}/embeddings.pt"
                )
                self.assertIn(
                    f"text_side.embeddings_path={expected_embedding}",
                    task["argv"],
                    task["task_id"],
                )
                self.assertEqual(
                    risk04["datasets"][task["dataset"]]["banks"][level][
                        "embedding_sha256"
                    ],
                    task["env"].get("AAAI_EMBEDDING_SHA256"),
                    task["task_id"],
                )
                self.assertEqual(
                    risk04["datasets"][task["dataset"]]["banks"][level][
                        "bank_sha256"
                    ],
                    task["env"].get("AAAI_BANK_SHA256"),
                    task["task_id"],
                )
                if task["arm"].startswith("risk_gated_full_c"):
                    expected_scale = prereg["phi_R"][task["dataset"]][level]
                    self.assertIn(
                        f"text_side.gate_dataset_scale_override={expected_scale}",
                        task["argv"],
                        task["task_id"],
                    )
                    self.assertEqual(
                        prereg_sha256,
                        task["env"].get("AAAI_RISK05_PREREG_SHA256"),
                        task["task_id"],
                    )
                    self.assertEqual(
                        str(expected_scale),
                        task["env"].get("AAAI_GATE_DATASET_SCALE"),
                        task["task_id"],
                    )

    def test_risk08_rejects_unproven_metrics_and_writes_one_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self._inputs(root)
            risk04_root = root / "risk04-2026-07-11"
            risk04 = build_risk04_bundle(config, risk04_root, generated_at="2026-07-11T08:00:00+08:00")
            preflight = self._preflight(root, risk04)
            e1, preflight = self._risk05_template(root, risk04, preflight)
            risk05_root = root / "risk05-2026-07-11"
            build_risk05_bundle(risk04_root, preflight, e1, risk05_root, generated_at="2026-07-11T08:10:00+08:00")
            queue_root = root / "queue-2026-07-11"
            null_curves = self._null_curves(root)
            risk04_runtime_root = risk04_root.resolve().as_posix()
            if not risk04_runtime_root.startswith("/"):
                risk04_runtime_root = "/srv/aaai27/risk04-2026-07-11"
            protocol = {
                "queue_id": "aaai27-risk0408-r8-test",
                "created_at": "2026-07-11T08:20:00+08:00",
                "queue_root_posix": "/srv/aaai27/queue/2026-07-11",
                "run_root_posix": "/srv/aaai27/queue/2026-07-11",
                "source_root_posix": "/srv/aaai27/source",
                "gpu_ids": [0, 1],
                "source_manifest_sha256": "d" * 64,
                "ledger_path_posix": "/srv/aaai27/ledger.csv",
                "ledger_sha256": "e" * 64,
                "code_revision": "f" * 40,
                "config_sha256": "1" * 64,
                "python_bin": "/srv/aaai27/source/.venv/bin/python",
                "single_train": "/srv/aaai27/source/single_train.py",
                "risk04_root_posix": risk04_runtime_root,
                "training_overrides": [],
                "estimated_gpu_hours": {"low": 0.5, "high": 1.0, "output_gib": 0.2},
                "datasets": {
                    dataset: {
                        "dataset_dir": f"/srv/data/{dataset}",
                        "text_bank_path": f"/srv/data/{dataset}/text_bank.csv",
                        "null_curve_path": null_curves[dataset]["path"],
                        "null_curve_sha256": null_curves[dataset]["sha256"],
                        "config_sha256": "2" * 64,
                    }
                    for dataset in ("Beauty", "Steam")
                },
            }
            manifest = build_risk0607_manifest(risk05_root, e1, queue_root, protocol)
            queue_hash = sha256_file(queue_root / "queue" / "queue_seed100.json")
            completed = [task["task_id"] for task in manifest["tasks"] if task["branch"] == "e1_pass"]
            artifact_paths: dict[str, str] = {}
            for task in manifest["tasks"]:
                if task["branch"] != "e1_pass":
                    continue
                relative_run = task["run_dir"].split("/runs/", 1)[1]
                run_dir = queue_root / "runs" / relative_run
                run_dir.mkdir(parents=True, exist_ok=True)
                metrics_path = queue_root / task["success_artifacts"][0]
                metrics_path.parent.mkdir(parents=True, exist_ok=True)
                metrics_path.write_text(
                    json.dumps(
                        {
                            "best_step": 10,
                            "validation": {
                                "p5": {
                                    "hr": [0.0, 0.0, 0.2],
                                    "ndcg": [0.0, 0.0, 0.1],
                                }
                            },
                            "test": {
                                "p5": {
                                    "hr": [0.0, 0.0, 0.2],
                                    "ndcg": [0.0, 0.0, 0.1],
                                }
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                log_path = run_dir / "single_train.log"
                log_path.write_text("AAAI_PILOT_WRAPPER_START\nAAAI_PILOT_WRAPPER_END\n", encoding="utf-8")
                task_env = task["env"]
                null_policy = task_env["AAAI_NULL_CURVE_REFERENCE_POLICY"]
                null_reference = {"policy": null_policy}
                if null_policy == "frozen_clean_calibration":
                    null_reference.update(
                        {
                            "path": str(Path(task_env["AAAI_NULL_CURVE_PATH"]).resolve()),
                            "sha256": task_env["AAAI_NULL_CURVE_SHA256"],
                            "source_bank_sha256": task_env[
                                "AAAI_NULL_CURVE_SOURCE_BANK_SHA256"
                            ],
                            "current_embedding_sha256": task_env[
                                "AAAI_CURRENT_EMBEDDING_SHA256"
                            ],
                        }
                    )
                gate_scale = task_env.get("AAAI_GATE_DATASET_SCALE")
                artifact = {
                    "schema_version": 1,
                    "task_id": task["task_id"],
                    "status": "pass",
                    "queue_manifest_sha256": queue_hash,
                    "source_revision": task["code_revision"],
                    "config_sha256": task["config_sha256"],
                    "split_sha256": task["split_sha256"],
                    "bank_sha256": task["bank_sha256"],
                    "evaluator_version": task["evaluator_version"],
                    "selector_version": task["selector_version"],
                    "gate_dataset_scale": (
                        float(gate_scale) if gate_scale is not None else None
                    ),
                    "metrics_provenance": {
                        "path": metrics_path.relative_to(queue_root).as_posix(),
                        "sha256": sha256_file(metrics_path),
                    },
                    "log_provenance": {
                        "path": log_path.relative_to(queue_root).as_posix(),
                        "sha256": sha256_file(log_path),
                        "size_bytes": log_path.stat().st_size,
                    },
                    "null_curve_reference": null_reference,
                }
                artifact["artifact_sha256"] = stable_sha256(artifact)
                artifact_path = queue_root / task["success_artifacts"][1]
                artifact_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
                artifact_paths[task["task_id"]] = artifact_path.relative_to(queue_root).as_posix()
            report = {
                "schema_version": 1,
                "branch": "e1_pass",
                "completed_task_ids": completed,
                "artifact_manifests": artifact_paths,
                "decision_source": "artifact_metrics",
                "phenomenon_pass": True,
                "phenomenon_checks": {"artifact_task_ids": completed},
            }
            pilot_report = root / "pilot-report.json"
            pilot_report.write_text(json.dumps(report, indent=2), encoding="utf-8")
            marker = run_risk08_decision(
                queue_root,
                e1_marker_path=e1,
                risk05_root=risk05_root,
                pilot_report_path=pilot_report,
            )
            self.assertEqual("risk_gated_method", marker["exit"])
            with self.assertRaises(FileExistsError):
                run_risk08_decision(
                    queue_root,
                    e1_marker_path=e1,
                    risk05_root=risk05_root,
                    pilot_report_path=pilot_report,
                )

            bad_report = dict(report)
            bad_report["phenomenon_checks"] = {"artifact_task_ids": completed[:-1]}
            bad_path = root / "bad-pilot-report.json"
            bad_path.write_text(json.dumps(bad_report), encoding="utf-8")
            # A second dated queue is needed because the first queue already has
            # its immutable RISK-08 marker.
            with self.assertRaises((QueueSafetyError, FileExistsError)):
                run_risk08_decision(
                    queue_root,
                    e1_marker_path=e1,
                    risk05_root=risk05_root,
                    pilot_report_path=bad_path,
                )


if __name__ == "__main__":
    unittest.main()
