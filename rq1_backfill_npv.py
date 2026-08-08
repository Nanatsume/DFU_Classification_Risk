"""One-off backfill: add missing 'npv' field to all existing RQ1 metrics.json
files, using the saved val_preds.npz predictions and the (deterministic)
patient-level fold splits, without any retraining.
"""
import glob
import json
import os

import numpy as np

from dfu_common import CONFIG, SEED, load_preprocessed_inaoe, get_inaoe_patient_ids, \
    create_patient_fold_splits

DATA_SOURCE = {
    'S1': '/home/ntphoto/DFU/INAOE_S1',
    'S2': '/home/ntphoto/DFU/INAOE_S2',
}


def main():
    fold_cache = {}
    for input_s, data_dir in DATA_SOURCE.items():
        images, labels = load_preprocessed_inaoe(data_dir, log=lambda *a: None)
        patient_ids = get_inaoe_patient_ids(data_dir)
        fold_indices, _ = create_patient_fold_splits(
            images, labels, patient_ids,
            n_splits=CONFIG['n_folds'], test_split=CONFIG['test_split'],
            random_state=SEED,
        )
        fold_cache[input_s] = (labels, fold_indices)

    pattern = os.path.join(CONFIG['results_dir'], 'rq1', '*', 'metrics.json')
    updated, skipped = 0, 0
    for mpath in sorted(glob.glob(pattern)):
        combo_dir = os.path.dirname(mpath)
        combo_id  = os.path.basename(combo_dir)
        with open(mpath) as f:
            m = json.load(f)

        if all('npv' in pf for pf in m['per_fold']):
            skipped += 1
            continue

        input_s = m['input_strategy']
        labels, fold_indices = fold_cache[input_s]

        vp_path = os.path.join(combo_dir, 'val_preds.npz')
        vp = np.load(vp_path)

        for fi, fold in enumerate(fold_indices):
            key = f'fold{fi + 1}'
            y_v = labels[fold['val_idx']]
            pred = vp[key]
            yb = (pred >= 0.5).astype(int)
            tn = int(np.sum((yb == 0) & (y_v == 0)))
            fn = int(np.sum((yb == 0) & (y_v == 1)))
            npv = tn / (tn + fn) if (tn + fn) > 0 else 0.0
            m['per_fold'][fi]['npv'] = npv

        npvs = [pf['npv'] for pf in m['per_fold']]
        m['mean']['npv'] = float(np.mean(npvs))
        m['std']['npv']  = float(np.std(npvs))

        with open(mpath, 'w') as f:
            json.dump(m, f, indent=2)
        updated += 1
        print(f"✓ {combo_id}: npv mean={m['mean']['npv']:.4f}")

    print(f"\nUpdated: {updated}  Skipped (already had npv): {skipped}")


if __name__ == '__main__':
    main()
