import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from aaai27_queue.models import TaskSpec
from aaai27_queue.runtime import (
    GpuBusyError,
    LinuxFlockBackend,
    ProcessSupervisor,
    QueueRuntime,
    probe_gpu_free_memory_mib,
    probe_gpu_pids,
)
from aaai27_queue_testdata import make_task


class FakeProcess:
    def __init__(self, pid: int, exit_code: int | None = None) -> None:
        self.pid = pid
        self.exit_code = exit_code

    def poll(self) -> int | None:
        return self.exit_code


class FakeLock:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeLockBackend:
    def __init__(self) -> None:
        self.handles: dict[str, FakeLock] = {}

    def try_acquire(self, path: Path) -> FakeLock | None:
        key = str(path)
        existing = self.handles.get(key)
        if existing is not None and not existing.closed:
            return None
        handle = FakeLock()
        self.handles[key] = handle
        return handle


class QueueRuntimeTests(unittest.TestCase):
    def runtime_task(self, root: Path, *, task_id: str, **overrides) -> TaskSpec:
        run_dir = root / "runs" / task_id
        return TaskSpec.from_dict(
            make_task(
                task_id=task_id,
                cwd=str(run_dir),
                run_dir=str(run_dir),
                **overrides,
            )
        )

    def test_gpu_probe_parses_integer_pids(self) -> None:
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, "123\n456\n", ""))

        self.assertEqual({123, 456}, probe_gpu_pids(1, runner=runner))
        self.assertIn("--id=1", runner.call_args.args[0])

    def test_gpu_probe_unknown_row_is_fail_closed(self) -> None:
        runner = mock.Mock(
            return_value=subprocess.CompletedProcess([], 0, "N/A\n", "")
        )

        with self.assertRaisesRegex(GpuBusyError, "unrecognized"):
            probe_gpu_pids(1, runner=runner)

    def test_gpu_probe_failure_is_fail_closed(self) -> None:
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 9, "", "driver error"))
        with self.assertRaisesRegex(GpuBusyError, "driver error"):
            probe_gpu_pids(0, runner=runner)

    def test_gpu_memory_probe_parses_one_integer(self) -> None:
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, "34837\n", ""))

        self.assertEqual(34837, probe_gpu_free_memory_mib(0, runner=runner))
        self.assertIn("--id=0", runner.call_args.args[0])

    def test_gpu_memory_probe_is_fail_closed_on_unknown_output(self) -> None:
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, "N/A\n", ""))

        with self.assertRaisesRegex(GpuBusyError, "memory probe"):
            probe_gpu_free_memory_mib(0, runner=runner)

    def test_supervisor_uses_argv_no_shell_new_session_and_env_allowlist(self) -> None:
        popen = mock.Mock(return_value=FakeProcess(77))
        supervisor = ProcessSupervisor(popen=popen, inherited_env={"PATH": "safe", "SECRET_TOKEN": "hidden"})
        with tempfile.TemporaryDirectory() as tmpdir:
            spawned = supervisor.start(
                argv=["python", "train.py", "--seed", "100"],
                cwd=Path(tmpdir),
                env={"CUDA_VISIBLE_DEVICES": "0", "PYTHONHASHSEED": "100"},
                stdout_path=Path(tmpdir) / "task.log",
            )
            kwargs = popen.call_args.kwargs
            self.assertFalse(kwargs["shell"])
            self.assertTrue(kwargs["start_new_session"])
            self.assertEqual("safe", kwargs["env"]["PATH"])
            self.assertNotIn("SECRET_TOKEN", kwargs["env"])
            self.assertEqual("0", kwargs["env"]["CUDA_VISIBLE_DEVICES"])
            spawned.log_handle.close()

    def test_unknown_gpu_process_blocks_spawn(self) -> None:
        popen = mock.Mock()
        runtime = QueueRuntime(
            queue_root=Path("/tmp/queue"),
            supervisor=ProcessSupervisor(popen=popen),
            lock_backend=FakeLockBackend(),
            gpu_probe=lambda gpu_id: {999},
            process_start_token=lambda pid: f"token-{pid}",
        )
        task = TaskSpec.from_dict(make_task(task_id="gpu.blocked"))

        self.assertIsNone(runtime.start_task(task, (0,)))
        popen.assert_not_called()

    def test_shared_gpu_allows_one_local_task_beside_one_external_process(self) -> None:
        process = FakeProcess(301)
        popen = mock.Mock(return_value=process)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime = QueueRuntime(
                queue_root=root,
                supervisor=ProcessSupervisor(popen=popen),
                lock_backend=FakeLockBackend(),
                gpu_probe=lambda gpu_id: {900},
                gpu_memory_probe=lambda gpu_id: 30000,
                process_descendants=lambda pid: set(),
                max_processes_per_gpu=2,
                min_free_memory_mib=8192,
                process_start_token=lambda pid: f"token-{pid}",
            )

            first = runtime.start_task(self.runtime_task(root, task_id="gpu.shared-first"), (0,))
            third_total = runtime.start_task(self.runtime_task(root, task_id="gpu.shared-third"), (0,))

            self.assertEqual(0, first.gpu_id)
            self.assertIsNone(third_total)
            self.assertEqual(1, popen.call_count)
            runtime._running[301].spawned.log_handle.close()

    def test_local_gpu_descendant_is_not_double_counted(self) -> None:
        processes = [FakeProcess(401), FakeProcess(402)]
        popen = mock.Mock(side_effect=processes)
        gpu_rows = iter((set(), set(), {1401}, {1401}))
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime = QueueRuntime(
                queue_root=root,
                supervisor=ProcessSupervisor(popen=popen),
                lock_backend=FakeLockBackend(),
                gpu_probe=lambda gpu_id: next(gpu_rows),
                gpu_memory_probe=lambda gpu_id: 30000,
                process_descendants=lambda pid: {1401} if pid == 401 else set(),
                max_processes_per_gpu=2,
                min_free_memory_mib=8192,
                process_start_token=lambda pid: f"token-{pid}",
            )

            first = runtime.start_task(self.runtime_task(root, task_id="gpu.wrapper-one"), (0,))
            second = runtime.start_task(self.runtime_task(root, task_id="gpu.wrapper-two"), (0,))

            self.assertEqual(0, first.gpu_id)
            self.assertEqual(0, second.gpu_id)
            self.assertEqual(2, popen.call_count)
            for running in runtime._running.values():
                running.spawned.log_handle.close()

    def test_shared_gpu_blocks_when_free_memory_is_below_reserve(self) -> None:
        popen = mock.Mock()
        runtime = QueueRuntime(
            queue_root=Path("/tmp/queue"),
            supervisor=ProcessSupervisor(popen=popen),
            lock_backend=FakeLockBackend(),
            gpu_probe=lambda gpu_id: {900},
            gpu_memory_probe=lambda gpu_id: 8191,
            process_descendants=lambda pid: set(),
            max_processes_per_gpu=2,
            min_free_memory_mib=8192,
        )

        self.assertIsNone(runtime.start_task(TaskSpec.from_dict(make_task(task_id="gpu.low-memory")), (0,)))
        popen.assert_not_called()

    def test_full_first_gpu_does_not_block_second_gpu(self) -> None:
        process = FakeProcess(501)
        popen = mock.Mock(return_value=process)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime = QueueRuntime(
                queue_root=root,
                supervisor=ProcessSupervisor(popen=popen),
                lock_backend=FakeLockBackend(),
                gpu_probe=lambda gpu_id: {801, 802} if gpu_id == 0 else {803},
                gpu_memory_probe=lambda gpu_id: 30000,
                process_descendants=lambda pid: set(),
                max_processes_per_gpu=2,
                min_free_memory_mib=8192,
                process_start_token=lambda pid: f"token-{pid}",
            )

            started = runtime.start_task(self.runtime_task(root, task_id="gpu.second-card"), (0, 1))

            self.assertEqual(1, started.gpu_id)
            runtime._running[501].spawned.log_handle.close()

    def test_efficiency_task_requires_an_empty_gpu_and_blocks_sharing(self) -> None:
        processes = [FakeProcess(601), FakeProcess(602)]
        popen = mock.Mock(side_effect=processes)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            occupied = QueueRuntime(
                queue_root=root,
                supervisor=ProcessSupervisor(popen=popen),
                lock_backend=FakeLockBackend(),
                gpu_probe=lambda gpu_id: {999},
                gpu_memory_probe=lambda gpu_id: 30000,
                process_descendants=lambda pid: set(),
                max_processes_per_gpu=2,
                min_free_memory_mib=8192,
            )
            efficiency = self.runtime_task(
                root,
                task_id="gpu.efficiency",
                kind="efficiency",
            )
            self.assertIsNone(occupied.start_task(efficiency, (0,)))

            empty = QueueRuntime(
                queue_root=root,
                supervisor=ProcessSupervisor(popen=popen),
                lock_backend=FakeLockBackend(),
                gpu_probe=lambda gpu_id: set(),
                gpu_memory_probe=lambda gpu_id: 30000,
                process_descendants=lambda pid: set(),
                max_processes_per_gpu=2,
                min_free_memory_mib=8192,
                process_start_token=lambda pid: f"token-{pid}",
            )
            exclusive = empty.start_task(efficiency, (0,))
            normal = empty.start_task(self.runtime_task(root, task_id="gpu.normal"), (0,))

            self.assertEqual(0, exclusive.gpu_id)
            self.assertIsNone(normal)
            empty._running[601].spawned.log_handle.close()

    def test_runtime_creates_contained_task_cwd_before_spawn(self) -> None:
        process = FakeProcess(97)
        popen = mock.Mock(return_value=process)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_dir = root / "runs" / "gpu.contained"
            runtime = QueueRuntime(
                queue_root=root,
                supervisor=ProcessSupervisor(popen=popen),
                lock_backend=FakeLockBackend(),
                gpu_probe=lambda gpu_id: set(),
                process_start_token=lambda pid: f"token-{pid}",
            )
            task = TaskSpec.from_dict(
                make_task(
                    task_id="gpu.contained",
                    cwd=str(run_dir),
                    run_dir=str(run_dir),
                )
            )

            try:
                runtime.start_task(task, (1,))

                self.assertTrue(run_dir.is_dir())
                self.assertEqual(str(run_dir), popen.call_args.kwargs["cwd"])
            finally:
                runtime._running[97].spawned.log_handle.close()

    def test_runtime_rejects_task_cwd_outside_queue_root(self) -> None:
        process = FakeProcess(99)
        popen = mock.Mock(return_value=process)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            outside = root.parent / "outside-r6-task"
            runtime = QueueRuntime(
                queue_root=root,
                supervisor=ProcessSupervisor(popen=popen),
                lock_backend=FakeLockBackend(),
                gpu_probe=lambda gpu_id: set(),
            )
            task = TaskSpec.from_dict(
                make_task(
                    task_id="gpu.outside",
                    cwd=str(outside),
                    run_dir=str(outside),
                )
            )

            try:
                with self.assertRaisesRegex(ValueError, "outside allowed root"):
                    runtime.start_task(task, (1,))
                popen.assert_not_called()
            finally:
                if 99 in runtime._running:
                    runtime._running[99].spawned.log_handle.close()

    def test_runtime_rejects_task_cwd_that_differs_from_run_dir(self) -> None:
        process = FakeProcess(100)
        popen = mock.Mock(return_value=process)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime = QueueRuntime(
                queue_root=root,
                supervisor=ProcessSupervisor(popen=popen),
                lock_backend=FakeLockBackend(),
                gpu_probe=lambda gpu_id: set(),
            )
            task = TaskSpec.from_dict(
                make_task(
                    task_id="gpu.mismatch",
                    cwd=str(root / "runs" / "cwd"),
                    run_dir=str(root / "runs" / "different"),
                )
            )

            try:
                with self.assertRaisesRegex(ValueError, "cwd must equal run_dir"):
                    runtime.start_task(task, (1,))
                popen.assert_not_called()
            finally:
                if 100 in runtime._running:
                    runtime._running[100].spawned.log_handle.close()

    def test_runtime_preserves_existing_source_cwd_for_cpu_contract_gate(self) -> None:
        process = FakeProcess(110)
        popen = mock.Mock(return_value=process)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "queue"
            source_root = Path(tmpdir) / "immutable-source"
            source_root.mkdir()
            runtime = QueueRuntime(
                queue_root=root,
                supervisor=ProcessSupervisor(popen=popen),
                lock_backend=FakeLockBackend(),
                process_start_token=lambda pid: f"token-{pid}",
            )
            task = TaskSpec.from_dict(
                make_task(
                    task_id="contract.gate",
                    kind="contract_gate",
                    gpu_slots=0,
                    seed=None,
                    cwd=str(source_root),
                    run_dir=str(root / "gates" / "contract"),
                )
            )

            try:
                try:
                    started = runtime.start_task(task, (1,))
                except ValueError as exc:
                    self.fail(f"CPU contract gate source cwd was rejected: {exc}")
                self.assertEqual("contract.gate", started.task_id)
                self.assertEqual(str(source_root), popen.call_args.kwargs["cwd"])
            finally:
                if 110 in runtime._running:
                    runtime._running[110].spawned.log_handle.close()

    def test_two_gpu_tasks_get_distinct_physical_cards_and_third_waits(self) -> None:
        processes = [FakeProcess(101), FakeProcess(102), FakeProcess(103)]
        popen = mock.Mock(side_effect=processes)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime = QueueRuntime(
                queue_root=root,
                supervisor=ProcessSupervisor(popen=popen, inherited_env={"PATH": os.environ.get("PATH", "")}),
                lock_backend=FakeLockBackend(),
                gpu_probe=lambda gpu_id: set(),
                process_start_token=lambda pid: f"token-{pid}",
                monotonic=lambda: 10.0,
            )
            first = runtime.start_task(self.runtime_task(root, task_id="gpu.first"), (0, 1))
            second = runtime.start_task(self.runtime_task(root, task_id="gpu.second"), (0, 1))
            third = runtime.start_task(self.runtime_task(root, task_id="gpu.third"), (0, 1))

            self.assertEqual(0, first.gpu_id)
            self.assertEqual(1, second.gpu_id)
            self.assertIsNone(third)
            self.assertEqual("0", popen.call_args_list[0].kwargs["env"]["CUDA_VISIBLE_DEVICES"])
            self.assertEqual("1", popen.call_args_list[1].kwargs["env"]["CUDA_VISIBLE_DEVICES"])

            for task_id in ("gpu.first", "gpu.second"):
                artifact = root / "artifacts" / task_id / "success.json"
                artifact.parent.mkdir(parents=True, exist_ok=True)
                artifact.write_text("{}\n", encoding="utf-8")
            processes[0].exit_code = 0
            processes[1].exit_code = 0
            self.assertEqual(2, len(runtime.observe_finished()))

    def test_gpu_binding_rewrites_hydra_cuda_override_to_physical_gpu(self) -> None:
        process = FakeProcess(131)
        popen = mock.Mock(return_value=process)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime = QueueRuntime(
                queue_root=root,
                supervisor=ProcessSupervisor(popen=popen),
                lock_backend=FakeLockBackend(),
                gpu_probe=lambda gpu_id: set(),
                process_start_token=lambda pid: f"token-{pid}",
            )
            task = self.runtime_task(
                root,
                task_id="gpu.cuda-override",
                argv=["python", "single_train.py", "cuda=0"],
            )

            try:
                started = runtime.start_task(task, (1,))

                self.assertEqual(1, started.gpu_id)
                self.assertEqual(["python", "single_train.py", "cuda=1"], popen.call_args.args[0])
                self.assertEqual("1", popen.call_args.kwargs["env"]["CUDA_VISIBLE_DEVICES"])
            finally:
                runtime._running[131].spawned.log_handle.close()

    def test_start_token_failure_keeps_spawned_child_tracked_until_observed(self) -> None:
        process = FakeProcess(151)
        popen = mock.Mock(return_value=process)
        locks = FakeLockBackend()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            task = self.runtime_task(root, task_id="gpu.unverified")
            runtime = QueueRuntime(
                queue_root=root,
                supervisor=ProcessSupervisor(popen=popen),
                lock_backend=locks,
                gpu_probe=lambda gpu_id: set(),
                process_start_token=mock.Mock(side_effect=OSError("/proc unavailable")),
                monotonic=lambda: 10.0,
            )

            started = runtime.start_task(task, (0,))

            self.assertEqual("unverified:151", started.process_start_time)
            lock = locks.handles[str(root / "state" / "gpu0.lock")]
            self.assertFalse(lock.closed)
            self.assertIsNone(
                runtime.start_task(self.runtime_task(root, task_id="gpu.waits"), (0,))
            )
            process.exit_code = 9
            finished = runtime.observe_finished()
            self.assertEqual("exit_code=9", finished[0].reason)
            self.assertTrue(lock.closed)

    def test_finished_task_releases_lock_and_accounts_gpu_seconds(self) -> None:
        process = FakeProcess(201)
        popen = mock.Mock(return_value=process)
        times = iter((10.0, 25.5))
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            task = self.runtime_task(
                root,
                task_id="gpu.done",
                success_artifacts=["artifacts/done.json"],
            )
            artifact = root / "artifacts" / "done.json"
            artifact.parent.mkdir()
            artifact.write_text("{}\n", encoding="utf-8")
            locks = FakeLockBackend()
            runtime = QueueRuntime(
                queue_root=root,
                supervisor=ProcessSupervisor(popen=popen),
                lock_backend=locks,
                gpu_probe=lambda gpu_id: set(),
                process_start_token=lambda pid: f"token-{pid}",
                monotonic=lambda: next(times),
            )
            runtime.start_task(task, (0,))
            runtime._task_log_path(task.task_id).write_text(
                "finished\n", encoding="utf-8"
            )
            process.exit_code = 0

            finished = runtime.observe_finished()

            self.assertEqual(1, len(finished))
            self.assertEqual(15.5, finished[0].gpu_seconds)
            self.assertTrue(finished[0].artifacts_valid)
            self.assertTrue(locks.handles[str(root / "state" / "gpu0.lock")].closed)

    def test_zero_byte_log_fails_artifact_validation(self) -> None:
        process = FakeProcess(202)
        popen = mock.Mock(return_value=process)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            task = self.runtime_task(
                root,
                task_id="gpu.empty-log",
                success_artifacts=["artifacts/done.json"],
            )
            artifact = root / "artifacts" / "done.json"
            artifact.parent.mkdir()
            artifact.write_text("{}\n", encoding="utf-8")
            runtime = QueueRuntime(
                queue_root=root,
                supervisor=ProcessSupervisor(popen=popen),
                lock_backend=FakeLockBackend(),
                gpu_probe=lambda gpu_id: set(),
                process_start_token=lambda pid: f"token-{pid}",
            )
            runtime.start_task(task, (0,))
            process.exit_code = 0

            finished = runtime.observe_finished()

            self.assertFalse(finished[0].artifacts_valid)
            self.assertIn("empty_log", finished[0].reason)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux flock integration")
    def test_linux_flock_rejects_second_holder(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LinuxFlockBackend()
            path = Path(tmpdir) / "gpu0.lock"
            first = backend.try_acquire(path)
            second = backend.try_acquire(path)
            self.assertIsNotNone(first)
            self.assertIsNone(second)
            first.close()
            third = backend.try_acquire(path)
            self.assertIsNotNone(third)
            third.close()


if __name__ == "__main__":
    unittest.main()
