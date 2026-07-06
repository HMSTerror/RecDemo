#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="${1:-/data/Zijian/goal/RecDemo}"
shift || true

PYTHON_BIN="${PYTHON_BIN:-/data/Zijian/goal/PreferGrow/.venv/bin/python}"
DATASET_ROOT="${DATASET_ROOT:-$REPO_ROOT/dataset/paper_raw_v1}"
RUN_ROOT="${RUN_ROOT:-/data/Zijian/goal/RecDemoRuns/main_table_text_side}"
MODEL_PATH="${MODEL_PATH:-/data/models/sentence-transformers/sentence-t5-xl}"
REPO_GIT_HEAD="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || true)"
GPU_IDS_CSV="${GPU_IDS_CSV:-0,1}"
SESSION_PREFIX="${SESSION_PREFIX:-textside_main_table}"
INNER_RUN="${INNER_RUN:-0}"
DATASETS_CSV="${DATASETS_CSV:-}"
FORCE="${FORCE:-0}"
SKIP_EXISTING="${SKIP_EXISTING:-1}"
DRY_RUN="${DRY_RUN:-0}"
REQUIRE_SUMMARY="${REQUIRE_SUMMARY:-1}"

TRAINING_N_ITERS="${TRAINING_N_ITERS:-2000000}"
TRAINING_BATCH_SIZE="${TRAINING_BATCH_SIZE:-256}"
EVAL_BATCH_SIZE="${EVAL_BATCH_SIZE:-256}"
TRAINING_EVAL_FREQ="${TRAINING_EVAL_FREQ:-1000}"
TRAINING_SNAPSHOT_FREQ="${TRAINING_SNAPSHOT_FREQ:-1000}"
TRAINING_SNAPSHOT_PREEMPT_FREQ="${TRAINING_SNAPSHOT_PREEMPT_FREQ:-1000}"
TRAINING_SNAPSHOT_SAMPLING="${TRAINING_SNAPSHOT_SAMPLING:-True}"
EARLY_STOP_PATIENCE="${EARLY_STOP_PATIENCE:-5}"
EARLY_STOP_MIN_STEP="${EARLY_STOP_MIN_STEP:-5000}"
EARLY_STOP_METRIC="${EARLY_STOP_METRIC:-ndcg10}"
EARLY_STOP_STRENGTH="${EARLY_STOP_STRENGTH:-p5}"
EARLY_STOP_MIN_DELTA="${EARLY_STOP_MIN_DELTA:-0.0}"
WRITE_SNAPSHOT_CHECKPOINT="${WRITE_SNAPSHOT_CHECKPOINT:-False}"
WRITE_BEST_CHECKPOINT="${WRITE_BEST_CHECKPOINT:-True}"

TEXT_KERNEL_VERSION="${TEXT_KERNEL_VERSION:-v2}"
TEXT_TEMPERATURE="${TEXT_TEMPERATURE:-0.2}"
TEXT_G_MAX="${TEXT_G_MAX:-0.5}"
TEXT_AGREEMENT_K="${TEXT_AGREEMENT_K:-2.0}"
TEXT_UTILITY_REPORT_PATH="${TEXT_UTILITY_REPORT_PATH:-$REPO_ROOT/docs/reports/data/2026-07-02-gate0/gate0_text_utility_report.json}"

