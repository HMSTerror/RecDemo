#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shlex
import subprocess
from pathlib import PurePosixPath
from typing import Sequence


SSH_BASE = ["ssh", "-n", "-T", "-o", "BatchMode=yes"]
DEFAULT_HOST = "zijian@172.18.0.40"
DEFAULT_REMOTE_PYTHON = "/data/Zijian/goal/PreferGrow/.venv/bin/python"
DEFAULT_REMOTE_ENTRY = "/data/Zijian/goal/aaai27_bundle/scripts/aaai27_remote_tmux_entry.py"
DEFAULT_CONTROLLER_PYTHON = DEFAULT_REMOTE_PYTHON
DEFAULT_CONTROLLER_ENTRY = "/data/Zijian/goal/aaai27_bundle/scripts/aaai27_resident_queue.py"
DEFAULT_QUEUE_ROOT = "/data/Zijian/goal/RecDemoRuns/aaai27_seed100_resident_20260710-220000"
DEFAULT_MANIFEST = f"{DEFAULT_QUEUE_ROOT}/queue/queue_seed100.json"
DEFAULT_SESSION = "aaai27_seed100_queue"


def build_ssh_argv(
    *,
    host: str,
    remote_python: str,
    remote_entry: str,
    queue_root: str,
    manifest: str,
    session: str,
    python_bin: str,
    controller_entry: str,
    connect_timeout: int | None = None,
) -> list[str]:
    base = list(SSH_BASE)
    if connect_timeout is not None:
        if connect_timeout <= 0:
            raise ValueError("connect_timeout must be positive")
        base.extend(["-o", f"ConnectTimeout={connect_timeout}"])
    remote_argv = [
        remote_python,
        remote_entry,
        "--queue-root",
        queue_root,
        "--manifest",
        manifest,
        "--session",
        session,
        "--python-bin",
        python_bin,
        "--controller-entry",
        controller_entry,
    ]
    return [*base, host, shlex.join(remote_argv)]


def launch_queue(
    *,
    host: str,
    remote_python: str,
    remote_entry: str,
    queue_root: str,
    manifest: str,
    session: str,
    python_bin: str,
    controller_entry: str,
    connect_timeout: int | None = None,
    print_only: bool = False,
) -> list[str]:
    argv = build_ssh_argv(
        host=host,
        remote_python=remote_python,
        remote_entry=remote_entry,
        queue_root=queue_root,
        manifest=manifest,
        session=session,
        python_bin=python_bin,
        controller_entry=controller_entry,
        connect_timeout=connect_timeout,
    )
    if not print_only:
        subprocess.run(argv, check=True)
    return argv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the validated AAAI-27 seed-100 queue on l20.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--remote-python", default=DEFAULT_REMOTE_PYTHON)
    parser.add_argument("--remote-entry", default=DEFAULT_REMOTE_ENTRY)
    parser.add_argument("--queue-root", default=DEFAULT_QUEUE_ROOT)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--session", default=DEFAULT_SESSION)
    parser.add_argument("--python-bin", default=DEFAULT_CONTROLLER_PYTHON)
    parser.add_argument("--controller-entry", default=DEFAULT_CONTROLLER_ENTRY)
    parser.add_argument("--connect-timeout", type=int, default=None)
    parser.add_argument("--print-only", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    command = launch_queue(
        host=args.host,
        remote_python=args.remote_python,
        remote_entry=args.remote_entry,
        queue_root=args.queue_root,
        manifest=args.manifest,
        session=args.session,
        python_bin=args.python_bin,
        controller_entry=args.controller_entry,
        connect_timeout=args.connect_timeout,
        print_only=args.print_only,
    )
    print(shlex.join(command))


if __name__ == "__main__":
    main()
