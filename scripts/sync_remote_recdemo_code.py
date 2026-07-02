#!/usr/bin/env python3

from __future__ import annotations

import argparse
import io
import shlex
import subprocess
import tarfile
import time
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REMOTE_HOST = "l20"
DEFAULT_REMOTE_REPO_ROOT = PurePosixPath("/data/Zijian/goal/RecDemo")
DEFAULT_CONNECT_TIMEOUT_SECONDS = 15
DEFAULT_RETRIES = 3
DEFAULT_RETRY_DELAY_SECONDS = 5
DEFAULT_SYNC_REL_PATHS = (
    "configs/config.yaml",
    "data.py",
    "dataset_runtime.py",
    "graph_lib.py",
    "losses.py",
    "noise_lib.py",
    "sampling.py",
    "single_train.py",
    "utility.py",
    "utils.py",
    "model/__init__.py",
    "model/ema.py",
    "model/fused_add_dropout_scale.py",
    "model/text_side.py",
    "model/transformer.py",
    "model/utils.py",
    "scripts/build_agreement_null_curves.py",
    "scripts/build_gate0_failure_diagnostic.py",
    "scripts/build_gate0_utilde_report.py",
    "scripts/build_text_side_embeddings.py",
    "scripts/launch_beauty_text_side_tmux.py",
    "scripts/launch_gate0_tmux.py",
)


