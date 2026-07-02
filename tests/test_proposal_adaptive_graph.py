import unittest
from pathlib import Path
import sys

import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import graph_lib


class ProposalAdaptiveGraphTests(unittest.TestCase):
    def test_prob_matrix_row_matches_core_row_semantics_for_identical_proposal(self) -> None:
        graph = graph_lib.ProposalAdaptiveWise(dim=3, is_disliked_item=True)
        core_graph = graph_lib.AdaptiveWise(dim=3, is_disliked_item=True)
        current = torch.tensor([[1]], dtype=torch.long)
        proposal = torch.tensor([[0.2, 0.3, 0.1, 0.4]], dtype=torch.float32)
        with torch.no_grad():
            core_graph.p1.copy_(proposal.squeeze(0).log())

        at_zero = graph.prob_matrix_row(current, torch.tensor([[0.0]]), proposal=proposal)
        self.assertTrue(
            torch.allclose(
                at_zero,
                torch.tensor([[[0.0, 1.0, 0.0, 0.0]]], dtype=torch.float32),
                atol=1e-6,
            )
        )

        sigma = torch.tensor([[1.0]], dtype=torch.float32)
        row = graph.prob_matrix_row(current, sigma, proposal=proposal)
        expected = core_graph.prob_matrix_row(current, sigma)

        self.assertTrue(torch.allclose(row, expected, atol=1e-6))

    def test_sample_nonpreference_can_follow_deterministic_proposal(self) -> None:
        graph = graph_lib.ProposalAdaptiveWise(dim=3, is_disliked_item=True)
        deterministic = torch.tensor([[0.0, 1.0, 0.0, 0.0]], dtype=torch.float32)
        sampled = graph.sample_nonpreference(1, 4, proposal=deterministic)
        self.assertTrue(torch.equal(sampled, torch.ones((1, 4), dtype=torch.long)))

    def test_reverse_prob_ratio_accepts_score_shaped_placeholder(self) -> None:
        graph = graph_lib.ProposalAdaptiveWise(dim=3, is_disliked_item=True)
        score = torch.ones((2, 1, 4), dtype=torch.float32)
        proposal = torch.tensor(
            [
                [0.1, 0.2, 0.3, 0.4],
                [0.4, 0.3, 0.2, 0.1],
            ],
            dtype=torch.float32,
        )
        ratio = graph.reverse_prob_ratio(score, torch.zeros((2, 1), dtype=torch.float32), proposal=proposal)
        self.assertEqual((2, 1, 4), tuple(ratio.shape))


if __name__ == "__main__":
    unittest.main()
