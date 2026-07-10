from __future__ import annotations

import importlib.util
import inspect
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "run_e01_gzero_trace.py"


def load_module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"missing script: {MODULE_PATH}")
    spec = importlib.util.spec_from_file_location("run_e01_gzero_trace", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def valid_e0_payload() -> dict:
    return {
        "schema_version": 1,
        "report_name": "E0 full-tail common-evaluator dated amendment",
        "execution": {
            "code_revision": "a" * 40,
            "completed_item_count": 18,
            "shards": [
                {"shard": 0, "item_finish_ids": [f"arm-{index}" for index in range(10)]},
                {"shard": 1, "item_finish_ids": [f"arm-{index}" for index in range(10, 18)]},
            ],
        },
        "metric_contract": {
            "version": "e0_full_tail_v2",
            "tail_batch_included": True,
            "aggregation_weight": "row",
            "candidate_universe": "all_mapped_real_catalog_items_exactly_once",
            "eval_seed": 100,
        },
        "matrix_validation": {
            "artifact_count": 18,
            "expected_artifact_count": 18,
            "all_contract_checks_pass": True,
        },
    }


def minimal_configs() -> dict[str, dict]:
    base = {
        "random_seed": 100,
        "work_dir": "/trace/host",
        "loss_type": "score_entropy",
        "training": {
            "data": "Beauty",
            "batch_size": 256,
            "accum": 1,
            "nonpreference_user_ratio": 0.1,
            "early_stop_patience": 5,
            "early_stop_min_step": 5000,
            "best_selection_min_step": 0,
            "early_stop_metric": "ndcg10",
            "early_stop_strength": "p5",
            "early_stop_min_delta": 0.0,
        },
        "data": {"Beauty": {"path": "/dataset/Beauty", "item_num": 12101, "seq_len": 10}},
        "graph": {"type": "adaptive", "is_disliked_item": True, "gamma": 0.5},
        "model": {"hidden_size": 256, "cond_dim": 256, "score_flag": False, "score_method": "oricos"},
        "sampling": {"predictor": "analytic", "steps": 20, "personalization_strength": 2},
        "optim": {"optimizer": "AdamW", "lr": 0.0001, "warmup": 2500, "grad_clip": 1.0},
        "text_side": {
            "enabled": False,
            "kernel_version": "v2",
            "ablation_mode": "none",
            "injection_mode": "kernel",
            "text_utility_report_path": "/assets/utility.json",
        },
    }
    host = json.loads(json.dumps(base))
    full = json.loads(json.dumps(base))
    global_p = json.loads(json.dumps(base))
    full["work_dir"] = "/trace/final_v2_closed_gate_full"
    global_p["work_dir"] = "/trace/global_p"
    for config in (full, global_p):
        config["graph"]["type"] = "proposal_adaptive"
        config["text_side"]["enabled"] = True
    global_p["text_side"]["ablation_mode"] = "global_p"
    return {
        "host": host,
        "final_v2_closed_gate_full": full,
        "global_p": global_p,
    }


class E01GZeroTraceTests(unittest.TestCase):
    def test_protocol_constants_are_frozen_before_observation(self) -> None:
        module = load_module()

        self.assertEqual("Beauty", module.DATASET_NAME)
        self.assertEqual(100, module.RANDOM_SEED)
        self.assertEqual((0, 1, 100, 1000), module.TRACE_STEPS)
        self.assertEqual(1e-6, module.FP32_TOLERANCE)
        self.assertEqual(
            ("host", "final_v2_closed_gate_full", "global_p"),
            module.ARM_NAMES,
        )
        self.assertIn("ML1M", module.PROTOCOL_SCOPE_DECISION)
        self.assertIn("hybrid", module.PROTOCOL_SCOPE_DECISION)

    def test_e0_amendment_gate_fails_closed(self) -> None:
        module = load_module()
        accepted = module.validate_e0_amendment_payload(valid_e0_payload())
        self.assertEqual("a" * 40, accepted["code_revision"])

        for field_path, replacement in (
            (("execution", "completed_item_count"), 17),
            (("matrix_validation", "artifact_count"), 17),
            (("matrix_validation", "all_contract_checks_pass"), False),
            (("metric_contract", "eval_seed"), 99),
        ):
            with self.subTest(field_path=field_path):
                payload = valid_e0_payload()
                cursor = payload
                for key in field_path[:-1]:
                    cursor = cursor[key]
                cursor[field_path[-1]] = replacement
                with self.assertRaisesRegex(ValueError, "E0 prerequisite"):
                    module.validate_e0_amendment_payload(payload)

    def test_synced_e0_amendment_is_an_authoritative_fixture(self) -> None:
        module = load_module()
        fixture = (
            REPO_ROOT
            / "docs"
            / "reports"
            / "data"
            / "2026-07-10-evaluator-amendment"
            / "e0_evaluator_amendment.json"
        )
        self.assertTrue(fixture.is_file(), f"missing synchronized E0 fixture: {fixture}")
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        accepted = module.validate_e0_amendment_payload(payload)
        self.assertEqual(18, accepted["artifact_count"])
        self.assertEqual(18, accepted["completed_item_count"])
        file_evidence = module.validate_e0_amendment_file(fixture)
        self.assertEqual(
            "d1b6664178b5880989c2ee2d3959c1ec6d1c67c4",
            file_evidence["code_revision"],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tampered = Path(tmpdir) / "e0.json"
            tampered.write_text(
                fixture.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "authoritative E0 amendment hash mismatch"):
                module.validate_e0_amendment_file(tampered)

    def test_config_whitelist_accepts_only_the_three_production_path_differences(self) -> None:
        module = load_module()
        configs = minimal_configs()
        result = module.validate_config_contract(configs)
        self.assertEqual("p5", result["selector"]["early_stop_strength"])
        self.assertEqual("ndcg10", result["selector"]["early_stop_metric"])
        self.assertEqual(0, result["selector"]["best_selection_min_step"])

        configs["global_p"]["optim"]["lr"] = 0.001
        with self.assertRaisesRegex(ValueError, "config mismatch.*optim.lr"):
            module.validate_config_contract(configs)

    def test_batch_order_and_rng_metadata_mismatch_fail_closed(self) -> None:
        module = load_module()
        matching = {arm: "same-hash" for arm in module.ARM_NAMES}
        self.assertEqual("same-hash", module.require_identical_arm_metadata("batch_order", matching))

        mismatched = dict(matching)
        mismatched["global_p"] = "other-hash"
        with self.assertRaisesRegex(ValueError, "batch_order mismatch"):
            module.require_identical_arm_metadata("batch_order", mismatched)

    def test_rng_state_round_trip_covers_python_numpy_and_torch(self) -> None:
        module = load_module()
        random.seed(91)
        np.random.seed(91)
        torch.manual_seed(91)
        state = module.capture_rng_state(include_cuda=False)
        metadata = module.rng_state_metadata(state)
        first = (random.random(), float(np.random.rand()), torch.rand(3))

        module.restore_rng_state(state)
        second = (random.random(), float(np.random.rand()), torch.rand(3))

        self.assertEqual(first[0], second[0])
        self.assertEqual(first[1], second[1])
        self.assertTrue(torch.equal(first[2], second[2]))
        self.assertEqual(64, len(metadata["combined_sha256"]))

    def test_trace_start_rng_normalization_preserves_constructor_provenance(self) -> None:
        module = load_module()
        construction_states = {}
        for arm, burn_count in (("host", 0), ("final_v2_closed_gate_full", 7), ("global_p", 13)):
            random.seed(100)
            np.random.seed(100)
            torch.manual_seed(100)
            for _ in range(burn_count):
                random.random()
                np.random.rand()
                torch.rand(1)
            construction_states[arm] = module.capture_rng_state(include_cuda=False)

        runtimes = {
            arm: SimpleNamespace(name=arm, rng_state=state)
            for arm, state in construction_states.items()
        }
        random.seed(100)
        np.random.seed(100)
        torch.manual_seed(100)
        trace_start_state = module.capture_rng_state(include_cuda=False)

        evidence = module.normalize_trace_start_rng(
            runtimes,
            trace_start_state=trace_start_state,
        )

        construction_hashes = {
            arm: evidence["construction"][arm]["combined_sha256"]
            for arm in module.ARM_NAMES
        }
        normalized_hashes = {
            arm: module.rng_state_metadata(runtimes[arm].rng_state)["combined_sha256"]
            for arm in module.ARM_NAMES
        }
        self.assertEqual(3, len(set(construction_hashes.values())))
        self.assertEqual(1, len(set(normalized_hashes.values())))
        self.assertEqual(
            evidence["trace_start"]["combined_sha256"],
            next(iter(normalized_hashes.values())),
        )
        self.assertEqual(
            evidence["trace_start"]["combined_sha256"],
            runtimes["host"].trace_start_rng_metadata["combined_sha256"],
        )

    def test_sampling_probe_uses_a_common_forked_rng_without_advancing_training_rng(self) -> None:
        module = load_module()
        torch.manual_seed(123)
        training_state = module.capture_rng_state(include_cuda=False)

        def fake_sampling_fn(_model, shape, history):
            return torch.rand((shape[0], 1, 3)) + history[:, :1].unsqueeze(-1)

        first = module.run_forked_sampling_probe(
            model=object(),
            sampling_fn=fake_sampling_fn,
            history=torch.zeros((2, 2)),
            probe_seed=10_101,
            training_rng_state=training_state,
            include_cuda=False,
        )
        value_after_probe = torch.rand(2)
        module.restore_rng_state(training_state)
        expected_after_probe = torch.rand(2)
        second = module.run_forked_sampling_probe(
            model=object(),
            sampling_fn=fake_sampling_fn,
            history=torch.zeros((2, 2)),
            probe_seed=10_101,
            training_rng_state=training_state,
            include_cuda=False,
        )

        self.assertTrue(torch.equal(first, second))
        self.assertTrue(torch.equal(value_after_probe, expected_after_probe))

    def test_initial_sampling_rng_diagnostic_records_without_advancing_rng(self) -> None:
        module = load_module()
        random.seed(100)
        np.random.seed(100)
        torch.manual_seed(100)
        initial_state = module.capture_rng_state(include_cuda=False)

        batches = [
            {"seq": torch.zeros((2, 3), dtype=torch.long)},
            {"seq": torch.ones((1, 3), dtype=torch.long)},
        ]

        class FakeUtils:
            @staticmethod
            def evaluate_loader(model, sampling_fn, data_loader, device, valid_item_count):
                del model, device, valid_item_count
                for batch in data_loader:
                    sampling_fn(object(), (batch["seq"].shape[0], 1), batch["seq"])
                return [0.0], [0.0]

        runtime = SimpleNamespace(
            name="host",
            rng_state=initial_state,
            sampling_fns={"p2": {"fn": lambda _model, _dims, _history: torch.zeros(1)}},
            val_loader=batches,
            device=torch.device("cpu"),
            model=object(),
            graph=SimpleNamespace(
                sample_nonpreference=lambda *_args, **_kwargs: torch.zeros((2, 1), dtype=torch.long)
            ),
            initial_sampling_rng_trace={},
        )

        module._run_initial_production_sampling(runtime, FakeUtils)

        self.assertEqual(2, runtime.initial_sampling_rng_trace["sampling_call_count"])
        self.assertEqual(
            runtime.initial_sampling_rng_trace["before_eval"]["combined_sha256"],
            runtime.initial_sampling_rng_trace["after_eval"]["combined_sha256"],
        )
        self.assertEqual(
            runtime.initial_sampling_rng_trace["iterator_before"]["combined_sha256"],
            runtime.initial_sampling_rng_trace["iterator_after"]["combined_sha256"],
        )

    def test_initial_sampling_graph_probe_records_probability_layout_and_output(self) -> None:
        module = load_module()
        random.seed(100)
        np.random.seed(100)
        torch.manual_seed(100)
        initial_state = module.capture_rng_state(include_cuda=False)

        class FakeModel:
            def encode_history_context(self, history):
                return {
                    "proposal": torch.full(
                        (history.shape[0], 4),
                        0.25,
                        dtype=torch.float32,
                    )
                }

        class FakeGraph:
            def sample_nonpreference(self, *batch_dims, proposal=None):
                self.last_proposal = proposal
                import graph_lib

                probability_rows = proposal.unsqueeze(1).expand(
                    batch_dims[0], batch_dims[1], proposal.shape[-1]
                )
                return graph_lib._sample_probability_rows(probability_rows, batch_dims)

        graph = FakeGraph()
        model = FakeModel()

        class FakeUtils:
            @staticmethod
            def evaluate_loader(model_arg, sampling_fn, data_loader, device, valid_item_count):
                del model_arg, device, valid_item_count
                for batch in data_loader:
                    sampling_fn(model, (batch["seq"].shape[0], 1), batch["seq"])
                return [0.0], [0.0]

        runtime = SimpleNamespace(
            name="proposal",
            rng_state=initial_state,
            sampling_fns={"p2": {"fn": lambda model_arg, dims, history: graph.sample_nonpreference(
                *dims,
                proposal=model_arg.encode_history_context(history)["proposal"],
            )}},
            val_loader=[{"seq": torch.zeros((2, 3), dtype=torch.long)}],
            device=torch.device("cpu"),
            model=model,
            graph=graph,
            initial_sampling_rng_trace={},
        )

        module._run_initial_production_sampling(runtime, FakeUtils)

        graph_probe = runtime.initial_sampling_rng_trace["first_call_stage_probe"][
            "graph_initial"
        ]
        self.assertIn("probability_rows", graph_probe)
        self.assertIn("input", graph_probe["probability_rows"])
        self.assertIn("output", graph_probe["probability_rows"])
        self.assertEqual([2, 1, 4], graph_probe["probability_rows"]["input"]["shape"])
        self.assertEqual(
            [2, 1], graph_probe["probability_rows"]["output"]["shape"]
        )
        self.assertEqual(
            graph_probe["probability_rows"]["input"]["dtype"],
            "torch.float32",
        )

    def test_execution_failure_report_preserves_traceback_and_context(self) -> None:
        module = load_module()
        try:
            raise NotImplementedError("amp backend probe")
        except NotImplementedError as exc:
            report = module.build_execution_failure_report(
                exc,
                context={
                    "phase": "training",
                    "arm": "host",
                    "trace_step": 1,
                    "device": "cuda:1",
                    "scaler_enabled": True,
                },
            )

        self.assertEqual("NotImplementedError", report["exception"]["type"])
        self.assertIn("amp backend probe", report["exception"]["message"])
        self.assertIn("test_execution_failure_report_preserves_traceback", report["exception"]["traceback"])
        self.assertEqual("training", report["execution_context"]["phase"])
        self.assertEqual(1, report["execution_context"]["trace_step"])

    def test_asset_fingerprints_bind_bank_split_null_curve_and_utility(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_dir = Path(tmpdir) / "Beauty"
            dataset_dir.mkdir()
            text_bank = dataset_dir / "text_bank.csv"
            embeddings = dataset_dir / "sentence_t5_xl_item_emb.pt"
            split = dataset_dir / "train_data.df"
            null_curve = dataset_dir / "agreement_null_curves.json"
            utility = Path(tmpdir) / "utility.json"
            text_bank.write_bytes(b"bank")
            embeddings.write_bytes(b"embeddings")
            split.write_bytes(b"split")
            null_curve.write_bytes(b"null")

            expected = module.compute_asset_fingerprints(
                dataset_dir=dataset_dir,
                text_utility_report_path=utility,
                allow_missing_utility=True,
            )
            utility_payload = {
                "datasets": [
                    {
                        "dataset": "Beauty",
                        "bank_hash": expected["bank_hash"],
                        "split_hash": expected["split_hash"],
                        "phi_u_ds": 0.0,
                        "u_ds_popularity": 0.7124275,
                    }
                ]
            }
            utility.write_text(json.dumps(utility_payload), encoding="utf-8")
            expected = module.compute_asset_fingerprints(dataset_dir, utility)

            result = module.validate_beauty_asset_contract(
                dataset_dir,
                utility,
                expected_fingerprints=expected,
                require_runtime_item_count=False,
            )
            self.assertEqual(0.0, result["phi_u_ds"])

            bad_expected = dict(expected)
            bad_expected["split_hash"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "Beauty asset hash mismatch.*split_hash"):
                module.validate_beauty_asset_contract(
                    dataset_dir,
                    utility,
                    expected_fingerprints=bad_expected,
                    require_runtime_item_count=False,
                )

    def test_checkpoint_comparison_reports_stable_first_divergence(self) -> None:
        module = load_module()
        snapshots = {
            "host": {
                "parameters": {"model.weight": torch.tensor([1.0, 2.0])},
                "optimizer": {"core_proposal_logits.in_optimizer": False},
                "rng": {"combined_sha256": "rng"},
            },
            "final_v2_closed_gate_full": {
                "parameters": {"model.weight": torch.tensor([1.0, 2.0 + 5e-7])},
                "optimizer": {"core_proposal_logits.in_optimizer": True},
                "rng": {"combined_sha256": "rng"},
            },
            "global_p": {
                "parameters": {"model.weight": torch.tensor([1.0, 2.0])},
                "optimizer": {"core_proposal_logits.in_optimizer": True},
                "rng": {"combined_sha256": "rng"},
            },
        }

        checkpoint = module.compare_checkpoint_snapshots(step=0, snapshots=snapshots)

        self.assertEqual("fail", checkpoint["status"])
        self.assertEqual("optimizer", checkpoint["first_divergence"]["category"])
        self.assertEqual(
            "core_proposal_logits.in_optimizer",
            checkpoint["first_divergence"]["key"],
        )
        parameter_rows = [
            row for row in checkpoint["comparisons"]
            if row["category"] == "parameters" and row["arm"] == "final_v2_closed_gate_full"
        ]
        self.assertEqual("pass", parameter_rows[0]["status"])
        self.assertLessEqual(parameter_rows[0]["max_abs_diff"], module.FP32_TOLERANCE)

    def test_float_difference_above_frozen_tolerance_is_a_failure(self) -> None:
        module = load_module()
        snapshots = {
            arm: {"loss_terms": {"loss": torch.tensor([1.0])}}
            for arm in module.ARM_NAMES
        }
        snapshots["global_p"]["loss_terms"]["loss"] = torch.tensor([1.0 + 2e-6])

        checkpoint = module.compare_checkpoint_snapshots(step=1, snapshots=snapshots)

        self.assertEqual("fail", checkpoint["status"])
        self.assertEqual("global_p", checkpoint["first_divergence"]["arm"])
        self.assertGreater(checkpoint["first_divergence"]["max_abs_diff"], 1e-6)

    def test_nonfinite_tensor_is_reported_without_emitting_nonstandard_json(self) -> None:
        module = load_module()
        snapshots = {
            arm: {"loss_terms": {"loss": torch.tensor([1.0])}}
            for arm in module.ARM_NAMES
        }
        snapshots["global_p"]["loss_terms"]["loss"] = torch.tensor([float("nan")])
        checkpoint = module.compare_checkpoint_snapshots(step=1, snapshots=snapshots)

        self.assertEqual("fail", checkpoint["status"])
        self.assertIsNone(checkpoint["first_divergence"]["max_abs_diff"])
        json.dumps(checkpoint, allow_nan=False)

    def test_optimizer_snapshot_preserves_real_parameter_membership(self) -> None:
        module = load_module()
        optimized = torch.nn.Parameter(torch.tensor([1.0]))
        omitted = torch.nn.Parameter(torch.tensor([2.0]))
        optimizer = torch.optim.AdamW([optimized], lr=1e-3)
        snapshot = module.snapshot_optimizer_state(
            optimizer,
            {"model.weight": optimized, "core_proposal_logits": omitted},
        )

        self.assertTrue(snapshot["model.weight.in_optimizer"])
        self.assertFalse(snapshot["core_proposal_logits.in_optimizer"])
        self.assertEqual(0, snapshot["model.weight.state_field_count"])

    def test_optimizer_membership_is_the_first_real_topology_difference(self) -> None:
        module = load_module()
        snapshots = {}
        for arm in module.ARM_NAMES:
            common = torch.nn.Parameter(torch.tensor([1.0]))
            core = torch.nn.Parameter(torch.tensor([2.0]))
            parameters = [common] if arm == "host" else [common, core]
            optimizer = torch.optim.AdamW(parameters, lr=1e-3)
            snapshots[arm] = {
                "optimizer": module.snapshot_optimizer_state(
                    optimizer,
                    {"model.weight": common, "core_proposal_logits": core},
                )
            }
        checkpoint = module.compare_checkpoint_snapshots(step=0, snapshots=snapshots)

        self.assertEqual(
            "core_proposal_logits.in_optimizer",
            checkpoint["first_divergence"]["key"],
        )

    def test_canonical_initialization_copy_aligns_values_without_changing_topology(self) -> None:
        module = load_module()

        class HostModel(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.body = torch.nn.Linear(2, 2, bias=False)

        class Builder(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.p1 = torch.nn.Parameter(torch.zeros(3))
                self.register_buffer("item_embeddings", torch.ones(3, 2))

        class ProposalModel(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.body = torch.nn.Linear(2, 2, bias=False)
                self.text_side_builder = Builder()

        class HostGraph(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.p1 = torch.nn.Parameter(torch.tensor([1.0, 2.0, 3.0]))

        host_model = HostModel()
        proposal_model = ProposalModel()
        host_graph = HostGraph()
        before_parameter_names = tuple(name for name, _ in proposal_model.named_parameters())

        result = module.copy_host_initialization_to_proposal(
            host_model=host_model,
            host_graph=host_graph,
            proposal_model=proposal_model,
        )

        self.assertTrue(torch.equal(host_model.body.weight, proposal_model.body.weight))
        self.assertTrue(
            torch.equal(host_graph.p1, proposal_model.text_side_builder.p1)
        )
        self.assertEqual(
            before_parameter_names,
            tuple(name for name, _ in proposal_model.named_parameters()),
        )
        self.assertIn("text_side_builder.p1", result["expected_missing_keys"])

    def test_graph_trace_proxy_records_real_loss_boundary_values(self) -> None:
        module = load_module()

        class FakeGraph:
            def sample_prob(self, target, sigma, proposal=None):
                return target + 1

            def score_entropy(self, score, sigma, noisy, target, proposal=None):
                return score.sum(dim=-1)

        proxy = module.GraphTraceProxy(FakeGraph())
        proposal = torch.tensor([[0.25, 0.75]])
        sampled = proxy.sample_prob(
            torch.tensor([[0]]), torch.tensor([[0.5]]), proposal=proposal
        )
        raw_loss = proxy.score_entropy(
            torch.tensor([[[1.0, 2.0]]]),
            torch.tensor([[0.5]]),
            sampled,
            torch.tensor([0]),
            proposal=proposal,
        )

        self.assertTrue(torch.equal(torch.tensor([[1]]), sampled))
        self.assertTrue(torch.equal(torch.tensor([[3.0]]), raw_loss))
        self.assertTrue(torch.equal(proposal, proxy.records["proposal_rows"]))
        self.assertIn("raw_score_entropy", proxy.records)

    def test_report_selects_earliest_checkpoint_divergence_and_freezes_scope(self) -> None:
        module = load_module()
        step0 = {
            "step": 0,
            "status": "pass",
            "first_divergence": None,
            "comparisons": [],
        }
        step1 = {
            "step": 1,
            "status": "fail",
            "first_divergence": {"step": 1, "category": "parameters", "key": "p1"},
            "comparisons": [],
        }
        step100 = {"step": 100, "status": "pass", "first_divergence": None, "comparisons": []}
        step1000 = {"step": 1000, "status": "pass", "first_divergence": None, "comparisons": []}
        report = module.build_trace_report(
            e0={"code_revision": "a" * 40},
            assets={"phi_u_ds": 0.0},
            config_contract={"status": "pass"},
            checkpoints=[step0, step1, step100, step1000],
            source_manifest=module.production_call_path_manifest(),
        )

        self.assertEqual("fail", report["status"])
        self.assertEqual(1, report["first_divergence"]["step"])
        self.assertEqual("Beauty", report["protocol"]["dataset"])
        self.assertIn("ML1M", report["protocol"]["scope_decision"])

        with self.assertRaisesRegex(ValueError, "trace checkpoint steps mismatch"):
            module.build_trace_report(
                e0={"code_revision": "a" * 40},
                assets={"phi_u_ds": 0.0},
                config_contract={"status": "pass"},
                checkpoints=[step0, step1],
                source_manifest=module.production_call_path_manifest(),
            )

    def test_failed_trace_never_writes_a_pass_marker(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "e01"
            failed_report = {
                "schema_version": 1,
                "status": "fail",
                "first_divergence": {"step": 0, "category": "optimizer"},
            }
            module.write_trace_artifacts(output_dir, failed_report)
            self.assertTrue((output_dir / "e01_gzero_trace.json").is_file())
            self.assertFalse((output_dir / "E01_PASS.json").exists())

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "e01"
            passed_report = {"schema_version": 1, "status": "pass", "first_divergence": None}
            module.write_trace_artifacts(output_dir, passed_report)
            marker = json.loads((output_dir / "E01_PASS.json").read_text(encoding="utf-8"))
            self.assertEqual("pass", marker["status"])
            self.assertEqual([0, 1, 100, 1000], marker["trace_steps"])
            self.assertEqual(1e-6, marker["fp32_tolerance"])

    def test_failure_trace_writes_structured_report_into_precreated_empty_directory(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "e01"
            output_dir.mkdir()
            failed_report = {
                "schema_version": 1,
                "status": "fail",
                "first_divergence": {"step": None, "category": "preflight_or_execution_error"},
            }
            report_path = module.write_trace_artifacts(output_dir, failed_report, allow_existing_empty=True)
            self.assertEqual(output_dir / "e01_gzero_trace.json", report_path)
            self.assertTrue(report_path.is_file())
            self.assertFalse((output_dir / "E01_PASS.json").exists())

    def test_cli_requires_explicit_execute_flag_and_exposes_no_tolerance_seed_or_step_override(self) -> None:
        module = load_module()
        parser = module.build_parser()
        option_strings = {
            option
            for action in parser._actions
            for option in action.option_strings
        }
        self.assertIn("--execute-production-trace", option_strings)
        self.assertNotIn("--seed", option_strings)
        self.assertNotIn("--trace-steps", option_strings)
        self.assertNotIn("--tolerance", option_strings)

    def test_script_bootstraps_repo_imports_outside_the_repo_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            command = (
                "import runpy; "
                f"runpy.run_path({str(MODULE_PATH)!r}, run_name='e01_import_probe'); "
                "import data, graph_lib, losses, sampling; "
                "print('repo-imports-ok')"
            )
            result = subprocess.run(
                [sys.executable, "-c", command],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("repo-imports-ok", result.stdout)

    def test_production_call_path_manifest_names_required_anchors(self) -> None:
        module = load_module()
        manifest = module.production_call_path_manifest()
        joined = json.dumps(manifest, sort_keys=True)
        for anchor in (
            "single_train.py",
            "model/text_side.py:502",
            "graph_lib.py:1312",
            "losses.py:11",
            "sampling.py:58",
        ):
            self.assertIn(anchor, joined)

    def test_arm_configs_are_composed_from_the_frozen_beauty_production_contract(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            configs = module.build_arm_configs(
                dataset_dir=root / "Beauty",
                text_utility_report_path=root / "utility.json",
                output_dir=root / "trace-output",
            )
        plain = module.configs_to_plain_dicts(configs)
        contract = module.validate_config_contract(plain)
        self.assertEqual("pass", contract["status"])
        self.assertEqual("adaptive", plain["host"]["graph"]["type"])
        self.assertEqual(
            "proposal_adaptive",
            plain["final_v2_closed_gate_full"]["graph"]["type"],
        )
        self.assertEqual(
            "global_p",
            plain["global_p"]["text_side"]["ablation_mode"],
        )

    def test_main_is_wired_to_the_production_trace_runner_without_a_placeholder_exit(self) -> None:
        module = load_module()
        self.assertTrue(hasattr(module, "run_production_trace"))
        main_source = inspect.getsource(module.main)
        runner_source = inspect.getsource(module.run_production_trace)
        self.assertIn("run_production_trace(args)", main_source)
        for production_symbol in (
            "graph_lib.get_graph",
            "SEDD4REC",
            "noise_lib.get_noise",
            "losses.get_optimizer",
            "losses.get_step_fn",
            "data.get_seqdataloader",
            "sampling.get_sampling_fn",
        ):
            self.assertIn(production_symbol, runner_source)


if __name__ == "__main__":
    unittest.main()
