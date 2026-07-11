"""Read-only marker verifier used by the continuation contract-gate task."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:  # pragma: no cover - direct CLI invocation
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.aaai27_adapters.common import stable_sha256
from scripts.aaai27_queue.storage import atomic_create_json, require_within, sha256_file


def _load(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"missing {label}: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return value


def _payload_hash(value: dict[str, Any]) -> str:
    body = dict(value)
    body.pop("artifact_sha256", None)
    return stable_sha256(body)


def _resolve(root: Path, value: str | Path, label: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        return require_within(candidate, root)
    except ValueError as exc:
        raise ValueError(f"{label} leaves queue root") from exc


def verify_method_pass_gate(
    queue_root: Path,
    e1_marker_path: str | Path,
    risk08_marker_path: str | Path,
    risk05_preregistration_sha256: str,
) -> dict[str, Any]:
    root = Path(queue_root).resolve(strict=False)
    e1_path = _resolve(root, e1_marker_path, "E1 marker")
    risk08_path = _resolve(root, risk08_marker_path, "RISK-08 marker")
    e1 = _load(e1_path, "E1 marker")
    risk08 = _load(risk08_path, "RISK-08 marker")
    if e1.get("risk_id") != "RISK-02" or e1.get("outcome") != "pass" or int(e1.get("random_seed", -1)) != 100:
        raise ValueError("E1 marker is not a seed-100 PASS")
    if risk08.get("risk_id") != "RISK-08" or risk08.get("exit") != "risk_gated_method":
        raise ValueError("RISK-08 marker is not risk_gated_method")
    e1_sha = sha256_file(e1_path)
    if risk08.get("e1_marker_sha256") != e1_sha:
        raise ValueError("RISK-08 E1 marker hash mismatch")
    if risk08.get("risk05_preregistration_sha256") != str(risk05_preregistration_sha256):
        raise ValueError("RISK-08 RISK-05 preregistration hash mismatch")
    if "artifact_sha256" in e1 and e1["artifact_sha256"] != _payload_hash(e1):
        raise ValueError("E1 marker self hash mismatch")
    if "artifact_sha256" in risk08 and risk08["artifact_sha256"] != _payload_hash(risk08):
        raise ValueError("RISK-08 marker self hash mismatch")
    result: dict[str, Any] = {
        "schema_version": 1,
        "status": "pass",
        "risk_id": "RISK-08",
        "exit": "risk_gated_method",
        "e1_marker_sha256": e1_sha,
        "risk08_marker_sha256": sha256_file(risk08_path),
        "risk05_preregistration_sha256": str(risk05_preregistration_sha256),
        "training_started": False,
    }
    result["artifact_sha256"] = _payload_hash(result)
    atomic_create_json(root / "state" / "method_pass_gate.json", result)
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Verify immutable method-pass markers without launching training.")
    parser.add_argument("--queue-root", type=Path, required=True)
    parser.add_argument("--e1-marker", required=True)
    parser.add_argument("--risk08-marker", required=True)
    parser.add_argument("--risk05-preregistration-sha256", required=True)
    args = parser.parse_args(argv)
    result = verify_method_pass_gate(args.queue_root, args.e1_marker, args.risk08_marker, args.risk05_preregistration_sha256)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":  # pragma: no cover
    main()
