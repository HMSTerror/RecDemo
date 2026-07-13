from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.audit_e05_sasrec_reuse import E5ReuseError, audit_e5_root


DOMAINS = ("Steam", "ML1M", "Beauty", "ATG")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _fixture(root: Path, domains: tuple[str, ...] = DOMAINS, seed: int = 100) -> Path:
    datasets = {
        dataset: {
            "config_sha256": chr(97 + index) * 64,
            "split_sha256": chr(101 + index) * 64,
            "mapping_sha256": chr(105 + index) * 64,
        }
        for index, dataset in enumerate(domains)
    }
    _write_json(
        root / "manifest.json",
        {
            "all_four_required": True,
            "atomic_group": "E05.SASRec.four-domain",
            "seed_set": [seed],
            "evaluator_version": "e0_full_tail_v2",
            "selector_version": "validation-ndcg10-rowweighted-v1",
            "datasets": datasets,
        },
    )
    _write_json(
        root / "queue_status.json",
        {
            "status": "passed_four_domain_atomic_group",
            "tasks": [
                {"dataset": dataset, "status": "passed", "returncode": 0}
                for dataset in domains
            ],
        },
    )
    for dataset in domains:
        run = root / "runs" / "SASRec" / dataset
        contract = datasets[dataset]
        _write_json(
            run / "artifact_manifest.json",
            {
                "method": "SASRec",
                "dataset": dataset,
                "seed": seed,
                "evaluator_version": "e0_full_tail_v2",
                "selector_version": "validation-ndcg10-rowweighted-v1",
                "config_sha256": contract["config_sha256"],
                "split_sha256": contract["split_sha256"],
                "mapping_sha256": contract["mapping_sha256"],
            },
        )
        _write_json(run / "best_summary_sasrec.json", {"dataset": dataset, "best_epoch": 1})
        _write_json(run / "metrics_sasrec.json", {"validation": {}, "test": {}})
        (run / "sasrec_best.pt").write_bytes(b"checkpoint")
        (run / "stdout.log").write_text("finished\n", encoding="utf-8")
    return root


def test_complete_four_domain_group_passes(tmp_path: Path) -> None:
    result = audit_e5_root(_fixture(tmp_path / "e5"))
    assert result["status"] == "pass"
    assert result["datasets"] == ["ATG", "Beauty", "ML1M", "Steam"]
    assert len(result["artifacts"]) == 4
    assert all(row["stdout_bytes"] > 0 for row in result["artifacts"])


def test_missing_domain_rejects_atomic_reuse(tmp_path: Path) -> None:
    with pytest.raises(E5ReuseError, match="four-domain atomic group"):
        audit_e5_root(_fixture(tmp_path / "e5", DOMAINS[:-1]))


def test_empty_log_and_wrong_seed_fail_closed(tmp_path: Path) -> None:
    root = _fixture(tmp_path / "empty")
    (root / "runs" / "SASRec" / "Steam" / "stdout.log").write_bytes(b"")
    with pytest.raises(E5ReuseError, match="empty artifact"):
        audit_e5_root(root)
    with pytest.raises(E5ReuseError, match="seed 100"):
        audit_e5_root(_fixture(tmp_path / "seed", seed=101))
