import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class Followup06ContractTests(unittest.TestCase):
    def test_transformer_exposes_text_utility_report_override(self) -> None:
        source = (REPO_ROOT / "model" / "transformer.py").read_text(encoding="utf-8")
        config_text = (REPO_ROOT / "configs" / "config.yaml").read_text(encoding="utf-8")
        self.assertIn(
            'text_side_cfg.get("text_utility_report_path")',
            source,
            "transformer.py should pass text_side.text_utility_report_path through to the text-side builder",
        )
        self.assertIn(
            "text_utility_report_path: null",
            config_text,
            "config.yaml should expose a nullable text-side utility report override",
        )

    def test_paper_syncs_utility_gated_gate_narrative(self) -> None:
        source = (REPO_ROOT / "paper" / "main.tex").read_text(encoding="utf-8")
        self.assertIn(
            r"\phi(U_{ds})",
            source,
            "paper/main.tex should describe the frozen dataset-level utility gate factor",
        )
        self.assertIn(
            "false negative",
            source,
            "paper/main.tex should explain the false-negative failure mode behind the utility gate amendment",
        )
        self.assertIn(
            "hard negative",
            source,
            "paper/main.tex should explain the hard-negative side of the amended calibration story",
        )


if __name__ == "__main__":
    unittest.main()
