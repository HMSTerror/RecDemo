from __future__ import annotations

import math
import re
from typing import Any

from .common import stable_sha256


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_HASH_FIELDS = (
    "split_sha256",
    "bank_sha256",
    "text_bank_sha256",
    "null_curve_sha256",
    "item_completeness_sha256",
    "popularity_sha256",
)


def _reject_validation_test(value: Any, path: str = "manifest") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).casefold()
            if any(token in lowered for token in ("validation", "test")):
                raise ValueError(f"proposal provenance must be train-only; forbidden field {path}.{key}")
            _reject_validation_test(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_validation_test(child, f"{path}[{index}]")


def _require_hash(manifest: dict[str, Any], key: str) -> str:
    value = str(manifest.get(key, "")).casefold()
    if not _SHA256.fullmatch(value):
        raise ValueError(f"proposal manifest field {key} must be a 64-character SHA-256 digest")
    return value


def validate_proposal_manifest(
    manifest: dict[str, Any],
    *,
    expected_dataset: str,
    expected_bank_sha256: str | None = None,
) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise ValueError("proposal manifest must be an object")
    _reject_validation_test(manifest)
    if str(manifest.get("dataset")) != str(expected_dataset):
        raise ValueError("proposal manifest dataset mismatch")
    if str(manifest.get("split_name", "")).casefold() != "train":
        raise ValueError("proposal manifest must be train-only")
    for key in _HASH_FIELDS:
        _require_hash(manifest, key)
    core_hash = manifest.get("core_p1_sha256", manifest.get("core_artifact_sha256"))
    if not _SHA256.fullmatch(str(core_hash or "").casefold()):
        raise ValueError("proposal manifest must bind a core proposal artifact hash")
    bank_hash = str(manifest["bank_sha256"]).casefold()
    if expected_bank_sha256 is not None and bank_hash != str(expected_bank_sha256).casefold():
        raise ValueError("proposal manifest bank hash mismatch")
    frozen_config = manifest.get("frozen_config") if isinstance(manifest.get("frozen_config"), dict) else {}
    kernel_version = str(manifest.get("kernel_version", frozen_config.get("kernel_version", "")))
    if kernel_version not in {"v1", "v2"}:
        raise ValueError("proposal manifest kernel_version must be v1 or v2")
    try:
        temperature = float(manifest.get("temperature", frozen_config.get("temperature")))
        g_max = float(manifest.get("g_max", frozen_config.get("g_max")))
    except (TypeError, ValueError) as exc:
        raise ValueError("proposal manifest must bind temperature and g_max") from exc
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("proposal manifest temperature must be positive and finite")
    if not math.isfinite(g_max) or not 0.0 <= g_max <= 1.0:
        raise ValueError("proposal manifest g_max must be in [0, 1]")
    if int(manifest.get("generation_seed", manifest.get("random_seed", -1))) != 100:
        raise ValueError("proposal manifest requires generation_seed=100")
    checked = dict(manifest)
    checked.update(
        {
            "kernel_version": kernel_version,
            "temperature": temperature,
            "g_max": g_max,
            "core_proposal_sha256": str(core_hash).casefold(),
        }
    )
    checked["manifest_sha256"] = stable_sha256(checked)
    return checked
