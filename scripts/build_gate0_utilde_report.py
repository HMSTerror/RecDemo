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
SCRIPT_ROOT = REPO_ROOT / "scripts"
for candidate in (REPO_ROOT, MODEL_ROOT, SCRIPT_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from build_agreement_null_curves import build_null_curve_artifact
from text_side import DEFAULT_EMBEDDING_FILENAME, DEFAULT_NULL_CURVE_FILENAME, TEXT_BANK_FILENAME, TextSideProposalBuilder, ensure_text_bank


DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "reports" / "data"
DEFAULT_DATASET_ROOT = REPO_ROOT / "dataset" / "paper_raw_v1"
DEFAULT_DATASETS = ("ML1M", "Steam", "Beauty", "ATG")
DEFAULT_SPLITS = ("train", "val", "test")
GATE0_MEDIAN_ABS_MAX = 0.5
ORIGINAL_HYPOTHESIS = (
    "Length-matched null calibration on production sentence-t5-xl banks should drive ML1M close to the "
    "null point while Steam and Beauty remain above ML1M, so text-evidence-poor regimes auto-fallback "
    "toward the core kernel."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Gate 0 real-user u_tilde diagnostics report from production text-side banks."
    )
    parser.add_argument(
        "--dataset",
        action="append",
        default=[],
        help="Dataset mapping in the form NAME=/abs/or/relative/path. Repeat once per dataset.",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for Gate 0 outputs")
    parser.add_argument("--max-users", type=int, default=0, help="Optional cap per split for smoke/debug")
    parser.add_argument("--batch-size", type=int, default=2048)
    parser.add_argument("--g-max", type=float, default=0.5)
    parser.add_argument("--agreement-k", type=float, default=2.0)
    parser.add_argument("--center-embeddings", action="store_true")
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


def _split_filename(split_name: str) -> str:
    if split_name == "train":
        return "train_data.df"
    if split_name == "val":
        return "val_data.df"
    return "test_data.df"


def _load_histories(dataset_dir: Path, split_names: tuple[str, ...], max_users: int = 0) -> tuple[torch.Tensor, dict[str, int]]:
    split_counts: dict[str, int] = {}
    split_frames: list[pd.DataFrame] = []
    for split_name in split_names:
        split_path = dataset_dir / _split_filename(split_name)
        if not split_path.exists():
            continue
        split_df = pd.read_pickle(split_path)
        if max_users > 0:
            split_df = split_df.iloc[:max_users].copy()
        split_counts[split_name] = int(len(split_df))
        split_frames.append(split_df[["seq"]])
    if not split_frames:
        raise FileNotFoundError(f"no dataset splits found under {dataset_dir}")
    merged = pd.concat(split_frames, ignore_index=True)
    return torch.as_tensor(np.asarray(merged["seq"].tolist()), dtype=torch.long), split_counts


def _ensure_supporting_artifacts(dataset_dir: Path, *, center_embeddings: bool, agreement_k: float) -> tuple[Path, Path, Path]:
    text_bank_path = dataset_dir / TEXT_BANK_FILENAME
    if not text_bank_path.exists():
        text_bank_path = ensure_text_bank(dataset_dir)

    embeddings_path = dataset_dir / DEFAULT_EMBEDDING_FILENAME
    if not embeddings_path.exists():
        raise FileNotFoundError(f"missing embeddings artifact: {embeddings_path}")

    null_curve_path = dataset_dir / DEFAULT_NULL_CURVE_FILENAME
    if not null_curve_path.exists():
        build_null_curve_artifact(
            dataset_dir=dataset_dir,
            embeddings_path=embeddings_path,
            text_bank_path=text_bank_path,
            output_path=null_curve_path,
            center_embeddings=center_embeddings,
            agreement_k=agreement_k,
        )
    return text_bank_path, embeddings_path, null_curve_path


def _summarize_distribution(values: torch.Tensor) -> dict[str, float]:
    values = values.detach().cpu().float()
    quantiles = torch.tensor([0.1, 0.5, 0.9], dtype=torch.float32)
    q10, median, q90 = torch.quantile(values, quantiles).tolist()
    return {
        "mean_u_tilde": float(values.mean().item()),
        "median_u_tilde": float(median),
        "std_u_tilde": float(values.std(unbiased=False).item()),
        "p10_u_tilde": float(q10),
        "p90_u_tilde": float(q90),
        "mean_g": float(values.clamp(0.0, 1.0).mean().item()),
    }


def _dataset_row(
    *,
    dataset_name: str,
    dataset_dir: Path,
    batch_size: int,
    max_users: int,
    g_max: float,
    agreement_k: float,
    center_embeddings: bool,
) -> dict[str, object]:
    text_bank_path, embeddings_path, null_curve_path = _ensure_supporting_artifacts(
        dataset_dir,
        center_embeddings=center_embeddings,
        agreement_k=agreement_k,
    )
    item_df = pd.read_csv(text_bank_path).sort_values("item_id").reset_index(drop=True)
    histories, split_counts = _load_histories(dataset_dir, DEFAULT_SPLITS, max_users=max_users)
    builder = TextSideProposalBuilder.from_files(
        dataset_dir=dataset_dir,
        item_num=len(item_df),
        is_disliked_item=True,
        embeddings_path=embeddings_path,
        text_bank_path=text_bank_path,
        kernel_version="v2",
        g_max=g_max,
        agreement_null_curve_path=null_curve_path,
        agreement_k=agreement_k,
        center_embeddings=center_embeddings,
    )
    builder.eval()

    u_tilde_batches: list[torch.Tensor] = []
    g_batches: list[torch.Tensor] = []
    with torch.no_grad():
        for start in range(0, histories.shape[0], batch_size):
            end = min(start + batch_size, histories.shape[0])
            context = builder.encode_history_context(histories[start:end])
            u_tilde_batches.append(context["u_tilde"].detach().cpu())
            g_batches.append(context["g"].detach().cpu())

    u_tilde = torch.cat(u_tilde_batches, dim=0)
    g = torch.cat(g_batches, dim=0)
    summary = _summarize_distribution(u_tilde)
    summary["mean_g"] = float(g.mean().item())

    return {
        "dataset": dataset_name,
        "dataset_dir": str(dataset_dir),
        "user_count": int(histories.shape[0]),
        "item_count": int(len(item_df)),
        "split_counts": split_counts,
        "bank_hash": _sha256_paths(text_bank_path, embeddings_path, null_curve_path),
        **summary,
    }


def _gate0_verdict(summary_rows: list[dict[str, object]]) -> tuple[str, list[str]]:
    by_dataset = {row["dataset"]: row for row in summary_rows}
    missing = [name for name in ("ML1M", "Steam", "Beauty") if name not in by_dataset]
    if missing:
        return "fail", [f"missing datasets for Gate 0 criterion: {', '.join(missing)}"]

    ml1m_median = float(by_dataset["ML1M"]["median_u_tilde"])
    steam_median = float(by_dataset["Steam"]["median_u_tilde"])
    beauty_median = float(by_dataset["Beauty"]["median_u_tilde"])

    reasons = []
    if abs(ml1m_median) >= GATE0_MEDIAN_ABS_MAX:
        reasons.append(
            f"|median_u_tilde(ML1M)|={abs(ml1m_median):.6f} exceeds {GATE0_MEDIAN_ABS_MAX:.2f}"
        )
    if steam_median <= ml1m_median:
        reasons.append(
            f"median_u_tilde(Steam)={steam_median:.6f} is not greater than ML1M={ml1m_median:.6f}"
        )
    if beauty_median <= ml1m_median:
        reasons.append(
            f"median_u_tilde(Beauty)={beauty_median:.6f} is not greater than ML1M={ml1m_median:.6f}"
        )
    return ("pass" if not reasons else "fail"), reasons


def _gate0_decision_payload(
    *,
    verdict: str,
    summary_rows: list[dict[str, object]],
) -> dict[str, object]:
    by_dataset = {row["dataset"]: row for row in summary_rows}
    ml1m_median = float(by_dataset["ML1M"]["median_u_tilde"])
    steam_median = float(by_dataset["Steam"]["median_u_tilde"])
    beauty_median = float(by_dataset["Beauty"]["median_u_tilde"])
    if verdict == "pass":
        return {
            "sprint05_status": "open",
            "main_table_retrains_blocked": False,
            "decision": (
                "Gate 0 passed on the production sentence-t5-xl banks, so this gate no longer blocks "
                "SPRINT-05 main-table retrains."
            ),
            "original_hypothesis": ORIGINAL_HYPOTHESIS,
            "revised_hypothesis": (
                "No hypothesis revision is required: the production-bank medians remain directionally "
                "consistent with the ML1M-near-null prediction."
            ),
            "next_step": "SPRINT-05 may proceed once the already-passed SPRINT-03 equivalence evidence is carried forward.",
        }
    return {
        "sprint05_status": "blocked",
        "main_table_retrains_blocked": True,
        "decision": "Gate 0 failed on the production sentence-t5-xl banks; keep SPRINT-05 main-table retrains blocked.",
        "original_hypothesis": ORIGINAL_HYPOTHESIS,
        "revised_hypothesis": (
            "Length-matched null calibration alone does not drive ML1M near the null point on the production "
            "sentence-t5-xl banks. Instead ML1M remains strongly positive "
            f"(median_u_tilde={ml1m_median:.6f}) and sits above Steam ({steam_median:.6f}) and Beauty "
            f"({beauty_median:.6f}). The calibrated-agreement signal is therefore not yet a reliable "
            "zero-information detector for ML1M, so the main path must stay on calibration/claim revision "
            "before any v2 main-table retrains."
        ),
        "next_step": "Keep SPRINT-05 blocked and revise the calibration or claim path before any v2 main-table retrain launch.",
    }


def _write_markdown(report: dict, output_path: Path) -> None:
    summary_df = pd.DataFrame(report["datasets"])
    lines = [
        "# Gate 0 u_tilde Diagnostics",
        "",
        f"Verdict: `{report['gate0_verdict']}`",
        "",
        "Criterion:",
        f"- `abs(median_u_tilde(ML1M)) < {GATE0_MEDIAN_ABS_MAX}`",
        "- `median_u_tilde(Steam) > median_u_tilde(ML1M)`",
        "- `median_u_tilde(Beauty) > median_u_tilde(ML1M)`",
        "",
        "## Decision",
        "",
        f"- `SPRINT-05` main-table retrains: `{report['sprint05_status']}`",
        f"- {report['decision']}",
        "",
        "## Hypothesis",
        "",
        f"- Original: {report['original_hypothesis']}",
        f"- Revised: {report['revised_hypothesis']}",
        "",
        "## Dataset Summary",
        "",
        summary_df.to_markdown(index=False),
        "",
    ]
    if report["gate0_reasons"]:
        lines.extend(["## Reasons", ""])
        lines.extend([f"- {reason}" for reason in report["gate0_reasons"]])
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def build_gate0_report(
    *,
    dataset_dirs: dict[str, Path],
    output_dir: Path | str,
    max_users: int = 0,
    batch_size: int = 2048,
    g_max: float = 0.5,
    agreement_k: float = 2.0,
    center_embeddings: bool = False,
) -> dict[str, object]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    for dataset_name, dataset_dir in dataset_dirs.items():
        summary_rows.append(
            _dataset_row(
                dataset_name=dataset_name,
                dataset_dir=Path(dataset_dir),
                batch_size=batch_size,
                max_users=max_users,
                g_max=g_max,
                agreement_k=agreement_k,
                center_embeddings=center_embeddings,
            )
        )

    verdict, reasons = _gate0_verdict(summary_rows)
    decision_payload = _gate0_decision_payload(verdict=verdict, summary_rows=summary_rows)
    report = {
        "gate0_verdict": verdict,
        "gate0_reasons": reasons,
        "criterion": {
            "ml1m_abs_median_max": GATE0_MEDIAN_ABS_MAX,
            "steam_median_gt_ml1m": True,
            "beauty_median_gt_ml1m": True,
        },
        "datasets": summary_rows,
        **decision_payload,
    }

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(output_dir / "gate0_u_tilde_summary.csv", index=False)
    _stable_json_dump(report, output_dir / "gate0_u_tilde_report.json")
    _write_markdown(report, output_dir / "gate0_u_tilde_report.md")
    return report


def main() -> None:
    args = parse_args()
    report = build_gate0_report(
        dataset_dirs=_parse_dataset_args(args.dataset),
        output_dir=Path(args.output_dir),
        max_users=args.max_users,
        batch_size=args.batch_size,
        g_max=args.g_max,
        agreement_k=args.agreement_k,
        center_embeddings=args.center_embeddings,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
