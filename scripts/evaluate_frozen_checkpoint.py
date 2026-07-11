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
from scripts.aaai27_adapters.optimizer_contract import (
    compose_named_training_parameters,
)


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


def validate_ema_state(
    ema: Any,
    parameters_or_model: Any,
    parameter_names: list[str] | None = None,
) -> None:
    if hasattr(parameters_or_model, "parameters"):
        parameters = [
            parameter
            for parameter in parameters_or_model.parameters()
            if parameter.requires_grad
        ]
    else:
        parameters = [
            parameter
            for parameter in parameters_or_model
            if parameter.requires_grad
        ]
    shadows = list(ema.shadow_params)
    if len(shadows) != len(parameters):
        raise ValueError(
            f"EMA shadow parameter count mismatch: expected {len(parameters)}, got {len(shadows)}"
        )
    for index, (shadow, parameter) in enumerate(zip(shadows, parameters)):
        if tuple(shadow.shape) != tuple(parameter.shape):
            label = (
                parameter_names[index]
                if parameter_names is not None and index < len(parameter_names)
                else str(index)
            )
            raise ValueError(
                f"EMA shadow parameter shape mismatch at {label}: "
                f"expected {tuple(parameter.shape)}, got {tuple(shadow.shape)}"
            )


def restore_evaluation_parameters(
    *,
    score_model: Any,
    graph: Any,
    checkpoint: dict[str, Any],
    ema_decay: float,
) -> dict[str, Any]:
    load_model_state_strict(score_model, checkpoint["model"])
    if "graph" in checkpoint:
        graph.load_state_dict(checkpoint["graph"], strict=True)

    named_parameters = compose_named_training_parameters(score_model, graph)
    parameter_names = [name for name, _ in named_parameters]
    checkpoint_names = checkpoint.get("training_parameter_names")
    if checkpoint_names is not None and list(checkpoint_names) != parameter_names:
        raise ValueError(
            "checkpoint training parameter order mismatch: "
            f"expected {parameter_names}, got {list(checkpoint_names)}"
        )
    training_parameters = [parameter for _, parameter in named_parameters]
    ema = ExponentialMovingAverage(training_parameters, decay=float(ema_decay))
    ema.load_state_dict(checkpoint["ema"])
    validate_ema_state(ema, training_parameters, parameter_names)
    ema.copy_to(training_parameters)
    return {
        "ema": ema,
        "training_parameters": training_parameters,
        "training_parameter_names": parameter_names,
        "legacy_parameter_order_inferred": checkpoint_names is None,
    }


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


def resolve_item_count_contract(
    logged_config: dict[str, Any],
    *,
    checkpoint_model_state: dict[str, Any],
    dataset_name: str,
    dataset_dir: Path,
    allow_legacy_model_catalog_mismatch: bool = False,
) -> dict[str, Any]:
    """Separate the frozen model vocabulary from the real candidate catalog.

    Legacy checkpoints must be reconstructed with the item count serialized in
    their training log.  The regenerated dataset protocol independently fixes
    how many real items may enter paper-facing top-k evaluation.
    """

    try:
        model_item_count = int(logged_config["data"][dataset_name]["item_num"])
        is_disliked_item = bool(logged_config["graph"]["is_disliked_item"])
        checkpoint_weight = checkpoint_model_state["vocab_embed.embedding.weight"]
        checkpoint_vocab_rows = int(checkpoint_weight.shape[0])
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as exc:
        raise ValueError("unable to resolve frozen checkpoint item-count contract") from exc

    valid_item_count = dataset_runtime.infer_runtime_item_num(dataset_dir)
    if valid_item_count is None or int(valid_item_count) <= 0:
        raise ValueError(f"unable to resolve real candidate item count for {dataset_name}")
    valid_item_count = int(valid_item_count)

    padding_rows = 1
    expected_checkpoint_vocab_rows = (
        model_item_count + (1 if is_disliked_item else 0) + padding_rows
    )
    if checkpoint_vocab_rows != expected_checkpoint_vocab_rows:
        raise ValueError(
            "checkpoint vocabulary rows do not match the serialized training config: "
            f"expected {expected_checkpoint_vocab_rows}, got {checkpoint_vocab_rows}"
        )
    if valid_item_count > model_item_count:
        raise ValueError(
            "real candidate item count exceeds frozen model item count: "
            f"candidates={valid_item_count}, model={model_item_count}"
        )

    text_side_enabled = bool(logged_config.get("text_side", {}).get("enabled", False))
    if text_side_enabled and valid_item_count != model_item_count:
        raise ValueError(
            "text-side item count mismatch: frozen model and real candidate catalog must agree; "
            f"model={model_item_count}, candidates={valid_item_count}"
        )
    if valid_item_count != model_item_count and not allow_legacy_model_catalog_mismatch:
        raise ValueError(
            "frozen model/catalog item count differs; an explicit legacy mismatch allowance "
            "is required for this evaluator invocation: "
            f"model={model_item_count}, candidates={valid_item_count}"
        )

    return {
        "model_item_count": model_item_count,
        "valid_item_count": valid_item_count,
        "non_candidate_model_item_slots": model_item_count - valid_item_count,
        "checkpoint_vocab_rows": checkpoint_vocab_rows,
        "legacy_model_catalog_mismatch_authorized": bool(
            allow_legacy_model_catalog_mismatch and valid_item_count != model_item_count
        ),
    }


