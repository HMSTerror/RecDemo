import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_e0_fulltail_matrix.sh"


class RunE0FulltailMatrixTests(unittest.TestCase):
    def test_matrix_contains_exactly_the_approved_18_frozen_evaluations(self) -> None:
        self.assertTrue(SCRIPT_PATH.exists(), f"missing script: {SCRIPT_PATH}")
        text = SCRIPT_PATH.read_text(encoding="utf-8")
        invocations = re.findall(r"^\s+run_(?:core|diff)\s+([a-z0-9_]+)\s+", text, re.MULTILINE)

        self.assertEqual(
            {
                "host_steam", "host_ml1m", "host_beauty", "host_atg",
                "ours_full_steam", "ours_full_ml1m", "ours_full_beauty", "ours_full_atg",
                "global_p_steam", "u_shuffle_steam", "text_anchor_only_steam",
                "global_p_beauty", "u_shuffle_beauty", "text_anchor_only_beauty",
                "diffurec_steam", "diffurec_ml1m", "diffurec_beauty", "diffurec_atg",
            },
            set(invocations),
        )
        self.assertIn("aaai27_e0_fulltail_20260710", text)
        self.assertIn("5709c6283cb127d727f6b769d8409343f4aae824", text)
        self.assertNotIn("single_train.py", text)


if __name__ == "__main__":
    unittest.main()
