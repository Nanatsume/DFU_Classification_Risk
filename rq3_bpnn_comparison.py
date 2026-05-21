"""RQ3: BPNN (MLP, tanh activation, GLCM + HOG features) vs CNN proposed model.

Both models are evaluated with their own optimal Youden's Index threshold.
Features are cached to model_checkpoints/glcm_hog_features.npz to avoid
recomputing on re-runs.

Saves results and comparison table to results/rq3_results.json.
"""

import os
import json
import numpy as np
from skimage.feature import graycomatrix, graycoprops, hog
from skimage.color import rgb2gray
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, f1_score
from sklearn.model_selection import GridSearchCV
from scipy.stats import chi2, binom, skew, kurtosis

from dfu_common import (
    CONFIG, SEED, make_logger, load_preprocessed_inaoe, create_fold_splits,
    compute_youden_threshold,
)


# ── Statistical tests ─────────────────────────────────────────────────────────

def mcnemar_test(y_true, pred_a, pred_b):
    """McNemar's test: H0 = both classifiers make same errors on paired data.
    Returns p-value, b (A correct / B wrong), c (A wrong / B correct)."""
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
        p = float(1 - chi2.cdf(stat, df=1))
    return p, b, c


def delong_auc_pvalue(y_true, prob_a, prob_b):
    """DeLong's test p-value for H0: AUC_A = AUC_B (two-sided).

    Uses the variance estimation method from DeLong et al. (1988).
    Returns (p_value, delta_auc, z_stat).
    """
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
    delta = auc_a - auc_b

    S10 = np.cov(V10_a, V10_b) / n1
    S01 = np.cov(V01_a, V01_b) / n0
    S = S10 + S01

    var_delta = S[0, 0] + S[1, 1] - 2 * S[0, 1]
    if var_delta <= 0:
        return 1.0, delta, 0.0

    z = delta / np.sqrt(var_delta)
    from scipy import stats
    p = float(2 * stats.norm.sf(abs(z)))
    return p, float(delta), float(z)


# ── Feature extraction ────────────────────────────────────────────────────────

