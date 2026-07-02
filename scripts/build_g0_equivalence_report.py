#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd
import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = REPO_ROOT / "model"
for candidate in (REPO_ROOT, MODEL_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import graph_lib
from text_side import TextSideProposalBuilder


DEFAULT_OUTPUT_PATH = REPO_ROOT / "docs" / "reports" / "data" / "g0_equivalence_report.csv"
ATOL = 1e-6


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the g==0 equivalence report comparing the v2 proposal kernel to core PreferGrow."
    )
    parser.add_argument("--output", default=None, help="Output CSV path")
    return parser.parse_args()


def _make_builder() -> TextSideProposalBuilder:
    return TextSideProposalBuilder(
        item_embeddings=torch.tensor(
            [
                [1.0, 0.0],
                [0.8, 0.2],
                [0.0, 1.0],
                [-1.0, 0.0],
            ],
            dtype=torch.float32,
        ),
        item_completeness=torch.tensor([1.0, 0.8, 0.5, 1.0], dtype=torch.float32),
        item_num=4,
        is_disliked_item=True,
        kernel_version="v2",
        g_max=0.5,
        ablation_mode="global_p",
        center_embeddings=True,
    )


def _make_history() -> torch.Tensor:
    return torch.tensor(
        [
            [0, 1, 4, 4],
            [2, 3, 1, 4],
        ],
        dtype=torch.long,
    )


def _load_g0_context(core_logits: torch.Tensor) -> tuple[graph_lib.AdaptiveWise, graph_lib.ProposalAdaptiveWise, torch.Tensor]:
    builder = _make_builder()
    core_graph = graph_lib.AdaptiveWise(dim=builder.item_num, is_disliked_item=True)
    proposal_graph = graph_lib.ProposalAdaptiveWise(dim=builder.item_num, is_disliked_item=True)

    with torch.no_grad():
        builder.p1.copy_(core_logits)
        core_graph.p1.copy_(core_logits)

    context = builder.encode_history_context(_make_history())
    proposal = context["proposal"].detach().cpu()
    g = context["g"].detach().cpu()
    if not torch.allclose(g, torch.zeros_like(g), atol=0.0):
        raise AssertionError(f"expected g==0 under global_p, got {g.tolist()}")
    return core_graph, proposal_graph, proposal


def _max_abs_diff(lhs: torch.Tensor, rhs: torch.Tensor) -> float:
    return float((lhs.detach().cpu().float() - rhs.detach().cpu().float()).abs().max().item())


def _make_row(check: str, diff: float, detail: str) -> dict[str, object]:
    return {
        "check": check,
        "status": "pass" if diff <= ATOL else "fail",
        "max_abs_diff": round(float(diff), 10),
        "detail": detail,
    }


def build_equivalence_report(output_path: Path | str | None = None) -> list[dict[str, object]]:
    output_path = Path(output_path) if output_path is not None else DEFAULT_OUTPUT_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)

    general_logits = torch.tensor([1.5, -0.25, 0.75, -1.0, 0.5], dtype=torch.float32)
    core_graph, proposal_graph, proposal = _load_g0_context(general_logits)
    core_probs = core_graph.nonpreference_probs().detach().cpu().unsqueeze(0).expand_as(proposal)

    x = torch.tensor([[0], [3]], dtype=torch.long)
    int_beta = torch.tensor([[0.37], [0.92]], dtype=torch.float32)
    score = torch.tensor(
        [
            [[0.20, -0.10, 0.35, 0.05, -0.25]],
            [[-0.30, 0.40, -0.15, 0.55, 0.10]],
        ],
        dtype=torch.float32,
    )
    exp_score = torch.tensor(
        [
            [[1.10, 0.80, 1.35, 0.95, 0.75]],
            [[0.70, 1.45, 0.85, 1.25, 1.05]],
        ],
        dtype=torch.float32,
    )
    target = torch.tensor([1, 2], dtype=torch.long)

    rows = [
        _make_row(
            "proposal",
            _max_abs_diff(proposal, core_probs),
            "TextSideProposalBuilder(kernel_version=v2, ablation_mode=global_p) reproduces core softmax(p1).",
        ),
        _make_row(
            "prob_matrix_row",
            _max_abs_diff(
                core_graph.prob_matrix_row(x, int_beta),
                proposal_graph.prob_matrix_row(x, int_beta, proposal=proposal),
            ),
            "Forward corruption transition rows match under identical p1 and shared pseudo coordinate.",
        ),
        _make_row(
            "score_entropy",
            _max_abs_diff(
                core_graph.score_entropy(score, int_beta, x, target),
                proposal_graph.score_entropy(score, int_beta, x, target, proposal=proposal),
            ),
            "score_entropy matches on the real AdaptiveWise and ProposalAdaptiveWise implementations.",
        ),
        _make_row(
            "reverse_prob_ratio",
            _max_abs_diff(
                core_graph.reverse_prob_ratio(exp_score, int_beta),
                proposal_graph.reverse_prob_ratio(exp_score, int_beta, proposal=proposal),
            ),
            "reverse_prob_ratio matches on the analytic reverse path used by sampling.",
        ),
    ]

    deterministic_logits = torch.tensor([1000.0, 0.0, -1000.0, -1000.0, -1000.0], dtype=torch.float32)
    det_core_graph, det_proposal_graph, det_proposal = _load_g0_context(deterministic_logits)
    det_x = torch.tensor([[4], [2]], dtype=torch.long)
    det_beta = torch.tensor([[0.35], [0.80]], dtype=torch.float32)

    torch.manual_seed(20260702)
    core_sample_prob = det_core_graph.sample_prob(det_x, det_beta)
    torch.manual_seed(20260702)
    proposal_sample_prob = det_proposal_graph.sample_prob(det_x, det_beta, proposal=det_proposal)
    rows.append(
        _make_row(
            "sample_prob",
            _max_abs_diff(core_sample_prob, proposal_sample_prob),
            "sample_prob draws match exactly in a deterministic g==0 core-proposal regime.",
        )
    )

    torch.manual_seed(20260702)
    core_nonpref = det_core_graph.sample_nonpreference(2, 3)
    torch.manual_seed(20260702)
    proposal_nonpref = det_proposal_graph.sample_nonpreference(2, 3, proposal=det_proposal)
    rows.append(
        _make_row(
            "sample_nonpreference",
            _max_abs_diff(core_nonpref, proposal_nonpref),
            "sample_nonpreference draws match exactly in the same deterministic regime.",
        )
    )

    pd.DataFrame(rows).to_csv(output_path, index=False)
    return rows


def main() -> None:
    args = parse_args()
    rows = build_equivalence_report(output_path=args.output)
    print(f"wrote {Path(args.output).resolve() if args.output else DEFAULT_OUTPUT_PATH.resolve()}")
    print(pd.DataFrame(rows).to_csv(index=False).strip())


if __name__ == "__main__":
    main()
