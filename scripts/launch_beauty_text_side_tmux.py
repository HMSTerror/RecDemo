#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import shlex
import subprocess


DEFAULT_HOST = "l20"
DEFAULT_REMOTE_REPO_ROOT = PurePosixPath("/data/Zijian/goal/RecDemo")
DEFAULT_REMOTE_DATASET_ROOT = DEFAULT_REMOTE_REPO_ROOT / "dataset" / "paper_raw_v1"
DEFAULT_REMOTE_TMP_DIR = DEFAULT_REMOTE_REPO_ROOT / ".tmp"
DEFAULT_DATASET_DIR = DEFAULT_REMOTE_DATASET_ROOT / "Beauty"
DEFAULT_MODEL_PATH = PurePosixPath("/data/models/sentence-transformers/sentence-t5-xl")
DEFAULT_PYTHON_BIN = PurePosixPath("/data/Zijian/goal/PreferGrow/.venv/bin/python3")
DEFAULT_RUN_DIR = PurePosixPath("/data/Zijian/goal/RecDemoRuns/beauty_fallback_safe")
DEFAULT_SESSION_NAME = "beauty_fallback_safe"


def _to_posix_path(pathlike: Path | PurePosixPath | str) -> PurePosixPath:
    return PurePosixPath(str(pathlike).replace("\\", "/"))


def _q(pathlike: Path | PurePosixPath | str) -> str:
    return shlex.quote(str(_to_posix_path(pathlike)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the Beauty-only text-side v2 run inside remote tmux.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--remote-repo-root", default=str(DEFAULT_REMOTE_REPO_ROOT))
    parser.add_argument("--dataset-dir", default=str(DEFAULT_DATASET_DIR))
    parser.add_argument("--model-path", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--python-bin", default=str(DEFAULT_PYTHON_BIN))
    parser.add_argument("--run-dir", default=str(DEFAULT_RUN_DIR))
    parser.add_argument("--session-name", default=DEFAULT_SESSION_NAME)
    parser.add_argument("--gpu-id", type=int, default=0)
    parser.add_argument("--print-only", action="store_true", help="Print the ssh command instead of executing it.")
    return parser.parse_args()


def build_remote_beauty_command(
    *,
    remote_repo_root: Path | PurePosixPath | str,
    dataset_dir: Path | PurePosixPath | str,
    model_path: Path | PurePosixPath | str,
    python_bin: Path | PurePosixPath | str,
    run_dir: Path | PurePosixPath | str,
    gpu_id: int,
) -> str:
    remote_repo_root = _to_posix_path(remote_repo_root)
    dataset_dir = _to_posix_path(dataset_dir)
    model_path = _to_posix_path(model_path)
    python_bin = _to_posix_path(python_bin)
    run_dir = _to_posix_path(run_dir)
    tmp_dir = _to_posix_path(DEFAULT_REMOTE_TMP_DIR)

    item_metadata_path = dataset_dir / "item_metadata.csv"
    embeddings_path = dataset_dir / "sentence_t5_xl_item_emb.pt"
    null_curve_path = dataset_dir / "agreement_null_curves.json"

    return (
        f"cd {_q(remote_repo_root)} && "
        f"mkdir -p {_q(tmp_dir)} && "
        f"export TMPDIR={_q(tmp_dir)} && "
        f"if [ ! -f {_q(item_metadata_path)} ]; then echo 'missing dataset metadata: {item_metadata_path}' >&2; exit 1; fi && "
        f"if [ ! -d {_q(model_path)} ]; then echo 'missing sentence-t5 model: {model_path}' >&2; exit 1; fi && "
        f"if [ ! -f {_q(embeddings_path)} ]; then "
        f"{_q(python_bin)} scripts/build_text_side_embeddings.py "
        f"--dataset-dir {_q(dataset_dir)} "
        f"--model-path {_q(model_path)} "
        f"--device {shlex.quote(f'cuda:{gpu_id}')}; "
        f"fi && "
        f"if [ ! -f {_q(null_curve_path)} ]; then "
        f"{_q(python_bin)} scripts/build_agreement_null_curves.py "
        f"--dataset-dir {_q(dataset_dir)} "
        f"--embeddings-path {_q(embeddings_path)}; "
        f"fi && "
        f"mkdir -p {_q(run_dir)} && "
        f"exec {_q(python_bin)} -u single_train.py "
        f"work_dir={_q(run_dir)} "
        f"cuda={gpu_id} "
        f"random_seed=100 "
        f"training.data=Beauty "
        f"data.Beauty.path={_q(dataset_dir)} "
        f"graph.type=proposal_adaptive "
        f"graph.is_disliked_item=True "
        f"model.hidden_size=256 "
        f"model.cond_dim=256 "
        f"training.nonpreference_user_ratio=0.1 "
        f"optim.lr=0.0001 "
        f"model.score_flag=False "
        f"model.score_method=oricos "
        f"training.n_iters=2000000 "
        f"training.eval_freq=1000 "
        f"training.snapshot_freq=1000 "
        f"training.snapshot_freq_for_preemption=1000 "
        f"training.snapshot_sampling=True "
        f"training.early_stop_patience=5 "
        f"training.early_stop_min_step=5000 "
        f"training.early_stop_metric=ndcg10 "
        f"training.early_stop_strength=p2 "
        f"training.early_stop_min_delta=0.0 "
        f"text_side.enabled=True "
        f"text_side.dataset_dir={_q(dataset_dir)} "
        f"text_side.embeddings_path={_q(embeddings_path)} "
        f"text_side.agreement_null_curve_path={_q(null_curve_path)} "
        f"text_side.kernel_version=v2"
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


def launch_remote_beauty(
    *,
    host: str,
    remote_repo_root: Path | PurePosixPath | str,
    dataset_dir: Path | PurePosixPath | str,
    model_path: Path | PurePosixPath | str,
    python_bin: Path | PurePosixPath | str,
    run_dir: Path | PurePosixPath | str,
    session_name: str,
    gpu_id: int,
    print_only: bool = False,
) -> str:
    remote_command = build_remote_beauty_command(
        remote_repo_root=remote_repo_root,
        dataset_dir=dataset_dir,
        model_path=model_path,
        python_bin=python_bin,
        run_dir=run_dir,
        gpu_id=gpu_id,
    )
    ssh_command = build_tmux_ssh_command(host=host, session_name=session_name, remote_command=remote_command)
    if print_only:
        return ssh_command
    subprocess.run(build_ssh_argv(host=host, session_name=session_name, remote_command=remote_command), check=True)
    return ssh_command


def main() -> None:
    args = parse_args()
    ssh_command = launch_remote_beauty(
        host=args.host,
        remote_repo_root=args.remote_repo_root,
        dataset_dir=args.dataset_dir,
        model_path=args.model_path,
        python_bin=args.python_bin,
        run_dir=args.run_dir,
        session_name=args.session_name,
        gpu_id=args.gpu_id,
        print_only=args.print_only,
    )
    print(ssh_command)


if __name__ == "__main__":
    main()
