"""RQ2 Comparison: CNN proposed model vs Baseline (Khandakar pipeline).

Reads the test probabilities saved by rq1_final_eval.py and rq2_baseline.py,
computes all metrics for both models, and runs McNemar's test restricted to
DM-positive patients (sensitivity McNemar) as the primary statistical test.
This design aligns with the study objective: DFU risk screening prioritises
detecting at-risk patients (sensitivity) over rejecting healthy ones.

Reads  : results/S2_best_test_probs.npy     (from rq1_final_eval.py)
         results/rq2_best_test_probs.npy    (from rq2_baseline.py)
         results/rq1_results.json           (CNN model id and CV metrics)
         results/rq2_baseline_results.json  (best combination and baseline details)

Writes : results/rq2_results.json

Run after rq1_final_eval.py and rq2_baseline.py.
"""

import os
import json
import numpy as np
from scipy.stats import binom
from sklearn.metrics import roc_auc_score, f1_score

from dfu_common import (
    CONFIG, SEED, make_logger, load_preprocessed_inaoe, create_fold_splits,
)

DATA_SOURCE = {
    'S1': '/home/ntphoto/DFU/INAOE_S1',
    'S2': '/home/ntphoto/DFU/INAOE_S2',
}


def metrics_at(y_true, y_prob, threshold, allow_nan=False):
    yb = (y_prob >= threshold).astype(int)
    tp = int(np.sum((yb == 1) & (y_true == 1)))
    fn = int(np.sum((yb == 0) & (y_true == 1)))
    tn = int(np.sum((yb == 0) & (y_true == 0)))
    fp = int(np.sum((yb == 1) & (y_true == 0)))
    nan = float('nan')
    try:
        auc = float(roc_auc_score(y_true, y_prob))
    except ValueError:
        auc = nan
    return {
        'sensitivity': tp / (tp + fn) if (tp + fn) > 0 else (nan if allow_nan else 0.0),
        'specificity': tn / (tn + fp) if (tn + fp) > 0 else (nan if allow_nan else 0.0),
        'ppv':         tp / (tp + fp) if (tp + fp) > 0 else (nan if allow_nan else 0.0),
        'npv':         tn / (tn + fn) if (tn + fn) > 0 else (nan if allow_nan else 0.0),
        'f1':          float(f1_score(y_true, yb, zero_division=0)),
        'auc_roc':     auc,
    }


def bootstrap_ci(y_true, y_prob, threshold, n_bootstrap=2000, seed=42):
    """Stratified bootstrap 95% CI for all metrics.

    Resamples CT and DM patients separately to preserve class balance,
    then takes the 2.5th–97.5th percentile of the bootstrap distribution.
    """
    rng       = np.random.default_rng(seed)
    ct_idx    = np.where(y_true == 0)[0]
    dm_idx    = np.where(y_true == 1)[0]
    metrics   = ['sensitivity', 'specificity', 'ppv', 'npv', 'f1', 'auc_roc']
    dist      = {m: [] for m in metrics}

    for _ in range(n_bootstrap):
        idx = np.concatenate([
            rng.choice(ct_idx, size=len(ct_idx), replace=True),
            rng.choice(dm_idx, size=len(dm_idx), replace=True),
        ])
        m = metrics_at(y_true[idx], y_prob[idx], threshold, allow_nan=True)
        for k in metrics:
            dist[k].append(m[k])

    ci = {}
    for k in metrics:
        vals = np.array(dist[k], dtype=float)
        lo   = float(np.nanpercentile(vals, 2.5))
        hi   = float(np.nanpercentile(vals, 97.5))
        ci[k] = [round(lo, 4), round(hi, 4)]
    return ci


def mcnemar_sensitivity(y_true, pred_a, pred_b):
    """McNemar's test on DM-positive patients only (sensitivity McNemar).

    Restricts comparison to samples where y=1 (DM patients) so the test
    directly measures whether the two models differ in sensitivity — i.e.,
    whether one model misses more at-risk patients than the other.

    b = CNN catches the DM patient, Baseline misses (CNN sens > Baseline sens)
    c = CNN misses the DM patient, Baseline catches (Baseline sens > CNN sens)
    """
    dm_mask = (y_true == 1)
    y_dm    = y_true[dm_mask]
    a_dm    = pred_a[dm_mask]
    b_dm    = pred_b[dm_mask]
    b = int(np.sum((a_dm == y_dm) & (b_dm != y_dm)))
    c = int(np.sum((a_dm != y_dm) & (b_dm == y_dm)))
    n = b + c
    if n == 0:
        return 1.0, b, c, int(dm_mask.sum())
    if n < 25:
        p = 2 * float(binom.cdf(min(b, c), n, 0.5))
        p = min(p, 1.0)
    else:
        stat = (abs(b - c) - 1) ** 2 / n
        from scipy.stats import chi2
        p = float(1 - chi2.cdf(stat, df=1))
    return p, b, c, int(dm_mask.sum())


