#!/usr/bin/env python3

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = REPO_ROOT / "model"
for candidate in (REPO_ROOT, MODEL_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from text_side import phi_from_text_utility


DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "reports" / "data" / "2026-07-02-gate0"
DEFAULT_TEXT_UTILITY_REPORT_JSON = "gate0_text_utility_report.json"
DEFAULT_VERDICT_JSON = "gate0_v2_frozen_verdict.json"
DEFAULT_VERDICT_MD = "gate0_v2_frozen_verdict.md"
DEFAULT_FAMILY_D_MEMO_ZH = "gate0_v2_family_d_downgrade_memo_zh.md"
NON_ML1M_DATASETS = ("Steam", "Beauty", "ATG")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the frozen Gate 0-v2 criterion from the FOLLOWUP-05 text-utility artifact."
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory holding Gate0 artifacts.")
    parser.add_argument(
        "--report-json",
        default=None,
        help="Optional explicit path to gate0_text_utility_report.json. Defaults to <output-dir>/gate0_text_utility_report.json.",
    )
    return parser.parse_args()


def _stable_json_dump(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_report(report_json: Path) -> dict[str, object]:
    return json.loads(Path(report_json).read_text(encoding="utf-8"))


def _build_dataset_rows(report_payload: dict[str, object]) -> list[dict[str, object]]:
    dataset_rows = []
    for raw_row in report_payload.get("datasets", []):
        utility_value = float(raw_row["u_ds_popularity"])
        dataset_rows.append(
            {
                "dataset": str(raw_row["dataset"]),
                "u_ds_popularity": utility_value,
                "phi_u_ds": float(phi_from_text_utility(utility_value)),
                "bank_hash": raw_row.get("bank_hash"),
                "split_hash": raw_row.get("split_hash"),
            }
        )
    return dataset_rows


def _build_conditions(dataset_rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, object]]:
    by_dataset = {str(row["dataset"]): row for row in dataset_rows}
    missing = [name for name in ("ML1M", *NON_ML1M_DATASETS) if name not in by_dataset]
    if missing:
        raise ValueError(f"missing datasets in text utility report: {', '.join(missing)}")

    ranking_desc = sorted(dataset_rows, key=lambda row: float(row["u_ds_popularity"]), reverse=True)
    ranking_names = [str(row["dataset"]) for row in ranking_desc]
    ml1m_u_ds = float(by_dataset["ML1M"]["u_ds_popularity"])
    next_best_other = max(float(by_dataset[name]["u_ds_popularity"]) for name in NON_ML1M_DATASETS)
    condition_1_margin = ml1m_u_ds - next_best_other
    condition_1_passed = ranking_names[0] == "ML1M"

    ml1m_phi = float(by_dataset["ML1M"]["phi_u_ds"])
    condition_2_margin = 0.2 - ml1m_phi
    condition_2_passed = ml1m_phi <= 0.2

    non_ml1m_phi_ge_0_5 = [
        name for name in NON_ML1M_DATASETS if float(by_dataset[name]["phi_u_ds"]) >= 0.5
    ]
    condition_3_count = len(non_ml1m_phi_ge_0_5)
    condition_3_margin = float(condition_3_count - 2)
    condition_3_passed = condition_3_count >= 2

    conditions = [
        {
            "id": "condition_1_ml1m_is_max",
            "label": "Condition 1: ML1M has the maximum U_ds",
            "passed": condition_1_passed,
            "margin": condition_1_margin,
            "detail": (
                f"ranking={ranking_names}; ML1M U_ds={ml1m_u_ds:.6f}; "
                f"next-best non-ML1M U_ds={next_best_other:.6f}"
            ),
        },
        {
            "id": "condition_2_ml1m_phi_lte_0_2",
            "label": "Condition 2: phi(U_ML1M) <= 0.2",
            "passed": condition_2_passed,
            "margin": condition_2_margin,
            "detail": f"phi(U_ML1M)={ml1m_phi:.6f}; threshold=0.200000",
        },
        {
            "id": "condition_3_two_non_ml1m_phi_ge_0_5",
            "label": "Condition 3: at least two of Steam/Beauty/ATG have phi(U_ds) >= 0.5",
            "passed": condition_3_passed,
            "margin": condition_3_margin,
            "detail": (
                f"qualifying_datasets={non_ml1m_phi_ge_0_5}; count={condition_3_count}; "
                "required_count=2"
            ),
        },
    ]
    derived = {
        "ml1m_u_ds": ml1m_u_ds,
        "ml1m_phi": ml1m_phi,
        "u_ds_ranking_desc": ranking_names,
        "non_ml1m_phi_ge_0_5_count": condition_3_count,
        "non_ml1m_phi_ge_0_5_datasets": non_ml1m_phi_ge_0_5,
    }
    return conditions, derived


def _render_markdown(verdict: dict[str, object]) -> str:
    lines = [
        "# Gate 0-v2 Frozen Criterion Verdict",
        "",
        f"- Source report JSON: `{verdict['source_report_json']}`",
        f"- Evaluated at: `{verdict['evaluated_at']}`",
        f"- Verdict: `{'PASSED' if verdict['criterion_pass'] else 'FAILED'}`",
        f"- `SPRINT-05` decision: `{verdict['sprint05_decision']}`",
        "",
        "## Dataset inputs",
        "",
        "| Dataset | U_ds | phi(U_ds) | bank_hash | split_hash |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for row in verdict["datasets"]:
        lines.append(
            "| {dataset} | {u_ds_popularity:.6f} | {phi_u_ds:.6f} | `{bank_hash}` | `{split_hash}` |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Frozen conditions",
            "",
        ]
    )
    for index, condition in enumerate(verdict["conditions"], start=1):
        status = "PASSED" if condition["passed"] else "FAILED"
        lines.extend(
            [
                f"{index}. {condition['label']}: `{status}`",
                f"   - margin: `{float(condition['margin']):.6f}`",
                f"   - detail: {condition['detail']}",
            ]
        )

    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- `criterion_pass`: `{str(bool(verdict['criterion_pass'])).lower()}`",
            f"- `third_gate_repair_round_allowed`: `{str(bool(verdict['third_gate_repair_round_allowed'])).lower()}`",
            f"- Action: {verdict['decision_summary']}",
        ]
    )
    if not verdict["criterion_pass"]:
        lines.append(f"- Family D deadline: `{verdict['family_d_deadline']}`")
    lines.append("")
    return "\n".join(lines)


