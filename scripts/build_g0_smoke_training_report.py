#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tempfile

import pandas as pd
import torch
from omegaconf import OmegaConf
from torch.utils.data import DataLoader

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = REPO_ROOT / "model"
for candidate in (REPO_ROOT, MODEL_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import data
import graph_lib
import losses
import noise_lib
from model.transformer import SEDD4REC


DEFAULT_OUTPUT_PATH = REPO_ROOT / "docs" / "reports" / "data" / "g0_smoke_training_curve.csv"
ITEM_NUM = 120
SEQ_LEN = 4
TRAIN_ROWS = 256
VAL_ROWS = 256
TRAIN_BATCH_SIZE = 64
VAL_BATCH_SIZE = 256
TRAIN_STEPS = 3
SAMPLING_STEPS = 2
PERSONALIZATION_STRENGTH = 2
ATOL = 1e-6


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a short same-seed smoke training comparison for core AdaptiveWise vs v2/global_p."
    )
    parser.add_argument("--output", default=None, help="Output CSV path")
    return parser.parse_args()


def _set_seed(seed: int) -> None:
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _build_rows(count: int, offset: int) -> pd.DataFrame:
    records = []
    for idx in range(count):
        start = (idx + offset) % ITEM_NUM
        seq = [int((start + shift) % ITEM_NUM) for shift in range(SEQ_LEN)]
        records.append(
            {
                "seq": seq,
                "len_seq": SEQ_LEN,
                "next": int((start + SEQ_LEN) % ITEM_NUM),
            }
        )
    return pd.DataFrame(records)


def _write_text_side_artifacts(dataset_dir: Path) -> Path:
    metadata_rows = []
    for item_id in range(ITEM_NUM):
        metadata_rows.append(
            {
                "item_id": item_id,
                "source_id": f"item-{item_id}",
                "title": f"Item {item_id}",
                "brand": f"Brand {item_id % 7}",
                "categories": f"Category {item_id % 11}",
                "description": f"Synthetic description {item_id}",
                "text": f"Item {item_id}. Brand {item_id % 7}. Category {item_id % 11}. Synthetic description {item_id}",
            }
        )
    pd.DataFrame(metadata_rows).to_csv(dataset_dir / "item_metadata.csv", index=False)

    generator = torch.Generator().manual_seed(20260702)
    embeddings = torch.randn((ITEM_NUM, 8), generator=generator, dtype=torch.float32)
    field_coverage = torch.ones(ITEM_NUM, dtype=torch.float32)
    embeddings_path = dataset_dir / "sentence_t5_xl_item_emb.pt"
    torch.save(
        {
            "item_ids": list(range(ITEM_NUM)),
            "embeddings": embeddings,
            "field_coverage": field_coverage,
        },
        embeddings_path,
    )
    return embeddings_path


def _build_config(dataset_dir: Path, graph_type: str, text_side_enabled: bool, embeddings_path: Path) -> object:
    return OmegaConf.create(
        {
            "training": {
                "data": "Beauty",
                "batch_size": TRAIN_BATCH_SIZE,
                "accum": 1,
                "nonpreference_user_ratio": 0.0,
            },
            "data": {
                "Beauty": {
                    "path": str(dataset_dir),
                    "seq_len": SEQ_LEN,
                    "item_num": ITEM_NUM,
                }
            },
            "graph": {
                "type": graph_type,
                "is_disliked_item": True,
                "gamma": 0.5,
            },
            "noise": {
                "type": "geometric",
                "sigma_min": 1e-3,
                "sigma_max": 1.0,
            },
            "sampling": {
                "predictor": "analytic",
                "steps": SAMPLING_STEPS,
                "noise_removal": True,
                "personalization_strength": PERSONALIZATION_STRENGTH,
            },
            "model": {
                "hidden_size": 16,
                "cond_dim": 16,
                "length": SEQ_LEN,
                "n_blocks": 1,
                "n_heads": 2,
                "scale_by_sigma": False,
                "dropout": 0.0,
                "score_flag": False,
                "score_method": "diffcos",
            },
            "text_side": {
                "enabled": text_side_enabled,
                "dataset_dir": str(dataset_dir),
                "embeddings_path": str(embeddings_path),
                "kernel_version": "v2",
                "g_max": 0.5,
                "ablation_mode": "global_p",
                "injection_mode": "kernel",
                "temperature": 0.2,
                "min_pseudo_mass": 0.05,
                "agreement_k": 2.0,
                "agreement_weight": 0.45,
                "completeness_weight": 0.15,
                "history_reliability_weight": 0.40,
                "ess_weight": 0.20,
                "recency_weight": 0.30,
                "stability_weight": 0.50,
                "max_temperature_scale": 2.0,
                "popularity_mix_scale": 1.0,
                "popularity_mix_power": 1.0,
                "center_embeddings": False,
                "pseudo_mass_scale": 1.0,
                "pseudo_mass_power": 1.0,
                "loss_weight_scale": 1.0,
            },
        }
    )


