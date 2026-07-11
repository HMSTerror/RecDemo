from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.aaai27_adapters.common import sha256_file, stable_sha256
from scripts.aaai27_adapters.continuation_adapters import (
    ContinuationSafetyError,
    build_method_pass_manifest,
)
from scripts.aaai27_queue.models import QueueManifest
from scripts.aaai27_queue.validation import ManifestError, validate_manifest
from scripts.verify_method_pass_gate import verify_method_pass_gate

from aaai27_queue_testdata import make_manifest, make_pilot_tasks


FOUR_DOMAINS = ("Steam", "ML1M", "Beauty", "ATG")
RISK14_ARMS = ("host", "text_anchor_only", "global_p", "dataset_gate_only", "full", "u_shuffle")


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _protocol() -> dict:
    return {
        "queue_id": "aaai27-method-pass-test",
        "created_at": "2026-07-11T12:00:00+08:00",
        "run_root": "/srv/queue/2026-07-11-method-pass",
        "source_root": "/srv/bundle/source",
        "source_manifest_sha256": "d" * 64,
        "ledger_path": "/srv/bundle/issues/execution.csv",
        "ledger_sha256": "e" * 64,
        "gpu_ids": [0, 1],
        "gpu_budget_hours": 168.0,
        "min_free_disk_gib": 40.0,
        "code_revision": "a" * 40,
        "python_bin": "/srv/venv/bin/python",
        "continuation_entrypoint": "/srv/bundle/source/scripts/fake_train.py",
        "method_gate_script": "/srv/bundle/source/scripts/verify_method_pass_gate.py",
        "evaluator_version": "e0_full_tail_v2",
        "selector_version": "validation-ndcg10-rowweighted-v1",
        "risk05_preregistration_sha256": "f" * 64,
        "risk14_arms": list(RISK14_ARMS),
        "risk14_selection": [
            {
                "rank": "high_risk",
                "dataset": "Beauty",
                "corruption_level": 100,
                "train_only": True,
                "selection_sha256": "1" * 64,
            },
            {
                "rank": "low_risk",
                "dataset": "Steam",
                "corruption_level": 0,
                "train_only": True,
                "selection_sha256": "2" * 64,
            },
        ],
        "estimates": {
            "method_gate": {"low": 0.0, "high": 0.0, "output_gib": 0.01},
            "risk13": {"low": 1.0, "high": 2.0, "output_gib": 0.2},
            "risk14": {"low": 0.5, "high": 1.0, "output_gib": 0.1},
            "risk10": {"low": 1.0, "high": 2.0, "output_gib": 0.2},
            "risk11": {"low": 1.0, "high": 2.0, "output_gib": 0.2},
        },
        "datasets": {
            dataset: {
                "dataset_dir": f"/srv/data/{dataset}",
                "split_sha256": ("3" if dataset == "Steam" else "4") * 64,
                "config_sha256": ("5" if dataset == "Steam" else "6") * 64,
                "bank_sha256": ("7" if dataset == "Steam" else "8") * 64,
            }
            for dataset in FOUR_DOMAINS
        },
    }


def _e1_marker() -> dict:
    return {
        "schema_version": 1,
        "risk_id": "RISK-02",
        "outcome": "pass",
        "random_seed": 100,
        "trace_steps": [0, 1, 100, 1000],
        "source_revision": "a" * 40,
    }


def _risk08_marker(e1: dict, e1_sha: str, prereg_sha: str) -> dict:
    marker = {
        "schema_version": 1,
        "risk_id": "RISK-08",
        "exit": "risk_gated_method",
        "e1_outcome": "pass",
        "e1_marker_sha256": e1_sha,
        "risk05_preregistration_sha256": prereg_sha,
    }
    marker["artifact_sha256"] = stable_sha256(marker)
    return marker


def _base_manifest(run_root: str) -> dict:
    return make_manifest(make_pilot_tasks("e1_pass", True) + make_pilot_tasks("e1_fail_audit", False), run_root=run_root)


