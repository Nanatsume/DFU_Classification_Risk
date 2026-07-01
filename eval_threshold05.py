"""
Quick comparison: both models at threshold = 0.5 vs stored threshold
"""
import numpy as np
import json
from sklearn.metrics import roc_auc_score, confusion_matrix
from dfu_common import CONFIG, SEED, load_preprocessed_inaoe, create_fold_splits

RESULTS_DIR = "results"
THR = 0.5

def compute_metrics(y_true, probs, thr):
    preds = (probs >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, preds).ravel()
    sens = tp / (tp + fn)
    spec = tn / (tn + fp)
    ppv  = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    npv  = tn / (tn + fn) if (tn + fn) > 0 else 0.0
    f1   = 2 * ppv * sens / (ppv + sens) if (ppv + sens) > 0 else 0.0
    auc  = roc_auc_score(y_true, probs)
    return dict(Sensitivity=sens, Specificity=spec, AUC=auc, PPV=ppv, NPV=npv, F1=f1)

# Load test labels via dfu_common (seed=42, same split as training)
X, y = load_preprocessed_inaoe(CONFIG['data_source'])
_, test_idx = create_fold_splits(X, y, n_splits=CONFIG['n_folds'], test_split=CONFIG['test_split'], random_state=SEED)
y_true = y[test_idx]

# Load probabilities
cnn_probs = np.load(f"{RESULTS_DIR}/final_eval_probs.npy")
ada_probs = np.load(f"{RESULTS_DIR}/rq3_test_probs.npy")

# Stored thresholds
with open(f"{RESULTS_DIR}/rq3_results.json") as f:
    rq3 = json.load(f)
cnn_thr = rq3["cnn_threshold"]
ada_thr = rq3["adaboost_threshold"]

# Compute metrics at both threshold=0.5 and stored threshold
cnn_05  = compute_metrics(y_true, cnn_probs, THR)
ada_05  = compute_metrics(y_true, ada_probs, THR)
cnn_thr_m = compute_metrics(y_true, cnn_probs, cnn_thr)
ada_thr_m = compute_metrics(y_true, ada_probs, ada_thr)

metrics = ["Sensitivity", "Specificity", "AUC", "PPV", "NPV", "F1"]
header  = f"{'Metric':<14} {'CNN (0.5)':>10} {'CNN (thr)':>12} {'AdaBoost (0.5)':>16} {'AdaBoost (thr)':>16}"
print(header)
print("-" * len(header))
for m in metrics:
    print(f"{m:<14} {cnn_05[m]:>10.4f} {cnn_thr_m[m]:>12.4f} {ada_05[m]:>16.4f} {ada_thr_m[m]:>16.4f}")

print(f"\nThresholds used — CNN: {cnn_thr:.4f} | AdaBoost: {ada_thr:.4f}")
