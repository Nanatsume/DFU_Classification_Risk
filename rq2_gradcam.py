"""RQ2: Grad-CAM, Grad-CAM++, and Eigen-CAM visualisations on the proposed model.

Applies all three methods to sample images from the test set and saves
side-by-side heatmap overlays to results/rq2_gradcam/.
Saves summary to results/gradcam_results.json.

NOTE: Pointing-game evaluation against ground-truth bounding boxes is deferred
until annotations are available.

Run after rq3_final_evaluation.py.
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

# ── Pointing-game annotation path ────────────────────────────────────────────
# TODO (POINTING GAME — when annotations arrive):
#
# 1. Create this JSON file:
#      ANNOTATIONS_PATH = CONFIG['data_source'] + '/annotations.json'
#    Format:
#      [
#        {
#          "filename": "DM/image001.npy",   ← relative to CONFIG['data_source']
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
ANNOTATIONS_PATH = os.path.join(CONFIG['data_source'], 'annotations.json')


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
    classifier_model: spatial features  → scalar prediction

    Rebuilds the computation graph by calling loaded layers on fresh tensors,
    avoiding the tensor-ID mismatch that occurs when using base_layer.output
    from the original loaded model's graph.
    """
    base_layer = get_base_layer(model)

    # ── Feature extractor ──
    inp      = tf.keras.Input(shape=(224, 224, 3))
    conv_out = base_layer(inp, training=False)
    feat_model = tf.keras.Model(inputs=inp, outputs=conv_out)

    # Get spatial shape via a dummy forward pass
    dummy       = tf.zeros((1, 224, 224, 3))
    spatial_out = feat_model(dummy)
    spatial_shape = tuple(spatial_out.shape[1:])   # (H, W, C)

    # ── Classifier (remaining layers after base model) ──
    feat_inp = tf.keras.Input(shape=spatial_shape)
    x = feat_inp
    remaining = [l for l in model.layers
                 if not isinstance(l, tf.keras.layers.InputLayer)
                 and l.name != base_layer.name]
    for layer in remaining:
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
    log = make_logger('rq2')

    rq3_path = os.path.join(CONFIG['results_dir'], 'final_eval_results.json')
    if not os.path.exists(rq3_path):
        log("❌ final_eval_results.json not found. Run final_evaluation.py first.")
        return
    with open(rq3_path) as f:
        rq3 = json.load(f)
    best_model = rq3['best_model']

    images, labels = load_preprocessed_inaoe(CONFIG['data_source'], log=log)
    _, test_indices = create_fold_splits(
        images, labels,
        n_splits=CONFIG['n_folds'],
        test_split=CONFIG['test_split'],
        random_state=SEED,
    )

    ckpt = os.path.join(CONFIG['checkpoint_dir'], f"{best_model}_final_retrain.keras")
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

    rng    = np.random.default_rng(SEED)
    dm_idx = rng.choice(np.where(y_test == 1)[0],
                        size=min(N_SAMPLES_PER_CLASS, int(np.sum(y_test == 1))),
                        replace=False)
    ct_idx = rng.choice(np.where(y_test == 0)[0],
                        size=min(N_SAMPLES_PER_CLASS, int(np.sum(y_test == 0))),
                        replace=False)
    sample_idx    = np.concatenate([dm_idx, ct_idx])
    sample_labels = y_test[sample_idx]
    sample_images = X_test[sample_idx]

    out_dir = os.path.join(CONFIG['results_dir'], 'rq2_gradcam')
    os.makedirs(out_dir, exist_ok=True)

    log(f"\n{'='*80}")
    log(f"RQ2: CAM VISUALISATIONS — {best_model}  (final retrained model)")
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
            f"{best_model} (proposed) — Sample {i+1} ({class_name}, p={proba:.3f})",
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
    rq2_result = {'best_model': best_model, 'model': 'final_retrain'}

    if os.path.exists(ANNOTATIONS_PATH):
        log(f"\nLoading annotations: {ANNOTATIONS_PATH}")
        with open(ANNOTATIONS_PATH) as f:
            annotations = json.load(f)
        image_names = get_image_names(CONFIG['data_source'])
        scores = run_pointing_game(
            feat_model, clf_model, images, image_names, test_indices, annotations, log
        )
        rq2_result['pointing_game'] = {'tau': POINTING_GAME_TAU, 'scores': scores}
    else:
        log(f"\n⚠ Pointing game skipped — annotations.json not found")
        log(f"   Expected at: {ANNOTATIONS_PATH}")
        log(f"   See the TODO comment near the top of this file for the required format.")

    out = os.path.join(CONFIG['results_dir'], 'gradcam_results.json')
    with open(out, 'w') as f:
        json.dump(rq2_result, f, indent=2)
    log(f"✓ Results → {out}")


if __name__ == '__main__':
    main()
