from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch

from model.text_side import TextSideProposalBuilder, load_agreement_null_stats

from .common import (
    load_embedding_payload,
    load_jsonl_records,
    sha256_file,
    stable_sha256,
    write_bytes_exclusive,
    atomic_write_json,
)
from .proposal_contract import validate_proposal_manifest


GENERATION_SEED = 100


def _load_core_p1(path: Path, expected_size: int) -> np.ndarray:
    path = Path(path)
    suffix = path.suffix.casefold()
    if suffix == ".npy":
        payload: Any = np.load(path, allow_pickle=False)
    elif suffix == ".npz":
        archive = np.load(path, allow_pickle=False)
        if "p1" not in archive:
            raise ValueError("core p1 npz must contain a p1 array")
        payload = archive["p1"]
    elif suffix in {".pt", ".pth"}:
        payload = torch.load(path, map_location="cpu", weights_only=False)
        if isinstance(payload, dict):
            candidates = [payload.get("p1"), payload.get("core_p1"), payload.get("model.text_side_builder.p1")]
            state_dict = payload.get("state_dict")
            if isinstance(state_dict, dict):
                candidates.extend(value for key, value in state_dict.items() if str(key).endswith("text_side_builder.p1") or str(key).endswith(".p1"))
            payload = next((candidate for candidate in candidates if candidate is not None), None)
        if payload is None:
            raise ValueError("core p1 checkpoint does not expose a p1 vector")
        if hasattr(payload, "detach"):
            payload = payload.detach().cpu().numpy()
    else:
        raise ValueError(f"unsupported core p1 artifact suffix: {path.suffix}")
    values = np.asarray(payload, dtype=np.float32).reshape(-1)
    if values.shape != (expected_size,) or not np.isfinite(values).all():
        raise ValueError(f"core p1 must be a finite vector of length {expected_size}")
    return values


def _load_item_bank(text_bank_path: Path) -> tuple[list[int], np.ndarray]:
    frame = pd.read_csv(text_bank_path)
    if "item_id" not in frame.columns or "field_coverage" not in frame.columns:
        raise ValueError("text bank must contain item_id and field_coverage columns")
    frame = frame.sort_values("item_id").reset_index(drop=True)
    item_ids = [int(value) for value in frame["item_id"].tolist()]
    if len(set(item_ids)) != len(item_ids):
        raise ValueError("text bank item IDs must be unique")
    completeness = frame["field_coverage"].to_numpy(dtype=np.float32)
    if not np.isfinite(completeness).all() or np.any(completeness < 0) or np.any(completeness > 1):
        raise ValueError("text bank field_coverage must be finite in [0, 1]")
    return item_ids, completeness


def _load_bank_sha256(path: Path, dataset: str) -> str:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or str(payload.get("dataset")) != str(dataset):
        raise ValueError("bank manifest dataset mismatch")
    digest = str(payload.get("bank_sha256", "")).casefold()
    if len(digest) != 64:
        raise ValueError("bank manifest must contain bank_sha256")
    return digest


