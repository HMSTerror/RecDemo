from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.aaai27_adapters.pilot_task_wrapper import cli


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one AAAI-27 pilot task with immutable log/artifact provenance."
    )
    parser.add_argument("child_argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    child_argv = list(args.child_argv)
    if child_argv[:1] == ["--"]:
        child_argv = child_argv[1:]
    raise SystemExit(cli(child_argv))


if __name__ == "__main__":
    main()
