#!/usr/bin/env python3

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path, PurePosixPath
import shlex
import subprocess


DEFAULT_HOST = "l20"
DEFAULT_REMOTE_BASE = PurePosixPath("/data/Zijian/goal/RecDemo_clean_closeout_chain")
DEFAULT_DATASET_ROOT = PurePosixPath("/data/Zijian/goal/RecDemo/dataset/paper_raw_v1")
DEFAULT_RUN_ROOT = PurePosixPath("/data/Zijian/goal/RecDemoRuns/close04_diffurec")
DEFAULT_PYTHON_BIN = PurePosixPath("/data/Zijian/goal/PreferGrow/.venv/bin/python")
DEFAULT_UPSTREAM_ROOT = PurePosixPath("/data/Zijian/goal/RecDemoExternal/DiffuRec")
DEFAULT_UPSTREAM_REPO = "https://github.com/WHUIR/DiffuRec.git"
DEFAULT_SESSION = "close04_diffurec"
DEFAULT_DATASETS = ("Steam", "ML1M", "Beauty", "ATG")
DEFAULT_OUTPUT_DIR = DEFAULT_REMOTE_BASE / "docs" / "reports" / "data" / f"{date.today().isoformat()}-close04-diffurec"


def _to_posix_path(pathlike: Path | PurePosixPath | str) -> PurePosixPath:
    return PurePosixPath(str(pathlike).replace("\\", "/"))


def _q(pathlike: Path | PurePosixPath | str) -> str:
    return shlex.quote(str(_to_posix_path(pathlike)))


def _dataset_dir(dataset_root: Path | PurePosixPath | str, dataset: str) -> PurePosixPath:
    return _to_posix_path(dataset_root) / dataset


def _run_dir(run_root: Path | PurePosixPath | str, dataset: str, random_seed: int) -> PurePosixPath:
    return _to_posix_path(run_root) / f"{dataset.lower()}_diffurec_seed{random_seed}"


def _log_path(run_root: Path | PurePosixPath | str, dataset: str, random_seed: int) -> PurePosixPath:
    run_dir = _run_dir(run_root, dataset, random_seed)
    return run_dir / "logs" / f"{dataset.lower()}_diffurec_seed{random_seed}.log"


def _summary_path(run_root: Path | PurePosixPath | str, dataset: str, random_seed: int) -> PurePosixPath:
    run_dir = _run_dir(run_root, dataset, random_seed)
    return run_dir / "checkpoints-meta" / dataset / "best_summary_diffurec.json"


def _manifest_path(run_root: Path | PurePosixPath | str, dataset: str, random_seed: int) -> PurePosixPath:
    run_dir = _run_dir(run_root, dataset, random_seed)
    return run_dir / "checkpoints-meta" / dataset / "diffurec_run_manifest.json"


