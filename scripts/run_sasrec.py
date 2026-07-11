#!/usr/bin/env python3
"""Run the audited PreferGrow SASRec baseline for one frozen dataset.

This adapter deliberately owns no preprocessing: it reads the paper_raw_v1
frames that are supplied on the command line, uses the full real-item catalog,
selects a checkpoint from validation NDCG@10, and writes a dated artifact set.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import torch
from torch import nn


EVALUATOR_VERSION = "e0_full_tail_v2"
SELECTOR_VERSION = "validation-ndcg10-rowweighted-v1"
DATASETS = ("Steam", "ML1M", "Beauty", "ATG")
SPLIT_FILES = ("protocol.json", "item_mapping.csv", "train_data.df", "val_data.df", "test_data.df")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_named_files(root: Path, names: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for name in names:
        path = root / name
        if not path.is_file():
            raise FileNotFoundError(f"missing protocol input: {path}")
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def canonical_hash(payload: Any) -> str:
    value = dict(payload) if isinstance(payload, dict) else payload
    if isinstance(value, dict):
        value.pop("artifact_sha256", None)
        value.pop("manifest_sha256", None)
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


def load_protocol(dataset_dir: Path) -> dict[str, Any]:
    protocol_path = dataset_dir / "protocol.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("protocol_version") != "paper_raw_v1":
        raise ValueError(f"unsupported dataset protocol: {protocol_path}")
    if protocol.get("dataset") not in DATASETS:
        raise ValueError(f"protocol dataset is not in the four-domain contract: {protocol_path}")
    return protocol


def _stack_sequences(series: pd.Series, *, expected_length: int, item_num: int, split: str) -> np.ndarray:
    values = np.asarray(list(series), dtype=np.int64)
    if values.ndim != 2 or values.shape[1] != expected_length:
        raise ValueError(f"{split} seq shape must be (N,{expected_length}), got {values.shape}")
    if int(values.min()) < 0 or int(values.max()) > item_num:
        raise ValueError(f"{split} history contains an item outside [0,{item_num}] including padding")
    if np.any(values[:, -1] == item_num):
        raise ValueError(f"{split} has a padded final position; paper_raw_v1 requires the last item to be real")
    return values


def load_split(dataset_dir: Path, split: str, protocol: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    frame_path = dataset_dir / f"{split}_data.df"
    frame = pd.read_pickle(frame_path).reset_index(drop=True)
    required = {"seq", "len_seq", "next"}
    if not required.issubset(frame.columns):
        raise ValueError(f"{frame_path} lacks required columns {sorted(required)}")
    counts = protocol["counts"]
    expected_rows = int(counts[f"{split}_row_count"])
    if len(frame) != expected_rows:
        raise ValueError(f"{split} row count mismatch: expected {expected_rows}, got {len(frame)}")
    item_num = int(counts["item_num"])
    seq_size = int(protocol["parameters"]["target_sequence_length"])
    sequences = _stack_sequences(frame["seq"], expected_length=seq_size, item_num=item_num, split=split)
    lengths = np.asarray(frame["len_seq"].to_numpy(), dtype=np.int64)
    if np.any(lengths < 1) or np.any(lengths > seq_size):
        raise ValueError(f"{split} len_seq is outside [1,{seq_size}]")
    # paper_raw_v1 stores histories left-padded with the catalog padding id.
    # Canonicalize to right padding before the causal Transformer. This keeps
    # item IDs and split rows unchanged while avoiding all-masked causal rows,
    # which otherwise yield NaNs in TransformerEncoder attention.
    canonical = np.full_like(sequences, item_num)
    for row_index, length in enumerate(lengths.tolist()):
        canonical[row_index, : int(length)] = sequences[row_index, -int(length) :]
    sequences = canonical
    targets = np.asarray(frame["next"].to_numpy(), dtype=np.int64)
    if int(targets.min()) < 0 or int(targets.max()) >= item_num:
        raise ValueError(f"{split} target is outside real catalog [0,{item_num - 1}]")
    return sequences, lengths, targets


class SASRec(nn.Module):
    def __init__(self, *, item_num: int, seq_size: int, hidden_size: int, num_heads: int, num_layers: int, dropout: float):
        super().__init__()
        self.item_num = int(item_num)
        self.seq_size = int(seq_size)
        self.padding_item_id = self.item_num
        self.item_embeddings = nn.Embedding(self.item_num + 1, hidden_size, padding_idx=self.padding_item_id)
        self.position_embeddings = nn.Embedding(self.seq_size, hidden_size)
        layer = nn.TransformerEncoderLayer(
            d_model=hidden_size,
            nhead=num_heads,
            dim_feedforward=hidden_size * 4,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=num_layers)
        self.output = nn.Linear(hidden_size, self.item_num)

    def forward(self, sequences: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        if sequences.ndim != 2 or sequences.shape[1] != self.seq_size:
            raise ValueError(f"sequences must have shape (B,{self.seq_size})")
        if lengths.ndim != 1 or lengths.shape[0] != sequences.shape[0]:
            raise ValueError("lengths must have shape (B,)")
        batch_size, seq_size = sequences.shape
        positions = torch.arange(seq_size, device=sequences.device).unsqueeze(0).expand(batch_size, -1)
        hidden = self.item_embeddings(sequences) + self.position_embeddings(positions)
        causal_mask = torch.triu(torch.ones((seq_size, seq_size), dtype=torch.bool, device=sequences.device), diagonal=1)
        padding_mask = sequences.eq(self.padding_item_id)
        encoded = self.encoder(hidden, mask=causal_mask, src_key_padding_mask=padding_mask)
        last_indices = lengths.to(device=sequences.device).clamp(min=1, max=seq_size) - 1
        batch_indices = torch.arange(batch_size, device=sequences.device)
        return self.output(encoded[batch_indices, last_indices])


def _batches(size: int, batch_size: int, rng: np.random.Generator | None) -> Iterable[np.ndarray]:
    order = np.arange(size, dtype=np.int64)
    if rng is not None:
        rng.shuffle(order)
    for start in range(0, size, batch_size):
        yield order[start : start + batch_size]


def evaluate(model: SASRec, sequences: np.ndarray, lengths: np.ndarray, targets: np.ndarray, *, device: torch.device, batch_size: int) -> dict[str, Any]:
    model.eval()
    max_k = min(50, model.item_num)
    top_batches: list[torch.Tensor] = []
    with torch.no_grad():
        for indices in _batches(len(sequences), batch_size, None):
            batch_sequences = torch.as_tensor(sequences[indices], dtype=torch.long, device=device)
            batch_lengths = torch.as_tensor(lengths[indices], dtype=torch.long, device=device)
            logits = model(batch_sequences, batch_lengths)
            if not torch.isfinite(logits).all():
                raise FloatingPointError("non-finite SASRec evaluation logits")
            top_batches.append(torch.topk(logits, k=max_k, dim=1, largest=True, sorted=True).indices.cpu())
    ranked = torch.cat(top_batches, dim=0) if top_batches else torch.empty((0, max_k), dtype=torch.long)
    target_tensor = torch.as_tensor(targets, dtype=torch.long)
    metrics: dict[str, float] = {}
    for k in (1, 5, 10, 20, 50):
        kk = min(k, max_k)
        window = ranked[:, :kk]
        matches = window.eq(target_tensor.view(-1, 1))
        hits = matches.any(dim=1)
        first_positions = matches.float().argmax(dim=1).to(torch.float32) + 1.0
        ndcg = torch.where(hits, 1.0 / torch.log2(first_positions + 1.0), torch.zeros_like(first_positions))
        metrics[f"HR@{k}"] = float(hits.float().mean().item()) if len(targets) else 0.0
        metrics[f"NDCG@{k}"] = float(ndcg.mean().item()) if len(targets) else 0.0
    return {
        "metrics": metrics,
        "expected_rows": int(len(targets)),
        "evaluated_rows": int(len(targets)),
        "candidate_policy": "all-real-catalog-items-0-through-M-minus-1",
        "aggregation": "row-weighted",
    }


def train_one(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = Path(args.run_dir).resolve()
    dataset_dir = Path(args.dataset_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    if (run_dir / "artifact_manifest.json").exists() or (run_dir / "best_summary_sasrec.json").exists():
        raise FileExistsError(f"dated run already has a terminal artifact: {run_dir}")
    if args.evaluator_version != EVALUATOR_VERSION or args.selector_version != SELECTOR_VERSION:
        raise ValueError("E5 requires the frozen evaluator and validation selector")
    if int(args.seed) != 100:
        raise ValueError("E5 permits seed=100 only")
    if args.dataset not in DATASETS:
        raise ValueError(f"unsupported E5 dataset: {args.dataset}")

    seed_everything(int(args.seed))
    protocol = load_protocol(dataset_dir)
    if protocol["dataset"] != args.dataset:
        raise ValueError("dataset argument does not match protocol.json")
    input_hash = sha256_named_files(dataset_dir, SPLIT_FILES)
    if args.split_sha256 and args.split_sha256 != input_hash:
        raise ValueError(f"split hash mismatch: expected {args.split_sha256}, actual {input_hash}")
    config = {
        "model": "SASRec",
        "dataset": args.dataset,
        "seed": int(args.seed),
        "hidden_size": int(args.hidden_size),
        "num_heads": int(args.num_heads),
        "num_layers": int(args.num_layers),
        "dropout": float(args.dropout),
        "epochs": int(args.epochs),
        "batch_size": int(args.batch_size),
        "eval_batch_size": int(args.eval_batch_size),
        "learning_rate": float(args.learning_rate),
        "weight_decay": float(args.weight_decay),
        "early_stop_patience": int(args.early_stop_patience),
        "early_stop_min_delta": float(args.early_stop_min_delta),
        "evaluator_version": args.evaluator_version,
        "selector_version": args.selector_version,
    }
    config_hash = canonical_hash(config)
    if args.config_sha256 and args.config_sha256 != config_hash:
        raise ValueError(f"config hash mismatch: expected {args.config_sha256}, actual {config_hash}")
    item_num = int(protocol["counts"]["item_num"])
    seq_size = int(protocol["parameters"]["target_sequence_length"])
    train_sequences, train_lengths, train_targets = load_split(dataset_dir, "train", protocol)
    val_sequences, val_lengths, val_targets = load_split(dataset_dir, "val", protocol)
    test_sequences, test_lengths, test_targets = load_split(dataset_dir, "test", protocol)

    requested_device = torch.device(args.device)
    device = requested_device
    if requested_device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    model = SASRec(
        item_num=item_num,
        seq_size=seq_size,
        hidden_size=int(args.hidden_size),
        num_heads=int(args.num_heads),
        num_layers=int(args.num_layers),
        dropout=float(args.dropout),
    ).to(device)
    if args.startup_probe_only:
        probe_rows = min(2, len(train_sequences))
        with torch.no_grad():
            probe_logits = model(
                torch.as_tensor(train_sequences[:probe_rows], dtype=torch.long, device=device),
                torch.as_tensor(train_lengths[:probe_rows], dtype=torch.long, device=device),
            )
        if not torch.isfinite(probe_logits).all():
            raise FloatingPointError("non-finite SASRec startup-probe logits")
        probe = {
            "schema_version": 1,
            "dataset": args.dataset,
            "seed": int(args.seed),
            "evaluator_version": args.evaluator_version,
            "selector_version": args.selector_version,
            "split_sha256": input_hash,
            "config_sha256": config_hash,
            "device": str(device),
            "model_parameters": int(sum(parameter.numel() for parameter in model.parameters())),
            "probe_batch_rows": probe_rows,
            "optimizer_steps": 0,
            "checkpoints_written": 0,
            "metrics_written": 0,
            "status": "STARTUP_PROBE_PASS",
        }
        write_json(run_dir / "startup_probe.json", probe)
        print("STARTUP_PROBE_PASS", flush=True)
        return probe

    optimizer = torch.optim.AdamW(model.parameters(), lr=float(args.learning_rate), weight_decay=float(args.weight_decay))
    criterion = nn.CrossEntropyLoss()
    rng = np.random.default_rng(int(args.seed))
    history: list[dict[str, Any]] = []
    best_metric = float("-inf")
    best_epoch = 0
    best_state: dict[str, torch.Tensor] | None = None
    best_val: dict[str, Any] | None = None
    patience_left = int(args.early_stop_patience)
    started_at = time.time()
    for epoch in range(1, int(args.epochs) + 1):
        model.train()
        losses: list[float] = []
        for indices in _batches(len(train_sequences), int(args.batch_size), rng):
            sequence_batch = torch.as_tensor(train_sequences[indices], dtype=torch.long, device=device)
            length_batch = torch.as_tensor(train_lengths[indices], dtype=torch.long, device=device)
            target_batch = torch.as_tensor(train_targets[indices], dtype=torch.long, device=device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(sequence_batch, length_batch)
            if not torch.isfinite(logits).all():
                raise FloatingPointError(f"non-finite SASRec logits at epoch {epoch}")
            loss = criterion(logits, target_batch)
            if not torch.isfinite(loss):
                raise FloatingPointError(f"non-finite SASRec loss at epoch {epoch}")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
        val_result = evaluate(model, val_sequences, val_lengths, val_targets, device=device, batch_size=int(args.eval_batch_size))
        selector_value = float(val_result["metrics"]["NDCG@10"])
        improved = selector_value > best_metric + float(args.early_stop_min_delta)
        if improved:
            best_metric = selector_value
            best_epoch = epoch
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
            best_val = val_result
            patience_left = int(args.early_stop_patience)
        else:
            patience_left -= 1
        epoch_row = {
            "epoch": epoch,
            "mean_train_loss": float(np.mean(losses)) if losses else math.nan,
            "validation": val_result,
            "selector_metric": "NDCG@10",
            "selector_value": selector_value,
            "is_best": bool(improved),
            "patience_left": patience_left,
        }
        history.append(epoch_row)
        print(json.dumps({"epoch": epoch, "mean_train_loss": epoch_row["mean_train_loss"], "validation_ndcg10": selector_value, "is_best": improved}), flush=True)
        if patience_left <= 0:
            break

    if best_state is None or best_val is None:
        raise RuntimeError("validation selector did not produce a checkpoint")
    model.load_state_dict(best_state)
    checkpoint_path = run_dir / "sasrec_best.pt"
    torch.save({"model_state_dict": best_state, "config": config, "best_epoch": best_epoch}, checkpoint_path)
    test_result = evaluate(model, test_sequences, test_lengths, test_targets, device=device, batch_size=int(args.eval_batch_size))
    summary = {
        "schema_version": 1,
        "method": "SASRec",
        "dataset": args.dataset,
        "seed": int(args.seed),
        "best_epoch": best_epoch,
        "selector": {"version": args.selector_version, "metric": "NDCG@10", "value": best_metric},
        "validation": best_val,
        "test": test_result,
        "test_disclosure": "test metrics were logged during development; model selection used validation only; not an untouched final holdout",
        "history": history,
    }
    summary_path = run_dir / "best_summary_sasrec.json"
    write_json(summary_path, summary)
    metrics_path = run_dir / "metrics_sasrec.json"
    write_json(metrics_path, {"validation": best_val, "test": test_result, "test_disclosure": summary["test_disclosure"]})
    manifest = {
        "schema_version": 1,
        "artifact_id": f"E05.SASRec.{args.dataset}.seed100",
        "method": "SASRec",
        "dataset": args.dataset,
        "seed": int(args.seed),
        "run_dir": str(run_dir),
        "dataset_dir": str(dataset_dir),
        "evaluator_version": args.evaluator_version,
        "selector_version": args.selector_version,
        "config": config,
        "config_sha256": config_hash,
        "split_sha256": input_hash,
        "protocol_sha256": sha256_file(dataset_dir / "protocol.json"),
        "mapping_sha256": sha256_file(dataset_dir / "item_mapping.csv"),
        "row_counts": {split: int(protocol["counts"][f"{split}_row_count"]) for split in ("train", "val", "test")},
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": sha256_file(checkpoint_path),
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "metrics_path": str(metrics_path),
        "metrics_sha256": sha256_file(metrics_path),
        "selection": "validation NDCG@10 row-weighted; test evaluated only after selection",
        "candidate_policy": "all-real-catalog-items-0-through-M-minus-1",
        "padding_contract": "paper_raw_v1-left-pad-canonicalized-to-right-pad-before-causal-encoder",
        "test_disclosure": summary["test_disclosure"],
        "parameter_count": int(sum(parameter.numel() for parameter in model.parameters())),
        "elapsed_seconds": float(time.time() - started_at),
    }
    manifest["artifact_sha256"] = canonical_hash(manifest)
    write_json(run_dir / "artifact_manifest.json", manifest)
    print(json.dumps({"status": "PASS", "dataset": args.dataset, "best_epoch": best_epoch, "validation_ndcg10": best_metric, "test_ndcg10": test_result["metrics"]["NDCG@10"]}), flush=True)
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, choices=DATASETS)
    parser.add_argument("--dataset-dir", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=100)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--gpu-id", type=int, default=0)
    parser.add_argument("--evaluator-version", default=EVALUATOR_VERSION)
    parser.add_argument("--selector-version", default=SELECTOR_VERSION)
    parser.add_argument("--split-sha256")
    parser.add_argument("--config-sha256")
    parser.add_argument("--hidden-size", type=int, default=64)
    parser.add_argument("--num-heads", type=int, default=2)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--eval-batch-size", type=int, default=1024)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--early-stop-patience", type=int, default=2)
    parser.add_argument("--early-stop-min-delta", type=float, default=0.0)
    parser.add_argument("--startup-probe-only", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    train_one(parse_args())