TEXT_AGREEMENT_WEIGHT="${TEXT_AGREEMENT_WEIGHT:-0.45}"
TEXT_COMPLETENESS_WEIGHT="${TEXT_COMPLETENESS_WEIGHT:-0.15}"
TEXT_HISTORY_RELIABILITY_WEIGHT="${TEXT_HISTORY_RELIABILITY_WEIGHT:-0.40}"
TEXT_ESS_WEIGHT="${TEXT_ESS_WEIGHT:-0.20}"
TEXT_RECENCY_WEIGHT="${TEXT_RECENCY_WEIGHT:-0.30}"
TEXT_STABILITY_WEIGHT="${TEXT_STABILITY_WEIGHT:-0.50}"
TEXT_MAX_TEMPERATURE_SCALE="${TEXT_MAX_TEMPERATURE_SCALE:-2.0}"
TEXT_MIN_PSEUDO_MASS="${TEXT_MIN_PSEUDO_MASS:-0.05}"
TEXT_POPULARITY_MIX_SCALE="${TEXT_POPULARITY_MIX_SCALE:-1.0}"
TEXT_POPULARITY_MIX_POWER="${TEXT_POPULARITY_MIX_POWER:-1.0}"
TEXT_PSEUDO_MASS_SCALE="${TEXT_PSEUDO_MASS_SCALE:-1.0}"
TEXT_PSEUDO_MASS_POWER="${TEXT_PSEUDO_MASS_POWER:-1.0}"
TEXT_CENTER_EMBEDDINGS="${TEXT_CENTER_EMBEDDINGS:-False}"
TEXT_ABLATION_MODE="${TEXT_ABLATION_MODE:-none}"
TEXT_INJECTION_MODE="${TEXT_INJECTION_MODE:-kernel}"


dataset_list() {
  local -a datasets
  if [[ -n "$DATASETS_CSV" ]]; then
    IFS=',' read -r -a datasets <<< "$DATASETS_CSV"
  elif [[ "$#" -gt 0 ]]; then
    datasets=("$@")
  else
    datasets=(Steam ML1M Beauty ATG)
  fi
  printf '%s\n' "${datasets[@]}"
}


configure_dataset() {
  local dataset="$1"
  case "$dataset" in
    Steam)
      NONPREFERENCE_USER_RATIO="0.05"
      LEARNING_RATE="0.001"
      SCORE_FLAG="False"
      SCORE_METHOD="oricos"
      ;;
    ML1M)
      NONPREFERENCE_USER_RATIO="0.1"
      LEARNING_RATE="0.0001"
      SCORE_FLAG="True"
      SCORE_METHOD="oricos"
      ;;
    Beauty)
      NONPREFERENCE_USER_RATIO="0.1"
      LEARNING_RATE="0.0001"
      SCORE_FLAG="False"
      SCORE_METHOD="oricos"
      ;;
    ATG)
      NONPREFERENCE_USER_RATIO="0.2"
      LEARNING_RATE="0.001"
      SCORE_FLAG="True"
      SCORE_METHOD="oricos"
      ;;
    ASO)
      NONPREFERENCE_USER_RATIO="0.2"
      LEARNING_RATE="0.001"
      SCORE_FLAG="True"
      SCORE_METHOD="oricos"
      ;;
    *)
      echo "unknown dataset: $dataset" >&2
      return 1
      ;;
  esac
}


summary_path_for() {
  local dataset="$1"
  local run_dir="$2"
  echo "$run_dir/checkpoints-meta/$dataset/best_summary_proposal_adaptive.json"
}


slugify_variant() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '_'
}


run_variant_label() {
  local label="mainpath"
  if [[ "$TEXT_ABLATION_MODE" != "none" ]]; then
    label="ablation_$(slugify_variant "$TEXT_ABLATION_MODE")"
  fi
  if [[ "$TEXT_INJECTION_MODE" != "kernel" ]]; then
    local injection_label="injection_$(slugify_variant "$TEXT_INJECTION_MODE")"
    if [[ "$label" == "mainpath" ]]; then
      label="$injection_label"
    else
      label="${label}_${injection_label}"
    fi
  fi
  echo "$label"
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
    f" val_p2_ndcg10={payload['validation']['p2']['ndcg'][2]}"
    f" test_p2_ndcg10={payload['test']['p2']['ndcg'][2]}"
    f" test_p5_ndcg10={payload['test']['p5']['ndcg'][2]}"
)
PY
}


build_embeddings_if_missing() {
  local dataset_dir="$1"
  local embeddings_path="$dataset_dir/sentence_t5_xl_item_emb.pt"
  if [[ -f "$embeddings_path" ]]; then
    return 0
  fi
  "$PYTHON_BIN" "$REPO_ROOT/scripts/build_text_side_embeddings.py" \
    --dataset-dir "$dataset_dir" \
    --model-path "$MODEL_PATH" \
    --device "cuda:$GPU_ID"
}


