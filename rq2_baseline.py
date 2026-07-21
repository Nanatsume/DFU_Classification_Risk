"""RQ2 Baseline: Exhaustive pipeline search following Khandakar et al. (2021).

Replicates the full methodology of Khandakar et al. (2021):
  1. Extract 39 thermal features (demographic, NTR class fractions, zone statistics)
  2. Standardise and apply correlation filter (>95% pairwise correlation)
  3. For each of 3 ranking methods (RF, XGBoost, ExtraTree):
       rank features on SMOTE-resampled training set
  4. For each combination of (ranking method x classifier x n_features):
       run 5-fold CV with SMOTE per fold, record mean AUC-ROC
  5. Select best combination by mean CV AUC-ROC
  6. Train final model on full 80% training set, evaluate on 20% test set

10 classifiers: AdaBoost, RandomForest, ExtraTree, GradientBoosting, SVM,
                KNN, XGBoost, LogisticRegression, LDA, MLP

Total combinations: 3 x 10 x N  (N = features after correlation filter)

Reads  : ThermoDataBase/ (raw CSVs and Excel demographics)
         results/rq1_results.json  (for data split indices)

Writes : results/rq2_baseline_results.json
         results/rq2_best_test_probs.npy  (test probabilities of best model)

Run after rq1_compare.py and before rq2_compare.py.
"""

import os
import json
import time
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import (
    AdaBoostClassifier, RandomForestClassifier, ExtraTreesClassifier,
    GradientBoostingClassifier,
)
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import roc_auc_score, f1_score
from sklearn.preprocessing import StandardScaler
from imblearn.over_sampling import SMOTE
import xgboost as xgb

from dfu_common import (
    CONFIG, SEED, make_logger, load_preprocessed_inaoe, create_fold_splits,
)

RAW_DIR    = '/home/ntphoto/Project/ThermoDataBase'
EXCEL_PATH = os.path.join(RAW_DIR, 'Plantar Thermogram Database.xlsx')

DATA_SOURCE = {
    'S1': '/home/ntphoto/DFU/INAOE_S1',
    'S2': '/home/ntphoto/DFU/INAOE_S2',
}

_ET_CLASSES = np.array([26.5, 28.5, 29.5, 30.5, 31.0, 32.5, 33.5, 34.5])
_NTR_BOUNDS = [0.0, 26.5, 28.5, 30.5, 32.5, float('inf')]
ZONES = ['LPA', 'MPA', 'LCA', 'MCA', 'FullFoot']

RANKING_METHODS = ['RF', 'XGBoost', 'ExtraTree']


def make_classifiers():
    return {
        'AdaBoost': AdaBoostClassifier(
            estimator=DecisionTreeClassifier(
                max_depth=1, class_weight='balanced', random_state=SEED),
            n_estimators=50, learning_rate=1.0, random_state=SEED),
        'RandomForest': RandomForestClassifier(
            n_estimators=100, class_weight='balanced',
            random_state=SEED, n_jobs=-1),
        'ExtraTree': ExtraTreesClassifier(
            n_estimators=100, class_weight='balanced',
            random_state=SEED, n_jobs=-1),
        'GradientBoosting': GradientBoostingClassifier(
            n_estimators=100, random_state=SEED),
        'SVM': SVC(
            kernel='rbf', class_weight='balanced',
            probability=True, random_state=SEED),
        'KNN': KNeighborsClassifier(n_neighbors=5, n_jobs=-1),
        'XGBoost': xgb.XGBClassifier(
            n_estimators=100, random_state=SEED,
            eval_metric='logloss', n_jobs=-1),
        'LogisticRegression': LogisticRegression(
            class_weight='balanced', max_iter=1000, random_state=SEED),
        'LDA': LinearDiscriminantAnalysis(),
        'MLP': MLPClassifier(
            hidden_layer_sizes=(100,), max_iter=500, random_state=SEED),
    }


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


def _nonzero(arr):
    flat = arr.flatten()
    return flat[flat > 0.0]


def _read_csv_arr(path):
    return pd.read_csv(path, header=None).values.astype(np.float64)


def _ntr_class(pixels, cls):
    if len(pixels) == 0:
        return 0.0
    lo = _NTR_BOUNDS[cls - 1]
    hi = _NTR_BOUNDS[cls]
    in_cls = np.sum((pixels > lo) & (pixels <= hi))
    return float(in_cls) / len(pixels)


