from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from .common import atomic_write_json, load_jsonl_records, sha256_file, stable_sha256
from .proposal_contract import validate_proposal_manifest
from .risk_report import build_train_only_risk_report


LEVELS = (0, 20, 40, 60, 80, 100)


def _reject_non_train_path(path: Path) -> None:
    lowered = path.name.casefold()
    if any(token in lowered for token in ("val", "test")):
        raise ValueError(f"RISK-04 preflight accepts train-only transition paths: {path}")


def _load_bank_manifest(path: Path, dataset: str, level: int) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"bank manifest does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"bank manifest must contain an object: {path}")
    if str(payload.get("dataset")) != str(dataset):
        raise ValueError(f"bank manifest dataset mismatch for {dataset} level {level}")
    if int(payload.get("corruption_level", -1)) != int(level):
        raise ValueError(f"bank manifest corruption level mismatch for {dataset} level {level}")
    if not payload.get("bank_sha256"):
        raise ValueError(f"bank manifest lacks immutable bank_sha256: {path}")
    return payload


def _optional_numeric_mean(records: list[dict[str, Any]], keys: tuple[str, ...]) -> float | None:
    values: list[float] = []
    for record in records:
        value: Any | None = None
        for key in keys:
            if key in record and record[key] not in (None, ""):
                value = record[key]
                break
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"optional preflight field {keys} contains a non-numeric value") from exc
        if not np.isfinite(numeric):
            raise ValueError(f"optional preflight field {keys} contains a non-finite value")
        values.append(numeric)
    return float(np.mean(values)) if values else None


def _history_length_strata(records: list[dict[str, Any]]) -> dict[str, int] | None:
    lengths: list[int] = []
    for record in records:
        history = record.get("history_item_ids", record.get("history", record.get("seq")))
        if history is None:
            continue
        if not isinstance(history, (list, tuple)):
            raise ValueError("history length strata require list-like history_item_ids")
        lengths.append(len(history))
    if not lengths:
        return None
    return {
        "length_1_5": int(sum(1 for value in lengths if 1 <= value <= 5)),
        "length_6_10": int(sum(1 for value in lengths if 6 <= value <= 10)),
        "length_11_plus": int(sum(1 for value in lengths if value >= 11)),
        "total": int(len(lengths)),
    }


def _level_summary(
    report: dict[str, Any],
    records: list[dict[str, Any]],
    manifest: dict[str, Any],
    proposal_manifest: dict[str, Any],
    level: int,
) -> dict[str, Any]:
    point = report["point_estimates"]
    return {
        "level": int(level),
        "epe": float(point["epe"]),
        "pne10": float(point["pne10"]),
        "excess_pne10": float(point["excess_pne10"]),
        "text_entropy": float(point["text_entropy"]),
        "top10_mass_concentration": float(point["top10_mass_concentration"]),
        "mean_gate": _optional_numeric_mean(records, ("gate", "mean_gate", "g")),
        "mean_u_tilde": _optional_numeric_mean(records, ("u_tilde", "mean_u_tilde")),
        "mean_target_popularity": _optional_numeric_mean(records, ("target_popularity", "target_count", "popularity")),
        "history_length_strata": _history_length_strata(records),
        "risk_report_sha256": report["artifact_sha256"],
        "bank_sha256": str(manifest["bank_sha256"]),
        "bank_manifest_sha256": sha256_file(Path(manifest["_path"])),
        "proposal_manifest_sha256": proposal_manifest["manifest_sha256"],
        "proposal_manifest_file_sha256": sha256_file(Path(proposal_manifest["_path"])),
        "kernel_version": proposal_manifest["kernel_version"],
        "temperature": proposal_manifest["temperature"],
        "g_max": proposal_manifest["g_max"],
        "transition_sha256": report["provenance"]["transition_sha256"],
        "embedding_sha256": report["provenance"]["embedding_sha256"],
    }


