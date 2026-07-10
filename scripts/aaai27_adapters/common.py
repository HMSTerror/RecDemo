from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def atomic_write_json(path: Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"immutable artifact already exists: {path}")
    fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    tmp = Path(raw_tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def write_bytes_exclusive(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _normalise_item_ids(values: Any, expected_count: int, *, label: str = "item_ids") -> list[int]:
    if hasattr(values, "detach"):
        values = values.detach().cpu().numpy()
    if isinstance(values, np.ndarray):
        values = values.tolist()
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{label} must be a one-dimensional sequence")
    normalised: list[int] = []
    for raw in values:
        if isinstance(raw, bool):
            raise ValueError(f"{label} must contain integer IDs")
        try:
            integer = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must contain integer IDs") from exc
        if str(raw).strip() not in {str(integer), f"{integer}.0"} and not isinstance(raw, (int, np.integer)):
            raise ValueError(f"{label} must contain integer IDs")
        normalised.append(integer)
    if len(normalised) != int(expected_count):
        raise ValueError(f"{label} length {len(normalised)} does not match embedding rows {expected_count}")
    if len(set(normalised)) != len(normalised):
        raise ValueError(f"{label} must contain unique IDs")
    return normalised


def load_embedding_payload(path: Path, *, expected_item_ids: Any | None = None) -> dict[str, Any]:
    path = Path(path)
    suffix = path.suffix.lower()
    item_ids: Any | None = None
    if suffix == ".npy":
        matrix = np.load(path, allow_pickle=False)
    elif suffix == ".npz":
        payload = np.load(path, allow_pickle=False)
        if "embeddings" not in payload:
            raise ValueError("npz embedding artifact must contain embeddings")
        matrix = payload["embeddings"]
        if "item_ids" in payload:
            item_ids = payload["item_ids"]
    elif suffix in {".pt", ".pth"}:
        try:
            import torch
        except ImportError as exc:  # pragma: no cover - production environment supplies torch
            raise RuntimeError("torch is required to load .pt embedding artifacts") from exc
        payload = torch.load(path, map_location="cpu", weights_only=False)
        if isinstance(payload, dict):
            item_ids = payload.get("item_ids")
            payload = payload.get("embeddings", payload.get("item_embeddings", payload))
        if hasattr(payload, "detach"):
            payload = payload.detach().cpu().numpy()
        matrix = np.asarray(payload)
    else:
        raise ValueError(f"unsupported embedding artifact suffix: {path.suffix}")
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[0] < 10 or matrix.shape[1] == 0:
        raise ValueError("embedding matrix must be [real_item_count, embedding_dim] with at least 10 items")
    if not np.isfinite(matrix).all():
        raise ValueError("embedding matrix contains non-finite values")
    if item_ids is not None:
        item_ids = _normalise_item_ids(item_ids, matrix.shape[0])
    if expected_item_ids is not None:
        expected = _normalise_item_ids(expected_item_ids, matrix.shape[0], label="expected item ID mapping")
        if item_ids is None:
            raise ValueError("embedding payload lacks item IDs required for item ID mapping audit")
        if item_ids != expected:
            raise ValueError("embedding payload item ID mapping does not match expected item ID mapping")
    return {
        "matrix": np.asarray(matrix, dtype=np.float32),
        "item_ids": item_ids,
        "item_id_mapping_sha256": stable_sha256(item_ids) if item_ids is not None else None,
        "embedding_shape": [int(matrix.shape[0]), int(matrix.shape[1])],
    }


def load_embedding_matrix(path: Path) -> np.ndarray:
    return load_embedding_payload(path)["matrix"]


def load_jsonl_records(path: Path) -> list[dict[str, Any]]:
    path = Path(path)
    records: list[dict[str, Any]] = []
    if path.suffix.lower() == ".jsonl":
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"record {line_number} in {path} is not an object")
                records.append(value)
    elif path.suffix.lower() == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise ValueError("JSON transition artifact must contain a list of objects")
        records = [dict(item) for item in value]
    elif path.suffix.lower() == ".csv":
        import csv

        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                converted = dict(row)
                for field in ("history_item_ids", "q_text", "q_core"):
                    if field in converted and isinstance(converted[field], str):
                        converted[field] = json.loads(converted[field])
                for field in ("target_item_id", "user_id"):
                    if field in converted and converted[field] not in (None, ""):
                        converted[field] = int(converted[field])
                records.append(converted)
    elif path.suffix.lower() == ".df":
        # The project stores split transitions as pickled pandas DataFrames with
        # a ``.df`` suffix.  Load only the train artifact selected by the caller
        # and map its native columns to the adapter's explicit schema; no split
        # inference or re-splitting is performed here.
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover - production environment supplies pandas
            raise RuntimeError("pandas is required to load .df transition artifacts") from exc

        frame = pd.read_pickle(path)
        if not isinstance(frame, pd.DataFrame):
            raise ValueError(f".df transition artifact must contain a pandas DataFrame: {path}")
        user_column = "user_id" if "user_id" in frame.columns else "user" if "user" in frame.columns else None
        if "next" not in frame.columns:
            raise ValueError(".df transition artifact must contain a 'next' target column")
        if "seq" not in frame.columns:
            raise ValueError(".df transition artifact must contain a 'seq' history column")

        def _python_value(value: Any) -> Any:
            if hasattr(value, "tolist"):
                value = value.tolist()
            if isinstance(value, tuple):
                return [_python_value(item) for item in value]
            if isinstance(value, list):
                return [_python_value(item) for item in value]
            if isinstance(value, np.generic):
                return value.item()
            return value

        for index, row in frame.iterrows():
            history = _python_value(row["seq"])
            if not isinstance(history, list):
                raise ValueError(".df 'seq' values must be list-like histories")
            target = _python_value(row["next"])
            record: dict[str, Any] = {
                "row_id": str(index),
                "history_item_ids": history,
                "target_item_id": int(target),
            }
            if user_column is not None:
                user = _python_value(row[user_column])
                if user is not None:
                    record["user_id"] = int(user)
            records.append(record)
    else:
        raise ValueError(f"transition artifact must be .jsonl, .json, .csv, or .df: {path}")
    if not records:
        raise ValueError(f"transition artifact is empty: {path}")
    return records


def normalise_distribution(values: Any, label: str, expected_size: int) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.shape != (expected_size,) or not np.isfinite(array).all() or np.any(array < 0):
        raise ValueError(f"{label} must be a finite nonnegative vector of length {expected_size}")
    total = float(array.sum())
    if total <= 0:
        raise ValueError(f"{label} must have positive mass")
    return array / total