def inspect_test_item_domain(
    test_dataset: Any,
    *,
    valid_item_count: int,
    model_item_count: int,
) -> dict[str, Any]:
    history_min: int | None = None
    history_max: int | None = None
    target_min: int | None = None
    target_max: int | None = None
    history_pad_occurrences = 0
    history_pad_rows = 0

    seq_data = list(getattr(test_dataset, "seq_data", []))
    next_data = list(getattr(test_dataset, "next_data", []))
    if not seq_data or len(seq_data) != len(next_data):
        raise ValueError("test dataset item-domain audit requires aligned non-empty seq/next rows")

    for sequence in seq_data:
        values = torch.as_tensor(sequence).detach().cpu().reshape(-1)
        if values.numel() == 0:
            raise ValueError("test history contains an empty sequence")
        row_min = int(values.min().item())
        row_max = int(values.max().item())
        if row_min < 0 or row_max > valid_item_count:
            raise ValueError(
                "history item id outside real-item-or-pad domain: "
                f"min={row_min}, max={row_max}, pad={valid_item_count}"
            )
        pad_count = int((values == valid_item_count).sum().item())
        history_pad_occurrences += pad_count
        history_pad_rows += int(pad_count > 0)
        history_min = row_min if history_min is None else min(history_min, row_min)
        history_max = row_max if history_max is None else max(history_max, row_max)

    for target in next_data:
        value = int(torch.as_tensor(target).detach().cpu().item())
        if value < 0 or value >= valid_item_count:
            raise ValueError(
                "target item id outside real candidate catalog: "
                f"target={value}, valid range=[0,{valid_item_count - 1}]"
            )
        target_min = value if target_min is None else min(target_min, value)
        target_max = value if target_max is None else max(target_max, value)

    pad_maps_to_non_candidate_slot = bool(
        model_item_count > valid_item_count and history_pad_occurrences > 0
    )
    return {
        "history_pad_value": valid_item_count,
        "history_pad_occurrences": history_pad_occurrences,
        "history_pad_rows": history_pad_rows,
        "history_pad_maps_to_non_candidate_model_slot": pad_maps_to_non_candidate_slot,
        "history_pad_semantics": (
            "ordinary_non_candidate_legacy_model_slot"
            if pad_maps_to_non_candidate_slot
            else "disliked_state"
        ),
        "minimum_history_item_id": history_min,
        "maximum_history_item_id": history_max,
        "minimum_target_item_id": target_min,
        "maximum_target_item_id": target_max,
    }


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
    model_item_count: int | None = None,
    legacy_model_catalog_mismatch_authorized: bool = False,
    test_item_domain: dict[str, Any] | None = None,
    summary_path: Path | None = None,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    if model_item_count is None:
        model_item_count = valid_item_count
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
            "model_item_count": model_item_count,
            "non_candidate_model_item_slots": model_item_count - valid_item_count,
            "legacy_model_catalog_mismatch_authorized": bool(
                legacy_model_catalog_mismatch_authorized
            ),
            "test_item_domain": test_item_domain or {},
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

    device = torch.device(args.device)
    checkpoint = torch.load(args.checkpoint_path, map_location=device, weights_only=False)
    item_count_contract = resolve_item_count_contract(
        logged_config,
        checkpoint_model_state=checkpoint["model"],
        dataset_name=args.dataset_name,
        dataset_dir=args.dataset_dir,
        allow_legacy_model_catalog_mismatch=args.allow_legacy_model_catalog_mismatch,
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

    graph = graph_lib.get_graph(cfg, device)
    score_model = SEDD4REC(cfg).to(device)
    checkpoint_step = int(checkpoint["step"])
    validate_best_summary(summary, checkpoint_step=checkpoint_step)
    restore_evaluation_parameters(
        score_model=score_model,
        graph=graph,
        checkpoint=checkpoint,
        ema_decay=float(cfg.training.ema),
    )
    score_model.eval()

    noise = noise_lib.get_noise(cfg).to(device)
    sampling_fns = build_sampling_functions(cfg, graph, noise, 1e-5, device)
    if args.strength not in sampling_fns:
        raise ValueError(f"unsupported strength: {args.strength}")

    _, _, test_loader = data.get_seqdataloader(cfg)
    valid_item_count = int(item_count_contract["valid_item_count"])
    test_item_domain = inspect_test_item_domain(
        test_loader.dataset,
        valid_item_count=valid_item_count,
        model_item_count=int(item_count_contract["model_item_count"]),
    )
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
        model_item_count=int(item_count_contract["model_item_count"]),
        legacy_model_catalog_mismatch_authorized=bool(
            item_count_contract["legacy_model_catalog_mismatch_authorized"]
        ),
        test_item_domain=test_item_domain,
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
    parser.add_argument(
        "--allow-legacy-model-catalog-mismatch",
        action="store_true",
        help=(
            "Explicitly allow a frozen non-text model whose logged model item count exceeds "
            "the regenerated real candidate catalog; the mismatch is recorded in the output."
        ),
    )
    parser.add_argument("--device", default="cuda:0" if torch.cuda.is_available() else "cpu")
    return parser.parse_args()


def main() -> None:
    output_path = evaluate_frozen_checkpoint(parse_args())
    print(json.dumps({"output_path": str(output_path)}, indent=2))


if __name__ == "__main__":
    main()