def _to_posix_path(pathlike: Path | PurePosixPath | str) -> PurePosixPath:
    return PurePosixPath(str(pathlike).replace("\\", "/"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync the minimal local RecDemo code needed for Gate0 / Beauty runs to the remote l20 repo."
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--remote-host", default=DEFAULT_REMOTE_HOST)
    parser.add_argument("--remote-repo-root", default=str(DEFAULT_REMOTE_REPO_ROOT))
    parser.add_argument("--rel-path", action="append", default=[], help="Relative file to sync; repeat as needed.")
    parser.add_argument("--no-verify", action="store_true", help="Skip remote py_compile verification after sync.")
    parser.add_argument("--connect-timeout", type=int, default=DEFAULT_CONNECT_TIMEOUT_SECONDS)
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--retry-delay-seconds", type=int, default=DEFAULT_RETRY_DELAY_SECONDS)
    parser.add_argument("--print-plan", action="store_true", help="Print sync plan without executing it.")
    return parser.parse_args()


def normalize_rel_paths(rel_paths: Sequence[str]) -> tuple[str, ...]:
    if rel_paths:
        return tuple(rel_paths)
    return DEFAULT_SYNC_REL_PATHS


def build_sync_pairs(
    repo_root: Path,
    remote_repo_root: Path | PurePosixPath | str,
    rel_paths: Sequence[str],
) -> list[tuple[Path, PurePosixPath]]:
    remote_repo_root = _to_posix_path(remote_repo_root)
    pairs: list[tuple[Path, PurePosixPath]] = []
    for rel_path in rel_paths:
        local_path = repo_root / rel_path
        remote_path = remote_repo_root / PurePosixPath(rel_path.replace("\\", "/"))
        pairs.append((local_path, remote_path))
    return pairs


def build_remote_verify_command(
    remote_repo_root: Path | PurePosixPath | str,
    rel_paths: Sequence[str],
) -> str:
    remote_repo_root = _to_posix_path(remote_repo_root)
    quoted_targets = " ".join(
        shlex.quote(str(remote_repo_root / PurePosixPath(rel_path.replace("\\", "/"))))
        for rel_path in rel_paths
        if rel_path.endswith(".py")
    )
    return f"cd {shlex.quote(str(remote_repo_root))} && python3 -m py_compile {quoted_targets}"


def build_sync_shell_command(
    remote_repo_root: Path | PurePosixPath | str,
    rel_paths: Sequence[str],
    *,
    verify: bool,
) -> str:
    remote_repo_root = _to_posix_path(remote_repo_root)
    commands = [
        f"mkdir -p {shlex.quote(str(remote_repo_root))}",
        f"tar -xf - -C {shlex.quote(str(remote_repo_root))}",
    ]
    if verify:
        commands.append(build_remote_verify_command(remote_repo_root=remote_repo_root, rel_paths=rel_paths))
    return " && ".join(commands)


def build_sync_argv(
    host: str,
    remote_repo_root: Path | PurePosixPath | str,
    rel_paths: Sequence[str],
    connect_timeout: int = DEFAULT_CONNECT_TIMEOUT_SECONDS,
    verify: bool = True,
) -> list[str]:
    return [
        "ssh",
        "-o",
        f"ConnectTimeout={connect_timeout}",
        host,
        build_sync_shell_command(remote_repo_root=remote_repo_root, rel_paths=rel_paths, verify=verify),
    ]


def build_archive_payload(
    repo_root: Path,
    rel_paths: Sequence[str],
) -> bytes:
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        for rel_path in rel_paths:
            local_path = repo_root / rel_path
            archive.add(local_path, arcname=rel_path.replace("\\", "/"))
    return payload.getvalue()


def run_with_retries(
    argv: Sequence[str],
    *,
    input_bytes: bytes | None = None,
    retries: int = DEFAULT_RETRIES,
    retry_delay_seconds: int = DEFAULT_RETRY_DELAY_SECONDS,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    sleeper: Callable[[float], None] = time.sleep,
) -> None:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            runner(argv, input=input_bytes, check=True)
            return
        except (subprocess.CalledProcessError, OSError) as exc:
            last_error = exc
            if attempt >= retries:
                raise
            sleeper(retry_delay_seconds)
    if last_error is not None:
        raise last_error


def sync_remote_code(
    *,
    repo_root: Path,
    remote_repo_root: Path | PurePosixPath | str,
    host: str,
    rel_paths: Sequence[str],
    verify: bool = True,
    connect_timeout: int = DEFAULT_CONNECT_TIMEOUT_SECONDS,
    retries: int = DEFAULT_RETRIES,
    retry_delay_seconds: int = DEFAULT_RETRY_DELAY_SECONDS,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    sleeper: Callable[[float], None] = time.sleep,
) -> None:
    pairs = build_sync_pairs(repo_root=repo_root, remote_repo_root=remote_repo_root, rel_paths=rel_paths)
    missing = [str(local_path) for local_path, _ in pairs if not local_path.exists()]
    if missing:
        raise FileNotFoundError(f"missing local sync inputs: {', '.join(missing)}")

    payload = build_archive_payload(repo_root=repo_root, rel_paths=rel_paths)
    run_with_retries(
        build_sync_argv(
            host=host,
            remote_repo_root=remote_repo_root,
            rel_paths=rel_paths,
            connect_timeout=connect_timeout,
            verify=verify,
        ),
        input_bytes=payload,
        retries=retries,
        retry_delay_seconds=retry_delay_seconds,
        runner=runner,
        sleeper=sleeper,
    )


def format_sync_plan(
    *,
    repo_root: Path,
    remote_repo_root: Path | PurePosixPath | str,
    host: str,
    rel_paths: Sequence[str],
    verify: bool,
    connect_timeout: int,
) -> str:
    lines = []
    for local_path, remote_path in build_sync_pairs(repo_root=repo_root, remote_repo_root=remote_repo_root, rel_paths=rel_paths):
        lines.append(f"SYNC {local_path} -> {host}:{remote_path}")
    lines.append(
        ("SYNC+VERIFY " if verify else "SYNC ")
        + " ".join(
            build_sync_argv(
                host=host,
                remote_repo_root=remote_repo_root,
                rel_paths=rel_paths,
                connect_timeout=connect_timeout,
                verify=verify,
            )
        )
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    rel_paths = normalize_rel_paths(args.rel_path)
    verify = not args.no_verify

    if args.print_plan:
        print(
            format_sync_plan(
                repo_root=args.repo_root,
                remote_repo_root=args.remote_repo_root,
                host=args.remote_host,
                rel_paths=rel_paths,
                verify=verify,
                connect_timeout=args.connect_timeout,
            )
        )
        return

    sync_remote_code(
        repo_root=args.repo_root,
        remote_repo_root=args.remote_repo_root,
        host=args.remote_host,
        rel_paths=rel_paths,
        verify=verify,
        connect_timeout=args.connect_timeout,
        retries=args.retries,
        retry_delay_seconds=args.retry_delay_seconds,
    )
    print(f"synced {len(rel_paths)} files to {args.remote_host}:{_to_posix_path(args.remote_repo_root)}")


if __name__ == "__main__":
    main()