def _et_feature(pixels):
    if len(pixels) == 0:
        return 0.0
    n_cls       = len(_ET_CLASSES)
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
        return float(_ET_CLASSES[j]) if denom == 0 else float(
            (a[j] * _ET_CLASSES[j] + a[j + 1] * _ET_CLASSES[j + 1]) / denom)
    if j == n_cls - 1:
        denom = a[j - 1] + a[j]
        return float(_ET_CLASSES[j]) if denom == 0 else float(
            (a[j - 1] * _ET_CLASSES[j - 1] + a[j] * _ET_CLASSES[j]) / denom)
    denom = a[j - 1] + a[j] + a[j + 1]
    return float(_ET_CLASSES[j]) if denom == 0 else float(
        (a[j - 1] * _ET_CLASSES[j - 1] + a[j] * _ET_CLASSES[j] +
         a[j + 1] * _ET_CLASSES[j + 1]) / denom)


def _hse_feature(pixels, et):
    # HSE = |Cl - ET|  (Khandakar et al. 2021, Eq. 4)
    # Cl = highest temperature present in the angiosome
    if len(pixels) == 0:
        return 0.0
    cl = float(pixels.max())
    return abs(cl - et)


def _zone_csv_path(stem, group_label, zone):
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


def _build_feature_names():
    names = ['Age', 'Gender', 'TCI', 'HighestTemp']
    names += [f'NTR_Class{c}' for c in range(1, 6)]
    for z in ZONES:
        for stat in ['Mean', 'Median', 'SD', 'ET', 'ETD', 'HSE']:
            names.append(f'{z}_{stat}')
    return names


FEATURE_NAMES_39 = _build_feature_names()


def extract_khandakar_features_full(preproc_dir, log=print):
    log("Extracting all 39 Khandakar et al. features ...")
    xl     = pd.ExcelFile(EXCEL_PATH)
    cg_raw = xl.parse('Control Group', header=None)
    dm_raw = xl.parse('DM Group',      header=None)

    def parse_sheet(raw):
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

    entries = []
    for group_label, preproc_sub in [
        ('Control Group', os.path.join(preproc_dir, 'CT')),
        ('DM Group',      os.path.join(preproc_dir, 'DM')),
    ]:
        stems = sorted(f[:-4] for f in os.listdir(preproc_sub) if f.endswith('.npy'))
        for stem in stems:
            entries.append((stem, group_label))

    log(f"  Total images to process: {len(entries)}")

    log("  Pass 1 — computing ET for all zones ...")
    et_map = {}
    for stem, group_label in entries:
        et_map[stem] = {}
        for zone in ZONES:
            pix = _get_zone_pixels(stem, group_label, zone)
            et_map[stem][zone] = _et_feature(pix)

    etd_map = {}
    for stem, _ in entries:
        parts      = stem.split('_')
        other_foot = 'R' if parts[2] == 'L' else 'L'
        other_stem = f'{parts[0]}_{parts[1]}_{other_foot}'
        etd_map[stem] = {}
        for zone in ZONES:
            et_self  = et_map.get(stem,       {}).get(zone, 0.0)
            et_other = et_map.get(other_stem, {}).get(zone, 0.0)
            etd_map[stem][zone] = abs(et_self - et_other)

    log("  Pass 2 — computing all features ...")
    rows    = []
    missing = 0
    for idx, (stem, group_label) in enumerate(entries):
        parts   = stem.split('_')
        subject = parts[0]
        gender  = parts[1]
        foot    = parts[2]

        if subject in demo.index:
            row        = demo.loc[subject]
            age        = float(row['Age'])   if not pd.isna(row['Age'])   else 0.0
            gender_val = 1.0 if str(row['Gender']).strip().upper() == 'F' else 0.0
            tci_col    = 'TCI_L' if foot == 'L' else 'TCI_R'
            tci        = float(row[tci_col]) if not pd.isna(row[tci_col]) else 0.0
        else:
            age        = 0.0
            gender_val = 1.0 if gender.upper() == 'F' else 0.0
            tci        = 0.0
            missing   += 1

        foot_pix     = _get_zone_pixels(stem, group_label, 'FullFoot')
        highest_temp = float(foot_pix.max()) if len(foot_pix) > 0 else 0.0
        ntr_feats    = [_ntr_class(foot_pix, c) for c in range(1, 6)]

        zone_feats = []
        for zone in ZONES:
            pix = _get_zone_pixels(stem, group_label, zone)
            zone_feats.extend([
                float(np.mean(pix))   if len(pix) > 0 else 0.0,
                float(np.median(pix)) if len(pix) > 0 else 0.0,
                float(np.std(pix))    if len(pix) > 0 else 0.0,
                et_map[stem][zone],
                etd_map[stem][zone],
                _hse_feature(pix, et_map[stem][zone]),
            ])

        rows.append([age, gender_val, tci, highest_temp] + ntr_feats + zone_feats)
        if (idx + 1) % 50 == 0:
            log(f"    {idx + 1}/{len(entries)} done")

    if missing:
        log(f"  Warning: {missing} subjects missing from Excel — demographics set to 0.")
    X = np.array(rows, dtype=np.float32)
    log(f"  Done — feature matrix: {X.shape}")
    return X, FEATURE_NAMES_39


