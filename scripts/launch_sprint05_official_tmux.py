#!/usr/bin/env python3

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path, PurePosixPath
import shlex
import subprocess


DEFAULT_HOST = "l20"
DEFAULT_REMOTE_BASE = PurePosixPath("/data/Zijian/goal/RecDemo_clean_main")
DEFAULT_OLD_ROOT = PurePosixPath("/data/Zijian/goal/RecDemo")
DEFAULT_RUN_ROOT = PurePosixPath("/data/Zijian/goal/RecDemoRuns/main_table_text_side")
DEFAULT_PYTHON_BIN = PurePosixPath("/data/Zijian/goal/PreferGrow/.venv/bin/python")
DEFAULT_LOG_PATH = DEFAULT_RUN_ROOT / "sprint05_watchdog.log"
DEFAULT_REPORT_DIR = DEFAULT_REMOTE_BASE / "docs" / "reports" / "data" / f"{date.today().isoformat()}-sprint05"
DEFAULT_SNAPSHOT_ROOT = DEFAULT_REMOTE_BASE / "docs" / "reports" / "data" / f"{date.today().isoformat()}-sprint05-watchdog"
DEFAULT_ORCHESTRATOR_SESSION = "sprint05_official_orchestrator"
DEFAULT_WATCHDOG_SESSION = "sprint05_watchdog"


def _to_posix_path(pathlike: Path | PurePosixPath | str) -> PurePosixPath:
    return PurePosixPath(str(pathlike).replace("\\", "/"))


def _q(pathlike: Path | PurePosixPath | str) -> str:
    return shlex.quote(str(_to_posix_path(pathlike)))


def build_remote_command(
    *,
    remote_base: Path | PurePosixPath | str,
    old_root: Path | PurePosixPath | str,
    run_root: Path | PurePosixPath | str,
    python_bin: Path | PurePosixPath | str,
    report_dir: Path | PurePosixPath | str,
    snapshot_root: Path | PurePosixPath | str,
    orchestrator_session: str,
    watchdog_session: str,
    log_path: Path | PurePosixPath | str,
) -> str:
    remote_base = _to_posix_path(remote_base)
    old_root = _to_posix_path(old_root)
    run_root = _to_posix_path(run_root)
    python_bin = _to_posix_path(python_bin)
    report_dir = _to_posix_path(report_dir)
    snapshot_root = _to_posix_path(snapshot_root)
    log_path = _to_posix_path(log_path)
    orchestrator_script = remote_base / "scripts" / "sprint05_official_orchestrator.sh"
    watchdog_script = remote_base / "scripts" / "sprint05_watchdog.sh"
    return (
        f"cd {_q(remote_base)} && "
        f"chmod +x {_q(orchestrator_script)} {_q(watchdog_script)} && "
        f"(tmux has-session -t {shlex.quote(orchestrator_session)} 2>/dev/null && tmux kill-session -t {shlex.quote(orchestrator_session)}) || true && "
        f"(tmux has-session -t {shlex.quote(watchdog_session)} 2>/dev/null && tmux kill-session -t {shlex.quote(watchdog_session)}) || true && "
        f"tmux new-session -d -s {shlex.quote(orchestrator_session)} "
        f"{shlex.quote(f'BASE={remote_base} OLD_ROOT={old_root} RUN_ROOT={run_root} PYTHON_BIN={python_bin} REPORT_DIR={report_dir} bash {orchestrator_script}')}"
        f" && tmux new-session -d -s {shlex.quote(watchdog_session)} "
        f"{shlex.quote(f'BASE={remote_base} OLD_ROOT={old_root} RUN_ROOT={run_root} PYTHON_BIN={python_bin} LOG_PATH={log_path} SNAPSHOT_ROOT={snapshot_root} ORCHESTRATOR_SESSION={orchestrator_session} bash {watchdog_script}')}"
        f" && tmux list-sessions | grep sprint05_ || true"
    )


def build_tmux_ssh_command(host: str, remote_command: str) -> str:
    return f"ssh {host} {shlex.quote(remote_command)}"


def build_ssh_argv(host: str, remote_command: str) -> list[str]:
    return ["ssh", host, remote_command]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the sprint05 official orchestrator and watchdog inside remote tmux.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--remote-base", default=str(DEFAULT_REMOTE_BASE))
    parser.add_argument("--old-root", default=str(DEFAULT_OLD_ROOT))
    parser.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT))
    parser.add_argument("--python-bin", default=str(DEFAULT_PYTHON_BIN))
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--snapshot-root", default=str(DEFAULT_SNAPSHOT_ROOT))
    parser.add_argument("--log-path", default=str(DEFAULT_LOG_PATH))
    parser.add_argument("--orchestrator-session", default=DEFAULT_ORCHESTRATOR_SESSION)
    parser.add_argument("--watchdog-session", default=DEFAULT_WATCHDOG_SESSION)
    parser.add_argument("--print-only", action="store_true")
    return parser.parse_args()


def launch_remote_sprint05(*, print_only: bool = False, **kwargs: str) -> str:
    host = kwargs["host"]
    remote_kwargs = {key: value for key, value in kwargs.items() if key != "host"}
    remote_command = build_remote_command(**remote_kwargs)
    ssh_command = build_tmux_ssh_command(host=host, remote_command=remote_command)
    if print_only:
        return ssh_command
    subprocess.run(build_ssh_argv(host=host, remote_command=remote_command), check=True)
    return ssh_command


def main() -> None:
    args = parse_args()
    ssh_command = launch_remote_sprint05(
        host=args.host,
        remote_base=args.remote_base,
        old_root=args.old_root,
        run_root=args.run_root,
        python_bin=args.python_bin,
        report_dir=args.report_dir,
        snapshot_root=args.snapshot_root,
        orchestrator_session=args.orchestrator_session,
        watchdog_session=args.watchdog_session,
        log_path=args.log_path,
        print_only=args.print_only,
    )
    print(ssh_command)


if __name__ == "__main__":
    main()
