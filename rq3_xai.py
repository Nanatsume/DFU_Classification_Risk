"""RQ3: Grad-CAM, Grad-CAM++, and Eigen-CAM visualisations on the best model.

Applies all three methods to sample images from the test set and saves
side-by-side heatmap overlays to results/rq3_xai/.
Saves summary to results/rq3_results.json.

NOTE: Pointing-game evaluation against ground-truth bounding boxes is deferred
until annotations are available.

Run after rq1_compare.py.
"""

import os
import json
import numpy as np
import tensorflow as tf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from dfu_common import (
    CONFIG, SEED, make_logger, load_preprocessed_inaoe, create_fold_splits,
)

N_SAMPLES_PER_CLASS = 4
POINTING_GAME_TAU   = 15   # spatial offset (pixels) applied to GT bbox on all sides

DATA_SOURCE = {
    'S1': '/home/ntphoto/DFU/INAOE_S1',
    'S2': '/home/ntphoto/DFU/INAOE_S2',
}

# ── Pointing-game annotation path ────────────────────────────────────────────
# TODO (POINTING GAME — when annotations arrive):
#
# 1. Create this JSON file inside the input-strategy data directory, e.g.:
#      <DATA_SOURCE[input_strategy]>/annotations.json
#    Format:
#      [
#        {
#          "filename": "DM/image001.npy",   ← relative to the data directory
#          "orig_w":   640,                 ← original image width  BEFORE 224×224 resize
#          "orig_h":   480,                 ← original image height BEFORE 224×224 resize
#          "bbox":     [x1, y1, x2, y2]    ← bounding box in ORIGINAL pixel coordinates
#        },
#        ...
#      ]
#    Note: bbox is in the coordinate space of the ORIGINAL image.
#    This script scales it to 224×224 automatically using:
#      x_scaled = x * 224 / orig_w
#      y_scaled = y * 224 / orig_h
#
# 2. No other code changes needed — run_pointing_game() below handles everything.
#
# 3. Evaluation method: instance-level pointing game (95th-percentile + τ variant)
#    - Expand GT bbox by τ=15 px on all sides (neighbourhood tolerance)
#    - Hit = any pixel in the top-5% activation region falls inside the expanded bbox
#    - Change τ by editing POINTING_GAME_TAU at the top of this file
#
# 4. Result: hit rate per CAM method saved to results/rq2_results.json


# ── Model helpers ─────────────────────────────────────────────────────────────

def get_base_layer(model):
    """Return the nested backbone layer (large submodel with many layers)."""
    for layer in model.layers:
        if hasattr(layer, 'layers') and len(layer.layers) > 5:
            return layer
    raise ValueError("Could not find base backbone layer in model")


def build_cam_models(model):
    """Return (feat_model, classifier_model).

    feat_model      : input (224,224,3) → 4-D spatial feature maps
                      includes all preprocessing layers (Rescaling, Lambda) + backbone
    classifier_model: spatial features  → scalar prediction
                      includes only post-backbone layers (GAP, Dense, ...)
    """
    base_layer = get_base_layer(model)

    # Walk model.layers in execution order.
    # Layers before the backbone (preprocessing) go into feat_model.
    # Layers after the backbone (classification head) go into clf_model.
    non_input = [l for l in model.layers
                 if not isinstance(l, tf.keras.layers.InputLayer)]
    backbone_idx = next(i for i, l in enumerate(non_input)
                        if l.name == base_layer.name)
    pre_layers  = non_input[:backbone_idx]   # Rescaling, Lambda, …
    post_layers = non_input[backbone_idx+1:] # GAP, Dense, Dropout, …

    # ── Feature extractor: preprocessing + backbone ──
    inp = tf.keras.Input(shape=(224, 224, 3))
    x = inp
    for layer in pre_layers:
        x = layer(x)
    x = base_layer(x, training=False)
    feat_model = tf.keras.Model(inputs=inp, outputs=x)

    # ── Classifier: post-backbone head only ──
    dummy         = tf.zeros((1, 224, 224, 3))
    spatial_shape = tuple(feat_model(dummy).shape[1:])  # (H, W, C)
    feat_inp = tf.keras.Input(shape=spatial_shape)
    x = feat_inp
    for layer in post_layers:
        x = layer(x)
    classifier_model = tf.keras.Model(inputs=feat_inp, outputs=x)

    return feat_model, classifier_model


