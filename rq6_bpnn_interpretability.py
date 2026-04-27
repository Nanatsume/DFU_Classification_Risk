"""RQ6 (Supplementary): BPNN Feature Interpretability.

Retrain the best BPNN (using hyperparameters from rq5_results.json) on the
full training set, then run:
  - Permutation Importance (sklearn, n_repeats=30, scoring=AUC)
  - SHAP KernelExplainer (beeswarm + bar plots)

Outputs saved to results/rq6_bpnn_interpretability/.
Run after rq5_bpnn_comparison.py.
"""

import os
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import shap

from skimage.feature import graycomatrix, graycoprops, hog
from skimage.color import rgb2gray
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.inspection import permutation_importance
from scipy.stats import skew, kurtosis

from dfu_common import (
    CONFIG, SEED, make_logger, load_preprocessed_inaoe, create_fold_splits,
)

FEAT_NAMES = (
    [f"{p} {a}" for p in ['Contrast', 'Correlation', 'Energy', 'Homogeneity']
                for a in ['0°', '45°', '90°', '135°']]
    + ['HOG Mean', 'HOG Std', 'HOG Var', 'HOG Median',
       'HOG Max', 'HOG Min', 'HOG Skew', 'HOG Kurtosis']
)


# ── Feature extraction (same as rq5) ─────────────────────────────────────────