def _materialize_train_batches() -> list[dict[str, torch.Tensor]]:
    train_loader = DataLoader(data.SeqDataset(_build_rows(TRAIN_ROWS, offset=0)), batch_size=TRAIN_BATCH_SIZE)
    return [batch for batch in train_loader]


def _build_val_loader() -> DataLoader:
    return DataLoader(data.SeqDataset(_build_rows(VAL_ROWS, offset=17)), batch_size=VAL_BATCH_SIZE)


def _make_eval_batch() -> dict[str, torch.Tensor]:
    return next(iter(_build_val_loader()))


def _make_eval_noisy(target: torch.Tensor) -> torch.Tensor:
    return ((target + 1) % ITEM_NUM).unsqueeze(-1)


def _ndcg_at_k(logits: torch.Tensor, target: torch.Tensor, k: int = 10) -> float:
    _, topk = logits.topk(k, dim=1, largest=True, sorted=True)
    total = 0.0
    for row_index, true_item in enumerate(target.tolist()):
        positions = (topk[row_index] == int(true_item)).nonzero(as_tuple=False)
        if positions.numel() == 0:
            continue
        rank = int(positions[0].item()) + 1
        total += 1.0 / torch.log2(torch.tensor(rank + 1.0)).item()
    return total / float(target.shape[0])


@torch.no_grad()
def _evaluate_p2_ndcg10(model: SEDD4REC, eval_batch: dict[str, torch.Tensor], device: torch.device) -> float:
    history = eval_batch["seq"].to(device)
    target = eval_batch["next"].to(device)
    noisy_indices = _make_eval_noisy(target).to(device)
    sigma = torch.full((history.shape[0],), 0.5, dtype=torch.float32, device=device)
    logits = model.forward_eval(history, noisy_indices, sigma, PERSONALIZATION_STRENGTH).squeeze(1)
    return _ndcg_at_k(logits.cpu(), target.cpu(), k=10)


