import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from aaai27_queue.models import QueueManifest
from aaai27_queue.validation import ManifestError, validate_manifest
from aaai27_queue_testdata import make_manifest, make_task


def make_pilot_tasks(branch: str, include_full: bool) -> list[dict]:
    tasks: list[dict] = []
    for dataset in ("Beauty", "Steam"):
        ledger_id = "RISK-06" if dataset == "Beauty" else "RISK-07"
        tasks.append(
            make_task(
                task_id=f"pilot.{branch}.{dataset}.host",
                ledger_id=ledger_id,
                phase="pilot",
                branch=branch,
                dataset=dataset,
                arm="host",
                argv=[
                    "/opt/venv/bin/python",
                    "/srv/bundle/source/single_train.py",
                    "graph.type=adaptive",
                ],
                success_artifacts=[
                    f"runs/{branch}/{dataset}/host/checkpoints-meta/"
                    f"{dataset}/best_summary_adaptive.json"
                ],
            )
        )
        for level in (0, 60, 100):
            tasks.append(
                make_task(
                    task_id=f"pilot.{branch}.{dataset}.anchor.c{level}",
                    ledger_id=ledger_id,
                    phase="pilot",
                    branch=branch,
                    dataset=dataset,
                    arm=f"text_anchor_only_c{level}",
                    argv=[
                        "/opt/venv/bin/python",
                        "/srv/bundle/source/single_train.py",
                        "graph.type=proposal_adaptive",
                    ],
                    success_artifacts=[
                        f"runs/{branch}/{dataset}/anchor_c{level}/"
                        f"checkpoints-meta/{dataset}/"
                        "best_summary_proposal_adaptive.json"
                    ],
                )
            )
            if include_full:
                tasks.append(
                    make_task(
                        task_id=f"pilot.{branch}.{dataset}.full.c{level}",
                        ledger_id=ledger_id,
                        phase="pilot",
                        branch=branch,
                        dataset=dataset,
                        arm=f"risk_gated_full_c{level}",
                        argv=[
                            "/opt/venv/bin/python",
                            "/srv/bundle/source/single_train.py",
                            "graph.type=proposal_adaptive",
                        ],
                        success_artifacts=[
                            f"runs/{branch}/{dataset}/full_c{level}/"
                            f"checkpoints-meta/{dataset}/"
                            "best_summary_proposal_adaptive.json"
                        ],
                    )
                )
    return tasks


def valid_pilots() -> list[dict]:
    return make_pilot_tasks("e1_pass", True) + make_pilot_tasks("e1_fail_audit", False)


def decoded(tasks: list[dict], **manifest_overrides) -> QueueManifest:
    return QueueManifest.from_dict(make_manifest(tasks, **manifest_overrides))