# ── CAM implementations ───────────────────────────────────────────────────────

def grad_cam(feat_model, clf_model, img_array):
    """Standard Grad-CAM (Selvaraju et al., 2017)."""
    with tf.GradientTape() as tape:
        conv_out = feat_model(img_array, training=False)
        tape.watch(conv_out)
        score = clf_model(conv_out, training=False)[:, 0]
    grads  = tape.gradient(score, conv_out)
    pooled = tf.reduce_mean(grads, axis=(0, 1, 2))
    cam    = (conv_out[0] @ pooled[..., tf.newaxis]).numpy().squeeze()
    cam    = np.maximum(cam, 0)
    return cam / (cam.max() + 1e-8)


def grad_cam_pp(feat_model, clf_model, img_array):
    """Grad-CAM++ (Chattopadhay et al., 2018)."""
    with tf.GradientTape() as tape:
        conv_out = feat_model(img_array, training=False)
        tape.watch(conv_out)
        score = clf_model(conv_out, training=False)[:, 0]
    grads = tape.gradient(score, conv_out).numpy()[0]   # (H, W, C)
    acts  = conv_out.numpy()[0]                         # (H, W, C)

    grad_sq  = grads ** 2
    grad_cu  = grads ** 3
    sum_acts = acts.sum(axis=(0, 1), keepdims=True)
    denom    = 2.0 * grad_sq + sum_acts * grad_cu
    denom    = np.where(np.abs(denom) > 1e-8, denom, 1e-8)
    alpha    = grad_sq / denom
    weights  = (alpha * np.maximum(grads, 0)).sum(axis=(0, 1))
    cam      = (acts * weights).sum(axis=-1)
    cam      = np.maximum(cam, 0)
    return cam / (cam.max() + 1e-8)


def eigen_cam(feat_model, img_array):
    """Eigen-CAM (Muhammad & Yeasin, 2020) — gradient-free."""
    conv_out = feat_model(img_array, training=False)
    acts     = conv_out.numpy()[0]          # (H, W, C)
    H, W, C  = acts.shape
    F        = acts.reshape(-1, C).astype(np.float64)
    F       -= F.mean(axis=0)
    U, _, _  = np.linalg.svd(F, full_matrices=False)
    cam      = U[:, 0].reshape(H, W)
    cam     -= cam.min()
    return cam / (cam.max() + 1e-8)


# ── Pointing-game helpers ────────────────────────────────────────────────────

def get_image_names(data_dir):
    """Return filenames in the same order as load_preprocessed_inaoe()."""
    names = []
    for group in ['CT', 'DM']:
        group_dir = os.path.join(data_dir, group)
        for f in sorted(fn for fn in os.listdir(group_dir) if fn.endswith('.npy')):
            names.append(f"{group}/{f}")
    return names


def scale_bbox_to_224(bbox, orig_w, orig_h, target=224):
    """Scale [x1, y1, x2, y2] from original resolution to target×target space."""
    x1, y1, x2, y2 = bbox
    return [
        int(x1 * target / orig_w), int(y1 * target / orig_h),
        int(x2 * target / orig_w), int(y2 * target / orig_h),
    ]


def expand_bbox(x1, y1, x2, y2, tau, img_size=224):
    """Expand bbox by tau pixels on all sides, clamped to [0, img_size-1]."""
    return (
        max(0,           x1 - tau),
        max(0,           y1 - tau),
        min(img_size - 1, x2 + tau),
        min(img_size - 1, y2 + tau),
    )


