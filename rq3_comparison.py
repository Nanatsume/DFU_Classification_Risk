"""RQ3: AdaBoost (full Khandakar et al. 2021 pipeline) vs CNN proposed model.

Replicates the complete pipeline from Khandakar et al. (2021):
  1. Extract all 39 features (Age, Gender, TCI, HighestTemp, NTR 1-5,
     and 30 zone stats: 5 zones x 6 params [Mean, Median, SD, ET, ETD, HSE])
  2. Correlation-based filtering (> 95% pairwise correlation -> drop one feature)
  3. SMOTE oversampling applied inside each CV fold and on final training set
  4. Feature importance ranking via Random Forest (+ XGBoost, ExtraTree for comparison)
  5. Select top 10 features by RF importance
  6. AdaBoost with decision stump base estimator

Saves results to results/rq3_results.json.
"""

import os
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import AdaBoostClassifier, RandomForestClassifier, ExtraTreesClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import roc_auc_score, f1_score
from sklearn.preprocessing import StandardScaler
from scipy.stats import chi2, binom
from imblearn.over_sampling import SMOTE
import xgboost as xgb

from dfu_common import (
    CONFIG, SEED, make_logger, load_preprocessed_inaoe, create_fold_splits,
)

# ── Raw data paths ─────────────────────────────────────────────────────────────
RAW_DIR    = '/home/ntphoto/Project/ThermoDataBase'
EXCEL_PATH = os.path.join(RAW_DIR, 'Plantar Thermogram Database.xlsx')

DATA_SOURCE = {
    'S1': '/home/ntphoto/DFU/INAOE_S1',
    'S2': '/home/ntphoto/DFU/INAOE_S2',
}

# Temperature class boundaries for ET computation (Khandakar et al.)
_ET_CLASSES = np.array([26.5, 28.5, 29.5, 30.5, 31.0, 32.5, 33.5, 34.5])

# NTR class temperature boundaries (Khandakar et al. 5 thermal ranges)
_NTR_BOUNDS = [0.0, 26.5, 28.5, 30.5, 32.5, float('inf')]

ZONES = ['LPA', 'MPA', 'LCA', 'MCA', 'FullFoot']


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


# ── Zone feature helpers ───────────────────────────────────────────────────────

def _nonzero(arr):
    flat = arr.flatten()
    return flat[flat > 0.0]


def _read_csv_arr(path):
    return pd.read_csv(path, header=None).values.astype(np.float64)


def _ntr_class(pixels, cls):
    """Fraction of non-zero pixels in NTR class cls (1-5)."""
    if len(pixels) == 0:
        return 0.0
    lo = _NTR_BOUNDS[cls - 1]
    hi = _NTR_BOUNDS[cls]
    in_cls = np.sum((pixels > lo) & (pixels <= hi))
    return float(in_cls) / len(pixels)


def _et_feature(pixels):
    """Estimated Temperature (ET) for a zone (Khandakar et al. / Barreto et al.).

    Assigns pixels to 8 temperature classes, finds the dominant class j,
    then computes weighted average of classes j-1, j, j+1.
    """
    if len(pixels) == 0:
        return 0.0
    n_cls = len(_ET_CLASSES)
    dists       = np.abs(pixels[:, None] - _ET_CLASSES[None, :])
    assignments = np.argmin(dists, axis=1)
    counts      = np.bincount(assignments, minlength=n_cls)
    total       = counts.sum()
    if total == 0:
        return 0.0
    a = counts / total
    j = int(np.argmax(a))
    if j == 0:
        denom = a[j] + a[j + 1]
        if denom == 0:
            return float(_ET_CLASSES[j])
        return float((a[j] * _ET_CLASSES[j] + a[j + 1] * _ET_CLASSES[j + 1]) / denom)
    if j == n_cls - 1:
        denom = a[j - 1] + a[j]
        if denom == 0:
            return float(_ET_CLASSES[j])
        return float((a[j - 1] * _ET_CLASSES[j - 1] + a[j] * _ET_CLASSES[j]) / denom)
    denom = a[j - 1] + a[j] + a[j + 1]
    if denom == 0:
        return float(_ET_CLASSES[j])
    return float((a[j - 1] * _ET_CLASSES[j - 1] +
                  a[j]     * _ET_CLASSES[j]     +
                  a[j + 1] * _ET_CLASSES[j + 1]) / denom)


