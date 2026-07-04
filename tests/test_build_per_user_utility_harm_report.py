import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import torch
from omegaconf import OmegaConf

import dataset_runtime
from model.ema import ExponentialMovingAverage
from model.transformer import SEDD4REC


REPO_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


report_module = load_module(
    "build_per_user_utility_harm_report",
    REPO_ROOT / "scripts" / "build_per_user_utility_harm_report.py",
)


def write_checkpoint(path: Path, cfg_dict: dict, *, seed: int) -> None:
    torch.manual_seed(seed)
    cfg = OmegaConf.create(cfg_dict)
    dataset_runtime.reconcile_runtime_dataset_config(cfg)
    model = SEDD4REC(cfg)
    ema = ExponentialMovingAverage(model.parameters(), decay=float(cfg.training.ema))
    checkpoint = {
        "model": model.state_dict(),
        "ema": ema.state_dict(),
        "step": 1234,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, path)


def make_summary(path: Path, *, best_step: int, best_metric: float, test_p2: float) -> None:
    payload = {
        "best_step": best_step,
        "best_metric": best_metric,
        "validation": {"p2": {"ndcg": [0.0, 0.0, test_p2, test_p2]}},
        "test": {"p2": {"ndcg": [0.0, 0.0, test_p2, test_p2]}},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def build_logged_cfg(dataset_name: str, dataset_dir: Path, *, score_flag: bool) -> dict:
    return {
        "ngpus": 0,
        "cuda": 0,
        "random_seed": 100,
        "work_dir": str(dataset_dir),
        "loss_type": "score_entropy",
        "training": {
            "data": dataset_name,
            "batch_size": 8,
            "accum": 1,
            "n_iters": 1000,
            "snapshot_freq": 100,
            "log_freq": 100,
            "eval_freq": 100,
            "snapshot_freq_for_preemption": 100,
            "weight": "standard",
            "snapshot_sampling": True,
            "ema": 0.9999,
            "nonpreference_user_ratio": 0.1 if score_flag else 0.05,
            "early_stop_patience": 5,
            "early_stop_min_step": 100,
            "early_stop_metric": "ndcg10",
            "early_stop_strength": "p2",
            "early_stop_min_delta": 0.0,
        },
        "data": {
            "Steam": {"path": "dataset/steam", "seq_len": 10, "item_num": 6},
            "Beauty": {"path": "dataset/beauty", "seq_len": 10, "item_num": 6},
            "ASO": {"path": "dataset/aso", "seq_len": 10, "item_num": 6},
            "ATG": {"path": "dataset/atg", "seq_len": 10, "item_num": 6},
            "ATV": {"path": "dataset/atv", "seq_len": 10, "item_num": 6},
            "ML1M": {"path": "dataset/ml1m", "seq_len": 10, "item_num": 6},
        },
        "graph": {
            "type": "proposal_adaptive",
            "is_disliked_item": True,
            "gamma": 0.5,
            "file": "data",
            "report_all": False,
        },
        "noise": {"type": "geometric", "sigma_min": 1e-3, "sigma_max": 10},
        "sampling": {"predictor": "analytic", "steps": 2, "noise_removal": True, "personalization_strength": 2},
        "text_side": {
            "enabled": True,
            "dataset_dir": str(dataset_dir),
            "text_bank_path": None,
            "embeddings_path": str(dataset_dir / "sentence_t5_xl_item_emb.pt"),
            "temperature": 0.2,
            "min_pseudo_mass": 0.03,
            "agreement_weight": 0.35,
            "completeness_weight": 0.05,
            "history_reliability_weight": 0.6,
            "ess_weight": 0.2,
            "recency_weight": 0.35,
            "stability_weight": 0.45,
            "max_temperature_scale": 1.4,
            "popularity_mix_scale": 0.0,
            "popularity_mix_power": 1.0,
            "center_embeddings": True,
            "pseudo_mass_scale": 1.0,
            "pseudo_mass_power": 1.0,
            "ablation_mode": "none",
            "injection_mode": "kernel",
            "encoder_context_scale": 1.0,
            "loss_weight_scale": 1.0,
        },
        "eval": {"batch_size": 8, "perplexity": True, "perplexity_batch_size": 8},
        "optim": {
            "weight_decay": 0.0,
            "optimizer": "AdamW",
            "lr": 1e-3 if not score_flag else 1e-4,
            "beta1": 0.9,
            "beta2": 0.999,
            "eps": 1e-8,
            "warmup": 10,
            "grad_clip": 1.0,
        },
        "model": {
            "name": "small",
            "type": "ddit",
            "hidden_size": 32,
            "cond_dim": 32,
            "length": 10,
            "n_blocks": 1,
            "n_heads": 2,
            "scale_by_sigma": False,
            "dropout": 0.0,
            "score_flag": score_flag,
            "score_method": "oricos",
        },
    }


def build_toy_dataset(dataset_dir: Path) -> None:
    dataset_dir.mkdir(parents=True, exist_ok=True)
    item_count = 6
    text_bank = pd.DataFrame(
        {
            "item_id": list(range(item_count)),
            "source_id": [f"src-{index}" for index in range(item_count)],
            "title": [f"title-{index}" for index in range(item_count)],
            "genres": [""] * item_count,
            "brand": [""] * item_count,
            "categories": [""] * item_count,
            "description": [f"description-{index}" for index in range(item_count)],
            "text": [f"text-{index}" for index in range(item_count)],
            "field_coverage": [0.2, 0.4, 0.6, 0.8, 1.0, 0.5],
            "text_length": [10, 11, 12, 13, 14, 15],
            "description_present": [1, 1, 1, 1, 0, 1],
            "title_present": [1, 1, 1, 1, 1, 1],
        }
    )
    text_bank.to_csv(dataset_dir / "text_bank.csv", index=False)
    np.save(dataset_dir / "items_pop.npy", np.asarray([10, 8, 6, 4, 2, 1], dtype=np.int64))

    embeddings = torch.tensor(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.8, 0.2, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.8, 0.2, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.5, 0.5],
        ],
        dtype=torch.float32,
    )
    torch.save(
        {
            "embeddings": embeddings,
            "item_ids": list(range(item_count)),
            "field_coverage": torch.tensor(text_bank["field_coverage"].to_numpy(dtype=np.float32)),
        },
        dataset_dir / "sentence_t5_xl_item_emb.pt",
    )

    sequences = [
        [0, 1, 2, 3],
        [1, 2, 3, 4],
        [2, 3, 4, 5],
    ]
    lines = [" ".join(str(item_id + 1) for item_id in sequence) for sequence in sequences]
    (dataset_dir / "train_data.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    train_rows = pd.DataFrame(
        [
            {"seq": [item_count] * 7 + [0, 1, 2], "len_seq": 3, "next": 3},
            {"seq": [item_count] * 7 + [1, 2, 3], "len_seq": 3, "next": 4},
            {"seq": [item_count] * 7 + [2, 3, 4], "len_seq": 3, "next": 5},
        ]
    )
    train_rows.to_pickle(dataset_dir / "train_data.df")
    pd.DataFrame([{"seq_size": 10, "item_num": item_count}]).to_pickle(dataset_dir / "data_statis.df")


