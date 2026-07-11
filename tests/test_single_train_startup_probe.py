from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import torch
from omegaconf import OmegaConf


REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT, REPO_ROOT / "scripts", REPO_ROOT / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import single_train
from aaai27_queue.models import QueueManifest
from aaai27_queue.validation import ManifestError, validate_manifest
from aaai27_queue_testdata import make_manifest, make_task


class FakeScoreModel(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.weight = torch.nn.Parameter(torch.tensor([1.0]))


class FakeNoise:
    def to(self, device):
        return self


class FakeOptimizer:
    def __init__(self, *, state=None) -> None:
        self.state = {} if state is None else state


class SingleTrainStartupProbeTests(unittest.TestCase):
    def test_config_defaults_startup_probe_to_false(self) -> None:
        cfg = OmegaConf.load(REPO_ROOT / "configs" / "config.yaml")

        self.assertIs(False, cfg.training.get("startup_probe_only"))

    def test_startup_probe_returns_before_dataloader_and_writes_scoped_artifact(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "startup-probe-run"
            run_dir.mkdir()
            cfg = OmegaConf.create(
                {
                    "random_seed": 100,
                    "cuda": 1,
                    "work_dir": str(run_dir),
                    "training": {
                        "data": "Beauty",
                        "ema": 0.999,
                        "startup_probe_only": True,
                    },
                    "graph": {"type": "adaptive"},
                }
            )
            score_model = FakeScoreModel()
            optimizer = FakeOptimizer()
            loaders = mock.Mock(
                side_effect=AssertionError(
                    "startup probe must return before dataloader construction"
                )
            )
            original_cwd = Path.cwd()
            os.chdir(run_dir)
            try:
                with (
                    mock.patch.object(single_train, "setup_seed"),
                    mock.patch.object(
                        single_train.dataset_runtime,
                        "reconcile_runtime_dataset_config",
                    ),
                    mock.patch.object(
                        single_train.torch.cuda, "is_available", return_value=False
                    ),
                    mock.patch.object(
                        single_train.graph_lib, "get_graph", return_value=object()
                    ),
                    mock.patch.object(
                        single_train, "SEDD4REC", return_value=score_model
                    ),
                    mock.patch.object(
                        single_train,
                        "compose_named_training_parameters",
                        return_value=[("model.weight", score_model.weight)],
                    ),
                    mock.patch.object(
                        single_train,
                        "compose_optimizer_parameters",
                        return_value=[score_model.weight],
                    ),
                    mock.patch.object(
                        single_train,
                        "ExponentialMovingAverage",
                        return_value=object(),
                    ),
                    mock.patch.object(
                        single_train.noise_lib, "get_noise", return_value=FakeNoise()
                    ),
                    mock.patch.object(
                        single_train.losses, "get_optimizer", return_value=optimizer
                    ),
                    mock.patch.object(
                        single_train.torch.cuda.amp,
                        "GradScaler",
                        return_value=object(),
                    ),
                    mock.patch.object(
                        single_train.data, "get_seqdataloader", loaders
                    ),
                ):
                    single_train.main.__wrapped__(cfg)
            finally:
                os.chdir(original_cwd)

            loaders.assert_not_called()
            marker_path = run_dir / "startup_probe.json"
            payload = json.loads(marker_path.read_text(encoding="utf-8"))
            self.assertEqual("pass", payload["status"])
            self.assertEqual("hydra_pre_step", payload["probe_type"])
            self.assertEqual(0, payload["step"])
            self.assertEqual(0, payload["optimizer_state_entries"])
            self.assertEqual(["model.weight"], payload["training_parameter_names"])
            self.assertEqual([], payload["checkpoint_files"])
            self.assertEqual([], payload["summary_files"])

    def test_startup_probe_payload_rejects_nonzero_state_or_optimizer_entries(
        self,
    ) -> None:
        self.assertTrue(hasattr(single_train, "build_startup_probe_payload"))
        cfg = OmegaConf.create(
            {
                "random_seed": 100,
                "training": {"data": "Beauty"},
                "graph": {"type": "adaptive"},
            }
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            checkpoint_dir = root / "checkpoints"
            checkpoint_meta_dir = root / "checkpoints-meta"
            checkpoint_dir.mkdir()
            checkpoint_meta_dir.mkdir()
            original_cwd = Path.cwd()
            os.chdir(root)
            try:
                for state, message in (
                    (
                        {
                            "step": 1,
                            "optimizer": FakeOptimizer(),
                            "training_parameter_names": ["model.weight"],
                            "training_parameters": [
                                torch.nn.Parameter(torch.ones(1))
                            ],
                        },
                        "step zero",
                    ),
                    (
                        {
                            "step": 0,
                            "optimizer": FakeOptimizer(
                                state={1: {"momentum": 0.0}}
                            ),
                            "training_parameter_names": ["model.weight"],
                            "training_parameters": [
                                torch.nn.Parameter(torch.ones(1))
                            ],
                        },
                        "optimizer state",
                    ),
                ):
                    with self.subTest(message=message):
                        with self.assertRaisesRegex(RuntimeError, message):
                            single_train.build_startup_probe_payload(
                                cfg=cfg,
                                state=state,
                                work_dir=root,
                                checkpoint_dir=checkpoint_dir,
                                checkpoint_meta_dir=checkpoint_meta_dir,
                            )
            finally:
                os.chdir(original_cwd)

    def test_startup_probe_payload_rejects_preexisting_scientific_artifact(
        self,
    ) -> None:
        cfg = OmegaConf.create(
            {
                "random_seed": 100,
                "training": {"data": "Beauty"},
                "graph": {"type": "adaptive"},
            }
        )
        state = {
            "step": 0,
            "optimizer": FakeOptimizer(),
            "training_parameter_names": ["model.weight"],
            "training_parameters": [torch.nn.Parameter(torch.ones(1))],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            checkpoint_dir = root / "checkpoints"
            checkpoint_meta_dir = root / "checkpoints-meta"
            checkpoint_dir.mkdir()
            checkpoint_meta_dir.mkdir()
            (checkpoint_meta_dir / "checkpoint_adaptive_best.pth").write_bytes(
                b"unexpected"
            )
            original_cwd = Path.cwd()
            os.chdir(root)
            try:
                with self.assertRaisesRegex(RuntimeError, "pre-existing"):
                    single_train.build_startup_probe_payload(
                        cfg=cfg,
                        state=state,
                        work_dir=root,
                        checkpoint_dir=checkpoint_dir,
                        checkpoint_meta_dir=checkpoint_meta_dir,
                    )
            finally:
                os.chdir(original_cwd)

    def test_queue_manifest_rejects_startup_probe_override(self) -> None:
        run_dir = "/srv/queue/runs/scientific-task"
        for token in (
            "training.startup_probe_only=True",
            "training.startup_probe_only=1",
            "+training.startup_probe_only=False",
        ):
            with self.subTest(token=token):
                task = make_task(
                    task_id="scientific-task",
                    cwd=run_dir,
                    run_dir=run_dir,
                    argv=[
                        "/opt/venv/bin/python3",
                        "/srv/bundle/source/single_train.py",
                        token,
                    ],
                )
                manifest = QueueManifest.from_dict(
                    make_manifest([task], gpu_ids=[1])
                )

                with self.assertRaisesRegex(ManifestError, "startup probe"):
                    validate_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
