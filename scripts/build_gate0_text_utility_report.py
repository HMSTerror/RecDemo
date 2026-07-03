#!/usr/bin/env python3

from __future__ import annotations

import argparse
from datetime import datetime
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

from text_side import DEFAULT_EMBEDDING_FILENAME, TEXT_BANK_FILENAME, ensure_text_bank


DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "reports" / "data" / "2026-07-02-gate0"
DEFAULT_DATASET_ROOT = REPO_ROOT / "dataset" / "paper_raw_v1"
DEFAULT_DATASETS = ("ML1M", "Steam", "Beauty", "ATG")
DEFAULT_SAMPLE_SIZE = 4000
DEFAULT_NEGATIVE_COUNT = 100
DEFAULT_SEED = 7


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the production-bank Gate0 text-utility diagnostic required by spec section 7.3."
    )
    parser.add_argument(
        "--dataset",
        action="append",
        default=[],
        help="Dataset mapping in the form NAME=/abs/or/relative/path. Repeat once per dataset.",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for Gate0 utility outputs.")
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--negative-count", type=int, default=DEFAULT_NEGATIVE_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
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


def _parse_dataset_args(dataset_args: list[str]) -> dict[str, Path]:
    if not dataset_args:
        return {name: DEFAULT_DATASET_ROOT / name for name in DEFAULT_DATASETS}
    mapping: dict[str, Path] = {}
    for entry in dataset_args:
        if "=" not in entry:
            raise ValueError(f"dataset entry must be NAME=PATH, got {entry!r}")
        name, raw_path = entry.split("=", 1)
        mapping[name] = Path(raw_path).resolve()
    return mapping


def _normalize_rows(values: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    return values / np.clip(norms, 1e-12, None)


def _load_embedding_matrix(embeddings_path: Path, item_ids: np.ndarray) -> np.ndarray:
    payload = torch.load(embeddings_path, map_location="cpu")
    if isinstance(payload, dict):
        embeddings = np.asarray(payload["embeddings"], dtype=np.float32)
        raw_item_ids = payload.get("item_ids")
        if raw_item_ids is None:
            raw_item_ids = list(range(len(embeddings)))
    else:
        embeddings = np.asarray(payload, dtype=np.float32)
        raw_item_ids = list(range(len(embeddings)))

    raw_item_ids = np.asarray(raw_item_ids, dtype=np.int64)
    if len(raw_item_ids) != len(embeddings):
        raise ValueError("embedding payload item_ids length does not match embedding row count")

    matrix = np.zeros((len(item_ids), embeddings.shape[1]), dtype=np.float32)
    seen = np.zeros(len(item_ids), dtype=bool)
    item_id_to_row = {int(item_id): row_index for row_index, item_id in enumerate(item_ids.tolist())}
    for row_index, item_id in enumerate(raw_item_ids.tolist()):
        if int(item_id) not in item_id_to_row:
            raise ValueError(f"embedding payload item_id {item_id} missing from text bank item_id column")
        target_index = item_id_to_row[int(item_id)]
        matrix[target_index] = embeddings[row_index]
        seen[target_index] = True

    if not seen.all():
        missing = item_ids[~seen].tolist()
        raise ValueError(f"embedding payload missing rows for item_ids: {missing[:10]}")

    return _normalize_rows(matrix)


def build_next_item_distribution(train_df: pd.DataFrame, item_count: int) -> np.ndarray:
    valid_targets = train_df["next"].astype(int)
    valid_targets = valid_targets[(valid_targets >= 0) & (valid_targets < item_count)]
    if valid_targets.empty:
        raise ValueError("train split contains no valid next-item ids for popularity sampling")
    counts = np.bincount(valid_targets.to_numpy(), minlength=item_count).astype(np.float64)
    return counts / counts.sum()


def _history_ids(sequence: list[int], item_count: int) -> list[int]:
    return [int(item_id) for item_id in sequence if 0 <= int(item_id) < item_count]


def _history_vector(embeddings: np.ndarray, history_ids: list[int]) -> np.ndarray | None:
    if not history_ids:
        return None
    history_mean = embeddings[np.asarray(history_ids, dtype=np.int64)].mean(axis=0)
    norm = float(np.linalg.norm(history_mean))
    if norm < 1e-12:
        return None
    return history_mean / norm


def _utility_score(next_score: float, negative_scores: np.ndarray) -> float:
    return float((next_score > negative_scores).mean() + 0.5 * (next_score == negative_scores).mean())


def _phi_from_utility(utility_value: float) -> float:
    return float(np.clip((0.70 - utility_value) / 0.10, 0.0, 1.0))


def _coherence_quartile_rows(
    *,
    dataset_name: str,
    coherence_scores: np.ndarray,
    utility_popularity: np.ndarray,
    utility_uniform: np.ndarray,
) -> list[dict[str, object]]:
    if len(coherence_scores) == 0:
        return []

    frame = pd.DataFrame(
        {
            "coherence": coherence_scores,
            "utility_popularity": utility_popularity,
            "utility_uniform": utility_uniform,
        }
    )
    bucket_count = min(4, len(frame))
    labels = [f"Q{index + 1}" for index in range(bucket_count)]
    ranked = frame["coherence"].rank(method="first")
    frame["coherence_bucket"] = pd.qcut(ranked, q=bucket_count, labels=labels, duplicates="drop")

    rows: list[dict[str, object]] = []
    grouped = frame.groupby("coherence_bucket", observed=True)
    for bucket_name, bucket_df in grouped:
        rows.append(
            {
                "dataset": dataset_name,
                "coherence_bucket": str(bucket_name),
                "row_count": int(len(bucket_df)),
                "coherence_mean": float(bucket_df["coherence"].mean()),
                "coherence_min": float(bucket_df["coherence"].min()),
                "coherence_max": float(bucket_df["coherence"].max()),
                "u_ds_popularity": float(bucket_df["utility_popularity"].mean()),
                "u_ds_uniform": float(bucket_df["utility_uniform"].mean()),
            }
        )
    return rows


def _dataset_row(
    *,
    dataset_name: str,
    dataset_dir: Path,
    sample_size: int,
    negative_count: int,
    seed: int,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    dataset_dir = Path(dataset_dir).resolve()
    text_bank_path = dataset_dir / TEXT_BANK_FILENAME
    if not text_bank_path.exists():
        text_bank_path = ensure_text_bank(dataset_dir)
    embeddings_path = dataset_dir / DEFAULT_EMBEDDING_FILENAME
    if not embeddings_path.exists():
        raise FileNotFoundError(f"missing embeddings artifact: {embeddings_path}")
    train_split_path = dataset_dir / "train_data.df"
    if not train_split_path.exists():
        raise FileNotFoundError(f"missing train split: {train_split_path}")

    item_df = pd.read_csv(text_bank_path).sort_values("item_id").reset_index(drop=True)
    item_ids = item_df["item_id"].astype(int).to_numpy()
    embeddings = _load_embedding_matrix(embeddings_path, item_ids)
    item_count = len(item_df)

    train_df = pd.read_pickle(train_split_path)
    sampled_df = train_df.sample(n=min(sample_size, len(train_df)), random_state=seed).reset_index(drop=True)
    popularity_probs = build_next_item_distribution(train_df, item_count=item_count)
    rng = np.random.default_rng(seed)
    sampled_popularity_negs = rng.choice(
        item_count,
        size=(len(sampled_df), negative_count),
        replace=True,
        p=popularity_probs,
    )
    sampled_uniform_negs = rng.integers(0, item_count, size=(len(sampled_df), negative_count))

    popularity_scores: list[float] = []
    uniform_scores: list[float] = []
    coherence_scores: list[float] = []
    history_lengths: list[int] = []
    skipped_rows = 0

    for row_index, row in sampled_df.iterrows():
        next_item = int(row["next"])
        if next_item < 0 or next_item >= item_count:
            skipped_rows += 1
            continue
        history_ids = _history_ids(list(row["seq"]), item_count=item_count)
        history_vector = _history_vector(embeddings, history_ids)
        if history_vector is None:
            skipped_rows += 1
            continue

        next_score = float(embeddings[next_item] @ history_vector)
        popularity_neg_scores = embeddings[sampled_popularity_negs[row_index]] @ history_vector
        uniform_neg_scores = embeddings[sampled_uniform_negs[row_index]] @ history_vector
        popularity_scores.append(_utility_score(next_score, popularity_neg_scores))
        uniform_scores.append(_utility_score(next_score, uniform_neg_scores))
        coherence_scores.append(float((embeddings[np.asarray(history_ids, dtype=np.int64)] @ history_vector).mean()))
        history_lengths.append(len(history_ids))

    if not popularity_scores:
        raise ValueError(f"no usable sampled transitions for dataset {dataset_name}")

    popularity_scores_array = np.asarray(popularity_scores, dtype=np.float64)
    uniform_scores_array = np.asarray(uniform_scores, dtype=np.float64)
    coherence_scores_array = np.asarray(coherence_scores, dtype=np.float64)
    history_lengths_array = np.asarray(history_lengths, dtype=np.float64)
    quartile_rows = _coherence_quartile_rows(
        dataset_name=dataset_name,
        coherence_scores=coherence_scores_array,
        utility_popularity=popularity_scores_array,
        utility_uniform=uniform_scores_array,
    )

    u_ds_popularity = float(popularity_scores_array.mean())
    row = {
        "dataset": dataset_name,
        "dataset_dir": str(dataset_dir),
        "train_row_count": int(len(train_df)),
        "sampled_row_count": int(len(sampled_df)),
        "usable_row_count": int(len(popularity_scores_array)),
        "skipped_row_count": int(skipped_rows),
        "negative_count": int(negative_count),
        "history_length_mean": float(history_lengths_array.mean()),
        "history_length_median": float(np.median(history_lengths_array)),
        "coherence_mean": float(coherence_scores_array.mean()),
        "coherence_median": float(np.median(coherence_scores_array)),
        "u_ds_popularity": u_ds_popularity,
        "u_ds_uniform": float(uniform_scores_array.mean()),
        "phi_u_ds": _phi_from_utility(u_ds_popularity),
        "bank_hash": _sha256_paths(text_bank_path, embeddings_path),
        "split_hash": _sha256_paths(train_split_path),
    }
    return row, quartile_rows


def _criterion_inputs(dataset_rows: list[dict[str, object]]) -> dict[str, object]:
    sorted_rows = sorted(dataset_rows, key=lambda row: (float(row["u_ds_popularity"]), str(row["dataset"])), reverse=True)
    ranking = [str(row["dataset"]) for row in sorted_rows]
    by_name = {str(row["dataset"]): row for row in dataset_rows}
    ml1m_row = by_name.get("ML1M")
    ml1m_rank = ranking.index("ML1M") + 1 if ml1m_row is not None and "ML1M" in ranking else None
    non_ml1m_phi_ge_0_5_count = sum(
        1
        for row in dataset_rows
        if str(row["dataset"]) != "ML1M" and float(row["phi_u_ds"]) >= 0.5
    )
    return {
        "u_ds_popularity_ranking_desc": ranking,
        "ml1m_rank_by_u_ds": ml1m_rank,
        "ml1m_u_ds": None if ml1m_row is None else float(ml1m_row["u_ds_popularity"]),
        "ml1m_phi": None if ml1m_row is None else float(ml1m_row["phi_u_ds"]),
        "non_ml1m_phi_ge_0_5_count": int(non_ml1m_phi_ge_0_5_count),
        "interpretation_note": "FOLLOWUP-07 owns the frozen Gate 0-v2 pass/fail decision.",
    }


def _write_markdown(report: dict[str, object], output_path: Path) -> None:
    summary_df = pd.DataFrame(report["datasets"])
    quartile_df = pd.DataFrame(report["coherence_quartiles"])

    lines = [
        "# Gate0 Text Utility Diagnostic",
        "",
        "This artifact freezes the production-bank `U_ds` inputs required by spec section 7.4.",
        "It does **not** make the Gate 0-v2 pass/fail decision; that interpretation belongs to `FOLLOWUP-07`.",
        "",
        "## Protocol",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Sample size per dataset: `{report['protocol']['sample_size']}`",
        f"- Negatives per sampled transition: `{report['protocol']['negative_count']}`",
        f"- Seed: `{report['protocol']['seed']}`",
        f"- Primary statistic: `{report['protocol']['primary_statistic']}`",
        f"- Diagnostic statistic: `{report['protocol']['diagnostic_statistic']}`",
        "",
        "## Dataset Summary",
        "",
        summary_df.to_markdown(index=False),
        "",
        "## Frozen Gate0-v2 Inputs",
        "",
        f"- `U_ds` descending rank: `{', '.join(report['criterion_inputs']['u_ds_popularity_ranking_desc'])}`",
        f"- `ML1M` rank by `U_ds`: `{report['criterion_inputs']['ml1m_rank_by_u_ds']}`",
        f"- `ML1M` `U_ds`: `{report['criterion_inputs']['ml1m_u_ds']}`",
        f"- `ML1M` `phi(U_ds)`: `{report['criterion_inputs']['ml1m_phi']}`",
        f"- Non-`ML1M` datasets with `phi(U_ds) >= 0.5`: `{report['criterion_inputs']['non_ml1m_phi_ge_0_5_count']}`",
        f"- Note: {report['criterion_inputs']['interpretation_note']}",
        "",
    ]

    if not quartile_df.empty:
        for dataset_name, dataset_df in quartile_df.groupby("dataset", sort=False):
            lines.extend(
                [
                    f"## Coherence Quartiles: `{dataset_name}`",
                    "",
                    dataset_df.to_markdown(index=False),
                    "",
                ]
            )

    output_path.write_text("\n".join(lines), encoding="utf-8")


def build_text_utility_report(
    *,
    dataset_dirs: dict[str, Path],
    output_dir: Path | str,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    negative_count: int = DEFAULT_NEGATIVE_COUNT,
    seed: int = DEFAULT_SEED,
) -> dict[str, object]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset_rows: list[dict[str, object]] = []
    quartile_rows: list[dict[str, object]] = []
    for dataset_name, dataset_dir in dataset_dirs.items():
        row, dataset_quartiles = _dataset_row(
            dataset_name=dataset_name,
            dataset_dir=Path(dataset_dir),
            sample_size=sample_size,
            negative_count=negative_count,
            seed=seed,
        )
        dataset_rows.append(row)
        quartile_rows.extend(dataset_quartiles)

    report = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "protocol": {
            "sample_size": int(sample_size),
            "negative_count": int(negative_count),
            "seed": int(seed),
            "primary_statistic": "U_ds_popularity = P(sim(h,next) > sim(h,neg_pop)) with 100 train-next-popularity negatives",
            "diagnostic_statistic": "U_ds_uniform = P(sim(h,next) > sim(h,neg_uniform)) with 100 uniform negatives",
            "history_vector": "normalized mean of valid history item embeddings from the production t5-xl bank",
            "coherence_breakdown": "ranked coherence quartiles over sampled train transitions",
        },
        "datasets": dataset_rows,
        "coherence_quartiles": quartile_rows,
        "criterion_inputs": _criterion_inputs(dataset_rows),
    }

    pd.DataFrame(dataset_rows).to_csv(output_dir / "gate0_text_utility_summary.csv", index=False)
    pd.DataFrame(quartile_rows).to_csv(output_dir / "gate0_text_utility_coherence_quartiles.csv", index=False)
    _stable_json_dump(report, output_dir / "gate0_text_utility_report.json")
    _write_markdown(report, output_dir / "gate0_text_utility_report.md")
    return report


def main() -> None:
    args = parse_args()
    report = build_text_utility_report(
        dataset_dirs=_parse_dataset_args(args.dataset),
        output_dir=Path(args.output_dir),
        sample_size=args.sample_size,
        negative_count=args.negative_count,
        seed=args.seed,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
