from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path, PurePosixPath

import torch


REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT, REPO_ROOT / "scripts", REPO_ROOT / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.aaai27_adapters.pilot_adapters import build_pilot_manifest
from scripts.aaai27_queue.models import QueueManifest
from scripts.aaai27_queue.validation import ManifestError, validate_manifest


def load_text_side_module():
    module_path = REPO_ROOT / "model" / "text_side.py"
    spec = importlib.util.spec_from_file_location("r7_text_side_contract", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_protocol(*, gpu_ids: list[int] | None = None) -> dict[str, object]:
    protocol: dict[str, object] = {
        "queue_id": "aaai27-risk0607-r6-contract-test",
        "created_at": "2026-07-11T20:30:00+08:00",
        "run_root": "/srv/aaai27/r6",
        "source_root": "/srv/aaai27/source-r6",
        "source_manifest_sha256": "a" * 64,
        "ledger_path": "/srv/aaai27/source-r6/issues/ledger.csv",
        "ledger_sha256": "b" * 64,
        "code_revision": "c" * 40,
        "config_sha256": "d" * 64,
        "python_bin": "/opt/prefergrow/bin/python3",
        "single_train": "/srv/aaai27/source-r6/single_train.py",
        "risk05_preregistration_sha256": "e" * 64,
        "training_overrides": ["training.n_iters=10"],
        "estimated_gpu_hours": {"low": 0.5, "high": 1.0, "output_gib": 0.2},
        "datasets": {
            dataset: {
                "dataset_dir": f"/srv/data/{dataset}",
                "split_sha256": "f" * 64,
                "text_bank_path": f"/srv/data/{dataset}/text_bank.csv",
                "null_curve_path": f"/srv/data/{dataset}/agreement_null_curves.json",
                "null_curve_sha256": "4" * 64,
                "config_sha256": "1" * 64,
                "banks": {
                    str(level): {
                        "embedding_path": f"/srv/banks/{dataset}/{level}/embeddings.pt",
                        "embedding_sha256": "2" * 64,
                        "bank_sha256": "3" * 64,
                        "phi_R": 1.0 - level / 100.0,
                    }
                    for level in (0, 60, 100)
                },
            }
            for dataset in ("Beauty", "Steam")
        },
    }
    if gpu_ids is not None:
        protocol["gpu_ids"] = gpu_ids
    return protocol


class R6LaunchContractTests(unittest.TestCase):
    def test_pilot_task_env_binds_wrapper_and_frozen_clean_null_provenance(self) -> None:
        manifest = build_pilot_manifest(make_protocol(gpu_ids=[0, 1]))

        for task in manifest["tasks"]:
            env = task["env"]
            self.assertEqual(task["task_id"], env["AAAI_TASK_ID"])
            self.assertEqual(manifest["run_root"], env["AAAI_QUEUE_ROOT"])
            self.assertEqual(task["run_dir"], env["AAAI_RUN_DIR"])
            self.assertEqual(
                f"{manifest['run_root']}/queue/queue_seed100.json",
                env["AAAI_QUEUE_MANIFEST_PATH"],
            )
            self.assertEqual(task["success_artifacts"][0], env["AAAI_SUMMARY_RELATIVE"])
            self.assertEqual(
                task["success_artifacts"][1],
                env["AAAI_ARTIFACT_MANIFEST_RELATIVE"],
            )
            self.assertEqual(task["code_revision"], env["AAAI_CODE_REVISION"])
            self.assertEqual(task["config_sha256"], env["AAAI_CONFIG_SHA256"])
            self.assertEqual(task["split_sha256"], env["AAAI_SPLIT_SHA256"])
            self.assertEqual(
                task["evaluator_version"], env["AAAI_EVALUATOR_VERSION"]
            )
            self.assertEqual(
                task["selector_version"], env["AAAI_SELECTOR_VERSION"]
            )
            if task["arm"] == "host":
                self.assertEqual(
                    "not_applicable", env["AAAI_NULL_CURVE_REFERENCE_POLICY"]
                )
                continue
            dataset_cfg = make_protocol(gpu_ids=[0, 1])["datasets"][task["dataset"]]
            self.assertEqual(
                "frozen_clean_calibration",
                env["AAAI_NULL_CURVE_REFERENCE_POLICY"],
            )
            self.assertEqual(
                dataset_cfg["null_curve_path"], env["AAAI_NULL_CURVE_PATH"]
            )
            self.assertEqual(
                dataset_cfg["null_curve_sha256"], env["AAAI_NULL_CURVE_SHA256"]
            )
            self.assertEqual(
                dataset_cfg["banks"]["0"]["bank_sha256"],
                env["AAAI_NULL_CURVE_SOURCE_BANK_SHA256"],
            )
            self.assertEqual(
                task["env"]["AAAI_EMBEDDING_SHA256"],
                env["AAAI_CURRENT_EMBEDDING_SHA256"],
            )

    def test_pilot_tasks_use_source_wrapper_and_require_summary_plus_manifest(self) -> None:
        manifest = build_pilot_manifest(make_protocol(gpu_ids=[0, 1]))
        expected_wrapper = "/srv/aaai27/source-r6/scripts/run_aaai27_pilot_task.py"

        for task in manifest["tasks"]:
            self.assertEqual(expected_wrapper, task["argv"][1], task["task_id"])
            self.assertEqual("--", task["argv"][2], task["task_id"])
            self.assertEqual(
                "/opt/prefergrow/bin/python3", task["argv"][3], task["task_id"]
            )
            self.assertEqual(
                "/srv/aaai27/source-r6/single_train.py",
                task["argv"][4],
                task["task_id"],
            )
            self.assertEqual(2, len(task["success_artifacts"]), task["task_id"])
            self.assertTrue(
                task["success_artifacts"][1].endswith("/artifact_manifest.json"),
                task["task_id"],
            )

    def test_e1_pass_anchor_tasks_bind_one_full_scale_and_no_utility_report(self) -> None:
        manifest = build_pilot_manifest(make_protocol(gpu_ids=[0, 1]))
        anchors = [
            task
            for task in manifest["tasks"]
            if task["branch"] == "e1_pass"
            and task["arm"].startswith("text_anchor_only_c")
        ]

        self.assertEqual(6, len(anchors))
        for task in anchors:
            scales = [
                token
                for token in task["argv"]
                if token.startswith("text_side.gate_dataset_scale_override=")
            ]
            reports = [
                token
                for token in task["argv"]
                if token.startswith("text_side.text_utility_report_path=")
            ]
            self.assertEqual(
                ["text_side.gate_dataset_scale_override=1.0"],
                scales,
                task["task_id"],
            )
            self.assertEqual([], reports, task["task_id"])

    def test_anchor_adapter_scale_prevents_phi_zero_final_proposal_core_override(self) -> None:
        manifest = build_pilot_manifest(make_protocol(gpu_ids=[0, 1]))
        task = next(
            task
            for task in manifest["tasks"]
            if task["task_id"] == "pilot.e1_pass.Beauty.anchor.c0"
        )
        scale_tokens = [
            token.split("=", 1)[1]
            for token in task["argv"]
            if token.startswith("text_side.gate_dataset_scale_override=")
        ]
        # Missing adapter scale reproduces the clean-phi-zero path that the
        # post-mixture closed-gate branch rewrites to p_core.
        adapter_scale = float(scale_tokens[0]) if scale_tokens else 0.0

        module = load_text_side_module()
        builder = module.TextSideProposalBuilder(
            item_embeddings=torch.tensor(
                [[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [-1.0, 0.0]],
                dtype=torch.float32,
            ),
            item_completeness=torch.ones(4),
            item_num=4,
            is_disliked_item=True,
            kernel_version="v2",
            injection_mode="kernel",
            ablation_mode="text_anchor_only",
            gate_dataset_scale=adapter_scale,
            g_max=0.5,
        )
        with torch.no_grad():
            builder.p1.copy_(torch.tensor([1.2, -0.4, 0.7, -1.1, 0.2]))
        context = builder.encode_history_context(
            torch.tensor([[0, 1, 2, 4]], dtype=torch.long)
        )

        self.assertFalse(
            torch.equal(context["proposal"], context["p_core"]),
            "anchor final proposal was silently overwritten by p_core",
        )
        self.assertTrue(
            torch.allclose(
                context["proposal"], context["anchor_proposal"], atol=1e-7
            )
        )
        self.assertTrue(
            torch.allclose(
                context["g"],
                torch.full_like(context["g"], builder.g_max),
                atol=1e-7,
            )
        )
        self.assertEqual(["1.0"], scale_tokens)

    def test_e1_pass_full_tasks_retain_exactly_one_frozen_scale(self) -> None:
        protocol = make_protocol(gpu_ids=[0, 1])
        manifest = build_pilot_manifest(protocol)
        full_tasks = [
            task
            for task in manifest["tasks"]
            if task["branch"] == "e1_pass"
            and task["arm"].startswith("risk_gated_full_c")
        ]

        self.assertEqual(6, len(full_tasks))
        for task in full_tasks:
            level = task["arm"].rsplit("c", 1)[-1]
            expected = float(protocol["datasets"][task["dataset"]]["banks"][level]["phi_R"])
            scales = [
                token.split("=", 1)[1]
                for token in task["argv"]
                if token.startswith("text_side.gate_dataset_scale_override=")
            ]
            self.assertEqual([str(expected)], scales, task["task_id"])
            self.assertEqual(str(expected), task["env"]["AAAI_GATE_DATASET_SCALE"])

    def test_e1_pass_full_c100_tasks_return_exact_core_proposal(self) -> None:
        manifest = build_pilot_manifest(make_protocol(gpu_ids=[0, 1]))
        c100_tasks = [
            task
            for task in manifest["tasks"]
            if task["branch"] == "e1_pass"
            and task["arm"] == "risk_gated_full_c100"
        ]

        self.assertEqual({"Beauty", "Steam"}, {task["dataset"] for task in c100_tasks})
        module = load_text_side_module()
        for task in c100_tasks:
            scales = [
                token.split("=", 1)[1]
                for token in task["argv"]
                if token.startswith("text_side.gate_dataset_scale_override=")
            ]
            self.assertEqual(["0.0"], scales, task["task_id"])
            self.assertIn("text_side.ablation_mode=none", task["argv"])

            builder = module.TextSideProposalBuilder(
                item_embeddings=torch.tensor(
                    [[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [-1.0, 0.0]],
                    dtype=torch.float32,
                ),
                item_completeness=torch.ones(4),
                item_num=4,
                is_disliked_item=True,
                kernel_version="v2",
                injection_mode="kernel",
                ablation_mode="none",
                gate_dataset_scale=float(scales[0]),
                g_max=0.5,
            )
            with torch.no_grad():
                builder.p1.copy_(torch.tensor([1.2, -0.4, 0.7, -1.1, 0.2]))
            context = builder.encode_history_context(
                torch.tensor([[0, 1, 2, 4]], dtype=torch.long)
            )

            self.assertTrue(torch.equal(context["g"], torch.zeros_like(context["g"])))
            self.assertTrue(
                torch.equal(context["proposal"], context["p_core"]),
                f"{task['task_id']} did not return the exact core proposal",
            )

    def test_pilot_manifest_copies_explicit_gpu1_allowlist(self) -> None:
        manifest = build_pilot_manifest(make_protocol(gpu_ids=[1]))

        self.assertEqual([1], manifest["gpu_ids"])

    def test_pilot_manifest_requires_explicit_gpu_allowlist(self) -> None:
        with self.assertRaisesRegex(ValueError, "gpu_ids"):
            build_pilot_manifest(make_protocol())

    def test_pilot_gpu_tasks_use_isolated_runtime_cwd_and_absolute_source_entry(self) -> None:
        manifest = build_pilot_manifest(make_protocol(gpu_ids=[1]))

        for task in manifest["tasks"]:
            self.assertEqual(task["run_dir"], task["cwd"], task["task_id"])
            self.assertTrue(PurePosixPath(task["argv"][0]).is_absolute(), task["task_id"])
            self.assertEqual(
                "/srv/aaai27/source-r6/scripts/run_aaai27_pilot_task.py",
                task["argv"][1],
                task["task_id"],
            )
            self.assertEqual("--", task["argv"][2], task["task_id"])
            self.assertEqual(
                "/srv/aaai27/source-r6/single_train.py",
                task["argv"][4],
                task["task_id"],
            )

    def test_validator_accepts_gpu1_only_isolated_pilot_manifest(self) -> None:
        manifest = QueueManifest.from_dict(
            build_pilot_manifest(make_protocol(gpu_ids=[1]))
        )

        validate_manifest(manifest)

    def test_validator_rejects_unsafe_gpu_allowlists(self) -> None:
        for gpu_ids in ([], [1, 1], [-1]):
            with self.subTest(gpu_ids=gpu_ids):
                raw = build_pilot_manifest(make_protocol(gpu_ids=[1]))
                raw["gpu_ids"] = gpu_ids
                with self.assertRaisesRegex(
                    ManifestError, "nonempty unique nonnegative"
                ):
                    validate_manifest(QueueManifest.from_dict(raw))

    def test_validator_rejects_gpu_task_cwd_that_differs_from_run_dir(self) -> None:
        raw = build_pilot_manifest(make_protocol(gpu_ids=[1]))
        raw["gpu_ids"] = [0, 1]
        raw["tasks"][0]["cwd"] = raw["source_root"]

        with self.assertRaisesRegex(ManifestError, "cwd must equal run_dir"):
            validate_manifest(QueueManifest.from_dict(raw))


if __name__ == "__main__":
    unittest.main()
