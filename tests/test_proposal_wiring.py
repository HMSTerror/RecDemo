import unittest
from pathlib import Path
import sys
import importlib.util
import types

import torch
import torch.nn as nn

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


model_pkg = types.ModuleType("model")
model_pkg.__path__ = [str(REPO_ROOT / "model")]
sys.modules["model"] = model_pkg
model_utils = load_module("model.utils", REPO_ROOT / "model" / "utils.py")
setattr(model_pkg, "utils", model_utils)
losses = load_module("losses", REPO_ROOT / "losses.py")
sampling = load_module("sampling", REPO_ROOT / "sampling.py")


class DummyNoise(nn.Module):
    def forward(self, t):
        sigma = torch.ones_like(t)
        dsigma = torch.ones_like(t) * 0.5
        return sigma, dsigma


class DummyGraph:
    def __init__(self, entropy_value: float = 0.0):
        self.sample_prob_calls = []
        self.score_entropy_calls = []
        self.sample_nonpreference_calls = []
        self.reverse_prob_ratio_calls = []
        self.prob_matrix_row_calls = []
        self.entropy_value = float(entropy_value)

    def sample_prob(self, target, sigma, proposal=None):
        self.sample_prob_calls.append(proposal.clone())
        return target

    def score_entropy(self, score, sigma, x, x0, proposal=None):
        self.score_entropy_calls.append(proposal.clone())
        return torch.full((score.shape[0], score.shape[1]), self.entropy_value, device=score.device)

    def sample_nonpreference(self, *batch_dims, proposal=None):
        self.sample_nonpreference_calls.append(proposal.clone())
        return torch.zeros(*batch_dims, dtype=torch.long)

    def reverse_prob_ratio(self, score, dsigma, proposal=None):
        self.reverse_prob_ratio_calls.append(proposal.clone())
        return torch.ones_like(score)

    def prob_matrix_row(self, x, dsigma, proposal=None):
        self.prob_matrix_row_calls.append(proposal.clone())
        return torch.ones(*x.shape, 4, device=x.device) / 4.0


class DummyModel(nn.Module):
    def encode_history_context(self, history):
        proposal = torch.tensor([[0.1, 0.2, 0.3, 0.4]], dtype=torch.float32, device=history.device)
        return {"proposal": proposal.expand(history.shape[0], -1)}

    def forward(self, history, noisy_indices, sigma):
        batch = history.shape[0]
        return torch.zeros(batch, noisy_indices.shape[1], 4, device=history.device)

    def forward_eval(self, history, noisy_indices, sigma, personalized_strength):
        batch = history.shape[0]
        return torch.zeros(batch, noisy_indices.shape[1], 4, device=history.device)


class DummyLossInjectionModel(DummyModel):
    def encode_history_context(self, history):
        proposal = torch.tensor([[0.1, 0.2, 0.3, 0.4]], dtype=torch.float32, device=history.device)
        loss_weight = torch.tensor([1.0, 2.0], dtype=torch.float32, device=history.device)
        return {
            "proposal": proposal.expand(history.shape[0], -1),
            "loss_weight": loss_weight[: history.shape[0]],
        }


class ProposalWiringTests(unittest.TestCase):
    def test_training_loss_passes_history_only_proposal(self) -> None:
        graph = DummyGraph()
        noise = DummyNoise()
        model = DummyModel()
        loss_fn = losses.get_loss_fn(noise, graph, train=True, loss_type="score_entropy")

        batch = {
            "seq": torch.tensor([[0, 1, 2]], dtype=torch.long),
            "len_seq": torch.tensor([3], dtype=torch.long),
            "next": torch.tensor([1], dtype=torch.long),
        }

        loss = loss_fn(model, batch, steps=4)
        self.assertTrue(torch.isfinite(loss).all())
        self.assertEqual(1, len(graph.sample_prob_calls))
        self.assertEqual(1, len(graph.score_entropy_calls))
        self.assertTrue(torch.allclose(graph.sample_prob_calls[0], graph.score_entropy_calls[0]))
        self.assertTrue(torch.allclose(graph.sample_prob_calls[0], torch.tensor([[0.1, 0.2, 0.3, 0.4]])))

    def test_training_loss_applies_text_side_loss_weights(self) -> None:
        graph = DummyGraph(entropy_value=1.0)
        noise = DummyNoise()
        model = DummyLossInjectionModel()
        loss_fn = losses.get_loss_fn(noise, graph, train=True, loss_type="score_entropy")

        batch = {
            "seq": torch.tensor([[0, 1, 2], [2, 1, 0]], dtype=torch.long),
            "len_seq": torch.tensor([3, 3], dtype=torch.long),
            "next": torch.tensor([1, 2], dtype=torch.long),
        }

        loss = loss_fn(model, batch, steps=4)
        self.assertTrue(torch.allclose(loss, torch.tensor([0.5, 1.0], dtype=torch.float32)))

    def test_sampler_passes_history_only_proposal(self) -> None:
        graph = DummyGraph()
        noise = DummyNoise()
        model = DummyModel()
        config = type(
            "Cfg",
            (),
            {
                "sampling": type("SamplingCfg", (), {"predictor": "analytic", "steps": 2, "noise_removal": True})(),
            },
        )()

        sampler = sampling.get_sampling_fn(config, graph, noise, 1e-5, personalization_strength=2, device=torch.device("cpu"))
        result = sampler(model, (1, 1), torch.tensor([[0, 1, 2]], dtype=torch.long))

        self.assertEqual(1, len(graph.sample_nonpreference_calls))
        self.assertTrue(torch.allclose(graph.sample_nonpreference_calls[0], torch.tensor([[0.1, 0.2, 0.3, 0.4]])))
        self.assertGreaterEqual(len(graph.reverse_prob_ratio_calls), 1)
        self.assertGreaterEqual(len(graph.prob_matrix_row_calls), 1)
        for call in graph.reverse_prob_ratio_calls:
            self.assertTrue(torch.allclose(call, torch.tensor([[0.1, 0.2, 0.3, 0.4]])))
        for call in graph.prob_matrix_row_calls:
            self.assertTrue(torch.allclose(call, torch.tensor([[0.1, 0.2, 0.3, 0.4]])))
        self.assertEqual((1, 1, 4), tuple(result.shape))


if __name__ == "__main__":
    unittest.main()
