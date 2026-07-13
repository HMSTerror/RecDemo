from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, IO, Protocol

from .models import TaskSpec
from .storage import require_within


ALLOWED_INHERITED_ENV = {
    "HOME",
    "LANG",
    "LC_ALL",
    "LD_LIBRARY_PATH",
    "LOGNAME",
    "PATH",
    "PYTHONPATH",
    "TMPDIR",
    "USER",
    "VIRTUAL_ENV",
}


class GpuBusyError(RuntimeError):
    """Raised when GPU ownership cannot be established safely."""


class LockHandle(Protocol):
    def close(self) -> None:
        raise NotImplementedError


class LockBackend(Protocol):
    def try_acquire(self, path: Path) -> LockHandle | None:
        raise NotImplementedError


@dataclass(frozen=True)
class SpawnedProcess:
    process: subprocess.Popen
    log_handle: IO[bytes]


@dataclass(frozen=True)
class StartedChild:
    task_id: str
    pid: int
    process_start_time: str
    gpu_id: int | None


@dataclass(frozen=True)
class FinishedChild:
    task_id: str
    exit_code: int
    gpu_seconds: float
    artifacts_valid: bool
    reason: str | None


@dataclass
class _RunningProcess:
    task: TaskSpec
    spawned: SpawnedProcess
    process_start_time: str
    gpu_id: int | None
    lock_handle: LockHandle | None
    started_monotonic: float


