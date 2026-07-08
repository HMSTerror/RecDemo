#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import shlex
import subprocess


DEFAULT_HOST = "l20"
DEFAULT_REMOTE_BASE = PurePosixPath("/data/Zijian/goal/RecDemo_clean_closeout_chain")
DEFAULT_RUN_ROOT = PurePosixPath("/data/Zijian/goal/RecDemoRuns/close02_ml1m_noise_floor")
DEFAULT_PYTHON_BIN = PurePosixPath("/data/Zijian/goal/PreferGrow/.venv/bin/python")
DEFAULT_DATASET_DIR = PurePosixPath("/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ML1M")
DEFAULT_SESSION = "close02_ml1m_noise_floor"
DEFAULT_SEEDS = (100, 101, 102)


def _to_posix_path(pathlike: Path | PurePosixPath | str) -> PurePosixPath:
    return PurePosixPath(str(pathlike).replace("\\", "/"))


def _q(pathlike: Path | PurePosixPath | str) -> str:
    return shlex.quote(str(_to_posix_path(pathlike)))


def _seed_run_dir(run_root: Path | PurePosixPath | str, seed: int) -> PurePosixPath:
    return _to_posix_path(run_root) / f"ml1m_core_seed{seed}"


def _seed_log_path(run_root: Path | PurePosixPath | str, seed: int) -> PurePosixPath:
    run_dir = _seed_run_dir(run_root, seed)
    return run_dir / "logs" / f"ml1m_core_seed{seed}.log"


def _seed_summary_path(run_root: Path | PurePosixPath | str, seed: int) -> PurePosixPath:
    run_dir = _seed_run_dir(run_root, seed)
    return run_dir / "checkpoints-meta" / "ML1M" / "best_summary_hybrid.json"


def _seed_manifest_path(run_root: Path | PurePosixPath | str, seed: int) -> PurePosixPath:
    run_dir = _seed_run_dir(run_root, seed)
    return run_dir / "checkpoints-meta" / "ML1M" / "frozen_run_manifest.json"


def build_seed_inner_command(
    *,
    remote_base: Path | PurePosixPath | str,
    run_root: Path | PurePosixPath | str,
    python_bin: Path | PurePosixPath | str,
    dataset_dir: Path | PurePosixPath | str,
    seed: int,
    gpu_id: int,
    force: bool = False,
    skip_existing: bool = True,
) -> str:
    remote_base = _to_posix_path(remote_base)
    run_root = _to_posix_path(run_root)
    python_bin = _to_posix_path(python_bin)
    dataset_dir = _to_posix_path(dataset_dir)
    run_dir = _seed_run_dir(run_root, seed)
    log_path = _seed_log_path(run_root, seed)
    summary_path = _seed_summary_path(run_root, seed)
    manifest_path = _seed_manifest_path(run_root, seed)

    prefix_lines = [
        f"mkdir -p {_q(run_dir / 'logs')}",
    ]
    if force:
        prefix_lines.insert(0, f"rm -rf {_q(run_dir)}")
        prefix_lines.append(f"mkdir -p {_q(run_dir / 'logs')}")
    if skip_existing and not force:
        prefix_lines.extend(
            [
                f"if [[ -f {_q(summary_path)} ]]; then",
                f"  echo SKIP seed={seed} reason=existing_summary path={summary_path}",
                "  exit 0",
                "fi",
            ]
        )

    manifest_block = f"""GIT_HEAD=$(git -C {_q(remote_base)} rev-parse HEAD 2>/dev/null || true)
REPO_ROOT_PATH={_q(remote_base)} \\
RUN_DIR={_q(run_dir)} \\
DATASET_DIR={_q(dataset_dir)} \\
MANIFEST_PATH={_q(manifest_path)} \\
RANDOM_SEED={shlex.quote(str(seed))} \\
GIT_HEAD="$GIT_HEAD" \\
{_q(python_bin)} - <<'PY'
import hashlib
import json
import os
from pathlib import Path

dataset_dir = Path(os.environ["DATASET_DIR"])
manifest_path = Path(os.environ["MANIFEST_PATH"])
run_dir = Path(os.environ["RUN_DIR"])
split_path = dataset_dir / "train_data.df"
split_hash = hashlib.sha256(split_path.read_bytes()).hexdigest()
manifest = {{
    "provenance": {{
        "repo_root": str(Path(os.environ["REPO_ROOT_PATH"]).resolve()),
        "git_head": os.environ.get("GIT_HEAD", ""),
    }},
    "dataset": "ML1M",
    "run_dir": str(run_dir),
    "random_seed": int(os.environ["RANDOM_SEED"]),
    "dataset_dir": str(dataset_dir),
    "split_hash": split_hash,
        "frozen_config": {{
            "graph_type": "hybrid",
            "text_side_enabled": False,
            "early_stop_metric": "ndcg10",
            "early_stop_strength": "p5",
            "write_snapshot_checkpoint": True,
            "write_best_checkpoint": True,
        }},
}}
manifest_path.parent.mkdir(parents=True, exist_ok=True)
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
print(f"MANIFEST {{manifest_path}}")
PY"""

    run_block = f"""(
  mkdir -p {_q(run_dir)}
  cd {_q(run_dir)}
  {_q(python_bin)} -u {_q(remote_base / 'single_train.py')} \\
    work_dir={_q(run_dir)} \\
    cuda={shlex.quote(str(gpu_id))} \\
    random_seed={shlex.quote(str(seed))} \\
    training.data=ML1M \\
    data.ML1M.path={_q(dataset_dir)} \\
    graph.type=hybrid \\
    graph.gamma=0.9999 \\
    graph.is_disliked_item=True \\
    model.hidden_size=256 \\
    model.cond_dim=256 \\
    training.nonpreference_user_ratio=0.1 \\
    optim.lr=0.0001 \\
    model.score_flag=True \\
    loss_type=score_entropy \\
    model.score_method=oricos \\
    training.batch_size=256 \\
    eval.batch_size=256 \\
    training.n_iters=2000000 \\
    training.eval_freq=1000 \\
    training.snapshot_freq=1000 \\
    training.snapshot_freq_for_preemption=1000 \\
    training.snapshot_sampling=True \\
    training.early_stop_patience=5 \\
    training.early_stop_min_step=5000 \\
    training.early_stop_metric=ndcg10 \\
    training.early_stop_strength=p5 \\
    training.early_stop_min_delta=0.0 \\
    +training.write_snapshot_checkpoint=True \\
    +training.write_best_checkpoint=True \\
    text_side.enabled=False
) 2>&1 | tee {_q(log_path)}"""

    suffix_lines = [
        f"if [[ ! -f {_q(summary_path)} ]]; then",
        f"  echo SUMMARY_MISSING seed={seed} path={summary_path} >&2",
        "  exit 1",
        "fi",
        f"echo FINISH seed={seed} summary={summary_path}",
    ]

    parts = prefix_lines + [manifest_block, run_block] + suffix_lines
    return "\n".join(parts)


