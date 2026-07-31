"""How sensitive are AI/CSI/SI to the binarisation threshold? Compare Otsu + fixed values."""
import numpy as np
from PIL import Image
from scipy import ndimage

PATH = "/home/ntphoto/Project/69b7a55ef1c9f8e33a9cbb5a/figures/P001_L_square_clahe.png"
img = np.array(Image.open(PATH).convert("L"))

def otsu(gray):
    hist, _ = np.histogram(gray.ravel(), bins=256, range=(0, 256))
    hist = hist.astype(float); tot = hist.sum()
    w0 = np.cumsum(hist); w1 = tot - w0
    mu = np.cumsum(hist * np.arange(256))
    mu_t = mu[-1]
    with np.errstate(invalid="ignore", divide="ignore"):
        between = (mu_t * w0 - mu) ** 2 / (w0 * w1)
    return int(np.nanargmax(between))

def indices(thr):
    mask = ndimage.binary_fill_holes(img > thr)
    lbl, n = ndimage.label(mask)
    sizes = ndimage.sum(np.ones_like(lbl), lbl, range(1, n + 1))
    foot = ndimage.binary_fill_holes(lbl == (np.argmax(sizes) + 1))
    rows = np.where(foot.any(axis=1))[0]; r0, r1 = rows.min(), rows.max()
    Lh = r1 - r0 + 1; b1, b2 = r0 + Lh // 3, r0 + 2 * Lh // 3
    def wid(a, b):
        ws = [np.where(foot[r])[0] for r in range(a, b)]
        return [c.max() - c.min() + 1 for c in ws if len(c)]
    maxC = max(wid(r0, b1)); minB = min(wid(b1, b2)); maxA = max(wid(b2, r1 + 1))
    aC = foot[r0:b1].sum(); aB = foot[b1:b2].sum(); aA = foot[b2:r1 + 1].sum()
    AI = aB / (aA + aB + aC)
    return int(foot.sum()), n, maxA, minB, maxC, AI, minB / maxA, minB / maxC

ot = otsu(img)
print(f"Otsu threshold = {ot}\n")
print(f"{'thr':>6} {'footpx':>7} {'ncomp':>5} {'maxA':>5} {'minB':>5} {'maxC':>5} "
      f"{'AI':>6} {'CSI':>6} {'SI':>6}")
for thr in sorted({ot, 5, 10, 20, 40, 60, 90, 120}):
    fp, n, mA, mB, mC, AI, CSI, SI = indices(thr)
    tag = "  <- Otsu" if thr == ot else ("  <- used" if thr == 20 else "")
    print(f"{thr:>6} {fp:>7} {n:>5} {mA:>5} {mB:>5} {mC:>5} "
          f"{AI:>6.3f} {CSI:>6.3f} {SI:>6.3f}{tag}")
