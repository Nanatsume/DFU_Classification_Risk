"""
Re-preprocess INAOE dataset correctly.

Pipeline per image:
  1. Load raw PNG (RGB)
  2. Convert to grayscale (luminance-weighted)
  3. Apply CLAHE (clip_limit=3.5, tile_grid=8x8)
  4. Convert to 3-channel grayscale
  5. Resize to 224x224
  6. Normalize by /255.0  (NOT per-image min-max)
  7. Save as float32 .npy

Produces two output directories:
  INAOE_S1/  — original orientation (left foot as-is)
  INAOE_S2/  — left foot flipped horizontally to match right foot orientation
"""

import os
import sys
import numpy as np
from PIL import Image
import cv2

RAW_DIR   = '/home/ntphoto/DFU/Model/INAOE Dataset'
OUT_S1    = '/home/ntphoto/DFU/INAOE_S1'
OUT_S2    = '/home/ntphoto/DFU/INAOE_S2'
IMG_SIZE  = (224, 224)
CLAHE_CLIP  = 3.5
CLAHE_TILE  = (8, 8)
GROUPS    = ['CT', 'DM']


def preprocess_image(png_path: str) -> np.ndarray:
    """Load raw PNG → grayscale → CLAHE → 3ch → resize → /255 → float32 [0,1]."""
    img = np.array(Image.open(png_path).convert('RGB'))

    # Grayscale (luminance)
    gray = (0.299 * img[..., 0] + 0.587 * img[..., 1] + 0.114 * img[..., 2]).astype(np.uint8)

    # CLAHE
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP, tileGridSize=CLAHE_TILE)
    gray = clahe.apply(gray)

    # 3-channel grayscale
    rgb = np.stack([gray, gray, gray], axis=-1)

    # Resize
    rgb = np.array(Image.fromarray(rgb).resize((IMG_SIZE[1], IMG_SIZE[0]), Image.BILINEAR))

    # Normalize: divide by 255 (global, not per-image min-max)
    return rgb.astype(np.float32) / 255.0


def main():
    for split in ['S1', 'S2']:
        out_root = OUT_S1 if split == 'S1' else OUT_S2
        for g in GROUPS:
            os.makedirs(os.path.join(out_root, g), exist_ok=True)

    total, ok, fail = 0, 0, 0

    for group in GROUPS:
        group_dir = os.path.join(RAW_DIR, group)
        if not os.path.isdir(group_dir):
            print(f'Missing group dir: {group_dir}')
            continue

        for patient in sorted(os.listdir(group_dir)):
            patient_dir = os.path.join(group_dir, patient)
            if not os.path.isdir(patient_dir):
                continue

            for foot in ['L', 'R']:
                fname = f'{patient}_{foot}.png'
                src   = os.path.join(patient_dir, fname)
                if not os.path.exists(src):
                    continue

                total += 1
                try:
                    img = preprocess_image(src)
                    base = f'{patient}_{foot}'   # e.g. DM001_M_L

                    # S1: save as-is
                    np.save(os.path.join(OUT_S1, group, base + '.npy'), img)

                    # S2: flip left foot horizontally; right foot unchanged
                    if foot == 'L':
                        img_s2 = img[:, ::-1, :]
                    else:
                        img_s2 = img
                    np.save(os.path.join(OUT_S2, group, base + '.npy'), img_s2)

                    ok += 1
                except Exception as e:
                    print(f'  ERROR {fname}: {e}')
                    fail += 1

        print(f'{group}: done')

    print(f'\nFinished — {ok}/{total} ok, {fail} failed')
    print(f'S1 → {OUT_S1}')
    print(f'S2 → {OUT_S2}')

    # Sanity check on one file
    sample = os.path.join(OUT_S1, 'CT',
                          sorted(os.listdir(os.path.join(OUT_S1, 'CT')))[0])
    arr = np.load(sample)
    print(f'\nSanity check [{os.path.basename(sample)}]:')
    print(f'  shape={arr.shape}  dtype={arr.dtype}  min={arr.min():.4f}  max={arr.max():.4f}')
    assert arr.dtype == np.float32
    assert arr.shape == (224, 224, 3)
    assert arr.min() >= 0.0 and arr.max() <= 1.0
    print('  ✓ assertions passed')


if __name__ == '__main__':
    main()
