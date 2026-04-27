"""
Foot Image Segmentation using GMM-HMRF in YDbDr Color Space
=============================================================
Algorithm:
  - Convert input image to YDbDr color space
  - Use Gaussian Mixture Model (GMM) with 3 clusters
  - Apply Hidden Markov Random Field (HMRF) with MAP criterion
  - Iteratively minimise Total Posterior Energy (Likelihood + Prior)
  - Extract foot contact region as final segmentation mask

Reference: GMM-HMRF segmentation with MAP estimation (3 clusters, GCE ≈ 0)
"""

import os
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from scipy.ndimage import uniform_filter


# ============================================================
# 1. Color Space Conversion: RGB → YDbDr
# ============================================================

def rgb_to_ydbdr(image_rgb: np.ndarray) -> np.ndarray:
    """
    Convert an RGB image (H, W, 3) in [0, 255] to YDbDr.

    Y  =  0.299 R + 0.587 G + 0.114 B          (Luminance)
    Db = -0.450 R - 0.883 G + 1.333 B          (Chrominance blue)
    Dr = -1.333 R + 1.116 G + 0.217 B          (Chrominance red)

    Returns float64 array (H, W, 3).
    """
    img = image_rgb.astype(np.float64)
    R, G, B = img[..., 0], img[..., 1], img[..., 2]

    Y  =  0.299 * R + 0.587 * G + 0.114 * B
    Db = -0.450 * R - 0.883 * G + 1.333 * B
    Dr = -1.333 * R + 1.116 * G + 0.217 * B

    return np.stack([Y, Db, Dr], axis=-1)


# ============================================================
# 2. GMM Parameter Estimation (Expectation-Maximisation)
# ============================================================

