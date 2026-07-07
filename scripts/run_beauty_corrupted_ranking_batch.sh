#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="${1:-/data/Zijian/goal/RecDemo}"
PYTHON_BIN="${PYTHON_BIN:-/data/Zijian/goal/PreferGrow/.venv/bin/python}"
DATASET_DIR="${DATASET_DIR:-$REPO_ROOT/dataset/paper_raw_v1/Beauty}"
RUN_ROOT="${RUN_ROOT:-/data/Zijian/goal/RecDemoRuns}"
GPU_ID="${GPU_ID:-0}"
SESSION_NAME="${SESSION_NAME:-beauty_corrupted_ranking_batch}"
EXPERIMENTS_CSV="${EXPERIMENTS_CSV:-full_u,text_anchor_only}"
RUN_PREFIX="${RUN_PREFIX:-beauty_corrupted}"
EMBEDDINGS_PATH="${EMBEDDINGS_PATH:-}"
EARLY_STOP_STRENGTH="${EARLY_STOP_STRENGTH:-p5}"
EARLY_STOP_PATIENCE="${EARLY_STOP_PATIENCE:-4}"
EARLY_STOP_MIN_STEP="${EARLY_STOP_MIN_STEP:-4000}"
WRITE_SNAPSHOT_CHECKPOINT="${WRITE_SNAPSHOT_CHECKPOINT:-True}"
WRITE_BEST_CHECKPOINT="${WRITE_BEST_CHECKPOINT:-True}"
INNER_RUN="${INNER_RUN:-0}"

build_experiment_list() {
  local -a experiments
  IFS=',' read -r -a experiments <<< "$EXPERIMENTS_CSV"
  printf '%s\n' "${experiments[@]}"
}

configure_experiment() {
  local experiment_name="$1"
  INJECTION_MODE="kernel"
  LOSS_WEIGHT_SCALE="1.0"
  case "$experiment_name" in
    full_u)
      AGREEMENT_WEIGHT="0.35"
      COMPLETENESS_WEIGHT="0.05"
      HISTORY_RELIABILITY_WEIGHT="0.60"
      ABLATION_MODE="none"
      ;;
    kernel_u)
      AGREEMENT_WEIGHT="0.35"
      COMPLETENESS_WEIGHT="0.05"
      HISTORY_RELIABILITY_WEIGHT="0.60"
      ABLATION_MODE="none"
      INJECTION_MODE="kernel"
      ;;
    encoder_u)
      AGREEMENT_WEIGHT="0.35"
      COMPLETENESS_WEIGHT="0.05"
      HISTORY_RELIABILITY_WEIGHT="0.60"
      ABLATION_MODE="none"
      INJECTION_MODE="encoder"
      ;;
    loss_u)
      AGREEMENT_WEIGHT="0.35"
      COMPLETENESS_WEIGHT="0.05"
      HISTORY_RELIABILITY_WEIGHT="0.60"
      ABLATION_MODE="none"
      INJECTION_MODE="loss"
      ;;
    agreement_only)
      AGREEMENT_WEIGHT="1.0"
      COMPLETENESS_WEIGHT="0.0"
      HISTORY_RELIABILITY_WEIGHT="0.0"
      ABLATION_MODE="none"
      ;;
    agreement_plus_text)
      AGREEMENT_WEIGHT="0.35"
      COMPLETENESS_WEIGHT="0.05"
      HISTORY_RELIABILITY_WEIGHT="0.0"
      ABLATION_MODE="none"
      ;;
    agreement_plus_history)
      AGREEMENT_WEIGHT="0.35"
      COMPLETENESS_WEIGHT="0.0"
      HISTORY_RELIABILITY_WEIGHT="0.60"
      ABLATION_MODE="none"
      ;;
    text_anchor_only)
      AGREEMENT_WEIGHT="0.35"
      COMPLETENESS_WEIGHT="0.05"
      HISTORY_RELIABILITY_WEIGHT="0.60"
      ABLATION_MODE="text_anchor_only"
      ;;
    global_p)
      AGREEMENT_WEIGHT="0.35"
      COMPLETENESS_WEIGHT="0.05"
      HISTORY_RELIABILITY_WEIGHT="0.60"
      ABLATION_MODE="global_p"
      ;;
    u_shuffle)
      AGREEMENT_WEIGHT="0.35"
      COMPLETENESS_WEIGHT="0.05"
      HISTORY_RELIABILITY_WEIGHT="0.60"
      ABLATION_MODE="u_shuffle"
      ;;
    *)
      echo "unknown experiment: $experiment_name" >&2
      return 1
      ;;
  esac
}

print_summary() {
  local summary_path="$1"
  SUMMARY_PATH="$summary_path" "$PYTHON_BIN" - <<'PY'
import json
import os

summary_path = os.environ["SUMMARY_PATH"]
with open(summary_path, "r", encoding="utf-8") as handle:
    payload = json.load(handle)

print(
    "SUMMARY"
    f" best_step={payload['best_step']}"
    f" best_metric={payload['best_metric']}"
    f" val_p5_ndcg10={payload['validation']['p5']['ndcg'][2]}"
    f" test_p5_ndcg10={payload['test']['p5']['ndcg'][2]}"
    f" test_p10_ndcg10={payload['test']['p10']['ndcg'][2]}"
)
PY
}

