from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT, REPO_ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.aaai27_adapters.common import sha256_file, stable_sha256
from scripts.aaai27_adapters.risk04_08 import _validate_artifact_manifest


WRAPPER = REPO_ROOT / "scripts" / "run_aaai27_pilot_task.py"


def valid_summary() -> dict[str, object]:
    return {
        "metric_name": "ndcg10",
        "best_step": 1000,
        "best_metric": 0.12,
        "validation": {
            "p5": {
                "hr": [0.01, 0.02, 0.03],
                "ndcg": [0.01, 0.02, 0.025],
            }
        },
        "test": {
            "p5": {
                "hr": [0.011, 0.021, 0.031],
                "ndcg": [0.011, 0.021, 0.026],
            }
        },
    }


class PilotTaskWrapperTests(unittest.TestCase):
    def _task_binding(self, env: dict[str, str], run_dir: Path) -> dict[str, object]:
        return {
            "task_id": env["AAAI_TASK_ID"],
            "run_dir": run_dir.as_posix(),
            "code_revision": env["AAAI_CODE_REVISION"],
            "config_sha256": env["AAAI_CONFIG_SHA256"],
            "split_sha256": env["AAAI_SPLIT_SHA256"],
            "bank_sha256": env["AAAI_BANK_SHA256"],
            "evaluator_version": env["AAAI_EVALUATOR_VERSION"],
            "selector_version": env["AAAI_SELECTOR_VERSION"],
            "arm": "risk_gated_full_c0",
            "success_artifacts": [
                env["AAAI_SUMMARY_RELATIVE"],
                env["AAAI_ARTIFACT_MANIFEST_RELATIVE"],
            ],
            "env": {key: value for key, value in env.items() if key.startswith("AAAI_")},
        }

    def _layout(self, root: Path) -> tuple[Path, Path, dict[str, str]]:
        queue_root = root / "queue-2026-07-12"
        run_dir = queue_root / "runs" / "e1_pass" / "Beauty" / "full_c0"
        run_dir.mkdir(parents=True)
        summary_relative = (
            "runs/e1_pass/Beauty/full_c0/checkpoints-meta/Beauty/"
            "best_summary_proposal_adaptive.json"
        )
        artifact_relative = "runs/e1_pass/Beauty/full_c0/artifact_manifest.json"
        task_id = "pilot.e1_pass.Beauty.full.c0"
        queue_manifest = queue_root / "queue" / "queue_seed100.json"
        queue_manifest.parent.mkdir(parents=True)
        queue_manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "queue_id": "r7-wrapper-test",
                    "tasks": [
                        {
                            "task_id": task_id,
                            "run_dir": run_dir.as_posix(),
                            "success_artifacts": [
                                summary_relative,
                                artifact_relative,
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        null_curve = root / "frozen" / "Beauty" / "agreement_null_curves.json"
        null_curve.parent.mkdir(parents=True)
        null_curve.write_text(json.dumps({"2": {"mu": 0.1, "sigma": 0.2}}), encoding="utf-8")
        env = {
            **os.environ,
            "AAAI_TASK_ID": task_id,
            "AAAI_QUEUE_ROOT": str(queue_root),
            "AAAI_RUN_DIR": str(run_dir),
            "AAAI_QUEUE_MANIFEST_PATH": str(queue_manifest),
            "AAAI_SUMMARY_RELATIVE": summary_relative,
            "AAAI_ARTIFACT_MANIFEST_RELATIVE": artifact_relative,
            "AAAI_CODE_REVISION": "a" * 40,
            "AAAI_CONFIG_SHA256": "b" * 64,
            "AAAI_SPLIT_SHA256": "c" * 64,
            "AAAI_BANK_SHA256": "d" * 64,
            "AAAI_EVALUATOR_VERSION": "e0_full_tail_v2",
            "AAAI_SELECTOR_VERSION": "validation-ndcg10-rowweighted-v1",
            "AAAI_NULL_CURVE_REFERENCE_POLICY": "frozen_clean_calibration",
            "AAAI_NULL_CURVE_PATH": str(null_curve),
            "AAAI_NULL_CURVE_SHA256": sha256_file(null_curve),
            "AAAI_NULL_CURVE_SOURCE_BANK_SHA256": "e" * 64,
            "AAAI_CURRENT_EMBEDDING_SHA256": "f" * 64,
            "AAAI_EMBEDDING_SHA256": "f" * 64,
            "AAAI_GATE_DATASET_SCALE": "1.0",
        }
        return queue_root, run_dir, env

    def _child_command(
        self,
        *,
        summary: dict[str, object] | None,
        exit_code: int = 0,
        output: str = "child-training-output",
    ) -> list[str]:
        statements = ["import json,sys", "from pathlib import Path"]
        if summary is not None:
            encoded = json.dumps(summary)
            statements.extend(
                [
                    "p=Path('checkpoints-meta/Beauty/best_summary_proposal_adaptive.json')",
                    "p.parent.mkdir(parents=True,exist_ok=True)",
                    f"p.write_text({encoded!r},encoding='utf-8')",
                ]
            )
        if output:
            statements.append(f"print({output!r},flush=True)")
        statements.append(f"sys.exit({int(exit_code)})")
        return [sys.executable, "-c", ";".join(statements)]

    def _run(
        self,
        root: Path,
        *,
        summary: dict[str, object] | None,
        exit_code: int = 0,
        output: str = "child-training-output",
        mutate_env=None,
    ):
        queue_root, run_dir, env = self._layout(root)
        if mutate_env is not None:
            mutate_env(env)
        completed = subprocess.run(
            [
                sys.executable,
                str(WRAPPER),
                "--",
                *self._child_command(
                    summary=summary, exit_code=exit_code, output=output
                ),
            ],
            cwd=run_dir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        return queue_root, run_dir, env, completed

    def test_success_streams_child_output_and_emits_validator_accepted_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            queue_root, run_dir, env, completed = self._run(
                Path(tmp), summary=valid_summary()
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertIn("child-training-output", completed.stdout)
            log_path = run_dir / "single_train.log"
            artifact_path = run_dir / "artifact_manifest.json"
            self.assertGreater(log_path.stat().st_size, 0)
            self.assertTrue(artifact_path.is_file())
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual("pass", artifact["status"])
            self.assertEqual(
                "frozen_clean_calibration",
                artifact["null_curve_reference"]["policy"],
            )
            self.assertEqual(
                env["AAAI_CURRENT_EMBEDDING_SHA256"],
                artifact["null_curve_reference"]["current_embedding_sha256"],
            )
            task = self._task_binding(env, run_dir)
            observed_hash = _validate_artifact_manifest(
                queue_root,
                artifact_path,
                task,
                sha256_file(queue_root / "queue" / "queue_seed100.json"),
            )
            self.assertEqual(sha256_file(artifact_path), observed_hash)

    def test_silent_success_still_has_a_nonempty_wrapper_audit_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, run_dir, _, completed = self._run(
                Path(tmp), summary=valid_summary(), output=""
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            log = (run_dir / "single_train.log").read_text(encoding="utf-8")
            self.assertIn("AAAI_PILOT_WRAPPER_START", log)
            self.assertIn("AAAI_PILOT_WRAPPER_END", log)

    def test_child_failure_preserves_nonempty_log_and_emits_no_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, run_dir, _, completed = self._run(
                Path(tmp), summary=None, exit_code=7, output="child-failed"
            )
            self.assertEqual(7, completed.returncode)
            self.assertGreater((run_dir / "single_train.log").stat().st_size, 0)
            self.assertFalse((run_dir / "artifact_manifest.json").exists())

    def test_missing_or_nonfinite_summary_fails_closed(self) -> None:
        for label, summary in (
            ("missing", None),
            ("nonfinite", {**valid_summary(), "best_metric": float("nan")}),
        ):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                _, run_dir, _, completed = self._run(Path(tmp), summary=summary)
                self.assertNotEqual(0, completed.returncode)
                self.assertFalse((run_dir / "artifact_manifest.json").exists())

    def test_path_escape_is_rejected_before_child_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, run_dir, _, completed = self._run(
                Path(tmp),
                summary=valid_summary(),
                mutate_env=lambda env: env.__setitem__(
                    "AAAI_SUMMARY_RELATIVE", "../outside.json"
                ),
            )
            self.assertNotEqual(0, completed.returncode)
            self.assertFalse((run_dir / "artifact_manifest.json").exists())

    def test_missing_frozen_null_provenance_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, run_dir, _, completed = self._run(
                Path(tmp),
                summary=valid_summary(),
                mutate_env=lambda env: env.pop("AAAI_NULL_CURVE_SHA256"),
            )
            self.assertNotEqual(0, completed.returncode)
            self.assertFalse((run_dir / "artifact_manifest.json").exists())

    def test_risk08_validator_rejects_empty_or_tampered_task_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            queue_root, run_dir, env, completed = self._run(
                Path(tmp), summary=valid_summary()
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            (run_dir / "single_train.log").write_bytes(b"")

            with self.assertRaisesRegex(ValueError, "log"):
                _validate_artifact_manifest(
                    queue_root,
                    run_dir / "artifact_manifest.json",
                    self._task_binding(env, run_dir),
                    sha256_file(queue_root / "queue" / "queue_seed100.json"),
                )

    def test_risk08_validator_rejects_rehashed_null_or_task_identity_mismatch(self) -> None:
        for field, mutate in (
            (
                "null",
                lambda artifact: artifact["null_curve_reference"].__setitem__(
                    "current_embedding_sha256", "0" * 64
                ),
            ),
            (
                "source",
                lambda artifact: artifact.__setitem__(
                    "source_revision", "0" * 40
                ),
            ),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                queue_root, run_dir, env, completed = self._run(
                    Path(tmp), summary=valid_summary()
                )
                self.assertEqual(0, completed.returncode, completed.stderr)
                artifact_path = run_dir / "artifact_manifest.json"
                artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
                mutate(artifact)
                artifact["artifact_sha256"] = stable_sha256(
                    {
                        key: value
                        for key, value in artifact.items()
                        if key != "artifact_sha256"
                    }
                )
                artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

                with self.assertRaisesRegex(ValueError, field):
                    _validate_artifact_manifest(
                        queue_root,
                        artifact_path,
                        self._task_binding(env, run_dir),
                        sha256_file(
                            queue_root / "queue" / "queue_seed100.json"
                        ),
                    )


if __name__ == "__main__":
    unittest.main()
