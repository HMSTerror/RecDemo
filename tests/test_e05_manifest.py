import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.build_e05_sasrec_manifest import build_manifest, parse_args
from scripts.run_e05_sasrec_queue import load_manifest
from tests.test_run_sasrec import make_dataset


class E05ManifestTest(unittest.TestCase):
    def test_manifest_is_four_domain_seed100_gpu0_atomic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            (source / "scripts").mkdir(parents=True)
            for name in ("run_sasrec.py", "build_e05_sasrec_manifest.py", "run_e05_sasrec_queue.py"):
                shutil.copy2(Path("scripts") / name, source / "scripts" / name)
            ledger = source / "issues.csv"
            ledger.write_text("ledger", encoding="utf-8")
            dataset_root = root / "datasets"
            for dataset in ("Steam", "ML1M", "Beauty", "ATG"):
                make_dataset(dataset_root, dataset)
            queue = root / "queue-2026-07-11"
            args = parse_args([
                "--queue-root", str(queue), "--source-root", str(source), "--dataset-root", str(dataset_root),
                "--ledger-path", str(ledger), "--code-revision", "0" * 40, "--python-bin", "python",
            ])
            manifest = build_manifest(args)
            self.assertEqual(len(manifest["tasks"]), 4)
            self.assertEqual(manifest["gpu_ids"], [0])
            self.assertEqual(manifest["seed_set"], [100])
            self.assertEqual({task["dataset"] for task in manifest["tasks"]}, {"Steam", "ML1M", "Beauty", "ATG"})
            decoded = load_manifest(queue / "manifest.json")
            self.assertEqual(decoded["manifest_sha256"], manifest["manifest_sha256"])

    def test_existing_queue_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "queue-2026-07-11"
            queue.mkdir()
            with self.assertRaises(FileExistsError):
                # The builder checks the root before any source or data mutation.
                build_manifest(parse_args([
                    "--queue-root", str(queue), "--source-root", str(root), "--dataset-root", str(root),
                    "--ledger-path", str(root / "missing.csv"), "--code-revision", "0" * 40,
                ]))


if __name__ == "__main__":
    unittest.main()
