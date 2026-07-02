from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F


TEXT_BANK_FILENAME = "text_bank.csv"
DEFAULT_EMBEDDING_FILENAME = "sentence_t5_xl_item_emb.pt"
DEFAULT_NULL_CURVE_FILENAME = "agreement_null_curves.json"
ABLATION_MODES = {"none", "global_p", "text_anchor_only", "u_shuffle"}
INJECTION_MODES = {"kernel", "encoder", "loss"}
KERNEL_VERSIONS = {"v1", "v2"}


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def _compose_text(*parts: str) -> str:
    return ". ".join(part for part in parts if part)


def ensure_text_bank(dataset_dir: Path, output_name: str = TEXT_BANK_FILENAME) -> Path:
    dataset_dir = Path(dataset_dir)
    metadata_path = dataset_dir / "item_metadata.csv"
    if not metadata_path.exists():
        raise FileNotFoundError(f"missing item metadata: {metadata_path}")

    metadata = pd.read_csv(metadata_path).fillna("")
    rows = []
    for row in metadata.to_dict(orient="records"):
        item_id = int(row["item_id"])
        source_id = _clean_text(row.get("source_id"))
        title = _clean_text(row.get("title"))
        brand = _clean_text(row.get("brand"))
        categories = _clean_text(row.get("categories"))
        description = _clean_text(row.get("description"))
        raw_text = _clean_text(row.get("text"))
        normalized_text = raw_text or _compose_text(title, brand, categories, description)
        present_fields = [
            bool(title),
            bool(brand),
            bool(categories),
            bool(description),
        ]
        field_coverage = sum(1 for present in present_fields if present) / len(present_fields)
        rows.append(
            {
                "item_id": item_id,
                "source_id": source_id,
                "title": title,
                "brand": brand,
                "categories": categories,
                "description": description,
                "normalized_text": normalized_text,
                "title_present": int(bool(title)),
                "brand_present": int(bool(brand)),
                "categories_present": int(bool(categories)),
                "description_present": int(bool(description)),
                "text_length": len(normalized_text),
                "field_coverage": field_coverage,
            }
        )

    text_bank_path = dataset_dir / output_name
    pd.DataFrame(rows).sort_values("item_id").to_csv(text_bank_path, index=False)
    return text_bank_path


def _safe_normalize_rows(tensor: torch.Tensor) -> torch.Tensor:
    denom = torch.linalg.norm(tensor, dim=-1, keepdim=True).clamp_min(1e-12)
    return tensor / denom


def _masked_mean(values: torch.Tensor, mask: torch.Tensor, dim: int) -> torch.Tensor:
    mask_f = mask.float()
    while mask_f.dim() < values.dim():
        mask_f = mask_f.unsqueeze(-1)
    denom = mask_f.sum(dim=dim).clamp_min(1.0)
    return (values * mask_f).sum(dim=dim) / denom


def _renormalize_rows(weights: torch.Tensor, fallback: torch.Tensor) -> torch.Tensor:
    totals = weights.sum(dim=-1, keepdim=True)
    normalized = weights / totals.clamp_min(1e-12)
    return torch.where(totals > 0, normalized, fallback)