class GaussianMixtureModel:
    """Diagonal-covariance GMM fitted with EM for D-dimensional data."""

    def __init__(self, K: int = 3, max_iter: int = 50, tol: float = 1e-4,
                 random_state: int = 42):
        self.K = K
        self.max_iter = max_iter
        self.tol = tol
        self.rng = np.random.RandomState(random_state)
        # Parameters (set after fit)
        self.weights = None   # (K,)
        self.means = None     # (K, D)
        self.covs = None      # (K, D, D)

    def _init_params(self, X: np.ndarray):
        N, D = X.shape
        # Init: กำหนดค่าเริ่มต้นด้วย K-means style
        indices = self.rng.choice(N, self.K, replace=False)
        self.means = X[indices].copy()
        self.covs = np.array([np.eye(D) * np.var(X, axis=0) for _ in range(self.K)])
        self.weights = np.ones(self.K) / self.K

    @staticmethod
    def _log_gaussian(X: np.ndarray, mu: np.ndarray, cov: np.ndarray) -> np.ndarray:
        """Log pdf of multivariate Gaussian (N,) for (N, D) data."""
        D = X.shape[1]
        diff = X - mu  # (N, D)
        sign, log_det = np.linalg.slogdet(cov)
        inv_cov = np.linalg.inv(cov)
        mahal = np.sum(diff @ inv_cov * diff, axis=1)  # (N,)
        return -0.5 * (D * np.log(2 * np.pi) + log_det + mahal)

    def fit(self, X: np.ndarray):
        """Run EM on (N, D) data."""
        N, D = X.shape
        self._init_params(X)
        prev_ll = -np.inf

        for iteration in range(self.max_iter):
            # --- E-step: คำนวณความน่าจะเป็น (Likelihood) ---
            log_resp = np.zeros((N, self.K))
            for k in range(self.K):
                log_resp[:, k] = np.log(self.weights[k] + 1e-300) + \
                                 self._log_gaussian(X, self.means[k], self.covs[k])
            # Log-sum-exp trick
            log_resp_max = log_resp.max(axis=1, keepdims=True)
            log_norm = log_resp_max + np.log(
                np.sum(np.exp(log_resp - log_resp_max), axis=1, keepdims=True))
            log_resp -= log_norm
            resp = np.exp(log_resp)  # (N, K)

            # --- M-step: อัปเดตพารามิเตอร์ของโมเดล ---
            Nk = resp.sum(axis=0)   # (K,)
            self.weights = Nk / N
            for k in range(self.K):
                self.means[k] = (resp[:, k:k+1].T @ X) / Nk[k]
                diff = X - self.means[k]
                self.covs[k] = (diff.T * resp[:, k]) @ diff / Nk[k]
                # regularise
                self.covs[k] += np.eye(D) * 1e-6

            # Iteration: จนกว่าค่าความน่าจะเป็นจะคงที่ (Converges)
            ll = np.sum(log_norm)
            if abs(ll - prev_ll) < self.tol:
                print(f"  GMM converged at iteration {iteration + 1}")
                break
            prev_ll = ll

        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return (N, K) responsibility matrix."""
        N = X.shape[0]
        log_resp = np.zeros((N, self.K))
        for k in range(self.K):
            log_resp[:, k] = np.log(self.weights[k] + 1e-300) + \
                             self._log_gaussian(X, self.means[k], self.covs[k])
        log_resp_max = log_resp.max(axis=1, keepdims=True)
        log_norm = log_resp_max + np.log(
            np.sum(np.exp(log_resp - log_resp_max), axis=1, keepdims=True))
        log_resp -= log_norm
        return np.exp(log_resp)


# ============================================================
# 3. HMRF-MAP Segmentation
# ============================================================

def _neighbourhood_label_counts(labels: np.ndarray, K: int) -> np.ndarray:
    """
    For each pixel, count how many of its 4-connected neighbours
    share each label.  Returns (H, W, K).
    """
    H, W = labels.shape
    counts = np.zeros((H, W, K), dtype=np.float64)
    for k in range(K):
        binary = (labels == k).astype(np.float64)
        # Shift in 4 directions and sum
        count_k = np.zeros_like(binary)
        count_k[1:, :]  += binary[:-1, :]   # top
        count_k[:-1, :] += binary[1:, :]    # bottom
        count_k[:, 1:]  += binary[:, :-1]   # left
        count_k[:, :-1] += binary[:, 1:]    # right
        counts[..., k] = count_k
    return counts


def hmrf_em_segmentation(image_ydbdr: np.ndarray, K: int = 3,
                         beta: float = 1.5, max_iter: int = 30,
                         tol: float = 1e-3) -> np.ndarray:
    """
    HMRF-EM segmentation with GMM (Background, Low-pressure, High-pressure).

    Parameters
    ----------
    image_ydbdr : (H, W, 3) float64 – image in YDbDr colour space
    K           : number of clusters (default 3)
    beta        : MRF smoothness parameter (Potts model weight)
    max_iter    : maximum ICM iterations
    tol         : convergence threshold (fraction of pixels that changed)

    Returns
    -------
    labels : (H, W) int array with values in {0, 1, ..., K-1}
    """
    H, W, D = image_ydbdr.shape
    X = image_ydbdr.reshape(-1, D)  # (N, D)
    N = X.shape[0]

    # ----- Step A: Initial GMM fit to get likelihood parameters -----
    print("[1/3] Fitting GMM (K={}) on YDbDr features ...".format(K))
    gmm = GaussianMixtureModel(K=K, max_iter=80)
    gmm.fit(X)

    # Initial labels from GMM (ignoring spatial prior)
    resp = gmm.predict_proba(X)  # (N, K)
    labels = resp.argmax(axis=1).reshape(H, W)

    # ----- Step B: Iterative HMRF MAP Labeling (Energy minimization) -----
    print("[2/3] Running HMRF-EM MAP Labeling (beta={}) ...".format(beta))

    # Pre-compute per-pixel likelihood energies  U_likelihood(x_i | k)
    # = -log p(x_i | mu_k, Sigma_k)
    likelihood_energy = np.zeros((N, K))
    for k in range(K):
        likelihood_energy[:, k] = -GaussianMixtureModel._log_gaussian(
            X, gmm.means[k], gmm.covs[k])
    likelihood_energy = likelihood_energy.reshape(H, W, K)

    for it in range(max_iter):
        # Prior energy from MRF (Potts model):
        #   U_prior(k | neighbours) = beta * (# neighbours with label ≠ k)
        nbr_counts = _neighbourhood_label_counts(labels, K)  # (H, W, K)
        # Max possible neighbours = 4; clique penalty = beta * (4 - same_count)
        prior_energy = beta * (4.0 - nbr_counts)  # (H, W, K)

        # At image borders some pixels have < 4 neighbours, but the small
        # bias is harmless.

        # Total posterior energy = Likelihood + Prior
        total_energy = likelihood_energy + prior_energy  # (H, W, K)

        # MAP Labeling: กำหนด Label โดยพิจารณาเพื่อลดพลังงานรวม (Energy minimization)
        new_labels = total_energy.argmin(axis=2)  # (H, W)

        # Convergence check
        changed = np.mean(new_labels != labels)
        labels = new_labels
        if changed < tol:
            print(f"  ICM converged at iteration {it + 1} "
                  f"(changed = {changed:.6f})")
            break

    # ----- Step C: Re-estimate GMM conditioned on final labels -----
    print("[3/3] Re-estimating GMM on final labels ...")
    for k in range(K):
        mask_k = (labels.ravel() == k)
        if mask_k.sum() < D + 1:
            continue
        gmm.means[k] = X[mask_k].mean(axis=0)
        gmm.covs[k] = np.cov(X[mask_k].T) + np.eye(D) * 1e-6

    return labels


# ============================================================
# 4. Post-processing: Identify Foot Contact Region
# ============================================================

def identify_foot_label(labels: np.ndarray, image_ydbdr: np.ndarray) -> int:
    """
    Among K labels, choose the one that corresponds to the bright
    foot-contact region on the glass.

    Strategy:
      - The foot contact area has HIGH luminance (Y) from the glass reflection
      - It also has significant chrominance (|Db|, |Dr|) from skin tone,
        unlike the plain bright background which has near-zero chrominance.
      - We score each cluster as: mean_Y * chrominance_magnitude
        to prefer clusters that are bright AND have colour (= skin).
    """
    K = labels.max() + 1
    scores = np.zeros(K)
    for k in range(K):
        mask_k = (labels == k)
        if mask_k.sum() == 0:
            continue
        mean_y  = image_ydbdr[mask_k, 0].mean()    # Luminance
        mean_db = np.abs(image_ydbdr[mask_k, 1]).mean()  # |Db|
        mean_dr = np.abs(image_ydbdr[mask_k, 2]).mean()  # |Dr|
        chrom_mag = np.sqrt(mean_db**2 + mean_dr**2)

        # Score: bright + colourful → foot skin on glass
        scores[k] = mean_y * (1.0 + chrom_mag)

    foot_label = int(np.argmax(scores))
    scores_dict = {i: round(float(s), 1) for i, s in enumerate(scores)}
    print(f"  Cluster scores: {scores_dict}")
    return foot_label


def create_foot_mask(labels: np.ndarray, foot_label: int) -> np.ndarray:
    """Binary mask: 1 = foot, 0 = background."""
    return np.where(labels == foot_label, 1, 0).astype(np.uint8)


def get_pure_sole_image(image_rgb: np.ndarray, foot_mask: np.ndarray,
               background: str = "black") -> np.ndarray:
    """
    Post-processing: สร้างภาพฝ่าเท้าที่สมบูรณ์ (Pure Sole Image)
    นำ Mask มาคูณกับภาพต้นฉบับ (Product of segmented mask with original image)
    เพื่อกำจัดสัญญาณรบกวน (Noise) และขอบภาพหยัก (Patchy edges)


    Parameters
    ----------
    image_rgb  : (H, W, 3) uint8 original image
    foot_mask  : (H, W) uint8 binary mask (0 or 1)
    background : "black" (default) or "white" — colour of non-foot pixels

    Returns
    -------
    masked_image : (H, W, 3) uint8
    """
    # Expand mask to 3 channels: (H, W) → (H, W, 1) so it broadcasts
    mask_3ch = foot_mask[:, :, np.newaxis]  # (H, W, 1)

    if background == "white":
        # foot pixels keep original, background → 255
        bg = np.full_like(image_rgb, 255)
        masked = image_rgb * mask_3ch + bg * (1 - mask_3ch)
    else:
        # foot pixels keep original, background → 0 (black)
        masked = image_rgb * mask_3ch

    return masked.astype(np.uint8)


# ============================================================
# 5. Visualisation Helpers
# ============================================================

def visualise_segmentation(image_rgb: np.ndarray, labels: np.ndarray,
                           foot_mask: np.ndarray, save_path: str | None = None):
    """Show original, label map, and foot mask side by side."""
    K = labels.max() + 1

    fig, axes = plt.subplots(1, 4, figsize=(20, 5))

    # (a) Original
    axes[0].imshow(image_rgb)
    axes[0].set_title("Original (RGB)")
    axes[0].axis("off")

    # (b) Label map
    try:
        cmap = plt.colormaps["Set1"].resampled(K)
    except AttributeError:
        cmap = plt.get_cmap("Set1", K)
        
    axes[1].imshow(labels, cmap=cmap, interpolation="nearest")
    axes[1].set_title(f"GMM-HMRF Labels (K={K})")
    axes[1].axis("off")

    # (c) Foot mask
    axes[2].imshow(foot_mask, cmap="gray", interpolation="nearest")
    axes[2].set_title("Foot Contact Mask")
    axes[2].axis("off")

    # (d) Overlay
    overlay = image_rgb.copy()
    overlay[foot_mask == 1] = (overlay[foot_mask == 1] * 0.5 +
                                np.array([0, 255, 0]) * 0.5).astype(np.uint8)
    axes[3].imshow(overlay)
    axes[3].set_title("Overlay (Green = Foot)")
    axes[3].axis("off")

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved visualisation → {save_path}")
    plt.show()


# ============================================================
# 6. Main Pipeline
# ============================================================

def segment_foot_image(image_path: str, K: int = 3, beta: float = 1.5,
                       save_dir: str | None = None) -> dict:
    """
    Full pipeline: load → YDbDr → GMM-HMRF-MAP → foot mask.

    Parameters
    ----------
    image_path : path to input foot image
    K          : number of GMM clusters (default 3)
    beta       : MRF smoothness weight
    save_dir   : directory to save outputs (optional)

    Returns
    -------
    dict with keys: 'labels', 'foot_mask', 'foot_label', 'image_rgb', 'image_ydbdr'
    """
    print("=" * 60)
    print(f"  Foot Segmentation – GMM-HMRF-MAP  (K={K}, β={beta})")
    print("=" * 60)

    # Load image
    img_pil = Image.open(image_path).convert("RGB")
    image_rgb = np.array(img_pil)
    print(f"Image loaded: {image_path}  ({image_rgb.shape[1]}×{image_rgb.shape[0]})")

    # Convert to YDbDr
    image_ydbdr = rgb_to_ydbdr(image_rgb)
    print(f"Converted to YDbDr colour space")
    print(f"  Y  range: [{image_ydbdr[...,0].min():.1f}, {image_ydbdr[...,0].max():.1f}]")
    print(f"  Db range: [{image_ydbdr[...,1].min():.1f}, {image_ydbdr[...,1].max():.1f}]")
    print(f"  Dr range: [{image_ydbdr[...,2].min():.1f}, {image_ydbdr[...,2].max():.1f}]")

    # Segment with HMRF-EM
    labels = hmrf_em_segmentation(image_ydbdr, K=K, beta=beta)

    # Identify foot
    foot_label = identify_foot_label(labels, image_ydbdr)
    foot_mask = create_foot_mask(labels, foot_label)
    print(f"Foot label = {foot_label}  "
          f"(covers {foot_mask.sum()} px, "
          f"{100 * foot_mask.mean():.1f}% of image)")

    # Post-processing: Product of segmented mask with original image (Pure Sole Image)
    pure_sole_black_bg = get_pure_sole_image(image_rgb, foot_mask, background="black")
    pure_sole_white_bg = get_pure_sole_image(image_rgb, foot_mask, background="white")

    # Save outputs
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(image_path))[0]

        mask_path = os.path.join(save_dir, f"{base}_foot_mask.png")
        Image.fromarray(foot_mask * 255).save(mask_path)
        print(f"Saved mask          → {mask_path}")

        # Masked foot on black background (Pure Sole Image)
        black_path = os.path.join(save_dir, f"{base}_foot_black_bg.png")
        Image.fromarray(pure_sole_black_bg).save(black_path)
        print(f"Saved foot (black)  → {black_path}")

        # Masked foot on white background (Pure Sole Image)
        white_path = os.path.join(save_dir, f"{base}_foot_white_bg.png")
        Image.fromarray(pure_sole_white_bg).save(white_path)
        print(f"Saved foot (white)  → {white_path}")

        labels_path = os.path.join(save_dir, f"{base}_labels.png")
        Image.fromarray((labels * (255 // max(K - 1, 1))).astype(np.uint8)).save(labels_path)
        print(f"Saved label map     → {labels_path}")

        vis_path = os.path.join(save_dir, f"{base}_visualisation.png")
        visualise_segmentation(image_rgb, labels, foot_mask, save_path=vis_path)

    print("=" * 60)
    print("  Done!")
    print("=" * 60)

    return {
        "labels": labels,
        "foot_mask": foot_mask,
        "foot_label": foot_label,
        "image_rgb": image_rgb,
        "image_ydbdr": image_ydbdr,
        "foot_black_bg": pure_sole_black_bg,
        "foot_white_bg": pure_sole_white_bg,
    }


# ============================================================
# 7. Entry Point
# ============================================================

if __name__ == "__main__":
    # --- Configuration ---
    # โฟลเดอร์เก็บภาพต้นฉบับ
    IMAGE_DIR = r"Z:\Model\img"
    # โฟลเดอร์เก็บผลลัพธ์
    OUTPUT_DIR = os.path.join(IMAGE_DIR, "output")

    # Find all image files in the directory
    supported_ext = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
    image_files = [
        f for f in os.listdir(IMAGE_DIR)
        if os.path.splitext(f)[1].lower() in supported_ext
    ]

    if not image_files:
        print("No image files found in", IMAGE_DIR)
    else:
        print(f"Found {len(image_files)} image(s) in {IMAGE_DIR}\n")
        for fname in image_files:
            fpath = os.path.join(IMAGE_DIR, fname)
            result = segment_foot_image(fpath, K=3, beta=1.5,
                                        save_dir=OUTPUT_DIR)
            print()