def _hse_feature(pixels):
    """Hot Surface Entropy (HSE): Shannon entropy of the ET-class distribution.

    Computed over the 8 temperature class bins used for ET estimation.
    Higher entropy = more uniform temperature distribution across classes.
    """
    if len(pixels) == 0:
        return 0.0
    n_cls       = len(_ET_CLASSES)
    dists       = np.abs(pixels[:, None] - _ET_CLASSES[None, :])
    assignments = np.argmin(dists, axis=1)
    counts      = np.bincount(assignments, minlength=n_cls)
    total       = counts.sum()
    if total == 0:
        return 0.0
    probs = counts / total
    probs = probs[probs > 0]
    return float(-np.sum(probs * np.log(probs + 1e-12)))


def _zone_csv_path(stem, group_label, zone):
    """Return path to zone temperature CSV for the given stem and zone."""
    parts   = stem.split('_')
    subject = parts[0]
    gender  = parts[1]
    foot    = parts[2]
    folder  = f'{subject}_{gender}'
    base    = os.path.join(RAW_DIR, group_label, folder)
    prefix  = f'{subject}_{gender}_{foot}'
    if zone == 'FullFoot':
        return os.path.join(base, f'{prefix}.csv')
    return os.path.join(base, 'Angiosoms', f'{prefix}_{zone}.csv')


def _get_zone_pixels(stem, group_label, zone):
    path = _zone_csv_path(stem, group_label, zone)
    try:
        return _nonzero(_read_csv_arr(path))
    except Exception:
        return np.array([], dtype=np.float64)


# ── Khandakar full 39-feature extraction ──────────────────────────────────────

def _build_feature_names():
    names = ['Age', 'Gender', 'TCI', 'HighestTemp']
    names += [f'NTR_Class{c}' for c in range(1, 6)]
    for z in ZONES:
        for stat in ['Mean', 'Median', 'SD', 'ET', 'ETD', 'HSE']:
            names.append(f'{z}_{stat}')
    return names


FEATURE_NAMES_39 = _build_feature_names()
assert len(FEATURE_NAMES_39) == 39, f"Expected 39 features, got {len(FEATURE_NAMES_39)}"


