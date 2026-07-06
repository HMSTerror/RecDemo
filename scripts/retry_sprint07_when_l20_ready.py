#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import io
import shlex
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PYTHON = Path(sys.executable)
DEFAULT_LOG_PATH = REPO_ROOT / "logs" / "sprint07_retry_l20.log"
DEFAULT_MAX_ATTEMPTS = 240
DEFAULT_INTERVAL_SECONDS = 60
DEFAULT_HOST = "l20"
DEFAULT_REMOTE_BASE = PurePosixPath("/data/Zijian/goal/RecDemo_clean_main")
DEFAULT_REMOTE_PYTHON = PurePosixPath("/data/Zijian/goal/PreferGrow/.venv/bin/python")
DEFAULT_REPORT_DIR = DEFAULT_REMOTE_BASE / "docs" / "reports" / "data" / f"{date.today().isoformat()}-sprint07"
DEFAULT_LOCAL_REPORT_DIR = REPO_ROOT / "docs" / "reports" / "data" / f"{date.today().isoformat()}-sprint07"
DEFAULT_CLOSE02_RUN_ROOT = PurePosixPath("/data/Zijian/goal/RecDemoRuns/close02_ml1m_noise_floor")
DEFAULT_CLOSE02_REPORT_DIR = (
    DEFAULT_REMOTE_BASE / "docs" / "reports" / "data" / f"{date.today().isoformat()}-close02-ml1m-noise-floor"
)
DEFAULT_LOCAL_CLOSE02_REPORT_DIR = (
    REPO_ROOT / "docs" / "reports" / "data" / f"{date.today().isoformat()}-close02-ml1m-noise-floor"
)
DEFAULT_CLOSE02_SEEDS = (100, 101, 102)
SPRINT07_REPORT_FILENAMES = ("sprint07_control_table.csv", "sprint07_control_report_zh.md")
CLOSE02_REPORT_FILENAMES = (
    "close02_ml1m_noise_floor_table.csv",
    "close02_ml1m_noise_floor_report.json",
    "close02_ml1m_noise_floor_report_zh.md",
)
TARGET_DATASETS = ("Beauty", "Steam")
TARGET_ARMS = ("full", "u_shuffle", "text_anchor_only", "global_p")


def _q(value: str) -> str:
    return shlex.quote(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Retry remote SPRINT-07 status collection until l20 is reachable and all control-arm rows complete."
    )
    parser.add_argument("--log-path", type=Path, default=DEFAULT_LOG_PATH)
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    parser.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--connect-timeout", type=int, default=8)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--remote-base", default=str(DEFAULT_REMOTE_BASE))
    parser.add_argument("--remote-python", default=str(DEFAULT_REMOTE_PYTHON))
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--local-report-dir", type=Path, default=DEFAULT_LOCAL_REPORT_DIR)
    parser.add_argument("--local-python", type=Path, default=DEFAULT_PYTHON)
    parser.add_argument("--close02-run-root", default=str(DEFAULT_CLOSE02_RUN_ROOT))
    parser.add_argument("--close02-report-dir", default=str(DEFAULT_CLOSE02_REPORT_DIR))
    parser.add_argument("--local-close02-report-dir", type=Path, default=DEFAULT_LOCAL_CLOSE02_REPORT_DIR)
    parser.add_argument("--launch-close02-on-complete", action="store_true")
    parser.add_argument("--close02-seeds", nargs="+", type=int, default=list(DEFAULT_CLOSE02_SEEDS))
    parser.add_argument("--print-only", action="store_true")
    return parser.parse_args()


def build_status_command(
    *,
    host: str,
    remote_base: str,
    remote_python: str,
    report_dir: str,
    connect_timeout: int,
) -> list[str]:
    control_csv = f"{report_dir}/sprint07_control_table.csv"
    remote_command = (
        f"cd {_q(remote_base)} && "
        f"{_q(remote_python)} scripts/build_sprint07_control_report.py >/tmp/sprint07_retry_refresh.log 2>&1 && "
        f"cat {_q(control_csv)}"
    )
    return ["ssh", "-o", f"ConnectTimeout={connect_timeout}", host, remote_command]