class QueueValidationTests(unittest.TestCase):
    def assert_invalid(self, task: dict, message: str) -> None:
        with self.assertRaisesRegex(ManifestError, message):
            validate_manifest(decoded([*valid_pilots(), task]))

    def test_complete_two_branch_pilot_manifest_is_valid(self) -> None:
        manifest = decoded(valid_pilots())

        validate_manifest(manifest)

        pass_tasks = [task for task in manifest.tasks if task.branch == "e1_pass"]
        audit_tasks = [task for task in manifest.tasks if task.branch == "e1_fail_audit"]
        self.assertEqual(14, len(pass_tasks))
        self.assertEqual(8, len(audit_tasks))
        self.assertEqual(6, sum("risk_gated_full" in (task.arm or "") for task in pass_tasks))
        self.assertEqual(0, sum("risk_gated_full" in (task.arm or "") for task in audit_tasks))

    def test_rejects_non_seed100_training(self) -> None:
        self.assert_invalid(make_task(task_id="bad.seed101", seed=101), "seed 100")
        self.assert_invalid(make_task(task_id="bad.seed102", seed=102), "seed 100")

    def test_rejects_diffurec_risk12_retry_and_non_fail_closed(self) -> None:
        self.assert_invalid(make_task(task_id="bad.diffurec", model="DiffuRec"), "DiffuRec")
        self.assert_invalid(make_task(task_id="bad.bert4rec", model="BERT4Rec"), "BERT4Rec")
        self.assert_invalid(make_task(task_id="bad.risk12", ledger_id="RISK-12"), "RISK-12")
        self.assert_invalid(make_task(task_id="bad.retry", max_attempts=2), "max_attempts")
        self.assert_invalid(make_task(task_id="bad.policy", failure_policy="continue"), "fail_closed")

    def test_rejects_destructive_argv_and_external_run_directory(self) -> None:
        for token in ("--force", "--no-skip-existing", "rm", "Remove-Item"):
            self.assert_invalid(
                make_task(task_id=f"bad.argv.{token}", argv=["python", "adapter.py", token]),
                "destructive",
            )
        self.assert_invalid(
            make_task(task_id="bad.root", run_dir="/data/Zijian/goal/RecDemoRuns/frozen"),
            "run_dir",
        )

    def test_rejects_hydra_work_dir_that_differs_from_task_run_dir(self) -> None:
        task = make_task(task_id="bad.work-dir")
        task["argv"] = [
            "python",
            "single_train.py",
            "work_dir=/data/Zijian/goal/aaai27_queue/dated/runs/collision",
        ]

        self.assert_invalid(task, "work_dir")

    def test_rejects_force_variants_and_overwrite_environment(self) -> None:
        self.assert_invalid(
            make_task(task_id="bad.force.assignment", argv=["python", "adapter.py", "--force=True"]),
            "destructive",
        )
        self.assert_invalid(
            make_task(task_id="bad.force.env", env={"FORCE": "1"}),
            "overwrite environment",
        )
        self.assert_invalid(
            make_task(task_id="bad.skip.env", env={"SKIP_EXISTING": "0"}),
            "overwrite environment",
        )

    def test_rejects_noncanonical_resource_contract(self) -> None:
        for gpu_ids in ([], [1, 1], [-1]):
            with self.subTest(gpu_ids=gpu_ids):
                with self.assertRaisesRegex(
                    ManifestError, "nonempty unique nonnegative"
                ):
                    validate_manifest(decoded(valid_pilots(), gpu_ids=gpu_ids))
        with self.assertRaisesRegex(ManifestError, "168 GPU-hours"):
            validate_manifest(decoded(valid_pilots(), gpu_budget_hours=169.0))
        with self.assertRaisesRegex(ManifestError, "40 GiB"):
            validate_manifest(decoded(valid_pilots(), min_free_disk_gib=39.0))

    def test_rejects_missing_or_extra_pilot_arms(self) -> None:
        missing = valid_pilots()
        missing.pop()
        with self.assertRaisesRegex(ManifestError, "8-run design"):
            validate_manifest(decoded(missing))

        bad = valid_pilots()
        for task in bad:
            if task["branch"] == "e1_fail_audit" and task["arm"] == "text_anchor_only_c60":
                task["arm"] = "risk_gated_full_c60"
                break
        with self.assertRaisesRegex(ManifestError, "8-run design"):
            validate_manifest(decoded(bad))

    def test_rejects_pilot_host_without_learned_adaptive_proposal(self) -> None:
        bad = valid_pilots()
        host = next(task for task in bad if task["arm"] == "host")
        host["argv"] = [
            "graph.type=hybrid" if token == "graph.type=adaptive" else token
            for token in host["argv"]
        ]

        with self.assertRaisesRegex(ManifestError, "AdaptiveWise"):
            validate_manifest(decoded(bad))

    def test_rejects_pilot_host_with_wrong_summary_identity(self) -> None:
        bad = valid_pilots()
        host = next(task for task in bad if task["arm"] == "host")
        host["success_artifacts"] = [
            path.replace("best_summary_adaptive.json", "best_summary_hybrid.json")
            for path in host["success_artifacts"]
        ]

        with self.assertRaisesRegex(ManifestError, "best_summary_adaptive"):
            validate_manifest(decoded(bad))

    def test_rejects_partial_classic_baseline_group(self) -> None:
        partial = [
            make_task(
                task_id=f"RISK-10.SASRec.{dataset}.seed100",
                ledger_id="RISK-10",
                phase="continuation",
                branch="method_pass",
                model="SASRec",
                dataset=dataset,
                atomic_group="RISK-10.SASRec.four-domain",
            )
            for dataset in ("Steam", "Beauty")
        ]
        with self.assertRaisesRegex(ManifestError, "all four domains"):
            validate_manifest(decoded([*valid_pilots(), *partial]))

    def test_rejects_unknown_dependency_and_cycle(self) -> None:
        self.assert_invalid(
            make_task(task_id="bad.dependency", dependencies=["missing.task"]),
            "unknown dependencies",
        )
        first = make_task(task_id="cycle.first", dependencies=["cycle.second"])
        second = make_task(task_id="cycle.second", dependencies=["cycle.first"])
        with self.assertRaisesRegex(ManifestError, "dependency cycle"):
            validate_manifest(decoded([*valid_pilots(), first, second]))


if __name__ == "__main__":
    unittest.main()
