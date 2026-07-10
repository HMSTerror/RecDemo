import re
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_e0_fulltail_matrix.sh"


class RunE0FulltailMatrixTests(unittest.TestCase):
    def test_matrix_contains_exactly_the_approved_18_frozen_evaluations(self) -> None:
        self.assertTrue(SCRIPT_PATH.exists(), f"missing script: {SCRIPT_PATH}")
        text = SCRIPT_PATH.read_text(encoding="utf-8")
        invocations = re.findall(r"^\s+run_(?:core|diff)\s+([a-z0-9_]+)\s+", text, re.MULTILINE)

        self.assertEqual(
            {
                "host_steam", "host_ml1m", "host_beauty", "host_atg",
                "ours_full_steam", "ours_full_ml1m", "ours_full_beauty", "ours_full_atg",
                "global_p_steam", "u_shuffle_steam", "text_anchor_only_steam",
                "global_p_beauty", "u_shuffle_beauty", "text_anchor_only_beauty",
                "diffurec_steam", "diffurec_ml1m", "diffurec_beauty", "diffurec_atg",
            },
            set(invocations),
        )
        self.assertIn("aaai27_e0_fulltail_20260710", text)
        self.assertIn("5709c6283cb127d727f6b769d8409343f4aae824", text)
        self.assertNotIn("single_train.py", text)

    def test_only_legacy_host_atg_receives_explicit_catalog_mismatch_allowance(self) -> None:
        text = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertRegex(
            text,
            r"run_core host_atg ATG .* 1942 - allow_legacy_catalog_mismatch",
        )
        authorized_calls = re.findall(
            r"^\s+run_core\s+([a-z0-9_]+)\s+.*\s+allow_legacy_catalog_mismatch$",
            text,
            re.MULTILINE,
        )
        self.assertEqual(["host_atg"], authorized_calls)

    def test_logger_is_drained_on_success_and_early_failure(self) -> None:
        text = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn('LOGGER_PID="$!"', text)
        self.assertIn("trap finalize_logger EXIT", text)
        self.assertRegex(
            text,
            r'finalize_logger\(\) \{\s+'
            r'local task_status=\$\?\s+'
            r'trap - EXIT\s+'
            r'set \+e\s+'
            r'exec 1>&- 2>&-\s+'
            r'wait "\$LOGGER_PID"\s+'
            r'local logger_status=\$\?\s+'
            r'if \(\( task_status != 0 \)\); then\s+'
            r'exit "\$task_status"\s+'
            r'fi\s+'
            r'exit "\$logger_status"\s+'
            r'\}',
        )
        self.assertRegex(text, r'echo "E0_SHARD_DONE shard=\$SHARD gpu=\$GPU_INDEX"\s*$')

    def test_logger_trap_waits_and_preserves_the_primary_exit_status(self) -> None:
        bash = Path(shutil.which("bash") or r"C:\Program Files\Git\bin\bash.exe")
        if "system32" in str(bash).lower():
            bash = Path(r"C:\Program Files\Git\bin\bash.exe")
        if not bash.exists():
            self.skipTest("Bash is required for the process-substitution lifecycle test")

        text = SCRIPT_PATH.read_text(encoding="utf-8")
        function_match = re.search(r"finalize_logger\(\) \{\n.*?\n\}", text, re.DOTALL)
        self.assertIsNotNone(function_match)
        function_source = function_match.group(0)
        harness = f'''set -euo pipefail
exec > >(sleep 0.2; tee -a "$1"; [[ "$2" != "logger_failure" ]]) 2>&1
LOGGER_PID="$!"
{function_source}
trap finalize_logger EXIT
echo "LOGGER_HARNESS_START"
if [[ "$2" == "failure" ]]; then
  echo "LOGGER_HARNESS_FAILURE_TAIL"
  exit 37
fi
echo "LOGGER_HARNESS_DONE"
'''

        with tempfile.TemporaryDirectory() as temp_dir:
            for mode, expected_status, expected_tail in (
                ("success", 0, "LOGGER_HARNESS_DONE"),
                ("failure", 37, "LOGGER_HARNESS_FAILURE_TAIL"),
                ("logger_failure", 1, "LOGGER_HARNESS_DONE"),
            ):
                with self.subTest(mode=mode):
                    log_path = Path(temp_dir) / f"{mode}.log"
                    started = time.monotonic()
                    result = subprocess.run(
                        [str(bash), "-c", harness, "logger-harness", str(log_path), mode],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    elapsed = time.monotonic() - started
                    self.assertEqual(expected_status, result.returncode, result.stderr)
                    self.assertGreaterEqual(elapsed, 0.15)
                    self.assertIn(expected_tail, log_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
