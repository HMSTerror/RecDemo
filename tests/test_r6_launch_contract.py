from __future__ import annotations

import sys
import unittest
from pathlib import Path, PurePosixPath


REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT, REPO_ROOT / "scripts", REPO_ROOT / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.aaai27_adapters.pilot_adapters import build_pilot_manifest
from scripts.aaai27_queue.models import QueueManifest
from scripts.aaai27_queue.validation import ManifestError, validate_manifest


def make_protocol(*, gpu_ids: list[int] | None = None) -> dict[str, object]:
    protocol: dict[str, object] = {
        "queue_id": "aaai27-risk0607-r6-contract-test",
        "created_at": "2026-07-11T20:30:00+08:00",
        "run_root": "/srv/aaai27/r6",
        "source_root": "/srv/aaai27/source-r6",
        "source_manifest_sha256": "a" * 64,
        "ledger_path": "/srv/aaai27/source-r6/issues/ledger.csv",
        "ledger_sha256": "b" * 64,
        "code_revision": "c" * 40,
        "config_sha256": "d" * 64,
        "python_bin": "/opt/prefergrow/bin/python3",
        "single_train": "/srv/aaai27/source-r6/single_train.py",
        "risk05_preregistration_sha256": "e" * 64,
        "training_overrides": ["training.n_iters=10"],
        "estimated_gpu_hours": {"low": 0.5, "high": 1.0, "output_gib": 0.2},
        "datasets": {
            dataset: {
                "dataset_dir": f"/srv/data/{dataset}",
                "split_sha256": "f" * 64,
                "text_bank_path": f"/srv/data/{dataset}/text_bank.csv",
                "null_curve_path": f"/srv/data/{dataset}/agreement_null_curves.json",
                "config_sha256": "1" * 64,
                "banks": {
                    str(level): {
                        "embedding_path": f"/srv/banks/{dataset}/{level}/embeddings.pt",
                        "embedding_sha256": "2" * 64,
                        "bank_sha256": "3" * 64,
                        "phi_R": 1.0 - level / 100.0,
                    }
                    for level in (0, 60, 100)
                },
            }
            for dataset in ("Beauty", "Steam")
        },
    }
    if gpu_ids is not None:
        protocol["gpu_ids"] = gpu_ids
    return protocol


class R6LaunchContractTests(unittest.TestCase):
    def test_pilot_manifest_copies_explicit_gpu1_allowlist(self) -> None:
        manifest = build_pilot_manifest(make_protocol(gpu_ids=[1]))

        self.assertEqual([1], manifest["gpu_ids"])

    def test_pilot_manifest_requires_explicit_gpu_allowlist(self) -> None:
        with self.assertRaisesRegex(ValueError, "gpu_ids"):
            build_pilot_manifest(make_protocol())

    def test_pilot_gpu_tasks_use_isolated_runtime_cwd_and_absolute_source_entry(self) -> None:
        manifest = build_pilot_manifest(make_protocol(gpu_ids=[1]))

        for task in manifest["tasks"]:
            self.assertEqual(task["run_dir"], task["cwd"], task["task_id"])
            self.assertTrue(PurePosixPath(task["argv"][0]).is_absolute(), task["task_id"])
            self.assertEqual(
                "/srv/aaai27/source-r6/single_train.py",
                task["argv"][1],
                task["task_id"],
            )

    def test_validator_accepts_gpu1_only_isolated_pilot_manifest(self) -> None:
        manifest = QueueManifest.from_dict(
            build_pilot_manifest(make_protocol(gpu_ids=[1]))
        )

        validate_manifest(manifest)

    def test_validator_rejects_unsafe_gpu_allowlists(self) -> None:
        for gpu_ids in ([], [1, 1], [-1]):
            with self.subTest(gpu_ids=gpu_ids):
                raw = build_pilot_manifest(make_protocol(gpu_ids=[1]))
                raw["gpu_ids"] = gpu_ids
                with self.assertRaisesRegex(
                    ManifestError, "nonempty unique nonnegative"
                ):
                    validate_manifest(QueueManifest.from_dict(raw))

    def test_validator_rejects_gpu_task_cwd_that_differs_from_run_dir(self) -> None:
        raw = build_pilot_manifest(make_protocol(gpu_ids=[1]))
        raw["gpu_ids"] = [0, 1]
        raw["tasks"][0]["cwd"] = raw["source_root"]

        with self.assertRaisesRegex(ManifestError, "cwd must equal run_dir"):
            validate_manifest(QueueManifest.from_dict(raw))


if __name__ == "__main__":
    unittest.main()
