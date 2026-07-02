import importlib.util
import tempfile
import unittest
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script_module():
    script_path = REPO_ROOT / "scripts" / "build_g0_smoke_training_report.py"
    spec = importlib.util.spec_from_file_location("build_g0_smoke_training_report", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class BuildG0SmokeTrainingReportTests(unittest.TestCase):
    def test_script_writes_matching_core_vs_v2_g0_smoke_curves(self) -> None:
        module = load_script_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "g0_smoke_training_curve.csv"
            rows = module.build_smoke_training_report(output_path=output_path)

            self.assertTrue(output_path.exists())
            written_rows = pd.read_csv(output_path).to_dict(orient="records")
            self.assertEqual(len(rows), len(written_rows))
            self.assertGreaterEqual(len(written_rows), 2)

            for row in written_rows:
                self.assertIn("step", row)
                self.assertIn("core_train_loss", row)
                self.assertIn("proposal_train_loss", row)
                self.assertIn("train_loss_abs_diff", row)
                self.assertIn("core_val_p2_ndcg10", row)
                self.assertIn("proposal_val_p2_ndcg10", row)
                self.assertIn("val_p2_ndcg10_abs_diff", row)
                self.assertLessEqual(float(row["train_loss_abs_diff"]), 1e-6)
                self.assertLessEqual(float(row["val_p2_ndcg10_abs_diff"]), 1e-6)


if __name__ == "__main__":
    unittest.main()
