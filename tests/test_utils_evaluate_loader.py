import contextlib
import io
import unittest

import torch

import utils


class EvaluateLoaderTailBatchTest(unittest.TestCase):
    def test_includes_incomplete_tail_batch_in_metrics(self) -> None:
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
            hr_list, ndcg_list = utils.evaluate_loader(
                model=object(),
                sampling_fn=sampling_fn,
                data_loader=[full_batch, tail_batch],
                device=torch.device("cpu"),
            )

        expected_tail_fraction = 11 / 267
        self.assertEqual([256, 11], observed_batch_sizes)
        self.assertAlmostEqual(expected_tail_fraction, hr_list[2])
        self.assertAlmostEqual(expected_tail_fraction, ndcg_list[2])


if __name__ == "__main__":
    unittest.main()
