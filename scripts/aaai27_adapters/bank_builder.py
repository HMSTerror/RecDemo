from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
from typing import Any

import numpy as np

from .common import (
    atomic_write_json,
    load_embedding_payload,
    load_jsonl_records,
    sha256_file,
    stable_sha256,
    write_bytes_exclusive,
)


CORRUPTION_LEVELS = (0, 20, 40, 60, 80, 100)
CORRUPTION_SEED = 100


def _target_counts(records: list[dict[str, Any]], item_count: int, item_ids: list[int] | None = None) -> np.ndarray:
    id_to_row = {item_id: row for row, item_id in enumerate(item_ids)} if item_ids is not None else None
    targets = []
    for record in records:
        raw = record.get("target_item_id", record.get("next"))
        if raw is None:
            raise ValueError("train record lacks target_item_id/next")
        target = int(raw)
        if id_to_row is not None:
            if target not in id_to_row:
                raise ValueError(f"train target item ID {target} is absent from embedding item ID mapping")
            targets.append(id_to_row[target])
        elif 0 <= target < item_count:
            targets.append(target)
    if not targets:
        raise ValueError("train transitions contain no real target items")
    return np.bincount(np.asarray(targets, dtype=np.int64), minlength=item_count).astype(np.int64)


def _strata_from_popularity(counts: np.ndarray, strata_count: int) -> list[list[int]]:
    if strata_count <= 0:
        raise ValueError("strata_count must be positive")
    order = np.argsort(-counts, kind="mergesort")
    strata = [[] for _ in range(min(strata_count, len(order)))]
    for index, item_id in enumerate(order.tolist()):
        strata[index % len(strata)].append(int(item_id))
    return strata


def _allocate_exact(total: int, strata: list[list[int]]) -> list[int]:
    if total < 0 or total > sum(len(group) for group in strata):
        raise ValueError("selected count outside eligible catalog")
    raw = np.asarray([total * len(group) / sum(len(g) for g in strata) for group in strata], dtype=np.float64)
    allocation = np.floor(raw).astype(int)
    remainder = int(total - allocation.sum())
    order = np.argsort(-(raw - allocation), kind="mergesort")
    for index in order[:remainder].tolist():
        allocation[index] += 1
    return allocation.tolist()


