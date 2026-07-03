"""RQ1: Aggregate all 48 CV results and select S1_best and S2_best.

For each input strategy (S1, S2), select the best backbone × fine-tuning
strategy combination by mean AUC-ROC across the 5-fold CV.

Reads  : results/rq1/*/metrics.json  (48 files from rq1_run_all.sh)
Writes : results/rq1_results.json

Usage:
    python rq1_compare.py
"""

import json
import os
import glob
import numpy as np

from dfu_common import CONFIG, ALL_STRATEGIES

BACKBONES        = ['EfficientNetB0', 'ResNet50', 'ConvNeXt-Tiny']
INPUT_STRATEGIES = ['S1', 'S2']


def best_for_input(results, input_s):
    subset = [r for r in results if r['input_strategy'] == input_s]
    if not subset:
        return None
    return max(subset, key=lambda r: r['mean']['auc'])


def print_table(results, input_s):
    subset = sorted(
        [r for r in results if r['input_strategy'] == input_s],
        key=lambda r: r['mean']['auc'], reverse=True,
    )
    print(f"\n{'─'*95}")
    print(f"  Input strategy: {input_s}  ({len(subset)}/24 completed)")
    print(f"{'─'*95}")
    print(f"  {'#':<4} {'Backbone':<18} {'Strategy':<10} "
          f"{'AUC':>8} {'±Std':>6} {'Sens':>7} {'Spec':>7} {'F1':>7}")
    print(f"  {'─'*88}")
    for i, r in enumerate(subset):
        m   = r['mean']
        s   = r['std']
        tag = '  ◄ BEST' if i == 0 else ''
        print(f"  {i+1:<4} {r['backbone']:<18} {r['strategy']:<10} "
              f"{m['auc']:>8.4f} {s['auc']:>6.4f} {m['sens']:>7.4f} "
              f"{m['spec']:>7.4f} {m['f1']:>7.4f}{tag}")


def main():
    pattern = os.path.join(CONFIG['results_dir'], 'rq1', '*', 'metrics.json')
    files   = sorted(glob.glob(pattern))

    if not files:
        print("No metrics.json files found under results/rq1/. Run rq1_run_all.sh first.")
        return

    results = []
    for f in files:
        with open(f) as fp:
            r = json.load(fp)
        results.append(r)

    expected = {f'{b}_{s}_{i}'
                for b in BACKBONES for s in ALL_STRATEGIES for i in INPUT_STRATEGIES}
    found    = {f"{r['backbone']}_{r['strategy']}_{r['input_strategy']}" for r in results}
    missing  = sorted(expected - found)

    print(f"\n{'='*95}")
    print(f"RQ1: 5-FOLD CV RESULTS — {len(results)}/48 COMBINATIONS COMPLETED")
    print(f"{'='*95}")

    for inp in INPUT_STRATEGIES:
        print_table(results, inp)

    if missing:
        print(f"\n⚠  Missing combos ({len(missing)}): {', '.join(missing)}")

    s1_best = best_for_input(results, 'S1')
    s2_best = best_for_input(results, 'S2')

    def best_entry(b):
        if b is None:
            return None
        combo_id = f"{b['backbone']}_{b['strategy']}_{b['input_strategy']}"
        print(f"\n→ {b['input_strategy']}_BEST : {combo_id}")
        print(f"  AUC-ROC    : {b['mean']['auc']:.4f} ± {b['std']['auc']:.4f}")
        print(f"  Sensitivity: {b['mean']['sens']:.4f}")
        print(f"  Specificity: {b['mean']['spec']:.4f}")
        print(f"  F1-Score   : {b['mean']['f1']:.4f}")
        ep = b.get('avg_epochs', {})
        print(f"  Avg epochs : phase1={ep.get('phase1')}, phase2={ep.get('phase2')}")
        return {
            'combo_id':       combo_id,
            'backbone':       b['backbone'],
            'strategy':       b['strategy'],
            'input_strategy': b['input_strategy'],
            'cv_metrics':     {'mean': b['mean'], 'std': b['std']},
            'avg_epochs':     b.get('avg_epochs', {}),
            'per_fold':       b['per_fold'],
        }

    output = {
        'S1_best': best_entry(s1_best),
        'S2_best': best_entry(s2_best),
        'all_results': [
            {
                'combo_id':       f"{r['backbone']}_{r['strategy']}_{r['input_strategy']}",
                'backbone':       r['backbone'],
                'strategy':       r['strategy'],
                'input_strategy': r['input_strategy'],
                'mean_auc':       r['mean']['auc'],
                'std_auc':        r['std']['auc'],
                'mean_sens':      r['mean']['sens'],
                'mean_spec':      r['mean']['spec'],
                'mean_f1':        r['mean']['f1'],
                'mean_acc':       r['mean']['acc'],
            }
            for r in sorted(results, key=lambda r: r['mean']['auc'], reverse=True)
        ],
        'missing_combos': missing,
    }

    out_path = os.path.join(CONFIG['results_dir'], 'rq1_results.json')
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\n✓ Saved → {out_path}")


if __name__ == '__main__':
    main()
