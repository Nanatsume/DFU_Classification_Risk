"""RQ2: Final test set evaluation of S1_best and S2_best models.

For each input strategy, retrain the best combo (from RQ1) on the full
training set for the average stopping epochs from CV, then evaluate on
the held-out test set.

Reads  : results/rq1_results.json          (from rq1_compare.py)
         results/rq1/<combo_id>/best_params.json

Writes : results/rq2_results.json
         results/S1_best_test_probs.npy
         results/S2_best_test_probs.npy
         checkpoints/<combo_id>_final_retrain.keras  (for each)

Run after rq1_compare.py.
"""

import os
import gc
import json
import numpy as np
import tensorflow as tf
from sklearn.metrics import f1_score, confusion_matrix, roc_auc_score, classification_report
from scipy.stats import binom

from dfu_common import (
    CONFIG, SEED, make_logger, load_preprocessed_inaoe, create_fold_splits,
    DFUModelTrainer, base_model_creators,
)

DATA_SOURCE = {
    'S1': '/home/ntphoto/DFU/INAOE_S1',
    'S2': '/home/ntphoto/DFU/INAOE_S2',
}


def mcnemar_test(y_true, pred_a, pred_b):
    b = int(np.sum((pred_a == y_true) & (pred_b != y_true)))
    c = int(np.sum((pred_a != y_true) & (pred_b == y_true)))
    n = b + c
    if n == 0:
        return 1.0, b, c
    if n < 25:
        p = 2 * float(binom.cdf(min(b, c), n, 0.5))
        p = min(p, 1.0)
    else:
        stat = (abs(b - c) - 1) ** 2 / n
        from scipy.stats import chi2 as _chi2
        p = float(1 - _chi2.cdf(stat, df=1))
    return p, b, c


def delong_auc_pvalue(y_true, prob_a, prob_b):
    y = np.asarray(y_true)
    a = np.asarray(prob_a)
    b = np.asarray(prob_b)
    pos = np.where(y == 1)[0]
    neg = np.where(y == 0)[0]
    n1, n0 = len(pos), len(neg)

    def placement_values(scores, pos_idx, neg_idx):
        V10 = np.array([np.mean(scores[pos_idx[i]] > scores[neg_idx]) +
                        0.5 * np.mean(scores[pos_idx[i]] == scores[neg_idx])
                        for i in range(len(pos_idx))])
        V01 = np.array([np.mean(scores[neg_idx[j]] < scores[pos_idx]) +
                        0.5 * np.mean(scores[neg_idx[j]] == scores[pos_idx])
                        for j in range(len(neg_idx))])
        return V10, V01

    V10_a, V01_a = placement_values(a, pos, neg)
    V10_b, V01_b = placement_values(b, pos, neg)
    auc_a = V10_a.mean()
    auc_b = V10_b.mean()
    delta  = auc_a - auc_b
    S10    = np.cov(V10_a, V10_b) / n1
    S01    = np.cov(V01_a, V01_b) / n0
    S      = S10 + S01
    var_delta = S[0, 0] + S[1, 1] - 2 * S[0, 1]
    if var_delta <= 0:
        return 1.0, delta, 0.0
    z = delta / np.sqrt(var_delta)
    from scipy import stats
    p = float(2 * stats.norm.sf(abs(z)))
    return p, float(delta), float(z)


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


