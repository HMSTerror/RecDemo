#!/usr/bin/env bash

set -euo pipefail

BASE="${BASE:-/data/Zijian/goal/RecDemo_clean_main}"
OLD_ROOT="${OLD_ROOT:-/data/Zijian/goal/RecDemo}"
RUN_ROOT="${RUN_ROOT:-/data/Zijian/goal/RecDemoRuns/main_table_text_side}"
PYTHON_BIN="${PYTHON_BIN:-/data/Zijian/goal/PreferGrow/.venv/bin/python}"
LOG_PATH="${LOG_PATH:-$RUN_ROOT/sprint05_watchdog.log}"
SNAPSHOT_ROOT="${SNAPSHOT_ROOT:-$BASE/docs/reports/data/$(date +%F)-sprint05-watchdog}"
ORCHESTRATOR_SESSION="${ORCHESTRATOR_SESSION:-sprint05_official_orchestrator}"
PROVISIONAL_SESSION="${PROVISIONAL_SESSION:-sprint05_backfill_gpu1}"
WAIT_SECONDS="${WAIT_SECONDS:-120}"

log() {
  local line="[$(date '+%F %T %z')] $*"
  echo "$line"
  echo "$line" >> "$LOG_PATH"
}

capture_snapshot() {
  local name="$1"
  mkdir -p "$SNAPSHOT_ROOT/$name"
  "$PYTHON_BIN" "$BASE/scripts/capture_text_side_main_table_snapshot.py" \
    --run-root "$RUN_ROOT" \
    --output-dir "$SNAPSHOT_ROOT/$name" \
    --datasets Steam ML1M Beauty ATG \
    --official-mode \
    --official-repo-root "$BASE" \
    --core-root "$OLD_ROOT/checkpoints-meta"
}

session_present() {
  local session_name="$1"
  tmux has-session -t "$session_name" 2>/dev/null
}

main() {
  : > "$LOG_PATH"
  log "watchdog start"
  local wave1_snapshot_done=0
  while true; do
    local provisional="absent"
    local wave1=0
    local done=0
    if session_present "$PROVISIONAL_SESSION"; then
      provisional="present"
    fi
    if session_present sprint05_official_beauty_gpu0 || session_present sprint05_official_ml1m_gpu1; then
      wave1=1
    fi
    if ! session_present "$ORCHESTRATOR_SESSION"; then
      done=1
    fi
    log "poll provisional=$provisional wave1=$wave1 done=$done"
    if [ "$wave1" -eq 1 ] && [ "$wave1_snapshot_done" -eq 0 ]; then
      capture_snapshot wave1_started
      log "captured wave1_started snapshot"
      wave1_snapshot_done=1
    fi
    if [ "$done" -eq 1 ]; then
      capture_snapshot final
      log "captured final snapshot"
      break
    fi
    sleep "$WAIT_SECONDS"
  done
  log "watchdog done"
}

main "$@"
