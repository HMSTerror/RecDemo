#!/usr/bin/env python3

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import random
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_ROOT = REPO_ROOT / "dataset" / "paper_raw_v1"
DEFAULT_UPSTREAM_ROOT = REPO_ROOT / "third_party" / "DiffuRec"
DEFAULT_RUN_ROOT = REPO_ROOT / "runs" / "close04_diffurec"
DEFAULT_METRIC_KS = (5, 10, 20)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_numpy_legacy_aliases() -> None:
    if not hasattr(np, "int"):
        np.int = int  # type: ignore[attr-defined]


def infer_item_num(dataset_dir: Path) -> tuple[int, Path]:
    protocol_path = dataset_dir / "protocol.json"
    if not protocol_path.exists():
        raise FileNotFoundError(f"missing protocol.json: {protocol_path}")
    protocol = load_json(protocol_path)
    item_num = int(protocol["counts"]["item_num"])
    return item_num, protocol_path


def normalize_sequence(seq: list[int], *, item_num: int) -> list[int]:
    pad_value = item_num
    normalized: list[int] = []
    for token in seq:
        token = int(token)
        if token == pad_value:
            normalized.append(0)
        else:
            normalized.append(token + 1)
    return normalized


def convert_split_frame(frame: pd.DataFrame, *, item_num: int) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for row in frame.itertuples(index=False):
        sequence = normalize_sequence(list(row.seq), item_num=item_num)
        label = int(row.next) + 1
        records.append({"sequence": sequence, "label": label})
    return records


def load_dataset_bundle(dataset_dir: Path) -> dict[str, object]:
    item_num, protocol_path = infer_item_num(dataset_dir)
    protocol = load_json(protocol_path)
    dataset_name = str(protocol.get("dataset", dataset_dir.name))
    bundle = {
        "dataset": dataset_name,
        "dataset_dir": dataset_dir,
        "protocol_path": protocol_path,
        "protocol": protocol,
        "item_num": item_num,
    }
    for split_name in ("train", "val", "test"):
        frame = pd.read_pickle(dataset_dir / f"{split_name}_data.df")
        bundle[f"{split_name}_examples"] = convert_split_frame(frame, item_num=item_num)
    return bundle


class DiffuRecExampleDataset(Dataset):
    def __init__(self, examples: list[dict[str, object]]) -> None:
        self.examples = examples

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, index: int):
        example = self.examples[index]
        return (
            torch.tensor(example["sequence"], dtype=torch.long),
            torch.tensor([int(example["label"])], dtype=torch.long),
        )


