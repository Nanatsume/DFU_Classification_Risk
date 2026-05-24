"""Final Evaluation: Test set performance of the proposed model.

Strategy:
  1. Identify best backbone from RQ1.
  2. Load average stopping epoch per phase from K-fold CV (saved by train_one_model).
  3. Retrain on the FULL training set (267 samples, no validation split) for exactly
     those many epochs — no early stopping.
  4. Evaluate on the held-out test set using the mean Youden's Index threshold.

Metrics reported: Sensitivity, Specificity, AUC-ROC, PPV, NPV, F1-Score.
Saves results to results/final_eval_results.json and results/final_eval_probs.npy.
Run after threshold_optimization.py.
"""

import os
import json
import numpy as np
import tensorflow as tf
from sklearn.metrics import (
    f1_score, confusion_matrix, roc_auc_score,
    classification_report,
)

from dfu_common import (
    CONFIG, SEED, make_logger, load_preprocessed_inaoe, create_fold_splits,
    DFUModelTrainer, base_model_creators,
)


def full_metrics(y_true, y_prob, threshold):
    yb = (y_prob >= threshold).astype(int)
    tp = int(np.sum((yb == 1) & (y_true == 1)))
    fn = int(np.sum((yb == 0) & (y_true == 1)))
    tn = int(np.sum((yb == 0) & (y_true == 0)))
    fp = int(np.sum((yb == 1) & (y_true == 0)))
    return {
        'sensitivity': tp / (tp + fn) if (tp + fn) > 0 else 0.0,
        'specificity': tn / (tn + fp) if (tn + fp) > 0 else 0.0,
        'ppv':         tp / (tp + fp) if (tp + fp) > 0 else 0.0,
        'npv':         tn / (tn + fn) if (tn + fn) > 0 else 0.0,
        'f1':          float(f1_score(y_true, yb, zero_division=0)),
        'auc_roc':     float(roc_auc_score(y_true, y_prob)),
    }


def main():
    log = make_logger('rq3')

    # ── Load prerequisites ────────────────────────────────────────────────────
    for fname, label in [('rq1_results.json', 'RQ1'), ('threshold_results.json', 'Threshold')]:
        p = os.path.join(CONFIG['results_dir'], fname)
        if not os.path.exists(p):
            log(f"❌ {fname} not found. Run {label} script first.")
            return

    with open(os.path.join(CONFIG['results_dir'], 'rq1_results.json')) as f:
        rq1 = json.load(f)
    with open(os.path.join(CONFIG['results_dir'], 'threshold_results.json')) as f:
        thr_data = json.load(f)

    best_model = rq1['best_model']
    threshold  = thr_data['mean_youden_threshold']
    log(f"Best backbone : {best_model}")
    log(f"Threshold     : {threshold:.4f}  (mean Youden's J)")

    # ── Load average stopping epochs from K-fold CV ───────────────────────────
    avg_epochs_path = os.path.join(CONFIG['checkpoint_dir'],
                                   f"{best_model}_avg_epochs.json")
    if not os.path.exists(avg_epochs_path):
        log(f"❌ {avg_epochs_path} not found.")
        log(f"   Delete existing fold checkpoints and re-run rq1_backbone_comparison.py "
            f"so that epoch history is recorded fresh.")
        return
    with open(avg_epochs_path) as f:
        avg_epochs = json.load(f)
    avg_p1 = avg_epochs['avg_phase1']
    avg_p2 = avg_epochs['avg_phase2']
    n_used = avg_epochs.get('n_folds_used', '?')
    log(f"Avg stop epoch: phase1={avg_p1}, phase2={avg_p2}  (from {n_used} folds)")

    # ── Load best hyperparameters ─────────────────────────────────────────────
    bp_path = os.path.join(CONFIG['checkpoint_dir'], f"{best_model}_best_params.json")
    if not os.path.exists(bp_path):
        log(f"❌ {bp_path} not found.")
        return
    with open(bp_path) as f:
        best_params = json.load(f)

    # ── Reproduce data splits (same SEED → identical indices) ─────────────────
    images, labels = load_preprocessed_inaoe(CONFIG['data_source'], log=log)
    _, test_indices = create_fold_splits(
        images, labels,
        n_splits=CONFIG['n_folds'],
        test_split=CONFIG['test_split'],
        random_state=SEED,
    )

    train_mask = np.ones(len(labels), dtype=bool)
    train_mask[test_indices] = False
    X_train, y_train = images[train_mask], labels[train_mask]
    X_test,  y_test  = images[test_indices], labels[test_indices]

    log(f"Full train : {len(y_train)}  "
        f"(DM={int(np.sum(y_train==1))}, CT={int(np.sum(y_train==0))})")
    log(f"Test set   : {len(y_test)}  "
        f"(DM={int(np.sum(y_test==1))},  CT={int(np.sum(y_test==0))})")

    # ── Final retraining on full training set ─────────────────────────────────
    log(f"\n{'='*80}")
    log(f"RQ3: FINAL RETRAINING — {best_model}  "
        f"({len(X_train)} samples, phase1={avg_p1} ep, phase2={avg_p2} ep)")
    log(f"{'='*80}")

    base = base_model_creators()[best_model]()
    trainer = DFUModelTrainer(
        model_name=f"{best_model}_final",
        base_model=base,
        dropout_rate=best_params['dropout_rate'],
        l2_reg=best_params['l2_reg'],
        dense_units=(best_params['dense_units_1'], best_params['dense_units_2']),
        log=log,
    )
    trainer.build_model()
    trainer.train_phase1(X_train, y_train,
                         batch_size=best_params['batch_size'],
                         optimizer=best_params['optimizer'],
                         learning_rate=best_params['phase1_lr'],
                         fixed_epochs=avg_p1,
                         verbose=1)
    trainer.train_phase2(X_train, y_train,
                         batch_size=best_params['batch_size'],
                         optimizer=best_params['optimizer'],
                         learning_rate=best_params['phase2_lr'],
                         fixed_epochs=avg_p2,
                         verbose=1)

    final_ckpt = os.path.join(CONFIG['checkpoint_dir'],
                              f"{best_model}_final_retrain.keras")
    trainer.save_model(final_ckpt)

    # ── Evaluate on test set ──────────────────────────────────────────────────
    log(f"\n{'='*80}")
    log(f"FINAL EVALUATION: TEST SET — {best_model}  threshold={threshold:.4f}")
    log(f"{'='*80}")

    probs   = trainer.get_predictions(X_test)
    np.save(os.path.join(CONFIG['results_dir'], 'final_eval_probs.npy'), probs)
    metrics = full_metrics(y_test, probs, threshold)

    metric_order = ['sensitivity', 'specificity', 'auc_roc', 'ppv', 'npv', 'f1']
    for k in metric_order:
        log(f"  {k:<14}: {metrics[k]:.4f}")

    yb = (probs >= threshold).astype(int)
    log(f"\nConfusion Matrix:\n{confusion_matrix(y_test, yb)}")
    report = classification_report(y_test, yb, target_names=['CT', 'DM'],
                                   digits=4, zero_division=0)
    log(f"\nClassification Report:\n{report}")

    result = {
        'best_model':     best_model,
        'retrain_epochs': {'phase1': avg_p1, 'phase2': avg_p2},
        'threshold':      threshold,
        'test_metrics':   metrics,
    }
    out = os.path.join(CONFIG['results_dir'], 'final_eval_results.json')
    with open(out, 'w') as f:
        json.dump(result, f, indent=2)
    log(f"✓ Results → {out}")


if __name__ == '__main__':
    main()
