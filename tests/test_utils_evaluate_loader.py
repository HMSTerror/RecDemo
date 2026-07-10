import contextlib
import inspect
import io
import unittest

import torch

import utils


class EvaluateLoaderTailBatchTest(unittest.TestCase):
    def test_includes_incomplete_tail_batch_in_metrics(self) -> None:
        self.assertIn("return_evaluated_rows", inspect.signature(utils.evaluate_loader).parameters)
        full_batch = {
            "seq": torch.zeros((256, 10), dtype=torch.long),
            "next": torch.zeros(256, dtype=torch.long),
        }
        tail_batch = {
            "seq": torch.ones((11, 10), dtype=torch.long),
            "next": torch.zeros(11, dtype=torch.long),
        }
        observed_batch_sizes: list[int] = []

        def sampling_fn(_model, _shape, history):
            observed_batch_sizes.append(len(history))
            scores = torch.arange(101, dtype=torch.float32).repeat(len(history), 1)
            tail_rows = history[:, 0].eq(1)
            scores[tail_rows, 0] = 1_000.0
            return scores.unsqueeze(1)

        with contextlib.redirect_stdout(io.StringIO()):
            hr_list, ndcg_list, evaluated_rows = utils.evaluate_loader(
                model=object(),
                sampling_fn=sampling_fn,
                data_loader=[full_batch, tail_batch],
                device=torch.device("cpu"),
                return_evaluated_rows=True,
            )

        expected_tail_fraction = 11 / 267
        self.assertEqual([256, 11], observed_batch_sizes)
        self.assertEqual(267, evaluated_rows)
        self.assertAlmostEqual(expected_tail_fraction, hr_list[2])
        self.assertAlmostEqual(expected_tail_fraction, ndcg_list[2])

    def test_excludes_non_catalog_state_from_ranking(self) -> None:
        self.assertIn("valid_item_count", inspect.signature(utils.evaluate_loader).parameters)
        batch = {
            "seq": torch.zeros((2, 10), dtype=torch.long),
            "next": torch.zeros(2, dtype=torch.long),
        }

        def sampling_fn(_model, _shape, history):
            scores = torch.arange(101, dtype=torch.float32).repeat(len(history), 1)
            scores[:, 0] = 1_000.0
            pseudo_scores = torch.full((len(history), 1), 2_000.0)
            return torch.cat([scores, pseudo_scores], dim=1).unsqueeze(1)

        with contextlib.redirect_stdout(io.StringIO()):
            hr_list, ndcg_list = utils.evaluate_loader(
                model=object(),
                sampling_fn=sampling_fn,
                data_loader=[batch],
                device=torch.device("cpu"),
                valid_item_count=101,
            )

        self.assertEqual(1.0, hr_list[0])
        self.assertEqual(1.0, ndcg_list[0])


if __name__ == "__main__":
    unittest.main()
