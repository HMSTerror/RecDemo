#!/usr/bin/env bash
set -euo pipefail

SHARD="${1:?usage: run_e0_fulltail_matrix.sh <0|1> <gpu-index>}"
GPU_INDEX="${2:?usage: run_e0_fulltail_matrix.sh <0|1> <gpu-index>}"
EXPECTED_CODE_REVISION="5709c6283cb127d727f6b769d8409343f4aae824"
CODE_ROOT="${CODE_ROOT:-/data/Zijian/goal/RecDemo_clean_aaai27_e0_5709c62}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/data/Zijian/goal/RecDemoRuns/aaai27_e0_fulltail_20260710}"
PYTHON_BIN="${PYTHON_BIN:-/data/Zijian/goal/PreferGrow/.venv/bin/python}"

actual_revision="$(git -C "$CODE_ROOT" rev-parse HEAD)"
if ! git -C "$CODE_ROOT" merge-base --is-ancestor "$EXPECTED_CODE_REVISION" "$actual_revision"; then
  echo "E0_EVALUATOR_REVISION_MISSING required_ancestor=$EXPECTED_CODE_REVISION actual=$actual_revision" >&2
  exit 2
fi
if [[ -n "$(git -C "$CODE_ROOT" status --short)" ]]; then
  echo "E0_CODE_ROOT_DIRTY root=$CODE_ROOT" >&2
  exit 3
fi

export CUDA_VISIBLE_DEVICES="$GPU_INDEX"
mkdir -p "$OUTPUT_ROOT/logs"
exec > >(tee -a "$OUTPUT_ROOT/logs/e0_shard${SHARD}_gpu${GPU_INDEX}.log") 2>&1

echo "E0_SHARD_START shard=$SHARD gpu=$GPU_INDEX code_revision=$actual_revision"
nvidia-smi --query-gpu=index,name,memory.used,utilization.gpu --format=csv,noheader

run_core() {
  local identifier="$1"
  local dataset="$2"
  local dataset_dir="$3"
  local log_path="$4"
  local summary_path="$5"
  local checkpoint_path="$6"
  local expected_rows="$7"
  local manifest_path="$8"
  local output_dir="$OUTPUT_ROOT/final/$identifier"
  local args=(
    "$PYTHON_BIN" "$CODE_ROOT/scripts/evaluate_frozen_checkpoint.py"
    --method-id "$identifier"
    --dataset-name "$dataset"
    --dataset-dir "$dataset_dir"
    --log-path "$log_path"
    --summary-path "$summary_path"
    --checkpoint-path "$checkpoint_path"
    --output-dir "$output_dir"
    --expected-test-rows "$expected_rows"
    --random-seed 100
    --eval-seed 100
    --strength p2
    --device cuda:0
  )
  if [[ "$manifest_path" != "-" ]]; then
    args+=(--manifest-path "$manifest_path")
  fi
  echo "E0_ITEM_START id=$identifier dataset=$dataset family=core"
  "${args[@]}"
  echo "E0_ITEM_FINISH id=$identifier dataset=$dataset family=core"
}

run_diff() {
  local identifier="$1"
  local dataset="$2"
  local manifest_path="$3"
  local checkpoint_path="$4"
  local expected_rows="$5"
  local output_dir="$OUTPUT_ROOT/final/$identifier"
  echo "E0_ITEM_START id=$identifier dataset=$dataset family=diffurec"
  "$PYTHON_BIN" "$CODE_ROOT/scripts/evaluate_frozen_diffurec.py" \
    --dataset-name "$dataset" \
    --manifest-path "$manifest_path" \
    --checkpoint-path "$checkpoint_path" \
    --output-dir "$output_dir" \
    --expected-test-rows "$expected_rows" \
    --random-seed 100 \
    --eval-seed 100 \
    --device cuda:0
  echo "E0_ITEM_FINISH id=$identifier dataset=$dataset family=diffurec"
}

