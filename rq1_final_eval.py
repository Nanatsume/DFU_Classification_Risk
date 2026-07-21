"""Final test set evaluation of the best CNN model (S2_best from RQ1).

Retrains the best configuration identified in RQ1 on the full 80% training
set using the average stopping epochs from cross-validation, then evaluates
on the held-out test set and saves the test probabilities for use in RQ2.

Reads  : results/rq1_results.json          (from rq1_compare.py)
         results/rq1/<combo_id>/best_params.json
         results/rq1/<combo_id>/metrics.json

Writes : results/S2_best_test_probs.npy
         checkpoints/<combo_id>_final_retrain.keras

Run after rq1_compare.py and before rq2_comparison.py.
"""

import os
import gc
import json
import numpy as np
import tensorflow as tf
from sklearn.metrics import f1_score, confusion_matrix, roc_auc_score, classification_report

from dfu_common import (
    CONFIG, SEED, make_logger, load_preprocessed_inaoe, create_fold_splits,
    DFUModelTrainer, base_model_creators,
)

DATA_SOURCE = {
    'S1': '/home/ntphoto/DFU/INAOE_S1',
    'S2': '/home/ntphoto/DFU/INAOE_S2',
}


def full_metrics(y_true, y_prob, threshold=0.5):
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
    log = make_logger('rq1_final_eval')

    rq1_path = os.path.join(CONFIG['results_dir'], 'rq1_results.json')
    if not os.path.exists(rq1_path):
        log("❌ rq1_results.json not found. Run rq1_compare.py first.")
        return
    with open(rq1_path) as f:
        rq1 = json.load(f)

    entry = rq1.get('S2_best')
    if entry is None:
        log("❌ S2_best not found in rq1_results.json.")
        return

    combo_id       = entry['combo_id']
    backbone       = entry['backbone']
    strategy       = entry['strategy']
    input_strategy = entry['input_strategy']

    mpath = os.path.join(CONFIG['results_dir'], 'rq1', combo_id, 'metrics.json')
    if not os.path.exists(mpath):
        log(f"❌ metrics.json not found for {combo_id}.")
        return
    with open(mpath) as f:
        m = json.load(f)
    avg_epochs = m.get('avg_epochs', {})
    avg_p1 = avg_epochs.get('phase1') or CONFIG['max_epochs']
    avg_p2 = avg_epochs.get('phase2') or 0

    bp_path = os.path.join(CONFIG['results_dir'], 'rq1', combo_id, 'best_params.json')
    if not os.path.exists(bp_path):
        log(f"❌ best_params.json not found for {combo_id}.")
        return
    with open(bp_path) as f:
        best_params = json.load(f)

    log(f"\n{'#'*80}")
    log(f"# RQ1 Final Eval: {combo_id}")
    log(f"# Strategy: {strategy}  |  Phase1 epochs: {avg_p1}  |  Phase2 epochs: {avg_p2}")
    log(f"{'#'*80}")

    data_path = DATA_SOURCE[input_strategy]
    images, labels = load_preprocessed_inaoe(data_path, log=log)
    fold_indices, test_indices = create_fold_splits(
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
        f"(DM={int(np.sum(y_train == 1))}, CT={int(np.sum(y_train == 0))})")
    log(f"Test set   : {len(y_test)}  "
        f"(DM={int(np.sum(y_test == 1))},  CT={int(np.sum(y_test == 0))})")

    final_ckpt  = os.path.join(CONFIG['checkpoint_dir'], f'{combo_id}_final_retrain.keras')
    probs_path  = os.path.join(CONFIG['results_dir'], 'S2_best_test_probs.npy')
    threshold   = 0.5

    if os.path.exists(final_ckpt):
        log(f"✓ Checkpoint found — skipping retrain: {final_ckpt}")
        loaded_model = tf.keras.models.load_model(final_ckpt)
        probs = loaded_model.predict(X_test, verbose=0).flatten()
        del loaded_model
        tf.keras.backend.clear_session()
        gc.collect()
    else:
        if backbone == 'ConvNeXt-Tiny':
            CONFIG['batch_size_default'] = 32
        else:
            CONFIG['batch_size_default'] = 64
        best_params.setdefault('batch_size', CONFIG['batch_size_default'])

        base_model_fn = base_model_creators()[backbone]
        base          = base_model_fn()
        trainer       = DFUModelTrainer(
            model_name=f'{combo_id}_final',
            base_model=base,
            dropout_rate=best_params['dropout_rate'],
            l2_reg=best_params['l2_reg'],
            dense_units=(best_params['dense_units_1'], best_params['dense_units_2']),
            log=log,
            backbone_name=backbone,
        )
        trainer.build_model()
        trainer.retrain_fixed(
            strategy=strategy,
            X_tr=X_train,
            y_tr=y_train,
            params=best_params,
            epochs_p1=avg_p1,
            epochs_p2=avg_p2,
            verbose=1,
        )
        trainer.save_model(final_ckpt)
        log(f"✓ Model saved → {final_ckpt}")
        probs = trainer.get_predictions(X_test)
        del trainer, base
        tf.keras.backend.clear_session()
        gc.collect()

    metrics = full_metrics(y_test, probs, threshold)

    log(f"\n{'='*80}")
    log(f"TEST SET EVALUATION — {combo_id}  threshold={threshold:.4f}")
    log(f"{'='*80}")
    for k in ['sensitivity', 'specificity', 'auc_roc', 'ppv', 'npv', 'f1']:
        log(f"  {k:<14}: {metrics[k]:.4f}")
    yb = (probs >= threshold).astype(int)
    log(f"\nConfusion Matrix:\n{confusion_matrix(y_test, yb)}")
    log(f"\nClassification Report:\n"
        f"{classification_report(y_test, yb, target_names=['CT', 'DM'], digits=4, zero_division=0)}")

    np.save(probs_path, probs)
    log(f"\n✓ Test probs → {probs_path}")


if __name__ == '__main__':
    main()
