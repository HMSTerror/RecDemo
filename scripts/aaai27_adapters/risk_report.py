from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from .common import (
    atomic_write_json,
    load_embedding_payload,
    load_jsonl_records,
    normalise_distribution,
    sha256_file,
    stable_sha256,
    write_bytes_exclusive,
)


EPSILON = 1e-12
SAMPLE_SIZE = 4000
SAMPLING_SEED = 7
PNE_K = 10


def _nearest_real_items(embeddings: np.ndarray, target: int, k: int = PNE_K) -> list[int]:
    if embeddings.shape[0] < k:
        raise ValueError(f"PNE@{k} requires at least {k} real catalog items")
    target_vector = embeddings[target]
    target_norm = float(np.linalg.norm(target_vector))
    if target_norm <= 0:
        similarities = np.zeros(embeddings.shape[0], dtype=np.float64)
    else:
        norms = np.linalg.norm(embeddings, axis=1)
        similarities = (embeddings @ target_vector) / np.clip(norms * target_norm, EPSILON, None)
    order = np.argsort(-similarities, kind="mergesort")
    neighborhood = [int(index) for index in order if int(index) == target or int(index) != target][:k]
    if target not in neighborhood:
        neighborhood[-1] = target
    return neighborhood


def _entropy(probabilities: np.ndarray) -> float:
    positive = probabilities[probabilities > 0]
    return float(-(positive * np.log(positive)).sum())


def _normalise_real_distribution(values: Any, label: str, item_count: int) -> tuple[np.ndarray, bool]:
    array = np.asarray(values, dtype=np.float64)
    if array.shape == (item_count + 1,):
        # The optional final coordinate is the model's non-preference/pseudo
        # mass.  It is retained only as provenance and excluded from every
        # real-catalog risk statistic.
        array = array[:-1]
        return normalise_distribution(array, label, item_count), True
    return normalise_distribution(array, label, item_count), False


def _user_cluster_interval(values: np.ndarray, user_ids: list[int | None], *, replicates: int, seed: int) -> dict[str, Any]:
    if any(user_id is None for user_id in user_ids):
        return {
            "status": "not_estimable",
            "reason": "user IDs absent for one or more sampled train transitions",
            "bootstrap_replicates": 0,
        }
    clusters: dict[int, list[float]] = {}
    for value, user_id in zip(values.tolist(), user_ids):
        clusters.setdefault(int(user_id), []).append(float(value))
    if len(clusters) < 2:
        return {
            "status": "not_estimable",
            "reason": "fewer than two user clusters in sampled train transitions",
            "bootstrap_replicates": 0,
        }
    cluster_means = np.asarray([np.mean(cluster) for cluster in clusters.values()], dtype=np.float64)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(cluster_means), size=(int(replicates), len(cluster_means)))
    estimates = cluster_means[draws].mean(axis=1)
    return {
        "status": "estimable",
        "bootstrap_replicates": int(replicates),
        "seed": int(seed),
        "cluster_count": int(len(cluster_means)),
        "mean": float(estimates.mean()),
        "ci95": [float(np.quantile(estimates, 0.025)), float(np.quantile(estimates, 0.975))],
    }