class BuildPerUserUtilityHarmReportTests(unittest.TestCase):
    def test_write_markdown_does_not_require_tabulate(self) -> None:
        report = {
            "generated_at": "2026-07-04T15:28:04+08:00",
            "protocol": {
                "rows_per_user": 4,
                "negative_count": 32,
                "seed": 7,
                "device": "cpu",
                "primary_claim_metric": "delta_ndcg10",
            },
            "datasets": [
                {
                    "dataset": "ML1M",
                    "user_count": 10,
                    "sampled_row_count": 40,
                    "spearman_utility_vs_delta_ndcg10": 0.1,
                    "pearson_utility_vs_delta_ndcg10": 0.2,
                    "inverse_ordering_observed": False,
                    "interpretation": "Association only.",
                    "utility_buckets": [
                        {
                            "utility_bucket": "Q1",
                            "user_count": 5,
                            "utility_mean": 0.3,
                            "delta_ndcg10_mean": -0.1,
                        }
                    ],
                    "correlations": [
                        {
                            "metric": "utility_vs_delta_ndcg10",
                            "pearson": 0.2,
                            "spearman": 0.1,
                        }
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.md"
            with mock.patch.object(pd.DataFrame, "to_markdown", side_effect=AssertionError("unexpected tabulate dependency")):
                report_module._write_markdown(report, output_path)
            text = output_path.read_text(encoding="utf-8")
            self.assertIn("| dataset |", text)
            self.assertIn("| utility_bucket |", text)
            self.assertIn("Association only.", text)

    def test_build_report_writes_dataset_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dataset_root = root / "dataset" / "paper_raw_v1"
            run_root = root / "runs"
            core_root = root / "core"
            output_dir = root / "report"

            dataset_dirs = {
                "ML1M": dataset_root / "ML1M",
                "Steam": dataset_root / "Steam",
            }
            for dataset_name, dataset_dir in dataset_dirs.items():
                build_toy_dataset(dataset_dir)
                score_flag = dataset_name == "ML1M"
                logged_cfg = build_logged_cfg(dataset_name, dataset_dir, score_flag=score_flag)

                run_dir = run_root / f"{dataset_name.lower()}_proposal_adaptive_mainpath"
                log_dir = run_dir / "logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                log_path = log_dir / f"{dataset_name.lower()}_proposal_adaptive_mainpath.log"
                log_path.write_text(f"{run_dir}\n{logged_cfg}\n", encoding="utf-8")

                v1_checkpoint = run_dir / "checkpoints-meta" / dataset_name / "checkpoint_proposal_adaptive_best.pth"
                write_checkpoint(v1_checkpoint, logged_cfg, seed=11 if dataset_name == "ML1M" else 13)
                make_summary(
                    run_dir / "checkpoints-meta" / dataset_name / "best_summary_proposal_adaptive.json",
                    best_step=3000,
                    best_metric=0.02,
                    test_p2=0.03,
                )

                core_graph_type = "hybrid" if dataset_name == "ML1M" else "adaptive"
                core_cfg = json.loads(json.dumps(logged_cfg))
                core_cfg["graph"]["type"] = core_graph_type
                core_cfg["text_side"]["enabled"] = False
                core_cfg["text_side"]["text_bank_path"] = None
                core_cfg["text_side"]["embeddings_path"] = None
                core_checkpoint = core_root / dataset_name / f"checkpoint_{core_graph_type}_best.pth"
                write_checkpoint(core_checkpoint, core_cfg, seed=17 if dataset_name == "ML1M" else 19)
                make_summary(
                    core_root / dataset_name / report_module.CORE_SUMMARY_NAMES[core_graph_type],
                    best_step=27000,
                    best_metric=0.01,
                    test_p2=0.02,
                )

            report = report_module.build_per_user_utility_harm_report(
                dataset_dirs=dataset_dirs,
                output_dir=output_dir,
                run_root=run_root,
                core_root=core_root,
                rows_per_user=1,
                negative_count=5,
                seed=7,
                eval_batch_size=2,
                utility_batch_size=2,
                device="cpu",
            )

            self.assertEqual({"ML1M", "Steam"}, {row["dataset"] for row in report["datasets"]})
            self.assertTrue((output_dir / "per_user_utility_harm_report.json").exists())
            self.assertTrue((output_dir / "per_user_utility_harm_report.md").exists())
            summary_df = pd.read_csv(output_dir / "per_user_utility_harm_summary.csv")
            self.assertEqual({"ML1M", "Steam"}, set(summary_df["dataset"]))

            ml1m_user_df = pd.read_csv(output_dir / "ML1M_per_user_points.csv")
            steam_user_df = pd.read_csv(output_dir / "Steam_per_user_points.csv")
            self.assertEqual(3, len(ml1m_user_df))
            self.assertEqual(3, len(steam_user_df))
            self.assertIn("utility_popularity", ml1m_user_df.columns)
            self.assertIn("delta_ndcg10", ml1m_user_df.columns)

            corr_df = pd.read_csv(output_dir / "ML1M_correlations.csv")
            self.assertIn("utility_vs_delta_ndcg10", set(corr_df["metric"]))


if __name__ == "__main__":
    unittest.main()