def build_dataset_inner_command(
    *,
    remote_base: Path | PurePosixPath | str,
    dataset_root: Path | PurePosixPath | str,
    run_root: Path | PurePosixPath | str,
    python_bin: Path | PurePosixPath | str,
    upstream_root: Path | PurePosixPath | str,
    upstream_repo: str,
    dataset: str,
    gpu_id: int,
    random_seed: int = 100,
    device: str = "cuda",
    batch_size: int = 256,
    epochs: int = 200,
    eval_interval: int = 10,
    patience: int = 5,
    skip_existing: bool = True,
    force: bool = False,
) -> str:
    remote_base = _to_posix_path(remote_base)
    dataset_root = _to_posix_path(dataset_root)
    run_root = _to_posix_path(run_root)
    python_bin = _to_posix_path(python_bin)
    upstream_root = _to_posix_path(upstream_root)
    dataset_dir = _dataset_dir(dataset_root, dataset)
    run_dir = _run_dir(run_root, dataset, random_seed)
    log_path = _log_path(run_root, dataset, random_seed)
    summary_path = _summary_path(run_root, dataset, random_seed)
    manifest_path = _manifest_path(run_root, dataset, random_seed)

    lines = [
        "set -euo pipefail",
        f"mkdir -p {_q(upstream_root.parent)}",
        f"if [[ ! -d {_q(upstream_root / '.git')} ]]; then git clone {shlex.quote(upstream_repo)} {_q(upstream_root)}; fi",
        f"UPSTREAM_HEAD=$(git -C {_q(upstream_root)} rev-parse HEAD 2>/dev/null || true)",
        f"mkdir -p {_q(run_dir / 'logs')}",
    ]
    if force:
        lines.append(f"rm -rf {_q(run_dir)}")
        lines.append(f"mkdir -p {_q(run_dir / 'logs')}")
    if skip_existing and not force:
        lines.extend(
            [
                f"if [[ -f {_q(summary_path)} && -f {_q(manifest_path)} ]]; then",
                f"  echo SKIP dataset={shlex.quote(dataset)} reason=existing_artifacts summary={summary_path}",
                "  exit 0",
                "fi",
            ]
        )

    lines.extend(
        [
            f"echo START dataset={shlex.quote(dataset)} gpu={shlex.quote(str(gpu_id))} upstream_head=$UPSTREAM_HEAD",
            f"cd {_q(remote_base)}",
            (
                f"CUDA_VISIBLE_DEVICES={shlex.quote(str(gpu_id))} "
                f"{_q(python_bin)} -u {_q(remote_base / 'scripts' / 'run_close04_diffurec.py')} "
                f"--dataset-name {shlex.quote(dataset)} "
                f"--dataset-dir {_q(dataset_dir)} "
                f"--upstream-root {_q(upstream_root)} "
                f"--run-root {_q(run_root)} "
                f"--random-seed {shlex.quote(str(random_seed))} "
                f"--device {shlex.quote(device)} "
                f"--batch-size {shlex.quote(str(batch_size))} "
                f"--epochs {shlex.quote(str(epochs))} "
                f"--eval-interval {shlex.quote(str(eval_interval))} "
                f"--patience {shlex.quote(str(patience))} "
                f"--cuda-visible-devices {shlex.quote(str(gpu_id))} "
                f"2>&1 | tee {_q(log_path)}"
            ),
            f"if [[ ! -f {_q(summary_path)} ]]; then echo SUMMARY_MISSING dataset={shlex.quote(dataset)} path={summary_path} >&2; exit 1; fi",
            f"if [[ ! -f {_q(manifest_path)} ]]; then echo MANIFEST_MISSING dataset={shlex.quote(dataset)} path={manifest_path} >&2; exit 1; fi",
            f"echo FINISH dataset={shlex.quote(dataset)} summary={summary_path}",
        ]
    )
    return "\n".join(lines)


def build_session_inner_command(
    *,
    remote_base: Path | PurePosixPath | str,
    dataset_root: Path | PurePosixPath | str,
    run_root: Path | PurePosixPath | str,
    python_bin: Path | PurePosixPath | str,
    upstream_root: Path | PurePosixPath | str,
    upstream_repo: str,
    output_dir: Path | PurePosixPath | str,
    datasets: tuple[str, ...] = DEFAULT_DATASETS,
    gpu_id: int = 0,
    random_seed: int = 100,
    device: str = "cuda",
    batch_size: int = 256,
    epochs: int = 200,
    eval_interval: int = 10,
    patience: int = 5,
    skip_existing: bool = True,
    force: bool = False,
) -> str:
    remote_base = _to_posix_path(remote_base)
    output_dir = _to_posix_path(output_dir)
    lines = [
        f"cd {_q(remote_base)}",
        "set -euo pipefail",
    ]
    for dataset in datasets:
        lines.append(
            build_dataset_inner_command(
                remote_base=remote_base,
                dataset_root=dataset_root,
                run_root=run_root,
                python_bin=python_bin,
                upstream_root=upstream_root,
                upstream_repo=upstream_repo,
                dataset=dataset,
                gpu_id=gpu_id,
                random_seed=random_seed,
                device=device,
                batch_size=batch_size,
                epochs=epochs,
                eval_interval=eval_interval,
                patience=patience,
                skip_existing=skip_existing,
                force=force,
            )
        )
    dataset_args = " ".join(shlex.quote(dataset) for dataset in datasets)
    lines.append(
        f"{_q(python_bin)} {_q(remote_base / 'scripts' / 'build_close04_external_baseline_table.py')} "
        f"--baseline-run-root {_q(run_root)} "
        f"--output-dir {_q(output_dir)} "
        f"--datasets {dataset_args}"
    )
    return "\n".join(lines)