def build_train_only_risk_report(
    transitions_path: Path,
    embeddings_path: Path,
    *,
    output_dir: Path,
    sample_size: int = SAMPLE_SIZE,
    sampling_seed: int = SAMPLING_SEED,
    bootstrap_replicates: int = 1000,
    bootstrap_seed: int = 100,
    split_name: str = "train",
    padding_item_id: int | None = None,
    pseudo_item_id: int | None = None,
    expected_item_ids: Any | None = None,
    proposal_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    transitions_path = Path(transitions_path)
    embeddings_path = Path(embeddings_path)
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"risk output directory already exists: {output_dir}")
    if split_name.casefold() != "train" or any(token in transitions_path.name.casefold() for token in ("val", "test")):
        raise ValueError("RISK-03 is train-only; validation/test transition input is forbidden")
    records = load_jsonl_records(transitions_path)
    if sample_size <= 0 or sample_size > len(records):
        raise ValueError(f"sample_size must be between 1 and {len(records)}")
    embedding_payload = load_embedding_payload(embeddings_path, expected_item_ids=expected_item_ids)
    embeddings = embedding_payload["matrix"]
    item_ids = embedding_payload["item_ids"]
    item_id_to_row = {int(item_id): row for row, item_id in enumerate(item_ids)} if item_ids is not None else None
    rng = np.random.default_rng(int(sampling_seed))
    sampled_indices = rng.choice(len(records), size=int(sample_size), replace=False)
    row_reports: list[dict[str, Any]] = []
    epe_values: list[float] = []
    pne_values: list[float] = []
    excess_pne_values: list[float] = []
    entropy_values: list[float] = []
    concentration_values: list[float] = []
    user_ids: list[int | None] = []
    sampled_ids: list[str] = []
    for raw_index in sampled_indices.tolist():
        record = records[int(raw_index)]
        target_item_id = int(record.get("target_item_id", record.get("next", -1)))
        if target_item_id in {padding_item_id, pseudo_item_id}:
            raise ValueError(f"target item {target_item_id} is outside the real catalog")
        if item_id_to_row is None:
            target = target_item_id
            if target < 0 or target >= embeddings.shape[0]:
                raise ValueError(f"target item {target_item_id} is outside the real catalog")
        else:
            if target_item_id not in item_id_to_row:
                raise ValueError(f"target item ID {target_item_id} is absent from embedding item ID mapping")
            target = item_id_to_row[target_item_id]
        q_text, text_has_pseudo = _normalise_real_distribution(record.get("q_text"), "q_text", embeddings.shape[0])
        q_core, core_has_pseudo = _normalise_real_distribution(record.get("q_core"), "q_core", embeddings.shape[0])
        neighborhood = _nearest_real_items(embeddings, target, PNE_K)
        epe = float(math.log(float(q_text[target]) + EPSILON) - math.log(float(q_core[target]) + EPSILON))
        pne = float(q_text[neighborhood].sum())
        core_pne = float(q_core[neighborhood].sum())
        excess_pne = pne - core_pne
        entropy = _entropy(q_text)
        concentration = float(q_text[neighborhood].sum())
        row_id = str(record.get("row_id", raw_index))
        sampled_ids.append(row_id)
        user_id = record.get("user_id")
        user_ids.append(int(user_id) if user_id is not None and str(user_id) != "" else None)
        epe_values.append(epe)
        pne_values.append(pne)
        excess_pne_values.append(excess_pne)
        entropy_values.append(entropy)
        concentration_values.append(concentration)
        row_reports.append(
            {
                "source_index": int(raw_index),
                "row_id": row_id,
                "user_id": user_ids[-1],
                "target_item_id": target_item_id,
                "pne_neighbor_item_ids": [int(item_ids[row]) for row in neighborhood] if item_ids is not None else neighborhood,
                "epe": epe,
                "pne10": pne,
                "core_pne10": core_pne,
                "excess_pne10": excess_pne,
                "text_entropy": entropy,
                "top10_mass_concentration": concentration,
                "pseudo_item_coordinate_excluded": bool(text_has_pseudo or core_has_pseudo),
            }
        )

    values_by_name = {
        "epe": np.asarray(epe_values, dtype=np.float64),
        "pne10": np.asarray(pne_values, dtype=np.float64),
        "excess_pne10": np.asarray(excess_pne_values, dtype=np.float64),
        "text_entropy": np.asarray(entropy_values, dtype=np.float64),
        "top10_mass_concentration": np.asarray(concentration_values, dtype=np.float64),
    }
    uncertainty = {
        name: _user_cluster_interval(values, user_ids, replicates=bootstrap_replicates, seed=bootstrap_seed + index)
        for index, (name, values) in enumerate(values_by_name.items())
    }
    row_jsonl = "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in row_reports).encode("utf-8")
    report_without_hash: dict[str, Any] = {
        "schema_version": 1,
        "report_name": "AAAI-RISK-03 train-only positive exposure",
        "protocol": {
            "split_name": "train",
            "sample_size": int(sample_size),
            "sampling_seed": int(sampling_seed),
            "pne_neighborhood_size": PNE_K,
            "epsilon": EPSILON,
            "candidate_policy": "real_catalog_items_only_excluding_padding_and_pseudo_items",
            "real_catalog_item_count": int(embeddings.shape[0]),
            "item_id_mapping_sha256": embedding_payload["item_id_mapping_sha256"],
            "proposal_manifest_sha256": proposal_manifest.get("manifest_sha256") if proposal_manifest else None,
            "pseudo_item_coordinate_excluded": any(
                bool(row["pseudo_item_coordinate_excluded"]) for row in row_reports
            ),
            "formulas": {
                "epe": "mean(log(q_text(y|h)+1e-12)-log(q_core(y)+1e-12))",
                "pne10": "sum_{j in N10(y)} q_text(j|h)",
                "excess_pne10": "pne10_text - pne10_core",
            },
        },
        "point_estimates": {name: float(values.mean()) for name, values in values_by_name.items()},
        "uncertainty": {"bootstrap_replicates": int(bootstrap_replicates), "user_clustered": uncertainty},
        "provenance": {
            "transition_path": str(transitions_path.resolve()),
            "transition_sha256": sha256_file(transitions_path),
            "embedding_path": str(embeddings_path.resolve()),
            "embedding_sha256": sha256_file(embeddings_path),
            "item_id_mapping_sha256": embedding_payload["item_id_mapping_sha256"],
            "proposal_manifest_sha256": proposal_manifest.get("manifest_sha256") if proposal_manifest else None,
            "proposal_provenance": proposal_manifest if proposal_manifest else {"status": "not_bound"},
            "sampled_row_ids": sampled_ids,
            "sampled_row_ids_sha256": stable_sha256(sampled_ids),
            "split_hash_scope": "train_transition_input_only",
        },
        "rows": row_reports,
    }
    report_without_hash["artifact_sha256"] = stable_sha256(report_without_hash)
    output_dir.mkdir(parents=True)
    write_bytes_exclusive(output_dir / "risk_rows.jsonl", row_jsonl)
    atomic_write_json(output_dir / "risk_report.json", report_without_hash)
    atomic_write_json(
        output_dir / "provenance_manifest.json",
        {
            "report_sha256": sha256_file(output_dir / "risk_report.json"),
            "rows_sha256": sha256_file(output_dir / "risk_rows.jsonl"),
            "transition_sha256": report_without_hash["provenance"]["transition_sha256"],
            "embedding_sha256": report_without_hash["provenance"]["embedding_sha256"],
            "item_id_mapping_sha256": report_without_hash["provenance"]["item_id_mapping_sha256"],
            "proposal_manifest_sha256": report_without_hash["provenance"]["proposal_manifest_sha256"],
        },
    )
    return report_without_hash


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the train-only RISK-03 exposure report.")
    parser.add_argument("--transitions", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=SAMPLE_SIZE)
    parser.add_argument("--sampling-seed", type=int, default=SAMPLING_SEED)
    parser.add_argument("--bootstrap-replicates", type=int, default=1000)
    parser.add_argument("--split-name", default="train")
    parser.add_argument("--expected-item-ids", type=Path)
    parser.add_argument("--proposal-manifest", type=Path)
    args = parser.parse_args()
    expected_item_ids = None
    if args.expected_item_ids is not None:
        expected_item_ids = json.loads(args.expected_item_ids.read_text(encoding="utf-8"))
    proposal_manifest = None
    if args.proposal_manifest is not None:
        proposal_manifest = json.loads(args.proposal_manifest.read_text(encoding="utf-8"))
    report = build_train_only_risk_report(
        args.transitions,
        args.embeddings,
        output_dir=args.output_dir,
        sample_size=args.sample_size,
        sampling_seed=args.sampling_seed,
        bootstrap_replicates=args.bootstrap_replicates,
        split_name=args.split_name,
        expected_item_ids=expected_item_ids,
        proposal_manifest=proposal_manifest,
    )
    print(json.dumps({"artifact_sha256": report["artifact_sha256"], "output_dir": str(args.output_dir)}, indent=2))


if __name__ == "__main__":
    main()
