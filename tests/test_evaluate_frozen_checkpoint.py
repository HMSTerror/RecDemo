import importlib.util
import hashlib
import inspect
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import torch


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "evaluate_frozen_checkpoint.py"


def load_module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"missing script: {MODULE_PATH}")
    spec = importlib.util.spec_from_file_location("evaluate_frozen_checkpoint", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class EvaluateFrozenCheckpointTests(unittest.TestCase):
    def test_separates_legacy_model_vocabulary_from_real_candidate_catalog(self) -> None:
        module = load_module()
        self.assertTrue(hasattr(module, "resolve_item_count_contract"))
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dataset_dir = root / "ATG"
            output_dir = root / "output"
            dataset_dir.mkdir(parents=True)
            (dataset_dir / "protocol.json").write_text(
                json.dumps({"counts": {"item_num": 11_921}}),
                encoding="utf-8",
            )
            logged_config = {
                "random_seed": 100,
                "training": {"data": "ATG", "batch_size": 256},
                "data": {
                    "ATG": {
                        "path": str(dataset_dir),
                        "item_num": 11_924,
                        "seq_len": 10,
                    }
                },
                "graph": {"is_disliked_item": True},
                "text_side": {"enabled": False},
            }
            checkpoint_model_state = {
                "vocab_embed.embedding.weight": torch.zeros(11_926, 256),
            }

            with self.assertRaisesRegex(ValueError, "explicit legacy mismatch allowance"):
                module.resolve_item_count_contract(
                    logged_config,
                    checkpoint_model_state=checkpoint_model_state,
                    dataset_name="ATG",
                    dataset_dir=dataset_dir,
                )
            contract = module.resolve_item_count_contract(
                logged_config,
                checkpoint_model_state=checkpoint_model_state,
                dataset_name="ATG",
                dataset_dir=dataset_dir,
                allow_legacy_model_catalog_mismatch=True,
            )
            cfg = module.prepare_config(
                logged_config,
                dataset_name="ATG",
                dataset_dir=dataset_dir,
                output_dir=output_dir,
                batch_size=256,
                random_seed=100,
            )

        self.assertEqual(11_924, contract["model_item_count"])
        self.assertEqual(11_921, contract["valid_item_count"])
        self.assertEqual(3, contract["non_candidate_model_item_slots"])
        self.assertEqual(11_926, contract["checkpoint_vocab_rows"])
        self.assertTrue(contract["legacy_model_catalog_mismatch_authorized"])
        self.assertEqual(11_924, int(cfg.data.ATG.item_num))

    def test_item_count_contract_rejects_checkpoint_or_text_asset_mismatch(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_dir = Path(tmpdir) / "ATG"
            dataset_dir.mkdir(parents=True)
            (dataset_dir / "protocol.json").write_text(
                json.dumps({"counts": {"item_num": 11_921}}),
                encoding="utf-8",
            )
            logged_config = {
                "data": {"ATG": {"path": str(dataset_dir), "item_num": 11_924}},
                "graph": {"is_disliked_item": True},
                "text_side": {"enabled": False},
            }
            wrong_checkpoint_state = {
                "vocab_embed.embedding.weight": torch.zeros(11_923, 256),
            }
            with self.assertRaisesRegex(ValueError, "checkpoint vocabulary rows"):
                module.resolve_item_count_contract(
                    logged_config,
                    checkpoint_model_state=wrong_checkpoint_state,
                    dataset_name="ATG",
                    dataset_dir=dataset_dir,
                )

            logged_config["text_side"]["enabled"] = True
            matching_legacy_state = {
                "vocab_embed.embedding.weight": torch.zeros(11_926, 256),
            }
            with self.assertRaisesRegex(ValueError, "text-side item count mismatch"):
                module.resolve_item_count_contract(
                    logged_config,
                    checkpoint_model_state=matching_legacy_state,
                    dataset_name="ATG",
                    dataset_dir=dataset_dir,
                    allow_legacy_model_catalog_mismatch=True,
                )

    def test_records_legacy_history_pad_semantics_and_rejects_candidate_targets(self) -> None:
        module = load_module()

        class FakeDataset:
            seq_data = [
                torch.tensor([11_921, 11_921, 3]),
                torch.tensor([4, 5, 6]),
            ]
            next_data = [torch.tensor(7), torch.tensor(11_920)]

        domain = module.inspect_test_item_domain(
            FakeDataset(),
            valid_item_count=11_921,
            model_item_count=11_924,
        )

        self.assertEqual(11_921, domain["history_pad_value"])
        self.assertEqual(2, domain["history_pad_occurrences"])
        self.assertEqual(1, domain["history_pad_rows"])
        self.assertTrue(domain["history_pad_maps_to_non_candidate_model_slot"])
        self.assertEqual(
            "ordinary_non_candidate_legacy_model_slot",
            domain["history_pad_semantics"],
        )
        self.assertEqual(11_920, domain["maximum_target_item_id"])

        class InvalidTargetDataset(FakeDataset):
            next_data = [torch.tensor(11_921)]
            seq_data = [torch.tensor([1, 2, 3])]

        with self.assertRaisesRegex(ValueError, "target item id outside real candidate catalog"):
            module.inspect_test_item_domain(
                InvalidTargetDataset(),
                valid_item_count=11_921,
                model_item_count=11_924,
            )

    def test_rejects_ema_shadow_shape_or_count_mismatch(self) -> None:
        module = load_module()
        self.assertTrue(hasattr(module, "validate_ema_state"))
        model = torch.nn.Linear(2, 1)

        class FakeEma:
            shadow_params = [torch.zeros(2, 2)]

        with self.assertRaisesRegex(ValueError, "EMA shadow parameter"):
            module.validate_ema_state(FakeEma(), model)

    def test_restores_graph_owned_host_p1_from_checkpoint_ema(self) -> None:
        module = load_module()

        class HostGraph(torch.nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.p1 = torch.nn.Parameter(torch.ones(3))

        model = torch.nn.Linear(2, 1, bias=False)
        graph = HostGraph()
        checkpoint = {
            "model": {"weight": torch.tensor([[1.5, -2.0]])},
            "graph": {"p1": torch.tensor([0.1, 0.2, 0.3])},
            "ema": {
                "decay": 0.9,
                "num_updates": 5,
                "shadow_params": [
                    torch.tensor([[2.5, -3.0]]),
                    torch.tensor([4.0, 5.0, 6.0]),
                ],
            },
            "training_parameter_names": ["model.weight", "graph.p1"],
            "step": 8,
        }

        restored = module.restore_evaluation_parameters(
            score_model=model,
            graph=graph,
            checkpoint=checkpoint,
            ema_decay=0.9,
        )

        self.assertEqual(
            ["model.weight", "graph.p1"],
            restored["training_parameter_names"],
        )
        self.assertTrue(torch.equal(model.weight.detach(), torch.tensor([[2.5, -3.0]])))
        self.assertTrue(torch.equal(graph.p1.detach(), torch.tensor([4.0, 5.0, 6.0])))

    def test_rejects_legacy_host_checkpoint_without_graph_ema_slot(self) -> None:
        module = load_module()

        class HostGraph(torch.nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.p1 = torch.nn.Parameter(torch.ones(3))

        model = torch.nn.Linear(2, 1, bias=False)
        checkpoint = {
            "model": model.state_dict(),
            "ema": {
                "decay": 0.9,
                "num_updates": 5,
                "shadow_params": [torch.zeros_like(model.weight)],
            },
            "step": 8,
        }

        with self.assertRaisesRegex(ValueError, "EMA shadow parameter count mismatch"):
            module.restore_evaluation_parameters(
                score_model=model,
                graph=HostGraph(),
                checkpoint=checkpoint,
                ema_decay=0.9,
            )

    def test_text_manifest_binds_external_assets_and_run_directory(self) -> None:
        module = load_module()
        self.assertTrue(hasattr(module, "validate_text_manifest"))

        def named_hash(*paths: Path) -> str:
            digest = hashlib.sha256()
            for path in paths:
                digest.update(path.name.encode("utf-8"))
                digest.update(path.read_bytes())
            return digest.hexdigest()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dataset_dir = root / "paper_raw_v1" / "Steam"
            run_dir = root / "run"
            checkpoint = run_dir / "checkpoints-meta" / "Steam" / "checkpoint_best.pth"
            bank = dataset_dir / "text_bank.csv"
            embeddings = dataset_dir / "embeddings.pt"
            null_curve = dataset_dir / "null.json"
            utility = root / "utility.json"
            train_split = dataset_dir / "train_data.df"
            for path, content in (
                (checkpoint, b"checkpoint"),
                (bank, b"bank"),
                (embeddings, b"embeddings"),
                (null_curve, b"null"),
                (utility, b"utility"),
                (train_split, b"train"),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)

            logged_config = {
                "text_side": {
                    "enabled": True,
                    "text_bank_path": str(bank),
                    "embeddings_path": str(embeddings),
                    "agreement_null_curve_path": str(null_curve),
                    "text_utility_report_path": str(utility),
                    "kernel_version": "v2",
                }
            }
            manifest = {
                "dataset": "Steam",
                "dataset_dir": str(dataset_dir),
                "run_dir": str(run_dir),
                "random_seed": 100,
                "bank_hash": named_hash(bank, embeddings),
                "null_curve_hash": hashlib.sha256(null_curve.read_bytes()).hexdigest(),
                "u_ds_artifact_hash": hashlib.sha256(utility.read_bytes()).hexdigest(),
                "split_hash": named_hash(train_split),
                "frozen_config": {"kernel_version": "v2"},
            }

            module.validate_text_manifest(
                manifest,
                logged_config=logged_config,
                dataset_name="Steam",
                dataset_dir=dataset_dir,
                checkpoint_path=checkpoint,
                random_seed=100,
            )
            bank.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "bank hash mismatch"):
                module.validate_text_manifest(
                    manifest,
                    logged_config=logged_config,
                    dataset_name="Steam",
                    dataset_dir=dataset_dir,
                    checkpoint_path=checkpoint,
                    random_seed=100,
                )

    def test_loads_model_state_with_strict_key_matching(self) -> None:
        module = load_module()
        self.assertTrue(hasattr(module, "load_model_state_strict"))
        observed: dict[str, object] = {}

        class FakeModel:
            def load_state_dict(self, state, strict=False):
                observed["state"] = state
                observed["strict"] = strict

        module.load_model_state_strict(FakeModel(), {"weight": "frozen"})

        self.assertEqual({"weight": "frozen"}, observed["state"])
        self.assertTrue(observed["strict"])

    def test_rejects_checkpoint_step_that_differs_from_best_summary(self) -> None:
        module = load_module()
        self.assertTrue(hasattr(module, "validate_best_summary"))

        module.validate_best_summary({"best_step": 32_000}, checkpoint_step=32_000)
        with self.assertRaisesRegex(ValueError, "best step mismatch"):
            module.validate_best_summary({"best_step": 32_000}, checkpoint_step=31_000)

    def test_result_filename_separates_strength_and_eval_seed(self) -> None:
        module = load_module()
        self.assertTrue(hasattr(module, "result_filename"))

        self.assertEqual(
            "steam_host_steam_p2_evalseed100_e0_eval.json",
            module.result_filename("steam_host", "Steam", "p2", 100),
        )

    def test_reset_eval_seed_repeats_random_stream_and_disables_benchmark(self) -> None:
        module = load_module()
        self.assertTrue(hasattr(module, "reset_evaluation_seed"))
        torch.backends.cudnn.benchmark = True

        module.reset_evaluation_seed(100)
        first = torch.rand(4)
        module.reset_evaluation_seed(100)
        second = torch.rand(4)

        self.assertTrue(torch.equal(first, second))
        self.assertFalse(torch.backends.cudnn.benchmark)
        self.assertTrue(torch.backends.cudnn.deterministic)

    def test_help_works_outside_repo_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, str(MODULE_PATH), "--help"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("--checkpoint-path", result.stdout)

    def test_parses_serialized_config_from_training_log(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "train.log"
            log_path.write_text(
                "header\n{'random_seed': 100, 'training': {'data': 'Steam'}}\nfooter\n",
                encoding="utf-8",
            )

            config = module.parse_logged_config(log_path)

        self.assertEqual(100, config["random_seed"])
        self.assertEqual("Steam", config["training"]["data"])

    def test_rejects_a_test_row_count_mismatch(self) -> None:
        module = load_module()

        with self.assertRaisesRegex(ValueError, "Steam test row count mismatch"):
            module.validate_expected_rows("Steam", "test", actual=80_640, expected=80_651)

    def test_builds_auditable_result_payload(self) -> None:
        module = load_module()
        self.assertIn("eval_seed", inspect.signature(module.build_result_payload).parameters)
        self.assertIn("valid_item_count", inspect.signature(module.build_result_payload).parameters)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            checkpoint_path = root / "checkpoint.pth"
            log_path = root / "train.log"
            split_path = root / "test_data.df"
            checkpoint_path.write_bytes(b"checkpoint")
            log_path.write_text("config", encoding="utf-8")
            split_path.write_bytes(b"split")

            payload = module.build_result_payload(
                method_id="steam_host",
                dataset_name="Steam",
                strength="p2",
                hr=[0.1, 0.2, 0.3, 0.4, 0.5],
                ndcg=[0.01, 0.02, 0.03, 0.04, 0.05],
                evaluated_rows=80_651,
                expected_rows=80_651,
                best_step=32_000,
                checkpoint_path=checkpoint_path,
                log_path=log_path,
                split_path=split_path,
                random_seed=100,
                eval_seed=10_010,
                valid_item_count=9_265,
                model_item_count=9_268,
                legacy_model_catalog_mismatch_authorized=True,
                test_item_domain={
                    "history_pad_value": 9_265,
                    "history_pad_occurrences": 10,
                    "history_pad_rows": 4,
                    "history_pad_maps_to_non_candidate_model_slot": True,
                    "history_pad_semantics": "ordinary_non_candidate_legacy_model_slot",
                    "minimum_history_item_id": 0,
                    "maximum_history_item_id": 9_265,
                    "minimum_target_item_id": 0,
                    "maximum_target_item_id": 9_264,
                },
            )

        self.assertEqual("e0_full_tail_v2", payload["metric_contract"]["version"])
        self.assertEqual("legacy_tail_skipping_validation", payload.get("checkpoint_selector_protocol"))
        self.assertTrue(payload.get("selection_bias_not_recomputed"))
        self.assertEqual("row", payload["metric_contract"]["aggregation_weight"])
        self.assertTrue(payload["metric_contract"]["tail_batch_included"])
        self.assertEqual(10_010, payload["metric_contract"]["eval_seed"])
        self.assertEqual("first-M-zero-based", payload["metric_contract"]["candidate_policy"])
        self.assertEqual(9_265, payload["metric_contract"]["valid_item_count"])
        self.assertEqual(9_268, payload["metric_contract"]["model_item_count"])
        self.assertEqual(3, payload["metric_contract"]["non_candidate_model_item_slots"])
        self.assertTrue(payload["metric_contract"]["legacy_model_catalog_mismatch_authorized"])
        self.assertTrue(
            payload["metric_contract"]["test_item_domain"]
            ["history_pad_maps_to_non_candidate_model_slot"]
        )
        self.assertEqual(
            "ordinary_non_candidate_legacy_model_slot",
            payload["metric_contract"]["test_item_domain"]["history_pad_semantics"],
        )
        self.assertEqual(80_651, payload["test"]["evaluated_rows"])
        self.assertEqual(0.3, payload["test"]["hr10"])
        self.assertEqual(0.03, payload["test"]["ndcg10"])
        self.assertEqual(64, len(payload["sources"]["checkpoint_sha256"]))
        json.dumps(payload)


if __name__ == "__main__":
    unittest.main()
