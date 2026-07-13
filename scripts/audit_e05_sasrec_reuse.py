from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from scripts.aaai27_queue.storage import atomic_create_json, load_json, sha256_file


DOMAINS = {"Steam", "ML1M", "Beauty", "ATG"}
EVALUATOR_VERSION = "e0_full_tail_v2"
SELECTOR_VERSION = "validation-ndcg10-rowweighted-v1"
REQUIRED_RUN_FILES = (
    "artifact_manifest.json",
    "best_summary_sasrec.json",
    "metrics_sasrec.json",
    "sasrec_best.pt",
    "stdout.log",
)


class E5ReuseError(RuntimeError):
    """Raised when the completed E5 group is unsafe to reuse."""


def _required_file(path: Path) -> Path:
    if not path.is_file():
        raise E5ReuseError(f"missing artifact: {path}")
    if path.stat().st_size <= 0:
        raise E5ReuseError(f"empty artifact: {path}")
    return path


def _required_json(path: Path) -> dict[str, Any]:
    _required_file(path)
    try:
        return load_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise E5ReuseError(f"invalid JSON artifact: {path}") from exc


def _validate_group_contract(
    manifest: dict[str, Any],
    status: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if manifest.get("all_four_required") is not True:
        raise E5ReuseError("E5 does not declare a four-domain atomic group")
    if manifest.get("atomic_group") != "E05.SASRec.four-domain":
        raise E5ReuseError("E5 four-domain atomic group identity mismatch")
    if manifest.get("seed_set") != [100]:
        raise E5ReuseError("E5 reuse requires seed 100 only")
    if manifest.get("evaluator_version") != EVALUATOR_VERSION:
        raise E5ReuseError("E5 evaluator version mismatch")
    if manifest.get("selector_version") != SELECTOR_VERSION:
        raise E5ReuseError("E5 selector version mismatch")
    datasets = manifest.get("datasets")
    if not isinstance(datasets, dict) or set(datasets) != DOMAINS:
        raise E5ReuseError("E5 is not a complete four-domain atomic group")
    if status.get("status") != "passed_four_domain_atomic_group":
        raise E5ReuseError("E5 queue status is not passed_four_domain_atomic_group")
    tasks = status.get("tasks")
    if not isinstance(tasks, list):
        raise E5ReuseError("E5 queue status lacks task records")
    passed = {
        row.get("dataset")
        for row in tasks
        if isinstance(row, dict)
        and row.get("status") == "passed"
        and row.get("returncode") == 0
    }
    if passed != DOMAINS:
        raise E5ReuseError("E5 task records do not pass the four-domain atomic group")
    return datasets


def audit_e5_root(e5_root: Path, dataset: str | None = None) -> dict[str, Any]:
    root = Path(e5_root).resolve(strict=False)
    if dataset is not None and dataset not in DOMAINS:
        raise E5ReuseError(f"unknown E5 dataset: {dataset}")
    manifest_path = root / "manifest.json"
    status_path = root / "queue_status.json"
    manifest = _required_json(manifest_path)
    status = _required_json(status_path)
    datasets = _validate_group_contract(manifest, status)

    artifact_rows: list[dict[str, Any]] = []
    for name in sorted(DOMAINS):
        contract = datasets[name]
        if not isinstance(contract, dict):
            raise E5ReuseError(f"invalid E5 dataset contract: {name}")
        run = root / "runs" / "SASRec" / name
        files = {filename: _required_file(run / filename) for filename in REQUIRED_RUN_FILES}
        artifact = _required_json(files["artifact_manifest.json"])
        _required_json(files["best_summary_sasrec.json"])
        _required_json(files["metrics_sasrec.json"])
        expected = {
            "method": "SASRec",
            "dataset": name,
            "seed": 100,
            "evaluator_version": EVALUATOR_VERSION,
            "selector_version": SELECTOR_VERSION,
            "config_sha256": contract.get("config_sha256"),
            "split_sha256": contract.get("split_sha256"),
            "mapping_sha256": contract.get("mapping_sha256"),
        }
        mismatches = {
            key: {"expected": value, "actual": artifact.get(key)}
            for key, value in expected.items()
            if artifact.get(key) != value
        }
        if mismatches:
            raise E5ReuseError(f"E5 {name} artifact identity mismatch: {mismatches}")
        artifact_rows.append(
            {
                "dataset": name,
                "artifact_manifest_sha256": sha256_file(files["artifact_manifest.json"]),
                "summary_sha256": sha256_file(files["best_summary_sasrec.json"]),
                "metrics_sha256": sha256_file(files["metrics_sasrec.json"]),
                "checkpoint_sha256": sha256_file(files["sasrec_best.pt"]),
                "stdout_sha256": sha256_file(files["stdout.log"]),
                "stdout_bytes": files["stdout.log"].stat().st_size,
            }
        )
    return {
        "schema_version": 1,
        "status": "pass",
        "artifact_type": "E5 SASRec four-domain reuse audit",
        "e5_root": str(root),
        "selected_dataset": dataset,
        "datasets": sorted(DOMAINS),
        "manifest_sha256": sha256_file(manifest_path),
        "queue_status_sha256": sha256_file(status_path),
        "evaluator_version": EVALUATOR_VERSION,
        "selector_version": SELECTOR_VERSION,
        "seed": 100,
        "artifacts": artifact_rows,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit E5 SASRec artifacts for reuse")
    parser.add_argument("--e5-root", type=Path, required=True)
    parser.add_argument("--dataset", choices=sorted(DOMAINS), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = audit_e5_root(args.e5_root, args.dataset)
        output = args.output_dir / "reuse_audit.json"
        atomic_create_json(output, result)
    except (E5ReuseError, FileExistsError, OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