def run_pointing_game(feat_model, clf_model, all_images, image_names,
                      test_indices, annotations, log, tau=POINTING_GAME_TAU):
    """Instance-level pointing game (95th-percentile + spatial offset variant).

    For each annotated test image:
      1. Scale bbox from original resolution → 224×224
      2. Expand bbox by τ pixels on all sides (neighbourhood tolerance)
      3. Upsample CAM from 7×7 → 224×224 (bilinear)
      4. Threshold CAM at its 95th percentile → high-activation region
      5. Hit = ANY pixel in that region falls inside the expanded bbox

    τ (tau): spatial offset applied to GT bbox to create a realistic
    neighbourhood — accounts for annotation imprecision and CAM quantisation.
    Default: POINTING_GAME_TAU = 15 pixels.
    Returns dict {method_name: hit_rate}.
    """
    ann_by_name = {a['filename']: a for a in annotations}
    test_names  = [image_names[i] for i in test_indices]

    hits = {'GradCAM': [], 'GradCAM++': [], 'EigenCAM': []}

    for local_idx, (global_idx, fname) in enumerate(zip(test_indices, test_names)):
        if fname not in ann_by_name:
            continue
        ann  = ann_by_name[fname]
        x1, y1, x2, y2 = scale_bbox_to_224(ann['bbox'], ann['orig_w'], ann['orig_h'])
        # Expand bbox by τ to create neighbourhood around GT
        ex1, ey1, ex2, ey2 = expand_bbox(x1, y1, x2, y2, tau)

        inp = all_images[global_idx][np.newaxis].astype(np.float32)

        cams = {
            'GradCAM':   grad_cam(feat_model, clf_model, inp),
            'GradCAM++': grad_cam_pp(feat_model, clf_model, inp),
            'EigenCAM':  eigen_cam(feat_model, inp),
        }
        for method, cam in cams.items():
            cam_224 = resize_cam(cam, 224, 224)
            # Region = pixels at or above 95th percentile intensity
            threshold = np.percentile(cam_224, 95)
            rows, cols = np.where(cam_224 >= threshold)
            hit = int(np.any(
                (cols >= ex1) & (cols <= ex2) & (rows >= ey1) & (rows <= ey2)
            ))
            hits[method].append(hit)

    log(f"\n{'='*80}")
    log(f"RQ2: POINTING GAME RESULTS  "
        f"({len(next(iter(hits.values())))} annotated images, τ={tau}px)")
    log(f"{'='*80}")
    scores = {}
    for method, h in hits.items():
        if h:
            s = float(np.mean(h))
            scores[method] = s
            log(f"  {method:<12}: {s:.4f}  ({sum(h)}/{len(h)} hits)")
        else:
            scores[method] = None
    return scores


# ── Visualisation ─────────────────────────────────────────────────────────────

def resize_cam(cam, h, w):
    t = tf.image.resize(cam[..., np.newaxis], (h, w), method='bilinear')
    return t.numpy().squeeze()


