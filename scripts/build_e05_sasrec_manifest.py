#!/usr/bin/env python3
"""Build an immutable four-domain E5 SASRec manifest without launching training."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .run_sasrec import DATASETS, EVALUATOR_VERSION, SELECTOR_VERSION, SPLIT_FILES, canonical_hash, load_protocol, sha256_file, sha256_named_files, write_json
except ImportError:  # direct `python scripts/build_e05_sasrec_manifest.py`
    from run_sasrec import DATASETS, EVALUATOR_VERSION, SELECTOR_VERSION, SPLIT_FILES, canonical_hash, load_protocol, sha256_file, sha256_named_files, write_json


CONFIG = {
    "model": "SASRec",
    "seed": 100,
    "hidden_size": 64,
    "num_heads": 2,
    "num_layers": 2,
    "dropout": 0.2,
    "epochs": 10,
    "batch_size": 512,
    "eval_batch_size": 1024,
    "learning_rate": 1e-3,
    "weight_decay": 0.0,
    "early_stop_patience": 2,
    "early_stop_min_delta": 0.0,
    "evaluator_version": EVALUATOR_VERSION,
    "selector_version": SELECTOR_VERSION,
}


def _file_sha256(path: Path) -> str:
    return sha256_file(path)


def _source_manifest(source_root: Path, files: list[str]) -> tuple[dict[str, str], str]:
    hashes: dict[str, str] = {}
    for relative in files:
        path = source_root / relative
        if not path.is_file():
            raise FileNotFoundError(f"missing immutable source file: {path}")
        hashes[relative] = _file_sha256(path)
    return hashes, canonical_hash(hashes)


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    queue_root = Path(args.queue_root).resolve()
    source_root = Path(args.source_root).resolve()
    dataset_root = Path(args.dataset_root).resolve()
    if queue_root.exists():
        raise FileExistsError(f"E5 queue root must be new: {queue_root}")
    if not source_root.is_dir():
        raise FileNotFoundError(f"missing immutable source root: {source_root}")
    ledger_path = Path(args.ledger_path).resolve()
    if not ledger_path.is_file():
        raise FileNotFoundError(f"missing ledger: {ledger_path}")
    source_files = ["scripts/run_sasrec.py", "scripts/build_e05_sasrec_manifest.py", "scripts/run_e05_sasrec_queue.py"]
    source_hashes, source_manifest_sha256 = _source_manifest(source_root, source_files)
    ledger_sha256 = _file_sha256(ledger_path)
    queue_root.mkdir(parents=True, exist_ok=False)
    tasks: list[dict[str, Any]] = []
    dataset_records: dict[str, Any] = {}
    for dataset in DATASETS:
        dataset_dir = dataset_root / dataset
        protocol = load_protocol(dataset_dir)
        if protocol.get("dataset") != dataset:
            raise ValueError(f"dataset directory/protocol mismatch: {dataset_dir}")
        split_sha256 = sha256_named_files(dataset_dir, SPLIT_FILES)
        config = dict(CONFIG)
        config["dataset"] = dataset
        config_sha256 = canonical_hash(config)
        relative = Path("runs") / "SASRec" / dataset
        run_dir = queue_root / relative
        dataset_records[dataset] = {
            "dataset_dir": str(dataset_dir),
            "protocol_sha256": _file_sha256(dataset_dir / "protocol.json"),
            "mapping_sha256": _file_sha256(dataset_dir / "item_mapping.csv"),
            "split_sha256": split_sha256,
            "config_sha256": config_sha256,
            "row_counts": {split: int(protocol["counts"][f"{split}_row_count"]) for split in ("train", "val", "test")},
            "item_num": int(protocol["counts"]["item_num"]),
        }
        argv = [
            str(args.python_bin),
            str(source_root / "scripts" / "run_sasrec.py"),
            "--dataset", dataset,
            "--dataset-dir", str(dataset_dir),
            "--run-dir", str(run_dir),
            "--seed", "100",
            "--device", "cuda:0",
            "--gpu-id", "0",
            "--evaluator-version", EVALUATOR_VERSION,
            "--selector-version", SELECTOR_VERSION,
            "--split-sha256", split_sha256,
            "--config-sha256", config_sha256,
            "--hidden-size", str(CONFIG["hidden_size"]),
            "--num-heads", str(CONFIG["num_heads"]),
            "--num-layers", str(CONFIG["num_layers"]),
            "--dropout", str(CONFIG["dropout"]),
            "--epochs", str(CONFIG["epochs"]),
            "--batch-size", str(CONFIG["batch_size"]),
            "--eval-batch-size", str(CONFIG["eval_batch_size"]),
            "--learning-rate", str(CONFIG["learning_rate"]),
            "--weight-decay", str(CONFIG["weight_decay"]),
            "--early-stop-patience", str(CONFIG["early_stop_patience"]),
            "--early-stop-min-delta", str(CONFIG["early_stop_min_delta"]),
        ]
        tasks.append({
            "schema_version": 1,
            "task_id": f"E05.SASRec.{dataset}.seed100",
            "ledger_id": "E05-SASREC-ADAPTER-20260711",
            "phase": "baseline",
            "branch": "e5_atomic",
            "kind": "gpu",
            "argv": argv,
            "cwd": str(run_dir),
            "env": {"CUDA_VISIBLE_DEVICES": "0", "PYTHONHASHSEED": "100"},
            "dependencies": [],
            "success_artifacts": ["artifact_manifest.json", "best_summary_sasrec.json", "sasrec_best.pt"],
            "failure_policy": "fail_closed",
            "max_attempts": 1,
            "gpu_slots": 1,
            "gpu_hours_low": 0.5,
            "gpu_hours_high": 8.0,
            "estimated_output_gib": 1.0,
            "seed": 100,
            "dataset": dataset,
            "arm": "author_default",
            "model": "SASRec",
            "run_dir": str(run_dir),
            "code_revision": str(args.code_revision),
            "config_sha256": config_sha256,
            "split_sha256": split_sha256,
            "bank_sha256": None,
            "evaluator_version": EVALUATOR_VERSION,
            "selector_version": SELECTOR_VERSION,
            "atomic_group": "E05.SASRec.four-domain",
            "priority": 0,
        })
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "queue_id": "E05-SASREC-SEED100-GPU0-20260711",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "queue_root": str(queue_root),
        "source_root": str(source_root),
        "source_files": source_hashes,
        "source_manifest_sha256": source_manifest_sha256,
        "ledger_path": str(ledger_path),
        "ledger_sha256": ledger_sha256,
        "code_revision": str(args.code_revision),
        "python_bin": str(args.python_bin),
        "gpu_ids": [0],
        "seed_set": [100],
        "evaluator_version": EVALUATOR_VERSION,
        "selector_version": SELECTOR_VERSION,
        "atomic_group": "E05.SASRec.four-domain",
        "all_four_required": True,
        "failure_policy": "fail_closed",
        "max_attempts": 1,
        "min_free_disk_gib": 40.0,
        "datasets": dataset_records,
        "config": CONFIG,
        "tasks": tasks,
    }
    manifest["manifest_sha256"] = canonical_hash(manifest)
    queue_root.joinpath("manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    queue_root.joinpath("SOURCE_MANIFEST.json").write_text(json.dumps({"files": source_hashes, "sha256": source_manifest_sha256}, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-root", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--ledger-path", required=True, type=Path)
    parser.add_argument("--python-bin", default="/usr/bin/python3")
    parser.add_argument("--code-revision", required=True)
    return parser.parse_args(argv)


if __name__ == "__main__":
    payload = build_manifest(parse_args())
    print(json.dumps({"queue_root": payload["queue_root"], "manifest_sha256": payload["manifest_sha256"], "tasks": len(payload["tasks"])}, sort_keys=True))
