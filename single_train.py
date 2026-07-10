import json
import logging
import os
import random
import time

import hydra
import numpy as np
import torch
from omegaconf import DictConfig

import data
import dataset_runtime
import graph_lib
import losses
import noise_lib
import sampling
import utils
from scripts.aaai27_adapters.optimizer_contract import compose_optimizer_parameters
from model.ema import ExponentialMovingAverage
from model.transformer import SEDD4REC


torch.backends.cudnn.benchmark = True
logging.getLogger().setLevel(logging.INFO)


def setup_seed(seed):
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)
    random.seed(seed)
    torch.backends.cudnn.deterministic = True


def format_personalization_strength(value: float) -> str:
    value = float(value)
    if value.is_integer():
        return str(int(value))
    return f"{value:g}"


def build_sampling_functions(cfg, graph, noise, sampling_eps, device):
    personalization = float(cfg.sampling.personalization_strength)
    personalization_label = format_personalization_strength(personalization)
    return {
        "base": {
            "label": "without personalzation strength",
            "fn": sampling.get_sampling_fn(cfg, graph, noise, sampling_eps, 1, device),
        },
        "p2": {
            "label": f"with personalzation strength {personalization_label}",
            "fn": sampling.get_sampling_fn(cfg, graph, noise, sampling_eps, personalization, device),
        },
        "p5": {
            "label": "with personalzation strength 5",
            "fn": sampling.get_sampling_fn(cfg, graph, noise, sampling_eps, 5, device),
        },
        "p10": {
            "label": "with personalzation strength 10",
            "fn": sampling.get_sampling_fn(cfg, graph, noise, sampling_eps, 10, device),
        },
    }


def run_eval_suite(
    score_model,
    ema,
    sampling_fns,
    val_loader,
    test_loader,
    device,
    valid_item_count,
    ema_parameters=None,
):
    val_results = {}
    test_results = {}

    evaluation_parameters = (
        list(ema_parameters)
        if ema_parameters is not None
        else list(score_model.parameters())
    )
    ema.store(evaluation_parameters)
    ema.copy_to(evaluation_parameters)
    try:
        hr, ndcg = utils.evaluate_loader(
            score_model, sampling_fns["base"]["fn"], val_loader, device, valid_item_count
        )
        val_results["base"] = {"hr": hr, "ndcg": ndcg}

        for key in ("p2", "p5", "p10"):
            print(sampling_fns[key]["label"])
            hr, ndcg = utils.evaluate_loader(
                score_model, sampling_fns[key]["fn"], val_loader, device, valid_item_count
            )
            val_results[key] = {"hr": hr, "ndcg": ndcg}

        print("test phase:")
        print(sampling_fns["base"]["label"])
        hr, ndcg = utils.evaluate_loader(
            score_model, sampling_fns["base"]["fn"], test_loader, device, valid_item_count
        )
        test_results["base"] = {"hr": hr, "ndcg": ndcg}

        for key in ("p2", "p5", "p10"):
            print(sampling_fns[key]["label"])
            hr, ndcg = utils.evaluate_loader(
                score_model, sampling_fns[key]["fn"], test_loader, device, valid_item_count
            )
            test_results[key] = {"hr": hr, "ndcg": ndcg}
    finally:
        ema.restore(evaluation_parameters)

    return val_results, test_results


def extract_metric(metric_results, strength_key, metric_name):
    metric_name = metric_name.lower()
    if metric_name not in {"hr10", "ndcg10", "hr20", "ndcg20"}:
        raise ValueError(f"Unsupported early stop metric: {metric_name}")

    metric_type = "hr" if metric_name.startswith("hr") else "ndcg"
    topk_index = 2 if metric_name.endswith("10") else 3
    return float(metric_results[strength_key][metric_type][topk_index])


def build_best_summary(metric_name, best_step, best_metric, best_val_results, best_test_results):
    return {
        "metric_name": metric_name,
        "best_step": best_step,
        "best_metric": best_metric,
        "validation": best_val_results,
        "test": best_test_results,
    }


def maybe_write_periodic_checkpoint(
    *,
    current_step,
    snapshot_freq_for_preemption,
    latest_checkpoint_path,
    state,
    write_latest_checkpoint,
):
    if not write_latest_checkpoint:
        return False
    if snapshot_freq_for_preemption <= 0:
        return False
    if current_step % snapshot_freq_for_preemption != 0:
        return False
    utils.save_single_checkpoint(latest_checkpoint_path, state)
    return True