def _render_family_d_memo_zh(verdict: dict[str, object]) -> str:
    condition_map = {condition["id"]: condition for condition in verdict["conditions"]}
    condition_3 = condition_map["condition_3_two_non_ml1m_phi_ge_0_5"]
    qualifying = ", ".join(verdict["non_ml1m_phi_ge_0_5_datasets"]) or "无"

    lines = [
        "# Gate 0-v2 Family D 降级决策备忘",
        "",
        "## 结论",
        "",
        "冻结的 Gate 0-v2 三条件判据未通过，因此 `SPRINT-05` 不重开，主线进入 Family D claim downgrade 路径。",
        "根据修订规范，这意味着不再进行第三轮门控修复。",
        "",
        "## 三条冻结条件",
        "",
    ]
    for index, condition in enumerate(verdict["conditions"], start=1):
        status = "通过" if condition["passed"] else "失败"
        lines.extend(
            [
                f"{index}. {condition['label']}：{status}",
                f"   - margin = {float(condition['margin']):.6f}",
                f"   - {condition['detail']}",
            ]
        )

    lines.extend(
        [
            "",
            "## 为什么失败",
            "",
            (
                f"第三条要求 Steam/Beauty/ATG 中至少两个数据集满足 phi(U_ds) >= 0.5，"
                f"但本次只有 {qualifying} 满足，实际数量为 {verdict['non_ml1m_phi_ge_0_5_count']}。"
            ),
            (
                "这说明 utility-gated 路线已经成功把 ML1M 的门基本关掉，但没有同时把足够多的"
                " v1 获益数据集推入明显开门区，因此不足以支撑重开四数据集 v2 主表训练。"
            ),
            "",
            "## 对 SPRINT-05 的影响",
            "",
            "- `SPRINT-05` decision: `blocked_family_d_downgrade`",
            "- 不再进行第三轮门控修复",
            "- 后续应按 Family D 路线冻结更弱但诚实的论文主张",
            "",
        ]
    )
    return "\n".join(lines)


def build_gate0_v2_frozen_verdict(
    *,
    output_dir: Path,
    report_json: Path | None = None,
) -> dict[str, object]:
    output_dir = Path(output_dir)
    report_json = Path(report_json) if report_json is not None else output_dir / DEFAULT_TEXT_UTILITY_REPORT_JSON
    report_payload = _load_report(report_json)
    dataset_rows = _build_dataset_rows(report_payload)
    conditions, derived = _build_conditions(dataset_rows)
    criterion_pass = all(bool(condition["passed"]) for condition in conditions)

    if criterion_pass:
        sprint05_decision = "reopen_sprint05"
        decision_summary = "Frozen Gate 0-v2 criterion passed; SPRINT-05 can reopen with the two-factor gate."
        third_gate_repair_round_allowed = True
    else:
        sprint05_decision = "blocked_family_d_downgrade"
        decision_summary = (
            "Frozen Gate 0-v2 criterion failed; keep SPRINT-05 blocked and switch to the Family D claim-downgrade path."
        )
        third_gate_repair_round_allowed = False

    verdict = {
        "criterion_name": "Gate 0-v2 frozen criterion (spec 7.4)",
        "evaluated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_report_json": str(report_json.resolve()),
        "datasets": dataset_rows,
        "conditions": conditions,
        "criterion_pass": criterion_pass,
        "sprint05_decision": sprint05_decision,
        "decision_summary": decision_summary,
        "third_gate_repair_round_allowed": third_gate_repair_round_allowed,
        "family_d_deadline": "2026-07-07" if not criterion_pass else None,
        **derived,
    }

    verdict_json_path = output_dir / DEFAULT_VERDICT_JSON
    verdict_md_path = output_dir / DEFAULT_VERDICT_MD
    _stable_json_dump(verdict, verdict_json_path)
    verdict_md_path.write_text(_render_markdown(verdict), encoding="utf-8")

    family_d_memo_path = output_dir / DEFAULT_FAMILY_D_MEMO_ZH
    if criterion_pass:
        if family_d_memo_path.exists():
            family_d_memo_path.unlink()
    else:
        family_d_memo_path.write_text(_render_family_d_memo_zh(verdict), encoding="utf-8")

    return verdict


def main() -> None:
    args = parse_args()
    verdict = build_gate0_v2_frozen_verdict(
        output_dir=Path(args.output_dir),
        report_json=Path(args.report_json) if args.report_json else None,
    )
    print(json.dumps(verdict, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
