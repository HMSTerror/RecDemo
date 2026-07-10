# CLOSE-03 Kernel Version Raw Audit

- Audit time: `2026-07-10T13:52:07+08:00`
- Remote host: `zijian@172.18.0.40`
- Operation: read-only `grep -m1 kernel_version`
- Verdict: all three historical CLOSE-03 runs recorded `kernel_version: v1`; none is final-v2 robustness evidence.

## Commands And Raw Lines

### full_u

```bash
ssh zijian@172.18.0.40 "grep -m1 kernel_version /data/Zijian/goal/RecDemoRuns/close03_beauty_token_dropout/close03_beauty_token_dropout_full_u_p5/logs/close03_beauty_token_dropout_full_u_p5.log"
```

```text
{'ngpus': 0, 'cuda': 1, 'random_seed': 100, 'work_dir': '/data/Zijian/goal/RecDemoRuns/close03_beauty_token_dropout/close03_beauty_token_dropout_full_u_p5', 'loss_type': 'score_entropy', 'training': {'data': 'Beauty', 'batch_size': 256, 'accum': 1, 'n_iters': 2000000, 'snapshot_freq': 500, 'log_freq': 2000, 'eval_freq': 500, 'snapshot_freq_for_preemption': 10000, 'weight': 'standard', 'snapshot_sampling': True, 'ema': 0.9999, 'nonpreference_user_ratio': 0.1, 'early_stop_patience': 4, 'early_stop_min_step': 4000, 'early_stop_metric': 'ndcg10', 'early_stop_strength': 'p5', 'early_stop_min_delta': 0.0, 'write_snapshot_checkpoint': True, 'write_best_checkpoint': True}, 'data': {'Steam': {'path': 'dataset/steam', 'seq_len': 10, 'item_num': 9265}, 'Beauty': {'path': '/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Beauty', 'seq_len': 10, 'item_num': 12101}, 'ASO': {'path': 'dataset/ASO', 'seq_len': 10, 'item_num': 18357}, 'ATG': {'path': 'dataset/ATG', 'seq_len': 10, 'item_num': 11924}, 'ATV': {'path': 'dataset/ATV', 'seq_len': 10, 'item_num': 44014}, 'ML1M': {'path': 'dataset/ML1M', 'seq_len': 10, 'item_num': 3883}}, 'graph': {'type': 'proposal_adaptive', 'is_disliked_item': True, 'gamma': 0.5, 'file': 'data', 'report_all': False}, 'noise': {'type': 'geometric', 'sigma_min': 0.001, 'sigma_max': 10}, 'sampling': {'predictor': 'analytic', 'steps': 20, 'noise_removal': True, 'personalization_strength': 2}, 'text_side': {'enabled': True, 'dataset_dir': '/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Beauty', 'text_bank_path': '/data/Zijian/goal/RecDemoRuns/beauty_corruptions/token_dropout_text_bank.csv', 'embeddings_path': '/data/Zijian/goal/RecDemoRuns/beauty_corruptions/token_dropout_sentence_t5_xl_item_emb.pt', 'temperature': 0.2, 'min_pseudo_mass': 0.03, 'kernel_version': 'v1', 'g_max': 0.5, 'agreement_null_curve_path': None, 'text_utility_report_path': '/data/Zijian/goal/RecDemoRuns/close03_beauty_token_dropout/close03_beauty_token_dropout/beauty_cleanphi_corruptedbank_gate_report.json', 'agreement_k': 2.0, 'agreement_weight': 0.35, 'completeness_weight': 0.05, 'history_reliability_weight': 0.6, 'ess_weight': 0.2, 'recency_weight': 0.35, 'stability_weight': 0.45, 'max_temperature_scale': 1.4, 'popularity_mix_scale': 0.0, 'popularity_mix_power': 1.0, 'center_embeddings': True, 'pseudo_mass_scale': 1.0, 'pseudo_mass_power': 1.0, 'ablation_mode': 'none', 'injection_mode': 'kernel', 'encoder_context_scale': 1.0, 'loss_weight_scale': 1.0}, 'eval': {'batch_size': 256, 'perplexity': True, 'perplexity_batch_size': 32}, 'optim': {'weight_decay': 0, 'optimizer': 'AdamW', 'lr': 0.0001, 'beta1': 0.9, 'beta2': 0.999, 'eps': 1e-08, 'warmup': 2500, 'grad_clip': 1.0}, 'model': {'name': 'small', 'type': 'ddit', 'hidden_size': 256, 'cond_dim': 256, 'length': 10, 'n_blocks': 1, 'n_heads': 2, 'scale_by_sigma': False, 'dropout': 0.1, 'score_flag': False, 'score_method': 'oricos'}}
```

### text_anchor_only

