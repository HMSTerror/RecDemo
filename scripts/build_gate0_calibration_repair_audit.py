#!/usr/bin/env python3

from __future__ import annotations

import argparse
import itertools
import json
import os
from pathlib import Path
import sys

import pandas as pd
import torch


REPO_ROOT = Path(os.environ["RECDEMO_REPO_ROOT"]).resolve() if os.environ.get("RECDEMO_REPO_ROOT") else Path(__file__).resolve().parents[1]
MODEL_ROOT = REPO_ROOT / "model"
SCRIPT_ROOT = REPO_ROOT / "scripts"
for candidate in (REPO_ROOT, MODEL_ROOT, SCRIPT_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from build_gate0_utilde_report import (  # noqa: E402
    DEFAULT_OUTPUT_DIR,
    _ensure_supporting_artifacts,
    _load_histories,
    _parse_dataset_args,
    _sha256_paths,
    _stable_json_dump,
)
from text_side import TextSideProposalBuilder  # noqa: E402


DEFAULT_GATE0_REPORT_JSON = "gate0_u_tilde_report.json"
DEFAULT_SPLITS = ("train", "val", "test")
DEFAULT_K_VALUES = (2.0, 2.5, 3.0, 4.0)
DEFAULT_SIGMA_SCALES = (1.0, 1.25, 1.5, 2.0)
DEFAULT_SIGMA_FLOORS = (0.0, 0.0045, 0.0050, 0.0055, 0.0060, 0.0070)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit simple global null-curve spread/scaling repair candidates on the existing Gate0 production-bank path."
        )
    )
    parser.add_argument(
        "--dataset",
        action="append",
        default=[],
        help="Dataset mapping in the form NAME=/abs/or/relative/path. Repeat once per dataset.",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for audit outputs")
    parser.add_argument(
        "--gate0-report-json",
        default=None,
        help="Optional existing Gate0 report JSON. Defaults to <output-dir>/gate0_u_tilde_report.json",
    )
    parser.add_argument("--max-users", type=int, default=0, help="Optional cap per split for smoke/debug")
    parser.add_argument("--batch-size", type=int, default=2048)
    parser.add_argument("--g-max", type=float, default=0.5)
    parser.add_argument("--agreement-k", type=float, default=2.0, help="Baseline agreement_k used by the current Gate0")
    parser.add_argument(
        "--k-values",
        default=",".join(str(value) for value in DEFAULT_K_VALUES),
        help="Comma-separated sweep of repaired agreement_k values.",
    )
    parser.add_argument(
        "--sigma-scales",
        default=",".join(str(value) for value in DEFAULT_SIGMA_SCALES),
        help="Comma-separated sweep of multiplicative sigma scaling factors.",
    )
    parser.add_argument(
        "--sigma-floors",
        default=",".join(str(value) for value in DEFAULT_SIGMA_FLOORS),
        help="Comma-separated sweep of global sigma floor values.",
    )
    parser.add_argument("--center-embeddings", action="store_true")
    return parser.parse_args()


def _parse_float_list(raw: str) -> tuple[float, ...]:
    values = []
    for chunk in raw.split(","):
        cleaned = chunk.strip()
        if not cleaned:
            continue
        values.append(float(cleaned))
    if not values:
        raise ValueError("expected at least one float value")
    return tuple(values)


def _load_gate0_report(gate0_report_json: Path) -> dict[str, object]:
    return json.loads(Path(gate0_report_json).read_text(encoding="utf-8"))


def _median(values: torch.Tensor) -> float:
    return float(values.detach().cpu().float().median().item())


def _collect_dataset_components(
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

    residual_chunks: list[torch.Tensor] = []
    sigma_chunks: list[torch.Tensor] = []
    baseline_u_chunks: list[torch.Tensor] = []
    baseline_g_chunks: list[torch.Tensor] = []

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

            residual_chunks.append((context["agreement"] - mu_null).detach().cpu().float())
            sigma_chunks.append(sigma_null.detach().cpu().float().clamp_min(1e-6))
            baseline_u_chunks.append(context["u_tilde"].detach().cpu().float())
            baseline_g_chunks.append(context["g"].detach().cpu().float())

    residual = torch.cat(residual_chunks, dim=0)
    sigma = torch.cat(sigma_chunks, dim=0)
    baseline_u = torch.cat(baseline_u_chunks, dim=0)
    baseline_g = torch.cat(baseline_g_chunks, dim=0)
    return {
        "dataset": dataset_name,
        "dataset_dir": str(dataset_dir),
        "user_count": int(histories.shape[0]),
        "item_count": int(len(item_df)),
        "split_counts": split_counts,
        "bank_hash": _sha256_paths(text_bank_path, embeddings_path, null_curve_path),
        "baseline_median_residual": _median(residual),
        "baseline_median_sigma_null": _median(sigma),
        "baseline_median_u_tilde": _median(baseline_u),
        "baseline_median_g": _median(baseline_g),
        "residual": residual,
        "sigma": sigma,
    }


def _candidate_family(*, agreement_k: float, sigma_scale: float, sigma_floor: float, baseline_k: float) -> str:
    tags = []
    if abs(agreement_k - baseline_k) > 1e-9:
        tags.append("k")
    if abs(sigma_scale - 1.0) > 1e-9:
        tags.append("sigma_scale")
    if sigma_floor > 0.0:
        tags.append("sigma_floor")
    return "+".join(tags) if tags else "baseline"


def _candidate_id(*, agreement_k: float, sigma_scale: float, sigma_floor: float) -> str:
    return f"k{agreement_k:g}_scale{sigma_scale:g}_floor{sigma_floor:g}"


def _evaluate_candidate_row(
    *,
    dataset_components: dict[str, dict[str, object]],
    agreement_k: float,
    sigma_scale: float,
    sigma_floor: float,
    g_max: float,
    baseline_k: float,
) -> dict[str, object]:
    row: dict[str, object] = {
        "candidate_id": _candidate_id(
            agreement_k=agreement_k,
            sigma_scale=sigma_scale,
            sigma_floor=sigma_floor,
        ),
        "family": _candidate_family(
            agreement_k=agreement_k,
            sigma_scale=sigma_scale,
            sigma_floor=sigma_floor,
            baseline_k=baseline_k,
        ),
        "agreement_k": float(agreement_k),
        "sigma_scale": float(sigma_scale),
        "sigma_floor": float(sigma_floor),
    }

    for dataset_name, summary in dataset_components.items():
        slug = dataset_name.lower()
        residual = summary["residual"]
        sigma = summary["sigma"]
        effective_sigma = (sigma * float(sigma_scale)).clamp_min(max(float(sigma_floor), 1e-6))
        repaired_u_tilde = residual / (float(agreement_k) * effective_sigma)
        repaired_g = float(g_max) * repaired_u_tilde.clamp(0.0, 1.0)
        row[f"{slug}_median_u_tilde"] = _median(repaired_u_tilde)
        row[f"{slug}_median_g"] = _median(repaired_g)

    ml1m = float(row["ml1m_median_u_tilde"])
    steam = float(row["steam_median_u_tilde"])
    beauty = float(row["beauty_median_u_tilde"])
    row["ml1m_abs_margin"] = 0.5 - abs(ml1m)
    row["steam_order_margin"] = steam - ml1m
    row["beauty_order_margin"] = beauty - ml1m
    row["gate0_min_margin"] = min(
        float(row["ml1m_abs_margin"]),
        float(row["steam_order_margin"]),
        float(row["beauty_order_margin"]),
    )
    row["gate0_pass"] = bool(
        float(row["ml1m_abs_margin"]) > 0.0
        and float(row["steam_order_margin"]) > 0.0
        and float(row["beauty_order_margin"]) > 0.0
    )
    return row


def _sorted_candidate_rows(candidate_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        candidate_rows,
        key=lambda row: (bool(row["gate0_pass"]), float(row["gate0_min_margin"])),
        reverse=True,
    )


def _build_decision(
    *,
    gate0_report: dict[str, object],
    dataset_components: dict[str, dict[str, object]],
    candidate_rows: list[dict[str, object]],
) -> dict[str, object]:
    sorted_rows = _sorted_candidate_rows(candidate_rows)
    best_candidate = sorted_rows[0]
    passing_candidates = [row for row in sorted_rows if bool(row["gate0_pass"])]
    max_ml1m_margin = max(float(row["ml1m_abs_margin"]) for row in candidate_rows)
    max_steam_margin = max(float(row["steam_order_margin"]) for row in candidate_rows)
    max_beauty_margin = max(float(row["beauty_order_margin"]) for row in candidate_rows)

    baseline_by_dataset = {
        name: {
            "dataset_dir": summary["dataset_dir"],
            "user_count": summary["user_count"],
            "item_count": summary["item_count"],
            "split_counts": summary["split_counts"],
            "bank_hash": summary["bank_hash"],
            "baseline_median_residual": summary["baseline_median_residual"],
            "baseline_median_sigma_null": summary["baseline_median_sigma_null"],
            "baseline_median_u_tilde": summary["baseline_median_u_tilde"],
            "baseline_median_g": summary["baseline_median_g"],
        }
        for name, summary in dataset_components.items()
    }

    if passing_candidates:
        best_passing = passing_candidates[0]
        return {
            "gate0_verdict": gate0_report.get("gate0_verdict", "unknown"),
            "gate0_reasons": gate0_report.get("gate0_reasons", []),
            "sprint05_status": "blocked",
            "decision": (
                "At least one audited global repair candidate directionally satisfies the Gate0 inequalities, "
                "but SPRINT-05 still stays blocked until that repair is implemented on the actual pipeline and "
                "Gate0 is rerun on production banks."
            ),
            "recommended_next_path": "implement_best_repair_and_rerun_gate0",
            "inference": (
                f"Best passing candidate `{best_passing['candidate_id']}` achieves min margin "
                f"{float(best_passing['gate0_min_margin']):.6f}; this is enough to justify a concrete repair "
                "implementation plus a fresh Gate0 rerun, not a direct reopen of main-table retraining."
            ),
            "candidate_count": len(candidate_rows),
            "passing_candidate_count": len(passing_candidates),
            "best_candidate": best_candidate,
            "best_passing_candidate": best_passing,
            "baseline_datasets": baseline_by_dataset,
        }

    if max_steam_margin <= 0.0 or max_beauty_margin <= 0.0:
        repair_limit = "ordering_never_recovers_under_global_repairs"
        extra = (
            f"Steam max order margin={max_steam_margin:.6f}, Beauty max order margin={max_beauty_margin:.6f}; "
            "simple global spread/scaling repairs never flip the ML1M ordering gate."
        )
    elif max_ml1m_margin <= 0.0:
        repair_limit = "ml1m_never_reaches_null_threshold_under_global_repairs"
        extra = f"Best ML1M threshold margin={max_ml1m_margin:.6f}; even the best audited candidate leaves |median_u_tilde(ML1M)| above 0.5."
    else:
        repair_limit = "mixed_global_repair_failure"
        extra = (
            f"No single audited candidate clears all three margins simultaneously; best candidate "
            f"`{best_candidate['candidate_id']}` stops at min margin {float(best_candidate['gate0_min_margin']):.6f}."
        )

    return {
        "gate0_verdict": gate0_report.get("gate0_verdict", "unknown"),
        "gate0_reasons": gate0_report.get("gate0_reasons", []),
        "sprint05_status": "blocked",
        "decision": (
            "No audited global k/sigma_scale/sigma_floor repair candidate directionally passes Gate0 on the current "
            "production-bank path, so SPRINT-05 must remain blocked."
        ),
        "recommended_next_path": "downgrade_claim_or_design_deeper_repair",
        "inference": extra,
        "repair_limit": repair_limit,
        "candidate_count": len(candidate_rows),
        "passing_candidate_count": 0,
        "best_candidate": best_candidate,
        "best_passing_candidate": None,
        "baseline_datasets": baseline_by_dataset,
    }


def _write_markdown(report: dict[str, object], output_path: Path) -> None:
    candidates_df = pd.DataFrame(report["candidates"])
    top_candidates = candidates_df.sort_values(
        by=["gate0_pass", "gate0_min_margin"],
        ascending=[False, False],
    ).head(12)
    baseline_df = pd.DataFrame(
        [
            {"dataset": dataset_name, **summary}
            for dataset_name, summary in report["baseline_datasets"].items()
        ]
    )
    lines = [
        "# Gate0 Calibration Repair Audit",
        "",
        f"- Gate0 report JSON: `{report['gate0_report_json']}`",
        f"- Gate0 verdict: `{report['gate0_verdict']}`",
        f"- `SPRINT-05` status: `{report['sprint05_status']}`",
        f"- Candidate count: `{report['candidate_count']}`",
        f"- Passing candidate count: `{report['passing_candidate_count']}`",
        "",
        "## Gate0 Reasons",
        "",
    ]
    gate0_reasons = report.get("gate0_reasons", [])
    if gate0_reasons:
        lines.extend([f"- {reason}" for reason in gate0_reasons])
    else:
        lines.append("- No explicit Gate0 reasons were provided in the source report.")

    best_candidate = report["best_candidate"]
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- Decision: {report['decision']}",
            f"- Recommended next path: `{report['recommended_next_path']}`",
            f"- Inference: {report['inference']}",
            "",
            "## Best Candidate",
            "",
            f"- Candidate id: `{best_candidate['candidate_id']}`",
            f"- Family: `{best_candidate['family']}`",
            f"- agreement_k: `{best_candidate['agreement_k']}`",
            f"- sigma_scale: `{best_candidate['sigma_scale']}`",
            f"- sigma_floor: `{best_candidate['sigma_floor']}`",
            f"- ML1M median_u_tilde: `{best_candidate['ml1m_median_u_tilde']:.6f}`",
            f"- Steam median_u_tilde: `{best_candidate['steam_median_u_tilde']:.6f}`",
            f"- Beauty median_u_tilde: `{best_candidate['beauty_median_u_tilde']:.6f}`",
            f"- Gate0 pass: `{best_candidate['gate0_pass']}`",
            f"- Gate0 min margin: `{best_candidate['gate0_min_margin']:.6f}`",
            "",
            "## Baseline Dataset Summary",
            "",
            baseline_df.to_markdown(index=False),
            "",
            "## Top Candidates",
            "",
            top_candidates.to_markdown(index=False),
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def build_gate0_calibration_repair_audit(
    *,
    dataset_dirs: dict[str, Path],
    output_dir: Path | str,
    gate0_report_json: Path | str | None = None,
    max_users: int = 0,
    batch_size: int = 2048,
    g_max: float = 0.5,
    agreement_k: float = 2.0,
    k_values: tuple[float, ...] = DEFAULT_K_VALUES,
    sigma_scales: tuple[float, ...] = DEFAULT_SIGMA_SCALES,
    sigma_floors: tuple[float, ...] = DEFAULT_SIGMA_FLOORS,
    center_embeddings: bool = False,
) -> dict[str, object]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    gate0_report_json = Path(gate0_report_json) if gate0_report_json else output_dir / DEFAULT_GATE0_REPORT_JSON
    gate0_report = _load_gate0_report(gate0_report_json)

    dataset_components = {
        dataset_name: _collect_dataset_components(
            dataset_name=dataset_name,
            dataset_dir=Path(dataset_dir),
            batch_size=batch_size,
            max_users=max_users,
            g_max=g_max,
            agreement_k=agreement_k,
            center_embeddings=center_embeddings,
        )
        for dataset_name, dataset_dir in dataset_dirs.items()
    }

    candidate_rows = []
    seen_candidate_ids: set[str] = set()
    for repaired_k, sigma_scale, sigma_floor in itertools.product(k_values, sigma_scales, sigma_floors):
        candidate_row = _evaluate_candidate_row(
            dataset_components=dataset_components,
            agreement_k=float(repaired_k),
            sigma_scale=float(sigma_scale),
            sigma_floor=float(sigma_floor),
            g_max=g_max,
            baseline_k=agreement_k,
        )
        candidate_id = str(candidate_row["candidate_id"])
        if candidate_id in seen_candidate_ids:
            continue
        seen_candidate_ids.add(candidate_id)
        candidate_rows.append(candidate_row)

    decision = _build_decision(
        gate0_report=gate0_report,
        dataset_components=dataset_components,
        candidate_rows=candidate_rows,
    )
    sorted_candidates = _sorted_candidate_rows(candidate_rows)
    report = {
        "gate0_report_json": str(gate0_report_json),
        "candidates": sorted_candidates,
        **decision,
    }

    pd.DataFrame(sorted_candidates).to_csv(output_dir / "gate0_calibration_repair_candidates.csv", index=False)
    _stable_json_dump(report, output_dir / "gate0_calibration_repair_audit.json")
    _write_markdown(report, output_dir / "gate0_calibration_repair_audit.md")
    return report


def main() -> None:
    args = parse_args()
    report = build_gate0_calibration_repair_audit(
        dataset_dirs=_parse_dataset_args(args.dataset),
        output_dir=Path(args.output_dir),
        gate0_report_json=args.gate0_report_json,
        max_users=args.max_users,
        batch_size=args.batch_size,
        g_max=args.g_max,
        agreement_k=args.agreement_k,
        k_values=_parse_float_list(args.k_values),
        sigma_scales=_parse_float_list(args.sigma_scales),
        sigma_floors=_parse_float_list(args.sigma_floors),
        center_embeddings=args.center_embeddings,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