def probe_gpu_pids(
    gpu_id: int,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> set[int]:
    command = [
        "nvidia-smi",
        f"--id={gpu_id}",
        "--query-compute-apps=pid",
        "--format=csv,noheader,nounits",
    ]
    result = runner(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise GpuBusyError(f"GPU probe failed for {gpu_id}: {(result.stderr or '').strip()}")
    rows = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if any(re.fullmatch(r"[1-9][0-9]*", row) is None for row in rows):
        raise GpuBusyError(
            f"GPU probe returned unrecognized rows for {gpu_id}: {rows!r}"
        )
    return {int(row) for row in rows}


def linux_process_start_token(pid: int) -> str:
    stat_path = Path("/proc") / str(pid) / "stat"
    fields = stat_path.read_text(encoding="utf-8").split()
    if len(fields) < 22:
        raise RuntimeError(f"cannot read Linux process start token for PID {pid}")
    return fields[21]


class LinuxFlockHandle:
    def __init__(self, handle: IO[str]) -> None:
        self._handle = handle

    def close(self) -> None:
        import fcntl

        fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close()


class LinuxFlockBackend:
    def try_acquire(self, path: Path) -> LinuxFlockHandle | None:
        import fcntl

        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            return None
        handle.seek(0)
        handle.truncate()
        handle.write(f"pid={os.getpid()}\n")
        handle.flush()
        os.fsync(handle.fileno())
        return LinuxFlockHandle(handle)


class ProcessSupervisor:
    def __init__(
        self,
        popen: Callable[..., subprocess.Popen] = subprocess.Popen,
        inherited_env: dict[str, str] | None = None,
    ) -> None:
        self._popen = popen
        source_env = dict(os.environ if inherited_env is None else inherited_env)
        self._base_env = {key: value for key, value in source_env.items() if key in ALLOWED_INHERITED_ENV}

    def start(
        self,
        *,
        argv: list[str],
        cwd: Path,
        env: dict[str, str],
        stdout_path: Path,
    ) -> SpawnedProcess:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        handle = stdout_path.open("ab", buffering=0)
        merged_env = dict(self._base_env)
        merged_env.update(env)
        try:
            process = self._popen(
                argv,
                cwd=str(cwd),
                env=merged_env,
                stdin=subprocess.DEVNULL,
                stdout=handle,
                stderr=subprocess.STDOUT,
                shell=False,
                start_new_session=True,
            )
        except BaseException:
            handle.close()
            raise
        return SpawnedProcess(process=process, log_handle=handle)


def _bind_cuda_override(argv: list[str], gpu_id: int) -> list[str]:
    """Keep Hydra's physical-device override aligned with the leased GPU.

    ``single_train.py`` derives ``CUDA_VISIBLE_DEVICES`` from its Hydra
    ``cuda=`` argument before it constructs ``cuda:0``.  The queue also sets
    ``CUDA_VISIBLE_DEVICES`` to the leased physical card, so leaving a stale
    ``cuda=0`` token would silently remap every leased card back to physical
    GPU 0.  Rewrite only the explicit Hydra override; all other argv tokens
    remain byte-for-byte unchanged.
    """

    return [f"cuda={gpu_id}" if token.startswith("cuda=") else token for token in argv]


class QueueRuntime:
    def __init__(
        self,
        *,
        queue_root: Path,
        supervisor: ProcessSupervisor,
        lock_backend: LockBackend,
        gpu_probe: Callable[[int], set[int]] = probe_gpu_pids,
        process_start_token: Callable[[int], str] = linux_process_start_token,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.queue_root = queue_root
        self.supervisor = supervisor
        self.lock_backend = lock_backend
        self.gpu_probe = gpu_probe
        self.process_start_token = process_start_token
        self.monotonic = monotonic
        self._running: dict[int, _RunningProcess] = {}

    def _task_log_path(self, task_id: str) -> Path:
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", task_id)
        return self.queue_root / "logs" / "tasks" / f"{safe_id}.log"

    def _start(
        self,
        task: TaskSpec,
        *,
        gpu_id: int | None,
        lock_handle: LockHandle | None,
    ) -> StartedChild:
        if task.gpu_slots == 1:
            cwd = require_within(Path(task.cwd), self.queue_root)
            run_dir = require_within(Path(task.run_dir), self.queue_root)
            if cwd != run_dir:
                raise ValueError(f"{task.task_id}: runtime cwd must equal run_dir")
            cwd.mkdir(parents=True, exist_ok=True)
        else:
            cwd = Path(task.cwd)
        env = dict(task.env)
        bound_argv = list(task.argv)
        if gpu_id is not None:
            env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
            env["AAAI_PHYSICAL_GPU_ID"] = str(gpu_id)
            env["AAAI_LOGICAL_GPU_ID"] = "0"
            bound_argv = _bind_cuda_override(bound_argv, gpu_id)
        try:
            spawned = self.supervisor.start(
                argv=bound_argv,
                cwd=cwd,
                env=env,
                stdout_path=self._task_log_path(task.task_id),
            )
        except BaseException:
            if lock_handle is not None:
                lock_handle.close()
            raise
        try:
            token = self.process_start_token(spawned.process.pid)
        except BaseException:
            # Popen has already succeeded. Releasing the GPU lock or dropping
            # the log handle here would orphan a live scientific run. Keep the
            # child supervised and persist an explicitly unverified identity;
            # recovery will fail closed instead of treating it as retryable.
            token = f"unverified:{spawned.process.pid}"
        running = _RunningProcess(
            task=task,
            spawned=spawned,
            process_start_time=token,
            gpu_id=gpu_id,
            lock_handle=lock_handle,
            started_monotonic=self.monotonic(),
        )
        self._running[spawned.process.pid] = running
        return StartedChild(task.task_id, spawned.process.pid, token, gpu_id)

    def start_task(self, task: TaskSpec, allowed_gpu_ids: tuple[int, ...]) -> StartedChild | None:
        if task.gpu_slots == 0:
            if any(running.gpu_id is None for running in self._running.values()):
                return None
            return self._start(task, gpu_id=None, lock_handle=None)

        locally_used = {running.gpu_id for running in self._running.values() if running.gpu_id is not None}
        for gpu_id in allowed_gpu_ids:
            if gpu_id in locally_used:
                continue
            lock_path = self.queue_root / "state" / f"gpu{gpu_id}.lock"
            lock_handle = self.lock_backend.try_acquire(lock_path)
            if lock_handle is None:
                continue
            try:
                if self.gpu_probe(gpu_id):
                    lock_handle.close()
                    continue
                return self._start(task, gpu_id=gpu_id, lock_handle=lock_handle)
            except BaseException:
                if not getattr(lock_handle, "closed", False):
                    try:
                        lock_handle.close()
                    except BaseException:
                        pass
                raise
        return None

    def observe_finished(self) -> list[FinishedChild]:
        finished: list[FinishedChild] = []
        for pid, running in list(self._running.items()):
            exit_code = running.spawned.process.poll()
            if exit_code is None:
                continue
            elapsed = max(0.0, self.monotonic() - running.started_monotonic)
            gpu_seconds = elapsed if running.gpu_id is not None else 0.0
            missing: list[str] = []
            empty: list[str] = []
            if exit_code == 0:
                for relative in running.task.success_artifacts:
                    artifact = require_within(self.queue_root / relative, self.queue_root)
                    if not artifact.is_file():
                        missing.append(relative)
                    elif artifact.stat().st_size <= 0:
                        empty.append(relative)
            log_path = self._task_log_path(running.task.task_id)
            empty_log = (
                exit_code == 0
                and (not log_path.is_file() or log_path.stat().st_size <= 0)
            )
            artifacts_valid = exit_code == 0 and not missing and not empty and not empty_log
            reason = None
            if exit_code != 0:
                reason = f"exit_code={exit_code}"
            elif missing:
                reason = f"missing_artifacts={','.join(missing)}"
            elif empty:
                reason = f"empty_artifacts={','.join(empty)}"
            elif empty_log:
                reason = f"empty_log={log_path.relative_to(self.queue_root).as_posix()}"
            running.spawned.log_handle.close()
            if running.lock_handle is not None:
                running.lock_handle.close()
            del self._running[pid]
            finished.append(
                FinishedChild(
                    task_id=running.task.task_id,
                    exit_code=exit_code,
                    gpu_seconds=gpu_seconds,
                    artifacts_valid=artifacts_valid,
                    reason=reason,
                )
            )
        return finished
