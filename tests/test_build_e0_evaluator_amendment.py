import csv
import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path


from scripts.build_e0_evaluator_amendment import (
    build_amendment,
    gate1_verdict,
    publish_directory_no_clobber,
    prediction_outcome,
)


DATASET_ROWS = {
    "Steam": 80651,
    "ML1M": 85405,
    "Beauty": 2237,
    "ATG": 1942,
}

CATALOG_ITEMS = {
    "Steam": 9265,
    "ML1M": 3706,
    "Beauty": 12101,
    "ATG": 11921,
}

EXPECTED_MATRIX = {
    "host_steam": "Steam",
    "host_ml1m": "ML1M",
    "host_beauty": "Beauty",
    "host_atg": "ATG",
    "ours_full_steam": "Steam",
    "ours_full_ml1m": "ML1M",
    "ours_full_beauty": "Beauty",
    "ours_full_atg": "ATG",
    "global_p_steam": "Steam",
    "u_shuffle_steam": "Steam",
    "text_anchor_only_steam": "Steam",
    "global_p_beauty": "Beauty",
    "u_shuffle_beauty": "Beauty",
    "text_anchor_only_beauty": "Beauty",
    "diffurec_steam": "Steam",
    "diffurec_ml1m": "ML1M",
    "diffurec_beauty": "Beauty",
    "diffurec_atg": "ATG",
}

SHARD_ITEMS = {
    0: [
        "host_beauty",
        "diffurec_steam",
        "host_steam",
        "ours_full_steam",
        "global_p_steam",
        "u_shuffle_steam",
        "text_anchor_only_steam",
        "ours_full_beauty",
        "global_p_beauty",
        "u_shuffle_beauty",
        "text_anchor_only_beauty",
    ],
    1: [
        "diffurec_beauty",
        "diffurec_ml1m",
        "diffurec_atg",
        "host_ml1m",
        "ours_full_ml1m",
        "host_atg",
        "ours_full_atg",
    ],
}