def main():
    log = make_logger('rq2_compare')

    rq1_path = os.path.join(CONFIG['results_dir'], 'rq1_results.json')
    if not os.path.exists(rq1_path):
        log("❌ rq1_results.json not found. Run rq1_compare.py first.")
        return
    with open(rq1_path) as f:
        rq1_data = json.load(f)
    s2_best   = rq1_data.get('S2_best', {})
    combo_id  = s2_best.get('combo_id', 'S2_best')
    backbone  = s2_best.get('backbone', '')
    strategy  = s2_best.get('strategy', '')
    input_strat = s2_best.get('input_strategy', 'S2')

    baseline_path = os.path.join(CONFIG['results_dir'], 'rq2_baseline_results.json')
    if not os.path.exists(baseline_path):
        log("❌ rq2_baseline_results.json not found. Run rq2_baseline.py first.")
        return
    with open(baseline_path) as f:
        baseline_data = json.load(f)
    ada_thr     = baseline_data.get('threshold', 0.5)
    ada_metrics = baseline_data.get('test_metrics', {})

    cnn_probs_path = os.path.join(CONFIG['results_dir'], 'S2_best_test_probs.npy')
    ada_probs_path = os.path.join(CONFIG['results_dir'], 'rq2_best_test_probs.npy')
    if not os.path.exists(cnn_probs_path):
        log("❌ S2_best_test_probs.npy not found. Run rq1_final_eval.py first.")
        return
    if not os.path.exists(ada_probs_path):
        log("❌ rq2_best_test_probs.npy not found. Run rq2_baseline.py first.")
        return

    cnn_probs = np.load(cnn_probs_path)
    ada_probs = np.load(ada_probs_path)
    log(f"✓ CNN probs loaded: {cnn_probs.shape}  ({combo_id})")
    log(f"✓ Baseline probs loaded: {ada_probs.shape}")

    data_path = DATA_SOURCE[input_strat]
    images, labels = load_preprocessed_inaoe(data_path, log=log)
    _, test_indices = create_fold_splits(
        images, labels,
        n_splits=CONFIG['n_folds'],
        test_split=CONFIG['test_split'],
        random_state=SEED,
    )
    y_test = labels[test_indices]
    log(f"Test set: {len(y_test)} samples  "
        f"(DM={int(np.sum(y_test == 1))}, CT={int(np.sum(y_test == 0))})")

    cnn_thr = 0.5
    cnn_m   = metrics_at(y_test, cnn_probs, cnn_thr)

    log(f"Computing bootstrap CIs (n=2000, stratified) ...")
    cnn_ci  = bootstrap_ci(y_test, cnn_probs, cnn_thr,  n_bootstrap=2000, seed=SEED)
    ada_ci  = bootstrap_ci(y_test, ada_probs, ada_thr,  n_bootstrap=2000, seed=SEED)
    log(f"✓ Bootstrap complete")

    log(f"\n{'='*80}")
    log(f"RQ2 COMPARISON: {combo_id} vs Baseline (Khandakar et al. 2021 pipeline)")
    log(f"{'='*80}")
    log(f"{'Metric':<14}  {'CNN':>22}  {'95% CI':>20}  {'Baseline':>22}  {'95% CI':>20}  {'Δ':>7}")
    log('─' * 105)
    for m in ['sensitivity', 'specificity', 'auc_roc', 'ppv', 'npv', 'f1']:
        cv  = cnn_m.get(m, 0.0)
        av  = ada_metrics.get(m, 0.0)
        ccl, cch = cnn_ci[m]
        acl, ach = ada_ci[m]
        log(f"{m:<14}  {cv:>22.4f}  [{ccl:.4f}, {cch:.4f}]  "
            f"{av:>22.4f}  [{acl:.4f}, {ach:.4f}]  {cv - av:>+7.4f}")

    log(f"\n{'─'*80}")
    log(f"Statistical Test  (CNN thr={cnn_thr:.4f}, Baseline thr={ada_thr:.4f})")
    log(f"{'─'*80}")

    cnn_bin = (cnn_probs >= cnn_thr).astype(int)
    ada_bin = (ada_probs >= ada_thr).astype(int)

    p_mc, b_s, c_s, n_dm = mcnemar_sensitivity(y_test, cnn_bin, ada_bin)
    sig_mc = ('***' if p_mc < 0.001 else
              ('**'  if p_mc < 0.01  else
               ('*'   if p_mc < 0.05  else 'ns')))
    log(f"McNemar's test (Sensitivity)  [PRIMARY]")
    log(f"  Subset: DM patients only  (n={n_dm})")
    log(f"  H0: CNN sensitivity = Baseline sensitivity at threshold")
    log(f"  b={b_s} (CNN catches DM / Baseline misses)  "
        f"c={c_s} (CNN misses DM / Baseline catches)  "
        f"p={p_mc:.4f} {sig_mc}")
    log(f"\nSignificance: * p<0.05  ** p<0.01  *** p<0.001  ns=not significant")

    label_name = {0: 'CT', 1: 'DM'}
    dm_mask = (y_test == 1)
    dm_indices = np.where(dm_mask)[0]
    b_idx = dm_indices[
        (cnn_bin[dm_mask] == y_test[dm_mask]) & (ada_bin[dm_mask] != y_test[dm_mask])
    ]
    c_idx = dm_indices[
        (cnn_bin[dm_mask] != y_test[dm_mask]) & (ada_bin[dm_mask] == y_test[dm_mask])
    ]

    log(f"\n{'─'*80}")
    log(f"Discordant DM Cases")
    log(f"b={b_s}: CNN detects DM / Baseline misses")
    for ii in b_idx:
        log(f"  test[{ii:2d}] dataset[{test_indices[ii]:3d}]  "
            f"true=DM  "
            f"CNN=DM({cnn_probs[ii]:.3f})  "
            f"Baseline=CT({ada_probs[ii]:.3f})")
    log(f"c={c_s}: CNN misses DM / Baseline detects")
    for ii in c_idx:
        log(f"  test[{ii:2d}] dataset[{test_indices[ii]:3d}]  "
            f"true=DM  "
            f"CNN=CT({cnn_probs[ii]:.3f})  "
            f"Baseline=DM({ada_probs[ii]:.3f})")

    discordant = {
        'b_cases': [
            {'test_idx':    int(ii),
             'dataset_idx': int(test_indices[ii]),
             'true_label':  1,
             'true_name':   'DM',
             'cnn_pred':    int(cnn_bin[ii]),
             'cnn_prob':    round(float(cnn_probs[ii]), 4),
             'ada_pred':    int(ada_bin[ii]),
             'ada_prob':    round(float(ada_probs[ii]), 4)}
            for ii in b_idx
        ],
        'c_cases': [
            {'test_idx':    int(ii),
             'dataset_idx': int(test_indices[ii]),
             'true_label':  1,
             'true_name':   'DM',
             'cnn_pred':    int(cnn_bin[ii]),
             'cnn_prob':    round(float(cnn_probs[ii]), 4),
             'ada_pred':    int(ada_bin[ii]),
             'ada_prob':    round(float(ada_probs[ii]), 4)}
            for ii in c_idx
        ],
    }

    best = baseline_data.get('best', {})
    result = {
        'proposed_model': combo_id,
        'backbone':       backbone,
        'strategy':       strategy,
        'input_strategy': input_strat,
        'baseline_model': (f"{best.get('ranking', '')} ranking + "
                           f"{best.get('classifier', '')} + "
                           f"top {best.get('n_features', '')} features"),
        'cnn_threshold':  cnn_thr,
        'ada_threshold':  ada_thr,
        'bootstrap_n':    2000,
        'cnn_test_metrics': cnn_m,
        'cnn_ci_95':        cnn_ci,
        'ada_test_metrics': ada_metrics,
        'ada_ci_95':        ada_ci,
        'statistical_tests': {
            'mcnemar_sensitivity': {
                'role':      'PRIMARY — McNemar on DM patients only, directly tests sensitivity difference',
                'subset':    'DM patients (y=1)',
                'n_subset':  n_dm,
                'b':         b_s,
                'c':         c_s,
                'p_value':   round(p_mc, 4),
                'significance': sig_mc,
                'discordant_cases': discordant,
            },
        },
    }
    out = os.path.join(CONFIG['results_dir'], 'rq2_results.json')
    with open(out, 'w') as f:
        json.dump(result, f, indent=2)
    log(f"\n✓ RQ2 comparison results -> {out}")


if __name__ == '__main__':
    main()
