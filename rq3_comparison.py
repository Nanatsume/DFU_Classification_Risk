"""RQ3: AdaBoost (Khandakar et al. 2021 top-10 features) vs CNN proposed model.

Implements the 10-feature set from Khandakar et al. (2021) using raw temperature
CSV files from the INAOE dataset:
  Age, LPA_STD, MPD_STD (=MPA_STD), NRT_Class1, NRT_Class5, LPA_mean,
  TCI, MCA_STD, LPA_ETD, LPA_ET

Features are cached to model_checkpoints/khandakar_features.npz.
AdaBoost uses fixed hyperparameters: decision stump, n_estimators=200, lr=1.0.
Saves results to results/rq3_results.json.
"""

import os
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import AdaBoostClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import roc_auc_score, f1_score
from sklearn.preprocessing import StandardScaler
from scipy.stats import chi2, binom

from dfu_common import (
    CONFIG, SEED, make_logger, load_preprocessed_inaoe, create_fold_splits,
)

# ── Raw data path ──────────────────────────────────────────────────────────────
RAW_DIR  = '/home/ntphoto/DFU3/Dataset/INAOE Dataset'
EXCEL_PATH = os.path.join(RAW_DIR, 'Plantar Thermogram Database.xlsx')

# Temperature class boundaries (C0–C7 from Khandakar et al. for ET computation)
_ET_CLASSES = [26.5, 28.5, 29.5, 30.5, 31.0, 32.5, 33.5, 34.5]

# NRT class boundaries (5 thermal ranges, verified with TCI in Khandakar et al.)
_NRT_BOUNDS = [0.0, 26.5, 28.5, 30.5, 32.5, float('inf')]


# ── Statistical tests ─────────────────────────────────────────────────────────

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


# ── Khandakar feature extraction ──────────────────────────────────────────────

def _nonzero(arr):
    """Return flattened non-zero temperature values from a 2D CSV array."""
    flat = arr.flatten()
    return flat[flat > 0.0]


def _et_feature(pixels):
    """Compute Estimated Temperature (ET) for an angiosome region.

    Based on Barreto et al. and Khandakar et al.:
    - Assign pixels to C0–C7 temperature classes by nearest boundary.
    - Find the class Cj with highest pixel fraction aj.
    - ET = (a_{j-1}*C_{j-1} + a_j*C_j + a_{j+1}*C_{j+1}) / (a_{j-1}+a_j+a_{j+1})
    - For boundary classes (j=0 or j=7), use one-sided average.
    """
    if len(pixels) == 0:
        return 0.0
    classes = np.array(_ET_CLASSES)
    n_cls = len(classes)
    # Assign each pixel to the nearest class index
    dists = np.abs(pixels[:, None] - classes[None, :])
    assignments = np.argmin(dists, axis=1)
    counts = np.bincount(assignments, minlength=n_cls)
    total = counts.sum()
    if total == 0:
        return 0.0
    a = counts / total
    j = int(np.argmax(a))

    if j == 0:
        # Only right neighbor
        denom = a[j] + a[j + 1]
        if denom == 0:
            return float(classes[j])
        return float((a[j] * classes[j] + a[j + 1] * classes[j + 1]) / denom)
    if j == n_cls - 1:
        # Only left neighbor
        denom = a[j - 1] + a[j]
        if denom == 0:
            return float(classes[j])
        return float((a[j - 1] * classes[j - 1] + a[j] * classes[j]) / denom)
    denom = a[j - 1] + a[j] + a[j + 1]
    if denom == 0:
        return float(classes[j])
    return float((a[j - 1] * classes[j - 1] + a[j] * classes[j] +
                  a[j + 1] * classes[j + 1]) / denom)


def _nrt_class(pixels, cls):
    """Fraction of non-zero pixels in NRT class cls (1–5)."""
    if len(pixels) == 0:
        return 0.0
    lo = _NRT_BOUNDS[cls - 1]
    hi = _NRT_BOUNDS[cls]
    in_cls = np.sum((pixels > lo) & (pixels <= hi))
    return float(in_cls) / len(pixels)


def _read_csv_arr(path):
    """Read an INAOE temperature CSV → 2D float64 array."""
    return pd.read_csv(path, header=None).values.astype(np.float64)


