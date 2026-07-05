#!/usr/bin/env bash

set -euo pipefail

BASE="${BASE:-/data/Zijian/goal/RecDemo_clean_main}"
OLD_ROOT="${OLD_ROOT:-/data/Zijian/goal/RecDemo}"
RUN_ROOT="${RUN_ROOT:-/data/Zijian/goal/RecDemoRuns/main_table_text_side}"
DATASET_ROOT="${DATASET_ROOT:-$OLD_ROOT/dataset/paper_raw_v1}"
PYTHON_BIN="${PYTHON_BIN:-/data/Zijian/goal/PreferGrow/.venv/bin/python}"
MODEL_PATH="${MODEL_PATH:-/data/models/sentence-transformers/sentence-t5-xl}"
TEXT_UTILITY_REPORT_PATH="${TEXT_UTILITY_REPORT_PATH:-$OLD_ROOT/docs/reports/data/2026-07-02-gate0/gate0_text_utility_report.json}"
REPORT_DIR="${REPORT_DIR:-$BASE/docs/reports/data/$(date +%F)-sprint05}"
PROVISIONAL_SESSION="${PROVISIONAL_SESSION:-sprint05_backfill_gpu1}"
PROVISIONAL_LOG="${PROVISIONAL_LOG:-$RUN_ROOT/ml1m_proposal_adaptive_mainpath/logs/ml1m_proposal_adaptive_mainpath.log}"
WAIT_SECONDS="${WAIT_SECONDS:-120}"

log() {
  echo "[$(date '+%F %T %z')] $*"
}

launch_dataset() {
  local dataset="$1"
  local gpu="$2"
  local prefix="$3"
  log "launch dataset=$dataset gpu=$gpu prefix=$prefix"
  env \
    PYTHON_BIN="$PYTHON_BIN" \
    DATASET_ROOT="$DATASET_ROOT" \
    RUN_ROOT="$RUN_ROOT" \
    MODEL_PATH="$MODEL_PATH" \
    GPU_IDS_CSV="$gpu" \
    SESSION_PREFIX="$prefix" \
    DATASETS_CSV="$dataset" \
    FORCE=1 \
    SKIP_EXISTING=0 \
    REQUIRE_SUMMARY=1 \
    WRITE_SNAPSHOT_CHECKPOINT=False \
    WRITE_BEST_CHECKPOINT=True \
    EARLY_STOP_STRENGTH=p5 \
    TEXT_KERNEL_VERSION=v2 \
    TEXT_G_MAX=0.5 \
    TEXT_AGREEMENT_K=2.0 \
    TEXT_UTILITY_REPORT_PATH="$TEXT_UTILITY_REPORT_PATH" \
    bash "$BASE/scripts/run_text_side_main_table_tmux.sh" "$BASE"
}

wait_for_sessions() {
  while true; do
    local active=0
    local session_name
    for session_name in "$@"; do
      if tmux has-session -t "$session_name" 2>/dev/null; then
        active=1
      fi
    done
    if [ "$active" -eq 0 ]; then
      break
    fi
    sleep "$WAIT_SECONDS"
  done
}

wait_for_provisional_ml1m() {
  log "waiting for provisional ML1M to finish"
  while tmux has-session -t "$PROVISIONAL_SESSION" 2>/dev/null; do
    if [ -f "$PROVISIONAL_LOG" ] && grep -q "FINISH dataset=ML1M" "$PROVISIONAL_LOG"; then
      log "provisional ML1M finished; killing session to block stale ATG/Steam continuation"
      tmux kill-session -t "$PROVISIONAL_SESSION" || true
      break
    fi
    sleep "$WAIT_SECONDS"
  done
  if tmux has-session -t "$PROVISIONAL_SESSION" 2>/dev/null; then
    log "provisional session still present after wait loop"
  else
    log "provisional session cleared"
  fi
}

run_report() {
  mkdir -p "$REPORT_DIR"
  "$PYTHON_BIN" "$BASE/scripts/capture_text_side_main_table_snapshot.py" \
    --run-root "$RUN_ROOT" \
    --output-dir "$REPORT_DIR" \
    --datasets Steam ML1M Beauty ATG \
    --official-mode \
    --official-repo-root "$BASE" \
    --core-root "$OLD_ROOT/checkpoints-meta"
}

main() {
  log "orchestrator start"
  wait_for_provisional_ml1m
  launch_dataset Beauty 0 sprint05_official_beauty
  launch_dataset ML1M 1 sprint05_official_ml1m
  wait_for_sessions sprint05_official_beauty_gpu0 sprint05_official_ml1m_gpu1
  log "wave1 complete"
  run_report
  launch_dataset Steam 0 sprint05_official_steam
  launch_dataset ATG 1 sprint05_official_atg
  wait_for_sessions sprint05_official_steam_gpu0 sprint05_official_atg_gpu1
  log "wave2 complete"
  run_report
  log "orchestrator done"
}

main "$@"