def build_risk_preflight(
    config: dict[str, Any],
    output_dir: Path,
    *,
    sample_size: int = 4000,
    sampling_seed: int = 7,
    bootstrap_replicates: int = 1000,
    bootstrap_seed: int = 100,
    code_revision: str | None = None,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"preflight output directory already exists: {output_dir}")
    datasets = config.get("datasets")
    if not isinstance(datasets, dict) or set(datasets) != {"Beauty", "Steam"}:
        raise ValueError("RISK-04 preflight requires exactly Beauty and Steam datasets")
    dataset_reports: dict[str, Any] = {}
    all_source_hashes: dict[str, Any] = {}
    report_root = output_dir / "risk_reports"
    for dataset in ("Beauty", "Steam"):
        dataset_config = datasets[dataset]
        if not isinstance(dataset_config, dict):
            raise ValueError(f"preflight configuration for {dataset} must be an object")
        levels = dataset_config.get("levels")
        if not isinstance(levels, list) or [int(row.get("level", -1)) for row in levels] != list(LEVELS):
            raise ValueError(f"{dataset} preflight must contain exactly levels {LEVELS}")
        level_summaries: list[dict[str, Any]] = []
        all_epe: list[float] = []
        dataset_hashes: dict[str, Any] = {}
        for level_config in levels:
            level = int(level_config["level"])
            transition_path = Path(level_config["transitions_path"])
            embedding_path = Path(level_config["embeddings_path"])
            manifest_path = Path(level_config["bank_manifest_path"])
            proposal_manifest_path = Path(level_config.get("proposal_manifest_path", ""))
            _reject_non_train_path(transition_path)
            manifest = _load_bank_manifest(manifest_path, dataset, level)
            manifest["_path"] = str(manifest_path)
            if not proposal_manifest_path.exists():
                raise FileNotFoundError(f"proposal manifest is required for train-only preflight: {proposal_manifest_path}")
            proposal_manifest = json.loads(proposal_manifest_path.read_text(encoding="utf-8"))
            proposal_manifest = validate_proposal_manifest(
                proposal_manifest,
                expected_dataset=dataset,
                expected_bank_sha256=str(manifest["bank_sha256"]),
            )
            proposal_manifest["_path"] = str(proposal_manifest_path)
            records = load_jsonl_records(transition_path)
            for record in records:
                split = str(record.get("split", "train")).casefold()
                if split != "train":
                    raise ValueError(f"non-train transition record entered RISK-04 preflight: {transition_path}")
            report_dir = report_root / dataset / f"level-{level:03d}"
            risk_report = build_train_only_risk_report(
                transition_path,
                embedding_path,
                output_dir=report_dir,
                sample_size=sample_size,
                sampling_seed=sampling_seed,
                bootstrap_replicates=bootstrap_replicates,
                bootstrap_seed=bootstrap_seed,
                split_name="train",
                expected_item_ids=level_config.get("expected_item_ids"),
                proposal_manifest=proposal_manifest,
            )
            summary = _level_summary(risk_report, records, manifest, proposal_manifest, level)
            level_summaries.append(summary)
            all_epe.extend(float(row["epe"]) for row in risk_report["rows"])
            dataset_hashes[str(level)] = {
                "transition_sha256": summary["transition_sha256"],
                "embedding_sha256": summary["embedding_sha256"],
                "bank_manifest_sha256": summary["bank_manifest_sha256"],
                "proposal_manifest_file_sha256": summary["proposal_manifest_file_sha256"],
                "proposal_manifest_sha256": summary["proposal_manifest_sha256"],
                "bank_sha256": summary["bank_sha256"],
            }
        pooled_sd = float(np.std(np.asarray(all_epe, dtype=np.float64), ddof=1)) if len(all_epe) > 1 else None
        dataset_source_hashes = {
            "train_transitions": {str(row["level"]): row["transition_sha256"] for row in level_summaries},
            "embeddings": {str(row["level"]): row["embedding_sha256"] for row in level_summaries},
            "bank_manifests": {str(row["level"]): row["bank_manifest_sha256"] for row in level_summaries},
            "banks": {str(row["level"]): row["bank_sha256"] for row in level_summaries},
            "proposal_manifests": {str(row["level"]): row["proposal_manifest_file_sha256"] for row in level_summaries},
            "proposal_bindings": {str(row["level"]): row["proposal_manifest_sha256"] for row in level_summaries},
            "by_level": dataset_hashes,
        }
        dataset_reports[dataset] = {
            "levels_order": list(LEVELS),
            "clean_epe": float(level_summaries[0]["epe"]),
            "pooled_sd": pooled_sd,
            "levels": level_summaries,
            "source_hashes": dataset_source_hashes,
            "code_revision": str(dataset_config.get("code_revision", code_revision or "unbound")),
        }
        all_source_hashes[dataset] = dataset_source_hashes

    result: dict[str, Any] = {
        "schema_version": 1,
        "report_name": "AAAI-RISK-04 train-only corruption-bank preflight",
        "protocol": {
            "datasets": ["Beauty", "Steam"],
            "corruption_levels": list(LEVELS),
            "corruption_seed": 100,
            "sample_size": int(sample_size),
            "sampling_seed": int(sampling_seed),
            "bootstrap_replicates": int(bootstrap_replicates),
            "bootstrap_seed": int(bootstrap_seed),
            "split": "train-only",
            "no_training_started": True,
        },
        "datasets": dataset_reports,
        "source_hashes": all_source_hashes,
        "config_sha256": stable_sha256(config),
    }
    result["artifact_sha256"] = stable_sha256(result)
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output_dir / "risk_preflight_report.json", result)
    lines = [
        "# AAAI-RISK-04 train-only corruption-bank preflight",
        "",
        "No training was started; all proposal records and target transitions are required to be train-only.",
        "",
        "| Dataset | Level | EPE | PNE@10 | mean gate | Risk report |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for dataset in ("Beauty", "Steam"):
        for row in dataset_reports[dataset]["levels"]:
            gate = "NA" if row["mean_gate"] is None else f"{row['mean_gate']:.6g}"
            lines.append(f"| {dataset} | {row['level']} | {row['epe']:.6g} | {row['pne10']:.6g} | {gate} | `{row['risk_report_sha256']}` |")
    (output_dir / "risk_preflight_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build train-only RISK-04 preflight over Beauty and Steam corruption banks.")
    parser.add_argument("--config-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=4000)
    parser.add_argument("--sampling-seed", type=int, default=7)
    parser.add_argument("--bootstrap-replicates", type=int, default=1000)
    parser.add_argument("--bootstrap-seed", type=int, default=100)
    parser.add_argument("--code-revision")
    args = parser.parse_args()
    config = json.loads(args.config_json.read_text(encoding="utf-8"))
    result = build_risk_preflight(
        config,
        args.output_dir,
        sample_size=args.sample_size,
        sampling_seed=args.sampling_seed,
        bootstrap_replicates=args.bootstrap_replicates,
        bootstrap_seed=args.bootstrap_seed,
        code_revision=args.code_revision,
    )
    print(json.dumps({"artifact_sha256": result["artifact_sha256"], "output_dir": str(args.output_dir)}, indent=2))


if __name__ == "__main__":
    main()