def overlay(img, cam, alpha=0.45):
    h, w    = img.shape[:2]
    cam_up  = resize_cam(cam, h, w)
    cam_up  = (cam_up - cam_up.min()) / (cam_up.max() - cam_up.min() + 1e-8)
    heatmap = plt.cm.jet(cam_up)[..., :3]
    return np.clip(alpha * heatmap + (1 - alpha) * img, 0, 1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log = make_logger('rq3')

    rq1_path = os.path.join(CONFIG['results_dir'], 'rq1_results.json')
    if not os.path.exists(rq1_path):
        log("❌ rq1_results.json not found. Run rq1_compare.py first.")
        return
    with open(rq1_path) as f:
        rq2_data = json.load(f)

    s2 = rq2_data.get('S2_best')
    if s2 is None:
        log("❌ S2_best not found in rq1_results.json.")
        return

    combo_id       = s2['combo_id']
    backbone       = s2['backbone']
    input_strategy = 'S2'
    data_path      = DATA_SOURCE[input_strategy]
    annotations_path = os.path.join(data_path, 'annotations.json')

    images, labels = load_preprocessed_inaoe(data_path, log=log)
    _, test_indices = create_fold_splits(
        images, labels,
        n_splits=CONFIG['n_folds'],
        test_split=CONFIG['test_split'],
        random_state=SEED,
    )

    ckpt = os.path.join(CONFIG['checkpoint_dir'], f"{combo_id}_final_retrain.keras")
    if not os.path.exists(ckpt):
        log(f"❌ {ckpt} not found.")
        return
    log(f"Loading proposed model: {ckpt}")
    model = tf.keras.models.load_model(ckpt, compile=False)

    log("Building CAM models ...")
    feat_model, clf_model = build_cam_models(model)
    log(f"  feat_model output : {feat_model.output_shape}")
    log(f"  classifier input  : {clf_model.input_shape}")

    X_test = images[test_indices]
    y_test = labels[test_indices]

    # Run inference on all test samples to pick confident correct predictions
    all_probs = clf_model(feat_model(X_test.astype(np.float32), training=False),
                          training=False).numpy()[:, 0]

    rng = np.random.default_rng(SEED)
    # DM: correct (pred=1) and confident (p >= 0.7), sorted by confidence desc
    dm_pool = np.where((y_test == 1) & (all_probs >= 0.7))[0]
    dm_pool = dm_pool[np.argsort(all_probs[dm_pool])[::-1]]
    dm_idx  = dm_pool[:N_SAMPLES_PER_CLASS]
    # CT: correct (pred=0) and confident (p <= 0.3), sorted by confidence asc
    ct_pool = np.where((y_test == 0) & (all_probs <= 0.3))[0]
    ct_pool = ct_pool[np.argsort(all_probs[ct_pool])]
    ct_idx  = ct_pool[:N_SAMPLES_PER_CLASS]
    log(f"Confident correct DM samples available: {len(dm_pool)} → using {len(dm_idx)}")
    log(f"Confident correct CT samples available: {len(ct_pool)} → using {len(ct_idx)}")
    sample_idx    = np.concatenate([dm_idx, ct_idx])
    sample_labels = y_test[sample_idx]
    sample_images = X_test[sample_idx]

    out_dir = os.path.join(CONFIG['results_dir'], 'rq3_xai')
    os.makedirs(out_dir, exist_ok=True)

    log(f"\n{'='*80}")
    log(f"RQ4: XAI VISUALISATIONS (S2_best) — {combo_id}")
    log(f"{'='*80}")
    log("NOTE: Pointing-game evaluation deferred (no ground-truth bboxes yet)\n")

    for i, (img, lbl) in enumerate(zip(sample_images, sample_labels)):
        inp        = img[np.newaxis].astype(np.float32)
        class_name = 'DM' if lbl == 1 else 'CT'
        proba      = float(clf_model(feat_model(inp, training=False),
                                     training=False)[0, 0])

        gc  = grad_cam(feat_model, clf_model, inp)
        gpp = grad_cam_pp(feat_model, clf_model, inp)
        ec  = eigen_cam(feat_model, inp)

        fig, axes = plt.subplots(1, 4, figsize=(18, 4.5))
        fig.suptitle(
            f"{combo_id} (proposed) — Sample {i+1} ({class_name}, p={proba:.3f})",
            fontsize=12,
        )
        panels = [('Original', img), ('Grad-CAM', overlay(img, gc)),
                  ('Grad-CAM++', overlay(img, gpp)), ('Eigen-CAM', overlay(img, ec))]
        for ax, (name, vis) in zip(axes, panels):
            ax.imshow(vis)
            ax.set_title(name, fontsize=10)
            ax.axis('off')

        plt.tight_layout()
        fname = os.path.join(out_dir, f"sample{i+1:02d}_{class_name}.png")
        plt.savefig(fname, dpi=150, bbox_inches='tight')
        plt.close()
        log(f"  Saved: {fname}")

    log(f"\n✓ {len(sample_images)} figures saved to {out_dir}/")

    # ── Pointing game (runs only when annotations.json is present) ────────────
    rq4_result = {'combo_id': combo_id, 'backbone': backbone,
                  'input_strategy': input_strategy, 'model': 'S2_best_final_retrain'}

    if os.path.exists(annotations_path):
        log(f"\nLoading annotations: {annotations_path}")
        with open(annotations_path) as f:
            annotations = json.load(f)
        image_names = get_image_names(data_path)
        scores = run_pointing_game(
            feat_model, clf_model, images, image_names, test_indices, annotations, log
        )
        rq4_result['pointing_game'] = {'tau': POINTING_GAME_TAU, 'scores': scores}
    else:
        log(f"\n⚠ Pointing game skipped — annotations.json not found")
        log(f"   Expected at: {annotations_path}")
        log(f"   See the TODO comment near the top of this file for the required format.")

    out = os.path.join(CONFIG['results_dir'], 'rq3_results.json')
    with open(out, 'w') as f:
        json.dump(rq4_result, f, indent=2)
    log(f"✓ Results → {out}")


if __name__ == '__main__':
    main()
