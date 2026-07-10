#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import uuid
from pathlib import Path
from typing import Any, Callable, Sequence


Runner = Callable[..., subprocess.CompletedProcess[str]]


def _path_text(path: Path) -> str:
    value = str(path).replace("\\", "/")
    if value.startswith("/") or (value.startswith("\\") and not value.startswith("//")):
        value = "/" + value.lstrip("/")
    return value


def _expected_metadata(session: str, queue_root: Path, manifest_sha256: str) -> dict[str, str]:
    return {
        "session": session,
        "queue_root": _path_text(queue_root),
        "manifest_sha256": manifest_sha256,
    }


def _metadata_matches(metadata: dict[str, Any], expected: dict[str, str]) -> bool:
    for key, value in expected.items():
        actual = metadata.get(key)
        if key == "queue_root" and isinstance(actual, str):
            actual = _path_text(Path(actual))
        if actual != value:
            return False
    return True


def _run(runner: Runner, argv: list[str]) -> subprocess.CompletedProcess[str]:
    return runner(argv, check=False, capture_output=True, text=True)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    try:
        with temporary.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def ensure_session(
    *,
    session: str,
    queue_root: Path,
    manifest: Path,
    python_bin: Path,
    controller_entry: Path,
    runner: Runner = subprocess.run,
    metadata: dict[str, Any] | None = None,
    manifest_sha256: str,
) -> str:
    if socket.gethostname() != "ubuntu":
        raise RuntimeError("remote tmux entry requires hostname ubuntu")
    if not session or any(char.isspace() for char in session):
        raise ValueError("session must be a nonempty name without whitespace")
    if len(manifest_sha256) != 64 or any(char not in "0123456789abcdef" for char in manifest_sha256):
        raise ValueError("manifest_sha256 must be lowercase SHA-256")

    expected = _expected_metadata(session, queue_root, manifest_sha256)
    existing = dict(metadata or {})
    if existing and not _metadata_matches(existing, expected):
        raise RuntimeError("tmux metadata mismatch")

    has_session = _run(runner, ["tmux", "has-session", "-t", session])

    terminal_path = queue_root / "state" / "TERMINAL.json"
    if terminal_path.is_file():
        try:
            terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("terminal marker is unreadable") from exc
        if terminal.get("status") == "terminal":
            return "terminal"

    if has_session.returncode == 0:
        return "already_running"

    root = queue_root.resolve(strict=False)
    root.mkdir(parents=True, exist_ok=True)
    state = root / "state"
    state.mkdir(parents=True, exist_ok=True)
    new_session = [
        "tmux",
        "new-session",
        "-d",
        "-s",
        session,
        str(python_bin),
        str(controller_entry),
        "run",
        "--queue-root",
        str(root),
        "--manifest",
        str(manifest),
    ]
    started = _run(runner, new_session)
    if started.returncode != 0:
        raise RuntimeError(f"tmux new-session failed: {(started.stderr or '').strip()}")
    _atomic_write_json(state / "tmux_session.json", expected)
    return "started"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Idempotently start the resident queue controller inside tmux.")
    parser.add_argument("--queue-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--python-bin", type=Path, required=True)
    parser.add_argument("--controller-entry", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if not args.manifest.is_file():
        raise SystemExit(f"manifest does not exist: {args.manifest}")
    metadata_path = args.queue_root / "state" / "tmux_session.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else None
    result = ensure_session(
        session=args.session,
        queue_root=args.queue_root,
        manifest=args.manifest,
        python_bin=args.python_bin,
        controller_entry=args.controller_entry,
        metadata=metadata,
        manifest_sha256=_sha256(args.manifest),
    )
    print(result)


if __name__ == "__main__":
    main()
