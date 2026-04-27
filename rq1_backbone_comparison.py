"""RQ1: Evaluate and compare EfficientNetB0, ResNet50, and ConvNeXt-Tiny.

Loads 5-fold CV validation predictions (produced by train_*.py) and compares
each backbone against clinical screening criteria.  The best backbone is saved
to results/rq1_results.json for use by downstream RQ scripts.

Run after all three train_*.py scripts have completed.
"""

import os
import json
import numpy as np
from sklearn.metrics import roc_auc_score

from dfu_common import (
    CONFIG, SEED, make_logger, load_preprocessed_inaoe, create_fold_splits,
)

MODEL_LIST = ['EfficientNetB0', 'ResNet50', 'ConvNeXt-Tiny']

CRITERIA = {
    'auc':  0.80,
    'sens': 0.85,
    'spec': 0.70,
}


def fold_metrics_at_05(val_preds, fold_indices, y_full):
    """Mean AUC, Sensitivity, Specificity across folds at threshold = 0.5."""
    aucs, sens_list, spec_list = [], [], []
    for fi, vp in zip(fold_indices, val_preds):
        yv = y_full[fi['val_idx']]
        aucs.append(roc_auc_score(yv, vp))
        yb = (vp >= 0.5).astype(int)
        tp = int(np.sum((yb == 1) & (yv == 1)))
        fn = int(np.sum((yb == 0) & (yv == 1)))
        tn = int(np.sum((yb == 0) & (yv == 0)))
        fp = int(np.sum((yb == 1) & (yv == 0)))
        sens_list.append(tp / (tp + fn) if (tp + fn) > 0 else 0.0)
        spec_list.append(tn / (tn + fp) if (tn + fp) > 0 else 0.0)
    return float(np.mean(aucs)), float(np.mean(sens_list)), float(np.mean(spec_list))


def main():
    log = make_logger('rq1')

    images, labels = load_preprocessed_inaoe(CONFIG['data_source'], log=log)
    fold_indices, _ = create_fold_splits(
        images, labels,
        n_splits=CONFIG['n_folds'],
        test_split=CONFIG['test_split'],
        random_state=SEED,
    )

    # Check all artifacts exist before proceeding
    missing = []
    for name in MODEL_LIST:
        p = os.path.join(CONFIG['checkpoint_dir'], f"{name}_val_preds.npz")
        if not os.path.exists(p):
            missing.append(name)
    if missing:
        log(f"❌ Missing val_preds.npz for: {missing}")
        log("   Run the corresponding train_*.py scripts first.")
        return

    log(f"\n{'='*80}")
    log(f"RQ1: 5-FOLD CV BACKBONE COMPARISON")
    log(f"{'='*80}")
    log(f"Criteria — AUC ≥ {CRITERIA['auc']},  "
        f"Sens ≥ {CRITERIA['sens']},  Spec ≥ {CRITERIA['spec']}\n")

    all_val_preds = {}
    summary = []
    for name in MODEL_LIST:
        npz = np.load(os.path.join(CONFIG['checkpoint_dir'], f"{name}_val_preds.npz"))
        val_preds = [npz[f'fold{i+1}'] for i in range(CONFIG['n_folds'])]
        all_val_preds[name] = val_preds
        m_auc, m_sens, m_spec = fold_metrics_at_05(val_preds, fold_indices, labels)

        pa  = m_auc  >= CRITERIA['auc']
        ps  = m_sens >= CRITERIA['sens']
        psp = m_spec >= CRITERIA['spec']
        qualifies = pa and ps and psp

        log(f"{name}:")
        log(f"  AUC  : {m_auc:.4f}  {'✓' if pa  else '✗'}")
        log(f"  Sens : {m_sens:.4f}  {'✓' if ps  else '✗'}")
        log(f"  Spec : {m_spec:.4f}  {'✓' if psp else '✗'}")
        log(f"  → ALL: {'PASS' if qualifies else 'FAIL'}\n")

        summary.append({
            'name':      name,
            'auc':       m_auc,
            'sens':      m_sens,
            'spec':      m_spec,
            'qualifies': qualifies,
        })

    # ── Per-fold breakdown ────────────────────────────────────────────────────
    log(f"\n{'='*80}")
    log(f"PER-FOLD DETAILS (threshold = 0.5)")
    log(f"{'='*80}")
    for name in MODEL_LIST:
        log(f"\n{name}:")
        log(f"  {'Fold':<6} {'AUC':>8} {'Sens':>8} {'Spec':>8}")
        log(f"  {'─'*34}")
        fold_aucs, fold_sens, fold_spec = [], [], []
        for i, fi in enumerate(fold_indices):
            yv = labels[fi['val_idx']]
            vp = all_val_preds[name][i]
            a = roc_auc_score(yv, vp)
            yb = (vp >= 0.5).astype(int)
            tp = int(np.sum((yb == 1) & (yv == 1)))
            fn = int(np.sum((yb == 0) & (yv == 1)))
            tn = int(np.sum((yb == 0) & (yv == 0)))
            fp = int(np.sum((yb == 1) & (yv == 0)))
            s  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            sp = tn / (tn + fp) if (tn + fp) > 0 else 0.0
            fold_aucs.append(a); fold_sens.append(s); fold_spec.append(sp)
            log(f"  Fold {i+1}  {a:>8.4f} {s:>8.4f} {sp:>8.4f}")
        log(f"  {'─'*34}")
        log(f"  {'Mean':<6} {np.mean(fold_aucs):>8.4f} "
            f"{np.mean(fold_sens):>8.4f} {np.mean(fold_spec):>8.4f}")
        log(f"  {'±Std':<6} {np.std(fold_aucs):>8.4f} "
            f"{np.std(fold_sens):>8.4f} {np.std(fold_spec):>8.4f}")

    log("")
    qualified = [s for s in summary if s['qualifies']]
    if qualified:
        best = max(qualified, key=lambda s: s['auc'])
        log(f"✓ {len(qualified)} backbone(s) passed criteria — selecting highest AUC")
    else:
        best = max(summary, key=lambda s: s['auc'])
        log(f"⚠ No backbone passed all criteria — selecting highest AUC as fallback")

    log(f"→ BEST BACKBONE: {best['name']}  "
        f"(AUC={best['auc']:.4f}, Sens={best['sens']:.4f}, Spec={best['spec']:.4f})\n")

    result = {
        'best_model': best['name'],
        'criteria':   CRITERIA,
        'comparison': summary,
    }
    out = os.path.join(CONFIG['results_dir'], 'rq1_results.json')
    with open(out, 'w') as f:
        json.dump(result, f, indent=2)
    log(f"✓ Results → {out}")


if __name__ == '__main__':
    main()