def build_remote_command(
    *,
    remote_base: Path | PurePosixPath | str,
    dataset_root: Path | PurePosixPath | str,
    run_root: Path | PurePosixPath | str,
    python_bin: Path | PurePosixPath | str,
    upstream_root: Path | PurePosixPath | str,
    upstream_repo: str,
    output_dir: Path | PurePosixPath | str,
    session_name: str,
    datasets: tuple[str, ...] = DEFAULT_DATASETS,
    gpu_id: int = 0,
    random_seed: int = 100,
    device: str = "cuda",
    batch_size: int = 256,
    epochs: int = 200,
    eval_interval: int = 10,
    patience: int = 5,
    skip_existing: bool = True,
    force: bool = False,
) -> str:
    inner_command = build_session_inner_command(
        remote_base=remote_base,
        dataset_root=dataset_root,
        run_root=run_root,
        python_bin=python_bin,
        upstream_root=upstream_root,
        upstream_repo=upstream_repo,
        output_dir=output_dir,
        datasets=datasets,
        gpu_id=gpu_id,
        random_seed=random_seed,
        device=device,
        batch_size=batch_size,
        epochs=epochs,
        eval_interval=eval_interval,
        patience=patience,
        skip_existing=skip_existing,
        force=force,
    )
    remote_base = _to_posix_path(remote_base)
    clauses = [
        f"cd {_q(remote_base)}",
        f"(tmux has-session -t {shlex.quote(session_name)} 2>/dev/null && tmux kill-session -t {shlex.quote(session_name)}) || true",
        f"tmux new-session -d -s {shlex.quote(session_name)} bash -lc {shlex.quote(inner_command)}",
        f"tmux list-sessions | grep {shlex.quote(session_name)} || true",
    ]
    return " && ".join(clauses)


def build_tmux_ssh_command(host: str, remote_command: str) -> str:
    return f"ssh {host} {shlex.quote(remote_command)}"


def build_ssh_argv(host: str, remote_command: str) -> list[str]:
    return ["ssh", host, remote_command]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch CLOSE-04 DiffuRec runs inside remote tmux.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--remote-base", default=str(DEFAULT_REMOTE_BASE))
    parser.add_argument("--dataset-root", default=str(DEFAULT_DATASET_ROOT))
    parser.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT))
    parser.add_argument("--python-bin", default=str(DEFAULT_PYTHON_BIN))
    parser.add_argument("--upstream-root", default=str(DEFAULT_UPSTREAM_ROOT))
    parser.add_argument("--upstream-repo", default=DEFAULT_UPSTREAM_REPO)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--session-name", default=DEFAULT_SESSION)
    parser.add_argument("--datasets", nargs="+", default=list(DEFAULT_DATASETS))
    parser.add_argument("--gpu-id", type=int, default=0)
    parser.add_argument("--random-seed", type=int, default=100)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--eval-interval", type=int, default=10)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-skip-existing", action="store_true")
    parser.add_argument("--print-only", action="store_true")
    return parser.parse_args()


def launch_remote_close04(*, print_only: bool = False, **kwargs: str | int) -> str:
    host = str(kwargs["host"])
    remote_kwargs = {key: value for key, value in kwargs.items() if key != "host"}
    remote_command = build_remote_command(**remote_kwargs)
    ssh_command = build_tmux_ssh_command(host=host, remote_command=remote_command)
    if print_only:
        return ssh_command
    subprocess.run(build_ssh_argv(host=host, remote_command=remote_command), check=True)
    return ssh_command


def main() -> None:
    args = parse_args()
    ssh_command = launch_remote_close04(
        host=args.host,
        remote_base=args.remote_base,
        dataset_root=args.dataset_root,
        run_root=args.run_root,
        python_bin=args.python_bin,
        upstream_root=args.upstream_root,
        upstream_repo=args.upstream_repo,
        output_dir=args.output_dir,
        session_name=args.session_name,
        datasets=tuple(args.datasets),
        gpu_id=args.gpu_id,
        random_seed=args.random_seed,
        device=args.device,
        batch_size=args.batch_size,
        epochs=args.epochs,
        eval_interval=args.eval_interval,
        patience=args.patience,
        skip_existing=not args.no_skip_existing,
        force=args.force,
        print_only=args.print_only,
    )
    print(ssh_command)


if __name__ == "__main__":
    main()
