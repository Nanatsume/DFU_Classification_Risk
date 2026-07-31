"""Geometric footprint features (Arch Index, Chippaux-Smirak, Staheli) with toe removal.

Prototype for the baseline feature extraction. Orientation assumed: heel at TOP,
toes at BOTTOM (as in the preprocessed CLAHE square footprints).

Usage:
    python geom_indices.py [image_path] [threshold]
Outputs a multi-panel visualization + prints the 11 geometric features.
"""
import sys, os, json
import numpy as np
from PIL import Image
from scipy import ndimage
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")
os.makedirs(OUT, exist_ok=True)

def analyse(path, thr=0):  # thr=0 -> foreground is any non-black pixel (matches the texture explorer's cutoff)
    name = os.path.splitext(os.path.basename(path))[0]
    side = "L" if "_L" in name else ("R" if "_R" in name else "?")
    img = np.array(Image.open(path).convert("L"))
    H, W = img.shape

    # 1. binarise + fill holes
    mask = ndimage.binary_fill_holes(img > thr)

    # 2. connected components -> keep largest (foot), rest = toes/noise
    lbl, n = ndimage.label(mask)
    sizes = ndimage.sum(np.ones_like(lbl), lbl, range(1, n + 1))
    order = np.argsort(sizes)[::-1]
    foot = ndimage.binary_fill_holes(lbl == order[0] + 1)
    removed_mask = mask & ~foot

    # 3. trisect along vertical extent: top=heel(C), mid=midfoot(B), bottom=forefoot(A)
    rows = np.where(foot.any(axis=1))[0]
    r0, r1 = rows.min(), rows.max()
    Lh = r1 - r0 + 1
    b1, b2 = r0 + Lh // 3, r0 + 2 * Lh // 3
    bands = {"C": (r0, b1), "B": (b1, b2), "A": (b2, r1 + 1)}

    def widths(a, b):
        out = []
        for rr in range(a, b):
            cols = np.where(foot[rr])[0]
            out.append((rr, cols.max() - cols.min() + 1, cols.min(), cols.max()) if len(cols)
                       else (rr, 0, 0, 0))
        return out

    wC, wB, wA = widths(*bands["C"]), widths(*bands["B"]), widths(*bands["A"])
    rowC = max(wC, key=lambda t: t[1]); maxC = rowC[1]
    rowB = min((t for t in wB if t[1] > 0), key=lambda t: t[1]); minB = rowB[1]
    rowA = max(wA, key=lambda t: t[1]); maxA = rowA[1]
    area_C = int(foot[bands["C"][0]:bands["C"][1]].sum())
    area_B = int(foot[bands["B"][0]:bands["B"][1]].sum())
    area_A = int(foot[bands["A"][0]:bands["A"][1]].sum())
    foot_area = int(foot.sum())

    AI = area_B / (area_A + area_B + area_C)
    CSI = minB / maxA
    SI = minB / maxC
    ai_cls = "high/cavus" if AI < 0.21 else ("flat/planus" if AI > 0.28 else "normal")

    feats = dict(maxA=int(maxA), maxC=int(maxC), minB=int(minB),
                 CSI=round(CSI, 4), SI=round(SI, 4),
                 area_A=area_A, area_B=area_B, area_C=area_C, AI=round(AI, 4),
                 foot_area=foot_area, foot_side=side)

    # ---- visualization ----
    reg = np.zeros((H, W, 3), np.uint8)
    reg[foot] = (70, 70, 70)
    for key, col in [("C", (30, 144, 255)), ("B", (0, 200, 0)), ("A", (255, 80, 80))]:
        a, b = bands[key]; seg = np.zeros_like(foot); seg[a:b] = foot[a:b]; reg[seg] = col
    toeimg = np.zeros((H, W, 3), np.uint8)
    toeimg[foot] = (0, 200, 0); toeimg[removed_mask] = (255, 60, 60)

    fig, ax = plt.subplots(1, 4, figsize=(16, 5))
    ax[0].imshow(img, cmap="gray"); ax[0].set_title(f"1. CLAHE input\n{name}")
    ax[1].imshow(mask, cmap="gray"); ax[1].set_title(f"2. Binary (thr={thr})\n{n} components")
    ax[2].imshow(toeimg); ax[2].set_title(f"3. Toe removal\nfoot={foot_area}px (green), "
                                          f"removed={int(removed_mask.sum())}px (red)")
    ax[3].imshow(reg)
    for row, lab, c in [(rowA, f"maxA={maxA}", "r"), (rowB, f"minB={minB}", "g"),
                        (rowC, f"maxC={maxC}", "b")]:
        rr, w, cmin, cmax = row
        ax[3].plot([cmin, cmax], [rr, rr], color="yellow", lw=2)
        ax[3].text(cmax + 5, rr, lab, color="yellow", fontsize=9, va="center")
    for bb in (b1, b2):
        ax[3].axhline(bb, color="white", ls="--", lw=0.8)
    ax[3].set_title(f"4. Regions + widths\nAI={AI:.3f} ({ai_cls})  CSI={CSI:.3f}  SI={SI:.3f}")
    for a in ax:
        a.axis("off")
    plt.tight_layout()
    figpath = os.path.join(OUT, f"{name}_geom.png")
    plt.savefig(figpath, dpi=110, bbox_inches="tight"); plt.close()

    with open(os.path.join(OUT, f"{name}_features.json"), "w") as f:
        json.dump(feats, f, indent=2)

    print(f"\n=== {name}  (side {side}) ===")
    for k, v in feats.items():
        print(f"  {k:10s} = {v}")
    print(f"  AI class   = {ai_cls}")
    print(f"  -> figure : {figpath}")
    return feats

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else \
        "/home/ntphoto/Project/69b7a55ef1c9f8e33a9cbb5a/figures/P001_L_square_clahe.png"
    thr = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    analyse(path, thr)
