#!/usr/bin/env python3

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path, PurePosixPath
import shlex
import subprocess


DEFAULT_HOST = "l20"
DEFAULT_REMOTE_REPO_ROOT = PurePosixPath("/data/Zijian/goal/RecDemo")
DEFAULT_REMOTE_DATASET_ROOT = DEFAULT_REMOTE_REPO_ROOT / "dataset" / "paper_raw_v1"
DEFAULT_SESSION_NAME = "gate0_utilde"
DEFAULT_DATASET_DIRS = {
    "ML1M": "dataset/paper_raw_v1/ML1M",
    "Steam": "dataset/paper_raw_v1/Steam",
    "Beauty": "dataset/paper_raw_v1/Beauty",
    "ATG": "dataset/paper_raw_v1/ATG",
}


def _to_posix_path(pathlike: Path | PurePosixPath | str) -> PurePosixPath:
    return PurePosixPath(str(pathlike).replace("\\", "/"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the Gate 0 u_tilde diagnostics inside remote tmux.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--remote-repo-root", default=str(DEFAULT_REMOTE_REPO_ROOT))
    parser.add_argument("--session-name", default=DEFAULT_SESSION_NAME)
    parser.add_argument("--output-dir", default=None, help="Remote output dir; defaults to docs/reports/data/<today>-gate0")
    parser.add_argument("--print-only", action="store_true", help="Print the ssh command instead of executing it.")
    return parser.parse_args()


def build_remote_gate0_command(remote_repo_root: PurePosixPath, output_dir: PurePosixPath) -> str:
    remote_repo_root = _to_posix_path(remote_repo_root)
    output_dir = _to_posix_path(output_dir)
    script_path = remote_repo_root / "scripts" / "build_gate0_utilde_report.py"
    dataset_args = " ".join(
        f"--dataset {name}={remote_repo_root / rel_path}"
        for name, rel_path in DEFAULT_DATASET_DIRS.items()
    )
    return (
        f"python3 {script_path} "
        f"{dataset_args} "
        f"--output-dir {output_dir}"
    )


def build_tmux_shell_command(session_name: str, remote_command: str) -> str:
    quoted_remote_command = shlex.quote(remote_command)
    return (
        f"(tmux has-session -t {session_name} 2>/dev/null && tmux kill-session -t {session_name}) || true; "
        f"tmux new-session -d -s {session_name} bash -lc {quoted_remote_command}; "
        f"tmux list-sessions | grep {shlex.quote(session_name)} || true"
    )


def build_tmux_ssh_command(host: str, session_name: str, remote_command: str) -> str:
    tmux_shell_command = build_tmux_shell_command(session_name=session_name, remote_command=remote_command)
    return f"ssh {host} {shlex.quote(tmux_shell_command)}"


def build_ssh_argv(host: str, session_name: str, remote_command: str) -> list[str]:
    return ["ssh", host, build_tmux_shell_command(session_name=session_name, remote_command=remote_command)]


def launch_remote_gate0(
    host: str,
    remote_repo_root: PurePosixPath,
    session_name: str,
    output_dir: PurePosixPath,
    print_only: bool = False,
) -> str:
    remote_command = build_remote_gate0_command(remote_repo_root=remote_repo_root, output_dir=output_dir)
    ssh_command = build_tmux_ssh_command(host=host, session_name=session_name, remote_command=remote_command)
    if print_only:
        return ssh_command
    subprocess.run(build_ssh_argv(host=host, session_name=session_name, remote_command=remote_command), check=True)
    return ssh_command


def main() -> None:
    args = parse_args()
    remote_repo_root = PurePosixPath(args.remote_repo_root)
    output_dir = (
        PurePosixPath(args.output_dir)
        if args.output_dir
        else remote_repo_root / "docs" / "reports" / "data" / f"{date.today().isoformat()}-gate0"
    )
    ssh_command = launch_remote_gate0(
        host=args.host,
        remote_repo_root=remote_repo_root,
        session_name=args.session_name,
        output_dir=output_dir,
        print_only=args.print_only,
    )
    print(ssh_command)


if __name__ == "__main__":
    main()
