#!/usr/bin/env python3

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = REPO_ROOT / "model"
SCRIPT_ROOT = REPO_ROOT / "scripts"
for candidate in (REPO_ROOT, MODEL_ROOT, SCRIPT_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from build_gate0_text_utility_report import (
    DEFAULT_NEGATIVE_COUNT,
    DEFAULT_SAMPLE_SIZE,
    DEFAULT_SEED,
    _history_ids,
    _history_vector,
    _load_embedding_matrix,
    _phi_from_utility,
    _sha256_paths,
    _stable_json_dump,
    _utility_score,
    build_next_item_distribution,
)


DEFAULT_BEAUTY_DATASET_DIR = REPO_ROOT / "dataset" / "paper_raw_v1" / "Beauty"
DEFAULT_CORRUPTION_DIR = Path("/data/Zijian/goal/RecDemoRuns/beauty_corruptions")
DEFAULT_CLEAN_SUMMARY_CSV = REPO_ROOT / "docs" / "reports" / "data" / "2026-07-02-gate0" / "gate0_text_utility_summary.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "reports" / "data" / "2026-07-04-followup10"
DEFAULT_CANONICAL_VARIANTS = (
    "token_dropout",
    "token_dropout40",
    "token_dropout40625",
    "token_dropout409375",
    "token_dropout4125",
    "token_dropout425",
    "token_dropout45",
    "token_dropout50",
)


@dataclass(frozen=True)
class VariantPaths:
    variant_tag: str
    text_bank_path: Path
    embeddings_path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Recompute the frozen U_ds estimator on existing Beauty token-dropout banks and summarize the observational "
            "phi response without changing any frozen parameter."
        )
    )
    parser.add_argument("--beauty-dataset-dir", type=Path, default=DEFAULT_BEAUTY_DATASET_DIR)
    parser.add_argument("--corruption-dir", type=Path, default=DEFAULT_CORRUPTION_DIR)
    parser.add_argument("--clean-summary-csv", type=Path, default=DEFAULT_CLEAN_SUMMARY_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--variant", action="append", default=[], help="Specific token-dropout variant tag(s) to evaluate.")
    parser.add_argument(
        "--include-all-discovered",
        action="store_true",
        help="Evaluate every discovered token_dropout* bank instead of the canonical frozen ladder.",
    )
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--negative-count", type=int, default=DEFAULT_NEGATIVE_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser.parse_args()


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


def _parse_dropout_rate(variant_tag: str) -> float | None:
    if variant_tag == "token_dropout":
        return 0.3
    if not variant_tag.startswith("token_dropout"):
        return None
    suffix = variant_tag.removeprefix("token_dropout")
    if not suffix or not suffix.isdigit():
        return None
    return float(f"0.{suffix}")


def _finite_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    if np.isnan(numeric) or np.isinf(numeric):
        return None
    return numeric


def _spearman_or_none(left: pd.Series, right: pd.Series) -> float | None:
    if len(left) < 2 or len(right) < 2:
        return None
    if left.nunique(dropna=True) < 2 or right.nunique(dropna=True) < 2:
        return None
    return _finite_float_or_none(left.corr(right, method="spearman"))


def _discover_token_dropout_variants(corruption_dir: Path) -> dict[str, VariantPaths]:
    variants: dict[str, VariantPaths] = {}
    for text_bank_path in sorted(corruption_dir.glob("token_dropout*_text_bank.csv")):
        variant_tag = text_bank_path.name.removesuffix("_text_bank.csv")
        embeddings_path = corruption_dir / f"{variant_tag}_sentence_t5_xl_item_emb.pt"
        if embeddings_path.exists():
            variants[variant_tag] = VariantPaths(
                variant_tag=variant_tag,
                text_bank_path=text_bank_path.resolve(),
                embeddings_path=embeddings_path.resolve(),
            )
    standard_text_bank = corruption_dir / "token_dropout_text_bank.csv"
    standard_embeddings = corruption_dir / "token_dropout_sentence_t5_xl_item_emb.pt"
    if standard_text_bank.exists() and standard_embeddings.exists():
        variants["token_dropout"] = VariantPaths(
            variant_tag="token_dropout",
            text_bank_path=standard_text_bank.resolve(),
            embeddings_path=standard_embeddings.resolve(),
        )
    return variants


def _variant_sort_key(variant_tag: str) -> tuple[float, str]:
    dropout_rate = _parse_dropout_rate(variant_tag)
    if dropout_rate is None:
        return (float("inf"), variant_tag)
    return (float(dropout_rate), variant_tag)


def _select_variants(
    discovered: dict[str, VariantPaths],
    *,
    explicit_variants: list[str],
    include_all_discovered: bool,
) -> tuple[list[VariantPaths], str]:
    if explicit_variants:
        missing = [variant_tag for variant_tag in explicit_variants if variant_tag not in discovered]
        if missing:
            raise FileNotFoundError(f"missing corrupted bank artifacts for variants: {', '.join(missing)}")
        return ([discovered[variant_tag] for variant_tag in explicit_variants], "explicit")

    if include_all_discovered:
        variant_tags = sorted(discovered, key=_variant_sort_key)
        return ([discovered[variant_tag] for variant_tag in variant_tags], "all_discovered")

    canonical_present = [variant_tag for variant_tag in DEFAULT_CANONICAL_VARIANTS if variant_tag in discovered]
    if canonical_present:
        return ([discovered[variant_tag] for variant_tag in canonical_present], "canonical_existing")

    variant_tags = sorted(discovered, key=_variant_sort_key)
    return ([discovered[variant_tag] for variant_tag in variant_tags], "fallback_all_discovered")


def _load_clean_reference(clean_summary_csv: Path) -> dict[str, Any]:
    summary_df = pd.read_csv(clean_summary_csv)
    beauty_rows = summary_df.loc[summary_df["dataset"] == "Beauty"]
    if beauty_rows.empty:
        raise ValueError(f"clean summary CSV does not contain a Beauty row: {clean_summary_csv}")
    row = beauty_rows.iloc[0].to_dict()
    row["source_summary_csv"] = str(clean_summary_csv.resolve())
    return row


def _compute_utility_row(
    *,
    dataset_name: str,
    text_bank_path: Path,
    embeddings_path: Path,
    train_df: pd.DataFrame,
    sampled_df: pd.DataFrame,
    sampled_popularity_negs: np.ndarray,
    sampled_uniform_negs: np.ndarray,
    negative_count: int,
) -> dict[str, Any]:
    item_df = pd.read_csv(text_bank_path).sort_values("item_id").reset_index(drop=True)
    item_ids = item_df["item_id"].astype(int).to_numpy()
    item_count = len(item_df)
    embeddings = _load_embedding_matrix(embeddings_path, item_ids)

    if sampled_popularity_negs.shape != (len(sampled_df), negative_count):
        raise ValueError("sampled popularity negatives shape does not match sampled rows")
    if sampled_uniform_negs.shape != (len(sampled_df), negative_count):
        raise ValueError("sampled uniform negatives shape does not match sampled rows")

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
        raise ValueError(f"no usable sampled transitions for variant {dataset_name}")

    popularity_scores_array = np.asarray(popularity_scores, dtype=np.float64)
    uniform_scores_array = np.asarray(uniform_scores, dtype=np.float64)
    coherence_scores_array = np.asarray(coherence_scores, dtype=np.float64)
    history_lengths_array = np.asarray(history_lengths, dtype=np.float64)
    u_ds_popularity = float(popularity_scores_array.mean())

    return {
        "dataset": dataset_name,
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
        "phi_u_ds": float(_phi_from_utility(u_ds_popularity)),
        "bank_hash": _sha256_paths(text_bank_path, embeddings_path),
    }


def _build_sample_inputs(
    *,
    beauty_dataset_dir: Path,
    sample_size: int,
    negative_count: int,
    seed: int,
) -> tuple[Path, pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray, str]:
    train_split_path = beauty_dataset_dir / "train_data.df"
    if not train_split_path.exists():
        raise FileNotFoundError(f"missing Beauty train split: {train_split_path}")

    clean_text_bank_path = beauty_dataset_dir / "text_bank.csv"
    clean_embeddings_path = beauty_dataset_dir / "sentence_t5_xl_item_emb.pt"
    if not clean_text_bank_path.exists():
        raise FileNotFoundError(f"missing clean Beauty text bank: {clean_text_bank_path}")
    if not clean_embeddings_path.exists():
        raise FileNotFoundError(f"missing clean Beauty embeddings: {clean_embeddings_path}")

    clean_item_df = pd.read_csv(clean_text_bank_path).sort_values("item_id").reset_index(drop=True)
    item_count = len(clean_item_df)
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
    split_hash = _sha256_paths(train_split_path)
    return train_split_path, train_df, sampled_df, sampled_popularity_negs, sampled_uniform_negs, split_hash


def _observation_summary(clean_reference: dict[str, Any], variant_rows: list[dict[str, Any]]) -> dict[str, Any]:
    clean_phi = float(clean_reference["phi_u_ds"])
    clean_u_ds = float(clean_reference["u_ds_popularity"])
    corrupted_df = pd.DataFrame(variant_rows)
    if corrupted_df.empty:
        return {
            "clean_phi_u_ds": clean_phi,
            "clean_u_ds_popularity": clean_u_ds,
            "phi_nonzero_variant_count": 0,
            "all_corrupted_phi_ge_clean": True,
            "all_corrupted_u_ds_le_clean": True,
            "monotone_phi_over_sorted_levels": True,
            "spearman_dropout_rate_vs_phi": None,
            "spearman_dropout_rate_vs_u_ds": None,
            "direction_note": "No corrupted variants were evaluated.",
        }

    rate_mask = corrupted_df["dropout_rate"].notna()
    rate_sorted = corrupted_df.loc[rate_mask].sort_values(["dropout_rate", "variant_tag"]).reset_index(drop=True)
    phi_values = rate_sorted["phi_u_ds"].tolist()
    monotone_phi = all(phi_values[index] <= phi_values[index + 1] for index in range(len(phi_values) - 1))
    spearman_phi = _spearman_or_none(rate_sorted["dropout_rate"], rate_sorted["phi_u_ds"])
    spearman_u_ds = _spearman_or_none(rate_sorted["dropout_rate"], rate_sorted["u_ds_popularity"])
    all_phi_ge_clean = bool((corrupted_df["phi_u_ds"] >= clean_phi).all())
    all_u_ds_le_clean = bool((corrupted_df["u_ds_popularity"] <= clean_u_ds).all())
    phi_nonzero_variant_count = int((corrupted_df["phi_u_ds"] > 0.0).sum())
    any_phi_gt_clean = bool((corrupted_df["phi_u_ds"] > clean_phi).any())

    if phi_nonzero_variant_count == 0:
        if all_u_ds_le_clean:
            direction_note = (
                "Observation only: relative to the clean Beauty bank, every evaluated token-dropout bank reduces U_ds, "
                "but all evaluated values remain above the frozen 0.70 shutoff, so phi(U_ds) stays at 0 throughout "
                "the canonical corruption ladder."
            )
        else:
            direction_note = (
                "Observation only: phi(U_ds) stays at 0 across all evaluated frozen token-dropout banks, so the "
                "frozen gate never opens on the canonical ladder. U_ds shifts only modestly under corruption and is "
                "not strictly monotone against the clean point."
            )
    elif all_phi_ge_clean and all_u_ds_le_clean and any_phi_gt_clean:
        direction_note = (
            "Observation only: relative to the clean Beauty bank, every evaluated token-dropout bank reduces U_ds "
            "and does not lower phi; some corrupted banks cross the frozen shutoff, so the gate opens weakly or "
            "strongly as evidence degrades."
        )
    else:
        direction_note = (
            "Observation only: the phi response to token dropout is mixed across the evaluated frozen banks, so the "
            "report should be read as an empirical scan rather than a monotone law."
        )

    return {
        "clean_phi_u_ds": clean_phi,
        "clean_u_ds_popularity": clean_u_ds,
        "phi_nonzero_variant_count": phi_nonzero_variant_count,
        "all_corrupted_phi_ge_clean": all_phi_ge_clean,
        "all_corrupted_u_ds_le_clean": all_u_ds_le_clean,
        "monotone_phi_over_sorted_levels": monotone_phi,
        "spearman_dropout_rate_vs_phi": spearman_phi,
        "spearman_dropout_rate_vs_u_ds": spearman_u_ds,
        "direction_note": direction_note,
    }


def _write_markdown(report: dict[str, Any], output_path: Path) -> None:
    summary_df = pd.DataFrame(report["summary_rows"])
    lines = [
        "# Beauty Corrupted-Bank Utility Response",
        "",
        "This artifact recomputes the frozen `U_ds` estimator on existing Beauty token-dropout banks and reports the "
        "observed `phi(U_ds)` response. It is observational evidence only and does not justify any frozen-parameter change.",
        "",
        "## Protocol",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Beauty dataset dir: `{report['protocol']['beauty_dataset_dir']}`",
        f"- Corruption dir: `{report['protocol']['corruption_dir']}`",
        f"- Variant selection mode: `{report['protocol']['variant_selection_mode']}`",
        f"- Sample size per bank: `{report['protocol']['sample_size']}`",
        f"- Negatives per sampled transition: `{report['protocol']['negative_count']}`",
        f"- Seed: `{report['protocol']['seed']}`",
        f"- Clean reference summary: `{report['protocol']['clean_summary_csv']}`",
        "",
        "## Observation",
        "",
        f"- Clean Beauty `U_ds`: `{report['observation']['clean_u_ds_popularity']}`",
        f"- Clean Beauty `phi(U_ds)`: `{report['observation']['clean_phi_u_ds']}`",
        f"- Corrupted banks with `phi(U_ds) > 0`: `{report['observation']['phi_nonzero_variant_count']}`",
        f"- All corrupted `phi(U_ds)` values stay at or above clean: `{report['observation']['all_corrupted_phi_ge_clean']}`",
        f"- All corrupted `U_ds` values stay at or below clean: `{report['observation']['all_corrupted_u_ds_le_clean']}`",
        f"- Monotone non-decreasing `phi(U_ds)` over sorted evaluated levels: `{report['observation']['monotone_phi_over_sorted_levels']}`",
        f"- Spearman(dropout_rate, `phi(U_ds)`): `{report['observation']['spearman_dropout_rate_vs_phi']}`",
        f"- Spearman(dropout_rate, `U_ds`): `{report['observation']['spearman_dropout_rate_vs_u_ds']}`",
        f"- Note: {report['observation']['direction_note']}",
        "",
        "## Clean Plus Corrupted Levels",
        "",
        _dataframe_to_markdown(summary_df),
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def build_corrupted_beauty_utility_report(
    *,
    beauty_dataset_dir: Path,
    corruption_dir: Path,
    clean_summary_csv: Path,
    output_dir: Path,
    variants: list[str] | None = None,
    include_all_discovered: bool = False,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    negative_count: int = DEFAULT_NEGATIVE_COUNT,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    beauty_dataset_dir = Path(beauty_dataset_dir).resolve()
    corruption_dir = Path(corruption_dir).resolve()
    clean_summary_csv = Path(clean_summary_csv).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    clean_reference = _load_clean_reference(clean_summary_csv)
    discovered = _discover_token_dropout_variants(corruption_dir)
    if not discovered:
        raise FileNotFoundError(f"no token-dropout corrupted banks found in {corruption_dir}")
    selected_variants, selection_mode = _select_variants(
        discovered,
        explicit_variants=list(variants or []),
        include_all_discovered=include_all_discovered,
    )

    (
        train_split_path,
        train_df,
        sampled_df,
        sampled_popularity_negs,
        sampled_uniform_negs,
        split_hash,
    ) = _build_sample_inputs(
        beauty_dataset_dir=beauty_dataset_dir,
        sample_size=sample_size,
        negative_count=negative_count,
        seed=seed,
    )

    variant_rows: list[dict[str, Any]] = []
    for variant in selected_variants:
        row = _compute_utility_row(
            dataset_name=f"Beauty::{variant.variant_tag}",
            text_bank_path=variant.text_bank_path,
            embeddings_path=variant.embeddings_path,
            train_df=train_df,
            sampled_df=sampled_df,
            sampled_popularity_negs=sampled_popularity_negs,
            sampled_uniform_negs=sampled_uniform_negs,
            negative_count=negative_count,
        )
        dropout_rate = _parse_dropout_rate(variant.variant_tag)
        row.update(
            {
                "level_kind": "corrupted",
                "variant_tag": variant.variant_tag,
                "dropout_rate": dropout_rate,
                "source_text_bank_path": str(variant.text_bank_path),
                "source_embeddings_path": str(variant.embeddings_path),
                "split_hash": split_hash,
                "u_ds_delta_vs_clean": float(row["u_ds_popularity"]) - float(clean_reference["u_ds_popularity"]),
                "phi_delta_vs_clean": float(row["phi_u_ds"]) - float(clean_reference["phi_u_ds"]),
            }
        )
        variant_rows.append(row)

    clean_row = {
        "level_kind": "clean_reference",
        "variant_tag": "clean",
        "dropout_rate": 0.0,
        "u_ds_popularity": float(clean_reference["u_ds_popularity"]),
        "u_ds_uniform": float(clean_reference["u_ds_uniform"]),
        "phi_u_ds": float(clean_reference["phi_u_ds"]),
        "u_ds_delta_vs_clean": 0.0,
        "phi_delta_vs_clean": 0.0,
        "bank_hash": str(clean_reference["bank_hash"]),
        "split_hash": str(clean_reference["split_hash"]),
        "source_text_bank_path": str(beauty_dataset_dir / "text_bank.csv"),
        "source_embeddings_path": str(beauty_dataset_dir / "sentence_t5_xl_item_emb.pt"),
    }

    summary_rows = [clean_row]
    summary_rows.extend(
        {
            "level_kind": row["level_kind"],
            "variant_tag": row["variant_tag"],
            "dropout_rate": row["dropout_rate"],
            "u_ds_popularity": row["u_ds_popularity"],
            "u_ds_uniform": row["u_ds_uniform"],
            "phi_u_ds": row["phi_u_ds"],
            "u_ds_delta_vs_clean": row["u_ds_delta_vs_clean"],
            "phi_delta_vs_clean": row["phi_delta_vs_clean"],
            "usable_row_count": row["usable_row_count"],
            "skipped_row_count": row["skipped_row_count"],
            "bank_hash": row["bank_hash"],
            "split_hash": row["split_hash"],
        }
        for row in variant_rows
    )
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(output_dir / "beauty_corrupted_u_ds_phi_summary.csv", index=False)

    observation = _observation_summary(clean_reference, variant_rows)
    report = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "protocol": {
            "beauty_dataset_dir": str(beauty_dataset_dir),
            "corruption_dir": str(corruption_dir),
            "clean_summary_csv": str(clean_summary_csv),
            "sample_size": int(sample_size),
            "negative_count": int(negative_count),
            "seed": int(seed),
            "variant_selection_mode": selection_mode,
        },
        "clean_reference": clean_reference,
        "variants": variant_rows,
        "summary_rows": summary_rows,
        "observation": observation,
        "train_split_path": str(train_split_path),
    }
    _stable_json_dump(report, output_dir / "beauty_corrupted_u_ds_phi_report.json")
    _write_markdown(report, output_dir / "beauty_corrupted_u_ds_phi_report.md")
    return report


def main() -> None:
    args = parse_args()
    report = build_corrupted_beauty_utility_report(
        beauty_dataset_dir=args.beauty_dataset_dir,
        corruption_dir=args.corruption_dir,
        clean_summary_csv=args.clean_summary_csv,
        output_dir=args.output_dir,
        variants=args.variant,
        include_all_discovered=args.include_all_discovered,
        sample_size=args.sample_size,
        negative_count=args.negative_count,
        seed=args.seed,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
