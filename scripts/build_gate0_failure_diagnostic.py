#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd
import torch


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = REPO_ROOT / "model"
SCRIPT_ROOT = REPO_ROOT / "scripts"
for candidate in (REPO_ROOT, MODEL_ROOT, SCRIPT_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from build_gate0_utilde_report import (
    DEFAULT_DATASETS,
    DEFAULT_OUTPUT_DIR,
    _ensure_supporting_artifacts,
    _load_histories,
    _parse_dataset_args,
    _sha256_paths,
    _stable_json_dump,
)
from text_side import TextSideProposalBuilder


DEFAULT_GATE0_REPORT_JSON = "gate0_u_tilde_report.json"
DEFAULT_SPLITS = ("train", "val", "test")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a component-level follow-up diagnostic for Gate0 failures on production text-side banks."
    )
    parser.add_argument(
        "--dataset",
        action="append",
        default=[],
        help="Dataset mapping in the form NAME=/abs/or/relative/path. Repeat once per dataset.",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for diagnostic outputs")
    parser.add_argument(
        "--gate0-report-json",
        default=None,
        help="Optional existing Gate0 report JSON. Defaults to <output-dir>/gate0_u_tilde_report.json",
    )
    parser.add_argument("--max-users", type=int, default=0, help="Optional cap per split for smoke/debug")
    parser.add_argument("--batch-size", type=int, default=2048)
    parser.add_argument("--g-max", type=float, default=0.5)
    parser.add_argument("--agreement-k", type=float, default=2.0)
    parser.add_argument("--center-embeddings", action="store_true")
    return parser.parse_args()


def _summarize_metric(prefix: str, values: torch.Tensor) -> dict[str, float]:
    values = values.detach().cpu().float()
    quantiles = torch.tensor([0.1, 0.5, 0.9], dtype=torch.float32)
    q10, median, q90 = torch.quantile(values, quantiles).tolist()
    return {
        f"mean_{prefix}": float(values.mean().item()),
        f"median_{prefix}": float(median),
        f"std_{prefix}": float(values.std(unbiased=False).item()),
        f"p10_{prefix}": float(q10),
        f"p90_{prefix}": float(q90),
    }


def _load_gate0_report(gate0_report_json: Path) -> dict[str, object]:
    return json.loads(Path(gate0_report_json).read_text(encoding="utf-8"))


def _dataset_diagnostic_row(
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

    collected: dict[str, list[torch.Tensor]] = {
        "history_length": [],
        "agreement": [],
        "mu_null": [],
        "sigma_null": [],
        "agreement_residual": [],
        "residual_to_sigma": [],
        "completeness": [],
        "history_reliability": [],
        "history_ess": [],
        "history_recency": [],
        "history_stability": [],
        "u_tilde": [],
        "g": [],
    }

    with torch.no_grad():
        for start in range(0, histories.shape[0], batch_size):
            end = min(start + batch_size, histories.shape[0])
            batch_histories = histories[start:end]
            history_lengths = (batch_histories != builder.pad_value).sum(dim=1).clamp_min(1).long()
            context = builder.encode_history_context(batch_histories)
            null_curve = builder._lookup_null_curve(history_lengths)
            if null_curve is None:
                mu_null = torch.zeros_like(context["agreement"])
                sigma_null = torch.ones_like(context["agreement"])
            else:
                mu_null, sigma_null = null_curve

            collected["history_length"].append(history_lengths.detach().cpu().float())
            collected["agreement"].append(context["agreement"].detach().cpu())
            collected["mu_null"].append(mu_null.detach().cpu())
            collected["sigma_null"].append(sigma_null.detach().cpu())
            collected["agreement_residual"].append((context["agreement"] - mu_null).detach().cpu())
            collected["residual_to_sigma"].append(((context["agreement"] - mu_null) / sigma_null.clamp_min(1e-6)).detach().cpu())
            collected["completeness"].append(context["completeness"].detach().cpu())
            collected["history_reliability"].append(context["history_reliability"].detach().cpu())
            collected["history_ess"].append(context["history_ess"].detach().cpu())
            collected["history_recency"].append(context["history_recency"].detach().cpu())
            collected["history_stability"].append(context["history_stability"].detach().cpu())
            collected["u_tilde"].append(context["u_tilde"].detach().cpu())
            collected["g"].append(context["g"].detach().cpu())

    summary: dict[str, object] = {
        "dataset": dataset_name,
        "dataset_dir": str(dataset_dir),
        "user_count": int(histories.shape[0]),
        "item_count": int(len(item_df)),
        "split_counts": split_counts,
        "bank_hash": _sha256_paths(text_bank_path, embeddings_path, null_curve_path),
    }
    for metric_name, tensors in collected.items():
        summary.update(_summarize_metric(metric_name, torch.cat(tensors, dim=0)))
    return summary


def _classify_primary_driver(summary_rows: list[dict[str, object]]) -> tuple[str, str]:
    by_dataset = {row["dataset"]: row for row in summary_rows}
    missing = [name for name in ("ML1M", "Steam", "Beauty") if name not in by_dataset]
    if missing:
        return (
            "mixed_or_other_mismatch",
            f"Cannot compare ML1M against Steam/Beauty because these datasets are missing: {', '.join(missing)}.",
        )

    ml1m = by_dataset["ML1M"]
    steam = by_dataset["Steam"]
    beauty = by_dataset["Beauty"]

    ml1m_residual = float(ml1m["median_agreement_residual"])
    steam_residual = float(steam["median_agreement_residual"])
    beauty_residual = float(beauty["median_agreement_residual"])
    ml1m_sigma = float(ml1m["median_sigma_null"])
    steam_sigma = float(steam["median_sigma_null"])
    beauty_sigma = float(beauty["median_sigma_null"])
    ml1m_ratio = float(ml1m["median_residual_to_sigma"])
    steam_ratio = float(steam["median_residual_to_sigma"])
    beauty_ratio = float(beauty["median_residual_to_sigma"])

    if ml1m_residual > 0.10 and ml1m_residual > max(steam_residual, beauty_residual) + 0.10:
        return (
            "agreement_residual_above_mu_null",
            (
                f"ML1M median(agreement-mu_null)={ml1m_residual:.6f} stays far above Steam={steam_residual:.6f} "
                f"and Beauty={beauty_residual:.6f}, so the dominant failure signal is the residual agreement "
                "still sitting above the matched null baseline."
            ),
        )
    if (
        ml1m_residual > 0.0
        and ml1m_sigma < min(steam_sigma, beauty_sigma) * 0.90
        and ml1m_ratio > max(steam_ratio, beauty_ratio) + 0.75
    ):
        return (
            "null_curve_spread_or_scaling_mismatch",
            (
                f"ML1M median residual={ml1m_residual:.6f} is only mildly positive, but median sigma_null={ml1m_sigma:.6f} "
                f"and residual/sigma={ml1m_ratio:.6f} amplify it well above Steam sigma={steam_sigma:.6f}, "
                f"ratio={steam_ratio:.6f} and Beauty sigma={beauty_sigma:.6f}, ratio={beauty_ratio:.6f}; the main "
                "failure signal is therefore null-curve spread or scaling mismatch rather than a huge raw residual."
            ),
        )
    return (
        "mixed_or_other_mismatch",
        (
            f"ML1M median residual={ml1m_residual:.6f} and sigma_null={ml1m_sigma:.6f} do not isolate a single "
            "driver cleanly; the Gate0 failure likely reflects a mixed calibration mismatch that still needs "
            "repair before retraining."
        ),
    )


def _decision_payload(
    *,
    gate0_report: dict[str, object],
    summary_rows: list[dict[str, object]],
) -> dict[str, object]:
    primary_driver, driver_evidence = _classify_primary_driver(summary_rows)
    gate0_verdict = str(gate0_report.get("gate0_verdict", "unknown"))
    if gate0_verdict == "pass":
        return {
            "primary_driver": primary_driver,
            "driver_evidence": driver_evidence,
            "sprint05_status": "open",
            "recommended_next_path": "resume_main_table",
            "fallback_path": "not_applicable",
            "decision": "Gate0 already passed, so this follow-up does not block reopening SPRINT-05.",
            "inference": "The component diagnostic does not overturn the passed Gate0 verdict.",
        }

    if primary_driver in {"agreement_residual_above_mu_null", "null_curve_spread_or_scaling_mismatch"}:
        recommended_next_path = "calibration_repair_first"
        inference = (
            "Inference from the component medians: the next main-path move should be a calibration repair pass on "
            "the Gate0 signal before any v2 main-table retrain is reopened."
        )
    else:
        recommended_next_path = "claim_downgrade_or_broader_repair"
        inference = (
            "Inference from the mixed diagnostic signature: do not reopen SPRINT-05 on the current path; either "
            "broaden the calibration repair scope or downgrade to the frozen-claim writing path."
        )

    return {
        "primary_driver": primary_driver,
        "driver_evidence": driver_evidence,
        "sprint05_status": "blocked",
        "recommended_next_path": recommended_next_path,
        "fallback_path": "frozen_claim_downgrade_if_schedule_expires",
        "decision": "Gate0 remains failed, so SPRINT-05 stays blocked until the chosen repair or downgrade path is completed.",
        "inference": inference,
    }


def _write_markdown(report: dict[str, object], output_path: Path) -> None:
    summary_df = pd.DataFrame(report["datasets"])
    lines = [
        "# Gate0 Failure Follow-up Diagnostic",
        "",
        f"- Gate0 report JSON: `{report['gate0_report_json']}`",
        f"- Gate0 verdict: `{report['gate0_verdict']}`",
        f"- `SPRINT-05` status: `{report['sprint05_status']}`",
        "",
        "## Gate0 Reasons",
        "",
    ]
    gate0_reasons = report.get("gate0_reasons", [])
    if gate0_reasons:
        lines.extend([f"- {reason}" for reason in gate0_reasons])
    else:
        lines.append("- No explicit Gate0 reasons were provided in the source report.")
    lines.extend(
        [
            "",
            "## Driver",
            "",
            f"- Primary driver: `{report['primary_driver']}`",
            f"- Evidence: {report['driver_evidence']}",
            f"- Decision: {report['decision']}",
            f"- Inference: {report['inference']}",
            f"- Recommended next path: `{report['recommended_next_path']}`",
            f"- Fallback path: `{report['fallback_path']}`",
            "",
            "## Dataset Summary",
            "",
            summary_df.to_markdown(index=False),
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def build_gate0_failure_diagnostic(
    *,
    dataset_dirs: dict[str, Path],
    output_dir: Path | str,
    gate0_report_json: Path | str | None = None,
    max_users: int = 0,
    batch_size: int = 2048,
    g_max: float = 0.5,
    agreement_k: float = 2.0,
    center_embeddings: bool = False,
) -> dict[str, object]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    gate0_report_json = Path(gate0_report_json) if gate0_report_json else output_dir / DEFAULT_GATE0_REPORT_JSON
    gate0_report = _load_gate0_report(gate0_report_json)

    summary_rows = []
    for dataset_name, dataset_dir in dataset_dirs.items():
        summary_rows.append(
            _dataset_diagnostic_row(
                dataset_name=dataset_name,
                dataset_dir=Path(dataset_dir),
                batch_size=batch_size,
                max_users=max_users,
                g_max=g_max,
                agreement_k=agreement_k,
                center_embeddings=center_embeddings,
            )
        )

    decision = _decision_payload(gate0_report=gate0_report, summary_rows=summary_rows)
    report = {
        "gate0_report_json": str(gate0_report_json),
        "gate0_verdict": gate0_report.get("gate0_verdict", "unknown"),
        "gate0_reasons": gate0_report.get("gate0_reasons", []),
        "datasets": summary_rows,
        **decision,
    }

    pd.DataFrame(summary_rows).to_csv(output_dir / "gate0_failure_component_summary.csv", index=False)
    _stable_json_dump(report, output_dir / "gate0_failure_diagnostic.json")
    _write_markdown(report, output_dir / "gate0_failure_diagnostic.md")
    return report


def main() -> None:
    args = parse_args()
    report = build_gate0_failure_diagnostic(
        dataset_dirs=_parse_dataset_args(args.dataset),
        output_dir=Path(args.output_dir),
        gate0_report_json=args.gate0_report_json,
        max_users=args.max_users,
        batch_size=args.batch_size,
        g_max=args.g_max,
        agreement_k=args.agreement_k,
        center_embeddings=args.center_embeddings,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
