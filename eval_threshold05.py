"""
Quick comparison: both models at threshold = 0.5 vs Youden threshold
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
cnn_probs  = np.load(f"{RESULTS_DIR}/final_eval_probs.npy")
bpnn_probs = np.load(f"{RESULTS_DIR}/rq3_test_probs.npy")

# Youden thresholds
with open(f"{RESULTS_DIR}/rq3_results.json") as f:
    rq3 = json.load(f)
cnn_youden  = rq3["cnn_threshold"]
bpnn_youden = rq3["mean_youden_threshold"]

# Compute metrics
cnn_05   = compute_metrics(y_true, cnn_probs,  THR)
bpnn_05  = compute_metrics(y_true, bpnn_probs, THR)
cnn_ydn  = compute_metrics(y_true, cnn_probs,  cnn_youden)
bpnn_ydn = compute_metrics(y_true, bpnn_probs, bpnn_youden)

metrics = ["Sensitivity", "Specificity", "AUC", "PPV", "NPV", "F1"]
header  = f"{'Metric':<14} {'CNN (0.5)':>10} {'CNN (Youden)':>14} {'BPNN (0.5)':>12} {'BPNN (Youden)':>14}"
print(header)
print("-" * len(header))
for m in metrics:
    print(f"{m:<14} {cnn_05[m]:>10.4f} {cnn_ydn[m]:>14.4f} {bpnn_05[m]:>12.4f} {bpnn_ydn[m]:>14.4f}")

print(f"\nThresholds used — CNN Youden: {cnn_youden:.4f} | BPNN Youden: {bpnn_youden:.4f}")