def _sample_shared_corruption(
    graph: graph_lib.AdaptiveWise,
    noise: torch.nn.Module,
    target: torch.Tensor,
    steps: int,
    seed: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    _set_seed(seed)
    t_candidates = torch.linspace(1.0, 1e-3, steps + 1, device=target.device)
    t = t_candidates[torch.randint(0, steps + 1, (target.shape[0],), device=target.device)]
    sigma = noise(t)[0]
    _set_seed(seed + 1000)
    perturbed_target = graph.sample_prob(target[:, None], sigma[:, None])
    return t, perturbed_target


def _copy_shared_weights(core_model: SEDD4REC, proposal_model: SEDD4REC) -> None:
    proposal_model.load_state_dict(core_model.state_dict(), strict=False)


def build_smoke_training_report(output_path: Path | str | None = None) -> list[dict[str, object]]:
    output_path = Path(output_path) if output_path is not None else DEFAULT_OUTPUT_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)

    device = torch.device("cpu")
    train_batches = _materialize_train_batches()
    eval_batch = _make_eval_batch()

    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_dir = Path(tmpdir)
        embeddings_path = _write_text_side_artifacts(dataset_dir)

        core_cfg = _build_config(dataset_dir, graph_type="adaptive", text_side_enabled=False, embeddings_path=embeddings_path)
        proposal_cfg = _build_config(
            dataset_dir,
            graph_type="proposal_adaptive",
            text_side_enabled=True,
            embeddings_path=embeddings_path,
        )

        _set_seed(20260702)
        core_model = SEDD4REC(core_cfg).to(device)
        _set_seed(20260702)
        proposal_model = SEDD4REC(proposal_cfg).to(device)
        _copy_shared_weights(core_model, proposal_model)

        core_graph = graph_lib.get_graph(core_cfg, device)
        proposal_graph = graph_lib.get_graph(proposal_cfg, device)
        core_noise = noise_lib.get_noise(core_cfg).to(device)
        proposal_noise = noise_lib.get_noise(proposal_cfg).to(device)

        core_loss_fn = losses.get_loss_fn(core_noise, core_graph, train=True, loss_type="score_entropy")
        proposal_loss_fn = losses.get_loss_fn(proposal_noise, proposal_graph, train=True, loss_type="score_entropy")

        core_optimizer = torch.optim.AdamW(
            list(core_model.parameters()) + list(core_graph.parameters()),
            lr=1e-3,
            betas=(0.9, 0.999),
            eps=1e-8,
            weight_decay=0.0,
        )
        proposal_optimizer = torch.optim.AdamW(
            list(proposal_model.parameters()),
            lr=1e-3,
            betas=(0.9, 0.999),
            eps=1e-8,
            weight_decay=0.0,
        )

        rows = []
        for step in range(1, TRAIN_STEPS + 1):
            batch = {key: value.to(device) for key, value in train_batches[(step - 1) % len(train_batches)].items()}
            shared_t, shared_perturbed_target = _sample_shared_corruption(
                graph=core_graph,
                noise=core_noise,
                target=batch["next"],
                steps=SAMPLING_STEPS,
                seed=7000 + step,
            )

            core_model.train()
            core_optimizer.zero_grad(set_to_none=True)
            core_loss = core_loss_fn(
                core_model,
                batch,
                SAMPLING_STEPS,
                t=shared_t,
                perturbed_target=shared_perturbed_target,
            ).mean()
            core_loss.backward()
            core_optimizer.step()

            proposal_model.train()
            proposal_optimizer.zero_grad(set_to_none=True)
            proposal_loss = proposal_loss_fn(
                proposal_model,
                batch,
                SAMPLING_STEPS,
                t=shared_t,
                perturbed_target=shared_perturbed_target,
            ).mean()
            proposal_loss.backward()
            proposal_optimizer.step()

            core_metric = _evaluate_p2_ndcg10(core_model, eval_batch, device)
            proposal_metric = _evaluate_p2_ndcg10(proposal_model, eval_batch, device)

            rows.append(
                {
                    "step": step,
                    "core_train_loss": float(core_loss.detach().cpu().item()),
                    "proposal_train_loss": float(proposal_loss.detach().cpu().item()),
                    "train_loss_abs_diff": float(abs(core_loss.detach().cpu().item() - proposal_loss.detach().cpu().item())),
                    "core_val_p2_ndcg10": core_metric,
                    "proposal_val_p2_ndcg10": proposal_metric,
                    "val_p2_ndcg10_abs_diff": float(abs(core_metric - proposal_metric)),
                }
            )

    pd.DataFrame(rows).to_csv(output_path, index=False)
    return rows


def main() -> None:
    args = parse_args()
    rows = build_smoke_training_report(output_path=args.output)
    print(f"wrote {Path(args.output).resolve() if args.output else DEFAULT_OUTPUT_PATH.resolve()}")
    print(pd.DataFrame(rows).to_csv(index=False).strip())


if __name__ == "__main__":
    main()
