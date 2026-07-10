#!/usr/bin/env python3
"""Re-evaluate a frozen PreferGrow-family checkpoint without training."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import random
from copy import deepcopy
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import torch
import numpy as np
from omegaconf import OmegaConf

import data
import dataset_runtime
import graph_lib
import noise_lib
import utils
from model.ema import ExponentialMovingAverage
from model.transformer import SEDD4REC


METRIC_CONTRACT_VERSION = "e0_full_tail_v2"


def reset_evaluation_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_named_files(*paths: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        path = Path(path)
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def load_model_state_strict(model: Any, state_dict: dict[str, Any]) -> None:
    model.load_state_dict(state_dict, strict=True)


def validate_best_summary(summary: dict[str, Any], *, checkpoint_step: int) -> None:
    summary_step = int(summary.get("best_step", -1))
    if summary_step != checkpoint_step:
        raise ValueError(
            f"best step mismatch: summary has {summary_step}, checkpoint has {checkpoint_step}"
        )


def validate_ema_state(ema: Any, model: Any) -> None:
    parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    shadows = list(ema.shadow_params)
    if len(shadows) != len(parameters):
        raise ValueError(
            f"EMA shadow parameter count mismatch: expected {len(parameters)}, got {len(shadows)}"
        )
    for index, (shadow, parameter) in enumerate(zip(shadows, parameters)):
        if tuple(shadow.shape) != tuple(parameter.shape):
            raise ValueError(
                f"EMA shadow parameter shape mismatch at index {index}: "
                f"expected {tuple(parameter.shape)}, got {tuple(shadow.shape)}"
            )


def validate_text_manifest(
    manifest: dict[str, Any],
    *,
    logged_config: dict[str, Any],
    dataset_name: str,
    dataset_dir: Path,
    checkpoint_path: Path,
    random_seed: int,
) -> None:
    if manifest.get("dataset") != dataset_name:
        raise ValueError("text manifest dataset mismatch")
    if Path(manifest.get("dataset_dir", "")).resolve() != Path(dataset_dir).resolve():
        raise ValueError("text manifest dataset directory mismatch")
    if int(manifest.get("random_seed", -1)) != random_seed:
        raise ValueError("text manifest random seed mismatch")
    run_dir = Path(manifest.get("run_dir", "")).resolve()
    if run_dir not in Path(checkpoint_path).resolve().parents:
        raise ValueError("text manifest run directory does not contain checkpoint")

    text_config = logged_config["text_side"]
    bank_path = Path(text_config["text_bank_path"])
    embeddings_path = Path(text_config["embeddings_path"])
    null_curve_path = Path(text_config["agreement_null_curve_path"])
    utility_path = Path(text_config["text_utility_report_path"])
    train_split_path = Path(dataset_dir) / "train_data.df"
    checks = {
        "bank_hash": sha256_named_files(bank_path, embeddings_path),
        "null_curve_hash": sha256_file(null_curve_path),
        "u_ds_artifact_hash": sha256_file(utility_path),
        "split_hash": sha256_named_files(train_split_path),
    }
    for key, actual in checks.items():
        if str(manifest.get(key)) != actual:
            label = key.replace("_", " ")
            raise ValueError(f"{label} mismatch: expected {manifest.get(key)}, got {actual}")
    for key, frozen_value in manifest.get("frozen_config", {}).items():
        if key in text_config and text_config[key] != frozen_value:
            raise ValueError(f"text manifest frozen config mismatch for {key}")


def result_filename(method_id: str, dataset_name: str, strength: str, eval_seed: int) -> str:
    return f"{method_id}_{dataset_name.lower()}_{strength}_evalseed{eval_seed}_e0_eval.json"


def parse_logged_config(log_path: Path) -> dict[str, Any]:
    for line in Path(log_path).read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if stripped.startswith("{") and "'training'" in stripped:
            payload = ast.literal_eval(stripped)
            if not isinstance(payload, dict):
                break
            return payload
    raise ValueError(f"unable to find serialized config dict in log: {log_path}")


def validate_expected_rows(dataset_name: str, split_name: str, *, actual: int, expected: int) -> int:
    if actual != expected:
        raise ValueError(
            f"{dataset_name} {split_name} row count mismatch: expected {expected}, got {actual}"
        )
    return actual


def build_result_payload(
    *,
    method_id: str,
    dataset_name: str,
    strength: str,
    hr: list[float],
    ndcg: list[float],
    evaluated_rows: int,
    expected_rows: int,
    best_step: int,
    checkpoint_path: Path,
    log_path: Path,
    split_path: Path,
    random_seed: int,
    eval_seed: int,
    valid_item_count: int,
    summary_path: Path | None = None,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    sources = {
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": sha256_file(checkpoint_path),
        "log_path": str(log_path),
        "log_sha256": sha256_file(log_path),
        "split_path": str(split_path),
        "split_sha256": sha256_file(split_path),
    }
    if summary_path is not None:
        sources["summary_path"] = str(summary_path)
        sources["summary_sha256"] = sha256_file(summary_path)
    if manifest_path is not None:
        sources["manifest_path"] = str(manifest_path)
        sources["manifest_sha256"] = sha256_file(manifest_path)
    return {
        "schema_version": 1,
        "method_id": method_id,
        "dataset": dataset_name,
        "random_seed": random_seed,
        "best_step": best_step,
        "strength": strength,
        "checkpoint_selector_protocol": "legacy_tail_skipping_validation",
        "selection_bias_not_recomputed": True,
        "metric_contract": {
            "version": METRIC_CONTRACT_VERSION,
            "aggregation_weight": "row",
            "tail_batch_included": True,
            "eval_seed": eval_seed,
            "candidate_policy": "first-M-zero-based",
            "valid_item_count": valid_item_count,
            "topk": [1, 5, 10, 20, 50],
        },
        "test": {
            "expected_rows": expected_rows,
            "evaluated_rows": evaluated_rows,
            "hr": [float(value) for value in hr],
            "ndcg": [float(value) for value in ndcg],
            "hr10": float(hr[2]),
            "ndcg10": float(ndcg[2]),
        },
        "sources": sources,
    }


def prepare_config(
    logged_config: dict[str, Any],
    *,
    dataset_name: str,
    dataset_dir: Path,
    output_dir: Path,
    batch_size: int,
    random_seed: int,
) -> Any:
    cfg_dict = deepcopy(logged_config)
    cfg_dict["work_dir"] = str(output_dir)
    cfg_dict["random_seed"] = int(random_seed)
    cfg_dict["training"]["data"] = dataset_name
    cfg_dict["training"]["batch_size"] = int(batch_size)
    cfg_dict["data"][dataset_name]["path"] = str(dataset_dir)
    cfg = OmegaConf.create(cfg_dict)
    dataset_runtime.reconcile_runtime_dataset_config(cfg)
    return cfg


def evaluate_frozen_checkpoint(args: argparse.Namespace) -> Path:
    from single_train import build_sampling_functions

    logged_config = parse_logged_config(args.log_path)
    logged_seed = int(logged_config["random_seed"])
    if logged_seed != args.random_seed:
        raise ValueError(
            f"checkpoint config seed mismatch: expected {args.random_seed}, logged {logged_seed}"
        )
    summary = json.loads(args.summary_path.read_text(encoding="utf-8"))
    text_manifest = None
    if bool(logged_config.get("text_side", {}).get("enabled", False)):
        if args.manifest_path is None:
            raise ValueError("text-side checkpoint requires --manifest-path")
        text_manifest = json.loads(args.manifest_path.read_text(encoding="utf-8"))
        validate_text_manifest(
            text_manifest,
            logged_config=logged_config,
            dataset_name=args.dataset_name,
            dataset_dir=args.dataset_dir,
            checkpoint_path=args.checkpoint_path,
            random_seed=args.random_seed,
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    cfg = prepare_config(
        logged_config,
        dataset_name=args.dataset_name,
        dataset_dir=args.dataset_dir,
        output_dir=args.output_dir,
        batch_size=args.batch_size,
        random_seed=args.random_seed,
    )
    reset_evaluation_seed(args.random_seed)
    device = torch.device(args.device)

    graph = graph_lib.get_graph(cfg, device)
    score_model = SEDD4REC(cfg).to(device)
    ema = ExponentialMovingAverage(score_model.parameters(), decay=float(cfg.training.ema))
    checkpoint = torch.load(args.checkpoint_path, map_location=device, weights_only=False)
    checkpoint_step = int(checkpoint["step"])
    validate_best_summary(summary, checkpoint_step=checkpoint_step)
    load_model_state_strict(score_model, checkpoint["model"])
    ema.load_state_dict(checkpoint["ema"])
    validate_ema_state(ema, score_model)
    ema.copy_to(score_model.parameters())
    score_model.eval()

    noise = noise_lib.get_noise(cfg).to(device)
    sampling_fns = build_sampling_functions(cfg, graph, noise, 1e-5, device)
    if args.strength not in sampling_fns:
        raise ValueError(f"unsupported strength: {args.strength}")

    _, _, test_loader = data.get_seqdataloader(cfg)
    valid_item_count = int(getattr(cfg.data, args.dataset_name).item_num)
    validate_expected_rows(
        args.dataset_name,
        "test",
        actual=len(test_loader.dataset),
        expected=args.expected_test_rows,
    )
    reset_evaluation_seed(args.eval_seed)
    with torch.no_grad():
        hr, ndcg, evaluated_rows = utils.evaluate_loader(
            score_model,
            sampling_fns[args.strength]["fn"],
            test_loader,
            device,
            valid_item_count,
            True,
        )
    validate_expected_rows(
        args.dataset_name,
        "evaluated test",
        actual=evaluated_rows,
        expected=args.expected_test_rows,
    )

    payload = build_result_payload(
        method_id=args.method_id,
        dataset_name=args.dataset_name,
        strength=args.strength,
        hr=hr,
        ndcg=ndcg,
        evaluated_rows=evaluated_rows,
        expected_rows=args.expected_test_rows,
        best_step=checkpoint_step,
        checkpoint_path=args.checkpoint_path,
        log_path=args.log_path,
        split_path=args.dataset_dir / "test_data.df",
        random_seed=args.random_seed,
        eval_seed=args.eval_seed,
        valid_item_count=valid_item_count,
        summary_path=args.summary_path,
        manifest_path=args.manifest_path,
    )
    output_path = args.output_dir / result_filename(
        args.method_id, args.dataset_name, args.strength, args.eval_seed
    )
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method-id", required=True)
    parser.add_argument("--dataset-name", required=True)
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--log-path", type=Path, required=True)
    parser.add_argument("--summary-path", type=Path, required=True)
    parser.add_argument("--manifest-path", type=Path)
    parser.add_argument("--checkpoint-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-test-rows", type=int, required=True)
    parser.add_argument("--random-seed", type=int, default=100)
    parser.add_argument("--eval-seed", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--strength", choices=("base", "p2", "p5", "p10"), default="p2")
    parser.add_argument("--device", default="cuda:0" if torch.cuda.is_available() else "cpu")
    return parser.parse_args()


def main() -> None:
    output_path = evaluate_frozen_checkpoint(parse_args())
    print(json.dumps({"output_path": str(output_path)}, indent=2))


if __name__ == "__main__":
    main()