build_null_curve_if_missing() {
  local dataset_dir="$1"
  local embeddings_path="$dataset_dir/sentence_t5_xl_item_emb.pt"
  local null_curve_path="$dataset_dir/agreement_null_curves.json"
  if [[ -f "$null_curve_path" ]]; then
    return 0
  fi
  local -a args
  args=(
    "$PYTHON_BIN" "$REPO_ROOT/scripts/build_agreement_null_curves.py"
    --dataset-dir "$dataset_dir"
    --embeddings-path "$embeddings_path"
    --text-utility-report-path "$TEXT_UTILITY_REPORT_PATH"
    --agreement-k "$TEXT_AGREEMENT_K"
  )
  if [[ "$TEXT_CENTER_EMBEDDINGS" == "True" ]]; then
    args+=(--center-embeddings)
  fi
  "${args[@]}"
}


write_run_manifest() {
  local dataset="$1"
  local dataset_dir="$2"
  local run_dir="$3"
  local embeddings_path="$dataset_dir/sentence_t5_xl_item_emb.pt"
  local text_bank_path="$dataset_dir/text_bank.csv"
  local null_curve_path="$dataset_dir/agreement_null_curves.json"
  local manifest_dir="$run_dir/checkpoints-meta/$dataset"
  local manifest_path="$manifest_dir/frozen_run_manifest.json"

  mkdir -p "$manifest_dir"
  DATASET_NAME="$dataset" \
  DATASET_DIR="$dataset_dir" \
  EMBEDDINGS_PATH="$embeddings_path" \
  TEXT_BANK_PATH="$text_bank_path" \
  NULL_CURVE_PATH="$null_curve_path" \
  UTILITY_REPORT_PATH="$TEXT_UTILITY_REPORT_PATH" \
  MANIFEST_PATH="$manifest_path" \
  REPO_ROOT_PATH="$REPO_ROOT" \
  REPO_GIT_HEAD="$REPO_GIT_HEAD" \
  RUN_DIR="$run_dir" \
  RANDOM_SEED="100" \
  "$PYTHON_BIN" - <<'PY'
import hashlib
import json
import os
from pathlib import Path


def sha256_paths(*paths: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


dataset_name = os.environ["DATASET_NAME"]
dataset_dir = Path(os.environ["DATASET_DIR"])
embeddings_path = Path(os.environ["EMBEDDINGS_PATH"])
text_bank_path = Path(os.environ["TEXT_BANK_PATH"])
null_curve_path = Path(os.environ["NULL_CURVE_PATH"])
utility_report_path = Path(os.environ["UTILITY_REPORT_PATH"])
manifest_path = Path(os.environ["MANIFEST_PATH"])
run_dir = Path(os.environ["RUN_DIR"])

bank_hash = sha256_paths(text_bank_path, embeddings_path)
split_hash = sha256_paths(dataset_dir / "train_data.df")
utility_report_hash = hashlib.sha256(utility_report_path.read_bytes()).hexdigest()
utility_payload = json.loads(utility_report_path.read_text(encoding="utf-8"))
dataset_row = next(row for row in utility_payload["datasets"] if str(row["dataset"]) == dataset_name)

if str(dataset_row["bank_hash"]) != bank_hash:
    raise ValueError(
        f"bank hash mismatch for {dataset_name}: utility report has {dataset_row['bank_hash']} vs local {bank_hash}"
    )
if str(dataset_row["split_hash"]) != split_hash:
    raise ValueError(
        f"split hash mismatch for {dataset_name}: utility report has {dataset_row['split_hash']} vs local {split_hash}"
    )

manifest = {
    "provenance": {
        "repo_root": str(Path(os.environ["REPO_ROOT_PATH"]).resolve()),
        "git_head": os.environ.get("REPO_GIT_HEAD", ""),
    },
    "dataset": dataset_name,
    "run_dir": str(run_dir),
    "random_seed": int(os.environ["RANDOM_SEED"]),
    "dataset_dir": str(dataset_dir),
    "bank_hash": bank_hash,
    "null_curve_hash": hashlib.sha256(null_curve_path.read_bytes()).hexdigest(),
    "u_ds_artifact_path": str(utility_report_path),
    "u_ds_artifact_hash": utility_report_hash,
    "u_ds_popularity": float(dataset_row["u_ds_popularity"]),
    "phi_u_ds": float(dataset_row["phi_u_ds"]),
    "split_hash": split_hash,
    "frozen_config": {
        "kernel_version": os.environ["TEXT_KERNEL_VERSION"],
        "temperature": float(os.environ["TEXT_TEMPERATURE"]),
        "g_max": float(os.environ["TEXT_G_MAX"]),
        "agreement_k": float(os.environ["TEXT_AGREEMENT_K"]),
        "agreement_weight": float(os.environ["TEXT_AGREEMENT_WEIGHT"]),
        "completeness_weight": float(os.environ["TEXT_COMPLETENESS_WEIGHT"]),
        "history_reliability_weight": float(os.environ["TEXT_HISTORY_RELIABILITY_WEIGHT"]),
        "ess_weight": float(os.environ["TEXT_ESS_WEIGHT"]),
        "recency_weight": float(os.environ["TEXT_RECENCY_WEIGHT"]),
        "stability_weight": float(os.environ["TEXT_STABILITY_WEIGHT"]),
        "max_temperature_scale": float(os.environ["TEXT_MAX_TEMPERATURE_SCALE"]),
        "min_pseudo_mass": float(os.environ["TEXT_MIN_PSEUDO_MASS"]),
        "popularity_mix_scale": float(os.environ["TEXT_POPULARITY_MIX_SCALE"]),
        "popularity_mix_power": float(os.environ["TEXT_POPULARITY_MIX_POWER"]),
        "pseudo_mass_scale": float(os.environ["TEXT_PSEUDO_MASS_SCALE"]),
        "pseudo_mass_power": float(os.environ["TEXT_PSEUDO_MASS_POWER"]),
        "center_embeddings": os.environ["TEXT_CENTER_EMBEDDINGS"] == "True",
        "ablation_mode": os.environ["TEXT_ABLATION_MODE"],
        "injection_mode": os.environ["TEXT_INJECTION_MODE"],
        "write_snapshot_checkpoint": os.environ["WRITE_SNAPSHOT_CHECKPOINT"] == "True",
        "write_best_checkpoint": os.environ["WRITE_BEST_CHECKPOINT"] == "True",
        "early_stop_metric": os.environ["EARLY_STOP_METRIC"],
        "early_stop_strength": os.environ["EARLY_STOP_STRENGTH"],
    },
}
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"MANIFEST {manifest_path}")
PY
}


