"""RQ2: Quantify improvement when transitioning from the default threshold (0.5)
to the optimised Youden's Index threshold for the best backbone from RQ1.

Youden's J = Sensitivity + Specificity − 1  →  threshold = argmax(TPR − FPR)

Reporting:
  Step 1 — Show per-fold Youden thresholds → compute mean Youden threshold
  Step 2 — Apply mean threshold to each fold's val set (Option B)
            Report mean ± std at default vs mean Youden threshold

Saves results to results/rq2_results.json.
Run after rq1_backbone_comparison.py.
"""

import os
import json
import numpy as np

from dfu_common import (
    CONFIG, SEED, make_logger, load_preprocessed_inaoe, create_fold_splits,
    compute_youden_threshold,
)


def binary_metrics(y_true, y_prob, threshold):
    yb = (y_prob >= threshold).astype(int)
    tp = int(np.sum((yb == 1) & (y_true == 1)))
    fn = int(np.sum((yb == 0) & (y_true == 1)))
    tn = int(np.sum((yb == 0) & (y_true == 0)))
    fp = int(np.sum((yb == 1) & (y_true == 0)))
    sens = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    return sens, spec


def main():
    log = make_logger('rq2')

    rq1_path = os.path.join(CONFIG['results_dir'], 'rq1_results.json')
    if not os.path.exists(rq1_path):
        log("❌ rq1_results.json not found. Run rq1_backbone_comparison.py first.")
        return
    with open(rq1_path) as f:
        rq1 = json.load(f)
    best_model = rq1['best_model']
    log(f"Best backbone from RQ1: {best_model}")

    images, labels = load_preprocessed_inaoe(CONFIG['data_source'], log=log)
    fold_indices, _ = create_fold_splits(
        images, labels,
        n_splits=CONFIG['n_folds'],
        test_split=CONFIG['test_split'],
        random_state=SEED,
    )

    vp_path = os.path.join(CONFIG['checkpoint_dir'], f"{best_model}_val_preds.npz")
    if not os.path.exists(vp_path):
        log(f"❌ {vp_path} not found.")
        return
    npz = np.load(vp_path)

    # ── Step 1: Per-fold Youden threshold ────────────────────────────────────
    log(f"\n{'='*80}")
    log(f"RQ2: STEP 1 — Per-fold Youden's Index threshold ({best_model})")
    log(f"{'='*80}")
    log(f"  {'Fold':<6} {'Youden Threshold':>18} {'Sens @ thr':>12} {'Spec @ thr':>12}")
    log(f"  {'─'*52}")

    youden_thresholds = []
    fold_results = []
    val_preds_list = []

    for i, fi in enumerate(fold_indices):
        yv = labels[fi['val_idx']]
        vp = npz[f'fold{i+1}']
        val_preds_list.append((yv, vp))

        y_thr, y_sens, y_spec = compute_youden_threshold(yv, vp)
        youden_thresholds.append(y_thr)
        log(f"  Fold {i+1}  {y_thr:>18.4f} {y_sens:>12.4f} {y_spec:>12.4f}")

        fold_results.append({
            'fold':            i + 1,
            'youden_threshold': y_thr,
            'youden_sens':      y_sens,
            'youden_spec':      y_spec,
        })

    mean_thr = float(np.mean(youden_thresholds))
    std_thr  = float(np.std(youden_thresholds))
    log(f"  {'─'*52}")
    log(f"  {'Mean':<6} {mean_thr:>18.4f}")

    # ── Step 2: Apply mean threshold to each fold → compare vs default ────────
    log(f"\n{'='*80}")
    log(f"RQ2: STEP 2 — Default (0.5) vs Mean Youden ({mean_thr:.4f}) per fold")
    log(f"{'='*80}")
    log(f"  {'Fold':<6} {'Default Sens':>13} {'Default Spec':>13} "
        f"{'Youden Sens':>13} {'Youden Spec':>13}")
    log(f"  {'─'*62}")

    d_sens_list, d_spec_list = [], []
    y_sens_list, y_spec_list = [], []

    for i, (yv, vp) in enumerate(val_preds_list):
        d_s, d_sp = binary_metrics(yv, vp, 0.5)
        y_s, y_sp = binary_metrics(yv, vp, mean_thr)
        d_sens_list.append(d_s);  d_spec_list.append(d_sp)
        y_sens_list.append(y_s);  y_spec_list.append(y_sp)
        log(f"  Fold {i+1}  {d_s:>13.4f} {d_sp:>13.4f} {y_s:>13.4f} {y_sp:>13.4f}")

    mean_d_sens = float(np.mean(d_sens_list));  std_d_sens = float(np.std(d_sens_list))
    mean_d_spec = float(np.mean(d_spec_list));  std_d_spec = float(np.std(d_spec_list))
    mean_y_sens = float(np.mean(y_sens_list));  std_y_sens = float(np.std(y_sens_list))
    mean_y_spec = float(np.mean(y_spec_list));  std_y_spec = float(np.std(y_spec_list))

    delta_sens = mean_y_sens - mean_d_sens
    delta_spec = mean_y_spec - mean_d_spec

    log(f"  {'─'*62}")
    log(f"  {'Mean':<6} {mean_d_sens:>13.4f} {mean_d_spec:>13.4f} "
        f"{mean_y_sens:>13.4f} {mean_y_spec:>13.4f}")
    log(f"  {'±Std':<6} {std_d_sens:>13.4f} {std_d_spec:>13.4f} "
        f"{std_y_sens:>13.4f} {std_y_spec:>13.4f}")

    delta_sens_pct = (delta_sens / mean_d_sens * 100) if mean_d_sens > 1e-9 else 0.0
    delta_spec_pct = (delta_spec / mean_d_spec * 100) if mean_d_spec > 1e-9 else 0.0

    log(f"\n{'─'*80}")
    log(f"  Summary  (Default 0.5  →  Youden {mean_thr:.4f})")
    log(f"{'─'*80}")
    log(f"  Sensitivity : {mean_d_sens:.4f} ± {std_d_sens:.4f}  →  "
        f"{mean_y_sens:.4f} ± {std_y_sens:.4f}   Δ = {delta_sens:+.4f} pp  ({delta_sens_pct:+.1f}%)")
    log(f"  Specificity : {mean_d_spec:.4f} ± {std_d_spec:.4f}  →  "
        f"{mean_y_spec:.4f} ± {std_y_spec:.4f}   Δ = {delta_spec:+.4f} pp  ({delta_spec_pct:+.1f}%)")

    result = {
        'best_model':            best_model,
        'mean_youden_threshold': mean_thr,
        'std_youden_threshold':  std_thr,
        'per_fold_thresholds':   fold_results,
        'default_threshold': {
            'mean_sens': mean_d_sens, 'std_sens': std_d_sens,
            'mean_spec': mean_d_spec, 'std_spec': std_d_spec,
        },
        'youden_threshold': {
            'mean_sens': mean_y_sens, 'std_sens': std_y_sens,
            'mean_spec': mean_y_spec, 'std_spec': std_y_spec,
        },
        'delta_sens_pp': delta_sens,
        'delta_spec_pp': delta_spec,
    }
    out = os.path.join(CONFIG['results_dir'], 'rq2_results.json')
    with open(out, 'w') as f:
        json.dump(result, f, indent=2)
    log(f"\n✓ Results → {out}")


if __name__ == '__main__':
    main()