```bash
ssh zijian@172.18.0.40 "grep -m1 kernel_version /data/Zijian/goal/RecDemoRuns/close03_beauty_token_dropout/close03_beauty_token_dropout_text_anchor_only_p5/logs/close03_beauty_token_dropout_text_anchor_only_p5.log"
```

```text
{'ngpus': 0, 'cuda': 1, 'random_seed': 100, 'work_dir': '/data/Zijian/goal/RecDemoRuns/close03_beauty_token_dropout/close03_beauty_token_dropout_text_anchor_only_p5', 'loss_type': 'score_entropy', 'training': {'data': 'Beauty', 'batch_size': 256, 'accum': 1, 'n_iters': 2000000, 'snapshot_freq': 500, 'log_freq': 2000, 'eval_freq': 500, 'snapshot_freq_for_preemption': 10000, 'weight': 'standard', 'snapshot_sampling': True, 'ema': 0.9999, 'nonpreference_user_ratio': 0.1, 'early_stop_patience': 4, 'early_stop_min_step': 4000, 'early_stop_metric': 'ndcg10', 'early_stop_strength': 'p5', 'early_stop_min_delta': 0.0, 'write_snapshot_checkpoint': True, 'write_best_checkpoint': True}, 'data': {'Steam': {'path': 'dataset/steam', 'seq_len': 10, 'item_num': 9265}, 'Beauty': {'path': '/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Beauty', 'seq_len': 10, 'item_num': 12101}, 'ASO': {'path': 'dataset/ASO', 'seq_len': 10, 'item_num': 18357}, 'ATG': {'path': 'dataset/ATG', 'seq_len': 10, 'item_num': 11924}, 'ATV': {'path': 'dataset/ATV', 'seq_len': 10, 'item_num': 44014}, 'ML1M': {'path': 'dataset/ML1M', 'seq_len': 10, 'item_num': 3883}}, 'graph': {'type': 'proposal_adaptive', 'is_disliked_item': True, 'gamma': 0.5, 'file': 'data', 'report_all': False}, 'noise': {'type': 'geometric', 'sigma_min': 0.001, 'sigma_max': 10}, 'sampling': {'predictor': 'analytic', 'steps': 20, 'noise_removal': True, 'personalization_strength': 2}, 'text_side': {'enabled': True, 'dataset_dir': '/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Beauty', 'text_bank_path': '/data/Zijian/goal/RecDemoRuns/beauty_corruptions/token_dropout_text_bank.csv', 'embeddings_path': '/data/Zijian/goal/RecDemoRuns/beauty_corruptions/token_dropout_sentence_t5_xl_item_emb.pt', 'temperature': 0.2, 'min_pseudo_mass': 0.03, 'kernel_version': 'v1', 'g_max': 0.5, 'agreement_null_curve_path': None, 'text_utility_report_path': '/data/Zijian/goal/RecDemoRuns/close03_beauty_token_dropout/close03_beauty_token_dropout/beauty_cleanphi_corruptedbank_gate_report.json', 'agreement_k': 2.0, 'agreement_weight': 0.35, 'completeness_weight': 0.05, 'history_reliability_weight': 0.6, 'ess_weight': 0.2, 'recency_weight': 0.35, 'stability_weight': 0.45, 'max_temperature_scale': 1.4, 'popularity_mix_scale': 0.0, 'popularity_mix_power': 1.0, 'center_embeddings': True, 'pseudo_mass_scale': 1.0, 'pseudo_mass_power': 1.0, 'ablation_mode': 'text_anchor_only', 'injection_mode': 'kernel', 'encoder_context_scale': 1.0, 'loss_weight_scale': 1.0}, 'eval': {'batch_size': 256, 'perplexity': True, 'perplexity_batch_size': 32}, 'optim': {'weight_decay': 0, 'optimizer': 'AdamW', 'lr': 0.0001, 'beta1': 0.9, 'beta2': 0.999, 'eps': 1e-08, 'warmup': 2500, 'grad_clip': 1.0}, 'model': {'name': 'small', 'type': 'ddit', 'hidden_size': 256, 'cond_dim': 256, 'length': 10, 'n_blocks': 1, 'n_heads': 2, 'scale_by_sigma': False, 'dropout': 0.1, 'score_flag': False, 'score_method': 'oricos'}}
```

### u_shuffle

```bash
ssh zijian@172.18.0.40 "grep -m1 kernel_version /data/Zijian/goal/RecDemoRuns/close03_beauty_token_dropout/close03_beauty_token_dropout_u_shuffle_p5/logs/close03_beauty_token_dropout_u_shuffle_p5.log"
```