def build_dataloader(examples: list[dict[str, object]], *, batch_size: int, shuffle: bool) -> DataLoader:
    return DataLoader(DiffuRecExampleDataset(examples), batch_size=batch_size, shuffle=shuffle, pin_memory=torch.cuda.is_available())


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def load_module_from_path(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_upstream_modules(upstream_root: Path):
    ensure_numpy_legacy_aliases()
    src_dir = upstream_root / "src"
    if not src_dir.exists():
        raise FileNotFoundError(f"missing DiffuRec src directory: {src_dir}")

    step_sample_module = load_module_from_path(
        "close04_diffurec_upstream_step_sample",
        src_dir / "step_sample.py",
    )
    sys.modules["step_sample"] = step_sample_module
    diffurec_module = load_module_from_path(
        "close04_diffurec_upstream_diffurec",
        src_dir / "diffurec.py",
    )
    sys.modules["diffurec"] = diffurec_module
    model_module = load_module_from_path(
        "close04_diffurec_upstream_model",
        src_dir / "model.py",
    )
    return SimpleNamespace(
        model=model_module,
        diffurec=diffurec_module,
        step_sample=step_sample_module,
        src_dir=src_dir,
    )


def topk_metrics(scores: torch.Tensor, labels: torch.Tensor, ks: tuple[int, ...] = DEFAULT_METRIC_KS) -> dict[str, float]:
    max_k = max(ks)
    effective_max_k = min(max_k, int(scores.shape[-1]))
    _, topk_indices = torch.topk(scores, k=effective_max_k, dim=-1)
    labels = labels.view(-1, 1)
    hits = topk_indices.eq(labels)
    metrics: dict[str, float] = {}
    for k in ks:
        effective_k = min(k, effective_max_k)
        topk_hits = hits[:, :effective_k]
        hr = topk_hits.any(dim=1).float().mean().item()
        ndcg_terms = topk_hits.float() / torch.log2(
            torch.arange(2, effective_k + 2, device=scores.device, dtype=torch.float32)
        )
        ndcg = ndcg_terms.sum(dim=1).mean().item()
        metrics[f"HR@{k}"] = hr
        metrics[f"NDCG@{k}"] = ndcg
    return metrics


def evaluate_model(model, data_loader: DataLoader, device: torch.device, ks: tuple[int, ...] = DEFAULT_METRIC_KS) -> dict[str, float]:
    metric_sums = {f"HR@{k}": 0.0 for k in ks}
    metric_sums.update({f"NDCG@{k}": 0.0 for k in ks})
    evaluated_rows = 0
    model.eval()
    with torch.no_grad():
        for sequences, labels in data_loader:
            sequences = sequences.to(device)
            labels = labels.to(device)
            _, rep_diffu, _, _, _, _ = model(sequences, labels, train_flag=False)
            scores = model.diffu_rep_pre(rep_diffu)
            batch_metrics = topk_metrics(scores, labels, ks=ks)
            batch_rows = int(labels.shape[0])
            for key, value in batch_metrics.items():
                metric_sums[key] += value * batch_rows
            evaluated_rows += batch_rows
    return {key: value / evaluated_rows for key, value in metric_sums.items()}


def metric_percent_to_fraction_dict(metrics_percent: dict[str, float]) -> dict[str, float]:
    return {key: float(value) / 100.0 for key, value in metrics_percent.items()}


def build_summary_payload(
    *,
    dataset_name: str,
    upstream_root: Path,
    dataset_dir: Path,
    protocol_path: Path,
    item_num: int,
    random_seed: int,
    best_epoch: int,
    selection_metric: str,
    best_metric_value_percent: float,
    validation_metrics_percent: dict[str, float],
    test_metrics_percent: dict[str, float],
) -> dict[str, object]:
    return {
        "method": "DiffuRec",
        "dataset": dataset_name,
        "upstream_root": str(upstream_root),
        "dataset_dir": str(dataset_dir),
        "protocol_path": str(protocol_path),
        "item_num": int(item_num),
        "random_seed": int(random_seed),
        "selector": {
            "split": "validation",
            "metric": selection_metric,
            "best_epoch": int(best_epoch),
            "best_metric_value": float(best_metric_value_percent) / 100.0,
        },
        "validation": metric_percent_to_fraction_dict(validation_metrics_percent),
        "test": metric_percent_to_fraction_dict(test_metrics_percent),
    }


def get_git_revision(path: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return result.stdout.strip()


def build_manifest_payload(
    *,
    summary_path: Path,
    run_dir: Path,
    upstream_root: Path,
    dataset_dir: Path,
    protocol_path: Path,
    dataset_name: str,
    item_num: int,
    random_seed: int,
    batch_size: int,
    max_len: int,
    epochs: int,
    eval_interval: int,
    patience: int,
    selection_metric: str,
) -> dict[str, object]:
    return {
        "method": "DiffuRec",
        "dataset": dataset_name,
        "summary_path": str(summary_path),
        "run_dir": str(run_dir),
        "upstream_root": str(upstream_root),
        "upstream_revision": get_git_revision(upstream_root),
        "dataset_dir": str(dataset_dir),
        "protocol_path": str(protocol_path),
        "item_num": int(item_num),
        "random_seed": int(random_seed),
        "batch_size": int(batch_size),
        "max_len": int(max_len),
        "epochs": int(epochs),
        "eval_interval": int(eval_interval),
        "patience": int(patience),
        "selection_metric": selection_metric,
        "checkpoint_policy": "latest_plus_best",
        "provenance": {
            "repo_root": str(REPO_ROOT.resolve()),
            "script": str(Path(__file__).resolve()),
        },
    }


def torch_metrics_to_percent(metrics_fraction: dict[str, float]) -> dict[str, float]:
    return {key: float(value) * 100.0 for key, value in metrics_fraction.items()}


def make_upstream_args(args: argparse.Namespace, *, item_num: int):
    return SimpleNamespace(
        hidden_size=args.hidden_size,
        item_num=item_num,
        emb_dropout=args.emb_dropout,
        max_len=args.max_len,
        dropout=args.dropout,
        optimizer="Adam",
        lr=args.lr,
        weight_decay=args.weight_decay,
        momentum=None,
        num_gpu=1,
        schedule_sampler_name=args.schedule_sampler_name,
        diffusion_steps=args.diffusion_steps,
        noise_schedule=args.noise_schedule,
        rescale_timesteps=args.rescale_timesteps,
        num_blocks=args.num_blocks,
        hidden_act="gelu",
        lambda_uncertainty=args.lambda_uncertainty,
        loss_lambda=args.loss_lambda,
        device=str(args.device),
        batch_size=args.batch_size,
    )


def train_close04_diffurec(args: argparse.Namespace) -> dict[str, object]:
    seed_everything(args.random_seed)
    bundle = load_dataset_bundle(args.dataset_dir)
    upstream = load_upstream_modules(args.upstream_root)

    run_dir = args.run_dir
    checkpoint_meta_dir = run_dir / "checkpoints-meta" / bundle["dataset"]
    checkpoint_meta_dir.mkdir(parents=True, exist_ok=True)
    latest_checkpoint_path = checkpoint_meta_dir / "checkpoint_diffurec.pt"
    best_checkpoint_path = checkpoint_meta_dir / "checkpoint_diffurec_best.pt"
    summary_path = checkpoint_meta_dir / "best_summary_diffurec.json"
    manifest_path = checkpoint_meta_dir / "diffurec_run_manifest.json"

    train_loader = build_dataloader(bundle["train_examples"], batch_size=args.batch_size, shuffle=True)
    val_loader = build_dataloader(bundle["val_examples"], batch_size=args.batch_size, shuffle=False)
    test_loader = build_dataloader(bundle["test_examples"], batch_size=args.batch_size, shuffle=False)

    upstream_args = make_upstream_args(args, item_num=int(bundle["item_num"]))
    diffu_model = upstream.model.create_model_diffu(upstream_args)
    model = upstream.model.Att_Diffuse_model(diffu_model, upstream_args).to(args.device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=max(args.decay_step, 1), gamma=args.gamma)

    best_state = None
    best_epoch = 0
    best_metric_value = float("-inf")
    best_val_metrics: dict[str, float] | None = None
    bad_count = 0

    for epoch in range(1, args.epochs + 1):
        model.train()
        last_loss = 0.0
        for sequences, labels in train_loader:
            sequences = sequences.to(args.device)
            labels = labels.to(args.device)
            optimizer.zero_grad()
            _, diffu_rep, _, _, _, _ = model(sequences, labels, train_flag=True)
            loss = model.loss_diffu_ce(diffu_rep, labels)
            loss.backward()
            optimizer.step()
            last_loss = float(loss.item())
        scheduler.step()

        torch.save({"epoch": epoch, "model_state_dict": model.state_dict()}, latest_checkpoint_path)
        print(f"epoch={epoch} train_loss={last_loss:.6f}")

        should_eval = epoch % args.eval_interval == 0 or epoch == args.epochs
        if not should_eval:
            continue

        val_metrics_fraction = evaluate_model(model, val_loader, args.device)
        current_metric = val_metrics_fraction[args.selection_metric]
        print(f"epoch={epoch} {args.selection_metric}={current_metric:.6f}")
        if current_metric > best_metric_value + args.min_delta:
            best_metric_value = current_metric
            best_epoch = epoch
            best_val_metrics = val_metrics_fraction
            best_state = copy.deepcopy(model.state_dict())
            torch.save({"epoch": epoch, "model_state_dict": best_state}, best_checkpoint_path)
            bad_count = 0
        else:
            bad_count += 1
            if args.patience > 0 and bad_count >= args.patience:
                break

    if best_state is None or best_val_metrics is None:
        best_epoch = args.epochs
        best_val_metrics = evaluate_model(model, val_loader, args.device)
        best_metric_value = best_val_metrics[args.selection_metric]
        best_state = copy.deepcopy(model.state_dict())
        torch.save({"epoch": best_epoch, "model_state_dict": best_state}, best_checkpoint_path)

    model.load_state_dict(best_state)
    test_metrics_fraction = evaluate_model(model, test_loader, args.device)

    best_val_metrics_percent = torch_metrics_to_percent(best_val_metrics)
    test_metrics_percent = torch_metrics_to_percent(test_metrics_fraction)
    summary_payload = build_summary_payload(
        dataset_name=str(bundle["dataset"]),
        upstream_root=args.upstream_root,
        dataset_dir=args.dataset_dir,
        protocol_path=Path(bundle["protocol_path"]),
        item_num=int(bundle["item_num"]),
        random_seed=args.random_seed,
        best_epoch=best_epoch,
        selection_metric=args.selection_metric,
        best_metric_value_percent=best_metric_value * 100.0,
        validation_metrics_percent=best_val_metrics_percent,
        test_metrics_percent=test_metrics_percent,
    )
    summary_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    manifest_payload = build_manifest_payload(
        summary_path=summary_path,
        run_dir=run_dir,
        upstream_root=args.upstream_root,
        dataset_dir=args.dataset_dir,
        protocol_path=Path(bundle["protocol_path"]),
        dataset_name=str(bundle["dataset"]),
        item_num=int(bundle["item_num"]),
        random_seed=args.random_seed,
        batch_size=args.batch_size,
        max_len=args.max_len,
        epochs=args.epochs,
        eval_interval=args.eval_interval,
        patience=args.patience,
        selection_metric=args.selection_metric,
    )
    manifest_path.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")
    return {"summary_path": summary_path, "manifest_path": manifest_path}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CLOSE-04 DiffuRec on paper_raw_v1 row-level splits.")
    parser.add_argument("--dataset-name", required=True, help="Dataset label, e.g. ML1M or Beauty.")
    parser.add_argument("--dataset-dir", type=Path, help="paper_raw_v1/<dataset> directory.")
    parser.add_argument("--upstream-root", type=Path, default=DEFAULT_UPSTREAM_ROOT, help="Pinned DiffuRec checkout root.")
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT, help="Root directory for DiffuRec run outputs.")
    parser.add_argument("--random-seed", type=int, default=100)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--cuda-visible-devices", default=None)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--eval-interval", type=int, default=10)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--min-delta", type=float, default=0.0)
    parser.add_argument("--selection-metric", default="NDCG@10", choices=["HR@10", "NDCG@10"])
    parser.add_argument("--max-len", type=int, default=10)
    parser.add_argument("--hidden-size", type=int, default=128)
    parser.add_argument("--num-blocks", type=int, default=4)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--emb-dropout", type=float, default=0.3)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--gamma", type=float, default=0.1)
    parser.add_argument("--decay-step", type=int, default=100)
    parser.add_argument("--loss-lambda", type=float, default=0.001)
    parser.add_argument("--lambda-uncertainty", type=float, default=0.001)
    parser.add_argument("--schedule-sampler-name", default="lossaware")
    parser.add_argument("--diffusion-steps", type=int, default=32)
    parser.add_argument("--noise-schedule", default="trunc_lin")
    parser.add_argument("--rescale-timesteps", action="store_true", default=True)
    args = parser.parse_args()
    if args.dataset_dir is None:
        args.dataset_dir = DEFAULT_DATASET_ROOT / args.dataset_name
    args.run_dir = args.run_root / f"{args.dataset_name.lower()}_diffurec_seed{args.random_seed}"
    args.device = torch.device(args.device)
    return args


def main() -> None:
    args = parse_args()
    if args.cuda_visible_devices is not None:
        os.environ["CUDA_VISIBLE_DEVICES"] = str(args.cuda_visible_devices)
    result = train_close04_diffurec(args)
    print(json.dumps({key: str(value) for key, value in result.items()}, indent=2))


if __name__ == "__main__":
    main()
