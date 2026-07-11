import tempfile
import unittest
from pathlib import Path
import sys
import importlib.util
import json
import hashlib

import pandas as pd
import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MODULE_PATH = REPO_ROOT / "model" / "text_side.py"


def load_module():
    spec = importlib.util.spec_from_file_location("text_side", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TextSideProposalTests(unittest.TestCase):
    def test_v2_disliked_kernel_uses_core_pseudo_mass_and_gated_real_item_mixture(self) -> None:
        module = load_module()
        builder = module.TextSideProposalBuilder(
            item_embeddings=torch.tensor(
                [
                    [1.0, 0.0],
                    [0.9, 0.1],
                    [0.0, 1.0],
                    [-1.0, 0.0],
                ],
                dtype=torch.float32,
            ),
            item_completeness=torch.tensor([1.0, 1.0, 0.0, 1.0], dtype=torch.float32),
            item_num=4,
            is_disliked_item=True,
            kernel_version="v2",
            g_max=0.5,
            temperature=0.2,
        )
        with torch.no_grad():
            builder.p1.copy_(torch.tensor([2.0, 0.5, -0.5, -1.0, 1.5], dtype=torch.float32))

        history = torch.tensor([[0, 1, 0, 4]], dtype=torch.long)
        context = builder.encode_history_context(history)

        self.assertIn("p_core", context)
        self.assertIn("content_anchor", context)
        self.assertIn("u_tilde", context)
        self.assertIn("g", context)

        p_core = context["p_core"][0]
        g = float(context["g"][0])
        real_core = p_core[:-1] / p_core[:-1].sum()
        expected_real = (1.0 - g) * real_core + g * context["content_anchor"][0]
        expected_proposal = torch.cat(
            [
                expected_real * (1.0 - p_core[-1]),
                p_core[-1:].clone(),
            ]
        )

        self.assertTrue(torch.allclose(context["proposal"][0], expected_proposal, atol=1e-6))
        self.assertAlmostEqual(float(context["proposal"][0, -1]), float(p_core[-1]), places=6)
        self.assertLess(float(context["content_anchor"][0, 2]), 1e-7)

    def test_v2_ablation_modes_map_to_gate_controls(self) -> None:
        module = load_module()
        common_kwargs = dict(
            item_embeddings=torch.tensor(
                [
                    [1.0, 0.0],
                    [0.9, 0.1],
                    [0.0, 1.0],
                    [-1.0, 0.0],
                ],
                dtype=torch.float32,
            ),
            item_completeness=torch.tensor([1.0, 0.9, 0.8, 1.0], dtype=torch.float32),
            item_num=4,
            is_disliked_item=True,
            kernel_version="v2",
            g_max=1.0,
            center_embeddings=True,
        )
        global_builder = module.TextSideProposalBuilder(ablation_mode="global_p", **common_kwargs)
        anchor_builder = module.TextSideProposalBuilder(ablation_mode="text_anchor_only", **common_kwargs)
        shuffle_builder = module.TextSideProposalBuilder(ablation_mode="u_shuffle", **common_kwargs)
        base_builder = module.TextSideProposalBuilder(**common_kwargs)
        for builder in (global_builder, anchor_builder, shuffle_builder, base_builder):
            with torch.no_grad():
                builder.p1.copy_(torch.tensor([1.0, 0.0, -1.0, 0.5, -0.5], dtype=torch.float32))

        history = torch.tensor(
            [
                [0, 0, 1, 4],
                [2, 2, 3, 4],
                [0, 2, 3, 4],
            ],
            dtype=torch.long,
        )

        global_context = global_builder.encode_history_context(history)
        anchor_context = anchor_builder.encode_history_context(history)
        baseline_context = base_builder.encode_history_context(history)
        torch.manual_seed(0)
        shuffled_context = shuffle_builder.encode_history_context(history)

        self.assertTrue(torch.allclose(global_context["proposal"][0], global_context["proposal"][1], atol=1e-6))
        self.assertTrue(torch.allclose(global_context["proposal"], global_context["p_core"], atol=1e-6))
        self.assertTrue(torch.allclose(anchor_context["g"], torch.ones_like(anchor_context["g"]), atol=1e-6))
        self.assertTrue(
            torch.allclose(
                anchor_context["proposal"][:, -1],
                anchor_context["p_core"][:, -1],
                atol=1e-6,
            )
        )
        self.assertTrue(
            torch.allclose(
                anchor_context["proposal"][:, :-1] / (1.0 - anchor_context["proposal"][:, -1:]),
                anchor_context["content_anchor"],
                atol=1e-6,
            )
        )
        self.assertTrue(torch.allclose(shuffled_context["agreement"], baseline_context["agreement"], atol=1e-6))
        self.assertCountEqual(
            [round(float(x), 6) for x in shuffled_context["u_tilde"].tolist()],
            [round(float(x), 6) for x in baseline_context["u_tilde"].tolist()],
        )
        self.assertFalse(torch.allclose(shuffled_context["u_tilde"], baseline_context["u_tilde"], atol=1e-6))

    def test_v2_proposal_backpropagates_into_core_p1(self) -> None:
        module = load_module()
        builder = module.TextSideProposalBuilder(
            item_embeddings=torch.tensor(
                [
                    [1.0, 0.0],
                    [0.9, 0.1],
                    [0.0, 1.0],
                    [-1.0, 0.0],
                ],
                dtype=torch.float32,
            ),
            item_completeness=torch.tensor([1.0, 0.8, 0.7, 1.0], dtype=torch.float32),
            item_num=4,
            is_disliked_item=True,
            kernel_version="v2",
            g_max=0.5,
            center_embeddings=True,
        )

        history = torch.tensor(
            [
                [0, 0, 1, 4],
                [0, 2, 3, 4],
            ],
            dtype=torch.long,
        )
        context = builder.encode_history_context(history)
        loss = (
            context["proposal"][:, 0].sum()
            + 0.5 * context["proposal"][:, 1].sum()
            + 0.25 * context["proposal"][:, -1].sum()
        )
        loss.backward()

        self.assertIsNotNone(builder.p1.grad)
        self.assertGreater(float(builder.p1.grad.abs().sum()), 0.0)
        self.assertGreater(float(builder.p1.grad[:-1].abs().sum()), 0.0)
        self.assertGreater(float(builder.p1.grad[-1].abs()), 0.0)

    def test_kernel_closed_gate_proposal_has_core_softmax_gradient_identity(self) -> None:
        module = load_module()
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
            gate_dataset_scale=0.0,
        )
        with torch.no_grad():
            builder.p1.copy_(torch.tensor([0.4, -0.3, 0.8, 0.1, -0.2]))
        history = torch.tensor([[0, 1, 2, 4], [2, 3, 0, 4]], dtype=torch.long)
        weights = torch.tensor(
            [[1.0, -0.5, 0.25, 0.75, -0.25], [0.3, 0.8, -0.4, 0.2, 0.6]]
        )

        proposal = builder.encode_history_context(history)["proposal"]
        (proposal * weights).sum().backward()
        observed = builder.p1.grad.detach().clone()

        builder.p1.grad = None
        core = torch.softmax(builder.p1, dim=-1).unsqueeze(0).expand_as(proposal)
        (core * weights).sum().backward()
        expected = builder.p1.grad.detach().clone()

        self.assertTrue(torch.equal(observed, expected))

    def test_v2_from_files_uses_length_matched_null_curve_lookup(self) -> None:
        self.assertTrue(MODULE_PATH.exists(), f"missing module: {MODULE_PATH}")
        module = load_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_dir = Path(tmpdir)
            pd.DataFrame(
                [
                    {
                        "item_id": 0,
                        "source_id": "a0",
                        "title": "Alpha",
                        "brand": "",
                        "categories": "",
                        "description": "",
                        "text": "Alpha",
                    },
                    {
                        "item_id": 1,
                        "source_id": "a1",
                        "title": "Beta",
                        "brand": "",
                        "categories": "",
                        "description": "",
                        "text": "Beta",
                    },
                    {
                        "item_id": 2,
                        "source_id": "a2",
                        "title": "Gamma",
                        "brand": "",
                        "categories": "",
                        "description": "",
                        "text": "Gamma",
                    },
                ]
            ).to_csv(dataset_dir / "item_metadata.csv", index=False)
            module.ensure_text_bank(dataset_dir)
            torch.save(
                {
                    "item_ids": [0, 1, 2],
                    "embeddings": torch.tensor(
                        [
                            [1.0, 0.0],
                            [1.0, 0.0],
                            [0.0, 1.0],
                        ],
                        dtype=torch.float32,
                    ),
                    "field_coverage": torch.tensor([1.0, 1.0, 1.0], dtype=torch.float32),
                },
                dataset_dir / "sentence_t5_xl_item_emb.pt",
            )
            (dataset_dir / "agreement_null_curves.json").write_text(
                json.dumps(
                    {
                        "protocol": {
                            "agreement_k": 2.0,
                        },
                        "length_bins": {
                            "2": {
                                "mu": 1.0,
                                "sigma": 0.25,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            builder = module.TextSideProposalBuilder.from_files(
                dataset_dir=dataset_dir,
                item_num=3,
                is_disliked_item=False,
                embeddings_path=dataset_dir / "sentence_t5_xl_item_emb.pt",
                kernel_version="v2",
                agreement_null_curve_path=dataset_dir / "agreement_null_curves.json",
                agreement_k=2.0,
            )

            context = builder.encode_history_context(torch.tensor([[0, 0, 3]], dtype=torch.long))
            self.assertAlmostEqual(0.0, float(context["u_tilde"][0]), places=6)
            self.assertAlmostEqual(0.0, float(context["g"][0]), places=6)

    def test_v2_from_files_scales_g_with_frozen_utility_factor(self) -> None:
        module = load_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_dir = Path(tmpdir) / "ToySet"
            dataset_dir.mkdir()
            pd.DataFrame(
                [
                    {
                        "item_id": 0,
                        "source_id": "a0",
                        "title": "Alpha",
                        "brand": "",
                        "categories": "",
                        "description": "",
                        "text": "Alpha",
                    },
                    {
                        "item_id": 1,
                        "source_id": "a1",
                        "title": "Beta",
                        "brand": "",
                        "categories": "",
                        "description": "",
                        "text": "Beta",
                    },
                    {
                        "item_id": 2,
                        "source_id": "a2",
                        "title": "Gamma",
                        "brand": "",
                        "categories": "",
                        "description": "",
                        "text": "Gamma",
                    },
                ]
            ).to_csv(dataset_dir / "item_metadata.csv", index=False)
            text_bank_path = module.ensure_text_bank(dataset_dir)
            torch.save(
                {
                    "item_ids": [0, 1, 2],
                    "embeddings": torch.tensor(
                        [
                            [1.0, 0.0],
                            [1.0, 0.0],
                            [0.0, 1.0],
                        ],
                        dtype=torch.float32,
                    ),
                    "field_coverage": torch.tensor([1.0, 1.0, 1.0], dtype=torch.float32),
                },
                dataset_dir / "sentence_t5_xl_item_emb.pt",
            )
            (dataset_dir / "agreement_null_curves.json").write_text(
                json.dumps(
                    {
                        "protocol": {
                            "agreement_k": 2.0,
                        },
                        "length_bins": {
                            "2": {
                                "mu": 0.5,
                                "sigma": 0.25,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            bank_digest = hashlib.sha256()
            for path in (text_bank_path, dataset_dir / "sentence_t5_xl_item_emb.pt"):
                bank_digest.update(path.name.encode("utf-8"))
                bank_digest.update(path.read_bytes())
            utility_report_path = dataset_dir / "gate0_text_utility_report.json"
            utility_report_path.write_text(
                json.dumps(
                    {
                        "datasets": [
                            {
                                "dataset": dataset_dir.name,
                                "bank_hash": bank_digest.hexdigest(),
                                "u_ds_popularity": 0.65,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            base_builder = module.TextSideProposalBuilder.from_files(
                dataset_dir=dataset_dir,
                item_num=3,
                is_disliked_item=False,
                embeddings_path=dataset_dir / "sentence_t5_xl_item_emb.pt",
                kernel_version="v2",
                agreement_null_curve_path=dataset_dir / "agreement_null_curves.json",
                agreement_k=2.0,
                g_max=0.5,
            )
            scaled_builder = module.TextSideProposalBuilder.from_files(
                dataset_dir=dataset_dir,
                item_num=3,
                is_disliked_item=False,
                embeddings_path=dataset_dir / "sentence_t5_xl_item_emb.pt",
                kernel_version="v2",
                agreement_null_curve_path=dataset_dir / "agreement_null_curves.json",
                text_utility_report_path=utility_report_path,
                agreement_k=2.0,
                g_max=0.5,
            )

            history = torch.tensor([[0, 0, 3]], dtype=torch.long)
            base_context = base_builder.encode_history_context(history)
            scaled_context = scaled_builder.encode_history_context(history)

            self.assertAlmostEqual(1.0, float(base_context["u_tilde"][0]), places=6)
            self.assertAlmostEqual(float(base_context["u_tilde"][0]), float(scaled_context["u_tilde"][0]), places=6)
            self.assertAlmostEqual(0.5, float(base_context["g"][0]), places=6)
            self.assertAlmostEqual(0.25, float(scaled_context["g"][0]), places=6)
            self.assertAlmostEqual(0.5, float(scaled_context["gate_dataset_scale"][0]), places=6)

    def test_v2_from_files_rejects_text_utility_bank_hash_mismatch(self) -> None:
        module = load_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_dir = Path(tmpdir) / "ToySet"
            dataset_dir.mkdir()
            pd.DataFrame(
                [
                    {
                        "item_id": 0,
                        "source_id": "a0",
                        "title": "Alpha",
                        "brand": "",
                        "categories": "",
                        "description": "",
                        "text": "Alpha",
                    },
                    {
                        "item_id": 1,
                        "source_id": "a1",
                        "title": "Beta",
                        "brand": "",
                        "categories": "",
                        "description": "",
                        "text": "Beta",
                    },
                ]
            ).to_csv(dataset_dir / "item_metadata.csv", index=False)
            module.ensure_text_bank(dataset_dir)
            torch.save(
                {
                    "item_ids": [0, 1],
                    "embeddings": torch.tensor([[1.0, 0.0], [1.0, 0.0]], dtype=torch.float32),
                    "field_coverage": torch.tensor([1.0, 1.0], dtype=torch.float32),
                },
                dataset_dir / "sentence_t5_xl_item_emb.pt",
            )
            utility_report_path = dataset_dir / "gate0_text_utility_report.json"
            utility_report_path.write_text(
                json.dumps(
                    {
                        "datasets": [
                            {
                                "dataset": dataset_dir.name,
                                "bank_hash": "not-the-real-bank-hash",
                                "u_ds_popularity": 0.65,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "bank hash"):
                module.TextSideProposalBuilder.from_files(
                    dataset_dir=dataset_dir,
                    item_num=2,
                    is_disliked_item=False,
                    embeddings_path=dataset_dir / "sentence_t5_xl_item_emb.pt",
                    kernel_version="v2",
                    text_utility_report_path=utility_report_path,
                )

    def test_strict_v2_full_requires_gate_source_and_accepts_explicit_scale(self) -> None:
        module = load_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            dataset_dir = repo_root / "dataset" / "paper_raw_v1" / "ToySet"
            dataset_dir.mkdir(parents=True)
            pd.DataFrame(
                [
                    {"item_id": 0, "field_coverage": 1.0},
                    {"item_id": 1, "field_coverage": 1.0},
                ]
            ).to_csv(dataset_dir / "text_bank.csv", index=False)
            torch.save(
                {
                    "embeddings": torch.tensor(
                        [[1.0, 0.0], [0.0, 1.0]], dtype=torch.float32
                    ),
                    "field_coverage": torch.ones(2, dtype=torch.float32),
                },
                dataset_dir / "embeddings.pt",
            )
            null_curve = dataset_dir / "agreement_null_curves.json"
            null_curve.write_text(
                json.dumps(
                    {
                        "length_bins": {
                            "1": {"mu": 0.0, "sigma": 1.0},
                        }
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "gate source"):
                module.TextSideProposalBuilder.from_files(
                    dataset_dir=dataset_dir,
                    item_num=2,
                    is_disliked_item=False,
                    embeddings_path=dataset_dir / "embeddings.pt",
                    agreement_null_curve_path=null_curve,
                    kernel_version="v2",
                    ablation_mode="none",
                    require_gate_source=True,
                )

            default_report = (
                repo_root
                / "docs"
                / "reports"
                / "data"
                / "2026-07-02-gate0"
                / "gate0_text_utility_report.json"
            )
            default_report.parent.mkdir(parents=True)
            default_report.write_text(
                json.dumps(
                    {
                        "datasets": [
                            {
                                "dataset": "ToySet",
                                "bank_hash": "default-report-must-not-win",
                                "u_ds_popularity": 0.65,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            builder = module.TextSideProposalBuilder.from_files(
                dataset_dir=dataset_dir,
                item_num=2,
                is_disliked_item=False,
                embeddings_path=dataset_dir / "embeddings.pt",
                agreement_null_curve_path=null_curve,
                kernel_version="v2",
                ablation_mode="none",
                gate_dataset_scale_override=0.25,
                require_gate_source=True,
            )
            self.assertAlmostEqual(0.25, builder.gate_dataset_scale, places=12)

    def test_text_anchor_only_ablation_still_forces_full_gate_under_dataset_scaling(self) -> None:
        module = load_module()
        builder = module.TextSideProposalBuilder(
            item_embeddings=torch.tensor(
                [
                    [1.0, 0.0],
                    [1.0, 0.0],
                    [0.0, 1.0],
                ],
                dtype=torch.float32,
            ),
            item_completeness=torch.tensor([1.0, 1.0, 1.0], dtype=torch.float32),
            item_num=3,
            is_disliked_item=False,
            kernel_version="v2",
            agreement_null_stats={2: (0.5, 0.25)},
            agreement_k=2.0,
            g_max=0.5,
            gate_dataset_scale=0.25,
            ablation_mode="text_anchor_only",
        )

        history = torch.tensor([[0, 0, 3]], dtype=torch.long)
        context = builder.encode_history_context(history)

        self.assertAlmostEqual(1.0, float(context["u_tilde"][0]), places=6)
        self.assertAlmostEqual(1.0, float(context["gate_user_factor"][0]), places=6)
        self.assertAlmostEqual(1.0, float(context["gate_dataset_scale"][0]), places=6)
        self.assertAlmostEqual(0.5, float(context["g"][0]), places=6)

    def test_context_exposes_reliability_components_and_reliability_controls_pseudo_mass(self) -> None:
        module = load_module()
        builder = module.TextSideProposalBuilder(
            item_embeddings=torch.tensor(
                [
                    [1.0, 0.0],
                    [0.8, 0.2],
                    [0.0, 1.0],
                    [-1.0, 0.0],
                ],
                dtype=torch.float32,
            ),
            item_completeness=torch.tensor([0.9, 0.9, 0.9, 0.9], dtype=torch.float32),
            item_num=4,
            is_disliked_item=True,
            temperature=0.2,
        )

        history = torch.tensor(
            [
                [0, 0, 1, 4],
                [0, 2, 3, 4],
            ],
            dtype=torch.long,
        )

        context = builder.encode_history_context(history)

        for key in (
            "agreement",
            "completeness",
            "history_ess",
            "history_recency",
            "history_stability",
            "history_reliability",
            "u",
            "proposal",
        ):
            self.assertIn(key, context)

        self.assertGreater(float(context["agreement"][0]), float(context["agreement"][1]))
        self.assertGreater(float(context["history_stability"][0]), float(context["history_stability"][1]))
        self.assertGreater(float(context["history_reliability"][0]), float(context["history_reliability"][1]))
        self.assertGreater(float(context["u"][0]), float(context["u"][1]))
        self.assertLess(float(context["proposal"][0, -1]), float(context["proposal"][1, -1]))

    def test_recent_interest_shift_reduces_history_recency(self) -> None:
        module = load_module()
        builder = module.TextSideProposalBuilder(
            item_embeddings=torch.tensor(
                [
                    [1.0, 0.0],
                    [0.8, 0.2],
                    [0.0, 1.0],
                    [-1.0, 0.0],
                ],
                dtype=torch.float32,
            ),
            item_completeness=torch.tensor([0.9, 0.9, 0.9, 0.9], dtype=torch.float32),
            item_num=4,
            is_disliked_item=True,
            temperature=0.2,
        )

        history = torch.tensor(
            [
                [0, 0, 0, 0],
                [0, 0, 2, 2],
            ],
            dtype=torch.long,
        )

        context = builder.encode_history_context(history)
        self.assertGreater(float(context["history_recency"][0]), float(context["history_recency"][1]))

    def test_short_history_has_lower_history_ess_proxy(self) -> None:
        module = load_module()
        builder = module.TextSideProposalBuilder(
            item_embeddings=torch.tensor(
                [
                    [1.0, 0.0],
                    [0.8, 0.2],
                    [0.0, 1.0],
                    [-1.0, 0.0],
                ],
                dtype=torch.float32,
            ),
            item_completeness=torch.tensor([0.9, 0.9, 0.9, 0.9], dtype=torch.float32),
            item_num=4,
            is_disliked_item=True,
            temperature=0.2,
        )

        history = torch.tensor(
            [
                [0, 1, 2, 4],
                [0, 4, 4, 4],
            ],
            dtype=torch.long,
        )

        context = builder.encode_history_context(history)
        self.assertGreater(float(context["history_ess"][0]), float(context["history_ess"][1]))

    def test_low_reliability_history_leans_more_on_popularity_prior(self) -> None:
        module = load_module()
        builder = module.TextSideProposalBuilder(
            item_embeddings=torch.tensor(
                [
                    [1.0, 0.0],
                    [0.0, 1.0],
                    [1.0, 0.0],
                    [-1.0, 0.0],
                ],
                dtype=torch.float32,
            ),
            item_completeness=torch.tensor([1.0, 1.0, 0.0, 1.0], dtype=torch.float32),
            item_num=4,
            is_disliked_item=False,
            temperature=0.2,
            item_popularity=torch.tensor([1.0, 1.0, 1.0, 100.0], dtype=torch.float32),
        )

        history = torch.tensor(
            [
                [0, 0, 0, 0],
                [2, 4, 4, 4],
            ],
            dtype=torch.long,
        )

        context = builder.encode_history_context(history)

        self.assertIn("content_probs", context)
        self.assertIn("popularity_prior", context)
        self.assertIn("popularity_mix", context)
        self.assertGreater(float(context["popularity_mix"][1]), float(context["popularity_mix"][0]))
        self.assertGreater(float(context["proposal"][1, 3]), float(context["proposal"][0, 3]))

    def test_centered_embeddings_reduce_agreement_saturation_in_anisotropic_histories(self) -> None:
        module = load_module()
        raw_builder = module.TextSideProposalBuilder(
            item_embeddings=torch.tensor(
                [
                    [1.0, 0.00],
                    [1.0, 0.05],
                    [1.0, -0.05],
                    [-1.0, 0.00],
                ],
                dtype=torch.float32,
            ),
            item_completeness=torch.ones(4, dtype=torch.float32),
            item_num=4,
            is_disliked_item=False,
            center_embeddings=False,
        )
        centered_builder = module.TextSideProposalBuilder(
            item_embeddings=torch.tensor(
                [
                    [1.0, 0.00],
                    [1.0, 0.05],
                    [1.0, -0.05],
                    [-1.0, 0.00],
                ],
                dtype=torch.float32,
            ),
            item_completeness=torch.ones(4, dtype=torch.float32),
            item_num=4,
            is_disliked_item=False,
            center_embeddings=True,
        )

        coherent = torch.tensor([[0, 0, 1, 4]], dtype=torch.long)
        mixed = torch.tensor([[0, 1, 2, 4]], dtype=torch.long)

        raw_mixed = raw_builder.encode_history_context(mixed)
        centered_coherent = centered_builder.encode_history_context(coherent)
        centered_mixed = centered_builder.encode_history_context(mixed)

        self.assertLess(float(centered_mixed["agreement"][0]), float(raw_mixed["agreement"][0]))
        self.assertGreater(float(centered_coherent["agreement"][0]), float(centered_mixed["agreement"][0]))

    def test_popularity_mix_scale_can_disable_global_prior_fallback(self) -> None:
        module = load_module()
        builder = module.TextSideProposalBuilder(
            item_embeddings=torch.tensor(
                [
                    [1.0, 0.0],
                    [0.0, 1.0],
                    [1.0, 0.0],
                    [-1.0, 0.0],
                ],
                dtype=torch.float32,
            ),
            item_completeness=torch.tensor([1.0, 1.0, 0.0, 1.0], dtype=torch.float32),
            item_num=4,
            is_disliked_item=False,
            item_popularity=torch.tensor([1.0, 1.0, 1.0, 100.0], dtype=torch.float32),
            popularity_mix_scale=0.0,
        )

        history = torch.tensor([[2, 4, 4, 4]], dtype=torch.long)
        context = builder.encode_history_context(history)

        self.assertEqual(0.0, float(context["popularity_mix"][0]))
        self.assertTrue(torch.allclose(context["proposal"], context["content_probs"], atol=1e-6))

    def test_global_p_ablation_returns_shared_global_proposal(self) -> None:
        module = load_module()
        builder = module.TextSideProposalBuilder(
            item_embeddings=torch.tensor(
                [
                    [1.0, 0.0],
                    [0.0, 1.0],
                    [-1.0, 0.0],
                    [0.0, -1.0],
                ],
                dtype=torch.float32,
            ),
            item_completeness=torch.ones(4, dtype=torch.float32),
            item_num=4,
            is_disliked_item=False,
            item_popularity=torch.tensor([1.0, 3.0, 9.0, 27.0], dtype=torch.float32),
            ablation_mode="global_p",
        )

        history = torch.tensor(
            [
                [0, 1, 2, 4],
                [3, 3, 3, 4],
            ],
            dtype=torch.long,
        )
        context = builder.encode_history_context(history)

        self.assertTrue(torch.allclose(context["proposal"][0], context["proposal"][1], atol=1e-6))
        self.assertTrue(torch.allclose(context["proposal"], context["popularity_prior"], atol=1e-6))

    def test_u_shuffle_ablation_keeps_content_anchor_but_breaks_reliability_alignment(self) -> None:
        module = load_module()
        base_builder = module.TextSideProposalBuilder(
            item_embeddings=torch.tensor(
                [
                    [1.0, 0.0],
                    [0.8, 0.2],
                    [0.0, 1.0],
                    [-1.0, 0.0],
                ],
                dtype=torch.float32,
            ),
            item_completeness=torch.tensor([1.0, 0.8, 0.2, 0.2], dtype=torch.float32),
            item_num=4,
            is_disliked_item=True,
            center_embeddings=True,
        )
        shuffled_builder = module.TextSideProposalBuilder(
            item_embeddings=torch.tensor(
                [
                    [1.0, 0.0],
                    [0.8, 0.2],
                    [0.0, 1.0],
                    [-1.0, 0.0],
                ],
                dtype=torch.float32,
            ),
            item_completeness=torch.tensor([1.0, 0.8, 0.2, 0.2], dtype=torch.float32),
            item_num=4,
            is_disliked_item=True,
            center_embeddings=True,
            ablation_mode="u_shuffle",
        )

        history = torch.tensor(
            [
                [0, 0, 1, 4],
                [2, 2, 3, 4],
                [0, 2, 3, 4],
            ],
            dtype=torch.long,
        )

        baseline_context = base_builder.encode_history_context(history)
        torch.manual_seed(0)
        shuffled_context = shuffled_builder.encode_history_context(history)

        self.assertTrue(torch.allclose(shuffled_context["agreement"], baseline_context["agreement"], atol=1e-6))
        self.assertTrue(torch.allclose(shuffled_context["history_reliability"], baseline_context["history_reliability"], atol=1e-6))
        self.assertCountEqual(
            [round(float(x), 6) for x in shuffled_context["u"].tolist()],
            [round(float(x), 6) for x in baseline_context["u"].tolist()],
        )
        self.assertFalse(torch.allclose(shuffled_context["u"], baseline_context["u"], atol=1e-6))

    def test_encoder_and_loss_injection_modes_fall_back_to_anchor_proposal(self) -> None:
        module = load_module()
        kwargs = dict(
            item_embeddings=torch.tensor(
                [
                    [1.0, 0.0],
                    [0.0, 1.0],
                    [1.0, 0.0],
                    [-1.0, 0.0],
                ],
                dtype=torch.float32,
            ),
            item_completeness=torch.tensor([1.0, 1.0, 0.0, 0.2], dtype=torch.float32),
            item_num=4,
            is_disliked_item=True,
            item_popularity=torch.tensor([1.0, 1.0, 1.0, 100.0], dtype=torch.float32),
            center_embeddings=True,
        )
        kernel_builder = module.TextSideProposalBuilder(**kwargs)
        anchor_builder = module.TextSideProposalBuilder(ablation_mode="text_anchor_only", **kwargs)
        encoder_builder = module.TextSideProposalBuilder(injection_mode="encoder", **kwargs)
        loss_builder = module.TextSideProposalBuilder(injection_mode="loss", **kwargs)

        history = torch.tensor(
            [
                [0, 0, 0, 4],
                [2, 4, 4, 4],
            ],
            dtype=torch.long,
        )

        kernel_context = kernel_builder.encode_history_context(history)
        anchor_context = anchor_builder.encode_history_context(history)
        encoder_context = encoder_builder.encode_history_context(history)
        loss_context = loss_builder.encode_history_context(history)

        self.assertFalse(torch.allclose(kernel_context["proposal"], anchor_context["proposal"], atol=1e-6))
        self.assertTrue(torch.allclose(encoder_context["proposal"], anchor_context["proposal"], atol=1e-6))
        self.assertTrue(torch.allclose(loss_context["proposal"], anchor_context["proposal"], atol=1e-6))
        self.assertIn("history_repr", encoder_context)
        self.assertIn("loss_weight", loss_context)

    def test_pseudo_mass_scale_can_soften_disliked_fallback(self) -> None:
        module = load_module()
        default_builder = module.TextSideProposalBuilder(
            item_embeddings=torch.tensor(
                [
                    [1.0, 0.0],
                    [0.0, 1.0],
                    [-1.0, 0.0],
                    [0.0, -1.0],
                ],
                dtype=torch.float32,
            ),
            item_completeness=torch.tensor([0.2, 0.2, 0.2, 0.2], dtype=torch.float32),
            item_num=4,
            is_disliked_item=True,
        )
        softened_builder = module.TextSideProposalBuilder(
            item_embeddings=torch.tensor(
                [
                    [1.0, 0.0],
                    [0.0, 1.0],
                    [-1.0, 0.0],
                    [0.0, -1.0],
                ],
                dtype=torch.float32,
            ),
            item_completeness=torch.tensor([0.2, 0.2, 0.2, 0.2], dtype=torch.float32),
            item_num=4,
            is_disliked_item=True,
            pseudo_mass_scale=0.5,
        )

        history = torch.tensor([[0, 1, 2, 4]], dtype=torch.long)
        default_context = default_builder.encode_history_context(history)
        softened_context = softened_builder.encode_history_context(history)

        self.assertLess(float(softened_context["pseudo_mass"][0]), float(default_context["pseudo_mass"][0]))
        self.assertGreater(float(softened_context["proposal"][0, :-1].sum()), float(default_context["proposal"][0, :-1].sum()))

    def test_builder_uses_cached_embeddings_and_history_completeness(self) -> None:
        self.assertTrue(MODULE_PATH.exists(), f"missing module: {MODULE_PATH}")
        module = load_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_dir = Path(tmpdir)
            pd.DataFrame(
                [
                    {
                        "item_id": 0,
                        "source_id": "a0",
                        "title": "Alpha",
                        "genres": "",
                        "brand": "BrandA",
                        "categories": "CatA",
                        "description": "Alpha desc",
                        "text": "Alpha. BrandA. CatA. Alpha desc",
                    },
                    {
                        "item_id": 1,
                        "source_id": "a1",
                        "title": "",
                        "genres": "",
                        "brand": "",
                        "categories": "",
                        "description": "",
                        "text": "",
                    },
                    {
                        "item_id": 2,
                        "source_id": "a2",
                        "title": "Gamma",
                        "genres": "",
                        "brand": "",
                        "categories": "CatG",
                        "description": "Gamma desc",
                        "text": "Gamma. CatG. Gamma desc",
                    },
                ]
            ).to_csv(dataset_dir / "item_metadata.csv", index=False)

            text_bank_path = module.ensure_text_bank(dataset_dir)
            self.assertTrue(text_bank_path.exists())

            torch.save(
                {
                    "item_ids": [0, 1, 2],
                    "embeddings": torch.tensor(
                        [
                            [1.0, 0.0],
                            [0.0, 1.0],
                            [1.0, 1.0],
                        ],
                        dtype=torch.float32,
                    ),
                    "field_coverage": torch.tensor([1.0, 0.0, 0.75], dtype=torch.float32),
                },
                dataset_dir / "sentence_t5_xl_item_emb.pt",
            )

            builder = module.TextSideProposalBuilder.from_files(
                dataset_dir=dataset_dir,
                item_num=3,
                is_disliked_item=True,
                embeddings_path=dataset_dir / "sentence_t5_xl_item_emb.pt",
            )

            history = torch.tensor(
                [
                    [0, 2, 3],
                    [1, 3, 3],
                ],
                dtype=torch.long,
            )
            context = builder.encode_history_context(history)
            proposal = context["proposal"]

            self.assertEqual((2, 4), tuple(proposal.shape))
            self.assertTrue(torch.allclose(proposal.sum(dim=-1), torch.ones(2), atol=1e-5))
            self.assertLess(float(proposal[0, -1]), float(proposal[1, -1]))


if __name__ == "__main__":
    unittest.main()