def build_session_inner_command(
    *,
    remote_base: Path | PurePosixPath | str,
    run_root: Path | PurePosixPath | str,
    python_bin: Path | PurePosixPath | str,
    dataset_dir: Path | PurePosixPath | str,
    gpu_id: int,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    force: bool = False,
    skip_existing: bool = True,
) -> str:
    remote_base = _to_posix_path(remote_base)
    run_root = _to_posix_path(run_root)
    lines = [
        f"cd {_q(remote_base)}",
        "set -euo pipefail",
        f"mkdir -p {_q(run_root)}",
    ]
    for seed in seeds:
        lines.append(
            build_seed_inner_command(
                remote_base=remote_base,
                run_root=run_root,
                python_bin=python_bin,
                dataset_dir=dataset_dir,
                seed=seed,
                gpu_id=gpu_id,
                force=force,
                skip_existing=skip_existing,
            )
        )
    return "\n".join(lines)


def build_remote_command(
    *,
    remote_base: Path | PurePosixPath | str,
    run_root: Path | PurePosixPath | str,
    python_bin: Path | PurePosixPath | str,
    dataset_dir: Path | PurePosixPath | str,
    session_name: str,
    gpu_id: int,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    force: bool = False,
    skip_existing: bool = True,
) -> str:
    remote_base = _to_posix_path(remote_base)
    inner_command = build_session_inner_command(
        remote_base=remote_base,
        run_root=run_root,
        python_bin=python_bin,
        dataset_dir=dataset_dir,
        gpu_id=gpu_id,
        seeds=seeds,
        force=force,
        skip_existing=skip_existing,
    )
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
    parser = argparse.ArgumentParser(
        description="Launch CLOSE-02 ML1M core noise-floor seeds inside a remote tmux session."
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--remote-base", default=str(DEFAULT_REMOTE_BASE))
    parser.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT))
    parser.add_argument("--python-bin", default=str(DEFAULT_PYTHON_BIN))
    parser.add_argument("--dataset-dir", default=str(DEFAULT_DATASET_DIR))
    parser.add_argument("--session-name", default=DEFAULT_SESSION)
    parser.add_argument("--gpu-id", type=int, default=1)
    parser.add_argument("--seeds", nargs="+", type=int, default=list(DEFAULT_SEEDS))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-skip-existing", action="store_true")
    parser.add_argument("--print-only", action="store_true")
    return parser.parse_args()


def launch_remote_close02(*, print_only: bool = False, **kwargs: str | int | tuple[int, ...] | bool) -> str:
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
    ssh_command = launch_remote_close02(
        host=args.host,
        remote_base=args.remote_base,
        run_root=args.run_root,
        python_bin=args.python_bin,
        dataset_dir=args.dataset_dir,
        session_name=args.session_name,
        gpu_id=args.gpu_id,
        seeds=tuple(args.seeds),
        force=args.force,
        skip_existing=not args.no_skip_existing,
        print_only=args.print_only,
    )
    print(ssh_command)


if __name__ == "__main__":
    main()