def extract_khandakar_features_full(preproc_dir, log=print):
    """Extract all 39 Khandakar et al. (2021) features from raw INAOE CSVs.

    Returns (X, feature_names) where X.shape = (n_samples, 39).
    The sample order matches load_preprocessed_inaoe (CT sorted, then DM sorted).
    """
    log("Extracting all 39 Khandakar et al. features ...")

    # Load demographics from Excel
    xl     = pd.ExcelFile(EXCEL_PATH)
    cg_raw = xl.parse('Control Group', header=None)
    dm_raw = xl.parse('DM Group',      header=None)

    def parse_sheet(raw):
        # Row 0 = section headers, row 1 = sub-column headers, row 2+ = data
        # Columns: Subject(0), Gender(1), Age(2), ..., TCI_R(11), ..., TCI_L(17)
        df = raw.iloc[2:].copy()
        df.columns = range(len(df.columns))
        df = df[[0, 1, 2, 11, 17]].copy()
        df.columns = ['Subject', 'Gender', 'Age', 'TCI_R', 'TCI_L']
        df = df.dropna(subset=['Subject'])
        df['Subject'] = df['Subject'].astype(str).str.strip()
        df['Gender']  = df['Gender'].astype(str).str.strip()
        return df.set_index('Subject')

    cg_df = parse_sheet(cg_raw)
    dm_df = parse_sheet(dm_raw)
    demo  = pd.concat([cg_df, dm_df])

    # Collect stems in sorted order (CT then DM) — matches load_preprocessed_inaoe
    entries = []
    for group_label, preproc_sub in [
        ('Control Group', os.path.join(preproc_dir, 'CT')),
        ('DM Group',      os.path.join(preproc_dir, 'DM')),
    ]:
        stems = sorted(f[:-4] for f in os.listdir(preproc_sub) if f.endswith('.npy'))
        for stem in stems:
            entries.append((stem, group_label))

    log(f"  Total images to process: {len(entries)}")

    # Pass 1: compute ET for all zones (needed for ETD bilateral difference)
    log("  Pass 1 — computing ET for all zones ...")
    et_map = {}   # stem -> {zone: float}
    for stem, group_label in entries:
        et_map[stem] = {}
        for zone in ZONES:
            pix = _get_zone_pixels(stem, group_label, zone)
            et_map[stem][zone] = _et_feature(pix)

    # Compute ETD: |ET_L - ET_R| per zone per stem
    etd_map = {}   # stem -> {zone: float}
    for stem, _ in entries:
        parts      = stem.split('_')
        other_foot = 'R' if parts[2] == 'L' else 'L'
        other_stem = f'{parts[0]}_{parts[1]}_{other_foot}'
        etd_map[stem] = {}
        for zone in ZONES:
            et_self  = et_map.get(stem,       {}).get(zone, 0.0)
            et_other = et_map.get(other_stem, {}).get(zone, 0.0)
            etd_map[stem][zone] = abs(et_self - et_other)

    # Pass 2: compute all 39 features
    log("  Pass 2 — computing all features ...")
    rows    = []
    missing = 0
    for idx, (stem, group_label) in enumerate(entries):
        parts   = stem.split('_')
        subject = parts[0]
        gender  = parts[1]
        foot    = parts[2]

        # Demographics
        if subject in demo.index:
            row = demo.loc[subject]
            age     = float(row['Age'])   if not pd.isna(row['Age'])   else 0.0
            gender_val = 1.0 if str(row['Gender']).strip().upper() == 'F' else 0.0
            tci_col = 'TCI_L' if foot == 'L' else 'TCI_R'
            tci     = float(row[tci_col]) if not pd.isna(row[tci_col]) else 0.0
        else:
            age        = 0.0
            gender_val = 1.0 if gender.upper() == 'F' else 0.0
            tci        = 0.0
            missing   += 1

        # Full foot pixels for global features
        foot_pix = _get_zone_pixels(stem, group_label, 'FullFoot')

        highest_temp = float(foot_pix.max()) if len(foot_pix) > 0 else 0.0

        ntr_feats = [_ntr_class(foot_pix, c) for c in range(1, 6)]

        # Zone features
        zone_feats = []
        for zone in ZONES:
            pix = _get_zone_pixels(stem, group_label, zone)
            mean_v   = float(np.mean(pix))   if len(pix) > 0 else 0.0
            median_v = float(np.median(pix)) if len(pix) > 0 else 0.0
            sd_v     = float(np.std(pix))    if len(pix) > 0 else 0.0
            et_v     = et_map[stem][zone]
            etd_v    = etd_map[stem][zone]
            hse_v    = _hse_feature(pix)
            zone_feats.extend([mean_v, median_v, sd_v, et_v, etd_v, hse_v])

        feat_row = [age, gender_val, tci, highest_temp] + ntr_feats + zone_feats
        rows.append(feat_row)

        if (idx + 1) % 50 == 0:
            log(f"    {idx + 1}/{len(entries)} done")

    if missing:
        log(f"  Warning: {missing} subjects missing from Excel — demographics set to 0.")

    X = np.array(rows, dtype=np.float32)
    log(f"  Done — feature matrix: {X.shape}  ({len(FEATURE_NAMES_39)} features)")
    return X, FEATURE_NAMES_39


# ── Feature selection pipeline ─────────────────────────────────────────────────

def correlation_filter(X, feature_names, threshold=0.95, log=print):
    """Remove features with pairwise correlation > threshold.

    When two features exceed the threshold, the one with higher index is dropped
    (preserving the first occurrence — matching Khandakar et al.).
    Returns (X_filtered, names_filtered, kept_indices).
    """
    corr = np.corrcoef(X.T)
    n    = len(feature_names)
    drop = set()
    for i in range(n):
        if i in drop:
            continue
        for j in range(i + 1, n):
            if j in drop:
                continue
            if abs(corr[i, j]) > threshold:
                drop.add(j)
    kept = [i for i in range(n) if i not in drop]
    log(f"  Correlation filter (>{threshold*100:.0f}%): "
        f"{n} -> {len(kept)} features  (dropped {len(drop)})")
    return X[:, kept], [feature_names[i] for i in kept], kept