def build_close02_status_command(
    *,
    host: str,
    remote_base: str,
    remote_python: str,
    close02_run_root: str,
    close02_report_dir: str,
    close02_seeds: tuple[int, ...],
    connect_timeout: int,
) -> list[str]:
    report_csv = f"{close02_report_dir}/close02_ml1m_noise_floor_table.csv"
    seeds_fragment = " ".join(str(seed) for seed in close02_seeds)
    remote_command = (
        f"cd {_q(remote_base)} && "
        f"{_q(remote_python)} scripts/build_close02_ml1m_noise_floor_report.py "
        f"--run-root {_q(close02_run_root)} "
        f"--official-repo-root {_q(remote_base)} "
        f"--output-dir {_q(close02_report_dir)} "
        f"--seeds {seeds_fragment} "
        f">/tmp/close02_retry_refresh.log 2>&1 && "
        f"cat {_q(report_csv)}"
    )
    return ["ssh", "-o", f"ConnectTimeout={connect_timeout}", host, remote_command]


def append_log(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


def parse_status_csv(csv_text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(csv_text)))


def summarize_incomplete_rows(rows: list[dict[str, str]]) -> str:
    parts: list[str] = []
    for row in rows:
        dataset = row.get("dataset", "")
        arm = row.get("arm", "")
        status = row.get("status", "")
        last_step = row.get("last_logged_step", "") or "NA"
        parts.append(f"{dataset}/{arm}:{status}@{last_step}")
    return ", ".join(parts)


def completion_state(rows: list[dict[str, str]]) -> tuple[bool, list[dict[str, str]]]:
    target_rows = [
        row
        for row in rows
        if row.get("dataset") in TARGET_DATASETS and row.get("arm") in TARGET_ARMS
    ]
    if len(target_rows) != len(TARGET_DATASETS) * len(TARGET_ARMS):
        return False, target_rows
    incomplete = [row for row in target_rows if row.get("status") != "completed"]
    return len(incomplete) == 0, incomplete


def summarize_incomplete_close02_rows(rows: list[dict[str, str]]) -> str:
    parts: list[str] = []
    for row in rows:
        seed = row.get("seed", "")
        status = row.get("status", "")
        last_step = row.get("last_logged_step", "") or "NA"
        parts.append(f"seed{seed}:{status}@{last_step}")
    return ", ".join(parts)


def close02_completion_state(
    rows: list[dict[str, str]],
    *,
    expected_seeds: tuple[int, ...],
) -> tuple[bool, list[dict[str, str]]]:
    expected = {str(seed) for seed in expected_seeds}
    target_rows = [row for row in rows if row.get("seed") in expected]
    if len(target_rows) != len(expected):
        return False, target_rows
    incomplete = [row for row in target_rows if row.get("status") != "completed"]
    return len(incomplete) == 0, incomplete


def run_attempt_loop(
    *,
    status_command: list[str],
    log_path: Path,
    max_attempts: int,
    interval_seconds: int,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    sleeper: Callable[[float], None] = time.sleep,
) -> bool:
    for attempt in range(1, max_attempts + 1):
        append_log(log_path, f"attempt {attempt}/{max_attempts}: query start")
        result = runner(status_command, cwd=REPO_ROOT, capture_output=True, text=True)
        if result.returncode == 0:
            rows = parse_status_csv(result.stdout)
            complete, incomplete_rows = completion_state(rows)
            if complete:
                append_log(log_path, f"attempt {attempt}/{max_attempts}: sprint07 complete")
                return True
            append_log(
                log_path,
                f"attempt {attempt}/{max_attempts}: sprint07 incomplete -> {summarize_incomplete_rows(incomplete_rows)}",
            )
        else:
            stderr = (result.stderr or "").strip().replace("\n", " | ")
            append_log(log_path, f"attempt {attempt}/{max_attempts}: query failed rc={result.returncode} stderr={stderr}")

        if attempt < max_attempts:
            sleeper(interval_seconds)

    append_log(log_path, f"exhausted {max_attempts} attempts without completing sprint07")
    return False


