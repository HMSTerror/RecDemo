from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

from scripts.aaai27_adapters.common import atomic_write_json, sha256_file, stable_sha256
from scripts.aaai27_adapters.pilot_report import (
    PilotReportError,
    build_artifact_derived_pilot_report,
    finalize_artifact_derived_risk08,
)
from scripts.aaai27_adapters.risk04_08 import (
    build_risk04_bundle,
    build_risk05_bundle,
    build_risk0607_manifest,
)


DATASETS = ("Beauty", "Steam")
LEVELS = (0, 20, 40, 60, 80, 100)
PILOT_LEVELS = (0, 60, 100)

BASE_ANCHOR_DELTAS = {
    ("Beauty", 0): -0.006,
    ("Beauty", 60): -0.004,
    ("Beauty", 100): -0.002,
    ("Steam", 0): -0.005,
    ("Steam", 60): -0.003,
    ("Steam", 100): -0.001,
}

BASE_FULL_DELTAS = {
    (dataset, level): (0.001 if level != 100 else 0.0)
    for dataset in DATASETS
    for level in PILOT_LEVELS
}


class R7PilotReportTests(unittest.TestCase):
    def test_finalizer_cli_is_directly_invokable(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts" / "finalize_r7_pilot.py"
        completed = subprocess.run(
            [sys.executable, str(script), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("--risk-preflight-json", completed.stdout)

    @classmethod
    def setUpClass(cls) -> None:
        cls._base_tmp = tempfile.TemporaryDirectory()
        cls.base_root = Path(cls._base_tmp.name)
        cls._build_base_layout(cls.base_root)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._base_tmp.cleanup()

    @classmethod
    def _inputs(cls, root: Path) -> dict[str, object]:
        datasets: dict[str, object] = {}
        for dataset in DATASETS:
            clean = root / f"{dataset}_clean_embeddings.npy"
            np.save(
                clean,
                (np.arange(48, dtype=np.float32).reshape(12, 4) + 1.0) / 10.0,
            )
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
            "severe_gate": {
                "clean_mean_gate": 0.50,
                "steam_c60_mean_gate": 0.35,
            },
            "code_revision": "a" * 40,
        }

    @classmethod
    def _preflight(cls, root: Path, risk04: dict[str, object]) -> Path:
        epe_by_dataset = {
            "Beauty": [6.0, 5.0, 4.0, 3.0, 2.5, 2.0],
            "Steam": [5.0, 4.0, 3.0, 2.2, 1.5, 1.0],
        }
        report = {
            "schema_version": 1,
            "report_name": "synthetic train-only r7 pilot-report fixture",
            "protocol": {
                "split": "train-only",
                "corruption_seed": 100,
                "sampling_seed": 7,
            },
            "datasets": {
                dataset: {
                    "clean_epe": epe_by_dataset[dataset][0],
                    "levels": [
                        {"level": level, "epe": epe}
                        for level, epe in zip(LEVELS, epe_by_dataset[dataset])
                    ],
                    "source_hashes": {
                        **risk04["datasets"][dataset]["source_hashes"],
                        "banks": {
                            str(level): risk04["datasets"][dataset]["banks"][
                                str(level)
                            ]["bank_sha256"]
                            for level in LEVELS
                        },
                    },
                }
                for dataset in DATASETS
            },
            "source_hashes": {
                dataset: {
                    **risk04["datasets"][dataset]["source_hashes"],
                    "banks": {
                        str(level): risk04["datasets"][dataset]["banks"][
                            str(level)
                        ]["bank_sha256"]
                        for level in LEVELS
                    },
                }
                for dataset in DATASETS
            },
        }
        report["artifact_sha256"] = stable_sha256(report)
        path = root / "risk_preflight_report.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return path

    @classmethod
    def _build_base_layout(cls, root: Path) -> None:
        risk04_root = root / "risk04-2026-07-12"
        risk04 = build_risk04_bundle(
            cls._inputs(root),
            risk04_root,
            generated_at="2026-07-12T08:00:00+08:00",
        )
        preflight = cls._preflight(root, risk04)
        e1 = root / "RISK-02_PASS.json"
        atomic_write_json(
            e1,
            {
                "schema_version": 1,
                "risk_id": "RISK-02",
                "outcome": "pass",
                "random_seed": 100,
                "trace_steps": [0, 1, 100, 1000],
                "source_revision": "b" * 40,
                "first_divergence": None,
            },
        )
        risk05_root = root / "risk05-2026-07-12"
        build_risk05_bundle(
            risk04_root,
            preflight,
            e1,
            risk05_root,
            generated_at="2026-07-12T08:10:00+08:00",
        )
        null_curves: dict[str, dict[str, str]] = {}
        for dataset in DATASETS:
            path = root / f"{dataset}_agreement_null_curves.json"
            path.write_text(json.dumps({"dataset": dataset}), encoding="utf-8")
            null_curves[dataset] = {
                "path": path.resolve().as_posix(),
                "sha256": sha256_file(path),
            }
        queue_root = root / "queue-2026-07-12"
        runtime_risk04 = risk04_root.resolve().as_posix()
        if not runtime_risk04.startswith("/"):
            runtime_risk04 = "/srv/aaai27/risk04-2026-07-12"
        protocol = {
            "queue_id": "aaai27-r7-pilot-report-test",
            "created_at": "2026-07-12T08:20:00+08:00",
            "queue_root_posix": "/srv/aaai27/queue/r7-test",
            "run_root_posix": "/srv/aaai27/queue/r7-test",
            "source_root_posix": "/srv/aaai27/source-r7",
            "gpu_ids": [1],
            "source_manifest_sha256": "c" * 64,
            "ledger_path_posix": "/srv/aaai27/source-r7/issues/r7.csv",
            "ledger_sha256": "d" * 64,
            "code_revision": "e" * 40,
            "config_sha256": "f" * 64,
            "python_bin": "/srv/aaai27/source-r7/.venv/bin/python3",
            "single_train": "/srv/aaai27/source-r7/single_train.py",
            "risk04_root_posix": runtime_risk04,
            "training_overrides": ["training.n_iters=10"],
            "estimated_gpu_hours": {"low": 0.1, "high": 0.2, "output_gib": 0.1},
            "datasets": {
                dataset: {
                    "dataset_dir": f"/srv/data/{dataset}",
                    "text_bank_path": f"/srv/data/{dataset}/text_bank.csv",
                    "null_curve_path": null_curves[dataset]["path"],
                    "null_curve_sha256": null_curves[dataset]["sha256"],
                    "config_sha256": "f" * 64,
                }
                for dataset in DATASETS
            },
        }
        manifest = build_risk0607_manifest(
            risk05_root,
            e1,
            queue_root,
            protocol,
        )
        cls._write_artifacts(
            queue_root,
            manifest,
            anchor_deltas=BASE_ANCHOR_DELTAS,
            full_deltas=BASE_FULL_DELTAS,
        )

    @classmethod
    def _write_artifacts(
        cls,
        queue_root: Path,
        manifest: dict[str, object],
        *,
        anchor_deltas: dict[tuple[str, int], float],
        full_deltas: dict[tuple[str, int], float],
    ) -> None:
        queue_hash = sha256_file(queue_root / "queue" / "queue_seed100.json")
        for task in manifest["tasks"]:
            if task["branch"] != "e1_pass":
                continue
            if task["arm"] == "host":
                delta = 0.0
            else:
                level = int(task["arm"].rsplit("c", 1)[1])
                source = (
                    anchor_deltas
                    if task["arm"].startswith("text_anchor_only")
                    else full_deltas
                )
                delta = source[(task["dataset"], level)]
            validation_ndcg = 0.1 + delta
            test_ndcg = 0.1 + delta
            summary = {
                "best_step": 1000,
                "validation": {
                    "p5": {
                        "hr": [0.0, 0.0, 0.2 + delta],
                        "ndcg": [0.0, 0.0, validation_ndcg],
                    }
                },
                "test": {
                    "p5": {
                        "hr": [0.0, 0.0, 0.2 + delta],
                        "ndcg": [0.0, 0.0, test_ndcg],
                    }
                },
            }
            summary_path = queue_root / task["success_artifacts"][0]
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            artifact_path = queue_root / task["success_artifacts"][1]
            run_dir = artifact_path.parent
            log_path = run_dir / "single_train.log"
            log_path.write_text(
                "AAAI_PILOT_WRAPPER_START\nAAAI_PILOT_WRAPPER_END\n",
                encoding="utf-8",
            )
            task_env = task["env"]
            policy = task_env["AAAI_NULL_CURVE_REFERENCE_POLICY"]
            null_reference: dict[str, object] = {"policy": policy}
            if policy == "frozen_clean_calibration":
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
            gate = task_env.get("AAAI_GATE_DATASET_SCALE")
            artifact = {
                "schema_version": 1,
                "task_id": task["task_id"],
                "status": "pass",
                "seed": 100,
                "child_exit_code": 0,
                "queue_manifest_sha256": queue_hash,
                "source_revision": task["code_revision"],
                "config_sha256": task["config_sha256"],
                "split_sha256": task["split_sha256"],
                "bank_sha256": task["bank_sha256"],
                "evaluator_version": task["evaluator_version"],
                "selector_version": task["selector_version"],
                "gate_dataset_scale": float(gate) if gate is not None else None,
                "metrics_provenance": {
                    "path": summary_path.relative_to(queue_root).as_posix(),
                    "sha256": sha256_file(summary_path),
                },
                "log_provenance": {
                    "path": log_path.relative_to(queue_root).as_posix(),
                    "sha256": sha256_file(log_path),
                    "size_bytes": log_path.stat().st_size,
                },
                "null_curve_reference": null_reference,
                "selected_metrics": {
                    "best_step": 1000,
                    "validation_hr10": 0.2 + delta,
                    "validation_ndcg10": validation_ndcg,
                    "test_hr10": 0.2 + delta,
                    "test_ndcg10": test_ndcg,
                },
            }
            artifact["artifact_sha256"] = stable_sha256(artifact)
            artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

    def _copy_layout(self, destination: Path) -> Path:
        root = destination / "layout"
        shutil.copytree(self.base_root, root)
        return root

    def _task(self, root: Path, dataset: str, kind: str, level: int | None = None):
        manifest = json.loads(
            (root / "queue-2026-07-12" / "queue" / "queue_seed100.json").read_text(
                encoding="utf-8"
            )
        )
        if kind == "host":
            task_id = f"pilot.e1_pass.{dataset}.host"
        else:
            task_id = f"pilot.e1_pass.{dataset}.{kind}.c{level}"
        return next(task for task in manifest["tasks"] if task["task_id"] == task_id)

    def _set_test_delta(
        self,
        root: Path,
        dataset: str,
        kind: str,
        level: int,
        delta: float,
    ) -> None:
        queue_root = root / "queue-2026-07-12"
        task = self._task(root, dataset, kind, level)
        summary_path = queue_root / task["success_artifacts"][0]
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["test"]["p5"]["ndcg"][2] = 0.1 + delta
        summary_path.write_text(json.dumps(summary), encoding="utf-8")
        artifact_path = queue_root / task["success_artifacts"][1]
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["metrics_provenance"]["sha256"] = sha256_file(summary_path)
        artifact["selected_metrics"]["test_ndcg10"] = 0.1 + delta
        artifact["artifact_sha256"] = stable_sha256(
            {key: value for key, value in artifact.items() if key != "artifact_sha256"}
        )
        artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

    def _build(self, root: Path) -> dict[str, object]:
        return build_artifact_derived_pilot_report(
            root / "queue-2026-07-12",
            risk05_root=root / "risk05-2026-07-12",
            risk_preflight_path=root / "risk_preflight_report.json",
        )

    def test_pass_report_is_derived_from_all_fourteen_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._copy_layout(Path(tmp))
            report = self._build(root)

            self.assertTrue(report["phenomenon_pass"])
            self.assertEqual("artifact_metrics", report["decision_source"])
            self.assertNotIn("metrics", report)
            self.assertEqual(14, len(report["completed_task_ids"]))
            self.assertEqual(14, len(report["artifact_manifests"]))
            association = report["phenomenon_checks"]["spearman_association"]
            self.assertEqual(6, association["point_count"])
            self.assertAlmostEqual(-1.0, association["rho"], places=12)
            self.assertEqual(
                {"validation_hr10", "validation_ndcg10", "test_hr10", "test_ndcg10"},
                set(report["results"]["Beauty"]["host"]["selected_metrics"])
                - {"best_step"},
            )
            self.assertEqual(
                6,
                len(report["phenomenon_checks"]["full_predictions"]["points"]),
            )

    def test_failed_full_prediction_is_visible_and_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._copy_layout(Path(tmp))
            self._set_test_delta(root, "Beauty", "full", 0, 0.0)
            report = self._build(root)

            self.assertFalse(report["phenomenon_pass"])
            prediction = next(
                row
                for row in report["phenomenon_checks"]["full_predictions"]["points"]
                if row["dataset"] == "Beauty" and row["level"] == 0
            )
            self.assertEqual(0.0, prediction["test_delta_ndcg10"])
            self.assertFalse(prediction["passed"])
            self.assertIn("full_predictions", report["failure_reasons"])

    def test_anchor_ordering_failure_is_not_rescued_by_subset_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._copy_layout(Path(tmp))
            for dataset in DATASETS:
                for level, delta in ((0, 0.0), (60, -0.003), (100, -0.006)):
                    self._set_test_delta(root, dataset, "anchor", level, delta)
            report = self._build(root)

            ordering = report["phenomenon_checks"]["anchor_response_ordering"]
            self.assertFalse(ordering["passed"])
            self.assertFalse(any(row["passed"] for row in ordering["datasets"].values()))
            self.assertTrue(
                all(len(row["adjacent_checks"]) == 2 for row in ordering["datasets"].values())
            )

    def test_spearman_failure_uses_all_six_points(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._copy_layout(Path(tmp))
            for dataset in DATASETS:
                for level in PILOT_LEVELS:
                    self._set_test_delta(root, dataset, "anchor", level, 0.0)
            report = self._build(root)

            association = report["phenomenon_checks"]["spearman_association"]
            self.assertEqual(6, association["point_count"])
            self.assertIsNone(association["rho"])
            self.assertFalse(association["passed"])

    def test_worst_anchor_rule_requires_absolute_improvement_or_true_halving(self) -> None:
        small_anchor = {
            ("Beauty", 0): -0.0006,
            ("Beauty", 60): -0.0004,
            ("Beauty", 100): -0.0002,
            ("Steam", 0): -0.0005,
            ("Steam", 60): -0.0003,
            ("Steam", 100): -0.0001,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = self._copy_layout(Path(tmp))
            for (dataset, level), delta in small_anchor.items():
                self._set_test_delta(root, dataset, "anchor", level, delta)
            self._set_test_delta(root, "Beauty", "full", 0, 0.0004)
            report = self._build(root)

            worst = report["phenomenon_checks"]["worst_anchor_improvement"]
            self.assertFalse(worst["passed"])
            self.assertAlmostEqual(0.001, worst["absolute_improvement"], places=12)
            self.assertFalse(worst["passed_absolute_improvement"])
            self.assertFalse(worst["passed_negative_magnitude_halving"])

    def test_missing_or_nonfinite_summary_fails_closed(self) -> None:
        for case in ("missing", "nonfinite"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = self._copy_layout(Path(tmp))
                queue_root = root / "queue-2026-07-12"
                task = self._task(root, "Beauty", "anchor", 0)
                summary_path = queue_root / task["success_artifacts"][0]
                if case == "missing":
                    summary_path.unlink()
                else:
                    summary = json.loads(summary_path.read_text(encoding="utf-8"))
                    summary["test"]["p5"]["ndcg"][2] = float("nan")
                    summary_path.write_text(json.dumps(summary), encoding="utf-8")
                    artifact_path = queue_root / task["success_artifacts"][1]
                    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
                    artifact["metrics_provenance"]["sha256"] = sha256_file(summary_path)
                    artifact["artifact_sha256"] = stable_sha256(
                        {
                            key: value
                            for key, value in artifact.items()
                            if key != "artifact_sha256"
                        }
                    )
                    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
                with self.assertRaises(PilotReportError):
                    self._build(root)

    def test_preflight_hash_tampering_fails_before_epe_is_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._copy_layout(Path(tmp))
            preflight = root / "risk_preflight_report.json"
            payload = json.loads(preflight.read_text(encoding="utf-8"))
            payload["datasets"]["Beauty"]["levels"][0]["epe"] = 999.0
            preflight.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(PilotReportError, "preflight.*hash"):
                self._build(root)

    def test_finalizer_writes_one_report_and_one_original_risk08_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._copy_layout(Path(tmp))
            queue_root = root / "queue-2026-07-12"
            marker = finalize_artifact_derived_risk08(
                queue_root,
                risk05_root=root / "risk05-2026-07-12",
                risk_preflight_path=root / "risk_preflight_report.json",
            )

            self.assertEqual("risk_gated_method", marker["exit"])
            self.assertTrue((queue_root / "reports" / "pilot_report.json").is_file())
            self.assertTrue((queue_root / "markers" / "RISK-08_EXIT.json").is_file())
            with self.assertRaises(FileExistsError):
                finalize_artifact_derived_risk08(
                    queue_root,
                    risk05_root=root / "risk05-2026-07-12",
                    risk_preflight_path=root / "risk_preflight_report.json",
                )

    def test_finalizer_rejects_report_path_outside_dated_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._copy_layout(Path(tmp))
            outside = root / "outside-pilot-report.json"
            with self.assertRaisesRegex(PilotReportError, "inside.*queue"):
                finalize_artifact_derived_risk08(
                    root / "queue-2026-07-12",
                    risk05_root=root / "risk05-2026-07-12",
                    risk_preflight_path=root / "risk_preflight_report.json",
                    report_path=outside,
                )
            self.assertFalse(outside.exists())


if __name__ == "__main__":
    unittest.main()
