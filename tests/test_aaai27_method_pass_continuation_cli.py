from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from unittest import mock
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.aaai27_method_pass_continuation import (
    prepare_queue,
    status_queue,
    validate_queue,
)
import scripts.aaai27_method_pass_continuation as continuation_cli
from tests.test_aaai27_continuation_manifest import _inputs
from tests.test_aaai27_continuation_upstream import _build_r7_fixture
from tests.test_audit_e05_sasrec_reuse import _fixture as build_e5_fixture


UTC8 = timezone(timedelta(hours=8))


def test_cli_supports_the_documented_direct_script_entrypoint() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "aaai27_method_pass_continuation.py"),
            "--help",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "method-pass continuation" in result.stdout


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _posix(path: Path) -> str:
    value = path.resolve().as_posix()
    return value[2:] if len(value) >= 2 and value[1] == ":" else value


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _protocol(tmp_path: Path, *, exit_value: str | None = None) -> tuple[Path, Path]:
    binding = _build_r7_fixture(
        tmp_path / "upstream",
        exit_value=exit_value,
        passed=14 if exit_value else 8,
    )
    queue_root = tmp_path / "continuation"
    source_root = tmp_path / "source"
    for relative in (
        "single_train.py",
        "graph_lib.py",
        "model/text_side.py",
        "scripts/run_aaai27_pilot_task.py",
        "scripts/audit_e05_sasrec_reuse.py",
        "scripts/aaai27_method_pass_continuation.py",
    ):
        _write(source_root / relative, f"# fixture {relative}\n")
    source_manifest = source_root / "source_manifest.txt"
    _write(source_manifest, "fixture-source-manifest\n")
    ledger = source_root / "issues" / "risk.csv"
    _write(ledger, "id,status\nRISK-13,approved\n")
    e5_root = build_e5_fixture(tmp_path / "e5")

    base = _inputs()
    inputs = replace(
        base,
        queue_root=_posix(queue_root),
        source_root=_posix(source_root),
        source_manifest_sha256=_sha256(source_manifest),
        ledger_path=_posix(ledger),
        ledger_sha256=_sha256(ledger),
        e5_root=_posix(e5_root),
    )
    protocol = {
        "schema_version": 1,
        "inputs": asdict(inputs),
        "source_manifest_path": _posix(source_manifest),
        "upstream": {
            "queue_root": _posix(binding.queue_root),
            "manifest_path": _posix(binding.manifest_path),
            "manifest_sha256": binding.manifest_sha256,
            "finalizer_config_path": _posix(binding.finalizer_config_path),
            "finalizer_config_sha256": binding.finalizer_config_sha256,
            "expected_active_tasks": 14,
        },
        "maintenance": {
            "planned_shutdown": datetime(2026, 7, 17, 0, 0, tzinfo=UTC8).isoformat(),
            "launch_cutoff": datetime(2026, 7, 16, 12, 0, tzinfo=UTC8).isoformat(),
            "buffer_hours": 3.0,
        },
    }
    protocol_path = tmp_path / "prepare_protocol.json"
    protocol_path.write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")
    return protocol_path, queue_root


def test_prepare_writes_manifest_bindings_and_ready_adapter_markers(tmp_path: Path) -> None:
    protocol_path, root = _protocol(tmp_path)
    result = prepare_queue(protocol_path)
    assert result["status"] == "prepared"
    assert (root / "queue" / "queue_seed100_continuation.json").is_file()
    assert (root / "protocol" / "upstream_binding.json").is_file()
    assert (root / "protocol" / "maintenance_window.json").is_file()
    for dataset in ("Steam", "ML1M", "Beauty", "ATG"):
        assert (
            root
            / "protocol"
            / "adapters"
            / "prefergrow"
            / dataset
            / "PASS.json"
        ).is_file()
    assert (root / "protocol" / "adapters" / "sasrec" / "PASS.json").is_file()
    assert not (root / "protocol" / "adapters" / "caser" / "PASS.json").exists()


def test_validate_and_status_are_read_only_while_r7_waits(tmp_path: Path) -> None:
    protocol_path, root = _protocol(tmp_path)
    prepare_queue(protocol_path)
    before = {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in root.rglob("*")
        if path.is_file()
    }
    validated = validate_queue(root)
    status = status_queue(root, now=lambda: datetime(2026, 7, 15, 12, 0, tzinfo=UTC8))
    after = {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in root.rglob("*")
        if path.is_file()
    }
    assert validated["status"] == "valid"
    assert status["gate"] == "waiting_r7"
    assert status["counts"]["blocked_upstream"] == 37
    assert status["gpu_slots_per_card"] == 2
    assert status["min_free_gpu_memory_mib"] == 8192
    assert before == after


def test_prepare_refuses_existing_nonempty_root(tmp_path: Path) -> None:
    protocol_path, root = _protocol(tmp_path)
    root.mkdir(parents=True)
    _write(root / "foreign.txt", "do not overwrite\n")
    try:
        prepare_queue(protocol_path)
    except FileExistsError as exc:
        assert "nonempty" in str(exc)
    else:
        raise AssertionError("prepare_queue overwrote an existing nonempty root")


def test_continuation_runtime_uses_two_slots_and_eight_gib_reserve(tmp_path: Path) -> None:
    lock_backend = object()
    with mock.patch.object(continuation_cli, "QueueRuntime") as runtime_class:
        continuation_cli._queue_runtime(tmp_path, lock_backend)

    kwargs = runtime_class.call_args.kwargs
    assert kwargs["max_processes_per_gpu"] == 2
    assert kwargs["min_free_memory_mib"] == 8192
