#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = REPO_ROOT / "model"
for candidate in (REPO_ROOT, MODEL_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from text_side import (
    DEFAULT_EMBEDDING_FILENAME,
    DEFAULT_NULL_CURVE_FILENAME,
    TEXT_BANK_FILENAME,
    TextSideProposalBuilder,
    ensure_text_bank,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build length-matched agreement null curves from a frozen text bank.")
    parser.add_argument("--dataset-dir", required=True, help="Dataset directory containing *_data.df and text bank artifacts")
    parser.add_argument("--embeddings-path", default=None, help="Optional override for sentence_t5_xl_item_emb.pt")
    parser.add_argument("--text-bank", default=None, help="Optional override for text_bank.csv")
    parser.add_argument(
        "--text-utility-report-path",
        default=None,
        help="Optional override for the dataset-level frozen U_ds artifact used by text-side gating.",
    )
    parser.add_argument("--output", default=None, help="Output JSON path")
    parser.add_argument("--samples-per-length", type=int, default=256)
    parser.add_argument("--seed", type=int, default=20260702)
    parser.add_argument("--center-embeddings", action="store_true")
    parser.add_argument("--agreement-k", type=float, default=2.0)
    return parser.parse_args()


def _stable_json_dump(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256_paths(*paths: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _load_split_lengths(dataset_dir: Path) -> list[int]:
    lengths: set[int] = set()
    for split_name in ("train_data.df", "val_data.df", "test_data.df"):
        split_path = dataset_dir / split_name
        if not split_path.exists():
            continue
        split_df = pd.read_pickle(split_path)
        if "len_seq" in split_df.columns:
            split_lengths = split_df["len_seq"].astype(int).tolist()
        else:
            split_lengths = [int(sum(item != max(seq) for item in seq)) for seq in split_df["seq"].tolist()]
        lengths.update(length for length in split_lengths if length > 0)
    if not lengths:
        raise FileNotFoundError(f"no split lengths found under {dataset_dir}")
    return sorted(lengths)


def _sample_histories(
    *,
    sample_count: int,
    history_length: int,
    sequence_width: int,
    item_num: int,
    generator: torch.Generator,
) -> torch.Tensor:
    histories = torch.full((sample_count, sequence_width), item_num, dtype=torch.long)
    sampled = torch.randint(0, item_num, (sample_count, history_length), generator=generator, dtype=torch.long)
    histories[:, -history_length:] = sampled
    return histories


def build_null_curve_artifact(
    *,
    dataset_dir: Path,
    embeddings_path: Path | None = None,
    text_bank_path: Path | None = None,
    text_utility_report_path: Path | None = None,
    output_path: Path | None = None,
    samples_per_length: int = 256,
    seed: int = 20260702,
    center_embeddings: bool = False,
    agreement_k: float = 2.0,
) -> dict:
    dataset_dir = Path(dataset_dir).resolve()
    text_bank_path = Path(text_bank_path).resolve() if text_bank_path else dataset_dir / TEXT_BANK_FILENAME
    if not text_bank_path.exists():
        text_bank_path = ensure_text_bank(dataset_dir)

    embeddings_path = Path(embeddings_path).resolve() if embeddings_path else dataset_dir / DEFAULT_EMBEDDING_FILENAME
    output_path = Path(output_path).resolve() if output_path else dataset_dir / DEFAULT_NULL_CURVE_FILENAME

    item_df = pd.read_csv(text_bank_path).sort_values("item_id").reset_index(drop=True)
    history_lengths = _load_split_lengths(dataset_dir)
    max_history_length = max(history_lengths)
    builder = TextSideProposalBuilder.from_files(
        dataset_dir=dataset_dir,
        item_num=len(item_df),
        is_disliked_item=False,
        embeddings_path=embeddings_path,
        text_bank_path=text_bank_path,
        center_embeddings=center_embeddings,
        text_utility_report_path=Path(text_utility_report_path).resolve() if text_utility_report_path else None,
    )
    builder.eval()

    generator = torch.Generator().manual_seed(seed)
    length_bins: dict[str, dict[str, float | int]] = {}
    for history_length in history_lengths:
        histories = _sample_histories(
            sample_count=samples_per_length,
            history_length=history_length,
            sequence_width=max_history_length,
            item_num=builder.item_num,
            generator=generator,
        )
        with torch.no_grad():
            context = builder.encode_history_context(histories)
        agreements = context["agreement"].float().cpu()
        length_bins[str(history_length)] = {
            "mu": round(float(agreements.mean().item()), 10),
            "sigma": round(float(agreements.std(unbiased=False).clamp_min(1e-6).item()), 10),
            "samples": int(samples_per_length),
        }

    artifact = {
        "protocol": {
            "agreement_k": float(agreement_k),
            "bank_hash": _sha256_paths(text_bank_path, embeddings_path),
            "center_embeddings": bool(center_embeddings),
            "dataset_dir": dataset_dir.name,
            "embeddings_filename": embeddings_path.name,
            "seed": int(seed),
            "sequence_width": int(max_history_length),
            "samples_per_length": int(samples_per_length),
            "text_bank_filename": text_bank_path.name,
        },
        "length_bins": length_bins,
    }
    _stable_json_dump(artifact, output_path)
    return artifact


def main() -> None:
    args = parse_args()
    artifact = build_null_curve_artifact(
        dataset_dir=Path(args.dataset_dir),
        embeddings_path=Path(args.embeddings_path) if args.embeddings_path else None,
        text_bank_path=Path(args.text_bank) if args.text_bank else None,
        text_utility_report_path=Path(args.text_utility_report_path) if args.text_utility_report_path else None,
        output_path=Path(args.output) if args.output else None,
        samples_per_length=args.samples_per_length,
        seed=args.seed,
        center_embeddings=args.center_embeddings,
        agreement_k=args.agreement_k,
    )
    print(f"wrote {Path(args.output).resolve() if args.output else Path(args.dataset_dir).resolve() / DEFAULT_NULL_CURVE_FILENAME}")
    print(json.dumps({"length_bins": sorted(artifact["length_bins"]), "bank_hash": artifact["protocol"]["bank_hash"]}, sort_keys=True))


if __name__ == "__main__":
    main()
