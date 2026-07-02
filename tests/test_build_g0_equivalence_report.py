import importlib.util
import tempfile
import unittest
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script_module():
    script_path = REPO_ROOT / "scripts" / "build_g0_equivalence_report.py"
    spec = importlib.util.spec_from_file_location("build_g0_equivalence_report", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class BuildG0EquivalenceReportTests(unittest.TestCase):
    def test_script_writes_real_numeric_equivalence_report(self) -> None:
        module = load_script_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "g0_equivalence_report.csv"
            rows = module.build_equivalence_report(output_path=output_path)

            self.assertTrue(output_path.exists())
            written_rows = pd.read_csv(output_path).to_dict(orient="records")
            self.assertEqual(len(rows), len(written_rows))

            by_check = {row["check"]: row for row in written_rows}
            for check_name in (
                "proposal",
                "prob_matrix_row",
                "score_entropy",
                "reverse_prob_ratio",
                "sample_prob",
                "sample_nonpreference",
            ):
                self.assertIn(check_name, by_check)
                self.assertEqual("pass", by_check[check_name]["status"])
                self.assertLessEqual(float(by_check[check_name]["max_abs_diff"]), 1e-6)


if __name__ == "__main__":
    unittest.main()
