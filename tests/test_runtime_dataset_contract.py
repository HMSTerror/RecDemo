import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import dataset_runtime


class RuntimeDatasetContractTests(unittest.TestCase):
    def test_reconcile_runtime_dataset_config_prefers_protocol_item_num(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_dir = Path(tmpdir) / "ATG"
            dataset_dir.mkdir(parents=True, exist_ok=True)
            (dataset_dir / "protocol.json").write_text(
                json.dumps({"counts": {"item_num": 11921}}),
                encoding="utf-8",
            )

            cfg = SimpleNamespace(
                training=SimpleNamespace(data="ATG"),
                data=SimpleNamespace(
                    ATG=SimpleNamespace(
                        path=str(dataset_dir),
                        item_num=11924,
                        seq_len=10,
                    )
                ),
            )

            resolved_item_num = dataset_runtime.reconcile_runtime_dataset_config(cfg)

            self.assertEqual(11921, resolved_item_num)
            self.assertEqual(11921, int(cfg.data.ATG.item_num))

    def test_reconcile_runtime_dataset_config_keeps_existing_when_no_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_dir = Path(tmpdir) / "Beauty"
            dataset_dir.mkdir(parents=True, exist_ok=True)
            cfg = SimpleNamespace(
                training=SimpleNamespace(data="Beauty"),
                data=SimpleNamespace(
                    Beauty=SimpleNamespace(
                        path=str(dataset_dir),
                        item_num=12101,
                        seq_len=10,
                    )
                ),
            )

            resolved_item_num = dataset_runtime.reconcile_runtime_dataset_config(cfg)

            self.assertIsNone(resolved_item_num)
            self.assertEqual(12101, int(cfg.data.Beauty.item_num))


if __name__ == "__main__":
    unittest.main()