def run_close02_attempt_loop(
    *,
    status_command: list[str],
    log_path: Path,
    expected_seeds: tuple[int, ...],
    max_attempts: int,
    interval_seconds: int,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    sleeper: Callable[[float], None] = time.sleep,
) -> bool:
    for attempt in range(1, max_attempts + 1):
        append_log(log_path, f"attempt {attempt}/{max_attempts}: close02 query start")
        result = runner(status_command, cwd=REPO_ROOT, capture_output=True, text=True)
        if result.returncode == 0:
            rows = parse_status_csv(result.stdout)
            complete, incomplete_rows = close02_completion_state(rows, expected_seeds=expected_seeds)
            if complete:
                append_log(log_path, f"attempt {attempt}/{max_attempts}: close02 complete")
                return True
            append_log(
                log_path,
                f"attempt {attempt}/{max_attempts}: close02 incomplete -> {summarize_incomplete_close02_rows(incomplete_rows)}",
            )
        else:
            stderr = (result.stderr or "").strip().replace("\n", " | ")
            append_log(log_path, f"attempt {attempt}/{max_attempts}: close02 query failed rc={result.returncode} stderr={stderr}")

        if attempt < max_attempts:
            sleeper(interval_seconds)

    append_log(log_path, f"exhausted {max_attempts} attempts without completing close02")
    return False


def build_close02_launch_command(*, local_python: Path, close02_seeds: tuple[int, ...]) -> list[str]:
    command = [
        str(local_python),
        str(REPO_ROOT / "scripts" / "launch_close02_ml1m_noise_floor_tmux.py"),
    ]
    if close02_seeds:
        command.append("--seeds")
        command.extend(str(seed) for seed in close02_seeds)
    return command


def build_report_sync_commands(
    *,
    host: str,
    report_dir: str,
    local_report_dir: Path,
    connect_timeout: int,
    filenames: tuple[str, ...] = SPRINT07_REPORT_FILENAMES,
) -> list[list[str]]:
    commands: list[list[str]] = []
    for filename in filenames:
        commands.append(
            [
                "scp",
                "-o",
                f"ConnectTimeout={connect_timeout}",
                f"{host}:{report_dir}/{filename}",
                str(local_report_dir / filename),
            ]
        )
    return commands


def build_close02_report_sync_commands(
    *,
    host: str,
    report_dir: str,
    local_report_dir: Path,
    connect_timeout: int,
) -> list[list[str]]:
    return build_report_sync_commands(
        host=host,
        report_dir=report_dir,
        local_report_dir=local_report_dir,
        connect_timeout=connect_timeout,
        filenames=CLOSE02_REPORT_FILENAMES,
    )


