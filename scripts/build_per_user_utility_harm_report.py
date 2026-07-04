#!/usr/bin/env python3

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from omegaconf import OmegaConf


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = REPO_ROOT / "model"
SCRIPT_ROOT = REPO_ROOT / "scripts"
for candidate in (REPO_ROOT, MODEL_ROOT, SCRIPT_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import dataset_runtime
import graph_lib
import noise_lib
import sampling
from build_gate0_text_utility_report import (
    DEFAULT_DATASET_ROOT,
    DEFAULT_NEGATIVE_COUNT,
    DEFAULT_SEED,
    DEFAULT_EMBEDDING_FILENAME,
    TEXT_BANK_FILENAME,
    _load_embedding_matrix,
    _parse_dataset_args,
    _sha256_paths,
    _stable_json_dump,
    build_next_item_distribution,
)
from model.ema import ExponentialMovingAverage
from model.transformer import SEDD4REC


DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "reports" / "data" / "2026-07-04-followup09"
DEFAULT_RUN_ROOT = Path("/data/Zijian/goal/RecDemoRuns/main_table_text_side")
DEFAULT_CORE_ROOT = Path("/data/Zijian/goal/RecDemo/checkpoints-meta")
DEFAULT_DATASETS = ("ML1M", "Steam")
DEFAULT_ROWS_PER_USER = 4
DEFAULT_EVAL_BATCH_SIZE = 256
DEFAULT_UTILITY_BATCH_SIZE = 1024
DEFAULT_DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
DEFAULT_TARGET_LENGTH = 10

CORE_GRAPH_TYPES = {
    "ASO": "hybrid",
    "ATG": "hybrid",
    "Beauty": "adaptive",
    "ML1M": "hybrid",
    "Steam": "adaptive",
}

CORE_SUMMARY_NAMES = {
    "adaptive": "best_summary_adaptive.json",
    "hybrid": "best_summary_hybrid.json",
    "proposal_adaptive": "best_summary_proposal_adaptive.json",
}


@dataclass(frozen=True)
class DatasetPaths:
    name: str
    dataset_dir: Path
    v1_log_path: Path
    v1_checkpoint_path: Path
    v1_summary_path: Path
    core_checkpoint_path: Path
    core_summary_path: Path
    core_graph_type: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the FOLLOWUP-09 per-user utility-vs-harm report by pairing train-only text utility "
            "with frozen v1-vs-core per-user deltas."
        )
    )
    parser.add_argument(
        "--dataset",
        action="append",
        default=[],
        help="Dataset mapping in the form NAME=PATH. Defaults to ML1M and Steam under dataset/paper_raw_v1.",
    )
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--core-root", type=Path, default=DEFAULT_CORE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--rows-per-user", type=int, default=DEFAULT_ROWS_PER_USER)
    parser.add_argument("--negative-count", type=int, default=DEFAULT_NEGATIVE_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--eval-batch-size", type=int, default=DEFAULT_EVAL_BATCH_SIZE)
    parser.add_argument("--utility-batch-size", type=int, default=DEFAULT_UTILITY_BATCH_SIZE)
    parser.add_argument("--device", default=DEFAULT_DEVICE)
    parser.add_argument(
        "--core-graph-type",
        action="append",
        default=[],
        help="Optional NAME=GRAPH override for the frozen core checkpoint graph type.",
    )
    return parser.parse_args()


def _parse_name_mapping(entries: list[str], *, value_name: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for entry in entries:
        if "=" not in entry:
            raise ValueError(f"{value_name} entry must be NAME=VALUE, got {entry!r}")
        name, value = entry.split("=", 1)
        mapping[name] = value
    return mapping


def _default_dataset_dirs(dataset_args: list[str]) -> dict[str, Path]:
    if dataset_args:
        return _parse_dataset_args(dataset_args)
    return {name: DEFAULT_DATASET_ROOT / name for name in DEFAULT_DATASETS}


def _default_v1_run_dir(run_root: Path, dataset_name: str) -> Path:
    return Path(run_root) / f"{dataset_name.lower()}_proposal_adaptive_mainpath"


def _default_v1_log_path(run_root: Path, dataset_name: str) -> Path:
    run_dir = _default_v1_run_dir(run_root, dataset_name)
    return run_dir / "logs" / f"{dataset_name.lower()}_proposal_adaptive_mainpath.log"


def _default_v1_checkpoint_path(run_root: Path, dataset_name: str) -> Path:
    run_dir = _default_v1_run_dir(run_root, dataset_name)
    return run_dir / "checkpoints-meta" / dataset_name / "checkpoint_proposal_adaptive_best.pth"


def _default_v1_summary_path(run_root: Path, dataset_name: str) -> Path:
    run_dir = _default_v1_run_dir(run_root, dataset_name)
    return run_dir / "checkpoints-meta" / dataset_name / "best_summary_proposal_adaptive.json"


def _default_core_checkpoint_path(core_root: Path, dataset_name: str, core_graph_type: str) -> Path:
    return Path(core_root) / dataset_name / f"checkpoint_{core_graph_type}_best.pth"


def _default_core_summary_path(core_root: Path, dataset_name: str, core_graph_type: str) -> Path:
    summary_name = CORE_SUMMARY_NAMES.get(core_graph_type)
    if summary_name is None:
        raise ValueError(f"unsupported core graph type: {core_graph_type}")
    return Path(core_root) / dataset_name / summary_name


def _build_dataset_paths(
    dataset_dirs: dict[str, Path],
    *,
    run_root: Path,
    core_root: Path,
    core_graph_overrides: dict[str, str],
) -> list[DatasetPaths]:
    rows: list[DatasetPaths] = []
    for dataset_name, dataset_dir in dataset_dirs.items():
        core_graph_type = core_graph_overrides.get(dataset_name, CORE_GRAPH_TYPES.get(dataset_name))
        if core_graph_type is None:
            raise ValueError(f"missing core graph type for dataset {dataset_name!r}")
        rows.append(
            DatasetPaths(
                name=dataset_name,
                dataset_dir=Path(dataset_dir).resolve(),
                v1_log_path=_default_v1_log_path(run_root, dataset_name),
                v1_checkpoint_path=_default_v1_checkpoint_path(run_root, dataset_name),
                v1_summary_path=_default_v1_summary_path(run_root, dataset_name),
                core_checkpoint_path=_default_core_checkpoint_path(core_root, dataset_name, core_graph_type),
                core_summary_path=_default_core_summary_path(core_root, dataset_name, core_graph_type),
                core_graph_type=core_graph_type,
            )
        )
    return rows


def _pad_to_length(sequence: list[int], *, target_length: int, pad_value: int) -> list[int]:
    if len(sequence) < target_length:
        return [pad_value] * (target_length - len(sequence)) + sequence
    return sequence


def _load_train_sequences(path: Path) -> list[list[int]]:
    sequences: list[list[int]] = []
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Stored protocol text is 1-indexed; the in-memory/train_data.df protocol is 0-indexed.
        sequence = [int(token) - 1 for token in line.split()]
        sequences.append(sequence)
    return sequences


def _expand_user_rows(
    sequences: list[list[int]],
    *,
    pad_value: int,
    target_length: int,
    rows_per_user: int,
    seed: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for user_index, raw_sequence in enumerate(sequences):
        sequence = list(raw_sequence)
        if len(sequence) <= 1:
            continue
        candidate_rows: list[dict[str, Any]] = []
        if len(sequence) <= target_length + 1:
            prefix = sequence[:-1]
            candidate_rows.append(
                {
                    "seq": _pad_to_length(prefix, target_length=target_length, pad_value=pad_value),
                    "len_seq": len(prefix),
                    "next": sequence[-1],
                }
            )
        else:
            for start in range(len(sequence) - target_length):
                candidate_rows.append(
                    {
                        "seq": sequence[start : start + target_length],
                        "len_seq": target_length,
                        "next": sequence[start + target_length],
                    }
                )

        selected_indices = list(range(len(candidate_rows)))
        if rows_per_user > 0 and len(candidate_rows) > rows_per_user:
            rng = np.random.default_rng(seed + user_index)
            selected_indices = sorted(rng.choice(len(candidate_rows), size=rows_per_user, replace=False).tolist())

        for sampled_order, candidate_index in enumerate(selected_indices):
            row = deepcopy(candidate_rows[candidate_index])
            row["user_index"] = int(user_index)
            row["user_total_rows"] = int(len(candidate_rows))
            row["candidate_row_index"] = int(candidate_index)
            row["sampled_order"] = int(sampled_order)
            rows.append(row)

    return pd.DataFrame(rows, columns=["user_index", "user_total_rows", "candidate_row_index", "sampled_order", "seq", "len_seq", "next"])


def _parse_logged_cfg(log_path: Path) -> dict[str, Any]:
    lines = Path(log_path).read_text(encoding="utf-8", errors="ignore").splitlines()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("{") and "'training'" in stripped:
            return ast.literal_eval(stripped)
    raise ValueError(f"unable to find serialized config dict in log: {log_path}")


def _cfg_from_logged_dict(
    logged_cfg: dict[str, Any],
    *,
    dataset_name: str,
    dataset_dir: Path,
    text_side_enabled: bool,
    graph_type: str,
) -> Any:
    cfg_dict = deepcopy(logged_cfg)
    cfg_dict["work_dir"] = str(REPO_ROOT)
    cfg_dict["training"]["data"] = dataset_name
    cfg_dict["graph"]["type"] = graph_type
    cfg_dict["data"][dataset_name]["path"] = str(dataset_dir)
    cfg_dict["data"][dataset_name]["item_num"] = int(len(pd.read_csv(dataset_dir / TEXT_BANK_FILENAME)))
    cfg_dict.setdefault("text_side", {})
    cfg_dict["text_side"]["enabled"] = bool(text_side_enabled)
    cfg_dict["text_side"]["dataset_dir"] = str(dataset_dir)
    cfg_dict["text_side"]["text_bank_path"] = str(dataset_dir / TEXT_BANK_FILENAME)
    cfg_dict["text_side"]["embeddings_path"] = str(dataset_dir / DEFAULT_EMBEDDING_FILENAME)
    if not text_side_enabled:
        cfg_dict["text_side"]["dataset_dir"] = str(dataset_dir)
        cfg_dict["text_side"]["text_bank_path"] = None
        cfg_dict["text_side"]["embeddings_path"] = None
    cfg = OmegaConf.create(cfg_dict)
    dataset_runtime.reconcile_runtime_dataset_config(cfg)
    return cfg


def _load_summary_metrics(path: Path) -> dict[str, float | int | None]:
    if not Path(path).exists():
        return {
            "best_step": None,
            "best_metric": None,
            "test_p2_ndcg10": None,
        }
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        "best_step": int(payload["best_step"]),
        "best_metric": float(payload["best_metric"]),
        "test_p2_ndcg10": float(payload["test"]["p2"]["ndcg"][2]),
    }


def _load_checkpoint_sampling_fn(
    *,
    cfg: Any,
    checkpoint_path: Path,
    device: torch.device,
) -> tuple[SEDD4REC, Any]:
    graph = graph_lib.get_graph(cfg, device)
    model = SEDD4REC(cfg).to(device)
    ema = ExponentialMovingAverage(model.parameters(), decay=float(cfg.training.ema))
    checkpoint = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(checkpoint["model"], strict=False)
    ema.load_state_dict(checkpoint["ema"])
    ema.copy_to(model.parameters())
    model.eval()
    noise = noise_lib.get_noise(cfg).to(device)
    sampling_fn = sampling.get_sampling_fn(
        cfg,
        graph,
        noise,
        eps=1e-5,
        personalization_strength=float(cfg.sampling.personalization_strength),
        device=device,
    )
    return model, sampling_fn


def _evaluate_rows(
    rows_df: pd.DataFrame,
    *,
    model: SEDD4REC,
    sampling_fn: Any,
    batch_size: int,
    item_count: int,
    device: torch.device,
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    sequences = np.asarray(rows_df["seq"].tolist(), dtype=np.int64)
    targets = rows_df["next"].to_numpy(dtype=np.int64)

    with torch.no_grad():
        for start in range(0, len(rows_df), batch_size):
            end = min(start + batch_size, len(rows_df))
            batch_histories = torch.as_tensor(sequences[start:end], dtype=torch.long, device=device)
            batch_targets = torch.as_tensor(targets[start:end], dtype=torch.long, device=device)
            prediction = sampling_fn(model, (end - start, 1), batch_histories)[:, 0, :item_count]
            target_scores = prediction.gather(1, batch_targets.unsqueeze(1)).squeeze(1)
            higher_counts = (prediction > target_scores.unsqueeze(1)).sum(dim=1)
            ranks = higher_counts + 1
            ndcg10 = torch.where(
                ranks <= 10,
                1.0 / torch.log2(ranks.float() + 1.0),
                torch.zeros_like(ranks, dtype=torch.float32),
            )
            hit10 = (ranks <= 10).float()
            for offset in range(end - start):
                row = rows_df.iloc[start + offset]
                records.append(
                    {
                        "user_index": int(row["user_index"]),
                        "candidate_row_index": int(row["candidate_row_index"]),
                        "sampled_order": int(row["sampled_order"]),
                        "rank": int(ranks[offset].item()),
                        "hit10": float(hit10[offset].item()),
                        "ndcg10": float(ndcg10[offset].item()),
                    }
                )

    return pd.DataFrame(records)


def _compute_utility_rows(
    rows_df: pd.DataFrame,
    *,
    embeddings: np.ndarray,
    popularity_probs: np.ndarray,
    item_count: int,
    negative_count: int,
    seed: int,
    batch_size: int,
    device: torch.device,
) -> pd.DataFrame:
    sampled_rows = rows_df.reset_index(drop=True)
    negative_ids = np.random.default_rng(seed).choice(
        item_count,
        size=(len(sampled_rows), negative_count),
        replace=True,
        p=popularity_probs,
    )

    embedding_tensor = torch.as_tensor(embeddings, dtype=torch.float32, device=device)
    history_tensor = torch.as_tensor(np.asarray(sampled_rows["seq"].tolist(), dtype=np.int64), dtype=torch.long)
    target_tensor = torch.as_tensor(sampled_rows["next"].to_numpy(dtype=np.int64), dtype=torch.long)
    negative_tensor = torch.as_tensor(negative_ids, dtype=torch.long)
    pad_value = item_count

    rows: list[dict[str, Any]] = []
    with torch.no_grad():
        for start in range(0, len(sampled_rows), batch_size):
            end = min(start + batch_size, len(sampled_rows))
            batch_histories = history_tensor[start:end].to(device)
            batch_targets = target_tensor[start:end].to(device)
            batch_negatives = negative_tensor[start:end].to(device)

            valid_mask = batch_histories != pad_value
            safe_history = batch_histories.clamp(max=item_count - 1)
            gathered = embedding_tensor[safe_history] * valid_mask.unsqueeze(-1)
            valid_counts = valid_mask.sum(dim=1).clamp_min(1).unsqueeze(-1)
            history_repr = F.normalize(gathered.sum(dim=1) / valid_counts, dim=-1)
            next_scores = (embedding_tensor[batch_targets] * history_repr).sum(dim=-1)
            negative_scores = (embedding_tensor[batch_negatives] * history_repr.unsqueeze(1)).sum(dim=-1)
            utility = (
                (next_scores.unsqueeze(1) > negative_scores).float().mean(dim=1)
                + 0.5 * (next_scores.unsqueeze(1) == negative_scores).float().mean(dim=1)
            )
            coherence = (gathered * history_repr.unsqueeze(1)).sum(dim=-1)
            coherence = (coherence * valid_mask.float()).sum(dim=1) / valid_mask.sum(dim=1).clamp_min(1).float()
            history_lengths = valid_mask.sum(dim=1)

            for offset in range(end - start):
                row = sampled_rows.iloc[start + offset]
                rows.append(
                    {
                        "user_index": int(row["user_index"]),
                        "candidate_row_index": int(row["candidate_row_index"]),
                        "sampled_order": int(row["sampled_order"]),
                        "utility_popularity": float(utility[offset].item()),
                        "coherence": float(coherence[offset].item()),
                        "history_length": int(history_lengths[offset].item()),
                    }
                )

    return pd.DataFrame(rows)


def _correlation_row(metric: str, x: pd.Series, y: pd.Series) -> dict[str, Any]:
    valid = pd.concat([x, y], axis=1).dropna()
    if valid.empty:
        pearson = float("nan")
        spearman = float("nan")
        user_count = 0
    else:
        pearson = float(valid.iloc[:, 0].corr(valid.iloc[:, 1], method="pearson"))
        spearman = float(valid.iloc[:, 0].corr(valid.iloc[:, 1], method="spearman"))
        user_count = int(len(valid))
    return {
        "metric": metric,
        "user_count": user_count,
        "pearson": pearson,
        "spearman": spearman,
    }


def _make_quartile_bucket(values: pd.Series, *, bucket_name: str) -> pd.Series:
    ranked = values.rank(method="first")
    bucket_count = min(4, int(ranked.nunique()))
    if bucket_count <= 1:
        return pd.Series(["all"] * len(values), index=values.index, name=bucket_name)
    labels = [f"Q{index + 1}" for index in range(bucket_count)]
    buckets = pd.qcut(ranked, q=bucket_count, labels=labels, duplicates="drop")
    return buckets.rename(bucket_name)


def _markdown_cell(value: Any) -> str:
    if value is None:
        return ""
    if pd.api.types.is_scalar(value) and pd.isna(value):
        return ""
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _dataframe_to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "_(no rows)_"
    headers = [str(column) for column in df.columns]
    lines = [
        "| " + " | ".join(_markdown_cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in df.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(_markdown_cell(value) for value in row) + " |")
    return "\n".join(lines)


def _write_markdown(report: dict[str, Any], output_path: Path) -> None:
    dataset_df = pd.DataFrame(report["datasets"])
    lines = [
        "# Per-user Utility vs Harm Report",
        "",
        "This artifact pairs train-only sampled per-user text utility with frozen first-generation (`v1`) vs host-core",
        "per-user `p2` ranking deltas on the same sampled train-user transitions.",
        "",
        "## Protocol",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Rows sampled per user: `{report['protocol']['rows_per_user']}`",
        f"- Utility negatives per sampled row: `{report['protocol']['negative_count']}`",
        f"- Seed: `{report['protocol']['seed']}`",
        f"- Device: `{report['protocol']['device']}`",
        f"- Primary correlation claim: `{report['protocol']['primary_claim_metric']}`",
        "",
        "## Dataset Summary",
        "",
        _dataframe_to_markdown(dataset_df),
        "",
    ]

    for dataset_row in report["datasets"]:
        dataset_name = str(dataset_row["dataset"])
        lines.extend(
            [
                f"## {dataset_name}",
                "",
                f"- User count: `{dataset_row['user_count']}`",
                f"- Sampled rows: `{dataset_row['sampled_row_count']}`",
                f"- Spearman(`utility`, `delta_ndcg10`): `{dataset_row['spearman_utility_vs_delta_ndcg10']}`",
                f"- Pearson(`utility`, `delta_ndcg10`): `{dataset_row['pearson_utility_vs_delta_ndcg10']}`",
                f"- Inverse ordering observed: `{dataset_row['inverse_ordering_observed']}`",
                f"- Interpretation: {dataset_row['interpretation']}",
                "",
                "### Utility buckets",
                "",
                _dataframe_to_markdown(pd.DataFrame(dataset_row["utility_buckets"])),
                "",
                "### Correlations",
                "",
                _dataframe_to_markdown(pd.DataFrame(dataset_row["correlations"])),
                "",
            ]
        )

    output_path.write_text("\n".join(lines), encoding="utf-8")


def _dataset_report_row(
    paths: DatasetPaths,
    *,
    rows_per_user: int,
    negative_count: int,
    seed: int,
    eval_batch_size: int,
    utility_batch_size: int,
    device: torch.device,
    output_dir: Path,
) -> dict[str, Any]:
    dataset_dir = paths.dataset_dir
    text_bank_path = dataset_dir / TEXT_BANK_FILENAME
    embeddings_path = dataset_dir / DEFAULT_EMBEDDING_FILENAME
    train_text_path = dataset_dir / "train_data.txt"
    train_df_path = dataset_dir / "train_data.df"
    if not text_bank_path.exists():
        raise FileNotFoundError(f"missing text bank: {text_bank_path}")
    if not embeddings_path.exists():
        raise FileNotFoundError(f"missing embeddings artifact: {embeddings_path}")
    if not train_text_path.exists():
        raise FileNotFoundError(f"missing train sequence text: {train_text_path}")
    if not train_df_path.exists():
        raise FileNotFoundError(f"missing train df: {train_df_path}")

    item_df = pd.read_csv(text_bank_path).sort_values("item_id").reset_index(drop=True)
    item_ids = item_df["item_id"].astype(int).to_numpy()
    item_count = int(len(item_df))
    embeddings = _load_embedding_matrix(embeddings_path, item_ids)
    train_df = pd.read_pickle(train_df_path)
    popularity_probs = build_next_item_distribution(train_df, item_count=item_count)
    train_sequences = _load_train_sequences(train_text_path)
    sampled_rows = _expand_user_rows(
        train_sequences,
        pad_value=item_count,
        target_length=DEFAULT_TARGET_LENGTH,
        rows_per_user=rows_per_user,
        seed=seed,
    )
    if sampled_rows.empty:
        raise ValueError(f"dataset {paths.name} produced no sampled train-user rows")

    utility_rows = _compute_utility_rows(
        sampled_rows,
        embeddings=embeddings,
        popularity_probs=popularity_probs,
        item_count=item_count,
        negative_count=negative_count,
        seed=seed,
        batch_size=utility_batch_size,
        device=device,
    )

    logged_cfg = _parse_logged_cfg(paths.v1_log_path)
    v1_cfg = _cfg_from_logged_dict(
        logged_cfg,
        dataset_name=paths.name,
        dataset_dir=dataset_dir,
        text_side_enabled=True,
        graph_type="proposal_adaptive",
    )
    core_cfg = _cfg_from_logged_dict(
        logged_cfg,
        dataset_name=paths.name,
        dataset_dir=dataset_dir,
        text_side_enabled=False,
        graph_type=paths.core_graph_type,
    )

    v1_model, v1_sampling_fn = _load_checkpoint_sampling_fn(cfg=v1_cfg, checkpoint_path=paths.v1_checkpoint_path, device=device)
    core_model, core_sampling_fn = _load_checkpoint_sampling_fn(
        cfg=core_cfg,
        checkpoint_path=paths.core_checkpoint_path,
        device=device,
    )

    v1_eval = _evaluate_rows(
        sampled_rows,
        model=v1_model,
        sampling_fn=v1_sampling_fn,
        batch_size=eval_batch_size,
        item_count=item_count,
        device=device,
    ).rename(columns={"rank": "v1_rank", "hit10": "v1_hit10", "ndcg10": "v1_ndcg10"})
    core_eval = _evaluate_rows(
        sampled_rows,
        model=core_model,
        sampling_fn=core_sampling_fn,
        batch_size=eval_batch_size,
        item_count=item_count,
        device=device,
    ).rename(columns={"rank": "core_rank", "hit10": "core_hit10", "ndcg10": "core_ndcg10"})

    merged_rows = utility_rows.merge(
        v1_eval,
        on=["user_index", "candidate_row_index", "sampled_order"],
        how="inner",
    ).merge(
        core_eval,
        on=["user_index", "candidate_row_index", "sampled_order"],
        how="inner",
    )
    merged_rows["delta_ndcg10"] = merged_rows["v1_ndcg10"] - merged_rows["core_ndcg10"]
    merged_rows["delta_hit10"] = merged_rows["v1_hit10"] - merged_rows["core_hit10"]
    merged_rows["delta_rank"] = merged_rows["core_rank"] - merged_rows["v1_rank"]
    merged_rows["dataset"] = paths.name

    per_user = (
        merged_rows.groupby("user_index", observed=True)
        .agg(
            user_total_rows=("candidate_row_index", "count"),
            utility_popularity=("utility_popularity", "mean"),
            coherence=("coherence", "mean"),
            history_length_mean=("history_length", "mean"),
            v1_ndcg10=("v1_ndcg10", "mean"),
            core_ndcg10=("core_ndcg10", "mean"),
            delta_ndcg10=("delta_ndcg10", "mean"),
            v1_hit10=("v1_hit10", "mean"),
            core_hit10=("core_hit10", "mean"),
            delta_hit10=("delta_hit10", "mean"),
            v1_rank=("v1_rank", "mean"),
            core_rank=("core_rank", "mean"),
            delta_rank=("delta_rank", "mean"),
        )
        .reset_index()
    )
    per_user["utility_bucket"] = _make_quartile_bucket(per_user["utility_popularity"], bucket_name="utility_bucket")

    bucket_summary = (
        per_user.groupby("utility_bucket", observed=True)
        .agg(
            user_count=("user_index", "count"),
            utility_mean=("utility_popularity", "mean"),
            utility_min=("utility_popularity", "min"),
            utility_max=("utility_popularity", "max"),
            delta_ndcg10_mean=("delta_ndcg10", "mean"),
            delta_hit10_mean=("delta_hit10", "mean"),
            delta_rank_mean=("delta_rank", "mean"),
            v1_ndcg10_mean=("v1_ndcg10", "mean"),
            core_ndcg10_mean=("core_ndcg10", "mean"),
        )
        .reset_index()
    )

    correlations = pd.DataFrame(
        [
            _correlation_row("utility_vs_delta_ndcg10", per_user["utility_popularity"], per_user["delta_ndcg10"]),
            _correlation_row("utility_vs_delta_hit10", per_user["utility_popularity"], per_user["delta_hit10"]),
            _correlation_row("utility_vs_delta_rank", per_user["utility_popularity"], per_user["delta_rank"]),
        ]
    )
    correlation_row = correlations.loc[correlations["metric"] == "utility_vs_delta_ndcg10"].iloc[0]
    bucket_delta_values = bucket_summary["delta_ndcg10_mean"].tolist()
    inverse_ordering_observed = bool(
        float(correlation_row["spearman"]) < 0.0
        and all(bucket_delta_values[index] >= bucket_delta_values[index + 1] for index in range(len(bucket_delta_values) - 1))
    )
    interpretation = (
        "A negative within-dataset association is visible at user level."
        if float(correlation_row["spearman"]) < 0.0
        else "The within-dataset user-level association is weak or non-negative in this readout."
    )

    per_user_path = output_dir / f"{paths.name}_per_user_points.csv"
    bucket_path = output_dir / f"{paths.name}_utility_bucket_summary.csv"
    correlation_path = output_dir / f"{paths.name}_correlations.csv"
    merged_rows.to_csv(output_dir / f"{paths.name}_sampled_transition_points.csv", index=False)
    per_user.to_csv(per_user_path, index=False)
    bucket_summary.to_csv(bucket_path, index=False)
    correlations.to_csv(correlation_path, index=False)

    v1_summary = _load_summary_metrics(paths.v1_summary_path)
    core_summary = _load_summary_metrics(paths.core_summary_path)
    return {
        "dataset": paths.name,
        "dataset_dir": str(dataset_dir),
        "user_count": int(len(per_user)),
        "sampled_row_count": int(len(merged_rows)),
        "rows_per_user": int(rows_per_user),
        "negative_count": int(negative_count),
        "bank_hash": _sha256_paths(text_bank_path, embeddings_path),
        "split_hash": _sha256_paths(train_text_path, train_df_path),
        "v1_log_path": str(paths.v1_log_path),
        "v1_checkpoint_path": str(paths.v1_checkpoint_path),
        "core_checkpoint_path": str(paths.core_checkpoint_path),
        "core_graph_type": paths.core_graph_type,
        "v1_best_step": v1_summary["best_step"],
        "v1_test_p2_ndcg10": v1_summary["test_p2_ndcg10"],
        "core_best_step": core_summary["best_step"],
        "core_test_p2_ndcg10": core_summary["test_p2_ndcg10"],
        "pearson_utility_vs_delta_ndcg10": float(correlation_row["pearson"]),
        "spearman_utility_vs_delta_ndcg10": float(correlation_row["spearman"]),
        "inverse_ordering_observed": inverse_ordering_observed,
        "interpretation": interpretation,
        "utility_buckets": bucket_summary.to_dict(orient="records"),
        "correlations": correlations.to_dict(orient="records"),
        "per_user_csv": str(per_user_path),
        "bucket_csv": str(bucket_path),
        "correlation_csv": str(correlation_path),
    }


def build_per_user_utility_harm_report(
    *,
    dataset_dirs: dict[str, Path],
    output_dir: Path | str,
    run_root: Path = DEFAULT_RUN_ROOT,
    core_root: Path = DEFAULT_CORE_ROOT,
    rows_per_user: int = DEFAULT_ROWS_PER_USER,
    negative_count: int = DEFAULT_NEGATIVE_COUNT,
    seed: int = DEFAULT_SEED,
    eval_batch_size: int = DEFAULT_EVAL_BATCH_SIZE,
    utility_batch_size: int = DEFAULT_UTILITY_BATCH_SIZE,
    device: str = DEFAULT_DEVICE,
    core_graph_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    resolved_device = torch.device(device if device == "cpu" or torch.cuda.is_available() else "cpu")
    dataset_paths = _build_dataset_paths(
        dataset_dirs,
        run_root=Path(run_root),
        core_root=Path(core_root),
        core_graph_overrides=dict(core_graph_overrides or {}),
    )

    dataset_rows: list[dict[str, Any]] = []
    for paths in dataset_paths:
        dataset_rows.append(
            _dataset_report_row(
                paths,
                rows_per_user=rows_per_user,
                negative_count=negative_count,
                seed=seed,
                eval_batch_size=eval_batch_size,
                utility_batch_size=utility_batch_size,
                device=resolved_device,
                output_dir=output_dir,
            )
        )

    summary_df = pd.DataFrame(
        [
            {
                "dataset": row["dataset"],
                "user_count": row["user_count"],
                "sampled_row_count": row["sampled_row_count"],
                "pearson_utility_vs_delta_ndcg10": row["pearson_utility_vs_delta_ndcg10"],
                "spearman_utility_vs_delta_ndcg10": row["spearman_utility_vs_delta_ndcg10"],
                "inverse_ordering_observed": row["inverse_ordering_observed"],
                "v1_test_p2_ndcg10": row["v1_test_p2_ndcg10"],
                "core_test_p2_ndcg10": row["core_test_p2_ndcg10"],
            }
            for row in dataset_rows
        ]
    )
    summary_df.to_csv(output_dir / "per_user_utility_harm_summary.csv", index=False)

    report = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "protocol": {
            "rows_per_user": int(rows_per_user),
            "negative_count": int(negative_count),
            "seed": int(seed),
            "eval_batch_size": int(eval_batch_size),
            "utility_batch_size": int(utility_batch_size),
            "device": str(resolved_device),
            "primary_claim_metric": "per-user mean delta_ndcg10 under p2 personalization on sampled train-user transitions",
            "utility_statistic": "per-user mean popularity-negative utility over sampled train-only transitions",
        },
        "datasets": dataset_rows,
    }
    _stable_json_dump(report, output_dir / "per_user_utility_harm_report.json")
    _write_markdown(report, output_dir / "per_user_utility_harm_report.md")
    return report


def main() -> None:
    args = parse_args()
    report = build_per_user_utility_harm_report(
        dataset_dirs=_default_dataset_dirs(args.dataset),
        output_dir=args.output_dir,
        run_root=args.run_root,
        core_root=args.core_root,
        rows_per_user=args.rows_per_user,
        negative_count=args.negative_count,
        seed=args.seed,
        eval_batch_size=args.eval_batch_size,
        utility_batch_size=args.utility_batch_size,
        device=args.device,
        core_graph_overrides=_parse_name_mapping(args.core_graph_type, value_name="core graph"),
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