HOST_NEW = {"Steam": 0.100, "ML1M": 0.200, "Beauty": 0.300, "ATG": 0.400}
OURS_NEW = {"Steam": 0.104, "ML1M": 0.195, "Beauty": 0.305, "ATG": 0.389}
HOST_OLD = {"Steam": 0.099, "ML1M": 0.199, "Beauty": 0.299, "ATG": 0.399}
LEGACY_DELTAS = {
    "Steam": 0.002015202301118,
    "ML1M": -0.015133045070724,
    "Beauty": -0.003858886468956,
    "ATG": -0.011410105406507,
}
OURS_OLD = {
    dataset: HOST_OLD[dataset] + LEGACY_DELTAS[dataset]
    for dataset in DATASET_ROWS
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class E0EvaluatorAmendmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.input_root = self.root / "final"
        self.output_dir = self.root / "amendment"
        self.gate0_original_path = self.root / "gate0_original.json"
        self.gate0_v2_path = self.root / "gate0_v2.json"
        self.gate1_path = self.root / "gate1.json"
        self.diffurec_csv_path = self.root / "diffurec.csv"
        self.revision = "a" * 40
        self._write_gate_inputs()
        self._write_matrix()
        self._write_diffurec_table()
        self.execution_logs = self._write_execution_logs()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_gate_inputs(self) -> None:
        write_json(
            self.gate0_original_path,
            {
                "criterion": {
                    "ml1m_abs_median_max": 0.5,
                    "steam_median_gt_ml1m": True,
                    "beauty_median_gt_ml1m": True,
                },
                "datasets": [
                    {"dataset": "ML1M", "median_u_tilde": 1.427543},
                    {"dataset": "Steam", "median_u_tilde": 0.107291},
                    {"dataset": "Beauty", "median_u_tilde": 0.798168},
                    {"dataset": "ATG", "median_u_tilde": 0.724168},
                ],
                "gate0_verdict": "fail",
                "gate0_reasons": ["frozen failure"],
            },
        )
        write_json(
            self.gate0_v2_path,
            {
                "criterion_name": "Gate 0-v2 frozen criterion (spec 7.4)",
                "criterion_pass": False,
                "conditions": [
                    {"id": "condition_1_ml1m_is_max", "passed": True},
                    {"id": "condition_2_ml1m_phi_lte_0_2", "passed": True},
                    {"id": "condition_3_two_non_ml1m_phi_ge_0_5", "passed": False},
                ],
                "datasets": [
                    {"dataset": "Steam", "u_ds_popularity": 0.56956625, "phi_u_ds": 1.0},
                    {"dataset": "ML1M", "u_ds_popularity": 0.75353875, "phi_u_ds": 0.0},
                    {"dataset": "Beauty", "u_ds_popularity": 0.7124275, "phi_u_ds": 0.0},
                    {"dataset": "ATG", "u_ds_popularity": 0.6882625, "phi_u_ds": 0.117375},
                ],
            },
        )
        archived_rows = []
        for dataset in DATASET_ROWS:
            outcome = prediction_outcome(dataset, LEGACY_DELTAS[dataset])
            archived_rows.append(
                {
                    "dataset": dataset,
                    "core_test_p2_ndcg10": HOST_OLD[dataset],
                    "current_test_p2_ndcg10": OURS_OLD[dataset],
                    "delta_test_p2_ndcg10": LEGACY_DELTAS[dataset],
                    "dataset_verdict": outcome,
                }
            )
        write_json(
            self.gate1_path,
            {
                "gate1": {
                    "dataset": "ML1M",
                    "delta_test_p2_ndcg10": LEGACY_DELTAS["ML1M"],
                    "pass_threshold": -0.01,
                    "diagnostic_threshold": -0.03,
                    "verdict": "fail_no_diagnostic",
                },
                "datasets": archived_rows,
            },
        )

    def _new_ndcg(self, artifact_id: str, dataset: str) -> float:
        if artifact_id.startswith("host_"):
            return HOST_NEW[dataset]
        if artifact_id.startswith("ours_full_"):
            return OURS_NEW[dataset]
        ordinal = sorted(EXPECTED_MATRIX).index(artifact_id) + 1
        return 0.05 + ordinal / 1000.0

    def _old_ndcg(self, artifact_id: str, dataset: str, new_ndcg: float) -> float:
        if artifact_id.startswith("host_"):
            return HOST_OLD[dataset]
        if artifact_id.startswith("ours_full_"):
            return OURS_OLD[dataset]
        return new_ndcg - 0.001

    def _write_matrix(self) -> None:
        split_paths: dict[str, Path] = {}
        for dataset in DATASET_ROWS:
            split_path = self.root / "splits" / dataset / "test_data.df"
            split_path.parent.mkdir(parents=True, exist_ok=True)
            split_path.write_bytes(("split:" + dataset).encode("utf-8"))
            split_paths[dataset] = split_path

        runner_path = self.root / "runner" / "run_close04_diffurec.py"
        runner_path.parent.mkdir(parents=True, exist_ok=True)
        runner_path.write_text("# frozen runner\n", encoding="utf-8")

        for artifact_id, dataset in EXPECTED_MATRIX.items():
            is_diffurec = artifact_id.startswith("diffurec_")
            is_host = artifact_id.startswith("host_")
            new_ndcg = self._new_ndcg(artifact_id, dataset)
            new_hr = new_ndcg + 0.02
            old_ndcg = self._old_ndcg(artifact_id, dataset, new_ndcg)
            old_hr = new_hr - 0.002

            source_dir = self.root / "frozen" / artifact_id
            checkpoint_path = source_dir / "checkpoint_best.pt"
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            checkpoint_path.write_bytes(("checkpoint:" + artifact_id).encode("utf-8"))
            summary_path = source_dir / "best_summary.json"
            if is_diffurec:
                summary = {
                    "selector": {"metric": "NDCG@10", "best_epoch": 80},
                    "test": {"HR@10": old_hr, "NDCG@10": old_ndcg},
                }
            else:
                summary = {
                    "best_step": 100,
                    "test": {
                        "p2": {
                            "hr": [0.0, 0.0, old_hr, 0.0, 0.0],
                            "ndcg": [0.0, 0.0, old_ndcg, 0.0, 0.0],
                        }
                    },
                }
            write_json(summary_path, summary)

            manifest_path = source_dir / "frozen_manifest.json"
            if not is_host:
                write_json(
                    manifest_path,
                    {
                        "dataset": dataset,
                        "random_seed": 100,
                        "item_num": CATALOG_ITEMS[dataset],
                        "summary_path": str(summary_path),
                    },
                )

            sources = {
                "checkpoint_path": str(checkpoint_path),
                "checkpoint_sha256": sha256(checkpoint_path),
                "summary_path": str(summary_path),
                "summary_sha256": sha256(summary_path),
                "split_path": str(split_paths[dataset]),
                "split_sha256": sha256(split_paths[dataset]),
            }
            if is_diffurec:
                sources.update(
                    {
                        "manifest_path": str(manifest_path),
                        "manifest_sha256": sha256(manifest_path),
                        "upstream_revision": "b" * 40,
                        "evaluator_runner_path": str(runner_path),
                        "evaluator_runner_sha256": sha256(runner_path),
                    }
                )
            else:
                log_path = source_dir / "train.log"
                log_path.write_text("frozen training log\n", encoding="utf-8")
                sources.update({"log_path": str(log_path), "log_sha256": sha256(log_path)})
                if not is_host:
                    sources.update(
                        {
                            "manifest_path": str(manifest_path),
                            "manifest_sha256": sha256(manifest_path),
                        }
                    )

            contract = {
                "version": "e0_full_tail_v2",
                "aggregation_weight": "row",
                "tail_batch_included": True,
                "eval_seed": 100,
                "candidate_policy": (
                    "exclude-padding-id-0" if is_diffurec else "first-M-zero-based"
                ),
            }
            if not is_diffurec:
                model_count = CATALOG_ITEMS[dataset]
                legacy_mismatch = artifact_id == "host_atg"
                if legacy_mismatch:
                    model_count = 11924
                contract.update(
                    {
                        "valid_item_count": CATALOG_ITEMS[dataset],
                        "model_item_count": model_count,
                        "non_candidate_model_item_slots": model_count - CATALOG_ITEMS[dataset],
                        "legacy_model_catalog_mismatch_authorized": legacy_mismatch,
                        "test_item_domain": {
                            "history_pad_value": CATALOG_ITEMS[dataset],
                            "history_pad_occurrences": 4,
                            "history_pad_rows": 2,
                            "history_pad_maps_to_non_candidate_model_slot": legacy_mismatch,
                            "history_pad_semantics": (
                                "ordinary_non_candidate_legacy_model_slot"
                                if legacy_mismatch
                                else "disliked_state"
                            ),
                            "minimum_history_item_id": 0,
                            "maximum_history_item_id": CATALOG_ITEMS[dataset],
                            "minimum_target_item_id": 0,
                            "maximum_target_item_id": CATALOG_ITEMS[dataset] - 1,
                        },
                    }
                )

            payload = {
                "schema_version": 1,
                "method_id": "diffurec" if is_diffurec else artifact_id,
                "dataset": dataset,
                "random_seed": 100,
                "checkpoint_selector_protocol": (
                    "legacy_equal_batch_mean_validation"
                    if is_diffurec
                    else "legacy_tail_skipping_validation"
                ),
                "selection_bias_not_recomputed": True,
                "metric_contract": contract,
                "test": {
                    "expected_rows": DATASET_ROWS[dataset],
                    "evaluated_rows": DATASET_ROWS[dataset],
                    "hr10": new_hr,
                    "ndcg10": new_ndcg,
                },
                "sources": sources,
            }
            if is_diffurec:
                payload.update(
                    {
                        "best_epoch": 80,
                        "training_wrapper_revision": "c" * 40,
                        "model_config": {"hidden_size": 128},
                    }
                )
                payload["test"]["metrics"] = {"HR@10": new_hr, "NDCG@10": new_ndcg}
            else:
                payload.update({"strength": "p2", "best_step": 100})
                payload["test"]["hr"] = [0.0, 0.0, new_hr, 0.0, 0.0]
                payload["test"]["ndcg"] = [0.0, 0.0, new_ndcg, 0.0, 0.0]

            output_path = self.input_root / artifact_id / f"{artifact_id}_e0_eval.json"
            write_json(output_path, payload)

    def _write_diffurec_table(self) -> None:
        rows = []
        for dataset in DATASET_ROWS:
            artifact_id = "diffurec_" + dataset.lower()
            payload_path = next((self.input_root / artifact_id).glob("*.json"))
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            summary = json.loads(Path(payload["sources"]["summary_path"]).read_text(encoding="utf-8"))
            rows.append(
                {
                    "dataset": dataset,
                    "baseline_method": "DiffuRec",
                    "baseline_seed": 100,
                    "baseline_summary_path": payload["sources"]["summary_path"],
                    "baseline_selector_metric": "NDCG@10",
                    "baseline_best_epoch": 80,
                    "baseline_test_hr10": summary["test"]["HR@10"],
                    "baseline_test_ndcg10": summary["test"]["NDCG@10"],
                }
            )
        write_csv(self.diffurec_csv_path, rows)

    def _write_execution_logs(self) -> list[Path]:
        paths = []
        for shard, artifact_ids in SHARD_ITEMS.items():
            path = self.root / "logs" / f"e0_shard{shard}_gpu{shard}.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            lines = [
                f"E0_SHARD_START shard={shard} gpu={shard} code_revision={self.revision}"
            ]
            for artifact_id in artifact_ids:
                dataset = EXPECTED_MATRIX[artifact_id]
                family = "diffurec" if artifact_id.startswith("diffurec_") else "core"
                lines.append(
                    f"E0_ITEM_START id={artifact_id} dataset={dataset} family={family}"
                )
                result_path = next((self.input_root / artifact_id).glob("*.json"))
                lines.append(f'  "output_path": "{result_path}"')
                lines.append(
                    f"E0_ITEM_FINISH id={artifact_id} dataset={dataset} family={family}"
                )
            lines.append(f"E0_SHARD_DONE shard={shard} gpu={shard}")
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            paths.append(path)
        return paths

    def _build(self) -> dict:
        return build_amendment(
            input_root=self.input_root,
            output_dir=self.output_dir,
            execution_log_paths=self.execution_logs,
            gate0_original_path=self.gate0_original_path,
            gate0_v2_path=self.gate0_v2_path,
            legacy_gate1_report_path=self.gate1_path,
            diffurec_comparison_path=self.diffurec_csv_path,
            generated_at="2026-07-10T16:00:00+08:00",
        )

    def test_builds_auditable_package_and_rereads_all_frozen_gates(self) -> None:
        report = self._build()

        self.assertEqual(18, report["matrix_validation"]["artifact_count"])
        self.assertTrue(report["matrix_validation"]["all_contract_checks_pass"])
        self.assertEqual(self.revision, report["execution"]["code_revision"])
        self.assertEqual("fail", report["gate_reread"]["gate0_original"]["corrected_verdict"])
        self.assertFalse(report["gate_reread"]["gate0_original"]["verdict_flipped"])
        self.assertEqual("fail", report["gate_reread"]["gate0_v2"]["corrected_verdict"])
        self.assertFalse(report["gate_reread"]["gate0_v2"]["verdict_flipped"])
        gate1 = report["gate_reread"]["gate1_ml1m"]
        self.assertEqual("fail_no_diagnostic", gate1["old_verdict"])
        self.assertEqual("pass", gate1["corrected_verdict"])
        self.assertTrue(gate1["verdict_flipped"])
        self.assertEqual(
            "legacy_training_padding_semantics_not_protocol_aligned",
            report["comparability_limitations"]["host_atg"],
        )
        self.assertEqual(
            "confirmed_under_e0_corrected_test_contract",
            report["diffurec_comparability"]["status"],
        )

        with (self.output_dir / "e0_old_new_metrics.csv").open(
            "r", encoding="utf-8", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(18, len(rows))
        self.assertTrue((self.output_dir / "provenance" / "e0_results" / "host_atg.json").is_file())
        self.assertTrue((self.output_dir / "provenance" / "execution_logs" / "shard0.log").is_file())
        self.assertTrue((self.output_dir / "provenance" / "execution_logs" / "shard1.log").is_file())
        self.assertTrue((self.output_dir / "provenance_manifest.json").is_file())
        self.assertTrue((self.output_dir / "SHA256SUMS").is_file())
        self.assertTrue(
            (self.output_dir / "provenance" / "code" / "build_e0_evaluator_amendment.py").is_file()
        )
        self.assertTrue(
            (self.output_dir / "provenance" / "code" / "evaluate_frozen_checkpoint.py").is_file()
        )
        self.assertTrue(
            (self.output_dir / "provenance" / "code" / "run_e0_fulltail_matrix.sh").is_file()
        )

        combined_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                self.output_dir / "e0_evaluator_amendment.md",
                self.output_dir / "e0_evaluator_amendment_zh.md",
            )
        ).lower()
        for forbidden in (
            "significant",
            "statistically equivalent",
            "within noise",
            "untouched final holdout",
            "adaptive-backoff",
        ):
            self.assertNotIn(forbidden, combined_text)

    def test_missing_matrix_member_is_a_hard_failure(self) -> None:
        next((self.input_root / "host_atg").glob("*.json")).unlink()
        with self.assertRaisesRegex(ValueError, "E0 matrix mismatch"):
            self._build()
        self.assertFalse(self.output_dir.exists())

    def test_requires_two_complete_same_revision_execution_logs(self) -> None:
        text = self.execution_logs[1].read_text(encoding="utf-8")
        self.execution_logs[1].write_text(
            text.replace("E0_SHARD_DONE shard=1 gpu=1\n", ""), encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "E0_SHARD_DONE"):
            self._build()
        self.execution_logs[1].write_text(
            text.replace(self.revision, "d" * 40), encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "code revision mismatch"):
            self._build()

    def test_execution_logs_must_bind_the_exact_result_files(self) -> None:
        text = self.execution_logs[0].read_text(encoding="utf-8")
        self.execution_logs[0].write_text(
            text.replace(str(self.input_root), str(self.root / "other-final"), 1),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "execution output path mismatch"):
            self._build()

    def test_execution_lifecycle_order_is_strict(self) -> None:
        lines = self.execution_logs[0].read_text(encoding="utf-8").splitlines()
        start = lines.pop(0)
        done = lines.pop(-1)
        self.execution_logs[0].write_text(
            "\n".join([done, *lines, start]) + "\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "execution lifecycle order"):
            self._build()
        self.assertFalse(self.output_dir.exists())

    def test_gate1_top_level_record_must_bind_to_archived_ml1m_row(self) -> None:
        payload = json.loads(self.gate1_path.read_text(encoding="utf-8"))
        payload["gate1"]["dataset"] = "Steam"
        write_json(self.gate1_path, payload)
        with self.assertRaisesRegex(ValueError, "Gate-1 dataset mismatch"):
            self._build()

        self._write_gate_inputs()
        payload = json.loads(self.gate1_path.read_text(encoding="utf-8"))
        payload["gate1"]["delta_test_p2_ndcg10"] = -0.02
        write_json(self.gate1_path, payload)
        with self.assertRaisesRegex(ValueError, "Gate-1 delta mismatch"):
            self._build()
        self.assertFalse(self.output_dir.exists())

    def test_same_named_execution_logs_archive_by_validated_shard(self) -> None:
        renamed = []
        for shard, source in enumerate(self.execution_logs):
            destination = self.root / f"source-{shard}" / "same.log"
            destination.parent.mkdir(parents=True)
            destination.write_bytes(source.read_bytes())
            renamed.append(destination)
        self.execution_logs = renamed

        self._build()

        archive_root = self.output_dir / "provenance" / "execution_logs"
        self.assertEqual(self.execution_logs[0].read_bytes(), (archive_root / "shard0.log").read_bytes())
        self.assertEqual(self.execution_logs[1].read_bytes(), (archive_root / "shard1.log").read_bytes())
        manifest = json.loads(
            (self.output_dir / "provenance_manifest.json").read_text(encoding="utf-8")
        )
        relative_paths = [entry["relative_path"] for entry in manifest["entries"]]
        self.assertEqual(len(relative_paths), len(set(relative_paths)))

    def test_rejects_wrong_method_identity_strength_or_selector(self) -> None:
        path = next((self.input_root / "global_p_steam").glob("*.json"))
        original = path.read_text(encoding="utf-8")
        mutations = (
            ("method_id", "ours_full_steam", "method identity mismatch"),
            ("strength", "p5", "strength mismatch"),
            (
                "checkpoint_selector_protocol",
                "other",
                "selector protocol mismatch",
            ),
        )
        for key, value, error in mutations:
            with self.subTest(key=key):
                payload = json.loads(original)
                payload[key] = value
                write_json(path, payload)
                with self.assertRaisesRegex(ValueError, error):
                    self._build()
                path.write_text(original, encoding="utf-8")

    def test_rejects_row_split_summary_or_checkpoint_hash_mismatch(self) -> None:
        path = next((self.input_root / "ours_full_steam").glob("*.json"))
        original = path.read_text(encoding="utf-8")

        payload = json.loads(original)
        payload["test"]["evaluated_rows"] -= 1
        write_json(path, payload)
        with self.assertRaisesRegex(ValueError, "row count mismatch"):
            self._build()

        path.write_text(original, encoding="utf-8")
        payload = json.loads(original)
        payload["sources"]["split_sha256"] = "f" * 64
        write_json(path, payload)
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            self._build()

        path.write_text(original, encoding="utf-8")
        payload = json.loads(original)
        Path(payload["sources"]["summary_path"]).write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            self._build()

    def test_rejects_diffurec_table_or_gate_threshold_drift(self) -> None:
        with self.diffurec_csv_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        rows[0]["baseline_test_ndcg10"] = "0.999"
        write_csv(self.diffurec_csv_path, rows)
        with self.assertRaisesRegex(ValueError, "DiffuRec comparison mismatch"):
            self._build()

        self._write_diffurec_table()
        gate1 = json.loads(self.gate1_path.read_text(encoding="utf-8"))
        gate1["gate1"]["pass_threshold"] = -0.02
        write_json(self.gate1_path, gate1)
        with self.assertRaisesRegex(ValueError, "Gate-1 threshold drift"):
            self._build()

    def test_rejects_inconsistent_gate0_or_nonfinite_metrics(self) -> None:
        gate0 = json.loads(self.gate0_v2_path.read_text(encoding="utf-8"))
        gate0["criterion_pass"] = True
        write_json(self.gate0_v2_path, gate0)
        with self.assertRaisesRegex(ValueError, "Gate 0-v2 verdict mismatch"):
            self._build()

        self._write_gate_inputs()
        path = next((self.input_root / "host_beauty").glob("*.json"))
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["test"]["ndcg10"] = math.nan
        write_json(path, payload)
        with self.assertRaisesRegex(ValueError, "finite metric"):
            self._build()

    def test_output_directory_is_no_clobber(self) -> None:
        self.output_dir.mkdir(parents=True)
        (self.output_dir / "existing.txt").write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(FileExistsError, "already exists"):
            self._build()
        self.assertEqual("keep", (self.output_dir / "existing.txt").read_text(encoding="utf-8"))

    def test_atomic_publication_refuses_a_target_created_after_staging(self) -> None:
        staging = self.root / "ready-staging"
        destination = self.root / "raced-destination"
        staging.mkdir()
        destination.mkdir()
        (staging / "new.txt").write_text("new", encoding="utf-8")
        (destination / "keep.txt").write_text("keep", encoding="utf-8")

        with self.assertRaises(FileExistsError):
            publish_directory_no_clobber(staging, destination)

        self.assertEqual("keep", (destination / "keep.txt").read_text(encoding="utf-8"))
        self.assertEqual("new", (staging / "new.txt").read_text(encoding="utf-8"))

    def test_frozen_threshold_boundaries_remain_strict(self) -> None:
        self.assertEqual("miss", prediction_outcome("Steam", 0.0))
        self.assertEqual("full_hit", prediction_outcome("Steam", 0.003))
        self.assertEqual("miss", prediction_outcome("Beauty", 0.01))
        self.assertEqual("miss", prediction_outcome("Beauty", -0.01))
        self.assertEqual("fail_no_diagnostic", gate1_verdict(-0.01))
        self.assertEqual("diagnostic_allowed", gate1_verdict(-0.03))


if __name__ == "__main__":
    unittest.main()