def sync_artifacts(
    *,
    commands: list[list[str]],
    log_path: Path,
    local_report_dir: Path,
    label: str,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> bool:
    local_report_dir.mkdir(parents=True, exist_ok=True)
    append_log(log_path, f"{label} -> syncing artifacts to {local_report_dir}")
    for command in commands:
        result = runner(command, cwd=REPO_ROOT, capture_output=True, text=True)
        if result.returncode != 0:
            stderr = (result.stderr or "").strip().replace("\n", " | ")
            append_log(log_path, f"artifact sync failed rc={result.returncode} stderr={stderr}")
            return False
    append_log(log_path, "artifact sync succeeded")
    return True


def sync_sprint07_artifacts(
    *,
    commands: list[list[str]],
    log_path: Path,
    local_report_dir: Path,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> bool:
    return sync_artifacts(
        commands=commands,
        log_path=log_path,
        local_report_dir=local_report_dir,
        label="sprint07 complete",
        runner=runner,
    )


def sync_close02_artifacts(
    *,
    commands: list[list[str]],
    log_path: Path,
    local_report_dir: Path,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> bool:
    return sync_artifacts(
        commands=commands,
        log_path=log_path,
        local_report_dir=local_report_dir,
        label="close02 complete",
        runner=runner,
    )


def launch_close02_followup(
    *,
    command: list[str],
    log_path: Path,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> bool:
    append_log(log_path, "sprint07 complete -> launching CLOSE-02")
    result = runner(command, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode == 0:
        stdout = (result.stdout or "").strip().replace("\n", " | ")
        append_log(log_path, f"CLOSE-02 launch succeeded stdout={stdout}")
        return True
    stderr = (result.stderr or "").strip().replace("\n", " | ")
    append_log(log_path, f"CLOSE-02 launch failed rc={result.returncode} stderr={stderr}")
    return False


def main() -> None:
    args = parse_args()
    status_command = build_status_command(
        host=args.host,
        remote_base=args.remote_base,
        remote_python=args.remote_python,
        report_dir=args.report_dir,
        connect_timeout=args.connect_timeout,
    )
    if args.print_only:
        print("STATUS " + " ".join(status_command))
        print(f"LOG {args.log_path}")
        for command in build_report_sync_commands(
            host=args.host,
            report_dir=args.report_dir,
            local_report_dir=args.local_report_dir,
            connect_timeout=args.connect_timeout,
        ):
            print("SYNC " + " ".join(command))
        if args.launch_close02_on_complete:
            close02_command = build_close02_launch_command(
                local_python=args.local_python,
                close02_seeds=tuple(args.close02_seeds),
            )
            print("CLOSE02 " + " ".join(close02_command))
            close02_status_command = build_close02_status_command(
                host=args.host,
                remote_base=args.remote_base,
                remote_python=args.remote_python,
                close02_run_root=args.close02_run_root,
                close02_report_dir=args.close02_report_dir,
                close02_seeds=tuple(args.close02_seeds),
                connect_timeout=args.connect_timeout,
            )
            print("CLOSE02_STATUS " + " ".join(close02_status_command))
            for command in build_close02_report_sync_commands(
                host=args.host,
                report_dir=args.close02_report_dir,
                local_report_dir=args.local_close02_report_dir,
                connect_timeout=args.connect_timeout,
            ):
                print("CLOSE02_SYNC " + " ".join(command))
        return

    ok = run_attempt_loop(
        status_command=status_command,
        log_path=args.log_path,
        max_attempts=args.max_attempts,
        interval_seconds=args.interval_seconds,
    )
    if not ok:
        raise SystemExit(1)
    sync_ok = sync_sprint07_artifacts(
        commands=build_report_sync_commands(
            host=args.host,
            report_dir=args.report_dir,
            local_report_dir=args.local_report_dir,
            connect_timeout=args.connect_timeout,
        ),
        log_path=args.log_path,
        local_report_dir=args.local_report_dir,
    )
    if args.launch_close02_on_complete:
        close02_command = build_close02_launch_command(
            local_python=args.local_python,
            close02_seeds=tuple(args.close02_seeds),
        )
        launched = launch_close02_followup(command=close02_command, log_path=args.log_path)
        if not launched:
            raise SystemExit(1)
        close02_ok = run_close02_attempt_loop(
            status_command=build_close02_status_command(
                host=args.host,
                remote_base=args.remote_base,
                remote_python=args.remote_python,
                close02_run_root=args.close02_run_root,
                close02_report_dir=args.close02_report_dir,
                close02_seeds=tuple(args.close02_seeds),
                connect_timeout=args.connect_timeout,
            ),
            log_path=args.log_path,
            expected_seeds=tuple(args.close02_seeds),
            max_attempts=args.max_attempts,
            interval_seconds=args.interval_seconds,
        )
        if not close02_ok:
            raise SystemExit(1)
        close02_sync_ok = sync_close02_artifacts(
            commands=build_close02_report_sync_commands(
                host=args.host,
                report_dir=args.close02_report_dir,
                local_report_dir=args.local_close02_report_dir,
                connect_timeout=args.connect_timeout,
            ),
            log_path=args.log_path,
            local_report_dir=args.local_close02_report_dir,
        )
        if not sync_ok or not close02_sync_ok:
            raise SystemExit(1)
    elif not sync_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
