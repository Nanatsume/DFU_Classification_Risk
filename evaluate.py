"""Compare 3 models, optimize threshold for best, retrain on full train, evaluate on test set.
Run after train_efficientnet.py / train_resnet.py / train_convnext.py have completed."""

import os
import json
import gc
import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, roc_curve, roc_auc_score, classification_report,
)

from dfu_common import (
    CONFIG, SEED, make_logger, load_preprocessed_inaoe, create_fold_splits,
    base_model_creators, DFUModelTrainer,
)

CRITERIA = {
    'auc_threshold':         0.8,
    'sensitivity_threshold': 0.85,
    'specificity_threshold': 0.7,
}

MODEL_LIST = [
    ('EfficientNetB0',  'EfficientNetB0'),
    ('ResNet50',        'ResNet50'),
    ('ConvNeXt-Tiny',   'ConvNeXt-Tiny'),
]


def load_model_artifacts(model_name, n_folds, log):
    ckpt_dir = CONFIG['checkpoint_dir']
    bp_path  = os.path.join(ckpt_dir, f"{model_name}_best_params.json")
    vp_path  = os.path.join(ckpt_dir, f"{model_name}_val_preds.npz")
    if not os.path.exists(bp_path):
        log(f"⚠ {model_name}: missing {bp_path} — run train_*.py first")
        return None
    if not os.path.exists(vp_path):
        log(f"⚠ {model_name}: missing {vp_path} — run train_*.py first")
        return None
    with open(bp_path) as f:
        best_params = json.load(f)
    npz = np.load(vp_path)
    fold_val_preds = [npz[f'fold{i+1}'] for i in range(n_folds)]
    return {'best_params': best_params, 'fold_val_predictions': fold_val_preds}


def compute_mean_cv_metrics(fold_val_predictions, fold_indices, y_full):
    aucs, sens, specs = [], [], []
    for fi, vp in zip(fold_indices, fold_val_predictions):
        yv = y_full[fi['val_idx']]
        aucs.append(roc_auc_score(yv, vp))
        yb = (vp >= 0.5).astype(int)
        tp = int(np.sum((yb == 1) & (yv == 1)))
        fn = int(np.sum((yb == 0) & (yv == 1)))
        tn = int(np.sum((yb == 0) & (yv == 0)))
        fp = int(np.sum((yb == 1) & (yv == 0)))
        sens.append(tp / (tp + fn) if (tp + fn) > 0 else 0.0)
        specs.append(tn / (tn + fp) if (tn + fp) > 0 else 0.0)
    return float(np.mean(aucs)), float(np.mean(sens)), float(np.mean(specs))


def optimize_threshold_per_fold(y_true, y_pred, target_sensitivity=0.85):
    fpr, tpr, thresholds = roc_curve(y_true, y_pred)
    valid = []
    for i, t in enumerate(thresholds):
        if tpr[i] >= target_sensitivity:
            valid.append({'threshold': t, 'sensitivity': tpr[i], 'specificity': 1 - fpr[i]})
    if not valid:
        return float(thresholds[np.argmax(tpr)]), fpr, tpr, thresholds
    return float(max(valid, key=lambda x: x['specificity'])['threshold']), fpr, tpr, thresholds