def retrain_and_eval(key, entry, log):
    """Retrain one best combo and evaluate on test set. Returns result dict."""
    combo_id       = entry['combo_id']
    backbone       = entry['backbone']
    strategy       = entry['strategy']
    input_strategy = entry['input_strategy']
    avg_epochs     = entry.get('avg_epochs', {})
    avg_p1         = avg_epochs.get('phase1') or CONFIG['max_epochs']
    avg_p2         = avg_epochs.get('phase2') or 0
    threshold      = 0.5

    log(f"\n{'#'*80}")
    log(f"# RQ2: {key} — {combo_id}")
    log(f"# Strategy: {strategy}  |  Phase1 epochs: {avg_p1}  |  Phase2 epochs: {avg_p2}")
    log(f"{'#'*80}")

    # ── Load hyperparameters ──────────────────────────────────────────────────
    bp_path = os.path.join(CONFIG['results_dir'], 'rq1', combo_id, 'best_params.json')
    if not os.path.exists(bp_path):
        log(f"❌ {bp_path} not found.")
        return None
    with open(bp_path) as f:
        best_params = json.load(f)

    # ── Load data ─────────────────────────────────────────────────────────────
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

    final_ckpt = os.path.join(CONFIG['checkpoint_dir'],
                              f'{combo_id}_final_retrain.keras')

    # ── Retrain on full training set (skip if checkpoint exists) ─────────────
    if os.path.exists(final_ckpt):
        log(f"✓ Checkpoint found — skipping retrain: {final_ckpt}")
        loaded_model = tf.keras.models.load_model(final_ckpt)

        probs_path = os.path.join(CONFIG['results_dir'], f'{key}_test_probs.npy')
        probs = loaded_model.predict(X_test, verbose=0).flatten()
        metrics = full_metrics(y_test, probs, threshold)
        for k in ['sensitivity', 'specificity', 'auc_roc', 'ppv', 'npv', 'f1']:
            log(f"  {k:<14}: {metrics[k]:.4f}")
        np.save(probs_path, probs)
        log(f"✓ Test probs → {probs_path}")

        del loaded_model
        tf.keras.backend.clear_session()
        gc.collect()

        return {
            'combo_id':       combo_id,
            'backbone':       backbone,
            'strategy':       strategy,
            'input_strategy': input_strategy,
            'retrain_epochs': {'phase1': avg_p1, 'phase2': avg_p2},
            'threshold':      threshold,
            'cv_metrics':     entry.get('cv_metrics', {}),
            'test_metrics':   metrics,
            'final_model':    final_ckpt,
            'test_probs_path': probs_path,
        }
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

    # ── Evaluate on test set ──────────────────────────────────────────────────
    log(f"\n{'='*80}")
    log(f"TEST SET EVALUATION — {combo_id}  threshold={threshold:.4f}")
    log(f"{'='*80}")

    probs   = trainer.get_predictions(X_test)
    metrics = full_metrics(y_test, probs, threshold)

    for k in ['sensitivity', 'specificity', 'auc_roc', 'ppv', 'npv', 'f1']:
        log(f"  {k:<14}: {metrics[k]:.4f}")

    yb = (probs >= threshold).astype(int)
    log(f"\nConfusion Matrix:\n{confusion_matrix(y_test, yb)}")
    log(f"\nClassification Report:\n"
        f"{classification_report(y_test, yb, target_names=['CT', 'DM'], digits=4, zero_division=0)}")

    # Save probs
    probs_path = os.path.join(CONFIG['results_dir'], f'{key}_test_probs.npy')
    np.save(probs_path, probs)
    log(f"✓ Test probs → {probs_path}")

    del trainer, base
    tf.keras.backend.clear_session()
    gc.collect()

    return {
        'combo_id':       combo_id,
        'backbone':       backbone,
        'strategy':       strategy,
        'input_strategy': input_strategy,
        'retrain_epochs': {'phase1': avg_p1, 'phase2': avg_p2},
        'threshold':      threshold,
        'cv_metrics':     entry.get('cv_metrics', {}),
        'test_metrics':   metrics,
        'final_model':    final_ckpt,
        'test_probs_path': probs_path,
    }


