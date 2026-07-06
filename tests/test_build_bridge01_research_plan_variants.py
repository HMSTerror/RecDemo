import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


builder = load_module(
    "build_bridge01_research_plan_variants",
    REPO_ROOT / "scripts" / "build_bridge01_research_plan_variants.py",
)


class BuildBridge01ResearchPlanVariantsTests(unittest.TestCase):
    def test_build_variants_selects_only_requested_team_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cn_source = root / "cn.md"
            en_source = root / "en.md"
            output_dir = root / "out"
            cn_source.write_text(
                "# 标题\n\n前文。\n\n## 4A. 团队钩子（Lumina 版本）\n\nLumina 段。\n\n## 4B. 团队钩子（InternVideo 版本）\n\nInternVideo 段。\n",
                encoding="utf-8",
            )
            en_source.write_text(
                "# Title\n\nPrefix.\n\n## 4A. Team hook (Lumina variant)\n\nLumina paragraph.\n\n## 4B. Team hook (InternVideo variant)\n\nInternVideo paragraph.\n",
                encoding="utf-8",
            )

            outputs = builder.build_variants(
                cn_source=cn_source,
                en_source=en_source,
                output_dir=output_dir,
            )

            self.assertEqual(4, len(outputs))
            cn_lumina = (output_dir / "07-bridge01-research-plan-cn-lumina.md").read_text(encoding="utf-8")
            cn_internvideo = (output_dir / "07-bridge01-research-plan-cn-internvideo.md").read_text(encoding="utf-8")
            en_lumina = (output_dir / "07-bridge01-research-plan-en-lumina.md").read_text(encoding="utf-8")
            en_internvideo = (output_dir / "07-bridge01-research-plan-en-internvideo.md").read_text(encoding="utf-8")

            self.assertIn("Lumina 段。", cn_lumina)
            self.assertNotIn("InternVideo 段。", cn_lumina)
            self.assertIn("InternVideo 段。", cn_internvideo)
            self.assertNotIn("Lumina 段。", cn_internvideo)

            self.assertIn("Lumina paragraph.", en_lumina)
            self.assertNotIn("InternVideo paragraph.", en_lumina)
            self.assertIn("InternVideo paragraph.", en_internvideo)
            self.assertNotIn("Lumina paragraph.", en_internvideo)

            self.assertIn("## 4. 团队钩子", cn_lumina)
            self.assertIn("## 4. Team hook", en_internvideo)


if __name__ == "__main__":
    unittest.main()