def rf_feature_ranking(X, y, feature_names, top_k=10, log=print):
    """Rank features by RF importance (with SMOTE-balanced data).

    Returns (top_indices, top_names, importances) where top_indices indexes into
    the supplied feature_names list.
    """
    rf = RandomForestClassifier(n_estimators=200, random_state=SEED, n_jobs=-1)
    rf.fit(X, y)
    importances = rf.feature_importances_
    ranked      = np.argsort(importances)[::-1]
    top_k_idx   = ranked[:top_k]
    log(f"  RF top-{top_k} features:")
    for rank, i in enumerate(top_k_idx):
        log(f"    {rank+1:2d}. {feature_names[i]:<22}  importance={importances[i]:.4f}")
    return top_k_idx, [feature_names[i] for i in top_k_idx], importances[top_k_idx]


def show_all_rankings(X, y, feature_names, top_k=10, log=print):
    """Show RF, XGBoost, and ExtraTree rankings side by side (informational)."""
    log(f"\n  {'Rank':<5}  {'Random Forest':<25}  {'XGBoost':<25}  {'ExtraTree':<25}")
    log('  ' + '-' * 85)

    rf = RandomForestClassifier(n_estimators=200, random_state=SEED, n_jobs=-1)
    rf.fit(X, y)
    rf_rank = np.argsort(rf.feature_importances_)[::-1][:top_k]

    et = ExtraTreesClassifier(n_estimators=200, random_state=SEED, n_jobs=-1)
    et.fit(X, y)
    et_rank = np.argsort(et.feature_importances_)[::-1][:top_k]

    xg = xgb.XGBClassifier(n_estimators=200, random_state=SEED,
                             eval_metric='logloss', use_label_encoder=False)
    xg.fit(X, y)
    xg_rank = np.argsort(xg.feature_importances_)[::-1][:top_k]

    for r in range(top_k):
        log(f"  {r+1:<5}  {feature_names[rf_rank[r]]:<25}  "
            f"{feature_names[xg_rank[r]]:<25}  "
            f"{feature_names[et_rank[r]]:<25}")


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

    # Use S1 data for split indices (same patients and ordering as S2)
    images, labels = load_preprocessed_inaoe(DATA_SOURCE['S1'], log=log)
    fold_indices, test_indices = create_fold_splits(
        images, labels,
        n_splits=CONFIG['n_folds'],
        test_split=CONFIG['test_split'],
        random_state=SEED,
    )

    # ── Step 1: Extract / load all 39 features ────────────────────────────────
    cache = os.path.join(CONFIG['checkpoint_dir'], 'khandakar_features_39.npz')
    if os.path.exists(cache):
        log(f"✓ Loading cached 39-feature matrix: {cache}")
        loaded       = np.load(cache, allow_pickle=True)
        X_all        = loaded['features']
        feature_names = list(loaded['feature_names'])
    else:
        X_all, feature_names = extract_khandakar_features_full(
            DATA_SOURCE['S1'], log=log)
        np.savez(cache, features=X_all,
                 feature_names=np.array(feature_names, dtype=str))
        log(f"✓ Features cached -> {cache}")

    log(f"Features ({len(feature_names)}): {feature_names}")

    # ── Step 2: Train/test split (identical to CNN pipeline) ─────────────────
    train_mask               = np.ones(len(labels), dtype=bool)
    train_mask[test_indices] = False
    X_train, y_train = X_all[train_mask],    labels[train_mask]
    X_test,  y_test  = X_all[test_indices],  labels[test_indices]
    log(f"Train: {len(y_train)}  |  Test: {len(y_test)}  "
        f"(DM_train={y_train.sum()}  CT_train={(y_train==0).sum()})")

    # Standardize (fit on train, apply to all)
    scaler     = StandardScaler()
    X_train_s  = scaler.fit_transform(X_train)
    X_test_s   = scaler.transform(X_test)
    X_all_s    = scaler.transform(X_all)

    # ── Step 3: Correlation filter on training set ────────────────────────────
    log(f"\n{'='*80}")
    log("Step 3: Correlation-based feature filtering (threshold=0.95)")
    log(f"{'='*80}")
    X_train_c, names_c, kept_indices = correlation_filter(
        X_train_s, feature_names, threshold=0.95, log=log)
    X_test_c  = X_test_s[:, kept_indices]
    X_all_c   = X_all_s[:, kept_indices]
    log(f"  Retained features ({len(names_c)}): {names_c}")

    # ── Step 4: SMOTE on full training set for feature ranking ────────────────
    log(f"\n{'='*80}")
    log("Step 4: SMOTE on training set -> feature ranking")
    log(f"{'='*80}")
    smote           = SMOTE(random_state=SEED)
    X_train_sm, y_train_sm = smote.fit_resample(X_train_c, y_train)
    log(f"  After SMOTE: {X_train_sm.shape[0]} samples  "
        f"(DM={y_train_sm.sum()}  CT={(y_train_sm==0).sum()})")

    log("\n  Feature rankings (RF / XGBoost / ExtraTree):")
    show_all_rankings(X_train_sm, y_train_sm, names_c, top_k=10, log=log)

    top10_idx, top10_names, top10_imp = rf_feature_ranking(
        X_train_sm, y_train_sm, names_c, top_k=10, log=log)

    # Apply top-10 selection
    X_train_top = X_train_c[:, top10_idx]
    X_test_top  = X_test_c[:,  top10_idx]
    X_all_top   = X_all_c[:,   top10_idx]

    log(f"\n  Selected top-10 features: {top10_names}")

    # AdaBoost hyperparameters following Khandakar et al.
    ADA_N_EST = 50
    ADA_LR    = 1.0

    # ── Step 5: 5-fold CV with SMOTE inside each fold ─────────────────────────
    log(f"\n{'='*80}")
    log(f"Step 5: AdaBoost 5-fold CV  (n_estimators={ADA_N_EST}, lr={ADA_LR})")
    log(f"{'='*80}")

    fold_aucs     = []
    all_y_val     = []
    all_probs_val = []

    for i, fi in enumerate(fold_indices):
        X_tr_fold = X_all_top[fi['train_idx']]
        y_tr_fold = labels[fi['train_idx']]
        X_v_fold  = X_all_top[fi['val_idx']]
        y_v_fold  = labels[fi['val_idx']]

        # SMOTE inside fold
        smote_fold         = SMOTE(random_state=SEED)
        X_tr_sm, y_tr_sm  = smote_fold.fit_resample(X_tr_fold, y_tr_fold)

        ada = AdaBoostClassifier(
            estimator=DecisionTreeClassifier(
                max_depth=1, class_weight='balanced', random_state=SEED),
            n_estimators=ADA_N_EST,
            learning_rate=ADA_LR,
            random_state=SEED,
        )
        ada.fit(X_tr_sm, y_tr_sm)
        probs_v = ada.predict_proba(X_v_fold)[:, 1]

        auc_v = roc_auc_score(y_v_fold, probs_v)
        fold_aucs.append(auc_v)
        all_y_val.append(y_v_fold)
        all_probs_val.append(probs_v)
        log(f"  Fold {i+1}: AUC={auc_v:.4f}")

    log(f"\n✓ Mean CV AUC: {np.mean(fold_aucs):.4f} +/-{np.std(fold_aucs):.4f}  "
        f"(per fold: {[round(a, 4) for a in fold_aucs]})")

    ada_thr = 0.5

    # ── Step 6: Final AdaBoost on full training set -> test evaluation ─────────
    log(f"\n{'='*80}")
    log(f"Step 6: AdaBoost final training (threshold={ada_thr})")
    log(f"{'='*80}")

    smote_final          = SMOTE(random_state=SEED)
    X_train_final, y_train_final = smote_final.fit_resample(X_train_top, y_train)
    log(f"  After SMOTE: {X_train_final.shape[0]} samples")

    final_ada = AdaBoostClassifier(
        estimator=DecisionTreeClassifier(
            max_depth=1, class_weight='balanced', random_state=SEED),
        n_estimators=ADA_N_EST,
        learning_rate=ADA_LR,
        random_state=SEED,
    )
    final_ada.fit(X_train_final, y_train_final)
    test_probs = final_ada.predict_proba(X_test_top)[:, 1]

    ada_metrics = metrics_at(y_test, test_probs, ada_thr)

    log(f"\n{'='*80}")
    log(f"Step 6: AdaBoost TEST RESULTS  (threshold={ada_thr:.4f})")
    log(f"{'='*80}")
    for k, v in ada_metrics.items():
        log(f"  {k:<14}: {v:.4f}")

    # ── Step 7: Compare with S2_best CNN (RQ2 result) ─────────────────────────
    rq2_path       = os.path.join(CONFIG['results_dir'], 'rq2_results.json')
    rq2_probs_path = os.path.join(CONFIG['results_dir'], 'S2_best_test_probs.npy')
    cnn_thr    = 0.5
    stat_tests = {}

    if os.path.exists(rq2_path):
        with open(rq2_path) as f:
            rq2_data = json.load(f)
        rq2      = rq2_data.get('S2_best', {})
        cnn_name = rq2.get('combo_id', 'S2_best')
        log(f"✓ CNN model: {cnn_name}  threshold: {cnn_thr:.4f}")

        if os.path.exists(rq2_probs_path):
            cnn_probs = np.load(rq2_probs_path)
            cnn_m     = metrics_at(y_test, cnn_probs, cnn_thr)
        else:
            cnn_probs = None
            cnn_m     = rq2.get('test_metrics', {})

        log(f"\n{'='*80}")
        log(f"RQ3: COMPARISON TABLE")
        log(f"{'='*80}")
        baseline_label = 'AdaBoost (Khandakar)'
        log(f"{'Metric':<14}  {'CNN (' + cnn_name + ')':>28}  {baseline_label:>22}  {'Delta':>8}")
        log('─' * 80)
        order = ['sensitivity', 'specificity', 'auc_roc', 'ppv', 'npv', 'f1']
        for m in order:
            cv = cnn_m.get(m, 0.0)
            av = ada_metrics[m]
            log(f"{m:<14}  {cv:>28.4f}  {av:>22.4f}  {cv - av:>+8.4f}")

        if cnn_probs is not None:
            log(f"\n{'─'*80}")
            log(f"Statistical Tests  (CNN thr={cnn_thr:.4f}, AdaBoost thr={ada_thr:.4f})")
            log(f"{'─'*80}")

            cnn_bin = (cnn_probs  >= cnn_thr).astype(int)
            ada_bin = (test_probs >= ada_thr).astype(int)

            p_mc, b, c = mcnemar_test(y_test, cnn_bin, ada_bin)
            sig_mc = ('***' if p_mc < 0.001 else
                      ('**'  if p_mc < 0.01  else
                       ('*'   if p_mc < 0.05  else 'ns')))
            log(f"McNemar's test  (H0: same error rate)")
            log(f"  b={b} (CNN correct/AdaBoost wrong)  c={c} (CNN wrong/AdaBoost correct)  "
                f"p={p_mc:.4f} {sig_mc}")

            p_auc, delta_auc, z_stat = delong_auc_pvalue(y_test, cnn_probs, test_probs)
            sig_auc = ('***' if p_auc < 0.001 else
                       ('**'  if p_auc < 0.01  else
                        ('*'   if p_auc < 0.05  else 'ns')))
            log(f"DeLong's test   (H0: AUC_CNN = AUC_AdaBoost)")
            log(f"  AUC_CNN={cnn_m['auc_roc']:.4f}  AUC_AdaBoost={ada_metrics['auc_roc']:.4f}  "
                f"ΔAUC={delta_auc:+.4f}  z={z_stat:.4f}  p={p_auc:.4f} {sig_auc}")
            log(f"\nSignificance: * p<0.05  ** p<0.01  *** p<0.001  ns=not significant")

            label_name = {0: 'CT', 1: 'DM'}
            b_idx = np.where((cnn_bin == y_test) & (ada_bin != y_test))[0]
            c_idx = np.where((cnn_bin != y_test) & (ada_bin == y_test))[0]

            log(f"\n{'─'*80}")
            log(f"McNemar Discordant Cases")
            log(f"b={b}: CNN correct / AdaBoost wrong")
            for ii in b_idx:
                log(f"  test[{ii:2d}] dataset[{test_indices[ii]:3d}]  "
                    f"true={label_name[y_test[ii]]}  "
                    f"CNN={label_name[cnn_bin[ii]]}({cnn_probs[ii]:.3f})  "
                    f"AdaBoost={label_name[ada_bin[ii]]}({test_probs[ii]:.3f})")
            log(f"c={c}: CNN wrong / AdaBoost correct")
            for ii in c_idx:
                log(f"  test[{ii:2d}] dataset[{test_indices[ii]:3d}]  "
                    f"true={label_name[y_test[ii]]}  "
                    f"CNN={label_name[cnn_bin[ii]]}({cnn_probs[ii]:.3f})  "
                    f"AdaBoost={label_name[ada_bin[ii]]}({test_probs[ii]:.3f})")

            discordant = {
                'b_cases': [
                    {'test_idx': int(ii), 'dataset_idx': int(test_indices[ii]),
                     'true_label': int(y_test[ii]), 'true_name': label_name[y_test[ii]],
                     'cnn_pred': int(cnn_bin[ii]),  'cnn_prob':  round(float(cnn_probs[ii]), 4),
                     'ada_pred': int(ada_bin[ii]),  'ada_prob':  round(float(test_probs[ii]), 4)}
                    for ii in b_idx
                ],
                'c_cases': [
                    {'test_idx': int(ii), 'dataset_idx': int(test_indices[ii]),
                     'true_label': int(y_test[ii]), 'true_name': label_name[y_test[ii]],
                     'cnn_pred': int(cnn_bin[ii]),  'cnn_prob':  round(float(cnn_probs[ii]), 4),
                     'ada_pred': int(ada_bin[ii]),  'ada_prob':  round(float(test_probs[ii]), 4)}
                    for ii in c_idx
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
                    'delta_auc':    round(delta_auc, 4),
                    'z_stat':       round(z_stat, 4),
                    'p_value':      round(p_auc, 4),
                    'significance': sig_auc,
                },
            }
    else:
        log("\nWarning: rq2_results.json not found — CNN comparison skipped.")

    # Save AdaBoost test probabilities
    ada_probs_path = os.path.join(CONFIG['results_dir'], 'rq3_test_probs.npy')
    np.save(ada_probs_path, test_probs)
    log(f"\n✓ AdaBoost test probs -> {ada_probs_path}")

    result = {
        'pipeline': 'full Khandakar et al. (2021) pipeline',
        'steps': [
            '1. Extract 39 features (Age, Gender, TCI, HighestTemp, NTR_1-5, 5-zones x 6-stats)',
            '2. Correlation filter >95%',
            '3. SMOTE inside each CV fold and on final training set',
            '4. RF feature ranking -> top 10 selected',
            '5. AdaBoost (decision stump, max_depth=1, class_weight=balanced)',
        ],
        'adaboost_params': (f'n_estimators={ADA_N_EST}, '
                            f'learning_rate={ADA_LR}, '
                            f'base=DecisionStump(max_depth=1, class_weight=balanced)'),
        'features_before_filter': feature_names,
        'features_after_corr_filter': names_c,
        'top10_features': top10_names,
        'top10_rf_importances': [round(float(v), 6) for v in top10_imp],
        'fold_aucs':       [round(a, 4) for a in fold_aucs],
        'mean_cv_auc':     round(float(np.mean(fold_aucs)), 4),
        'std_cv_auc':      round(float(np.std(fold_aucs)),  4),
        'adaboost_threshold': ada_thr,
        'cnn_threshold':     cnn_thr,
        'test_metrics':      ada_metrics,
        'statistical_tests': stat_tests,
    }
    out = os.path.join(CONFIG['results_dir'], 'rq3_results.json')
    with open(out, 'w') as f:
        json.dump(result, f, indent=2)
    log(f"\n✓ Results -> {out}")


if __name__ == '__main__':
    main()