def correlation_filter(X, feature_names, threshold=0.95, log=print):
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


def save_correlation_heatmaps(X_before, names_before, X_after, names_after,
                               out_dir, log=print):
    """Save before/after correlation heatmaps, replicating Khandakar et al. (2021) Fig. 3."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        log("  Warning: matplotlib/seaborn not available — skipping heatmaps")
        return []

    os.makedirs(out_dir, exist_ok=True)
    paths = []

    panels = [
        (X_before, names_before, 'rq2_corr_heatmap_A_before.png',
         f'(A) Correlation matrix — all {len(names_before)} features'),
        (X_after,  names_after,  'rq2_corr_heatmap_B_after.png',
         f'(B) After removing highly correlated features ({len(names_after)} remaining)'),
    ]

    for X, names, fname, panel_title in panels:
        n    = len(names)
        corr = np.corrcoef(X.T)
        fw   = max(7.0, n * 0.42)
        fig, ax = plt.subplots(figsize=(fw, fw))
        sns.heatmap(
            corr,
            ax=ax,
            vmin=-1, vmax=1,
            cmap='RdBu_r',
            xticklabels=names,
            yticklabels=names,
            linewidths=0.2,
            linecolor='white',
            square=True,
            annot=False,
            cbar_kws={'label': 'Pearson r', 'shrink': 0.6},
        )
        ax.set_title(panel_title, fontsize=10, pad=8)
        tick_fs = max(5, 9 - n // 8)
        ax.tick_params(axis='x', rotation=90, labelsize=tick_fs)
        ax.tick_params(axis='y', rotation=0,  labelsize=tick_fs)
        plt.tight_layout()
        path = os.path.join(out_dir, fname)
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        log(f"  Saved: {path}")
        paths.append(path)

    return paths


def get_feature_ranking(X, y, method, log=print):
    log(f"  Computing {method} feature ranking ...")
    if method == 'RF':
        model = RandomForestClassifier(
            n_estimators=200, random_state=SEED, n_jobs=-1)
    elif method == 'XGBoost':
        model = xgb.XGBClassifier(
            n_estimators=200, random_state=SEED,
            eval_metric='logloss', use_label_encoder=False, n_jobs=-1)
    elif method == 'ExtraTree':
        model = ExtraTreesClassifier(
            n_estimators=200, random_state=SEED, n_jobs=-1)
    model.fit(X, y)
    importances = model.feature_importances_
    ranked = np.argsort(importances)[::-1]
    return ranked, importances


def save_feature_importance_plot(ranked_indices, importances, feature_names,
                                  ranking_method, out_dir, log=print):
    """Save horizontal bar chart of feature importance scores (like Khandakar et al. Fig. 7)."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        log("  Warning: matplotlib not available — skipping importance plot")
        return

    n = len(ranked_indices)
    names = [feature_names[i] for i in ranked_indices]
    imps  = [float(importances[i]) for i in ranked_indices]

    # Reverse for horizontal bar (highest at top)
    names_plot = names[::-1]
    imps_plot  = imps[::-1]

    fig_h = max(5.0, n * 0.33)
    fig, ax = plt.subplots(figsize=(8, fig_h))

    colors = plt.cm.RdYlGn(np.linspace(0.25, 0.85, n))
    ax.barh(names_plot, imps_plot, color=colors)

    ax.set_xlabel('Relative Importance', fontsize=11)
    ax.set_ylabel('Features', fontsize=11)
    ax.set_title(f'{ranking_method} Feature Selection\n(top {n} selected features)', fontsize=12)
    ax.tick_params(axis='y', labelsize=9)

    for i, v in enumerate(imps_plot):
        ax.text(v + max(imps_plot) * 0.01, i, f'{v:.4f}', va='center', fontsize=7)

    plt.tight_layout()
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f'rq2_feature_importance_{ranking_method}.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    log(f"  Saved: {path}")
    return path