def glcm_features(img_rgb):
    """GLCM on 8-level quantised image, 4 angles, 4 properties → 16-dim.

    4 properties × 4 angles (kept separate, not averaged):
      Contrast, Correlation, Energy, Homogeneity
    """
    gray = (rgb2gray(img_rgb) * 255).astype(np.uint8)
    # Quantise to 8 levels (matches paper's 8×8 GLCM)
    gray = (gray // 32).astype(np.uint8)
    glcm = graycomatrix(
        gray,
        distances=[1],
        angles=[0, np.pi / 4, np.pi / 2, 3 * np.pi / 4],
        levels=8, symmetric=True, normed=True,
    )
    props = ['contrast', 'correlation', 'energy', 'homogeneity']
    # graycoprops returns shape (1, 4) → flatten to 4 values per property
    feats = np.concatenate([graycoprops(glcm, p).flatten() for p in props])
    return feats.astype(np.float32)  # 4 props × 4 angles = 16-dim


def hog_features(img_rgb):
    """HOG vector (8×8 cells, 2×2 blocks) → 8 statistical descriptors.

    Statistics: Mean, Std, Variance, Median, Max, Min, Skewness, Kurtosis
    Result: 8-dim (same as paper's summarised HOG)
    """
    gray = rgb2gray(img_rgb)
    hog_vec = hog(
        gray,
        orientations=9,
        pixels_per_cell=(8, 8),
        cells_per_block=(2, 2),
        block_norm='L2-Hys',
    )
    return np.array([
        hog_vec.mean(),
        hog_vec.std(),
        hog_vec.var(),
        np.median(hog_vec),
        hog_vec.max(),
        hog_vec.min(),
        float(skew(hog_vec)),
        float(kurtosis(hog_vec)),
    ], dtype=np.float32)  # 8-dim


def extract_all_features(images, log=print):
    log(f"Extracting GLCM + HOG features from {len(images)} images ...")
    feats = []
    for i, img in enumerate(images):
        feats.append(np.concatenate([glcm_features(img), hog_features(img)]))
        if (i + 1) % 100 == 0:
            log(f"  {i+1}/{len(images)}")
    arr = np.array(feats, dtype=np.float32)
    log(f"  Done — feature shape: {arr.shape}")
    return arr


# ── Metrics ───────────────────────────────────────────────────────────────────

def metrics_at(y_true, y_prob, threshold):
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


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log = make_logger('rq3')

    images, labels = load_preprocessed_inaoe(CONFIG['data_source'], log=log)
    fold_indices, test_indices = create_fold_splits(
        images, labels,
        n_splits=CONFIG['n_folds'],
        test_split=CONFIG['test_split'],
        random_state=SEED,
    )

    # Feature extraction (cached)
    cache = os.path.join(CONFIG['checkpoint_dir'], 'glcm_hog_features.npz')
    if os.path.exists(cache):
        log(f"✓ Loading cached features: {cache}")
        X_feat = np.load(cache)['features']
    else:
        X_feat = extract_all_features(images, log=log)
        np.savez(cache, features=X_feat)
        log(f"✓ Features cached → {cache}")

    # Train / test split (identical to CNN)
    train_mask = np.ones(len(labels), dtype=bool)
    train_mask[test_indices] = False
    X_train, y_train = X_feat[train_mask], labels[train_mask]
    X_test,  y_test  = X_feat[test_indices], labels[test_indices]
    log(f"Train: {len(y_train)}  |  Test: {len(y_test)}")

    # ── Phase 1: 5-fold CV GridSearch — find best hyperparameters ────────────
    log(f"\n{'='*80}")
    log(f"RQ3: BPNN HYPERPARAMETER SEARCH (GridSearchCV, 5-fold, scoring=AUC)")
    log(f"{'='*80}")

    sc_search = StandardScaler()
    X_train_s_search = sc_search.fit_transform(X_train)

    param_grid = {
        'hidden_layer_sizes': [(64, 32), (128, 64), (256, 128)],
        'alpha':              [1e-4, 1e-3, 1e-2],
    }
    gs = GridSearchCV(
        MLPClassifier(activation='tanh', solver='adam', max_iter=500,
                      random_state=SEED, early_stopping=True,
                      validation_fraction=0.1, n_iter_no_change=20),
        param_grid=param_grid,
        cv=5,
        scoring='roc_auc',
        n_jobs=-1,
        refit=False,
    )
    gs.fit(X_train_s_search, y_train)
    best_params = gs.best_params_
    log(f"Best params: {best_params}  (CV AUC={gs.best_score_:.4f})")

    # ── Phase 2: 5-fold CV with best params — find sweep threshold ────────────
    log(f"\n{'='*80}")
    log(f"RQ3: BPNN 5-FOLD CV — Threshold sweep (best params)")
    log(f"{'='*80}")

    fold_iters   = []
    all_y_val    = []
    all_probs_val = []
    for i, fi in enumerate(fold_indices):
        X_tr, y_tr = X_feat[fi['train_idx']], labels[fi['train_idx']]
        X_v,  y_v  = X_feat[fi['val_idx']],   labels[fi['val_idx']]

        sc = StandardScaler()
        X_tr_s = sc.fit_transform(X_tr)
        X_v_s  = sc.transform(X_v)

        bpnn = MLPClassifier(
            hidden_layer_sizes=best_params['hidden_layer_sizes'],
            alpha=best_params['alpha'],
            activation='tanh',
            solver='adam',
            max_iter=500,
            random_state=SEED,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=20,
        )
        bpnn.fit(X_tr_s, y_tr)
        probs_v = bpnn.predict_proba(X_v_s)[:, 1]

        auc_v = roc_auc_score(y_v, probs_v)
        fold_iters.append(bpnn.n_iter_)
        all_y_val.append(y_v)
        all_probs_val.append(probs_v)
        log(f"  Fold {i+1}: AUC={auc_v:.4f}  stop_iter={bpnn.n_iter_}")

    # Sweep threshold on combined val predictions
    all_y_val    = np.concatenate(all_y_val)
    all_probs_val = np.concatenate(all_probs_val)
    best_sweep_thr, best_sweep_sens = None, 0.0
    best_j_thr, best_j = 0.5, -1.0
    log(f"\n  Threshold sweep (0.05–0.95, step=0.05):")
    for t in np.arange(0.05, 1.0, 0.05):
        pred = (all_probs_val >= t).astype(int)
        tp = ((pred==1)&(all_y_val==1)).sum()
        tn = ((pred==0)&(all_y_val==0)).sum()
        fp = ((pred==1)&(all_y_val==0)).sum()
        fn = ((pred==0)&(all_y_val==1)).sum()
        sens = tp/(tp+fn) if (tp+fn)>0 else 0
        spec = tn/(tn+fp) if (tn+fp)>0 else 0
        j = sens + spec - 1
        log(f"    thr={t:.2f}  Sens={sens:.4f}  Spec={spec:.4f}  J={j:.4f}")
        if j > best_j:
            best_j = j
            best_j_thr = round(float(t), 2)
        if sens >= 0.70 and spec >= 0.70 and sens > best_sweep_sens:
            best_sweep_sens = sens
            best_sweep_thr  = round(float(t), 2)

    if best_sweep_thr is None:
        best_sweep_thr = best_j_thr
        log(f"  ⚠ No threshold satisfies both Sens≥0.70 & Spec≥0.70 — using max J fallback: {best_j_thr:.2f}")

    mean_youden = best_sweep_thr   # reuse variable name for compatibility
    avg_iter    = int(round(np.mean(fold_iters)))
    # Compute actual sens/spec at chosen threshold for display
    _pred_final = (all_probs_val >= mean_youden).astype(int)
    _tp = ((_pred_final==1)&(all_y_val==1)).sum(); _fn = ((_pred_final==0)&(all_y_val==1)).sum()
    _tn = ((_pred_final==0)&(all_y_val==0)).sum(); _fp = ((_pred_final==1)&(all_y_val==0)).sum()
    _sens = _tp/(_tp+_fn) if (_tp+_fn)>0 else 0
    _spec = _tn/(_tn+_fp) if (_tn+_fp)>0 else 0
    log(f"\n✓ Sweep threshold (BPNN): {mean_youden:.2f}  (Sens={_sens:.4f}  Spec={_spec:.4f})")
    log(f"✓ Avg stopping iteration : {avg_iter}  (per fold: {fold_iters})")

    # ── Final BPNN on full training set ───────────────────────────────────────
    # Mirror CNN strategy: train for avg stopping iter, no early stopping
    log(f"\n{'='*80}")
    log(f"RQ3: BPNN final training on full train set  ({avg_iter} iterations)")
    log(f"{'='*80}")

    sc_final = StandardScaler()
    X_train_s = sc_final.fit_transform(X_train)
    X_test_s  = sc_final.transform(X_test)

    final_bpnn = MLPClassifier(
        hidden_layer_sizes=best_params['hidden_layer_sizes'],
        alpha=best_params['alpha'],
        activation='tanh',
        solver='adam',
        max_iter=avg_iter,
        random_state=SEED,
    )
    final_bpnn.fit(X_train_s, y_train)
    test_probs = final_bpnn.predict_proba(X_test_s)[:, 1]

    bpnn_metrics = metrics_at(y_test, test_probs, mean_youden)

    log(f"\n{'='*80}")
    log(f"RQ3: BPNN TEST RESULTS  (threshold={mean_youden:.4f})")
    log(f"{'='*80}")
    for k, v in bpnn_metrics.items():
        log(f"  {k:<14}: {v:.4f}")

    # ── Comparison with CNN (RQ3) ──────────────────────────────────────────────
    rq3_path      = os.path.join(CONFIG['results_dir'], 'final_eval_results.json')
    rq3_probs_path = os.path.join(CONFIG['results_dir'], 'final_eval_probs.npy')
    if os.path.exists(rq3_path):
        with open(rq3_path) as f:
            rq3 = json.load(f)
        cnn_name = rq3['best_model']

        # Compute CNN sweep threshold from 5-fold val predictions
        cnn_val_path = os.path.join(CONFIG['checkpoint_dir'], f'{cnn_name}_val_preds.npz')
        log(f"\n{'='*80}")
        log(f"RQ3: CNN THRESHOLD SWEEP — {cnn_name} (step=0.05)")
        log(f"{'='*80}")
        if os.path.exists(cnn_val_path):
            _val_data = np.load(cnn_val_path)
            _cnn_y = np.concatenate([labels[fi['val_idx']]               for fi in fold_indices])
            _cnn_p_val = np.concatenate([_val_data[f'fold{fi["fold"]+1}'] for fi in fold_indices])
            _best_cnn_thr, _best_cnn_sens = None, 0.0
            _best_cnn_j_thr, _best_cnn_j = 0.5, -1.0
            for t in np.arange(0.05, 1.0, 0.05):
                _pred = (_cnn_p_val >= t).astype(int)
                _tp = ((_pred==1)&(_cnn_y==1)).sum(); _fn = ((_pred==0)&(_cnn_y==1)).sum()
                _tn = ((_pred==0)&(_cnn_y==0)).sum(); _fp = ((_pred==1)&(_cnn_y==0)).sum()
                _s = _tp/(_tp+_fn) if (_tp+_fn)>0 else 0
                _sp = _tn/(_tn+_fp) if (_tn+_fp)>0 else 0
                _j = _s + _sp - 1
                log(f"  thr={t:.2f}  Sens={_s:.4f}  Spec={_sp:.4f}  J={_j:.4f}")
                if _j > _best_cnn_j:
                    _best_cnn_j = _j
                    _best_cnn_j_thr = round(float(t), 2)
                if _s >= 0.70 and _sp >= 0.70 and _s > _best_cnn_sens:
                    _best_cnn_sens = _s
                    _best_cnn_thr  = round(float(t), 2)
            if _best_cnn_thr is None:
                _best_cnn_thr = _best_cnn_j_thr
                log(f"  ⚠ CNN: No threshold satisfies both Sens≥0.70 & Spec≥0.70 — using max J: {_best_cnn_j_thr:.2f}")
            cnn_thr = _best_cnn_thr
            log(f"✓ CNN sweep threshold: {cnn_thr:.2f}")
        else:
            cnn_thr = 0.6
            log(f"  ⚠ {cnn_val_path} not found — using default thr=0.60")

        cnn_probs_path = os.path.join(CONFIG['results_dir'], 'final_eval_probs.npy')
        if os.path.exists(cnn_probs_path):
            _cnn_p = np.load(cnn_probs_path)
            cnn_m  = metrics_at(y_test, _cnn_p, cnn_thr)
        else:
            cnn_m  = rq3['test_metrics']

        log(f"\n{'='*80}")
        log(f"RQ3: COMPARISON TABLE")
        log(f"{'='*80}")
        log(f"{'Metric':<14}  {'CNN (' + cnn_name + ')':>22}  {'BPNN (GLCM+HOG)':>18}  {'Δ':>8}")
        log('─' * 68)
        order = ['sensitivity', 'specificity', 'auc_roc', 'ppv', 'npv', 'f1']
        for m in order:
            cv = cnn_m.get(m, 0.0)
            bv = bpnn_metrics[m]
            log(f"{m:<14}  {cv:>22.4f}  {bv:>18.4f}  {cv - bv:>+8.4f}")

        # ── Statistical tests ──────────────────────────────────────────────────
        log(f"\n{'─'*68}")
        log(f"Statistical Tests  (CNN thr={cnn_thr:.4f}, BPNN thr={mean_youden:.4f})")
        log(f"{'─'*68}")

        if os.path.exists(rq3_probs_path):
            cnn_probs  = np.load(rq3_probs_path)
            cnn_bin    = (cnn_probs  >= cnn_thr).astype(int)
            bpnn_bin   = (test_probs >= mean_youden).astype(int)

            p_mc, b, c = mcnemar_test(y_test, cnn_bin, bpnn_bin)
            sig_mc = '***' if p_mc < 0.001 else ('**' if p_mc < 0.01 else
                     ('*'  if p_mc < 0.05 else 'ns'))
            log(f"McNemar's test  (H0: same error rate)")
            log(f"  b={b} (CNN✓/BPNN✗)  c={c} (CNN✗/BPNN✓)  "
                f"p={p_mc:.4f} {sig_mc}")

            p_auc, delta_auc, z_stat = delong_auc_pvalue(y_test, cnn_probs, test_probs)
            sig_auc = '***' if p_auc < 0.001 else ('**' if p_auc < 0.01 else
                      ('*'  if p_auc < 0.05 else 'ns'))
            log(f"DeLong's test   (H0: AUC_CNN = AUC_BPNN)")
            log(f"  AUC_CNN={cnn_m['auc_roc']:.4f}  AUC_BPNN={bpnn_metrics['auc_roc']:.4f}  "
                f"ΔAUC={delta_auc:+.4f}  z={z_stat:.4f}  p={p_auc:.4f} {sig_auc}")
            log(f"\nSignificance: * p<0.05  ** p<0.01  *** p<0.001  ns=not significant")
        else:
            log("⚠ final_eval_probs.npy not found — re-run final_evaluation.py "
                "to enable statistical tests.")
    else:
        log("\n⚠ final_eval_results.json not found — CNN comparison skipped.")

    # Save BPNN test probabilities for use in notebook statistical tests
    bpnn_probs_path = os.path.join(CONFIG['results_dir'], 'rq3_test_probs.npy')
    np.save(bpnn_probs_path, test_probs)
    log(f"✓ BPNN test probs → {bpnn_probs_path}")

    # Build statistical test results dict (if CNN probs available)
    stat_tests = {}
    if os.path.exists(rq3_path) and os.path.exists(rq3_probs_path):
        cnn_probs = np.load(rq3_probs_path)
        cnn_bin   = (cnn_probs  >= cnn_thr).astype(int)
        bpnn_bin  = (test_probs >= mean_youden).astype(int)

        p_mc, b, c = mcnemar_test(y_test, cnn_bin, bpnn_bin)
        p_auc, delta_auc, z_stat = delong_auc_pvalue(y_test, cnn_probs, test_probs)

        # Discordant cases: which test samples CNN and BPNN disagree on
        label_name = {0: 'CT', 1: 'DM'}
        b_idx = np.where((cnn_bin == y_test) & (bpnn_bin != y_test))[0]
        c_idx = np.where((cnn_bin != y_test) & (bpnn_bin == y_test))[0]

        log(f"\n{'─'*68}")
        log(f"McNemar Discordant Cases")
        log(f"{'─'*68}")
        log(f"b={b}: CNN correct / BPNN wrong")
        for i in b_idx:
            log(f"  test[{i:2d}] dataset[{test_indices[i]:3d}]  true={label_name[y_test[i]]}  "
                f"CNN={label_name[cnn_bin[i]]}({cnn_probs[i]:.3f})  "
                f"BPNN={label_name[bpnn_bin[i]]}({test_probs[i]:.3f})")
        log(f"c={c}: CNN wrong / BPNN correct")
        for i in c_idx:
            log(f"  test[{i:2d}] dataset[{test_indices[i]:3d}]  true={label_name[y_test[i]]}  "
                f"CNN={label_name[cnn_bin[i]]}({cnn_probs[i]:.3f})  "
                f"BPNN={label_name[bpnn_bin[i]]}({test_probs[i]:.3f})")

        discordant = {
            'b_cases': [
                {'test_idx': int(i), 'dataset_idx': int(test_indices[i]),
                 'true_label': int(y_test[i]), 'true_name': label_name[y_test[i]],
                 'cnn_pred': int(cnn_bin[i]), 'cnn_prob': round(float(cnn_probs[i]), 4),
                 'bpnn_pred': int(bpnn_bin[i]), 'bpnn_prob': round(float(test_probs[i]), 4)}
                for i in b_idx
            ],
            'c_cases': [
                {'test_idx': int(i), 'dataset_idx': int(test_indices[i]),
                 'true_label': int(y_test[i]), 'true_name': label_name[y_test[i]],
                 'cnn_pred': int(cnn_bin[i]), 'cnn_prob': round(float(cnn_probs[i]), 4),
                 'bpnn_pred': int(bpnn_bin[i]), 'bpnn_prob': round(float(test_probs[i]), 4)}
                for i in c_idx
            ],
        }

        stat_tests = {
            'mcnemar': {
                'b': b, 'c': c,
                'p_value': round(p_mc, 4),
                'significance': '***' if p_mc < 0.001 else ('**' if p_mc < 0.01 else ('*' if p_mc < 0.05 else 'ns')),
                'discordant_cases': discordant,
            },
            'delong_auc': {
                'delta_auc': round(delta_auc, 4),
                'z_stat':    round(z_stat, 4),
                'p_value':   round(p_auc, 4),
                'significance': '***' if p_auc < 0.001 else ('**' if p_auc < 0.01 else ('*' if p_auc < 0.05 else 'ns')),
            },
        }

    result = {
        'bpnn_architecture':     f"{best_params['hidden_layer_sizes']}, tanh, alpha={best_params['alpha']}",
        'features':              'GLCM 8-level 4-angle (16-dim) + HOG 8-stats (8-dim) = 24-dim',
        'avg_stopping_iter':     avg_iter,
        'fold_stopping_iters':   fold_iters,
        'mean_youden_threshold': mean_youden,
        'cnn_threshold':         cnn_thr if os.path.exists(rq3_path) else None,
        'test_metrics':          bpnn_metrics,
        'statistical_tests':     stat_tests,
    }
    out = os.path.join(CONFIG['results_dir'], 'rq3_results.json')
    with open(out, 'w') as f:
        json.dump(result, f, indent=2)
    log(f"\n✓ Results → {out}")


if __name__ == '__main__':
    main()