def main():
    log = make_logger('rq2')

    rq1_path = os.path.join(CONFIG['results_dir'], 'rq1_results.json')
    if not os.path.exists(rq1_path):
        log("❌ rq1_results.json not found. Run rq1_compare.py first.")
        return
    with open(rq1_path) as f:
        rq1 = json.load(f)

    # ── Derive RQ2 comparison pair ────────────────────────────────────────────
    # Fix the best backbone from RQ1, then find the strategy with the highest
    # average mean AUC across S1 and S2 for that backbone.
    # This isolates orientation as the only variable in the comparison.
    best_backbone = rq1['S2_best']['backbone']  # overall best backbone
    results_dir = os.path.join(CONFIG['results_dir'], 'rq1')
    strategies = ['FT', 'LP', 'G-LF', 'G-FL', 'LP-FT', 'L1-SP', 'L2-SP', 'Auto-RGN']

    best_strategy, best_avg = None, -1.0
    for st in strategies:
        aucs = []
        for s in ['S1', 'S2']:
            combo = f"{best_backbone}_{st}_{s}"
            mpath = os.path.join(results_dir, combo, 'metrics.json')
            if os.path.exists(mpath):
                aucs.append(json.load(open(mpath))['mean']['auc'])
        if len(aucs) == 2:
            avg = sum(aucs) / 2
            if avg > best_avg:
                best_avg = avg
                best_strategy = st

    log(f"RQ2 pair: {best_backbone} + {best_strategy} (avg AUC across S1/S2 = {best_avg:.4f})")

    output = {}
    for s, key in [('S1', 'S1_best'), ('S2', 'S2_best')]:
        combo_id = f"{best_backbone}_{best_strategy}_{s}"
        mpath = os.path.join(results_dir, combo_id, 'metrics.json')
        m = json.load(open(mpath))
        entry = {
            'combo_id':       combo_id,
            'backbone':       best_backbone,
            'strategy':       best_strategy,
            'input_strategy': s,
            'avg_epochs':     m.get('avg_epochs', {}),
            'cv_metrics':     {'mean': m['mean'], 'std': m['std']},
        }
        result = retrain_and_eval(key, entry, log)
        if result is not None:
            output[key] = result

    # ── Summary comparison ────────────────────────────────────────────────────
    if 'S1_best' in output and 'S2_best' in output:
        log(f"\n{'='*80}")
        log(f"RQ2: S1_best vs S2_best — TEST SET COMPARISON")
        log(f"{'='*80}")
        log(f"{'Metric':<14}  {'S1_best':>22}  {'S2_best':>22}  {'Δ (S2−S1)':>10}")
        log('─' * 74)
        for m in ['sensitivity', 'specificity', 'auc_roc', 'ppv', 'npv', 'f1']:
            v1 = output['S1_best']['test_metrics'][m]
            v2 = output['S2_best']['test_metrics'][m]
            log(f"{m:<14}  {v1:>22.4f}  {v2:>22.4f}  {v2 - v1:>+10.4f}")
        log(f"\n  S1_best: {output['S1_best']['combo_id']}")
        log(f"  S2_best: {output['S2_best']['combo_id']}")

    # ── Statistical tests ─────────────────────────────────────────────────────
    if 'S1_best' in output and 'S2_best' in output:
        s1_probs_path = output['S1_best']['test_probs_path']
        s2_probs_path = output['S2_best']['test_probs_path']

        data_path = DATA_SOURCE[output['S1_best']['input_strategy']]
        images, labels = load_preprocessed_inaoe(data_path, log=lambda x: None)
        _, test_indices = create_fold_splits(
            images, labels,
            n_splits=CONFIG['n_folds'],
            test_split=CONFIG['test_split'],
            random_state=SEED,
        )
        y_test = labels[test_indices]

        s1_probs = np.load(s1_probs_path)
        s2_probs = np.load(s2_probs_path)
        s1_bin = (s1_probs >= 0.5).astype(int)
        s2_bin = (s2_probs >= 0.5).astype(int)

        p_mc, b, c = mcnemar_test(y_test, s1_bin, s2_bin)
        p_dl, delta_auc, z_stat = delong_auc_pvalue(y_test, s1_probs, s2_probs)

        log(f"\n{'='*80}")
        log(f"RQ2: STATISTICAL SIGNIFICANCE TESTS (threshold = 0.5)")
        log(f"{'='*80}")
        log(f"McNemar's Test  (H0: S1 and S2 have equal error rates)")
        log(f"  Discordant pairs: S1 correct & S2 wrong (b)={b},  S1 wrong & S2 correct (c)={c}")
        log(f"  p-value = {p_mc:.4f}  {'*significant* (p < 0.05)' if p_mc < 0.05 else 'not significant'}")
        log(f"DeLong's Test   (H0: AUC_S1 = AUC_S2)")
        log(f"  ΔAUC (S1−S2) = {delta_auc:+.4f},  z = {z_stat:.4f}")
        log(f"  p-value = {p_dl:.4f}  {'*significant* (p < 0.05)' if p_dl < 0.05 else 'not significant'}")

        output['statistical_tests'] = {
            'mcnemar': {'b': b, 'c': c, 'p_value': p_mc, 'significant': p_mc < 0.05},
            'delong':  {'delta_auc': delta_auc, 'z_stat': z_stat, 'p_value': p_dl,
                        'significant': p_dl < 0.05},
        }

    out_path = os.path.join(CONFIG['results_dir'], 'rq2_results.json')
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    log(f"\n✓ Results → {out_path}")


if __name__ == '__main__':
    main()