def load_agreement_null_stats(path: Path) -> dict[int, tuple[float, float]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    stats = payload.get("length_bins", {})
    parsed: dict[int, tuple[float, float]] = {}
    for raw_length, values in stats.items():
        length = int(raw_length)
        parsed[length] = (float(values["mu"]), float(values["sigma"]))
    return parsed


@dataclass
class TextSideContext:
    history_repr: torch.Tensor
    u: torch.Tensor
    proposal: torch.Tensor


class TextSideProposalBuilder(nn.Module):
    def __init__(
        self,
        item_embeddings: torch.Tensor,
        item_completeness: torch.Tensor,
        item_num: int,
        is_disliked_item: bool,
        item_popularity: torch.Tensor | None = None,
        temperature: float = 0.2,
        min_pseudo_mass: float = 0.05,
        kernel_version: str = "v1",
        g_max: float = 0.5,
        agreement_null_stats: dict[int, tuple[float, float]] | None = None,
        agreement_k: float = 2.0,
        agreement_weight: float = 0.45,
        completeness_weight: float = 0.15,
        history_reliability_weight: float = 0.40,
        ess_weight: float = 0.20,
        recency_weight: float = 0.30,
        stability_weight: float = 0.50,
        max_temperature_scale: float = 2.0,
        popularity_mix_scale: float = 1.0,
        popularity_mix_power: float = 1.0,
        center_embeddings: bool = False,
        pseudo_mass_scale: float = 1.0,
        pseudo_mass_power: float = 1.0,
        ablation_mode: str = "none",
        injection_mode: str = "kernel",
        loss_weight_scale: float = 1.0,
    ) -> None:
        super().__init__()
        if item_embeddings.shape[0] != item_num:
            raise ValueError(
                f"embedding row count {item_embeddings.shape[0]} does not match item_num {item_num}"
            )
        if item_completeness.shape[0] != item_num:
            raise ValueError(
                f"completeness row count {item_completeness.shape[0]} does not match item_num {item_num}"
            )
        if item_popularity is not None and item_popularity.shape[0] != item_num:
            raise ValueError(
                f"popularity row count {item_popularity.shape[0]} does not match item_num {item_num}"
            )

        self.item_num = int(item_num)
        self.is_disliked_item = bool(is_disliked_item)
        self.pad_value = self.item_num
        self.kernel_version = str(kernel_version)
        if self.kernel_version not in KERNEL_VERSIONS:
            raise ValueError(f"unsupported kernel_version: {self.kernel_version}")
        self.temperature = float(temperature)
        self.min_pseudo_mass = float(min_pseudo_mass)
        self.g_max = float(g_max)
        self.agreement_k = float(agreement_k)
        self.agreement_weight = float(agreement_weight)
        self.completeness_weight = float(completeness_weight)
        self.history_reliability_weight = float(history_reliability_weight)
        self.ess_weight = float(ess_weight)
        self.recency_weight = float(recency_weight)
        self.stability_weight = float(stability_weight)
        self.max_temperature_scale = float(max_temperature_scale)
        self.popularity_mix_scale = float(popularity_mix_scale)
        self.popularity_mix_power = float(popularity_mix_power)
        self.center_embeddings = bool(center_embeddings)
        self.pseudo_mass_scale = float(pseudo_mass_scale)
        self.pseudo_mass_power = float(pseudo_mass_power)
        self.ablation_mode = str(ablation_mode)
        if self.ablation_mode not in ABLATION_MODES:
            raise ValueError(f"unsupported ablation_mode: {self.ablation_mode}")
        self.injection_mode = str(injection_mode)
        if self.injection_mode not in INJECTION_MODES:
            raise ValueError(f"unsupported injection_mode: {self.injection_mode}")
        self.loss_weight_scale = float(loss_weight_scale)
        self.component_weight_sum = max(
            self.agreement_weight + self.completeness_weight + self.history_reliability_weight,
            1e-6,
        )
        self.history_weight_sum = max(self.ess_weight + self.recency_weight + self.stability_weight, 1e-6)

        embeddings = item_embeddings.detach().float()
        normalized_embeddings = _safe_normalize_rows(embeddings)
        self.register_buffer("item_embeddings", normalized_embeddings)
        if self.center_embeddings:
            centered_embeddings = normalized_embeddings - normalized_embeddings.mean(dim=0, keepdim=True)
            semantic_embeddings = _safe_normalize_rows(centered_embeddings)
        else:
            semantic_embeddings = normalized_embeddings
        self.register_buffer("semantic_embeddings", semantic_embeddings)
        self.register_buffer("item_completeness", item_completeness.detach().float().clamp(0.0, 1.0))
        popularity = torch.ones(item_num, dtype=torch.float32) if item_popularity is None else item_popularity.detach().float()
        popularity = popularity.clamp_min(1e-8)
        self.register_buffer("popularity_prior", popularity / popularity.sum())
        self.agreement_null_stats = dict(agreement_null_stats or {})
        self.agreement_null_lengths = sorted(self.agreement_null_stats)
        proposal_dim = self.item_num + (1 if self.is_disliked_item else 0)
        if self.kernel_version == "v2":
            self.p1 = nn.Parameter(torch.ones(proposal_dim, dtype=torch.float32))
        else:
            self.p1 = None

    @classmethod
    def from_files(
        cls,
        dataset_dir: Path,
        item_num: int,
        is_disliked_item: bool,
        embeddings_path: Path | None = None,
        text_bank_path: Path | None = None,
        temperature: float = 0.2,
        min_pseudo_mass: float = 0.05,
        kernel_version: str = "v1",
        g_max: float = 0.5,
        agreement_null_curve_path: Path | None = None,
        agreement_k: float = 2.0,
        agreement_weight: float = 0.45,
        completeness_weight: float = 0.15,
        history_reliability_weight: float = 0.40,
        ess_weight: float = 0.20,
        recency_weight: float = 0.30,
        stability_weight: float = 0.50,
        max_temperature_scale: float = 2.0,
        popularity_mix_scale: float = 1.0,
        popularity_mix_power: float = 1.0,
        center_embeddings: bool = False,
        pseudo_mass_scale: float = 1.0,
        pseudo_mass_power: float = 1.0,
        ablation_mode: str = "none",
        injection_mode: str = "kernel",
        loss_weight_scale: float = 1.0,
    ) -> "TextSideProposalBuilder":
        dataset_dir = Path(dataset_dir)
        if text_bank_path is None:
            text_bank_path = dataset_dir / TEXT_BANK_FILENAME
        if not Path(text_bank_path).exists():
            text_bank_path = ensure_text_bank(dataset_dir)
        if agreement_null_curve_path is None:
            default_null_curve_path = dataset_dir / DEFAULT_NULL_CURVE_FILENAME
            if default_null_curve_path.exists():
                agreement_null_curve_path = default_null_curve_path

        if embeddings_path is None:
            embeddings_path = dataset_dir / DEFAULT_EMBEDDING_FILENAME
        payload = torch.load(embeddings_path, map_location="cpu")
        popularity_path = dataset_dir / "items_pop.npy"
        if isinstance(payload, dict):
            embeddings = payload["embeddings"]
            completeness = payload.get("field_coverage")
        else:
            embeddings = payload
            completeness = None
        popularity = None
        if popularity_path.exists():
            popularity = torch.tensor(np.load(popularity_path), dtype=torch.float32)

        if completeness is None:
            text_bank = pd.read_csv(text_bank_path).sort_values("item_id")
            completeness = torch.tensor(text_bank["field_coverage"].to_numpy(), dtype=torch.float32)
        agreement_null_stats = None
        if agreement_null_curve_path is not None and Path(agreement_null_curve_path).exists():
            agreement_null_stats = load_agreement_null_stats(Path(agreement_null_curve_path))

        return cls(
            item_embeddings=torch.as_tensor(embeddings, dtype=torch.float32),
            item_completeness=torch.as_tensor(completeness, dtype=torch.float32),
            item_popularity=torch.as_tensor(popularity, dtype=torch.float32) if popularity is not None else None,
            item_num=item_num,
            is_disliked_item=is_disliked_item,
            temperature=temperature,
            min_pseudo_mass=min_pseudo_mass,
            kernel_version=kernel_version,
            g_max=g_max,
            agreement_null_stats=agreement_null_stats,
            agreement_k=agreement_k,
            agreement_weight=agreement_weight,
            completeness_weight=completeness_weight,
            history_reliability_weight=history_reliability_weight,
            ess_weight=ess_weight,
            recency_weight=recency_weight,
            stability_weight=stability_weight,
            max_temperature_scale=max_temperature_scale,
            popularity_mix_scale=popularity_mix_scale,
            popularity_mix_power=popularity_mix_power,
            center_embeddings=center_embeddings,
            pseudo_mass_scale=pseudo_mass_scale,
            pseudo_mass_power=pseudo_mass_power,
            ablation_mode=ablation_mode,
            injection_mode=injection_mode,
            loss_weight_scale=loss_weight_scale,
        )

    def _build_v1_context(
        self,
        *,
        similarity: torch.Tensor,
        raw_content_probs: torch.Tensor,
        popularity_prior: torch.Tensor,
        u: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        anchor_temperature_scale = torch.ones_like(u)
        anchor_popularity_mix = torch.zeros_like(u)
        anchor_content_probs = raw_content_probs
        anchor_item_probs = raw_content_probs

        if self.ablation_mode == "global_p":
            content_probs = raw_content_probs
            temperature_scale = torch.ones_like(u)
            popularity_mix = torch.ones_like(u)
            item_probs = popularity_prior
        else:
            if self.ablation_mode == "u_shuffle" and u.shape[0] > 1:
                shuffle_index = torch.randperm(u.shape[0], device=u.device)
                u = u[shuffle_index]

            if self.ablation_mode == "text_anchor_only":
                temperature_scale = torch.ones_like(u)
                popularity_mix = torch.zeros_like(u)
                item_probs = raw_content_probs
            else:
                temperature_scale = 1.0 + (self.max_temperature_scale - 1.0) * (1.0 - u)
                content_probs = torch.softmax(
                    similarity / (self.temperature * temperature_scale.unsqueeze(-1)),
                    dim=-1,
                )
                popularity_mix = self.popularity_mix_scale * torch.pow(
                    (1.0 - u).clamp(0.0, 1.0),
                    self.popularity_mix_power,
                )
                popularity_mix = popularity_mix.clamp(0.0, 1.0)
                item_probs = (1.0 - popularity_mix.unsqueeze(-1)) * content_probs + popularity_mix.unsqueeze(-1) * popularity_prior

            if self.ablation_mode == "text_anchor_only":
                content_probs = raw_content_probs

        if self.is_disliked_item:
            if self.ablation_mode == "global_p":
                adaptive_pseudo_mass = torch.full_like(u, self.min_pseudo_mass)
            elif self.ablation_mode == "text_anchor_only":
                adaptive_pseudo_mass = torch.full_like(u, self.min_pseudo_mass)
            else:
                adaptive_pseudo_mass = self.pseudo_mass_scale * torch.pow((1.0 - u).clamp(0.0, 1.0), self.pseudo_mass_power)
            adaptive_pseudo_mass = torch.clamp(adaptive_pseudo_mass, min=self.min_pseudo_mass, max=0.95)
            anchor_pseudo_mass = torch.full_like(u, self.min_pseudo_mass)
            adaptive_actual_mass = 1.0 - adaptive_pseudo_mass
            anchor_actual_mass = 1.0 - anchor_pseudo_mass
            adaptive_proposal = torch.cat(
                [
                    item_probs * adaptive_actual_mass.unsqueeze(-1),
                    adaptive_pseudo_mass.unsqueeze(-1),
                ],
                dim=-1,
            )
            anchor_proposal = torch.cat(
                [
                    anchor_item_probs * anchor_actual_mass.unsqueeze(-1),
                    anchor_pseudo_mass.unsqueeze(-1),
                ],
                dim=-1,
            )
        else:
            adaptive_pseudo_mass = torch.zeros_like(u)
            anchor_pseudo_mass = torch.zeros_like(u)
            adaptive_proposal = item_probs
            anchor_proposal = anchor_item_probs

        if self.injection_mode in {"encoder", "loss"} and self.ablation_mode == "none":
            proposal = anchor_proposal
            pseudo_mass = anchor_pseudo_mass
            temperature_scale = anchor_temperature_scale
            popularity_mix = anchor_popularity_mix
            content_probs = anchor_content_probs
        else:
            proposal = adaptive_proposal
            pseudo_mass = adaptive_pseudo_mass

        return {
            "temperature_scale": temperature_scale,
            "content_probs": content_probs,
            "popularity_prior": popularity_prior,
            "popularity_mix": popularity_mix,
            "anchor_proposal": anchor_proposal,
            "adaptive_proposal": adaptive_proposal,
            "pseudo_mass": pseudo_mass,
            "u": u,
            "proposal": proposal,
        }

    def _lookup_null_curve(self, history_lengths: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor] | None:
        if not self.agreement_null_lengths:
            return None

        mu_values = []
        sigma_values = []
        min_length = self.agreement_null_lengths[0]
        max_length = self.agreement_null_lengths[-1]
        for length_tensor in history_lengths.tolist():
            length = int(length_tensor)
            if length <= min_length:
                chosen_length = min_length
            elif length >= max_length:
                chosen_length = max_length
            elif length in self.agreement_null_stats:
                chosen_length = length
            else:
                chosen_length = min(
                    self.agreement_null_lengths,
                    key=lambda candidate: abs(candidate - length),
                )
            mu, sigma = self.agreement_null_stats[chosen_length]
            mu_values.append(mu)
            sigma_values.append(max(sigma, 1e-6))

        return (
            torch.tensor(mu_values, dtype=self.item_embeddings.dtype, device=history_lengths.device),
            torch.tensor(sigma_values, dtype=self.item_embeddings.dtype, device=history_lengths.device),
        )

    def _build_v2_context(
        self,
        *,
        raw_content_probs: torch.Tensor,
        agreement: torch.Tensor,
        history_lengths: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        if self.p1 is None:
            raise RuntimeError("v2 kernel requires learnable core proposal logits p1")

        completeness_weights = self.item_completeness.unsqueeze(0).expand_as(raw_content_probs).clamp(0.0, 1.0)
        content_anchor = _renormalize_rows(raw_content_probs * completeness_weights, raw_content_probs)

        null_curve = self._lookup_null_curve(history_lengths)
        if null_curve is None:
            u_tilde = agreement.clamp(0.0, 1.0)
        else:
            mu_null, sigma_null = null_curve
            u_tilde = (agreement - mu_null) / (self.agreement_k * sigma_null)
        if self.ablation_mode == "u_shuffle" and u_tilde.shape[0] > 1:
            shuffle_index = torch.randperm(u_tilde.shape[0], device=u_tilde.device)
            u_tilde = u_tilde[shuffle_index]

        if self.ablation_mode == "global_p":
            g = torch.zeros_like(u_tilde)
        elif self.ablation_mode == "text_anchor_only":
            g = torch.full_like(u_tilde, self.g_max)
        else:
            g = self.g_max * u_tilde.clamp(0.0, 1.0)

        p_core_full = torch.softmax(self.p1, dim=-1).unsqueeze(0).expand(raw_content_probs.shape[0], -1)
        if self.is_disliked_item:
            core_pseudo_mass = p_core_full[:, -1]
            real_core = _renormalize_rows(p_core_full[:, :-1], raw_content_probs)
            mixed_real = (1.0 - g.unsqueeze(-1)) * real_core + g.unsqueeze(-1) * content_anchor
            adaptive_proposal = torch.cat(
                [
                    mixed_real * (1.0 - core_pseudo_mass).unsqueeze(-1),
                    core_pseudo_mass.unsqueeze(-1),
                ],
                dim=-1,
            )
            anchor_real = (1.0 - self.g_max) * real_core + self.g_max * content_anchor
            anchor_proposal = torch.cat(
                [
                    anchor_real * (1.0 - core_pseudo_mass).unsqueeze(-1),
                    core_pseudo_mass.unsqueeze(-1),
                ],
                dim=-1,
            )
            pseudo_mass = core_pseudo_mass
        else:
            real_core = p_core_full
            adaptive_proposal = (1.0 - g.unsqueeze(-1)) * real_core + g.unsqueeze(-1) * content_anchor
            anchor_proposal = (1.0 - self.g_max) * real_core + self.g_max * content_anchor
            pseudo_mass = torch.zeros_like(g)

        if self.injection_mode in {"encoder", "loss"} and self.ablation_mode == "none":
            proposal = anchor_proposal
        else:
            proposal = adaptive_proposal

        return {
            "temperature_scale": torch.ones_like(g),
            "content_probs": content_anchor,
            "popularity_prior": p_core_full[:, :-1] if self.is_disliked_item else p_core_full,
            "popularity_mix": torch.zeros_like(g),
            "anchor_proposal": anchor_proposal,
            "adaptive_proposal": adaptive_proposal,
            "pseudo_mass": pseudo_mass,
            "u_tilde": u_tilde,
            "u": u_tilde.clamp(0.0, 1.0),
            "g": g,
            "p_core": p_core_full,
            "content_anchor": content_anchor,
            "proposal": proposal,
        }

    def encode_history_context(self, history_indices: torch.Tensor) -> dict[str, torch.Tensor]:
        if history_indices.dim() != 2:
            raise ValueError(f"history_indices must be rank-2, got shape {tuple(history_indices.shape)}")

        history = history_indices.long()
        valid_mask = history != self.pad_value
        safe_history = history.clamp(max=self.item_num - 1)
        valid_counts = valid_mask.sum(dim=1, keepdim=True).clamp_min(1)
        has_history = valid_mask.any(dim=1)

        gathered_embeddings = self.semantic_embeddings[safe_history]
        gathered_embeddings = gathered_embeddings * valid_mask.unsqueeze(-1)
        mean_embedding = gathered_embeddings.sum(dim=1) / valid_counts
        history_stability = torch.linalg.norm(mean_embedding, dim=-1).clamp(0.0, 1.0)
        history_repr = _safe_normalize_rows(mean_embedding)

        gathered_completeness = self.item_completeness[safe_history] * valid_mask.float()
        completeness = gathered_completeness.sum(dim=1) / valid_counts.squeeze(-1).float()

        item_similarity = (gathered_embeddings * history_repr.unsqueeze(1)).sum(dim=-1)
        agreement = _masked_mean((item_similarity + 1.0) * 0.5, valid_mask, dim=1)

        seq_len = max(history.shape[1], 1)
        history_ess = (valid_counts.squeeze(-1).float() / float(seq_len)).clamp(0.0, 1.0)

        position_scores = torch.arange(
            1,
            history.shape[1] + 1,
            device=history.device,
            dtype=self.item_embeddings.dtype,
        ).pow(2).unsqueeze(0)
        recency_weights = position_scores * valid_mask.float()
        recency_weights = recency_weights / recency_weights.sum(dim=1, keepdim=True).clamp_min(1.0)
        recent_embedding = (gathered_embeddings * recency_weights.unsqueeze(-1)).sum(dim=1)
        recent_repr = _safe_normalize_rows(recent_embedding)
        history_recency = ((recent_repr * history_repr).sum(dim=-1) + 1.0) * 0.5
        history_recency = torch.where(has_history, history_recency, torch.zeros_like(history_recency))

        history_reliability = (
            self.ess_weight * history_ess
            + self.recency_weight * history_recency
            + self.stability_weight * history_stability
        ) / self.history_weight_sum

        u = (
            self.agreement_weight * agreement
            + self.completeness_weight * completeness
            + self.history_reliability_weight * history_reliability
        ) / self.component_weight_sum
        u = u.clamp(0.0, 1.0)

        similarity = history_repr @ self.semantic_embeddings.T
        raw_content_probs = torch.softmax(similarity / self.temperature, dim=-1)
        popularity_prior = self.popularity_prior.unsqueeze(0).expand(history.shape[0], -1)
        if self.kernel_version == "v2":
            proposal_context = self._build_v2_context(
                raw_content_probs=raw_content_probs,
                agreement=agreement,
                history_lengths=valid_counts.squeeze(-1).long(),
            )
        else:
            proposal_context = self._build_v1_context(
                similarity=similarity,
                raw_content_probs=raw_content_probs,
                popularity_prior=popularity_prior,
                u=u,
            )

        loss_weight = None
        if self.injection_mode == "loss":
            loss_weight = 1.0 + self.loss_weight_scale * proposal_context["u"]

        context = {
            "history_repr": history_repr,
            "agreement": agreement,
            "completeness": completeness,
            "history_ess": history_ess,
            "history_recency": history_recency,
            "history_stability": history_stability,
            "history_reliability": history_reliability,
            "loss_weight": loss_weight,
        }
        context.update(proposal_context)
        return context