```text
{'ngpus': 0, 'cuda': 1, 'random_seed': 100, 'work_dir': '/data/Zijian/goal/RecDemoRuns/close03_beauty_token_dropout/close03_beauty_token_dropout_u_shuffle_p5', 'loss_type': 'score_entropy', 'training': {'data': 'Beauty', 'batch_size': 256, 'accum': 1, 'n_iters': 2000000, 'snapshot_freq': 500, 'log_freq': 2000, 'eval_freq': 500, 'snapshot_freq_for_preemption': 10000, 'weight': 'standard', 'snapshot_sampling': True, 'ema': 0.9999, 'nonpreference_user_ratio': 0.1, 'early_stop_patience': 4, 'early_stop_min_step': 4000, 'early_stop_metric': 'ndcg10', 'early_stop_strength': 'p5', 'early_stop_min_delta': 0.0, 'write_snapshot_checkpoint': True, 'write_best_checkpoint': True}, 'data': {'Steam': {'path': 'dataset/steam', 'seq_len': 10, 'item_num': 9265}, 'Beauty': {'path': '/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Beauty', 'seq_len': 10, 'item_num': 12101}, 'ASO': {'path': 'dataset/ASO', 'seq_len': 10, 'item_num': 18357}, 'ATG': {'path': 'dataset/ATG', 'seq_len': 10, 'item_num': 11924}, 'ATV': {'path': 'dataset/ATV', 'seq_len': 10, 'item_num': 44014}, 'ML1M': {'path': 'dataset/ML1M', 'seq_len': 10, 'item_num': 3883}}, 'graph': {'type': 'proposal_adaptive', 'is_disliked_item': True, 'gamma': 0.5, 'file': 'data', 'report_all': False}, 'noise': {'type': 'geometric', 'sigma_min': 0.001, 'sigma_max': 10}, 'sampling': {'predictor': 'analytic', 'steps': 20, 'noise_removal': True, 'personalization_strength': 2}, 'text_side': {'enabled': True, 'dataset_dir': '/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Beauty', 'text_bank_path': '/data/Zijian/goal/RecDemoRuns/beauty_corruptions/token_dropout_text_bank.csv', 'embeddings_path': '/data/Zijian/goal/RecDemoRuns/beauty_corruptions/token_dropout_sentence_t5_xl_item_emb.pt', 'temperature': 0.2, 'min_pseudo_mass': 0.03, 'kernel_version': 'v1', 'g_max': 0.5, 'agreement_null_curve_path': None, 'text_utility_report_path': '/data/Zijian/goal/RecDemoRuns/close03_beauty_token_dropout/close03_beauty_token_dropout/beauty_cleanphi_corruptedbank_gate_report.json', 'agreement_k': 2.0, 'agreement_weight': 0.35, 'completeness_weight': 0.05, 'history_reliability_weight': 0.6, 'ess_weight': 0.2, 'recency_weight': 0.35, 'stability_weight': 0.45, 'max_temperature_scale': 1.4, 'popularity_mix_scale': 0.0, 'popularity_mix_power': 1.0, 'center_embeddings': True, 'pseudo_mass_scale': 1.0, 'pseudo_mass_power': 1.0, 'ablation_mode': 'u_shuffle', 'injection_mode': 'kernel', 'encoder_context_scale': 1.0, 'loss_weight_scale': 1.0}, 'eval': {'batch_size': 256, 'perplexity': True, 'perplexity_batch_size': 32}, 'optim': {'weight_decay': 0, 'optimizer': 'AdamW', 'lr': 0.0001, 'beta1': 0.9, 'beta2': 0.999, 'eps': 1e-08, 'warmup': 2500, 'grad_clip': 1.0}, 'model': {'name': 'small', 'type': 'ddit', 'hidden_size': 256, 'cond_dim': 256, 'length': 10, 'n_blocks': 1, 'n_heads': 2, 'scale_by_sigma': False, 'dropout': 0.1, 'score_flag': False, 'score_method': 'oricos'}}
```

## Fresh Revalidation

The same three read-only `grep -m1 'kernel_version'` commands were rerun at
`2026-07-10T19:22:07+08:00`. Each fresh line was byte-for-byte present in the
archived command output above after line-ending normalization. SHA-256 over
the UTF-8 raw line without the trailing newline:

| Arm | `kernel_version` | Raw-line SHA-256 |
|---|---|---|
| `full_u` | `v1` | `3c3449f1431cdd3d47a060653eb6a1578c49f3a6849386daf1ea90f75ccfcce1` |
| `text_anchor_only` | `v1` | `d8a00cd41eeba98dd5806587d0a5c2e2f430731716c3cf14fde47f3c0f2f27d6` |
| `u_shuffle` | `v1` | `1424d2a6712f2baac88db7f6015c388dd78294d43880ed3e744f640fa83f1899` |

## Evidence Boundary

CLOSE-03 remains a historical v1 corruption rerun. It must not be cited as
final-v2 robustness evidence. AAAI-E03 was the authorized replacement source,
but the E1 step-0 hard stop blocked E3 before corruption construction or
training. Therefore this sprint has no final-v2 corruption-response evidence;
the manuscript keeps only explicitly scoped first-generation observations.
