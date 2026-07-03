import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script_module():
    script_path = REPO_ROOT / "scripts" / "build_gate0_v2_frozen_verdict.py"
    spec = importlib.util.spec_from_file_location("build_gate0_v2_frozen_verdict", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def write_text_utility_report(path: Path, dataset_rows: list[dict[str, object]]) -> None:
    path.write_text(json.dumps({"datasets": dataset_rows}, indent=2, sort_keys=True), encoding="utf-8")


class BuildGate0V2FrozenVerdictTests(unittest.TestCase):
    def test_fail_branch_writes_family_d_memo_and_blocks_sprint05(self) -> None:
        module = load_script_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            report_path = output_dir / "gate0_text_utility_report.json"
            write_text_utility_report(
                report_path,
                [
                    {"dataset": "ML1M", "u_ds_popularity": 0.75353875, "bank_hash": "bank-ml1m", "split_hash": "split-ml1m"},
                    {"dataset": "Steam", "u_ds_popularity": 0.56956625, "bank_hash": "bank-steam", "split_hash": "split-steam"},
                    {"dataset": "Beauty", "u_ds_popularity": 0.71242750, "bank_hash": "bank-beauty", "split_hash": "split-beauty"},
                    {"dataset": "ATG", "u_ds_popularity": 0.68826250, "bank_hash": "bank-atg", "split_hash": "split-atg"},
                ],
            )

            verdict = module.build_gate0_v2_frozen_verdict(output_dir=output_dir, report_json=report_path)

            self.assertFalse(verdict["criterion_pass"])
            self.assertEqual("blocked_family_d_downgrade", verdict["sprint05_decision"])
            self.assertFalse(verdict["conditions"][2]["passed"])
            self.assertEqual(1, verdict["non_ml1m_phi_ge_0_5_count"])
            self.assertFalse(verdict["third_gate_repair_round_allowed"])
            self.assertTrue((output_dir / "gate0_v2_frozen_verdict.json").exists())
            self.assertTrue((output_dir / "gate0_v2_frozen_verdict.md").exists())
            self.assertTrue((output_dir / "gate0_v2_family_d_downgrade_memo_zh.md").exists())

            markdown_text = (output_dir / "gate0_v2_frozen_verdict.md").read_text(encoding="utf-8")
            self.assertIn("Condition 3", markdown_text)
            self.assertIn("FAILED", markdown_text)
            self.assertIn("`SPRINT-05` decision: `blocked_family_d_downgrade`", markdown_text)

            zh_memo = (output_dir / "gate0_v2_family_d_downgrade_memo_zh.md").read_text(encoding="utf-8")
            self.assertIn("Family D", zh_memo)
            self.assertIn("不再进行第三轮门控修复", zh_memo)

    def test_pass_branch_reopens_sprint05_without_family_d_memo(self) -> None:
        module = load_script_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            report_path = output_dir / "gate0_text_utility_report.json"
            write_text_utility_report(
                report_path,
                [
                    {"dataset": "ML1M", "u_ds_popularity": 0.75353875, "bank_hash": "bank-ml1m", "split_hash": "split-ml1m"},
                    {"dataset": "Steam", "u_ds_popularity": 0.56956625, "bank_hash": "bank-steam", "split_hash": "split-steam"},
                    {"dataset": "Beauty", "u_ds_popularity": 0.62000000, "bank_hash": "bank-beauty", "split_hash": "split-beauty"},
                    {"dataset": "ATG", "u_ds_popularity": 0.68826250, "bank_hash": "bank-atg", "split_hash": "split-atg"},
                ],
            )

            verdict = module.build_gate0_v2_frozen_verdict(output_dir=output_dir, report_json=report_path)

            self.assertTrue(verdict["criterion_pass"])
            self.assertEqual("reopen_sprint05", verdict["sprint05_decision"])
            self.assertTrue(all(condition["passed"] for condition in verdict["conditions"]))
            self.assertTrue(verdict["third_gate_repair_round_allowed"])
            self.assertFalse((output_dir / "gate0_v2_family_d_downgrade_memo_zh.md").exists())

            markdown_text = (output_dir / "gate0_v2_frozen_verdict.md").read_text(encoding="utf-8")
            self.assertIn("PASSED", markdown_text)


if __name__ == "__main__":
    unittest.main()