def main():
    log = make_logger('evaluate')

    # ── Reproduce data + splits ──
    images, labels = load_preprocessed_inaoe(CONFIG['data_source'], log=log)
    X_full, y_full = images, labels
    fold_indices, test_indices = create_fold_splits(
        X_full, y_full, n_splits=CONFIG['n_folds'],
        test_split=CONFIG['test_split'], random_state=SEED,
    )
    X_test, y_test = X_full[test_indices], y_full[test_indices]
    log(f"Test set: {len(y_test)} samples (DM={int(np.sum(y_test==1))}, CT={int(np.sum(y_test==0))})")

    # ── Load each model's artifacts ──
    artifacts = {}
    for name, _ in MODEL_LIST:
        a = load_model_artifacts(name, CONFIG['n_folds'], log)
        if a is None:
            log(f"❌ Missing artifacts for {name}. Aborting.")
            return
        artifacts[name] = a

    # ── 1. Comparison + best model selection ──
    log(f"\n{'='*80}\n5-FOLD CV COMPARISON\n{'='*80}")
    log(f"Criteria: AUC>{CRITERIA['auc_threshold']}, "
        f"Sens>{CRITERIA['sensitivity_threshold']}, Spec>{CRITERIA['specificity_threshold']}\n")

    summary = []
    for name, _ in MODEL_LIST:
        m_auc, m_sens, m_spec = compute_mean_cv_metrics(
            artifacts[name]['fold_val_predictions'], fold_indices, y_full)
        pa = m_auc  > CRITERIA['auc_threshold']
        ps = m_sens > CRITERIA['sensitivity_threshold']
        psp= m_spec > CRITERIA['specificity_threshold']
        q = pa and ps and psp
        log(f"{name}:")
        log(f"  AUC  : {m_auc:.4f} {'✓' if pa else '✗'}")
        log(f"  Sens : {m_sens:.4f} {'✓' if ps else '✗'}")
        log(f"  Spec : {m_spec:.4f} {'✓' if psp else '✗'}")
        log(f"  → ALL: {'YES' if q else 'NO'}\n")
        summary.append({'name': name, 'auc': m_auc, 'sens': m_sens, 'spec': m_spec, 'qualifies': q})

    qualified = [s for s in summary if s['qualifies']]
    if qualified:
        best = max(qualified, key=lambda s: s['auc'])
        log(f"✓ {len(qualified)} model(s) passed — picking highest AUC")
    else:
        best = max(summary, key=lambda s: s['auc'])
        log(f"⚠ No model passed criteria — falling back to highest AUC")
    best_name = best['name']
    log(f"→ BEST MODEL: {best_name} (AUC={best['auc']:.4f}, Sens={best['sens']:.4f}, Spec={best['spec']:.4f})\n")

    # ── 2. Threshold optimization (best model only) ──
    log(f"\n{'='*80}\nTHRESHOLD OPTIMIZATION — {best_name}\n{'='*80}")
    fold_thresholds = []
    for i, (fi, vp) in enumerate(zip(fold_indices, artifacts[best_name]['fold_val_predictions'])):
        yv = y_full[fi['val_idx']]
        t, fpr, tpr, thr = optimize_threshold_per_fold(yv, vp)
        fold_thresholds.append(t)
        yb = (vp >= t).astype(int)
        s = recall_score(yv, yb, zero_division=0)
        sp = 1 - fpr[np.argmin(np.abs(thr - t))]
        log(f"  Fold {i+1}: threshold={t:.4f}  Sens={s:.4f}  Spec={sp:.4f}")
    mean_threshold = float(np.mean(fold_thresholds))
    log(f"\n✓ Mean threshold: {mean_threshold:.4f}")

    # ── 3. Retrain best model on full train set ──
    log(f"\n{'='*80}\nRETRAIN {best_name} ON FULL TRAIN SET\n{'='*80}")
    train_mask = np.ones(len(y_full), dtype=bool)
    train_mask[test_indices] = False
    X_train_full, y_train_full = X_full[train_mask], y_full[train_mask]
    log(f"Full train: {len(y_train_full)}  |  Test: {len(y_test)}")

    X_tr, X_iv, y_tr, y_iv = train_test_split(
        X_train_full, y_train_full, test_size=0.1,
        stratify=y_train_full, random_state=SEED,
    )
    log(f"Retrain split: train={len(y_tr)}  internal-val={len(y_iv)}")

    final_ckpt = os.path.join(CONFIG['checkpoint_dir'], f"{best_name}_FINAL.keras")
    if os.path.exists(final_ckpt):
        log(f"✓ Loading existing final model: {final_ckpt}")
        final_model = tf.keras.models.load_model(final_ckpt)
    else:
        bp = artifacts[best_name]['best_params']
        base_fn = base_model_creators()[best_name]
        base = base_fn()
        ft = DFUModelTrainer(
            model_name=f"{best_name}_FINAL",
            base_model=base,
            dropout_rate=bp['dropout_rate'],
            l2_reg=bp['l2_reg'],
            dense_units=(bp['dense_units_1'], bp['dense_units_2']),
            log=log,
        )
        ft.build_model()
        ft.train_phase1(X_tr, y_tr, X_iv, y_iv,
                        batch_size=bp['batch_size'], optimizer=bp['optimizer'],
                        learning_rate=bp['phase1_lr'], max_epochs=CONFIG['max_epochs'],
                        patience=CONFIG['phase1_patience'], verbose=1)
        ft.train_phase2(X_tr, y_tr, X_iv, y_iv,
                        batch_size=bp['batch_size'], optimizer=bp['optimizer'],
                        learning_rate=bp['phase2_lr'], max_epochs=CONFIG['max_epochs'],
                        patience=CONFIG['phase2_patience'], verbose=1)
        ft.save_model(final_ckpt)
        final_model = ft.model
        del ft, base
        gc.collect()

    # ── 4. Evaluate on test set ──
    log(f"\n{'='*80}\nTEST SET EVALUATION (threshold={mean_threshold:.4f})\n{'='*80}")
    probs = final_model.predict(X_test, verbose=0).flatten()
    yp = (probs >= mean_threshold).astype(int)

    tn = int(np.sum((yp == 0) & (y_test == 0)))
    fp = int(np.sum((yp == 1) & (y_test == 0)))
    tp = int(np.sum((yp == 1) & (y_test == 1)))
    fn = int(np.sum((yp == 0) & (y_test == 1)))
    spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    ppv  = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    npv  = tn / (tn + fn) if (tn + fn) > 0 else 0.0

    metrics = {
        'model':       best_name,
        'threshold':   mean_threshold,
        'accuracy':    accuracy_score(y_test, yp),
        'precision':   precision_score(y_test, yp, zero_division=0),
        'recall':      recall_score(y_test, yp, zero_division=0),
        'sensitivity': recall_score(y_test, yp, zero_division=0),
        'specificity': spec,
        'ppv':         ppv,
        'npv':         npv,
        'f1':          f1_score(y_test, yp, zero_division=0),
        'auc_roc':     roc_auc_score(y_test, probs),
    }
    for k, v in metrics.items():
        log(f"  {k:12s}: {v:.4f}" if isinstance(v, float) else f"  {k:12s}: {v}")
    log(f"\nConfusion Matrix:\n{confusion_matrix(y_test, yp)}")
    log(f"\nClassification Report:\n{classification_report(y_test, yp, digits=4, zero_division=0)}")

    out_csv = os.path.join(CONFIG['results_dir'], 'final_test_results.csv')
    pd.DataFrame([metrics]).set_index('model').to_csv(out_csv)
    log(f"✓ Results → {out_csv}")


if __name__ == '__main__':
    main()