run_experiment() {
  local experiment_name="$1"
  configure_experiment "$experiment_name"

  local run_name="${RUN_PREFIX}_${experiment_name}_${EARLY_STOP_STRENGTH}"
  local run_dir="$RUN_ROOT/$run_name"
  local log_dir="$run_dir/logs"
  local log_file="$log_dir/$run_name.log"
  local summary_path="$run_dir/checkpoints-meta/Beauty/best_summary_proposal_adaptive.json"

  mkdir -p "$log_dir"

  echo "[$(date "+%F %T %Z")] START experiment=$experiment_name gpu=$GPU_ID run_dir=$run_dir embeddings=$EMBEDDINGS_PATH"
  (
    cd "$REPO_ROOT"
    "$PYTHON_BIN" -u single_train.py \
      work_dir="$run_dir" \
      cuda="$GPU_ID" \
      random_seed=100 \
      training.data=Beauty \
      data.Beauty.path="$DATASET_DIR" \
      graph.type=proposal_adaptive \
      graph.is_disliked_item=True \
      model.hidden_size=256 \
      model.cond_dim=256 \
      training.nonpreference_user_ratio=0.1 \
      optim.lr=0.0001 \
      model.score_flag=False \
      model.score_method=oricos \
      training.n_iters=2000000 \
      training.eval_freq=500 \
      training.snapshot_freq=500 \
      training.snapshot_sampling=True \
      training.early_stop_patience="$EARLY_STOP_PATIENCE" \
      training.early_stop_min_step="$EARLY_STOP_MIN_STEP" \
      training.early_stop_metric=ndcg10 \
      training.early_stop_strength="$EARLY_STOP_STRENGTH" \
      training.early_stop_min_delta=0.0 \
      +training.write_snapshot_checkpoint="$WRITE_SNAPSHOT_CHECKPOINT" \
      +training.write_best_checkpoint="$WRITE_BEST_CHECKPOINT" \
      text_side.enabled=True \
      text_side.dataset_dir="$DATASET_DIR" \
      text_side.embeddings_path="$EMBEDDINGS_PATH" \
      text_side.center_embeddings=True \
      text_side.popularity_mix_scale=0.0 \
      text_side.agreement_weight="$AGREEMENT_WEIGHT" \
      text_side.completeness_weight="$COMPLETENESS_WEIGHT" \
      text_side.history_reliability_weight="$HISTORY_RELIABILITY_WEIGHT" \
      text_side.ess_weight=0.20 \
      text_side.recency_weight=0.35 \
      text_side.stability_weight=0.45 \
      text_side.max_temperature_scale=1.4 \
      text_side.min_pseudo_mass=0.03 \
      text_side.pseudo_mass_scale=1.0 \
      text_side.pseudo_mass_power=1.0 \
      text_side.ablation_mode="$ABLATION_MODE" \
      text_side.injection_mode="$INJECTION_MODE" \
      text_side.loss_weight_scale="$LOSS_WEIGHT_SCALE"
  ) 2>&1 | tee "$log_file"

  echo "[$(date "+%F %T %Z")] FINISH experiment=$experiment_name log_file=$log_file"
  if [[ -f "$summary_path" ]]; then
    print_summary "$summary_path"
  else
    echo "SUMMARY_MISSING path=$summary_path" >&2
    return 1
  fi
}

launch_tmux_session() {
  local launcher_dir="$RUN_ROOT/$SESSION_NAME"
  local launcher_path="$launcher_dir/run_batch.sh"

  mkdir -p "$launcher_dir"

  cat > "$launcher_path" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$REPO_ROOT"
export PYTHON_BIN="$PYTHON_BIN"
export DATASET_DIR="$DATASET_DIR"
export RUN_ROOT="$RUN_ROOT"
export GPU_ID="$GPU_ID"
export SESSION_NAME="$SESSION_NAME"
export EXPERIMENTS_CSV="$EXPERIMENTS_CSV"
export RUN_PREFIX="$RUN_PREFIX"
export EMBEDDINGS_PATH="$EMBEDDINGS_PATH"
export EARLY_STOP_STRENGTH="$EARLY_STOP_STRENGTH"
export EARLY_STOP_PATIENCE="$EARLY_STOP_PATIENCE"
export EARLY_STOP_MIN_STEP="$EARLY_STOP_MIN_STEP"
export WRITE_SNAPSHOT_CHECKPOINT="$WRITE_SNAPSHOT_CHECKPOINT"
export WRITE_BEST_CHECKPOINT="$WRITE_BEST_CHECKPOINT"
export INNER_RUN=1
bash "$REPO_ROOT/scripts/run_beauty_corrupted_ranking_batch.sh" "$REPO_ROOT"
EOF

  chmod +x "$launcher_path"

  if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    tmux kill-session -t "$SESSION_NAME"
  fi
  tmux new-session -d -s "$SESSION_NAME" "bash $launcher_path"

  echo "LAUNCHED session=$SESSION_NAME gpu=$GPU_ID launcher=$launcher_path"
  tmux list-sessions | grep "$SESSION_NAME" || true
}

main() {
  if [[ -z "$EMBEDDINGS_PATH" ]]; then
    echo "EMBEDDINGS_PATH must be set" >&2
    exit 1
  fi
  if [[ ! -f "$EMBEDDINGS_PATH" ]]; then
    echo "missing embeddings file: $EMBEDDINGS_PATH" >&2
    exit 1
  fi

  if [[ "$INNER_RUN" != "1" ]]; then
    launch_tmux_session
    exit 0
  fi

  local experiment_name
  while IFS= read -r experiment_name; do
    [[ -n "$experiment_name" ]] || continue
    run_experiment "$experiment_name"
  done < <(build_experiment_list)
}

main "$@"
