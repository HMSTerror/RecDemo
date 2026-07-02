#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PYTHON = Path(sys.executable)
DEFAULT_LOG_PATH = REPO_ROOT / "logs" / "gate0_retry_l20.log"
DEFAULT_MAX_ATTEMPTS = 120
DEFAULT_INTERVAL_SECONDS = 30


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Retry remote l20 Gate0 preparation until SSH is reachable, then sync code and launch Gate0 tmux."
    )
    parser.add_argument("--python-bin", type=Path, default=DEFAULT_PYTHON)
    parser.add_argument("--log-path", type=Path, default=DEFAULT_LOG_PATH)
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    parser.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--sync-retries", type=int, default=3)
    parser.add_argument("--sync-retry-delay-seconds", type=int, default=3)
    parser.add_argument("--connect-timeout", type=int, default=8)
    parser.add_argument("--print-only", action="store_true")
    return parser.parse_args()


def build_sync_command(
    python_bin: Path,
    *,
    sync_retries: int,
    sync_retry_delay_seconds: int,
    connect_timeout: int,
) -> list[str]:
    return [
        str(python_bin),
        str(REPO_ROOT / "scripts" / "sync_remote_recdemo_code.py"),
        "--retries",
        str(sync_retries),
        "--retry-delay-seconds",
        str(sync_retry_delay_seconds),
        "--connect-timeout",
        str(connect_timeout),
    ]


def build_launch_command(python_bin: Path) -> list[str]:
    return [
        str(python_bin),
        str(REPO_ROOT / "scripts" / "launch_gate0_tmux.py"),
    ]


def append_log(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


def run_attempt_loop(
    *,
    python_bin: Path,
    log_path: Path,
    max_attempts: int,
    interval_seconds: int,
    sync_retries: int,
    sync_retry_delay_seconds: int,
    connect_timeout: int,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    sleeper: Callable[[float], None] = time.sleep,
) -> bool:
    sync_command = build_sync_command(
        python_bin,
        sync_retries=sync_retries,
        sync_retry_delay_seconds=sync_retry_delay_seconds,
        connect_timeout=connect_timeout,
    )
    launch_command = build_launch_command(python_bin)

    for attempt in range(1, max_attempts + 1):
        append_log(log_path, f"attempt {attempt}/{max_attempts}: sync start")
        sync_result = runner(sync_command, cwd=REPO_ROOT)
        if sync_result.returncode == 0:
            append_log(log_path, f"attempt {attempt}/{max_attempts}: sync ok; launch Gate0")
            launch_result = runner(launch_command, cwd=REPO_ROOT)
            if launch_result.returncode == 0:
                append_log(log_path, f"attempt {attempt}/{max_attempts}: Gate0 launch ok")
                return True
            append_log(
                log_path,
                f"attempt {attempt}/{max_attempts}: Gate0 launch failed with returncode={launch_result.returncode}",
            )
        else:
            append_log(log_path, f"attempt {attempt}/{max_attempts}: sync failed with returncode={sync_result.returncode}")

        if attempt < max_attempts:
            sleeper(interval_seconds)

    append_log(log_path, f"exhausted {max_attempts} attempts without successful Gate0 launch")
    return False


def main() -> None:
    args = parse_args()
    sync_command = build_sync_command(
        args.python_bin,
        sync_retries=args.sync_retries,
        sync_retry_delay_seconds=args.sync_retry_delay_seconds,
        connect_timeout=args.connect_timeout,
    )
    launch_command = build_launch_command(args.python_bin)

    if args.print_only:
        print("SYNC " + " ".join(sync_command))
        print("LAUNCH " + " ".join(launch_command))
        print(f"LOG {args.log_path}")
        return

    ok = run_attempt_loop(
        python_bin=args.python_bin,
        log_path=args.log_path,
        max_attempts=args.max_attempts,
        interval_seconds=args.interval_seconds,
        sync_retries=args.sync_retries,
        sync_retry_delay_seconds=args.sync_retry_delay_seconds,
        connect_timeout=args.connect_timeout,
    )
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
