from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .common import sha256_file


EVALUATOR_VERSION = "e0_full_tail_v2"
SELECTOR_VERSION = "validation-ndcg10-rowweighted-v1"
CANDIDATE_POLICY = "all_mapped_real_catalog_items_exactly_once"


@dataclass(frozen=True)
class FrozenProtocolContract:
    dataset: str
    item_count: int
    expected_rows: dict[str, int]
    padding_item_id: int | None
    pseudo_item_id: int | None
    protocol_sha256: str
    evaluator_version: str = EVALUATOR_VERSION
    selector_version: str = SELECTOR_VERSION
    candidate_policy: str = CANDIDATE_POLICY


def load_frozen_protocol(dataset_dir: Path) -> FrozenProtocolContract:
    dataset_dir = Path(dataset_dir)
    protocol_path = dataset_dir / "protocol.json"
    if not protocol_path.is_file():
        raise FileNotFoundError(f"missing frozen protocol: {protocol_path}")
    payload = json.loads(protocol_path.read_text(encoding="utf-8"))
    counts = payload.get("counts")
    if not isinstance(counts, dict):
        raise ValueError("protocol counts are required")
    dataset = str(payload.get("dataset", dataset_dir.name))
    item_count = int(counts.get("item_num", -1))
    if item_count <= 0:
        raise ValueError("protocol item_num must be positive")
    expected_rows: dict[str, int] = {}
    for split in ("train", "val", "test"):
        key = f"{split}_rows"
        value = int(counts.get(key, -1))
        if value < 0:
            raise ValueError(f"protocol missing nonnegative {key}")
        expected_rows[split] = value
    return FrozenProtocolContract(
        dataset=dataset,
        item_count=item_count,
        expected_rows=expected_rows,
        padding_item_id=payload.get("padding_item_id"),
        pseudo_item_id=payload.get("pseudo_item_id"),
        protocol_sha256=sha256_file(protocol_path),
    )


def aggregate_row_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    if not rows:
        raise ValueError("metric rows cannot be empty")
    total_rows = 0
    sums: dict[str, float] = {}
    for row in rows:
        count = int(row.get("rows", 0))
        if count <= 0:
            raise ValueError("every metric row must have positive rows")
        total_rows += count
        for key, value in row.items():
            if key == "rows":
                continue
            numeric = float(value)
            if numeric != numeric or numeric in (float("inf"), float("-inf")):
                raise ValueError(f"non-finite metric: {key}")
            sums[key] = sums.get(key, 0.0) + numeric * count
    return {key: value / total_rows for key, value in sums.items()}


def select_validation_checkpoint(candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not candidates:
        raise ValueError("checkpoint candidates cannot be empty")
    for candidate in candidates:
        forbidden = [key for key in candidate if str(key).casefold().startswith("test")]
        if forbidden:
            raise ValueError(f"test metric cannot be used by validation selector: {forbidden}")
        if "validation_ndcg10" not in candidate:
            raise ValueError("validation_ndcg10 is required for every checkpoint candidate")
    selected = max(enumerate(candidates), key=lambda pair: (float(pair[1]["validation_ndcg10"]), -pair[0]))[1]
    result = dict(selected)
    result["selector_version"] = SELECTOR_VERSION
    result["selector_metric"] = "validation_ndcg10"
    return result


def validate_evaluated_rows(contract: FrozenProtocolContract, split: str, evaluated_rows: int) -> None:
    if split not in contract.expected_rows:
        raise ValueError(f"unknown split: {split}")
    if int(evaluated_rows) != contract.expected_rows[split]:
        raise ValueError(
            f"tail-complete row mismatch for {split}: expected {contract.expected_rows[split]}, got {evaluated_rows}"
        )


def evaluation_metadata(contract: FrozenProtocolContract, *, split: str, evaluated_rows: int, eval_seed: int) -> dict[str, Any]:
    validate_evaluated_rows(contract, split, evaluated_rows)
    if int(eval_seed) != 100:
        raise ValueError("new queue evaluation must use eval_seed=100")
    return {
        "evaluator_version": contract.evaluator_version,
        "selector_version": contract.selector_version,
        "candidate_policy": contract.candidate_policy,
        "split": split,
        "expected_rows": contract.expected_rows[split],
        "evaluated_rows": int(evaluated_rows),
        "eval_seed": int(eval_seed),
        "protocol_sha256": contract.protocol_sha256,
        "padding_item_id": contract.padding_item_id,
        "pseudo_item_id": contract.pseudo_item_id,
    }

