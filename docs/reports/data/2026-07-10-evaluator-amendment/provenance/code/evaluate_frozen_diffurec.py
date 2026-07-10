#!/usr/bin/env python3
"""Re-evaluate a frozen DiffuRec checkpoint under the E0 metric contract."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import torch


METRIC_CONTRACT_VERSION = "e0_full_tail_v2"
RUNNER_PATH = Path(__file__).resolve().with_name("run_close04_diffurec.py")
TRAINING_WRAPPER_REVISION = "f644a62933319a281076b23a01e7b9fd60954e06"
MODEL_CONFIG = {
    "hidden_size": 128,
    "emb_dropout": 0.3,
    "dropout": 0.1,
    "lr": 0.001,
    "weight_decay": 0.0,
    "schedule_sampler_name": "lossaware",
    "diffusion_steps": 32,
    "noise_schedule": "trunc_lin",
    "rescale_timesteps": True,
    "num_blocks": 4,
    "lambda_uncertainty": 0.001,
    "loss_lambda": 0.001,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_runner_module():
    spec = importlib.util.spec_from_file_location("e0_run_close04_diffurec", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_manifest(manifest: dict[str, Any], *, dataset_name: str, random_seed: int) -> None:
    if manifest.get("method") != "DiffuRec":
        raise ValueError("manifest method must be DiffuRec")
    if manifest.get("dataset") != dataset_name:
        raise ValueError(
            f"manifest dataset mismatch: expected {dataset_name}, got {manifest.get('dataset')}"
        )
    if int(manifest.get("random_seed", -1)) != random_seed:
        raise ValueError(
            f"manifest seed mismatch: expected {random_seed}, got {manifest.get('random_seed')}"
        )
    if manifest.get("checkpoint_policy") != "latest_plus_best":
        raise ValueError("manifest checkpoint policy is not latest_plus_best")


def load_model_state_strict(model: Any, state_dict: dict[str, Any]) -> None:
    model.load_state_dict(state_dict, strict=True)


def validate_best_checkpoint_binding(
    manifest: dict[str, Any],
    summary: dict[str, Any],
    *,
    checkpoint_path: Path,
    checkpoint_epoch: int,
) -> None:
    summary_path = Path(manifest["summary_path"]).resolve()
    checkpoint_path = Path(checkpoint_path).resolve()
    if checkpoint_path.name != "checkpoint_diffurec_best.pt":
        raise ValueError("DiffuRec checkpoint is not the frozen best checkpoint")
    if checkpoint_path.parent != summary_path.parent:
        raise ValueError("DiffuRec checkpoint and best summary are from different run directories")
    if summary.get("method") != "DiffuRec":
        raise ValueError("DiffuRec best summary method mismatch")
    if summary.get("dataset") != manifest.get("dataset"):
        raise ValueError("DiffuRec best summary dataset mismatch")
    if int(summary.get("random_seed", -1)) != int(manifest.get("random_seed", -2)):
        raise ValueError("DiffuRec best summary seed mismatch")
    best_epoch = int(summary.get("selector", {}).get("best_epoch", -1))
    if best_epoch != checkpoint_epoch:
        raise ValueError(
            f"best epoch mismatch: summary has {best_epoch}, checkpoint has {checkpoint_epoch}"
        )


def validate_expected_rows(dataset_name: str, *, actual: int, expected: int) -> int:
    if actual != expected:
        raise ValueError(
            f"{dataset_name} test row count mismatch: expected {expected}, got {actual}"
        )
    return actual


def build_result_payload(
    *,
    dataset_name: str,
    metrics: dict[str, float],
    evaluated_rows: int,
    expected_rows: int,
    best_epoch: int,
    checkpoint_path: Path,
    manifest_path: Path,
    split_path: Path,
    random_seed: int,
    eval_seed: int,
    upstream_revision: str,
    training_wrapper_revision: str,
    model_config: dict[str, Any],
    summary_path: Path,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "method_id": "diffurec",
        "dataset": dataset_name,
        "random_seed": random_seed,
        "best_epoch": best_epoch,
        "checkpoint_selector_protocol": "legacy_equal_batch_mean_validation",
        "selection_bias_not_recomputed": True,
        "training_wrapper_revision": training_wrapper_revision,
        "model_config": model_config,
        "metric_contract": {
            "version": METRIC_CONTRACT_VERSION,
            "aggregation_weight": "row",
            "tail_batch_included": True,
            "candidate_policy": "exclude-padding-id-0",
            "eval_seed": eval_seed,
        },
        "test": {
            "expected_rows": expected_rows,
            "evaluated_rows": evaluated_rows,
            "metrics": {key: float(value) for key, value in metrics.items()},
            "hr10": float(metrics["HR@10"]),
            "ndcg10": float(metrics["NDCG@10"]),
        },
        "sources": {
            "checkpoint_path": str(checkpoint_path),
            "checkpoint_sha256": sha256_file(checkpoint_path),
            "manifest_path": str(manifest_path),
            "manifest_sha256": sha256_file(manifest_path),
            "summary_path": str(summary_path),
            "summary_sha256": sha256_file(summary_path),
            "split_path": str(split_path),
            "split_sha256": sha256_file(split_path),
            "upstream_revision": upstream_revision,
            "evaluator_runner_path": str(RUNNER_PATH),
            "evaluator_runner_sha256": sha256_file(RUNNER_PATH),
        },
    }


def build_model_args(manifest: dict[str, Any], device: torch.device) -> SimpleNamespace:
    return SimpleNamespace(
        hidden_size=MODEL_CONFIG["hidden_size"],
        item_num=int(manifest["item_num"]),
        emb_dropout=MODEL_CONFIG["emb_dropout"],
        max_len=int(manifest["max_len"]),
        dropout=MODEL_CONFIG["dropout"],
        optimizer="Adam",
        lr=MODEL_CONFIG["lr"],
        weight_decay=MODEL_CONFIG["weight_decay"],
        momentum=None,
        num_gpu=1,
        schedule_sampler_name=MODEL_CONFIG["schedule_sampler_name"],
        diffusion_steps=MODEL_CONFIG["diffusion_steps"],
        noise_schedule=MODEL_CONFIG["noise_schedule"],
        rescale_timesteps=MODEL_CONFIG["rescale_timesteps"],
        num_blocks=MODEL_CONFIG["num_blocks"],
        hidden_act="gelu",
        lambda_uncertainty=MODEL_CONFIG["lambda_uncertainty"],
        loss_lambda=MODEL_CONFIG["loss_lambda"],
        device=str(device),
        batch_size=int(manifest["batch_size"]),
    )


def evaluate_frozen_diffurec(args: argparse.Namespace) -> Path:
    runner = load_runner_module()
    manifest = json.loads(args.manifest_path.read_text(encoding="utf-8"))
    validate_manifest(manifest, dataset_name=args.dataset_name, random_seed=args.random_seed)

    dataset_dir = Path(manifest["dataset_dir"])
    upstream_root = Path(manifest["upstream_root"])
    actual_revision = runner.get_git_revision(upstream_root)
    expected_revision = str(manifest["upstream_revision"])
    if not actual_revision:
        raise ValueError("unable to verify DiffuRec upstream revision")
    if actual_revision != expected_revision:
        raise ValueError(
            f"DiffuRec upstream revision mismatch: expected {expected_revision}, got {actual_revision}"
        )

    bundle = runner.load_dataset_bundle(dataset_dir)
    if int(bundle["item_num"]) != int(manifest["item_num"]):
        raise ValueError("DiffuRec item count differs from frozen manifest")
    validate_expected_rows(
        args.dataset_name,
        actual=len(bundle["test_examples"]),
        expected=args.expected_test_rows,
    )

    runner.seed_everything(args.random_seed)
    device = torch.device(args.device)
    upstream = runner.load_upstream_modules(upstream_root)
    model_args = build_model_args(manifest, device)
    diffu_model = upstream.model.create_model_diffu(model_args)
    model = upstream.model.Att_Diffuse_model(diffu_model, model_args).to(device)
    checkpoint = torch.load(args.checkpoint_path, map_location=device, weights_only=False)
    checkpoint_epoch = int(checkpoint["epoch"])
    summary_path = Path(manifest["summary_path"])
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    validate_best_checkpoint_binding(
        manifest,
        summary,
        checkpoint_path=args.checkpoint_path,
        checkpoint_epoch=checkpoint_epoch,
    )
    load_model_state_strict(model, checkpoint["model_state_dict"])

    test_loader = runner.build_dataloader(
        bundle["test_examples"],
        batch_size=int(manifest["batch_size"]),
        shuffle=False,
    )
    runner.seed_everything(args.eval_seed)
    metrics, evaluated_rows = runner.evaluate_model(
        model, test_loader, device, return_evaluated_rows=True
    )
    validate_expected_rows(
        args.dataset_name,
        actual=evaluated_rows,
        expected=args.expected_test_rows,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    payload = build_result_payload(
        dataset_name=args.dataset_name,
        metrics=metrics,
        evaluated_rows=evaluated_rows,
        expected_rows=args.expected_test_rows,
        best_epoch=checkpoint_epoch,
        checkpoint_path=args.checkpoint_path,
        manifest_path=args.manifest_path,
        split_path=dataset_dir / "test_data.df",
        random_seed=args.random_seed,
        eval_seed=args.eval_seed,
        upstream_revision=expected_revision,
        training_wrapper_revision=TRAINING_WRAPPER_REVISION,
        model_config=dict(MODEL_CONFIG),
        summary_path=summary_path,
    )
    output_path = args.output_dir / (
        f"diffurec_{args.dataset_name.lower()}_evalseed{args.eval_seed}_e0_eval.json"
    )
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-name", required=True)
    parser.add_argument("--manifest-path", type=Path, required=True)
    parser.add_argument("--checkpoint-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-test-rows", type=int, required=True)
    parser.add_argument("--random-seed", type=int, default=100)
    parser.add_argument("--eval-seed", type=int, default=100)
    parser.add_argument("--device", default="cuda:0" if torch.cuda.is_available() else "cpu")
    return parser.parse_args()


def main() -> None:
    output_path = evaluate_frozen_diffurec(parse_args())
    print(json.dumps({"output_path": str(output_path)}, indent=2))


if __name__ == "__main__":
    main()
