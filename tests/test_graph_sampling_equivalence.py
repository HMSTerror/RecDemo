import unittest
from types import SimpleNamespace

import torch

from graph_lib import AdaptiveWise, ProposalAdaptiveWise


class GraphSamplingEquivalenceTests(unittest.TestCase):
    def test_graph_factory_honors_requested_parameter_device(self):
        config = SimpleNamespace(
            training=SimpleNamespace(data="Beauty"),
            data=SimpleNamespace(Beauty=SimpleNamespace(item_num=3)),
            graph=SimpleNamespace(type="adaptive", is_disliked_item=True),
        )

        graph = __import__("graph_lib").get_graph(config, torch.device("meta"))

        self.assertEqual("meta", str(graph.p1.device))

    def _graphs(self):
        dimension = 7
        host = AdaptiveWise(dimension, True)
        proposal_graph = ProposalAdaptiveWise(dimension, True)
        with torch.no_grad():
            host.p1.copy_(torch.linspace(-1.0, 1.0, dimension + 1))
        proposal = torch.softmax(host.p1, dim=-1).view(1, 1, -1).expand(4, 3, -1)
        return host, proposal_graph, proposal

    def test_row_constant_proposal_matches_host_nonpreference_sampling_and_rng(self):
        host, proposal_graph, proposal = self._graphs()

        torch.manual_seed(100)
        host_sample = host.sample_nonpreference(4, 3)
        host_rng = torch.get_rng_state().clone()
        torch.manual_seed(100)
        proposal_sample = proposal_graph.sample_nonpreference(4, 3, proposal=proposal)
        proposal_rng = torch.get_rng_state().clone()

        self.assertTrue(torch.equal(host_sample, proposal_sample))
        self.assertTrue(torch.equal(host_rng, proposal_rng))

    def test_row_constant_proposal_matches_host_transition_sampling_and_rng(self):
        host, proposal_graph, proposal = self._graphs()
        states = torch.tensor(
            [[0, 1, 2], [3, 4, 5], [6, 7, 0], [1, 2, 3]],
            dtype=torch.long,
        )
        sigma = torch.full(states.shape, 0.2)

        torch.manual_seed(101)
        host_sample = host.sample_prob(states, sigma)
        host_rng = torch.get_rng_state().clone()
        torch.manual_seed(101)
        proposal_sample = proposal_graph.sample_prob(states, sigma, proposal=proposal)
        proposal_rng = torch.get_rng_state().clone()

        self.assertTrue(torch.equal(host_sample, proposal_sample))
        self.assertTrue(torch.equal(host_rng, proposal_rng))

    def test_nonconstant_proposal_keeps_rowwise_sampling(self):
        _, proposal_graph, proposal = self._graphs()
        proposal = proposal.clone()
        proposal[0, 0] = torch.roll(proposal[0, 0], shifts=1, dims=0)
        proposal[2, 1] = torch.roll(proposal[2, 1], shifts=-1, dims=0)
        proposal = proposal / proposal.sum(dim=-1, keepdim=True)

        torch.manual_seed(102)
        sample = proposal_graph.sample_nonpreference(4, 3, proposal=proposal)

        self.assertEqual((4, 3), tuple(sample.shape))
        self.assertTrue(bool(torch.all((sample >= 0) & (sample < proposal.shape[-1]))))

    def test_row_constant_proposal_score_entropy_has_host_gradient_identity(self):
        host = AdaptiveWise(4, True)
        proposal_graph = ProposalAdaptiveWise(4, True)
        values = torch.tensor([0.2, -0.1, 0.4, 0.7, -0.3], dtype=torch.float32)
        with torch.no_grad():
            host.p1.copy_(values)
        proposal_logits = torch.nn.Parameter(values.clone())
        proposal = torch.softmax(proposal_logits, dim=-1).unsqueeze(0).expand(4, -1)
        score = torch.tensor(
            [
                [[0.20, -0.10, 0.35, 0.05, -0.25]] * 3,
                [[-0.30, 0.40, -0.15, 0.55, 0.10]] * 3,
                [[0.15, 0.25, -0.45, 0.30, -0.05]] * 3,
                [[-0.20, 0.05, 0.10, -0.35, 0.45]] * 3,
            ],
            dtype=torch.float32,
        )
        int_beta = torch.tensor([[0.37], [0.92], [0.21], [0.63]], dtype=torch.float32)
        states = torch.tensor([[0, 1, 2], [3, 4, 0], [2, 1, 4], [1, 3, 0]], dtype=torch.long)
        targets = torch.tensor([1, 2, 4, 0], dtype=torch.long)

        host_loss = host.score_entropy(score, int_beta, states, targets).sum()
        proposal_loss = proposal_graph.score_entropy(
            score,
            int_beta,
            states,
            targets,
            proposal=proposal,
        ).sum()
        self.assertTrue(torch.equal(host_loss.detach(), proposal_loss.detach()))

        host_loss.backward()
        proposal_loss.backward()
        self.assertTrue(torch.equal(host.p1.grad, proposal_logits.grad))


if __name__ == "__main__":
    unittest.main()