run_dataset() {
  local dataset="$1"
  configure_dataset "$dataset"

  local dataset_dir="$DATASET_ROOT/$dataset"
  local embeddings_path="$dataset_dir/sentence_t5_xl_item_emb.pt"
  local null_curve_path="$dataset_dir/agreement_null_curves.json"
  local run_variant
  run_variant="$(run_variant_label)"
  local run_name="${dataset,,}_proposal_adaptive_${run_variant}"
  local run_dir="$RUN_ROOT/$run_name"
  local summary_path
  summary_path="$(summary_path_for "$dataset" "$run_dir")"
  local log_dir="$run_dir/logs"
  local log_file="$log_dir/${run_name}.log"

  if [[ ! -d "$dataset_dir" ]]; then
    echo "SKIP dataset=$dataset reason=missing_dataset_dir path=$dataset_dir" >&2
    return 1
  fi
  if [[ ! -f "$TEXT_UTILITY_REPORT_PATH" ]]; then
    echo "SKIP dataset=$dataset reason=missing_text_utility_report path=$TEXT_UTILITY_REPORT_PATH" >&2
    return 1
  fi
  if [[ "$SKIP_EXISTING" == "1" && "$FORCE" != "1" && -f "$summary_path" ]]; then
    echo "SKIP dataset=$dataset reason=existing_summary path=$summary_path"
    print_summary "$summary_path"
    return 0
  fi

  mkdir -p "$log_dir"
  if [[ "$FORCE" == "1" ]]; then
    rm -rf "$run_dir/checkpoints" "$run_dir/checkpoints-meta"
  fi

  build_embeddings_if_missing "$dataset_dir"
  build_null_curve_if_missing "$dataset_dir"
  if [[ ! -f "$embeddings_path" || ! -f "$null_curve_path" ]]; then
    echo "SKIP dataset=$dataset reason=missing_supporting_artifact embeddings=$embeddings_path null_curve=$null_curve_path" >&2
    return 1
  fi
  write_run_manifest "$dataset" "$dataset_dir" "$run_dir"

  echo "[$(date "+%F %T %Z")] START dataset=$dataset gpu=$GPU_ID run_dir=$run_dir embeddings=$embeddings_path"
  (
    mkdir -p "$run_dir"
    cd "$run_dir"
    "$PYTHON_BIN" -u "$REPO_ROOT/single_train.py" \
      work_dir="$run_dir" \
      cuda="$GPU_ID" \
      random_seed=100 \
      training.data="$dataset" \
      data."$dataset".path="$dataset_dir" \
      graph.type=proposal_adaptive \
      graph.is_disliked_item=True \
      model.hidden_size=256 \
      model.cond_dim=256 \
      training.nonpreference_user_ratio="$NONPREFERENCE_USER_RATIO" \
      optim.lr="$LEARNING_RATE" \
      model.score_flag="$SCORE_FLAG" \
      loss_type=score_entropy \
      model.score_method="$SCORE_METHOD" \
      training.batch_size="$TRAINING_BATCH_SIZE" \
      eval.batch_size="$EVAL_BATCH_SIZE" \
      training.n_iters="$TRAINING_N_ITERS" \
      training.eval_freq="$TRAINING_EVAL_FREQ" \
      training.snapshot_freq="$TRAINING_SNAPSHOT_FREQ" \
      training.snapshot_freq_for_preemption="$TRAINING_SNAPSHOT_PREEMPT_FREQ" \
      training.snapshot_sampling="$TRAINING_SNAPSHOT_SAMPLING" \
      training.early_stop_patience="$EARLY_STOP_PATIENCE" \
      training.early_stop_min_step="$EARLY_STOP_MIN_STEP" \
      training.early_stop_metric="$EARLY_STOP_METRIC" \
      training.early_stop_strength="$EARLY_STOP_STRENGTH" \
      training.early_stop_min_delta="$EARLY_STOP_MIN_DELTA" \
      +training.write_snapshot_checkpoint="$WRITE_SNAPSHOT_CHECKPOINT" \
      +training.write_best_checkpoint="$WRITE_BEST_CHECKPOINT" \
      text_side.enabled=True \
      text_side.dataset_dir="$dataset_dir" \
      text_side.text_bank_path="$dataset_dir/text_bank.csv" \
      text_side.embeddings_path="$embeddings_path" \
      text_side.temperature="$TEXT_TEMPERATURE" \
      text_side.kernel_version="$TEXT_KERNEL_VERSION" \
      text_side.g_max="$TEXT_G_MAX" \
      text_side.agreement_null_curve_path="$null_curve_path" \
      text_side.text_utility_report_path="$TEXT_UTILITY_REPORT_PATH" \
      text_side.agreement_k="$TEXT_AGREEMENT_K" \
      text_side.center_embeddings="$TEXT_CENTER_EMBEDDINGS" \
      text_side.popularity_mix_scale="$TEXT_POPULARITY_MIX_SCALE" \
      text_side.popularity_mix_power="$TEXT_POPULARITY_MIX_POWER" \
      text_side.agreement_weight="$TEXT_AGREEMENT_WEIGHT" \
      text_side.completeness_weight="$TEXT_COMPLETENESS_WEIGHT" \
      text_side.history_reliability_weight="$TEXT_HISTORY_RELIABILITY_WEIGHT" \
      text_side.ess_weight="$TEXT_ESS_WEIGHT" \
      text_side.recency_weight="$TEXT_RECENCY_WEIGHT" \
      text_side.stability_weight="$TEXT_STABILITY_WEIGHT" \
      text_side.max_temperature_scale="$TEXT_MAX_TEMPERATURE_SCALE" \
      text_side.min_pseudo_mass="$TEXT_MIN_PSEUDO_MASS" \
      text_side.pseudo_mass_scale="$TEXT_PSEUDO_MASS_SCALE" \
      text_side.pseudo_mass_power="$TEXT_PSEUDO_MASS_POWER" \
      text_side.ablation_mode="$TEXT_ABLATION_MODE" \
      text_side.injection_mode="$TEXT_INJECTION_MODE"
  ) 2>&1 | tee "$log_file"

  echo "[$(date "+%F %T %Z")] FINISH dataset=$dataset log_file=$log_file"
  if [[ -f "$summary_path" ]]; then
    print_summary "$summary_path"
  elif [[ "$REQUIRE_SUMMARY" != "1" ]]; then
    echo "SUMMARY_OPTIONAL_MISSING dataset=$dataset path=$summary_path"
  else
    echo "SUMMARY_MISSING dataset=$dataset path=$summary_path" >&2
    return 1
  fi
}


