import tempfile
import unittest
from pathlib import Path

import torch

import utils
from model.ema import ExponentialMovingAverage


class HostGraph(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.p1 = torch.nn.Parameter(torch.tensor([0.25, -0.75]))


class GraphCheckpointContractTests(unittest.TestCase):
    def test_single_checkpoint_persists_graph_state_and_parameter_order(self) -> None:
        model = torch.nn.Linear(2, 1, bias=False)
        graph = HostGraph()
        training_parameters = [*model.parameters(), graph.p1]
        optimizer = torch.optim.SGD(training_parameters, lr=0.1)
        ema = ExponentialMovingAverage(training_parameters, decay=0.9)
        state = {
            "optimizer": optimizer,
            "model": model,
            "graph": graph,
            "ema": ema,
            "training_parameter_names": ["model.weight", "graph.p1"],
            "step": 7,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_path = Path(tmpdir) / "checkpoint.pth"
            utils.save_single_checkpoint(checkpoint_path, state)
            checkpoint = torch.load(
                checkpoint_path,
                map_location="cpu",
                weights_only=False,
            )

        self.assertEqual(
            ["model.weight", "graph.p1"],
            checkpoint["training_parameter_names"],
        )
        self.assertTrue(torch.equal(graph.p1.detach(), checkpoint["graph"]["p1"]))

    def test_single_checkpoint_keeps_legacy_nonmodule_graph_compatible(self) -> None:
        model = torch.nn.Linear(2, 1, bias=False)
        optimizer = torch.optim.SGD(model.parameters(), lr=0.1)
        ema = ExponentialMovingAverage(model.parameters(), decay=0.9)
        state = {
            "optimizer": optimizer,
            "model": model,
            "graph": object(),
            "ema": ema,
            "training_parameter_names": ["model.weight"],
            "step": 3,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_path = Path(tmpdir) / "checkpoint.pth"
            utils.save_single_checkpoint(checkpoint_path, state)
            checkpoint = torch.load(
                checkpoint_path,
                map_location="cpu",
                weights_only=False,
            )

        self.assertNotIn("graph", checkpoint)


if __name__ == "__main__":
    unittest.main()
