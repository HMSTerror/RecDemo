from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from scripts.aaai27_adapters.bank_builder import build_corruption_bank
from scripts.aaai27_adapters.common import load_embedding_payload, load_jsonl_records
from scripts.aaai27_adapters.e01_lockstep_adapter import write_e1_gate_marker
from scripts.aaai27_adapters.evaluator_contract import (
    aggregate_row_metrics,
    load_frozen_protocol,
    select_validation_checkpoint,
)
from scripts.aaai27_adapters.preregistration import build_preregistration
from scripts.aaai27_adapters.preflight import build_risk_preflight
from scripts.aaai27_adapters.proposal_contract import validate_proposal_manifest
from scripts.aaai27_adapters.proposal_records import build_train_proposal_records
from scripts.aaai27_adapters.pilot_adapters import build_pilot_manifest, write_risk08_exit
from scripts.aaai27_queue.models import QueueManifest
from scripts.aaai27_queue.validation import validate_manifest
from scripts.aaai27_adapters.risk_report import build_train_only_risk_report
from scripts.aaai27_adapters.optimizer_contract import compose_optimizer_parameters


class FrontGateAdapterTests(unittest.TestCase):
    def test_pilot_manifest_has_frozen_e1_fail_eight_run_branch_and_pass_fourteen_run_branch(self) -> None:
        protocol = {
            "queue_id": "aaai27-audit-test",
            "created_at": "2026-07-11T02:00:00+08:00",
            "run_root": "/srv/aaai27/run",
            "source_root": "/srv/aaai27/source",
            "source_manifest_sha256": "a" * 64,
            "ledger_path": "/srv/aaai27/ledger.csv",
            "ledger_sha256": "b" * 64,
            "code_revision": "c" * 40,
            "config_sha256": "d" * 64,
            "python_bin": "/srv/aaai27/source/.venv/bin/python",
            "single_train": "/srv/aaai27/source/single_train.py",
            "training_overrides": ["model.hidden_size=256", "training.n_iters=10"],
            "estimated_gpu_hours": {"low": 0.5, "high": 1.0, "output_gib": 0.2},
            "datasets": {
                dataset: {
                    "dataset_dir": f"/srv/data/{dataset}",
                    "split_sha256": "e" * 64,
                    "text_bank_path": f"/srv/data/{dataset}/text_bank.csv",
                    "null_curve_path": f"/srv/data/{dataset}/agreement_null_curves.json",
                    "banks": {
                        str(level): {
                            "embedding_path": f"/srv/banks/{dataset}/{level}/embeddings.pt",
                            "bank_sha256": "f" * 64,
                        }
                        for level in (0, 60, 100)
                    },
                }
                for dataset in ("Beauty", "Steam")
            },
        }
        manifest = build_pilot_manifest(protocol)
        validate_manifest(QueueManifest.from_dict(manifest))
        audit = [task for task in manifest["tasks"] if task["branch"] == "e1_fail_audit"]
        passed = [task for task in manifest["tasks"] if task["branch"] == "e1_pass"]
        self.assertEqual(8, len(audit))
        self.assertEqual(14, len(passed))
        self.assertEqual({100}, {task["seed"] for task in manifest["tasks"]})
        self.assertFalse(any("risk_gated_full" in (task["arm"] or "") for task in audit))
        self.assertTrue(any("text_side.ablation_mode=text_anchor_only" in task["argv"] for task in audit))
        self.assertTrue(all(task["run_dir"].startswith("/srv/aaai27/run/runs/") for task in manifest["tasks"]))

    def test_risk08_exit_is_single_immutable_fail_closed_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            completed_audit = [
                f"pilot.e1_fail_audit.{dataset}.host" for dataset in ("Beauty", "Steam")
            ] + [
                f"pilot.e1_fail_audit.{dataset}.anchor.c{level}"
                for dataset in ("Beauty", "Steam")
                for level in (0, 60, 100)
            ]
            marker = write_risk08_exit(
                root,
                e1_marker={"outcome": "fail", "marker_sha256": "a" * 64},
                pilot_report={
                    "branch": "e1_fail_audit",
                    "completed_task_ids": completed_audit,
                    "phenomenon_pass": True,
                },
            )
            self.assertEqual("audit_only", marker["exit"])
            with self.assertRaises(FileExistsError):
                write_risk08_exit(
                    root,
                    e1_marker={"outcome": "fail"},
                    pilot_report={"branch": "e1_fail_audit", "completed_task_ids": completed_audit, "phenomenon_pass": True},
                )
            with tempfile.TemporaryDirectory() as second:
                stop = write_risk08_exit(
                    Path(second),
                    e1_marker={"outcome": "pass", "marker_sha256": "b" * 64},
                    pilot_report={
                        "branch": "e1_pass",
                        "completed_task_ids": [
                            f"pilot.e1_pass.{dataset}.host" for dataset in ("Beauty", "Steam")
                        ]
                        + [
                            f"pilot.e1_pass.{dataset}.anchor.c{level}"
                            for dataset in ("Beauty", "Steam")
                            for level in (0, 60, 100)
                        ]
                        + [
                            f"pilot.e1_pass.{dataset}.full.c{level}"
                            for dataset in ("Beauty", "Steam")
                            for level in (0, 60, 100)
                        ],
                        "phenomenon_pass": False,
                    },
                )
                self.assertEqual("submission_stop", stop["exit"])

    def test_proposal_records_reuse_production_builder_on_train_df_without_target_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            try:
                import pandas as pd
                import torch
            except ImportError:  # pragma: no cover - production environment supplies pandas and torch
                self.skipTest("pandas and torch are required for production proposal records")
            item_count = 12
            dataset_dir = root / "Beauty"
            dataset_dir.mkdir()
            item_ids = list(range(item_count))
            pd.DataFrame({"item_id": item_ids, "field_coverage": [1.0] * item_count}).to_csv(
                dataset_dir / "text_bank.csv", index=False
            )
            torch.save({"embeddings": torch.eye(item_count), "item_ids": item_ids}, dataset_dir / "embeddings.pt")
            np.save(dataset_dir / "items_pop.npy", np.arange(1, item_count + 1, dtype=np.float32))
            pd.DataFrame(
                {
                    "user": [1, 2, 1],
                    "seq": [[0, 1], [2, 3], [4, 5]],
                    "next": [2, 4, 6],
                }
            ).to_pickle(dataset_dir / "train_data.df")
            null_curve = dataset_dir / "null_curves.json"
            null_curve.write_text(json.dumps({"length_bins": {"2": {"mu": 0.5, "sigma": 0.1}}}), encoding="utf-8")
            p1 = dataset_dir / "core_p1.npy"
            np.save(p1, np.zeros(item_count + 1, dtype=np.float32))
            bank_manifest = dataset_dir / "bank_manifest.json"
            bank_manifest.write_text(
                json.dumps({"dataset": "Beauty", "corruption_level": 0, "bank_sha256": "a" * 64}),
                encoding="utf-8",
            )
            result = build_train_proposal_records(
                dataset="Beauty",
                train_transitions_path=dataset_dir / "train_data.df",
                embeddings_path=dataset_dir / "embeddings.pt",
                text_bank_path=dataset_dir / "text_bank.csv",
                null_curve_path=null_curve,
                core_p1_path=p1,
                bank_manifest_path=bank_manifest,
                output_dir=root / "proposal",
                generation_seed=100,
            )
            rows = [json.loads(line) for line in (root / "proposal" / "train_proposals.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(3, len(rows))
            self.assertEqual(2, len(rows[0]["history_item_ids"]))
            self.assertEqual(2, rows[0]["target_item_id"])
            self.assertEqual(item_count + 1, len(rows[0]["q_core"]))
            self.assertEqual(item_count, len(rows[0]["q_text"]))
            self.assertEqual("v2", result["proposal_manifest"]["kernel_version"])
            self.assertTrue(result["proposal_manifest"]["core_p1_sha256"])

    def test_proposal_manifest_binds_kernel_bank_core_and_train_split(self) -> None:
        valid = {
            "dataset": "Beauty",
            "split_name": "train",
            "split_sha256": "a" * 64,
            "bank_sha256": "b" * 64,
            "text_bank_sha256": "c" * 64,
            "null_curve_sha256": "d" * 64,
            "item_completeness_sha256": "e" * 64,
            "popularity_sha256": "f" * 64,
            "core_p1_sha256": "1" * 64,
            "kernel_version": "v2",
            "temperature": 0.2,
            "g_max": 0.5,
            "generation_seed": 100,
        }
        checked = validate_proposal_manifest(valid, expected_dataset="Beauty", expected_bank_sha256=valid["bank_sha256"])
        self.assertEqual("v2", checked["kernel_version"])
        self.assertTrue(checked["manifest_sha256"])
        with self.assertRaisesRegex(ValueError, "core proposal"):
            invalid = dict(valid)
            invalid.pop("core_p1_sha256")
            validate_proposal_manifest(invalid, expected_dataset="Beauty")
        with self.assertRaisesRegex(ValueError, "train-only"):
            invalid = dict(valid)
            invalid["split_name"] = "validation"
            validate_proposal_manifest(invalid, expected_dataset="Beauty")

    def test_risk_preflight_requires_all_twelve_train_only_banks_and_summarises_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            datasets: dict[str, dict[str, object]] = {}
            for dataset in ("Beauty", "Steam"):
                levels: list[dict[str, object]] = []
                for level in (0, 20, 40, 60, 80, 100):
                    transitions = root / f"{dataset}-level-{level}-train.jsonl"
                    with transitions.open("w", encoding="utf-8") as handle:
                        for index in range(4):
                            q_text = np.full(12, 1.0 / 12.0, dtype=float)
                            q_text[(index + level // 20) % 12] += 0.01
                            q_text /= q_text.sum()
                            handle.write(
                                json.dumps(
                                    {
                                        "row_id": f"{dataset}-{level}-{index}",
                                        "user_id": index,
                                        "target_item_id": index,
                                        "q_text": q_text.tolist(),
                                        "q_core": [1.0 / 12.0] * 12,
                                        "gate": level / 100.0,
                                        "u_tilde": index / 10.0,
                                        "target_popularity": index + 1,
                                        "history_item_ids": [index, (index + 1) % 12],
                                    }
                                )
                                + "\n"
                            )
                    embeddings = root / f"{dataset}-level-{level}-embeddings.npy"
                    np.save(embeddings, np.eye(12, dtype=np.float32))
                    manifest = root / f"{dataset}-level-{level}-bank_manifest.json"
                    manifest.write_text(
                        json.dumps({"dataset": dataset, "corruption_level": level, "bank_sha256": "a" * 64}),
                        encoding="utf-8",
                    )
                    proposal_manifest = root / f"{dataset}-level-{level}-proposal_manifest.json"
                    proposal_manifest.write_text(
                        json.dumps(
                            {
                                "dataset": dataset,
                                "split_name": "train",
                                "split_sha256": "1" * 64,
                                "bank_sha256": "a" * 64,
                                "text_bank_sha256": "2" * 64,
                                "null_curve_sha256": "3" * 64,
                                "item_completeness_sha256": "4" * 64,
                                "popularity_sha256": "5" * 64,
                                "core_p1_sha256": "6" * 64,
                                "kernel_version": "v2",
                                "temperature": 0.2,
                                "g_max": 0.5,
                                "generation_seed": 100,
                            }
                        ),
                        encoding="utf-8",
                    )
                    levels.append(
                        {
                            "level": level,
                            "transitions_path": str(transitions),
                            "embeddings_path": str(embeddings),
                            "bank_manifest_path": str(manifest),
                            "proposal_manifest_path": str(proposal_manifest),
                        }
                    )
                datasets[dataset] = {"levels": levels, "code_revision": "b" * 40}

            report = build_risk_preflight(
                {"datasets": datasets},
                root / "preflight",
                sample_size=2,
                bootstrap_replicates=10,
            )
            self.assertEqual([0, 20, 40, 60, 80, 100], report["datasets"]["Beauty"]["levels_order"])
            self.assertEqual(6, len(report["datasets"]["Steam"]["levels"]))
            self.assertIn("mean_gate", report["datasets"]["Beauty"]["levels"][3])
            self.assertIn("history_length_strata", report["datasets"]["Beauty"]["levels"][0])
            self.assertTrue(report["datasets"]["Beauty"]["source_hashes"]["train_transitions"])
            self.assertTrue((root / "preflight" / "risk_preflight_report.json").exists())

    def test_embedding_payload_audits_item_id_order_and_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            try:
                import torch
            except ImportError:  # pragma: no cover - production environment supplies torch
                self.skipTest("torch is required for production embedding payloads")
            embedding_path = root / "sentence_t5_xl_item_emb.pt"
            item_ids = [10 + index for index in range(10)]
            torch.save({"embeddings": torch.eye(10), "item_ids": item_ids}, embedding_path)
            payload = load_embedding_payload(embedding_path, expected_item_ids=item_ids)
            self.assertEqual(item_ids, payload["item_ids"])
            self.assertTrue(payload["item_id_mapping_sha256"])
            with self.assertRaisesRegex(ValueError, "item ID mapping"):
                load_embedding_payload(embedding_path, expected_item_ids=list(reversed(item_ids)))

    def test_df_transition_loader_maps_project_columns_without_split_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            try:
                import pandas as pd
            except ImportError:  # pragma: no cover - production environment supplies pandas
                self.skipTest("pandas is required for project .df transition artifacts")
            frame = pd.DataFrame(
                {
                    "user": [7, 8],
                    "seq": [[1, 2], [3]],
                    "next": [4, 5],
                },
                index=[31, 32],
            )
            source = root / "train_data.df"
            frame.to_pickle(source)
            records = load_jsonl_records(source)
            self.assertEqual(
                [
                    {"row_id": "31", "user_id": 7, "history_item_ids": [1, 2], "target_item_id": 4},
                    {"row_id": "32", "user_id": 8, "history_item_ids": [3], "target_item_id": 5},
                ],
                records,
            )

    def test_optimizer_contract_includes_graph_p1_once_for_canonical_ownership(self) -> None:
        class Model:
            def __init__(self) -> None:
                self.model_parameter = object()

            def parameters(self):
                return iter((self.model_parameter,))

        class Graph:
            def __init__(self) -> None:
                self.p1 = object()

        class Noise:
            def parameters(self):
                return iter(())

        model = Model()
        graph = Graph()
        parameters = compose_optimizer_parameters(model, graph, Noise())
        self.assertEqual([model.model_parameter, graph.p1], parameters)
    def make_protocol_dataset(self, root: Path, rows: int = 5) -> Path:
        dataset = root / "Beauty"
        dataset.mkdir()
        protocol = {
            "dataset": "Beauty",
            "counts": {"item_num": 12, "train_rows": rows, "val_rows": 2, "test_rows": 2},
            "padding_item_id": 12,
            "pseudo_item_id": 13,
        }
        (dataset / "protocol.json").write_text(json.dumps(protocol), encoding="utf-8")
        for split, count in (("train", rows), ("val", 2), ("test", 2)):
            with (dataset / f"{split}_data.jsonl").open("w", encoding="utf-8") as handle:
                for index in range(count):
                    handle.write(json.dumps({"row_id": f"{split}-{index}", "user_id": index % 2}) + "\n")
        return dataset

    def make_transitions(self, root: Path, include_users: bool = True) -> Path:
        path = root / "train_transitions.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for index in range(8):
                payload = {
                    "row_id": f"train-{index}",
                    "history_item_ids": [index % 12],
                    "target_item_id": (index + 1) % 12,
                    "q_text": [0.02, 0.05, 0.08, 0.11, 0.14, 0.17, 0.10, 0.08, 0.07, 0.06, 0.04, 0.08],
                    "q_core": [1.0 / 12.0] * 12,
                }
                if include_users:
                    payload["user_id"] = index % 2
                handle.write(json.dumps(payload) + "\n")
        return path

    def test_evaluator_uses_frozen_splits_row_weighting_and_validation_only_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dataset = self.make_protocol_dataset(Path(tmp))
            contract = load_frozen_protocol(dataset)
            self.assertEqual("e0_full_tail_v2", contract.evaluator_version)
            self.assertEqual(5, contract.expected_rows["train"])
            self.assertEqual(2, contract.expected_rows["test"])
            self.assertEqual(0.75, aggregate_row_metrics([{"rows": 1, "ndcg10": 0.5}, {"rows": 3, "ndcg10": 0.8333333333333334}])["ndcg10"])
            selected = select_validation_checkpoint(
                [
                    {"checkpoint": "a", "validation_ndcg10": 0.2},
                    {"checkpoint": "b", "validation_ndcg10": 0.3},
                ]
            )
            self.assertEqual("b", selected["checkpoint"])
            with self.assertRaisesRegex(ValueError, "test metric"):
                select_validation_checkpoint([{"checkpoint": "a", "test_ndcg10": 0.9}])

    def test_e1_fail_marker_is_single_immutable_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "e1"
            trace = {"status": "fail", "first_divergence": {"step": 0, "key": "optimizer"}}
            marker = write_e1_gate_marker(output, trace, source_revision="a" * 40)
            self.assertEqual("fail", marker["outcome"])
            self.assertTrue((output / "RISK-02_FAIL.json").exists())
            self.assertFalse((output / "RISK-02_PASS.json").exists())
            with self.assertRaises(FileExistsError):
                write_e1_gate_marker(output, trace, source_revision="a" * 40)

    def test_train_only_risk_report_has_exact_epe_and_positive_neighborhood(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            transitions = self.make_transitions(root)
            embeddings = root / "embeddings.npy"
            np.save(embeddings, np.eye(12, dtype=np.float32))
            report = build_train_only_risk_report(
                transitions,
                embeddings,
                output_dir=root / "risk",
                sample_size=4,
                sampling_seed=7,
                bootstrap_replicates=50,
            )
            q_text = np.asarray([0.02, 0.05, 0.08, 0.11, 0.14, 0.17, 0.10, 0.08, 0.07, 0.06, 0.04, 0.08])
            expected_epe = float(np.mean([np.log(q_text[row["target_item_id"]]) - np.log(1.0 / 12.0) for row in report["rows"]]))
            self.assertAlmostEqual(expected_epe, report["point_estimates"]["epe"], places=7)
            self.assertEqual(4, report["protocol"]["sample_size"])
            self.assertEqual("train", report["protocol"]["split_name"])
            self.assertEqual(10, report["protocol"]["pne_neighborhood_size"])
            self.assertIn("pne10", report["point_estimates"])
            self.assertEqual(50, report["uncertainty"]["bootstrap_replicates"])
            self.assertTrue(report["provenance"]["transition_sha256"])
            with self.assertRaisesRegex(ValueError, "train-only"):
                build_train_only_risk_report(
                    transitions,
                    embeddings,
                    output_dir=root / "risk2",
                    sample_size=4,
                    split_name="test",
                )

    def test_risk_report_without_user_ids_is_explicitly_not_estimable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            np.save(root / "embeddings.npy", np.eye(12, dtype=np.float32))
            report = build_train_only_risk_report(
                self.make_transitions(root, include_users=False),
                root / "embeddings.npy",
                output_dir=root / "risk",
                sample_size=4,
            )
            self.assertEqual("not_estimable", report["uncertainty"]["user_clustered"]["epe"]["status"])

    def test_risk_report_excludes_the_optional_pseudo_item_coordinate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            transitions = self.make_transitions(root)
            lines = transitions.read_text(encoding="utf-8").splitlines()
            converted = []
            for line in lines:
                payload = json.loads(line)
                payload["q_text"].append(0.5)
                payload["q_core"].append(0.5)
                converted.append(json.dumps(payload))
            transitions.write_text("\n".join(converted) + "\n", encoding="utf-8")
            np.save(root / "embeddings.npy", np.eye(12, dtype=np.float32))
            report = build_train_only_risk_report(
                transitions,
                root / "embeddings.npy",
                output_dir=root / "risk",
                sample_size=4,
            )
            self.assertEqual(12, report["protocol"]["real_catalog_item_count"])
            self.assertTrue(report["protocol"]["pseudo_item_coordinate_excluded"])

    def test_corruption_bank_preserves_norms_and_exact_selected_fraction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clean = root / "clean.npy"
            matrix = np.arange(30, dtype=np.float32).reshape(10, 3) + 1
            np.save(clean, matrix)
            train = root / "train.jsonl"
            with train.open("w", encoding="utf-8") as handle:
                for item_id in range(10):
                    for _ in range(item_id + 1):
                        handle.write(json.dumps({"target_item_id": item_id}) + "\n")
            report = build_corruption_bank(
                clean,
                train,
                output_dir=root / "bank",
                dataset="Steam",
                corruption_level=60,
                corruption_seed=100,
                strata_count=3,
            )
            corrupted = np.load(root / "bank" / "embeddings.npy")
            np.testing.assert_allclose(np.linalg.norm(matrix, axis=1), np.linalg.norm(corrupted, axis=1), rtol=0.0, atol=5e-6)
            self.assertEqual(6, report["permutation"]["selected_count"])
            self.assertEqual(60, report["corruption_level"])
            self.assertEqual("Steam", report["dataset"])
            with self.assertRaises(FileExistsError):
                build_corruption_bank(clean, train, output_dir=root / "bank", dataset="Steam", corruption_level=60, corruption_seed=100)

    def test_corruption_bank_preserves_noncanonical_item_id_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            try:
                import torch
            except ImportError:  # pragma: no cover - production environment supplies torch
                self.skipTest("torch is required for production embedding payloads")
            item_ids = [100 + index for index in range(10)]
            clean = root / "clean.pt"
            torch.save({"embeddings": torch.arange(30, dtype=torch.float32).reshape(10, 3) + 1, "item_ids": item_ids}, clean)
            train = root / "train.jsonl"
            with train.open("w", encoding="utf-8") as handle:
                for item_id in item_ids:
                    handle.write(json.dumps({"target_item_id": item_id}) + "\n")
            report = build_corruption_bank(
                clean,
                train,
                output_dir=root / "bank",
                dataset="Beauty",
                corruption_level=60,
                corruption_seed=100,
                expected_item_ids=item_ids,
            )
            self.assertEqual(item_ids, json.loads((root / "bank" / "item_ids.json").read_text(encoding="utf-8")))
            self.assertEqual(item_ids, report["item_id_mapping"]["item_ids"])
            flattened_strata = [item_id for stratum in report["strata"] for item_id in stratum["item_ids"]]
            self.assertEqual(sorted(item_ids), sorted(flattened_strata))
            self.assertTrue(report["item_id_mapping"]["sha256"])
            torch_payload = torch.load(root / "bank" / "embeddings.pt", map_location="cpu", weights_only=False)
            self.assertEqual(item_ids, [int(value) for value in torch_payload["item_ids"]])
            self.assertEqual([10, 3], list(torch_payload["embeddings"].shape))

    def test_preregistration_freezes_thresholds_or_writes_no_go(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preflight = {
                "schema_version": 1,
                "datasets": {
                    "Beauty": {"clean_epe": 0.0, "levels": [{"level": 0, "epe": 0.0}, {"level": 20, "epe": 0.002}, {"level": 40, "epe": 0.004}, {"level": 60, "epe": 0.01}, {"level": 80, "epe": 0.015}, {"level": 100, "epe": 0.02}]},
                    "Steam": {"clean_epe": 0.0, "levels": [{"level": 0, "epe": 0.0}, {"level": 20, "epe": 0.5}, {"level": 40, "epe": 0.8}, {"level": 60, "epe": 1.0}, {"level": 80, "epe": 1.5}, {"level": 100, "epe": 2.0}]},
                },
                "source_hashes": {"banks": "a" * 64, "code": "b" * 64},
            }
            result = build_preregistration(preflight, root / "prereg", generated_at="2026-07-11T02:00:00+08:00")
            self.assertEqual("pass", result["range_gate"]["status"])
            self.assertTrue((root / "prereg" / "RISK-05_PASS.json").exists())
            self.assertEqual(-0.5, result["frozen_thresholds"]["spearman_rho_max"])
            with self.assertRaisesRegex(ValueError, "validation/test"):
                bad = dict(preflight)
                bad["validation_metric"] = 1
                build_preregistration(bad, root / "bad", generated_at="2026-07-11T02:00:00+08:00")


if __name__ == "__main__":
    unittest.main()