@hydra.main(version_base=None, config_path="./configs", config_name="config")
def main(cfg: DictConfig):
    setup_seed(cfg.random_seed)
    os.environ["CUDA_VISIBLE_DEVICES"] = str(cfg.cuda)
    dataset_runtime.reconcile_runtime_dataset_config(cfg)

    work_dir = cfg.work_dir
    checkpoint_dir = "./checkpoints/" + cfg.training.data + "/"
    checkpoint_meta_dir = os.path.join(work_dir, "checkpoints-meta", cfg.training.data)
    os.makedirs(checkpoint_dir, exist_ok=True)
    os.makedirs(checkpoint_meta_dir, exist_ok=True)

    print(work_dir)
    print(cfg)

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    graph = graph_lib.get_graph(cfg, device)
    score_model = SEDD4REC(cfg).to(device)

    num_parameters = sum(p.numel() for p in score_model.parameters())
    print(f"Number of parameters in the model: {num_parameters}")

    training_parameters = list(score_model.parameters())
    graph_p1 = getattr(graph, "p1", None)
    if graph_p1 is not None and all(
        id(graph_p1) != id(parameter) for parameter in training_parameters
    ):
        training_parameters.append(graph_p1)
    ema = ExponentialMovingAverage(training_parameters, decay=cfg.training.ema)
    print(score_model)
    print(f"EMA: {ema}")

    noise = noise_lib.get_noise(cfg).to(device)
    sampling_eps = 1e-5

    optimizer = losses.get_optimizer(cfg, compose_optimizer_parameters(score_model, graph, noise))
    print(f"Optimizer: {optimizer}")
    scaler = torch.cuda.amp.GradScaler()
    print(f"Scaler: {scaler}")
    state = dict(
        optimizer=optimizer,
        scaler=scaler,
        model=score_model,
        noise=noise,
        ema=ema,
        training_parameters=training_parameters,
        step=0,
    )
    initial_step = int(state["step"])

    train_loader, val_loader, test_loader = data.get_seqdataloader(cfg)
    valid_item_count = int(getattr(cfg.data, str(cfg.training.data)).item_num)
    val_iter = iter(val_loader)
    print(f"Length of datasets: {len(train_loader)}, {len(val_loader)}, {len(test_loader)}")

    optimize_fn = losses.optimization_manager(cfg)
    train_step_fn = losses.get_step_fn(noise, graph, True, cfg.loss_type, optimize_fn, cfg.training.accum)
    eval_step_fn = losses.get_step_fn(noise, graph, False, cfg.loss_type, optimize_fn, cfg.training.accum)

    sampling_fns = None
    if cfg.training.snapshot_sampling:
        sampling_fns = build_sampling_functions(cfg, graph, noise, sampling_eps, device)

    num_train_steps = int(cfg.training.n_iters)
    print(f"Starting training loop at step {initial_step}.")
    start_time = time.time()

    if sampling_fns is not None:
        utils.evaluate_loader(
            score_model, sampling_fns["p2"]["fn"], val_loader, device, valid_item_count
        )

    early_stop_patience = int(cfg.training.get("early_stop_patience", 0))
    early_stop_min_step = int(cfg.training.get("early_stop_min_step", 0))
    best_selection_min_step = int(cfg.training.get("best_selection_min_step", 0))
    early_stop_metric = str(cfg.training.get("early_stop_metric", "ndcg10")).lower()
    early_stop_strength = str(cfg.training.get("early_stop_strength", "p2"))
    early_stop_min_delta = float(cfg.training.get("early_stop_min_delta", 0.0))
    early_stop_enabled = early_stop_patience > 0
    write_latest_checkpoint = bool(cfg.training.get("write_snapshot_checkpoint", True))
    write_best_checkpoint = bool(cfg.training.get("write_best_checkpoint", True))

    best_metric = float("-inf")
    best_step = None
    best_val_results = None
    best_test_results = None
    no_improve_count = 0
    stop_training = False
    summary_path = os.path.join(checkpoint_meta_dir, f"best_summary_{cfg.graph.type}.json")
    latest_checkpoint_path = os.path.join(checkpoint_meta_dir, f"checkpoint_{cfg.graph.type}.pth")
    best_checkpoint_path = os.path.join(checkpoint_meta_dir, f"checkpoint_{cfg.graph.type}_best.pth")

    while state["step"] < num_train_steps and not stop_training:
        for batch in train_loader:
            previous_step = state["step"]
            batch = {key: value.to(device) for key, value in batch.items()}
            loss = train_step_fn(state, batch, cfg.sampling.steps)
            current_step = state["step"]

            if previous_step == current_step:
                continue

            current_time = time.time()

            if current_step % cfg.training.log_freq == 0:
                elapsed_time = current_time - start_time
                print("step: %d, training_loss: %.5e, time_elapsed: %.2fs" % (current_step, loss.item(), elapsed_time))
                start_time = current_time

            maybe_write_periodic_checkpoint(
                current_step=current_step,
                snapshot_freq_for_preemption=cfg.training.snapshot_freq_for_preemption,
                latest_checkpoint_path=latest_checkpoint_path,
                state=state,
                write_latest_checkpoint=write_latest_checkpoint,
            )

            if current_step % cfg.training.eval_freq == 0:
                try:
                    eval_batch = next(val_iter)
                except StopIteration:
                    val_iter = iter(val_loader)
                    eval_batch = next(val_iter)
                eval_batch = {key: value.to(device) for key, value in eval_batch.items()}
                eval_loss = eval_step_fn(state, eval_batch, cfg.sampling.steps)
                eval_elapsed_time = time.time() - current_time
                print("step: %d, evaluation_loss: %.5e, eval_time: %.2fs" % (current_step, eval_loss.item(), eval_elapsed_time))

            should_snapshot = current_step > 0 and (
                current_step % cfg.training.snapshot_freq == 0 or current_step >= num_train_steps
            )
            if should_snapshot and sampling_fns is not None:
                if write_latest_checkpoint:
                    utils.save_single_checkpoint(latest_checkpoint_path, state)
                else:
                    print(f"SKIP_LATEST_CHECKPOINT step={current_step} path={latest_checkpoint_path}")
                print(f"Generating items at step: {current_step}")
                val_results, test_results = run_eval_suite(
                    score_model=score_model,
                    ema=ema,
                    sampling_fns=sampling_fns,
                    val_loader=val_loader,
                    test_loader=test_loader,
                    device=device,
                    valid_item_count=valid_item_count,
                    ema_parameters=state["training_parameters"],
                )

                if early_stop_enabled:
                    current_metric = extract_metric(val_results, early_stop_strength, early_stop_metric)
                    print(
                        f"EARLY_STOP_MONITOR step={current_step} metric={early_stop_metric} "
                        f"strength={early_stop_strength} value={current_metric:.6f}"
                    )
                    if current_step < best_selection_min_step:
                        print(
                            f"EARLY_STOP_SKIP_BEST_BEFORE_MIN step={current_step} "
                            f"threshold={best_selection_min_step}"
                        )
                    else:
                        if current_metric > best_metric + early_stop_min_delta:
                            best_metric = current_metric
                            best_step = current_step
                            best_val_results = val_results
                            best_test_results = test_results
                            no_improve_count = 0
                            if write_best_checkpoint:
                                utils.save_single_checkpoint(best_checkpoint_path, state)
                            else:
                                print(f"SKIP_BEST_CHECKPOINT step={current_step} path={best_checkpoint_path}")
                            summary = build_best_summary(
                                metric_name=early_stop_metric,
                                best_step=best_step,
                                best_metric=best_metric,
                                best_val_results=best_val_results,
                                best_test_results=best_test_results,
                            )
                            with open(summary_path, "w", encoding="utf-8") as f:
                                json.dump(summary, f, indent=2)
                            print(f"NEW_BEST step={best_step} metric={early_stop_metric} value={best_metric:.6f}")
                        else:
                            no_improve_count += 1
                            print(
                                f"EARLY_STOP_WAIT counter={no_improve_count}/{early_stop_patience} "
                                f"best_step={best_step} best_value={best_metric:.6f}"
                            )

                    if current_step >= early_stop_min_step and no_improve_count >= early_stop_patience:
                        print(
                            f"EARLY_STOP_TRIGGERED step={current_step} best_step={best_step} "
                            f"best_metric={best_metric:.6f}"
                        )
                        stop_training = True

            if current_step >= num_train_steps or stop_training:
                break

    if best_step is not None:
        print(
            f"BEST_RESULT step={best_step} metric={early_stop_metric} "
            f"value={best_metric:.6f} summary={summary_path}"
        )


if __name__ == "__main__":
    main()
