"""Run one RQ1 combination: backbone × strategy × input_strategy.

Usage:
    python rq1_run_combo.py --backbone ResNet50 --strategy FT --input S1

Resume-aware: if results/rq1/<combo>/metrics.json exists the combo is skipped.
"""

import argparse
import json
import os
import gc
import numpy as np
from sklearn.metrics import roc_auc_score
import tensorflow as tf

from dfu_common import (
    CONFIG, SEED, make_logger, load_preprocessed_inaoe, create_fold_splits,
    base_model_creators, DFUModelTrainer, ALL_STRATEGIES, StrategyTuner,
)

BACKBONES = ['EfficientNetB0', 'ResNet50', 'ConvNeXt-Tiny']
INPUT_STRATEGIES = ['S1', 'S2']

DATA_SOURCE = {
    'S1': '/home/ntphoto/DFU/INAOE_S1',
    'S2': '/home/ntphoto/DFU/INAOE_S2',
}


def compute_fold_metrics(y_true, y_pred) -> dict:
    auc  = float(roc_auc_score(y_true, y_pred))
    yb   = (y_pred >= 0.5).astype(int)
    tp   = int(np.sum((yb == 1) & (y_true == 1)))
    fp   = int(np.sum((yb == 1) & (y_true == 0)))
    fn   = int(np.sum((yb == 0) & (y_true == 1)))
    tn   = int(np.sum((yb == 0) & (y_true == 0)))
    sens = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    f1   = 2 * prec * sens / (prec + sens) if (prec + sens) > 0 else 0.0
    acc  = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0.0
    return {'auc': auc, 'sens': sens, 'spec': spec, 'prec': prec, 'f1': f1, 'acc': acc}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--backbone', required=True, choices=BACKBONES)
    parser.add_argument('--strategy', required=True, choices=ALL_STRATEGIES)
    parser.add_argument('--input',    required=True, choices=INPUT_STRATEGIES,
                        help='S1 = original orientation, S2 = left foot flipped')
    args = parser.parse_args()

    backbone = args.backbone
    strategy = args.strategy
    input_s  = args.input

    combo_id  = f'{backbone}_{strategy}_{input_s}'
    out_dir   = os.path.join(CONFIG['results_dir'], 'rq1', combo_id)
    os.makedirs(out_dir, exist_ok=True)

    metrics_path   = os.path.join(out_dir, 'metrics.json')
    bp_path        = os.path.join(out_dir, 'best_params.json')
    val_preds_path = os.path.join(out_dir, 'val_preds.npz')

    log = make_logger(f'rq1_{combo_id}')
    log(f"\n{'#'*80}\n# COMBO: {combo_id}\n{'#'*80}\n")

    if os.path.exists(metrics_path):
        log(f"✓ Already complete — skipping.")
        return

    # ConvNeXt-Tiny needs smaller batch size to avoid OOM
    if backbone == 'ConvNeXt-Tiny':
        CONFIG['batch_size_default'] = 32
    else:
        CONFIG['batch_size_default'] = 64

    images, labels = load_preprocessed_inaoe(DATA_SOURCE[input_s], log=log)
    fold_indices, _ = create_fold_splits(
        images, labels, n_splits=CONFIG['n_folds'],
        test_split=CONFIG['test_split'], random_state=SEED,
    )

    base_model_fn = base_model_creators()[backbone]

    # ── Step 1: Hyperparameter tuning ────────────────────────────────────────
    if os.path.exists(bp_path):
        with open(bp_path) as f:
            best_params = json.load(f)
        log(f"✓ Loaded best_params — skipping tuning")
    else:
        tuner = StrategyTuner(
            model_name=f'{combo_id}',
            base_model_fn=base_model_fn,
            strategy=strategy,
            backbone_name=backbone,
            n_trials=CONFIG['n_bo_trials'],
            log=log,
        )
        best_params = tuner.optimize(images, labels, fold_indices)
        with open(bp_path, 'w') as f:
            json.dump(best_params, f, indent=2)
        log(f"✓ best_params → {bp_path}")

    # ── Step 2: 5-fold CV ────────────────────────────────────────────────────
    fold_preds  = {}
    fold_epochs = []
    fold_ckpts  = [os.path.join(out_dir, f'fold{i+1}_final.keras')
                   for i in range(CONFIG['n_folds'])]
    epochs_path = os.path.join(out_dir, 'fold_epochs.json')

    if os.path.exists(epochs_path):
        with open(epochs_path) as f:
            fold_epochs = json.load(f)
    else:
        fold_epochs = []

    for fi, fold in enumerate(fold_indices):
        ckpt = fold_ckpts[fi]
        X_v  = images[fold['val_idx']]
        y_v  = labels[fold['val_idx']]

        if os.path.exists(ckpt):
            log(f"✓ Fold {fi+1}: loading checkpoint")
            m     = tf.keras.models.load_model(ckpt)
            preds = m.predict(X_v, verbose=0).flatten()
            del m
            tf.keras.backend.clear_session(); gc.collect()
        else:
            X_tr = images[fold['train_idx']]
            y_tr = labels[fold['train_idx']]
            log(f"\n{'='*80}\nFOLD {fi+1}/{CONFIG['n_folds']}: {combo_id}\n{'='*80}")
            log(f"Train: {len(X_tr)}  Val: {len(X_v)}")

            base    = base_model_fn()
            trainer = DFUModelTrainer(
                model_name=f'{combo_id}_Fold{fi+1}',
                base_model=base,
                dropout_rate=best_params['dropout_rate'],
                l2_reg=best_params['l2_reg'],
                dense_units=(best_params['dense_units_1'], best_params['dense_units_2']),
                log=log,
                backbone_name=backbone,
            )
            trainer.build_model()
            trainer.train_with_strategy(
                strategy, X_tr, y_tr, X_v, y_v,
                params=best_params,
                max_epochs=CONFIG['max_epochs'],
                patience=CONFIG['phase1_patience'],
                verbose=1,
            )
            ep = trainer.get_epochs()
            if len(fold_epochs) <= fi:
                fold_epochs.append(ep)
            else:
                fold_epochs[fi] = ep
            with open(epochs_path, 'w') as f:
                json.dump(fold_epochs, f)
            preds = trainer.get_predictions(X_v)
            trainer.save_model(ckpt)
            log(f"✓ Fold {fi+1} complete  epochs={ep}")
            del trainer, base
            tf.keras.backend.clear_session(); gc.collect()

        fold_preds[f'fold{fi+1}'] = preds

    np.savez(val_preds_path, **fold_preds)

    # ── Step 3: Metrics ───────────────────────────────────────────────────────
    per_fold = []
    for fi, fold in enumerate(fold_indices):
        m = compute_fold_metrics(labels[fold['val_idx']], fold_preds[f'fold{fi+1}'])
        m['fold'] = fi + 1
        per_fold.append(m)
        log(f"  Fold {fi+1}:  AUC={m['auc']:.4f}  Sens={m['sens']:.4f}  "
            f"Spec={m['spec']:.4f}  F1={m['f1']:.4f}")

    keys  = ['auc', 'sens', 'spec', 'prec', 'f1', 'acc']
    mean_m = {k: float(np.mean([f[k] for f in per_fold])) for k in keys}
    std_m  = {k: float(np.std( [f[k] for f in per_fold])) for k in keys}

    log(f"\n  Mean:  AUC={mean_m['auc']:.4f}±{std_m['auc']:.4f}  "
        f"Sens={mean_m['sens']:.4f}±{std_m['sens']:.4f}  "
        f"Spec={mean_m['spec']:.4f}±{std_m['spec']:.4f}")

    # Average stopping epochs across folds (for fixed-epoch final retraining)
    p1_vals = [e.get('phase1') for e in fold_epochs if e.get('phase1') is not None]
    p2_vals = [e.get('phase2') for e in fold_epochs if e.get('phase2') is not None]
    avg_epochs = {
        'phase1': int(round(float(np.mean(p1_vals)))) if p1_vals else None,
        'phase2': int(round(float(np.mean(p2_vals)))) if p2_vals else None,
    }
    log(f"  Avg epochs: phase1={avg_epochs['phase1']}, phase2={avg_epochs['phase2']}")

    result = {
        'backbone': backbone, 'strategy': strategy, 'input_strategy': input_s,
        'per_fold': per_fold, 'mean': mean_m, 'std': std_m,
        'avg_epochs': avg_epochs,
    }
    with open(metrics_path, 'w') as f:
        json.dump(result, f, indent=2)
    log(f"\n✓ Metrics → {metrics_path}")
    log(f"\n{'#'*80}\n# {combo_id} COMPLETE\n{'#'*80}\n")


if __name__ == '__main__':
    main()
