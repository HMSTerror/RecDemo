import csv
import json
import logging
from pathlib import Path
from typing import Optional


def _get_runtime_dataset_cfg(cfg):
    dataset_name = str(cfg.training.data)
    dataset_cfg = getattr(cfg.data, dataset_name)
    return dataset_name, dataset_cfg


def _read_protocol_item_num(dataset_dir: Path) -> Optional[int]:
    protocol_path = dataset_dir / "protocol.json"
    if not protocol_path.exists():
        return None

    payload = json.loads(protocol_path.read_text(encoding="utf-8"))
    item_num = payload.get("counts", {}).get("item_num")
    if item_num is None:
        return None
    return int(item_num)


def _read_item_mapping_count(dataset_dir: Path) -> Optional[int]:
    mapping_path = dataset_dir / "item_mapping.csv"
    if not mapping_path.exists():
        return None

    with mapping_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            next(reader)
        except StopIteration:
            return 0
        return sum(1 for _ in reader)


def infer_runtime_item_num(dataset_dir: str | Path) -> Optional[int]:
    dataset_dir = Path(dataset_dir)
    for reader in (_read_protocol_item_num, _read_item_mapping_count):
        item_num = reader(dataset_dir)
        if item_num is not None:
            return item_num
    return None


def reconcile_runtime_dataset_config(cfg) -> Optional[int]:
    dataset_name, dataset_cfg = _get_runtime_dataset_cfg(cfg)
    resolved_item_num = infer_runtime_item_num(dataset_cfg.path)
    if resolved_item_num is None:
        return None

    configured_item_num = int(dataset_cfg.item_num)
    if configured_item_num != resolved_item_num:
        logging.warning(
            "runtime dataset item_num mismatch for %s: config=%s resolved=%s path=%s; using resolved value",
            dataset_name,
            configured_item_num,
            resolved_item_num,
            dataset_cfg.path,
        )
        dataset_cfg.item_num = resolved_item_num
    return resolved_item_num