launch_tmux_batches() {
  local -a datasets gpu_ids gpu_batches
  mapfile -t datasets < <(dataset_list "$@")
  IFS=',' read -r -a gpu_ids <<< "$GPU_IDS_CSV"
  if [[ "${#gpu_ids[@]}" -eq 0 ]]; then
    echo "GPU_IDS_CSV produced no GPU ids" >&2
    exit 1
  fi

  local gpu_count="${#gpu_ids[@]}"
  local i dataset batch_index launcher_dir launcher_path session_name gpu_id
  for ((i = 0; i < gpu_count; i++)); do
    gpu_batches[i]=""
  done

  for ((i = 0; i < ${#datasets[@]}; i++)); do
    dataset="${datasets[i]}"
    batch_index=$((i % gpu_count))
    gpu_batches[batch_index]="${gpu_batches[batch_index]}${gpu_batches[batch_index]:+,}$dataset"
  done

  for ((i = 0; i < gpu_count; i++)); do
    if [[ -z "${gpu_batches[i]}" ]]; then
      continue
    fi
    gpu_id="${gpu_ids[i]}"
    session_name="${SESSION_PREFIX}_gpu${gpu_id}"
    launcher_dir="$RUN_ROOT/$session_name"
    launcher_path="$launcher_dir/run_batch.sh"
    mkdir -p "$launcher_dir"
    cat > "$launcher_path" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$REPO_ROOT"
export PYTHON_BIN="$PYTHON_BIN"
export DATASET_ROOT="$DATASET_ROOT"
export RUN_ROOT="$RUN_ROOT"
export GPU_IDS_CSV="$gpu_id"
export SESSION_PREFIX="$SESSION_PREFIX"
export INNER_RUN=1
export DATASETS_CSV="${gpu_batches[i]}"
export FORCE="$FORCE"
export SKIP_EXISTING="$SKIP_EXISTING"
export DRY_RUN="$DRY_RUN"
export REQUIRE_SUMMARY="$REQUIRE_SUMMARY"
export TRAINING_N_ITERS="$TRAINING_N_ITERS"
export TRAINING_BATCH_SIZE="$TRAINING_BATCH_SIZE"
export EVAL_BATCH_SIZE="$EVAL_BATCH_SIZE"
export TRAINING_EVAL_FREQ="$TRAINING_EVAL_FREQ"
export TRAINING_SNAPSHOT_FREQ="$TRAINING_SNAPSHOT_FREQ"
export TRAINING_SNAPSHOT_PREEMPT_FREQ="$TRAINING_SNAPSHOT_PREEMPT_FREQ"
export TRAINING_SNAPSHOT_SAMPLING="$TRAINING_SNAPSHOT_SAMPLING"
export EARLY_STOP_PATIENCE="$EARLY_STOP_PATIENCE"
export EARLY_STOP_MIN_STEP="$EARLY_STOP_MIN_STEP"
export EARLY_STOP_METRIC="$EARLY_STOP_METRIC"
export EARLY_STOP_STRENGTH="$EARLY_STOP_STRENGTH"
export EARLY_STOP_MIN_DELTA="$EARLY_STOP_MIN_DELTA"
export WRITE_SNAPSHOT_CHECKPOINT="$WRITE_SNAPSHOT_CHECKPOINT"
export WRITE_BEST_CHECKPOINT="$WRITE_BEST_CHECKPOINT"
export MODEL_PATH="$MODEL_PATH"
export TEXT_KERNEL_VERSION="$TEXT_KERNEL_VERSION"
export TEXT_TEMPERATURE="$TEXT_TEMPERATURE"
export TEXT_G_MAX="$TEXT_G_MAX"
export TEXT_AGREEMENT_K="$TEXT_AGREEMENT_K"
export TEXT_UTILITY_REPORT_PATH="$TEXT_UTILITY_REPORT_PATH"
export TEXT_AGREEMENT_WEIGHT="$TEXT_AGREEMENT_WEIGHT"
export TEXT_COMPLETENESS_WEIGHT="$TEXT_COMPLETENESS_WEIGHT"
export TEXT_HISTORY_RELIABILITY_WEIGHT="$TEXT_HISTORY_RELIABILITY_WEIGHT"
export TEXT_ESS_WEIGHT="$TEXT_ESS_WEIGHT"
export TEXT_RECENCY_WEIGHT="$TEXT_RECENCY_WEIGHT"
export TEXT_STABILITY_WEIGHT="$TEXT_STABILITY_WEIGHT"
export TEXT_MAX_TEMPERATURE_SCALE="$TEXT_MAX_TEMPERATURE_SCALE"
export TEXT_MIN_PSEUDO_MASS="$TEXT_MIN_PSEUDO_MASS"
export TEXT_POPULARITY_MIX_SCALE="$TEXT_POPULARITY_MIX_SCALE"
export TEXT_POPULARITY_MIX_POWER="$TEXT_POPULARITY_MIX_POWER"
export TEXT_PSEUDO_MASS_SCALE="$TEXT_PSEUDO_MASS_SCALE"
export TEXT_PSEUDO_MASS_POWER="$TEXT_PSEUDO_MASS_POWER"
export TEXT_CENTER_EMBEDDINGS="$TEXT_CENTER_EMBEDDINGS"
export TEXT_ABLATION_MODE="$TEXT_ABLATION_MODE"
export TEXT_INJECTION_MODE="$TEXT_INJECTION_MODE"
bash "$REPO_ROOT/scripts/run_text_side_main_table_tmux.sh" "$REPO_ROOT"
EOF
    chmod +x "$launcher_path"

    if [[ "$DRY_RUN" == "1" ]]; then
      echo "DRY_RUN session=$session_name gpu=$gpu_id datasets=${gpu_batches[i]} launcher=$launcher_path"
      continue
    fi

    tmux has-session -t "$session_name" 2>/dev/null && tmux kill-session -t "$session_name"
    tmux new-session -d -s "$session_name" "bash $launcher_path"
    echo "LAUNCHED session=$session_name gpu=$gpu_id datasets=${gpu_batches[i]} launcher=$launcher_path"
  done

  tmux list-sessions | grep "$SESSION_PREFIX" || true
}


main() {
  if [[ "$INNER_RUN" != "1" ]]; then
    launch_tmux_batches "$@"
    exit 0
  fi

  local -a datasets gpu_ids
  mapfile -t datasets < <(dataset_list "$@")
  IFS=',' read -r -a gpu_ids <<< "$GPU_IDS_CSV"
  GPU_ID="${gpu_ids[0]}"

  local dataset
  for dataset in "${datasets[@]}"; do
    run_dataset "$dataset"
  done
}


main "$@"