def cv_score(X_all, y_all, ranked_indices, n_features, clf_template, fold_indices):
    X_top = X_all[:, ranked_indices[:n_features]]
    aucs  = []
    for fi in fold_indices:
        X_tr = X_top[fi['train_idx']]
        y_tr = y_all[fi['train_idx']]
        X_v  = X_top[fi['val_idx']]
        y_v  = y_all[fi['val_idx']]
        smote = SMOTE(random_state=SEED)
        X_tr_sm, y_tr_sm = smote.fit_resample(X_tr, y_tr)
        clf = clone(clf_template)
        clf.fit(X_tr_sm, y_tr_sm)
        if hasattr(clf, 'predict_proba'):
            probs = clf.predict_proba(X_v)[:, 1]
        else:
            probs = clf.decision_function(X_v)
        try:
            aucs.append(float(roc_auc_score(y_v, probs)))
        except Exception:
            aucs.append(0.0)
    return float(np.mean(aucs)), float(np.std(aucs))


def main():
    log = make_logger('rq2_baseline')

    images, labels = load_preprocessed_inaoe(DATA_SOURCE['S1'], log=log)
    fold_indices, test_indices = create_fold_splits(
        images, labels,
        n_splits=CONFIG['n_folds'],
        test_split=CONFIG['test_split'],
        random_state=SEED,
    )

    cache = os.path.join(CONFIG['checkpoint_dir'], 'khandakar_features_39_v2.npz')
    if os.path.exists(cache):
        log(f"✓ Loading cached 39-feature matrix: {cache}")
        loaded        = np.load(cache, allow_pickle=True)
        X_all         = loaded['features']
        feature_names = list(loaded['feature_names'])
    else:
        X_all, feature_names = extract_khandakar_features_full(
            DATA_SOURCE['S1'], log=log)
        np.savez(cache, features=X_all,
                 feature_names=np.array(feature_names, dtype=str))
        log(f"✓ Features cached -> {cache}")

    train_mask               = np.ones(len(labels), dtype=bool)
    train_mask[test_indices] = False
    X_train, y_train = X_all[train_mask],   labels[train_mask]
    X_test,  y_test  = X_all[test_indices], labels[test_indices]
    log(f"Train: {len(y_train)}  |  Test: {len(y_test)}")

    scaler    = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s  = scaler.transform(X_test)
    X_all_s   = scaler.transform(X_all)

    log(f"\n{'='*80}")
    log("Step 1: Correlation-based feature filtering (threshold=0.95)")
    log(f"{'='*80}")
    X_train_c, names_c, kept_indices = correlation_filter(
        X_train_s, feature_names, threshold=0.95, log=log)
    X_test_c = X_test_s[:, kept_indices]
    X_all_c  = X_all_s[:, kept_indices]
    n_max    = len(names_c)
    log(f"  Features available for ranking: {n_max}")

    log(f"\n{'='*80}")
    log("Step 1b: Correlation heatmaps (before and after filter)")
    log(f"{'='*80}")
    save_correlation_heatmaps(
        X_train_s, feature_names,
        X_train_c, names_c,
        out_dir=CONFIG['results_dir'],
        log=log,
    )

    log(f"\n{'='*80}")
    log("Step 2: Compute feature rankings (RF, XGBoost, ExtraTree) on SMOTE training set")
    log(f"{'='*80}")
    smote_rank = SMOTE(random_state=SEED)
    X_rank_sm, y_rank_sm = smote_rank.fit_resample(X_train_c, y_train)

    rankings = {}
    importances_map = {}
    for method in RANKING_METHODS:
        ranked, importances = get_feature_ranking(X_rank_sm, y_rank_sm, method, log=log)
        rankings[method]     = ranked
        importances_map[method] = importances
        log(f"    Top 10: {[names_c[i] for i in ranked[:10]]}")

    log(f"\n{'='*80}")
    log(f"Step 3: Exhaustive search — "
        f"{len(RANKING_METHODS)} rankings x 10 classifiers x {n_max} feature counts "
        f"= {len(RANKING_METHODS) * 10 * n_max} combinations")
    log(f"{'='*80}")

    classifiers = make_classifiers()
    all_results = []
    total  = len(RANKING_METHODS) * len(classifiers) * n_max
    count  = 0
    t0     = time.time()

    for method in RANKING_METHODS:
        ranked = rankings[method]
        for clf_name, clf_template in classifiers.items():
            for n_feat in range(1, n_max + 1):
                count += 1
                mean_auc, std_auc = cv_score(
                    X_all_c, labels, ranked, n_feat, clf_template, fold_indices)
                all_results.append({
                    'ranking':      method,
                    'classifier':   clf_name,
                    'n_features':   n_feat,
                    'mean_cv_auc':  round(mean_auc, 4),
                    'std_cv_auc':   round(std_auc,  4),
                })
                if count % 30 == 0 or count == total:
                    elapsed = time.time() - t0
                    eta     = elapsed / count * (total - count)
                    log(f"  [{count:4d}/{total}] "
                        f"{method:<10} {clf_name:<20} top{n_feat:2d} "
                        f"AUC={mean_auc:.4f}  "
                        f"elapsed={elapsed/60:.1f}min  ETA={eta/60:.1f}min")

    best = max(all_results, key=lambda x: x['mean_cv_auc'])
    log(f"\n{'='*80}")
    log(f"Best combination: {best['ranking']} + {best['classifier']} "
        f"+ top {best['n_features']} features  ->  CV AUC = {best['mean_cv_auc']:.4f}")
    log(f"{'='*80}")

    best_ranked  = rankings[best['ranking']]
    n_best       = best['n_features']
    best_names   = [names_c[i] for i in best_ranked[:n_best]]
    X_train_best = X_train_c[:, best_ranked[:n_best]]
    X_test_best  = X_test_c[:,  best_ranked[:n_best]]

    log(f"  Selected features: {best_names}")

    log(f"\n{'='*80}")
    log("Step 3b: Feature importance plot (best ranking method)")
    log(f"{'='*80}")
    save_feature_importance_plot(
        best_ranked[:n_best],
        importances_map[best['ranking']],
        names_c,
        ranking_method=best['ranking'],
        out_dir=CONFIG['results_dir'],
        log=log,
    )

    log(f"\n{'='*80}")
    log("Step 4: Train final model on full training set")
    log(f"{'='*80}")
    smote_final = SMOTE(random_state=SEED)
    X_train_final, y_train_final = smote_final.fit_resample(X_train_best, y_train)
    log(f"  After SMOTE: {X_train_final.shape[0]} samples")

    final_clf = clone(classifiers[best['classifier']])
    final_clf.fit(X_train_final, y_train_final)

    if hasattr(final_clf, 'predict_proba'):
        test_probs = final_clf.predict_proba(X_test_best)[:, 1]
    else:
        test_probs = final_clf.decision_function(X_test_best)

    test_metrics = metrics_at(y_test, test_probs, 0.5)

    log(f"\n{'='*80}")
    log(f"TEST RESULTS  (threshold=0.5)")
    log(f"{'='*80}")
    for k, v in test_metrics.items():
        log(f"  {k:<14}: {v:.4f}")

    probs_path = os.path.join(CONFIG['results_dir'], 'rq2_best_test_probs.npy')
    np.save(probs_path, test_probs)
    log(f"\n✓ Test probs -> {probs_path}")

    result = {
        'pipeline': 'Khandakar et al. (2021) methodology — all combinations evaluated',
        'n_features_before_filter': len(feature_names),
        'n_features_after_filter':  n_max,
        'features_after_filter':    names_c,
        'ranking_methods':          RANKING_METHODS,
        'n_classifiers':            len(classifiers),
        'classifier_names':         list(classifiers.keys()),
        'total_combinations':       total,
        'best': {
            'ranking':    best['ranking'],
            'classifier': best['classifier'],
            'n_features': best['n_features'],
            'feature_names': best_names,
            'mean_cv_auc':   best['mean_cv_auc'],
            'std_cv_auc':    best['std_cv_auc'],
        },
        'test_metrics':  test_metrics,
        'all_results':   all_results,
    }
    out = os.path.join(CONFIG['results_dir'], 'rq2_baseline_results.json')
    with open(out, 'w') as f:
        json.dump(result, f, indent=2)
    log(f"✓ Full results -> {out}")


if __name__ == '__main__':
    main()