class MethodPassContinuationAdapterTests(unittest.TestCase):
    def _build(self, root: Path, *, diffrec: dict | None = None, protocol: dict | None = None) -> dict:
        protocol = dict(protocol or _protocol())
        e1 = _write_json(root / "RISK-02_PASS.json", _e1_marker())
        e1_sha = sha256_file(e1)
        prereg_payload = {"protocol": "frozen-train-only"}
        prereg_sha = stable_sha256(prereg_payload)
        protocol["risk05_preregistration_sha256"] = prereg_sha
        risk08 = _write_json(root / "RISK-08_EXIT.json", _risk08_marker(json.loads(e1.read_text()), e1_sha, prereg_sha))
        prereg = _write_json(root / "risk05_preregistration.json", prereg_payload)
        audit = _write_json(root / "diffrec_audit.json", diffrec) if diffrec is not None else None
        return build_method_pass_manifest(
            protocol,
            _base_manifest(protocol["run_root"]),
            root / "method-pass-2026-07-11",
            e1_marker_path=e1,
            risk08_marker_path=risk08,
            risk05_preregistration_path=prereg,
            diffrec_audit_path=audit,
        )

    def test_builds_exact_seed100_continuation_matrix_and_validates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self._build(Path(tmp))
            continuation = [task for task in manifest["tasks"] if task["phase"] == "continuation"]
            self.assertEqual(1 + 8 + 12 + 12, len(continuation))
            self.assertEqual(8, sum(task["ledger_id"] == "RISK-13" for task in continuation))
            self.assertEqual(12, sum(task["ledger_id"] == "RISK-14" for task in continuation))
            self.assertEqual(12, sum(task["ledger_id"] == "RISK-10" for task in continuation))
            self.assertEqual(0, sum(task["ledger_id"] == "RISK-11" for task in continuation))
            self.assertTrue(all(task["seed"] == 100 for task in continuation if task["kind"] == "gpu"))
            self.assertTrue(all(task["max_attempts"] == 1 and task["failure_policy"] == "fail_closed" for task in continuation))
            self.assertEqual(len({task["run_dir"] for task in continuation}), len(continuation))
            self.assertTrue(all(task["evaluator_version"] == "e0_full_tail_v2" for task in continuation if task["kind"] == "gpu"))
            self.assertTrue(all(task["selector_version"] == "validation-ndcg10-rowweighted-v1" for task in continuation if task["kind"] == "gpu"))
            self.assertTrue(all(not any(token in task["argv"] for token in ("rm", "--force", "--no-skip-existing")) for task in continuation))
            validate_manifest(QueueManifest.from_dict(manifest))

    def test_diffrec_is_added_only_after_identity_and_memory_audit_pass(self) -> None:
        audit = {
            "schema_version": 1,
            "status": "pass",
            "model_identity": "DiffRec",
            "source_revision": "b" * 40,
            "config_sha256": "9" * 64,
            "split_sha256": "a" * 64,
            "peak_memory_gib": 10.0,
            "memory_limit_gib": 24.0,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._build(root, diffrec=audit)
            tasks = [task for task in manifest["tasks"] if task["ledger_id"] == "RISK-11"]
            self.assertEqual(4, len(tasks))
            self.assertEqual({"Steam", "ML1M", "Beauty", "ATG"}, {task["dataset"] for task in tasks})
            self.assertEqual({"RISK-11.DiffRec.four-domain"}, {task["atomic_group"] for task in tasks})
            validate_manifest(QueueManifest.from_dict(manifest))

            blocked = dict(audit, model_identity="DiffuRec")
            blocked_root = root / "blocked"
            blocked_root.mkdir()
            blocked_manifest = self._build(blocked_root, diffrec=blocked)
            self.assertEqual(0, sum(task["ledger_id"] == "RISK-11" for task in blocked_manifest["tasks"]))
            metadata = json.loads((blocked_root / "method-pass-2026-07-11" / "adapter_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("diffrec_blocked", metadata["diffrec_audit"]["status"])

    def test_gate_hash_selection_and_budget_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            protocol = _protocol()
            bad = dict(protocol, risk14_selection=[dict(protocol["risk14_selection"][0], train_only=False), protocol["risk14_selection"][1]])
            with self.assertRaisesRegex(ContinuationSafetyError, "train-only"):
                self._build(root, protocol=bad)

            too_expensive = _protocol()
            too_expensive["estimates"] = {name: {"low": 10.0, "high": 10.0, "output_gib": 0.1} for name in too_expensive["estimates"]}
            with self.assertRaisesRegex(ContinuationSafetyError, "168"):
                self._build(root, protocol=too_expensive)

            wrong_risk08 = _write_json(root / "wrong-risk08.json", {"exit": "audit_only"})
            e1 = _write_json(root / "e1.json", _e1_marker())
            prereg = _write_json(root / "prereg.json", {"artifact_sha256": protocol["risk05_preregistration_sha256"]})
            with self.assertRaisesRegex(ContinuationSafetyError, "risk_gated_method"):
                build_method_pass_manifest(
                    protocol,
                    _base_manifest(protocol["run_root"]),
                    root / "wrong-gate-2026-07-11",
                    e1_marker_path=e1,
                    risk08_marker_path=wrong_risk08,
                    risk05_preregistration_path=prereg,
                )

    def test_continuation_tasks_depend_on_method_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self._build(Path(tmp))
            gate_id = "continuation.method_pass_gate"
            self.assertEqual(1, sum(task["task_id"] == gate_id for task in manifest["tasks"]))
            for task in manifest["tasks"]:
                if task["phase"] == "continuation" and task["task_id"] != gate_id:
                    self.assertIn(gate_id, task["dependencies"])
                    self.assertIn("AAAI_RISK08_MARKER_SHA256", task["env"])

    def test_method_pass_gate_verifier_is_atomic_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "markers").mkdir()
            e1 = _e1_marker()
            e1_path = _write_json(root / "markers" / "RISK-02_PASS.json", e1)
            prereg_sha = stable_sha256({"protocol": "frozen-train-only"})
            risk08 = _risk08_marker(e1, sha256_file(e1_path), prereg_sha)
            risk08_path = _write_json(root / "markers" / "RISK-08_EXIT.json", risk08)
            result = verify_method_pass_gate(root, e1_path, risk08_path, prereg_sha)
            self.assertEqual("pass", result["status"])
            self.assertTrue((root / "state" / "method_pass_gate.json").is_file())
            with self.assertRaises(FileExistsError):
                verify_method_pass_gate(root, e1_path, risk08_path, prereg_sha)


if __name__ == "__main__":
    unittest.main()
