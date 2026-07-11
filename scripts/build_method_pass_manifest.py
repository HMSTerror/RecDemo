"""CLI wrapper for the build-only method-pass continuation adapter."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:  # pragma: no cover - direct CLI invocation
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.aaai27_adapters.common import sha256_file
from scripts.aaai27_adapters.continuation_adapters import build_method_pass_manifest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build a dated seed-100 method-pass continuation manifest without launching training.")
    parser.add_argument("--protocol-json", type=Path, required=True)
    parser.add_argument("--base-manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--e1-marker-json", type=Path, required=True)
    parser.add_argument("--risk08-marker-json", type=Path, required=True)
    parser.add_argument("--risk05-preregistration-json", type=Path, required=True)
    parser.add_argument("--diffrec-audit-json", type=Path)
    args = parser.parse_args(argv)

    protocol = json.loads(args.protocol_json.read_text(encoding="utf-8"))
    base_manifest = json.loads(args.base_manifest.read_text(encoding="utf-8"))
    manifest = build_method_pass_manifest(
        protocol,
        base_manifest,
        args.output_root,
        e1_marker_path=args.e1_marker_json,
        risk08_marker_path=args.risk08_marker_json,
        risk05_preregistration_path=args.risk05_preregistration_json,
        diffrec_audit_path=args.diffrec_audit_json,
    )
    queue_path = args.output_root / "queue" / "queue_seed100_method_pass.json"
    continuation = [task for task in manifest["tasks"] if task["phase"] == "continuation"]
    print(json.dumps({
        "status": "manifest_built",
        "queue_manifest": str(queue_path),
        "queue_manifest_sha256": sha256_file(queue_path),
        "continuation_task_count": len(continuation),
        "training_started": False,
        "remote_launch": False,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":  # pragma: no cover
    main()
