import importlib.util
import inspect
import sys
import types
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_single_train_module():
    stub_hydra = types.ModuleType("hydra")
    stub_hydra.main = lambda **kwargs: (lambda fn: fn)
    stub_numpy = types.ModuleType("numpy")
    stub_numpy.random = types.SimpleNamespace(seed=lambda seed: None)
    stub_torch = types.ModuleType("torch")
    stub_torch.manual_seed = lambda seed: None
    stub_torch.cuda = types.SimpleNamespace(
        manual_seed_all=lambda seed: None,
        amp=types.SimpleNamespace(GradScaler=lambda: object()),
        is_available=lambda: False,
    )
    stub_torch.backends = types.SimpleNamespace(
        cudnn=types.SimpleNamespace(benchmark=False, deterministic=False)
    )
    stub_omegaconf = types.ModuleType("omegaconf")
    stub_omegaconf.DictConfig = dict
    stub_utils = types.ModuleType("utils")
    stub_utils.save_single_checkpoint = lambda path, state: None
    stub_utils.evaluate_loader = lambda *args, **kwargs: ([0.0] * 5, [0.0] * 5)
    stub_modules = {
        "hydra": stub_hydra,
        "numpy": stub_numpy,
        "torch": stub_torch,
        "omegaconf": stub_omegaconf,
        "data": types.ModuleType("data"),
        "dataset_runtime": types.ModuleType("dataset_runtime"),
        "graph_lib": types.ModuleType("graph_lib"),
        "losses": types.ModuleType("losses"),
        "noise_lib": types.ModuleType("noise_lib"),
        "sampling": types.ModuleType("sampling"),
        "utils": stub_utils,
        "model": types.ModuleType("model"),
        "model.ema": types.ModuleType("model.ema"),
        "model.transformer": types.ModuleType("model.transformer"),
    }
    stub_modules["model.ema"].ExponentialMovingAverage = object
    stub_modules["model.transformer"].SEDD4REC = object
    original_modules = {name: sys.modules.get(name) for name in stub_modules}
    sys.modules.update(stub_modules)

    script_path = REPO_ROOT / "single_train.py"
    spec = importlib.util.spec_from_file_location("single_train", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    try:
        spec.loader.exec_module(module)
        return module
    finally:
        for name, original in original_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


class SingleTrainCheckpointRetentionTests(unittest.TestCase):
    def test_periodic_checkpoint_reuses_single_latest_path(self) -> None:
        module = load_single_train_module()
        saved_paths: list[str] = []
        original = module.utils.save_single_checkpoint

        def fake_save(path, state):
            saved_paths.append(path)

        module.utils.save_single_checkpoint = fake_save
        try:
            module.maybe_write_periodic_checkpoint(
                current_step=1000,
                snapshot_freq_for_preemption=1000,
                latest_checkpoint_path="/tmp/checkpoint_hybrid.pth",
                state={"step": 1000},
                write_latest_checkpoint=True,
            )
            module.maybe_write_periodic_checkpoint(
                current_step=2000,
                snapshot_freq_for_preemption=1000,
                latest_checkpoint_path="/tmp/checkpoint_hybrid.pth",
                state={"step": 2000},
                write_latest_checkpoint=True,
            )
        finally:
            module.utils.save_single_checkpoint = original

        self.assertEqual(
            ["/tmp/checkpoint_hybrid.pth", "/tmp/checkpoint_hybrid.pth"],
            saved_paths,
        )

    def test_eval_suite_passes_catalog_size_to_every_metric_call(self) -> None:
        module = load_single_train_module()
        self.assertIn("valid_item_count", inspect.signature(module.run_eval_suite).parameters)
        observed_counts: list[int] = []

        def fake_evaluate(_model, _sampling_fn, _loader, _device, valid_item_count=None):
            observed_counts.append(valid_item_count)
            return [0.0] * 5, [0.0] * 5

        class FakeEma:
            def store(self, _parameters):
                pass

            def copy_to(self, _parameters):
                pass

            def restore(self, _parameters):
                pass

        class FakeModel:
            def parameters(self):
                return []

        original = module.utils.evaluate_loader
        module.utils.evaluate_loader = fake_evaluate
        try:
            module.run_eval_suite(
                score_model=FakeModel(),
                ema=FakeEma(),
                sampling_fns={key: {"fn": object(), "label": key} for key in ("base", "p2", "p5", "p10")},
                val_loader=object(),
                test_loader=object(),
                device=object(),
                valid_item_count=101,
            )
        finally:
            module.utils.evaluate_loader = original

        self.assertEqual([101] * 8, observed_counts)


if __name__ == "__main__":
    unittest.main()