def _subject_raw_csv(stem, group_label):
    """
    Return paths: (full_foot_csv, lpa_csv, mca_csv, mpa_csv).
    stem is e.g. 'CG001_M_L', group_label is 'Control Group' or 'DM Group'.
    """
    parts = stem.split('_')
    subject = parts[0]   # CG001 or DM001
    gender  = parts[1]   # M or F
    foot    = parts[2]   # L or R
    folder  = f'{subject}_{gender}'
    base    = os.path.join(RAW_DIR, group_label, folder)
    ang     = os.path.join(base, 'Angiosoms')
    prefix  = f'{subject}_{gender}_{foot}'
    return (
        os.path.join(base, f'{prefix}.csv'),
        os.path.join(ang,  f'{prefix}_LPA.csv'),
        os.path.join(ang,  f'{prefix}_MCA.csv'),
        os.path.join(ang,  f'{prefix}_MPA.csv'),   # MPD = MPA
    )


def extract_khandakar_features(preproc_dir, log=print):
    """
    Extract Khandakar et al. (2021) 10 features for every image in the
    preprocessed INAOE dataset, preserving the exact load order used by
    load_preprocessed_inaoe (CT sorted, then DM sorted).

    Returns (X, feature_names) where X.shape = (n_samples, 10).
    """
    log("Extracting Khandakar et al. (2021) features from raw INAOE CSV files ...")

    # Load demographics from Excel
    xl = pd.ExcelFile(EXCEL_PATH)
    cg_df = xl.parse('Control Group', skiprows=1)
    dm_df = xl.parse('DM Group',      skiprows=1)
    cg_df.rename(columns={'Unnamed: 0': 'Subject', 'Unnamed: 2': 'Age',
                           'TCI': 'TCI_R', 'TCI.1': 'TCI_L'}, inplace=True)
    dm_df.rename(columns={'Unnamed: 0': 'Subject', 'Unnamed: 2': 'Age',
                           'TCI': 'TCI_R', 'TCI.1': 'TCI_L'}, inplace=True)
    cg_df = cg_df[['Subject', 'Age', 'TCI_R', 'TCI_L']].dropna(subset=['Subject'])
    dm_df = dm_df[['Subject', 'Age', 'TCI_R', 'TCI_L']].dropna(subset=['Subject'])
    demo  = pd.concat([cg_df, dm_df], ignore_index=True)
    demo  = demo.set_index('Subject')

    # Collect all image stems in sorted order (CT then DM) — matches load_preprocessed_inaoe
    entries = []
    for group_label, folder, preproc_folder in [
        ('Control Group', 'CT', os.path.join(preproc_dir, 'CT')),
        ('DM Group',      'DM', os.path.join(preproc_dir, 'DM')),
    ]:
        stems = sorted(f[:-4] for f in os.listdir(preproc_folder)
                       if f.endswith('.npy'))
        for stem in stems:
            entries.append((stem, group_label))

    # --- Pass 1: compute ET for every image (needed to compute ETD across feet) ---
    log(f"  Pass 1 — computing LPA_ET for {len(entries)} images ...")
    et_map = {}   # stem → LPA_ET
    for stem, group_label in entries:
        _, lpa_csv, _, _ = _subject_raw_csv(stem, group_label)
        try:
            lpa_arr  = _read_csv_arr(lpa_csv)
            lpa_pix  = _nonzero(lpa_arr)
            et_map[stem] = _et_feature(lpa_pix)
        except Exception:
            et_map[stem] = 0.0

    # Build paired ETD map: for each stem, find its counterpart foot
    etd_map = {}
    for stem, _ in entries:
        parts = stem.split('_')
        foot  = parts[2]   # L or R
        other_foot = 'R' if foot == 'L' else 'L'
        other_stem = f'{parts[0]}_{parts[1]}_{other_foot}'
        et_self  = et_map.get(stem, 0.0)
        et_other = et_map.get(other_stem, 0.0)
        etd_map[stem] = abs(et_self - et_other)

    # --- Pass 2: compute all 10 features ---
    log(f"  Pass 2 — computing full feature set ...")
    rows = []
    missing = 0
    for idx, (stem, group_label) in enumerate(entries):
        parts   = stem.split('_')
        subject = parts[0]
        foot    = parts[2]   # L or R

        foot_csv, lpa_csv, mca_csv, mpa_csv = _subject_raw_csv(stem, group_label)

        try:
            foot_arr = _read_csv_arr(foot_csv)
            lpa_arr  = _read_csv_arr(lpa_csv)
            mca_arr  = _read_csv_arr(mca_csv)
            mpa_arr  = _read_csv_arr(mpa_csv)

            foot_pix = _nonzero(foot_arr)
            lpa_pix  = _nonzero(lpa_arr)
            mca_pix  = _nonzero(mca_arr)
            mpa_pix  = _nonzero(mpa_arr)
        except Exception as e:
            log(f"  ⚠ {stem}: CSV read error — {e}")
            foot_pix = lpa_pix = mca_pix = mpa_pix = np.array([])
            missing += 1

        # Lookup Age and TCI from Excel (per foot: L→TCI_L, R→TCI_R)
        if subject in demo.index:
            row = demo.loc[subject]
            age = float(row['Age']) if not pd.isna(row['Age']) else 0.0
            tci_col = 'TCI_L' if foot == 'L' else 'TCI_R'
            tci = float(row[tci_col]) if not pd.isna(row[tci_col]) else 0.0
        else:
            age = 0.0
            tci = 0.0

        feat = [
            age,
            float(np.std(lpa_pix))  if len(lpa_pix) > 0 else 0.0,   # LPA_STD
            float(np.std(mpa_pix))  if len(mpa_pix) > 0 else 0.0,   # MPD_STD (=MPA)
            _nrt_class(foot_pix, 1),                                   # NRT_Class1
            _nrt_class(foot_pix, 5),                                   # NRT_Class5
            float(np.mean(lpa_pix)) if len(lpa_pix) > 0 else 0.0,   # LPA_mean
            tci,
            float(np.std(mca_pix))  if len(mca_pix) > 0 else 0.0,   # MCA_STD
            etd_map.get(stem, 0.0),                                    # LPA_ETD
            et_map.get(stem, 0.0),                                     # LPA_ET
        ]
        rows.append(feat)

        if (idx + 1) % 50 == 0:
            log(f"    {idx+1}/{len(entries)} done")

    if missing:
        log(f"  ⚠ {missing} images had CSV read errors — features set to 0.")

    X = np.array(rows, dtype=np.float32)
    feature_names = [
        'Age', 'LPA_STD', 'MPD_STD', 'NRT_Class1', 'NRT_Class5',
        'LPA_mean', 'TCI', 'MCA_STD', 'LPA_ETD', 'LPA_ET',
    ]
    log(f"  Done — feature matrix shape: {X.shape}")
    return X, feature_names


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
    cache = os.path.join(CONFIG['checkpoint_dir'], 'khandakar_features.npz')
    if os.path.exists(cache):
        log(f"✓ Loading cached features: {cache}")
        loaded = np.load(cache)
        X_feat = loaded['features']
        feature_names = list(loaded['feature_names'])
    else:
        X_feat, feature_names = extract_khandakar_features(
            CONFIG['data_source'], log=log)
        np.savez(cache, features=X_feat,
                 feature_names=np.array(feature_names, dtype=str))
        log(f"✓ Features cached → {cache}")

    log(f"Features ({len(feature_names)}): {feature_names}")

    # Train / test split (identical to CNN)
    train_mask = np.ones(len(labels), dtype=bool)
    train_mask[test_indices] = False
    X_train, y_train = X_feat[train_mask], labels[train_mask]
    X_test,  y_test  = X_feat[test_indices], labels[test_indices]
    log(f"Train: {len(y_train)}  |  Test: {len(y_test)}")

    # Standardize features
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s  = scaler.transform(X_test)
    X_feat_s  = scaler.transform(X_feat)

    # AdaBoost with scikit-learn default hyperparameters (Khandakar et al. did not specify)
    ADA_N_EST = 50
    ADA_LR    = 1.0

    # ── 5-fold CV ─────────────────────────────────────────────────────────────
    log(f"\n{'='*80}")
    log(f"RQ3: AdaBoost 5-FOLD CV  (n_estimators={ADA_N_EST}, lr={ADA_LR})")
    log(f"{'='*80}")

    fold_aucs     = []
    all_y_val     = []
    all_probs_val = []
    for i, fi in enumerate(fold_indices):
        X_tr, y_tr = X_feat_s[fi['train_idx']], labels[fi['train_idx']]
        X_v,  y_v  = X_feat_s[fi['val_idx']],   labels[fi['val_idx']]

        ada = AdaBoostClassifier(
            estimator=DecisionTreeClassifier(max_depth=1, class_weight='balanced',
                                             random_state=SEED),
            n_estimators=ADA_N_EST,
            learning_rate=ADA_LR,
            random_state=SEED,
        )
        ada.fit(X_tr, y_tr)
        probs_v = ada.predict_proba(X_v)[:, 1]

        auc_v = roc_auc_score(y_v, probs_v)
        fold_aucs.append(auc_v)
        all_y_val.append(y_v)
        all_probs_val.append(probs_v)
        log(f"  Fold {i+1}: AUC={auc_v:.4f}")

    log(f"✓ Mean CV AUC: {np.mean(fold_aucs):.4f}  "
        f"±{np.std(fold_aucs):.4f}  "
        f"(per fold: {[round(a,4) for a in fold_aucs]})")
    ada_thr = 0.5

    # ── Final AdaBoost on full training set ───────────────────────────────────
    log(f"\n{'='*80}")
    log(f"RQ3: AdaBoost final training on full train set (threshold={ada_thr})")
    log(f"{'='*80}")

    final_ada = AdaBoostClassifier(
        estimator=DecisionTreeClassifier(max_depth=1, class_weight='balanced',
                                         random_state=SEED),
        n_estimators=ADA_N_EST,
        learning_rate=ADA_LR,
        random_state=SEED,
    )
    final_ada.fit(X_train_s, y_train)
    test_probs = final_ada.predict_proba(X_test_s)[:, 1]

    ada_metrics = metrics_at(y_test, test_probs, ada_thr)

    log(f"\n{'='*80}")
    log(f"RQ3: AdaBoost TEST RESULTS  (threshold={ada_thr:.4f})")
    log(f"{'='*80}")
    for k, v in ada_metrics.items():
        log(f"  {k:<14}: {v:.4f}")

    # ── Comparison with CNN ───────────────────────────────────────────────────
    rq3_path       = os.path.join(CONFIG['results_dir'], 'final_eval_results.json')
    rq3_probs_path = os.path.join(CONFIG['results_dir'], 'final_eval_probs.npy')
    cnn_thr = 0.5
    stat_tests = {}

    if os.path.exists(rq3_path):
        with open(rq3_path) as f:
            rq3 = json.load(f)
        cnn_name = rq3['best_model']
        log(f"✓ CNN threshold: {cnn_thr:.4f}  (default)")

        if os.path.exists(rq3_probs_path):
            _cnn_p = np.load(rq3_probs_path)
            cnn_m  = metrics_at(y_test, _cnn_p, cnn_thr)
        else:
            cnn_m  = rq3['test_metrics']

        log(f"\n{'='*80}")
        log(f"RQ3: COMPARISON TABLE")
        log(f"{'='*80}")
        baseline_label = 'AdaBoost (Khandakar)'
        log(f"{'Metric':<14}  {'CNN (' + cnn_name + ')':>22}  {baseline_label:>22}  {'Δ':>8}")
        log('─' * 74)
        order = ['sensitivity', 'specificity', 'auc_roc', 'ppv', 'npv', 'f1']
        for m in order:
            cv = cnn_m.get(m, 0.0)
            av = ada_metrics[m]
            log(f"{m:<14}  {cv:>22.4f}  {av:>22.4f}  {cv - av:>+8.4f}")

        log(f"\n{'─'*74}")
        log(f"Statistical Tests  (CNN thr={cnn_thr:.4f}, AdaBoost thr={ada_thr:.4f})")
        log(f"{'─'*74}")

        if os.path.exists(rq3_probs_path):
            cnn_probs = np.load(rq3_probs_path)
            cnn_bin   = (cnn_probs  >= cnn_thr).astype(int)
            ada_bin   = (test_probs >= ada_thr).astype(int)

            p_mc, b, c = mcnemar_test(y_test, cnn_bin, ada_bin)
            sig_mc = '***' if p_mc < 0.001 else ('**' if p_mc < 0.01 else
                     ('*'  if p_mc < 0.05 else 'ns'))
            log(f"McNemar's test  (H0: same error rate)")
            log(f"  b={b} (CNN✓/AdaBoost✗)  c={c} (CNN✗/AdaBoost✓)  "
                f"p={p_mc:.4f} {sig_mc}")

            p_auc, delta_auc, z_stat = delong_auc_pvalue(y_test, cnn_probs, test_probs)
            sig_auc = '***' if p_auc < 0.001 else ('**' if p_auc < 0.01 else
                      ('*'  if p_auc < 0.05 else 'ns'))
            log(f"DeLong's test   (H0: AUC_CNN = AUC_AdaBoost)")
            log(f"  AUC_CNN={cnn_m['auc_roc']:.4f}  AUC_AdaBoost={ada_metrics['auc_roc']:.4f}  "
                f"ΔAUC={delta_auc:+.4f}  z={z_stat:.4f}  p={p_auc:.4f} {sig_auc}")
            log(f"\nSignificance: * p<0.05  ** p<0.01  *** p<0.001  ns=not significant")

            label_name = {0: 'CT', 1: 'DM'}
            b_idx = np.where((cnn_bin == y_test) & (ada_bin != y_test))[0]
            c_idx = np.where((cnn_bin != y_test) & (ada_bin == y_test))[0]

            log(f"\n{'─'*74}")
            log(f"McNemar Discordant Cases")
            log(f"{'─'*74}")
            log(f"b={b}: CNN correct / AdaBoost wrong")
            for i in b_idx:
                log(f"  test[{i:2d}] dataset[{test_indices[i]:3d}]  true={label_name[y_test[i]]}  "
                    f"CNN={label_name[cnn_bin[i]]}({cnn_probs[i]:.3f})  "
                    f"AdaBoost={label_name[ada_bin[i]]}({test_probs[i]:.3f})")
            log(f"c={c}: CNN wrong / AdaBoost correct")
            for i in c_idx:
                log(f"  test[{i:2d}] dataset[{test_indices[i]:3d}]  true={label_name[y_test[i]]}  "
                    f"CNN={label_name[cnn_bin[i]]}({cnn_probs[i]:.3f})  "
                    f"AdaBoost={label_name[ada_bin[i]]}({test_probs[i]:.3f})")

            discordant = {
                'b_cases': [
                    {'test_idx': int(i), 'dataset_idx': int(test_indices[i]),
                     'true_label': int(y_test[i]), 'true_name': label_name[y_test[i]],
                     'cnn_pred': int(cnn_bin[i]), 'cnn_prob': round(float(cnn_probs[i]), 4),
                     'adaboost_pred': int(ada_bin[i]), 'adaboost_prob': round(float(test_probs[i]), 4)}
                    for i in b_idx
                ],
                'c_cases': [
                    {'test_idx': int(i), 'dataset_idx': int(test_indices[i]),
                     'true_label': int(y_test[i]), 'true_name': label_name[y_test[i]],
                     'cnn_pred': int(cnn_bin[i]), 'cnn_prob': round(float(cnn_probs[i]), 4),
                     'adaboost_pred': int(ada_bin[i]), 'adaboost_prob': round(float(test_probs[i]), 4)}
                    for i in c_idx
                ],
            }

            stat_tests = {
                'mcnemar': {
                    'b': b, 'c': c,
                    'p_value': round(p_mc, 4),
                    'significance': sig_mc,
                    'discordant_cases': discordant,
                },
                'delong_auc': {
                    'delta_auc': round(delta_auc, 4),
                    'z_stat':    round(z_stat, 4),
                    'p_value':   round(p_auc, 4),
                    'significance': sig_auc,
                },
            }
        else:
            log("⚠ final_eval_probs.npy not found — re-run final_evaluation.py "
                "to enable statistical tests.")
    else:
        log("\n⚠ final_eval_results.json not found — CNN comparison skipped.")

    # Save AdaBoost test probabilities
    ada_probs_path = os.path.join(CONFIG['results_dir'], 'rq3_test_probs.npy')
    np.save(ada_probs_path, test_probs)
    log(f"✓ AdaBoost test probs → {ada_probs_path}")

    result = {
        'adaboost_params':   f"n_estimators={ADA_N_EST}, "
                             f"learning_rate={ADA_LR}, "
                             f"base=DecisionStump(max_depth=1, class_weight=balanced)",
        'features':          'Khandakar et al. (2021) top-10: '
                             'Age, LPA_STD, MPD_STD, NRT_Class1, NRT_Class5, '
                             'LPA_mean, TCI, MCA_STD, LPA_ETD, LPA_ET',
        'fold_aucs':         [round(a, 4) for a in fold_aucs],
        'mean_cv_auc':       round(float(np.mean(fold_aucs)), 4),
        'std_cv_auc':        round(float(np.std(fold_aucs)), 4),
        'adaboost_threshold': ada_thr,
        'cnn_threshold':     cnn_thr,
        'test_metrics':      ada_metrics,
        'statistical_tests': stat_tests,
    }
    out = os.path.join(CONFIG['results_dir'], 'rq3_results.json')
    with open(out, 'w') as f:
        json.dump(result, f, indent=2)
    log(f"\n✓ Results → {out}")


if __name__ == '__main__':
    main()