case "$SHARD" in
  0)
    run_core host_beauty Beauty /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Beauty /data/Zijian/goal/RecDemo/logs/beauty_adaptive_earlystop.log /data/Zijian/goal/RecDemo/checkpoints-meta/Beauty/best_summary_adaptive.json /data/Zijian/goal/RecDemo/checkpoints-meta/Beauty/checkpoint_adaptive_best.pth 2237 -
    run_diff diffurec_steam Steam /data/Zijian/goal/RecDemoRuns/close04_diffurec/steam_diffurec_seed100/checkpoints-meta/Steam/diffurec_run_manifest.json /data/Zijian/goal/RecDemoRuns/close04_diffurec/steam_diffurec_seed100/checkpoints-meta/Steam/checkpoint_diffurec_best.pt 80651
    run_core host_steam Steam /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Steam /data/Zijian/goal/RecDemo/logs/steam_adaptive_earlystop.log /data/Zijian/goal/RecDemo/checkpoints-meta/Steam/best_summary_adaptive.json /data/Zijian/goal/RecDemo/checkpoints-meta/Steam/checkpoint_adaptive_best.pth 80651 -
    run_core ours_full_steam Steam /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Steam /data/Zijian/goal/RecDemoRuns/main_table_text_side/steam_proposal_adaptive_mainpath/logs/steam_proposal_adaptive_mainpath.log /data/Zijian/goal/RecDemoRuns/main_table_text_side/steam_proposal_adaptive_mainpath/checkpoints-meta/Steam/best_summary_proposal_adaptive.json /data/Zijian/goal/RecDemoRuns/main_table_text_side/steam_proposal_adaptive_mainpath/checkpoints-meta/Steam/checkpoint_proposal_adaptive_best.pth 80651 /data/Zijian/goal/RecDemoRuns/main_table_text_side/steam_proposal_adaptive_mainpath/checkpoints-meta/Steam/frozen_run_manifest.json
    run_core global_p_steam Steam /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Steam /data/Zijian/goal/RecDemoRuns/main_table_text_side/steam_proposal_adaptive_ablation_global_p/logs/steam_proposal_adaptive_ablation_global_p.log /data/Zijian/goal/RecDemoRuns/main_table_text_side/steam_proposal_adaptive_ablation_global_p/checkpoints-meta/Steam/best_summary_proposal_adaptive.json /data/Zijian/goal/RecDemoRuns/main_table_text_side/steam_proposal_adaptive_ablation_global_p/checkpoints-meta/Steam/checkpoint_proposal_adaptive_best.pth 80651 /data/Zijian/goal/RecDemoRuns/main_table_text_side/steam_proposal_adaptive_ablation_global_p/checkpoints-meta/Steam/frozen_run_manifest.json
    run_core u_shuffle_steam Steam /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Steam /data/Zijian/goal/RecDemoRuns/main_table_text_side/steam_proposal_adaptive_ablation_u_shuffle/logs/steam_proposal_adaptive_ablation_u_shuffle.log /data/Zijian/goal/RecDemoRuns/main_table_text_side/steam_proposal_adaptive_ablation_u_shuffle/checkpoints-meta/Steam/best_summary_proposal_adaptive.json /data/Zijian/goal/RecDemoRuns/main_table_text_side/steam_proposal_adaptive_ablation_u_shuffle/checkpoints-meta/Steam/checkpoint_proposal_adaptive_best.pth 80651 /data/Zijian/goal/RecDemoRuns/main_table_text_side/steam_proposal_adaptive_ablation_u_shuffle/checkpoints-meta/Steam/frozen_run_manifest.json
    run_core text_anchor_only_steam Steam /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Steam /data/Zijian/goal/RecDemoRuns/main_table_text_side/steam_proposal_adaptive_ablation_text_anchor_only/logs/steam_proposal_adaptive_ablation_text_anchor_only.log /data/Zijian/goal/RecDemoRuns/main_table_text_side/steam_proposal_adaptive_ablation_text_anchor_only/checkpoints-meta/Steam/best_summary_proposal_adaptive.json /data/Zijian/goal/RecDemoRuns/main_table_text_side/steam_proposal_adaptive_ablation_text_anchor_only/checkpoints-meta/Steam/checkpoint_proposal_adaptive_best.pth 80651 /data/Zijian/goal/RecDemoRuns/main_table_text_side/steam_proposal_adaptive_ablation_text_anchor_only/checkpoints-meta/Steam/frozen_run_manifest.json
    run_core ours_full_beauty Beauty /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Beauty /data/Zijian/goal/RecDemoRuns/main_table_text_side/beauty_proposal_adaptive_mainpath/logs/beauty_proposal_adaptive_mainpath.log /data/Zijian/goal/RecDemoRuns/main_table_text_side/beauty_proposal_adaptive_mainpath/checkpoints-meta/Beauty/best_summary_proposal_adaptive.json /data/Zijian/goal/RecDemoRuns/main_table_text_side/beauty_proposal_adaptive_mainpath/checkpoints-meta/Beauty/checkpoint_proposal_adaptive_best.pth 2237 /data/Zijian/goal/RecDemoRuns/main_table_text_side/beauty_proposal_adaptive_mainpath/checkpoints-meta/Beauty/frozen_run_manifest.json
    run_core global_p_beauty Beauty /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Beauty /data/Zijian/goal/RecDemoRuns/main_table_text_side/beauty_proposal_adaptive_ablation_global_p/logs/beauty_proposal_adaptive_ablation_global_p.log /data/Zijian/goal/RecDemoRuns/main_table_text_side/beauty_proposal_adaptive_ablation_global_p/checkpoints-meta/Beauty/best_summary_proposal_adaptive.json /data/Zijian/goal/RecDemoRuns/main_table_text_side/beauty_proposal_adaptive_ablation_global_p/checkpoints-meta/Beauty/checkpoint_proposal_adaptive_best.pth 2237 /data/Zijian/goal/RecDemoRuns/main_table_text_side/beauty_proposal_adaptive_ablation_global_p/checkpoints-meta/Beauty/frozen_run_manifest.json
    run_core u_shuffle_beauty Beauty /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Beauty /data/Zijian/goal/RecDemoRuns/main_table_text_side/beauty_proposal_adaptive_ablation_u_shuffle/logs/beauty_proposal_adaptive_ablation_u_shuffle.log /data/Zijian/goal/RecDemoRuns/main_table_text_side/beauty_proposal_adaptive_ablation_u_shuffle/checkpoints-meta/Beauty/best_summary_proposal_adaptive.json /data/Zijian/goal/RecDemoRuns/main_table_text_side/beauty_proposal_adaptive_ablation_u_shuffle/checkpoints-meta/Beauty/checkpoint_proposal_adaptive_best.pth 2237 /data/Zijian/goal/RecDemoRuns/main_table_text_side/beauty_proposal_adaptive_ablation_u_shuffle/checkpoints-meta/Beauty/frozen_run_manifest.json
    run_core text_anchor_only_beauty Beauty /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Beauty /data/Zijian/goal/RecDemoRuns/main_table_text_side/beauty_proposal_adaptive_ablation_text_anchor_only/logs/beauty_proposal_adaptive_ablation_text_anchor_only.log /data/Zijian/goal/RecDemoRuns/main_table_text_side/beauty_proposal_adaptive_ablation_text_anchor_only/checkpoints-meta/Beauty/best_summary_proposal_adaptive.json /data/Zijian/goal/RecDemoRuns/main_table_text_side/beauty_proposal_adaptive_ablation_text_anchor_only/checkpoints-meta/Beauty/checkpoint_proposal_adaptive_best.pth 2237 /data/Zijian/goal/RecDemoRuns/main_table_text_side/beauty_proposal_adaptive_ablation_text_anchor_only/checkpoints-meta/Beauty/frozen_run_manifest.json
    ;;
  1)
    run_diff diffurec_beauty Beauty /data/Zijian/goal/RecDemoRuns/close04_diffurec/beauty_diffurec_seed100/checkpoints-meta/Beauty/diffurec_run_manifest.json /data/Zijian/goal/RecDemoRuns/close04_diffurec/beauty_diffurec_seed100/checkpoints-meta/Beauty/checkpoint_diffurec_best.pt 2237
    run_diff diffurec_ml1m ML1M /data/Zijian/goal/RecDemoRuns/close04_diffurec/ml1m_diffurec_seed100/checkpoints-meta/ML1M/diffurec_run_manifest.json /data/Zijian/goal/RecDemoRuns/close04_diffurec/ml1m_diffurec_seed100/checkpoints-meta/ML1M/checkpoint_diffurec_best.pt 85405
    run_diff diffurec_atg ATG /data/Zijian/goal/RecDemoRuns/close04_diffurec/atg_diffurec_seed100/checkpoints-meta/ATG/diffurec_run_manifest.json /data/Zijian/goal/RecDemoRuns/close04_diffurec/atg_diffurec_seed100/checkpoints-meta/ATG/checkpoint_diffurec_best.pt 1942
    run_core host_ml1m ML1M /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ML1M /data/Zijian/goal/RecDemo/logs/ml1m_hybrid_earlystop.log /data/Zijian/goal/RecDemo/checkpoints-meta/ML1M/best_summary_hybrid.json /data/Zijian/goal/RecDemo/checkpoints-meta/ML1M/checkpoint_hybrid_best.pth 85405 -
    run_core ours_full_ml1m ML1M /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ML1M /data/Zijian/goal/RecDemoRuns/main_table_text_side/ml1m_proposal_adaptive_mainpath/logs/ml1m_proposal_adaptive_mainpath.log /data/Zijian/goal/RecDemoRuns/main_table_text_side/ml1m_proposal_adaptive_mainpath/checkpoints-meta/ML1M/best_summary_proposal_adaptive.json /data/Zijian/goal/RecDemoRuns/main_table_text_side/ml1m_proposal_adaptive_mainpath/checkpoints-meta/ML1M/checkpoint_proposal_adaptive_best.pth 85405 /data/Zijian/goal/RecDemoRuns/main_table_text_side/ml1m_proposal_adaptive_mainpath/checkpoints-meta/ML1M/frozen_run_manifest.json
    run_core host_atg ATG /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ATG /data/Zijian/goal/RecDemo/logs/atg_hybrid_earlystop.log /data/Zijian/goal/RecDemo/checkpoints-meta/ATG/best_summary_hybrid.json /data/Zijian/goal/RecDemo/checkpoints-meta/ATG/checkpoint_hybrid_best.pth 1942 -
    run_core ours_full_atg ATG /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ATG /data/Zijian/goal/RecDemoRuns/main_table_text_side/atg_proposal_adaptive_mainpath/logs/atg_proposal_adaptive_mainpath.log /data/Zijian/goal/RecDemoRuns/main_table_text_side/atg_proposal_adaptive_mainpath/checkpoints-meta/ATG/best_summary_proposal_adaptive.json /data/Zijian/goal/RecDemoRuns/main_table_text_side/atg_proposal_adaptive_mainpath/checkpoints-meta/ATG/checkpoint_proposal_adaptive_best.pth 1942 /data/Zijian/goal/RecDemoRuns/main_table_text_side/atg_proposal_adaptive_mainpath/checkpoints-meta/ATG/frozen_run_manifest.json
    ;;
  *)
    echo "invalid shard: $SHARD" >&2
    exit 4
    ;;
esac

echo "E0_SHARD_DONE shard=$SHARD gpu=$GPU_INDEX"