def glcm_features(img_rgb):
    gray = (rgb2gray(img_rgb) * 255).astype(np.uint8)
    gray = (gray // 32).astype(np.uint8)
    glcm = graycomatrix(gray, distances=[1],
                        angles=[0, np.pi/4, np.pi/2, 3*np.pi/4],
                        levels=8, symmetric=True, normed=True)
    props = ['contrast', 'correlation', 'energy', 'homogeneity']
    return np.concatenate([graycoprops(glcm, p).flatten() for p in props]).astype(np.float32)


def hog_features(img_rgb):
    gray = rgb2gray(img_rgb)
    hog_vec = hog(gray, orientations=9, pixels_per_cell=(8, 8),
                  cells_per_block=(2, 2), block_norm='L2-Hys')
    return np.array([
        hog_vec.mean(), hog_vec.std(), hog_vec.var(), np.median(hog_vec),
        hog_vec.max(), hog_vec.min(), float(skew(hog_vec)), float(kurtosis(hog_vec)),
    ], dtype=np.float32)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log = make_logger('rq6')

    rq5_path = os.path.join(CONFIG['results_dir'], 'rq5_results.json')
    if not os.path.exists(rq5_path):
        log("❌ rq5_results.json not found. Run rq5_bpnn_comparison.py first.")
        return
    with open(rq5_path) as f:
        rq5 = json.load(f)

    images, labels = load_preprocessed_inaoe(CONFIG['data_source'], log=log)
    _, test_indices = create_fold_splits(
        images, labels,
        n_splits=CONFIG['n_folds'],
        test_split=CONFIG['test_split'],
        random_state=SEED,
    )

    # Load cached features
    cache = os.path.join(CONFIG['checkpoint_dir'], 'glcm_hog_features.npz')
    if os.path.exists(cache):
        log(f"✓ Loading cached features: {cache}")
        X_feat = np.load(cache)['features']
    else:
        log("Extracting GLCM + HOG features ...")
        feats = []
        for i, img in enumerate(images):
            feats.append(np.concatenate([glcm_features(img), hog_features(img)]))
            if (i + 1) % 100 == 0:
                log(f"  {i+1}/{len(images)}")
        X_feat = np.array(feats, dtype=np.float32)
        np.savez(cache, features=X_feat)

    train_mask = np.ones(len(labels), dtype=bool)
    train_mask[test_indices] = False
    X_train, y_train = X_feat[train_mask], labels[train_mask]
    X_test,  y_test  = X_feat[test_indices], labels[test_indices]

    # Parse best params from rq5
    import ast
    arch_str = rq5['bpnn_architecture']
    avg_iter = rq5['avg_stopping_iter']
    hidden   = ast.literal_eval(arch_str[:arch_str.index(')') + 1])
    alpha    = float(arch_str.split('alpha=')[1])

    sc = StandardScaler()
    X_train_s = sc.fit_transform(X_train)
    X_test_s  = sc.transform(X_test)

    log(f"\n{'='*80}")
    log(f"RQ6: Retraining BPNN  (arch={hidden}, alpha={alpha}, iter={avg_iter})")
    log(f"{'='*80}")
    bpnn = MLPClassifier(
        hidden_layer_sizes=hidden, alpha=alpha,
        activation='tanh', solver='adam',
        max_iter=avg_iter, random_state=SEED,
    )
    bpnn.fit(X_train_s, y_train)

    out_dir = os.path.join(CONFIG['results_dir'], 'rq6_bpnn_interpretability')
    os.makedirs(out_dir, exist_ok=True)

    # ── Permutation Importance ────────────────────────────────────────────────
    log(f"\n{'='*80}")
    log("RQ6: PERMUTATION IMPORTANCE (test set, n_repeats=30, scoring=AUC)")
    log(f"{'='*80}")

    perm  = permutation_importance(bpnn, X_test_s, y_test,
                                   n_repeats=30, random_state=SEED,
                                   scoring='roc_auc')
    order = np.argsort(perm.importances_mean)[::-1]

    log(f"  {'Feature':<26} {'Mean':>8} {'±Std':>8}")
    log(f"  {'─'*44}")
    for i in order:
        log(f"  {FEAT_NAMES[i]:<26} {perm.importances_mean[i]:>8.4f}"
            f" {perm.importances_std[i]:>8.4f}")

    fig, ax = plt.subplots(figsize=(9, 7))
    ax.barh(
        [FEAT_NAMES[i] for i in order[::-1]],
        perm.importances_mean[order[::-1]],
        xerr=perm.importances_std[order[::-1]],
        color='steelblue', alpha=0.8,
    )
    ax.set_xlabel('Mean AUC Decrease (± std)', fontsize=11)
    ax.set_title('BPNN — Permutation Feature Importance (Test Set)', fontsize=12)
    plt.tight_layout()
    perm_path = os.path.join(out_dir, 'permutation_importance.png')
    plt.savefig(perm_path, dpi=150, bbox_inches='tight')
    plt.close()
    log(f"\n✓ Saved: {perm_path}")

    # ── SHAP KernelExplainer ──────────────────────────────────────────────────
    log(f"\n{'='*80}")
    log("RQ6: SHAP VALUES (KernelExplainer, k-means background k=50)")
    log(f"{'='*80}")

    background  = shap.kmeans(X_train_s, 50)
    explainer   = shap.KernelExplainer(
        lambda x: bpnn.predict_proba(x)[:, 1], background
    )
    shap_values = explainer.shap_values(X_test_s, silent=True)

    # Beeswarm (dot) plot
    shap.summary_plot(shap_values, X_test_s, feature_names=FEAT_NAMES,
                      show=False, plot_type='dot')
    plt.title('BPNN — SHAP Summary (Beeswarm)', fontsize=12)
    plt.tight_layout()
    dot_path = os.path.join(out_dir, 'shap_beeswarm.png')
    plt.savefig(dot_path, dpi=150, bbox_inches='tight')
    plt.close()

    # Bar plot (mean |SHAP|)
    shap.summary_plot(shap_values, X_test_s, feature_names=FEAT_NAMES,
                      show=False, plot_type='bar')
    plt.title('BPNN — Mean |SHAP| Feature Importance', fontsize=12)
    plt.tight_layout()
    bar_path = os.path.join(out_dir, 'shap_bar.png')
    plt.savefig(bar_path, dpi=150, bbox_inches='tight')
    plt.close()

    log(f"✓ Saved: {dot_path}")
    log(f"✓ Saved: {bar_path}")
    log(f"\n✓ All outputs → {out_dir}/")


if __name__ == '__main__':
    main()