def build_corruption_bank(
    clean_embeddings_path: Path,
    train_transitions_path: Path,
    *,
    output_dir: Path,
    dataset: str,
    corruption_level: int,
    corruption_seed: int = CORRUPTION_SEED,
    strata_count: int = 10,
    expected_item_ids: Any | None = None,
) -> dict[str, Any]:
    clean_embeddings_path = Path(clean_embeddings_path)
    train_transitions_path = Path(train_transitions_path)
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"bank output directory already exists: {output_dir}")
    if corruption_level not in CORRUPTION_LEVELS:
        raise ValueError(f"corruption_level must be one of {CORRUPTION_LEVELS}")
    if int(corruption_seed) != CORRUPTION_SEED:
        raise ValueError("new evidence banks require corruption_seed=100")
    embedding_payload = load_embedding_payload(clean_embeddings_path, expected_item_ids=expected_item_ids)
    clean = embedding_payload["matrix"]
    item_ids = embedding_payload["item_ids"]
    records = load_jsonl_records(train_transitions_path)
    counts = _target_counts(records, clean.shape[0], item_ids)
    strata = _strata_from_popularity(counts, strata_count)
    manifest_item_ids = item_ids if item_ids is not None else list(range(clean.shape[0]))
    selected_count = int(round(clean.shape[0] * corruption_level / 100.0))
    allocation = _allocate_exact(selected_count, strata)
    rng = np.random.default_rng(int(corruption_seed))
    corrupted = clean.copy()
    permutation: dict[int, int] = {}
    selected_ids: list[int] = []
    fixed_points = 0
    for group, count in zip(strata, allocation):
        if count == 0:
            continue
        chosen = sorted(rng.choice(np.asarray(group, dtype=np.int64), size=count, replace=False).tolist())
        values = np.asarray(chosen, dtype=np.int64)
        permuted = values[rng.permutation(len(values))]
        for source, destination in zip(values.tolist(), permuted.tolist()):
            source_item_id = int(manifest_item_ids[int(source)])
            destination_item_id = int(manifest_item_ids[int(destination)])
            permutation[source_item_id] = destination_item_id
            selected_ids.append(source_item_id)
            if source == destination:
                fixed_points += 1
            destination_norm = float(np.linalg.norm(clean[int(destination)]))
            source_norm = float(np.linalg.norm(clean[int(source)]))
            if destination_norm <= 1e-12:
                raise ValueError("cannot preserve row norm when a selected source maps from a zero-norm destination")
            corrupted[int(source)] = clean[int(destination)] * (source_norm / destination_norm)
    row_norms_before = np.linalg.norm(clean, axis=1)
    row_norms_after = np.linalg.norm(corrupted, axis=1)
    if not np.allclose(row_norms_before, row_norms_after, rtol=0.0, atol=5e-6):
        raise ValueError("corruption changed embedding row norms")
    output_dir.mkdir(parents=True)
    np.save(output_dir / "embeddings.npy", corrupted, allow_pickle=False)
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - production queue environment supplies torch
        raise RuntimeError("torch is required to emit a training-compatible corruption bank") from exc
    torch_buffer = io.BytesIO()
    torch.save(
        {
            "embeddings": torch.as_tensor(corrupted, dtype=torch.float32),
            "item_ids": [int(item_id) for item_id in manifest_item_ids],
        },
        torch_buffer,
    )
    write_bytes_exclusive(output_dir / "embeddings.pt", torch_buffer.getvalue())
    atomic_write_json(output_dir / "item_ids.json", [int(item_id) for item_id in manifest_item_ids])
    manifest = {
        "schema_version": 1,
        "dataset": str(dataset),
        "corruption_level": int(corruption_level),
        "corruption_seed": int(corruption_seed),
        "eligible_real_item_count": int(clean.shape[0]),
        "embedding_shape": list(clean.shape),
        "embedding_artifacts": {
            "numpy_filename": "embeddings.npy",
            "numpy_sha256": sha256_file(output_dir / "embeddings.npy"),
            "torch_filename": "embeddings.pt",
            "torch_sha256": sha256_file(output_dir / "embeddings.pt"),
        },
        "strata_count": len(strata),
        "strata": [
            {
                "item_count": len(group),
                "item_ids": [int(manifest_item_ids[row]) for row in group],
                "allocation": count,
            }
            for group, count in zip(strata, allocation)
        ],
        "permutation": {
            "selected_count": len(selected_ids),
            "selected_item_ids": selected_ids,
            "fixed_points": int(fixed_points),
            "mapping": permutation,
        },
        "source_hashes": {
            "clean_embeddings_sha256": sha256_file(clean_embeddings_path),
            "train_transitions_sha256": sha256_file(train_transitions_path),
        },
        "item_id_mapping": {
            "item_ids": [int(item_id) for item_id in manifest_item_ids],
            "sha256": stable_sha256([int(item_id) for item_id in manifest_item_ids]),
            "source_present": item_ids is not None,
            "reordering": "embedding_rows_only; item_ids remain in frozen row order",
        },
        "row_norm_max_abs_diff": float(np.max(np.abs(row_norms_before - row_norms_after))),
        "candidate_policy": "real_item_embeddings_only; no_padding_or_pseudo_item_rows",
    }
    # Hash the JSON-normalised manifest.  ``permutation.mapping`` uses integer
    # item IDs in memory but JSON object keys are strings on disk; hashing the
    # pre-serialisation object made a valid bank unverifiable after reload.
    manifest_for_hash = json.loads(json.dumps(manifest, sort_keys=True, ensure_ascii=False))
    manifest["bank_sha256"] = stable_sha256(
        {
            "manifest": manifest_for_hash,
            "numpy_sha256": sha256_file(output_dir / "embeddings.npy"),
            "torch_sha256": sha256_file(output_dir / "embeddings.pt"),
            "item_ids_sha256": sha256_file(output_dir / "item_ids.json"),
        }
    )
    atomic_write_json(output_dir / "bank_manifest.json", manifest)
    atomic_write_json(output_dir / "permutation.json", {"mapping": permutation, "selected_count": len(selected_ids), "fixed_points": fixed_points})
    write_bytes_exclusive(
        output_dir / "SHA256SUMS",
        (
            f"{sha256_file(output_dir / 'embeddings.npy')}  embeddings.npy\n"
            f"{sha256_file(output_dir / 'embeddings.pt')}  embeddings.pt\n"
            f"{sha256_file(output_dir / 'bank_manifest.json')}  bank_manifest.json\n"
            f"{sha256_file(output_dir / 'item_ids.json')}  item_ids.json\n"
        ).encode("ascii"),
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build one immutable popularity-stratified evidence bank.")
    parser.add_argument("--clean-embeddings", type=Path, required=True)
    parser.add_argument("--train-transitions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--corruption-level", type=int, choices=CORRUPTION_LEVELS, required=True)
    parser.add_argument("--corruption-seed", type=int, default=CORRUPTION_SEED)
    parser.add_argument("--strata-count", type=int, default=10)
    parser.add_argument("--expected-item-ids", type=Path)
    args = parser.parse_args()
    expected_item_ids = None
    if args.expected_item_ids is not None:
        expected_item_ids = json.loads(args.expected_item_ids.read_text(encoding="utf-8"))
    report = build_corruption_bank(
        args.clean_embeddings,
        args.train_transitions,
        output_dir=args.output_dir,
        dataset=args.dataset,
        corruption_level=args.corruption_level,
        corruption_seed=args.corruption_seed,
        strata_count=args.strata_count,
        expected_item_ids=expected_item_ids,
    )
    print(json.dumps({"bank_sha256": report["bank_sha256"], "output_dir": str(args.output_dir)}, indent=2))


if __name__ == "__main__":
    main()