def build_train_proposal_records(
    *,
    dataset: str,
    train_transitions_path: Path,
    embeddings_path: Path,
    text_bank_path: Path,
    null_curve_path: Path,
    core_p1_path: Path,
    bank_manifest_path: Path,
    output_dir: Path,
    item_popularity_path: Path | None = None,
    kernel_version: str = "v2",
    temperature: float = 0.2,
    g_max: float = 0.5,
    generation_seed: int = GENERATION_SEED,
    batch_size: int = 256,
) -> dict[str, Any]:
    if int(generation_seed) != GENERATION_SEED:
        raise ValueError("proposal generation requires generation_seed=100")
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"proposal output directory already exists: {output_dir}")
    train_transitions_path = Path(train_transitions_path)
    embeddings_path = Path(embeddings_path)
    text_bank_path = Path(text_bank_path)
    null_curve_path = Path(null_curve_path)
    core_p1_path = Path(core_p1_path)
    bank_manifest_path = Path(bank_manifest_path)
    if any(token in train_transitions_path.name.casefold() for token in ("val", "test")):
        raise ValueError("proposal records accept train-only transition input")
    records = load_jsonl_records(train_transitions_path)
    if any(str(record.get("split", "train")).casefold() != "train" for record in records):
        raise ValueError("proposal records contain a non-train transition")
    item_ids, completeness = _load_item_bank(text_bank_path)
    embedding_payload = load_embedding_payload(embeddings_path, expected_item_ids=item_ids)
    embeddings = embedding_payload["matrix"]
    if embeddings.shape[0] != len(item_ids):
        raise ValueError("text bank and embedding item counts differ")
    item_id_to_row = {item_id: row for row, item_id in enumerate(item_ids)}
    popularity_path = Path(item_popularity_path) if item_popularity_path is not None else text_bank_path.parent / "items_pop.npy"
    if not popularity_path.exists():
        raise FileNotFoundError(f"missing frozen item popularity artifact: {popularity_path}")
    popularity = np.asarray(np.load(popularity_path, allow_pickle=False), dtype=np.float32).reshape(-1)
    if popularity.shape != (len(item_ids),) or not np.isfinite(popularity).all() or np.any(popularity < 0):
        raise ValueError("item popularity must be a finite nonnegative vector aligned to the frozen item mapping")
    null_stats = load_agreement_null_stats(null_curve_path)
    p1 = _load_core_p1(core_p1_path, len(item_ids) + 1)
    torch.manual_seed(GENERATION_SEED)
    builder = TextSideProposalBuilder(
        item_embeddings=torch.as_tensor(embeddings, dtype=torch.float32),
        item_completeness=torch.as_tensor(completeness, dtype=torch.float32),
        item_num=len(item_ids),
        is_disliked_item=True,
        item_popularity=torch.as_tensor(popularity, dtype=torch.float32),
        temperature=float(temperature),
        kernel_version=str(kernel_version),
        g_max=float(g_max),
        agreement_null_stats=null_stats,
    )
    with torch.no_grad():
        if builder.p1 is None:
            raise ValueError("proposal record generation requires kernel_version=v2 with core p1")
        builder.p1.copy_(torch.as_tensor(p1, dtype=builder.p1.dtype))
    builder.eval()

    converted: list[tuple[dict[str, Any], list[int], int]] = []
    max_history = 1
    for index, record in enumerate(records):
        raw_history = record.get("history_item_ids", record.get("history", record.get("seq")))
        if not isinstance(raw_history, (list, tuple)):
            raise ValueError(f"train record {index} lacks a list-like history")
        history_rows: list[int] = []
        for raw_item in raw_history:
            item_id = int(raw_item)
            if item_id not in item_id_to_row:
                raise ValueError(f"history item ID {item_id} is absent from frozen item mapping")
            history_rows.append(item_id_to_row[item_id])
        target_item_id = int(record.get("target_item_id", record.get("next", -1)))
        if target_item_id not in item_id_to_row:
            raise ValueError(f"target item ID {target_item_id} is absent from frozen item mapping")
        converted.append((record, history_rows, target_item_id))
        max_history = max(max_history, len(history_rows))

    output_rows: list[dict[str, Any]] = []
    for start in range(0, len(converted), max(1, int(batch_size))):
        batch = converted[start : start + max(1, int(batch_size))]
        history_tensor = torch.full((len(batch), max_history), len(item_ids), dtype=torch.long)
        for row_index, (_, history_rows, _) in enumerate(batch):
            if history_rows:
                history_tensor[row_index, -len(history_rows) :] = torch.as_tensor(history_rows, dtype=torch.long)
        with torch.no_grad():
            context = builder.encode_history_context(history_tensor)
        for row_index, (record, _, target_item_id) in enumerate(batch):
            output_rows.append(
                {
                    "row_id": str(record.get("row_id", start + row_index)),
                    "user_id": int(record["user_id"]) if record.get("user_id") not in (None, "") else None,
                    "history_item_ids": [int(value) for value in record.get("history_item_ids", record.get("history", record.get("seq")))],
                    "target_item_id": target_item_id,
                    "q_text": context["content_anchor"][row_index].cpu().tolist(),
                    "q_core": context["p_core"][row_index].cpu().tolist(),
                    "gate": float(context["g"][row_index].item()),
                    "u_tilde": float(context["u_tilde"][row_index].item()),
                    "agreement": float(context["agreement"][row_index].item()),
                    "history_length": int((history_tensor[row_index] != len(item_ids)).sum().item()),
                    "target_popularity": float(popularity[item_id_to_row[target_item_id]]),
                }
            )

    bank_sha256 = _load_bank_sha256(bank_manifest_path, dataset)
    proposal_manifest = validate_proposal_manifest(
        {
            "dataset": dataset,
            "split_name": "train",
            "split_sha256": sha256_file(train_transitions_path),
            "bank_sha256": bank_sha256,
            "text_bank_sha256": sha256_file(text_bank_path),
            "null_curve_sha256": sha256_file(null_curve_path),
            "item_completeness_sha256": stable_sha256(completeness.tolist()),
            "popularity_sha256": sha256_file(popularity_path),
            "core_p1_sha256": sha256_file(core_p1_path),
            "embedding_sha256": sha256_file(embeddings_path),
            "item_id_mapping_sha256": embedding_payload["item_id_mapping_sha256"],
            "kernel_version": str(kernel_version),
            "temperature": float(temperature),
            "g_max": float(g_max),
            "generation_seed": int(generation_seed),
            "record_count": len(output_rows),
            "candidate_policy": "production_TextSideProposalBuilder_encode_history_context_train_only",
        },
        expected_dataset=dataset,
        expected_bank_sha256=bank_sha256,
    )
    row_bytes = "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in output_rows).encode("utf-8")
    output_dir.mkdir(parents=True)
    write_bytes_exclusive(output_dir / "train_proposals.jsonl", row_bytes)
    atomic_write_json(output_dir / "proposal_manifest.json", proposal_manifest)
    write_bytes_exclusive(
        output_dir / "SHA256SUMS",
        (
            f"{sha256_file(output_dir / 'train_proposals.jsonl')}  train_proposals.jsonl\n"
            f"{sha256_file(output_dir / 'proposal_manifest.json')}  proposal_manifest.json\n"
        ).encode("ascii"),
    )
    return {
        "proposal_manifest": proposal_manifest,
        "output_dir": str(output_dir.resolve()),
        "records": len(output_rows),
        "train_proposals_sha256": sha256_file(output_dir / "train_proposals.jsonl"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate train-only q_text/q_core records with the production TextSideProposalBuilder.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--train-transitions", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path, required=True)
    parser.add_argument("--text-bank", type=Path, required=True)
    parser.add_argument("--null-curve", type=Path, required=True)
    parser.add_argument("--core-p1", type=Path, required=True)
    parser.add_argument("--bank-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--item-popularity", type=Path)
    parser.add_argument("--kernel-version", default="v2")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--g-max", type=float, default=0.5)
    parser.add_argument("--generation-seed", type=int, default=GENERATION_SEED)
    parser.add_argument("--batch-size", type=int, default=256)
    args = parser.parse_args()
    result = build_train_proposal_records(
        dataset=args.dataset,
        train_transitions_path=args.train_transitions,
        embeddings_path=args.embeddings,
        text_bank_path=args.text_bank,
        null_curve_path=args.null_curve,
        core_p1_path=args.core_p1,
        bank_manifest_path=args.bank_manifest,
        output_dir=args.output_dir,
        item_popularity_path=args.item_popularity,
        kernel_version=args.kernel_version,
        temperature=args.temperature,
        g_max=args.g_max,
        generation_seed=args.generation_seed,
        batch_size=args.batch_size,
    )
    print(json.dumps({"records": result["records"], "manifest_sha256": result["proposal_manifest"]["manifest_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
