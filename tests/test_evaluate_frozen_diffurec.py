import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "evaluate_frozen_diffurec.py"


def load_module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"missing script: {MODULE_PATH}")
    spec = importlib.util.spec_from_file_location("evaluate_frozen_diffurec", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class EvaluateFrozenDiffuRecTests(unittest.TestCase):
    def test_binds_best_checkpoint_to_manifest_summary_epoch(self) -> None:
        module = load_module()
        self.assertTrue(hasattr(module, "validate_best_checkpoint_binding"))
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "checkpoints-meta" / "Steam"
            checkpoint = root / "checkpoint_diffurec_best.pt"
            summary_path = root / "best_summary_diffurec.json"
            root.mkdir(parents=True)
            checkpoint.write_bytes(b"checkpoint")
            summary_path.write_text("{}", encoding="utf-8")
            manifest = {
                "summary_path": str(summary_path),
                "dataset": "Steam",
                "random_seed": 100,
            }
            summary = {
                "method": "DiffuRec",
                "dataset": "Steam",
                "random_seed": 100,
                "selector": {"best_epoch": 120},
            }

            module.validate_best_checkpoint_binding(
                manifest,
                summary,
                checkpoint_path=checkpoint,
                checkpoint_epoch=120,
            )
            with self.assertRaisesRegex(ValueError, "best epoch mismatch"):
                module.validate_best_checkpoint_binding(
                    manifest,
                    summary,
                    checkpoint_path=checkpoint,
                    checkpoint_epoch=119,
                )

    def test_loads_diffurec_state_with_strict_key_matching(self) -> None:
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

    def test_validates_frozen_manifest_contract(self) -> None:
        module = load_module()
        manifest = {
            "method": "DiffuRec",
            "dataset": "Steam",
            "random_seed": 100,
            "checkpoint_policy": "latest_plus_best",
            "item_num": 9265,
            "batch_size": 256,
        }

        module.validate_manifest(manifest, dataset_name="Steam", random_seed=100)
        with self.assertRaisesRegex(ValueError, "dataset mismatch"):
            module.validate_manifest(manifest, dataset_name="Beauty", random_seed=100)

    def test_builds_row_weighted_full_catalog_payload(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            checkpoint = root / "checkpoint.pt"
            manifest = root / "manifest.json"
            split = root / "test_data.df"
            checkpoint.write_bytes(b"checkpoint")
            manifest.write_text("{}", encoding="utf-8")
            split.write_bytes(b"split")

            payload = module.build_result_payload(
                dataset_name="Steam",
                metrics={"HR@10": 0.2, "NDCG@10": 0.1},
                evaluated_rows=80_651,
                expected_rows=80_651,
                best_epoch=120,
                checkpoint_path=checkpoint,
                manifest_path=manifest,
                split_path=split,
                random_seed=100,
                eval_seed=100,
                upstream_revision="abc123",
                training_wrapper_revision="frozen-wrapper",
                model_config={"hidden_size": 128, "diffusion_steps": 32},
                summary_path=manifest,
            )

        self.assertEqual("e0_full_tail_v2", payload["metric_contract"]["version"])
        self.assertEqual("row", payload["metric_contract"]["aggregation_weight"])
        self.assertEqual("exclude-padding-id-0", payload["metric_contract"]["candidate_policy"])
        self.assertEqual(80_651, payload["test"]["evaluated_rows"])
        self.assertEqual(0.1, payload["test"]["ndcg10"])
        self.assertEqual(64, len(payload["sources"]["checkpoint_sha256"]))
        self.assertEqual("frozen-wrapper", payload["training_wrapper_revision"])
        self.assertEqual(32, payload["model_config"]["diffusion_steps"])
        self.assertIn("summary_sha256", payload["sources"])


if __name__ == "__main__":
    unittest.main()
