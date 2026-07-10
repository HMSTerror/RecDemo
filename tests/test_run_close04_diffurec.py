import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import torch


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "run_close04_diffurec.py"


def load_module():
    spec = importlib.util.spec_from_file_location("run_close04_diffurec", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RunClose04DiffuRecTests(unittest.TestCase):
    def test_script_module_exists(self) -> None:
        self.assertTrue(MODULE_PATH.exists(), f"missing script: {MODULE_PATH}")

    def test_convert_split_frame_uses_zero_pad_and_one_based_items(self) -> None:
        module = load_module()
        frame = pd.DataFrame(
            {
                "seq": [[3, 3, 0, 1], [3, 0, 2, 1]],
                "len_seq": [2, 3],
                "next": [2, 1],
            }
        )

        examples = module.convert_split_frame(frame, item_num=3)

        self.assertEqual(
            [
                {"sequence": [0, 0, 1, 2], "label": 3},
                {"sequence": [0, 1, 3, 2], "label": 2},
            ],
            examples,
        )

    def test_build_summary_payload_converts_percent_metrics_to_fraction(self) -> None:
        module = load_module()
        summary = module.build_summary_payload(
            dataset_name="Beauty",
            upstream_root=Path("/tmp/DiffuRec"),
            dataset_dir=Path("/tmp/paper_raw_v1/Beauty"),
            protocol_path=Path("/tmp/paper_raw_v1/Beauty/protocol.json"),
            item_num=12,
            random_seed=100,
            best_epoch=40,
            selection_metric="NDCG@10",
            best_metric_value_percent=8.75,
            validation_metrics_percent={
                "HR@5": 10.0,
                "NDCG@5": 5.0,
                "HR@10": 20.0,
                "NDCG@10": 8.75,
                "HR@20": 30.0,
                "NDCG@20": 12.5,
            },
            test_metrics_percent={
                "HR@5": 11.0,
                "NDCG@5": 5.5,
                "HR@10": 22.0,
                "NDCG@10": 9.25,
                "HR@20": 31.0,
                "NDCG@20": 13.0,
            },
        )

        self.assertEqual("DiffuRec", summary["method"])
        self.assertEqual("Beauty", summary["dataset"])
        self.assertEqual("NDCG@10", summary["selector"]["metric"])
        self.assertEqual(40, summary["selector"]["best_epoch"])
        self.assertAlmostEqual(0.0875, summary["selector"]["best_metric_value"])
        self.assertAlmostEqual(0.2, summary["validation"]["HR@10"])
        self.assertAlmostEqual(0.0875, summary["validation"]["NDCG@10"])
        self.assertAlmostEqual(0.22, summary["test"]["HR@10"])
        self.assertAlmostEqual(0.0925, summary["test"]["NDCG@10"])

    def test_load_dataset_bundle_reads_protocol_and_frames(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_dir = Path(tmpdir) / "ML1M"
            dataset_dir.mkdir(parents=True, exist_ok=True)
            protocol = {"dataset": "ML1M", "counts": {"item_num": 4}}
            (dataset_dir / "protocol.json").write_text(json.dumps(protocol), encoding="utf-8")
            for split_name in ("train", "val", "test"):
                pd.DataFrame(
                    {
                        "seq": [[4, 4, 0, 1]],
                        "len_seq": [2],
                        "next": [2],
                    }
                ).to_pickle(dataset_dir / f"{split_name}_data.df")

            bundle = module.load_dataset_bundle(dataset_dir)

            self.assertEqual("ML1M", bundle["dataset"])
            self.assertEqual(4, bundle["item_num"])
            self.assertEqual([{"sequence": [0, 0, 1, 2], "label": 3}], bundle["train_examples"])
            self.assertEqual([{"sequence": [0, 0, 1, 2], "label": 3}], bundle["val_examples"])
            self.assertEqual([{"sequence": [0, 0, 1, 2], "label": 3}], bundle["test_examples"])

    def test_ensure_numpy_legacy_aliases_restores_np_int_for_upstream_code(self) -> None:
        module = load_module()
        if hasattr(module.np, "int"):
            delattr(module.np, "int")

        module.ensure_numpy_legacy_aliases()

        self.assertTrue(hasattr(module.np, "int"))
        self.assertIs(int, module.np.int)

    def test_topk_metrics_clamps_requested_k_to_available_vocab(self) -> None:
        module = load_module()
        scores = torch.tensor([[0.1, 0.2, 0.9, 0.4]], dtype=torch.float32)
        labels = torch.tensor([[2]], dtype=torch.long)

        metrics = module.topk_metrics(scores, labels, ks=(5, 10, 20))

        self.assertAlmostEqual(1.0, metrics["HR@5"])
        self.assertAlmostEqual(1.0, metrics["HR@10"])
        self.assertAlmostEqual(1.0, metrics["HR@20"])
        self.assertAlmostEqual(1.0, metrics["NDCG@5"])
        self.assertAlmostEqual(1.0, metrics["NDCG@10"])
        self.assertAlmostEqual(1.0, metrics["NDCG@20"])

    def test_evaluate_model_weights_tail_metrics_by_row_count(self) -> None:
        module = load_module()

        class TailAwareModel:
            def eval(self) -> None:
                pass

            def __call__(self, sequences, labels, train_flag):
                del labels, train_flag
                return None, sequences, None, None, None, None

            def diffu_rep_pre(self, representations):
                scores = torch.tensor([0.0, 1.0]).repeat(len(representations), 1)
                tail_rows = representations[:, 0].eq(1)
                scores[tail_rows, 0] = 2.0
                return scores

        data_loader = [
            (torch.zeros((2, 1), dtype=torch.long), torch.zeros(2, dtype=torch.long)),
            (torch.ones((1, 1), dtype=torch.long), torch.zeros(1, dtype=torch.long)),
        ]

        metrics = module.evaluate_model(
            TailAwareModel(),
            data_loader,
            torch.device("cpu"),
            ks=(1,),
        )

        self.assertAlmostEqual(1 / 3, metrics["HR@1"])
        self.assertAlmostEqual(1 / 3, metrics["NDCG@1"])


if __name__ == "__main__":
    unittest.main()
