"""Foot image preprocessing pipeline (extracted from Image_Preprocessing_Pipeline.ipynb).

Single source of truth for the podoscope preprocessing used by the capture app and by training.
Pure Python (numpy / scipy / opencv / PIL), no model weights, no GPU.

Entry point:
    preprocess_foot_image(image_path) -> {'left_foot': (224,224,3) float32 [0,1], 'right_foot': ...}
"""


# ======================================================================
# --- notebook cell 3 ---
# ======================================================================

# Import Required Libraries
import os
import glob
import numpy as np
from PIL import Image
from scipy.ndimage import uniform_filter, label, find_objects, binary_dilation
import cv2
import warnings
warnings.filterwarnings('ignore')

print("✓ All libraries imported successfully")

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
        self.weights = None   # (K,)
        self.means = None     # (K, D)
        self.covs = None      # (K, D, D)

    def _init_params(self, X: np.ndarray):
        N, D = X.shape
        indices = self.rng.choice(N, self.K, replace=False)
        self.means = X[indices].copy()
        self.covs = np.array([np.eye(D) * np.var(X, axis=0) for _ in range(self.K)])
        self.weights = np.ones(self.K) / self.K

    @staticmethod
    def _log_gaussian(X: np.ndarray, mu: np.ndarray, cov: np.ndarray) -> np.ndarray:
        """Log pdf of multivariate Gaussian (N,) for (N, D) data."""
        D = X.shape[1]
        diff = X - mu
        sign, log_det = np.linalg.slogdet(cov)
        inv_cov = np.linalg.inv(cov)
        mahal = np.sum(diff @ inv_cov * diff, axis=1)
        return -0.5 * (D * np.log(2 * np.pi) + log_det + mahal)

    def fit(self, X: np.ndarray):
        """Run EM on (N, D) data."""
        N, D = X.shape
        self._init_params(X)
        prev_ll = -np.inf

        for iteration in range(self.max_iter):
            # E-step
            log_resp = np.zeros((N, self.K))
            for k in range(self.K):
                log_resp[:, k] = np.log(self.weights[k] + 1e-300) + \
                                 self._log_gaussian(X, self.means[k], self.covs[k])
            # Log-sum-exp trick
            log_resp_max = log_resp.max(axis=1, keepdims=True)
            log_norm = log_resp_max + np.log(
                np.sum(np.exp(log_resp - log_resp_max), axis=1, keepdims=True))
            log_resp -= log_norm
            resp = np.exp(log_resp)

            # M-step
            Nk = resp.sum(axis=0)
            self.weights = Nk / N
            for k in range(self.K):
                self.means[k] = (resp[:, k:k+1].T @ X) / Nk[k]
                diff = X - self.means[k]
                self.covs[k] = (diff.T * resp[:, k]) @ diff / Nk[k]
                self.covs[k] += np.eye(D) * 1e-6

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
    """For each pixel, count how many of its 4-connected neighbours share each label."""
    H, W = labels.shape
    counts = np.zeros((H, W, K), dtype=np.float64)
    for k in range(K):
        binary = (labels == k).astype(np.float64)
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
    """HMRF-EM segmentation with GMM."""
    H, W, D = image_ydbdr.shape
    X = image_ydbdr.reshape(-1, D)
    N = X.shape[0]

    print("[1/3] Fitting GMM (K={}) on YDbDr features ...".format(K))
    gmm = GaussianMixtureModel(K=K, max_iter=80)
    gmm.fit(X)

    resp = gmm.predict_proba(X)
    labels = resp.argmax(axis=1).reshape(H, W)

    print("[2/3] Running HMRF-EM MAP Labeling (beta={}) ...".format(beta))

    likelihood_energy = np.zeros((N, K))
    for k in range(K):
        likelihood_energy[:, k] = -GaussianMixtureModel._log_gaussian(
            X, gmm.means[k], gmm.covs[k])
    likelihood_energy = likelihood_energy.reshape(H, W, K)

    for it in range(max_iter):
        nbr_counts = _neighbourhood_label_counts(labels, K)
        prior_energy = beta * (4.0 - nbr_counts)

        total_energy = likelihood_energy + prior_energy

        new_labels = total_energy.argmin(axis=2)

        changed = np.mean(new_labels != labels)
        labels = new_labels
        if changed < tol:
            print(f"  ICM converged at iteration {it + 1} (changed = {changed:.6f})")
            break

    print("[3/3] Re-estimating GMM on final labels ...")
    for k in range(K):
        mask_k = (labels.ravel() == k)
        if mask_k.sum() < D + 1:
            continue
        gmm.means[k] = X[mask_k].mean(axis=0)
        gmm.covs[k] = np.cov(X[mask_k].T) + np.eye(D) * 1e-6

    return labels


# ============================================================
# 4. Identify Foot Label & Create Mask
# ============================================================

def identify_foot_label(labels: np.ndarray, image_ydbdr: np.ndarray) -> int:
    """Identify which cluster corresponds to the foot contact region."""
    K = labels.max() + 1
    scores = np.zeros(K)
    for k in range(K):
        mask_k = (labels == k)
        if mask_k.sum() == 0:
            continue
        mean_y  = image_ydbdr[mask_k, 0].mean()
        mean_db = np.abs(image_ydbdr[mask_k, 1]).mean()
        mean_dr = np.abs(image_ydbdr[mask_k, 2]).mean()
        chrom_mag = np.sqrt(mean_db**2 + mean_dr**2)
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
    """Apply mask to image."""
    mask_3ch = foot_mask[:, :, np.newaxis]
    if background == "white":
        bg = np.full_like(image_rgb, 255)
        masked = image_rgb * mask_3ch + bg * (1 - mask_3ch)
    else:
        masked = image_rgb * mask_3ch
    return masked.astype(np.uint8)


# ======================================================================
# --- notebook cell 5 ---
# ======================================================================

# ============================================================
# SECTION 2: Morphological Operations with Dilation
# ============================================================

def apply_morphological_dilation(input_data, output_dir: str | None = None):
    """
    Apply morphological dilation to dilate foot region.
    
    Parameters
    ----------
    input_data : str or np.ndarray
        Path to segmented foot image OR segmented image array (H, W, 3)
    output_dir : str, optional
        Directory to save intermediate outputs (currently unused)
    
    Returns
    -------
    merged_mask : (H, W) binary array with dilated foot region
    image_array : (H, W, 3) original image array
    """
    print("=" * 60)
    print(f"  Morphological Dilation")
    print("=" * 60)

    # Load image if string, use directly if array
    if isinstance(input_data, str):
        img_pil = Image.open(input_data).convert("RGB")
        img_array = np.array(img_pil)
    else:
        img_array = input_data.copy()
    
    # Create binary mask from image
    intensity = img_array.sum(axis=2)
    binary_mask = (intensity > 0).astype(np.uint8)
    print(f"Binary mask created from image")
    
    # Dynamic kernel: 12% of image height for vertical, 5px for horizontal
    img_h, img_w = img_array.shape[:2]
    dilate_h = max(10, int(img_h * 0.12))
    struct_dilate = np.ones((dilate_h, 5), dtype=bool)
    print(f"Dilation kernel size: ({dilate_h}, 5)")
    
    # Apply binary dilation
    merged_mask = binary_dilation(binary_mask, structure=struct_dilate)
    print(f"Dilation applied - bridges gaps between disconnected regions (e.g., toes)")
    print("=" * 60)
    
    return merged_mask, img_array


# ======================================================================
# --- notebook cell 7 ---
# ======================================================================

# ============================================================
# SECTION 3: Left-Right Separation & Square Crop
# ============================================================

def pad_to_square(img_array: np.ndarray) -> np.ndarray:
    """Pad an image with black pixels to make it a perfect square."""
    h, w = img_array.shape[:2]
    size = max(h, w)
    
    pad_h_top = (size - h) // 2
    pad_h_bottom = size - h - pad_h_top
    pad_w_left = (size - w) // 2
    pad_w_right = size - w - pad_w_left
    
    padded = np.pad(img_array, ((pad_h_top, pad_h_bottom), 
                                (pad_w_left, pad_w_right), 
                                (0, 0)), 
                    mode='constant', constant_values=0)
    return padded


def separate_and_crop_feet(merged_mask: np.ndarray, img_array: np.ndarray, output_dir: str | None = None):
    """
    Separate left and right footprints and create square images.
    
    Parameters
    ----------
    merged_mask : (H, W) binary array with dilated foot region
    img_array : (H, W, 3) original image array
    output_dir : str, optional
        Directory to save intermediate visualizations
    
    Returns
    -------
    foot_left_img : (H, H, 3) left foot square image
    foot_right_img : (H, H, 3) right foot square image
    """
    print("=" * 60)
    print(f"  Left-Right Separation & Square Crop")
    print("=" * 60)
    
    # Connected Component Labeling (8-connected)
    structure = np.ones((3, 3), dtype=np.int32)
    labeled_mask, num_features = label(merged_mask, structure=structure)
    
    if num_features < 2:
        print("Error: Could not find at least 2 separate feet in the image.")
        return None, None
    
    print(f"Found {num_features} connected components")
    
    # Find the 2 Largest Components
    component_sizes = np.bincount(labeled_mask.ravel())
    component_sizes[0] = 0  # ignore background
    largest_labels = np.argsort(component_sizes)[-2:]
    print(f"2 largest components identified: labels {largest_labels}")
    
    # Extract Bounding Boxes
    slices = find_objects(labeled_mask)
    
    extracted_feet = []
    
    for lbl in largest_labels:
        bbox = slices[lbl - 1]
        y_slice, x_slice = bbox
        center_x = (x_slice.start + x_slice.stop) / 2.0
        
        # Tight crop
        cropped_img = img_array[y_slice, x_slice]
        
        # Pad to Square
        square_img = pad_to_square(cropped_img)
        
        extracted_feet.append({
            'center_x': center_x,
            'bbox': bbox,
            'square_img': square_img
        })
    
    # Sort by X coordinate (Leftmost = Left foot)
    extracted_feet.sort(key=lambda item: item['center_x'])
    foot_left_img  = extracted_feet[0]['square_img']
    foot_right_img = extracted_feet[1]['square_img']
    
    print(f"Left Foot:  {foot_left_img.shape[0]}x{foot_left_img.shape[1]}")
    print(f"Right Foot: {foot_right_img.shape[0]}x{foot_right_img.shape[1]}")
    print("=" * 60)
    
    return foot_left_img, foot_right_img


# ======================================================================
# --- notebook cell 9 ---
# ======================================================================

# ============================================================
# SECTION 4: Grayscale Conversion & CLAHE Enhancement
# ============================================================

def convert_to_grayscale(img_array: np.ndarray) -> np.ndarray:
    """
    Convert RGB image to grayscale using standard luminance formula.

    Formula: Gray = 0.299 * R + 0.587 * G + 0.114 * B
    """
    if len(img_array.shape) == 3 and img_array.shape[2] == 3:
        gray = 0.299 * img_array[..., 0] + 0.587 * img_array[..., 1] + 0.114 * img_array[..., 2]
        return gray.astype(np.uint8)
    else:
        return img_array


def apply_clahe(image_gray: np.ndarray, clip_limit: float = 3.5, tile_grid_size: tuple = (8, 8)) -> np.ndarray:
    """
    Apply Contrast Limited Adaptive Histogram Equalization (CLAHE).

    Parameters
    ----------
    image_gray : (H, W) uint8
    clip_limit : float
        Default 3.5, selected via CLAHE parameter tuning (Section 11).
    tile_grid_size : tuple
        Default (8, 8).

    Returns
    -------
    clahe_image : (H, W) uint8
    """
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    return clahe.apply(image_gray)


# ======================================================================
# --- notebook cell 11 ---
# ======================================================================

# ============================================================
# SECTION 5.1: Three-Channel RGB Conversion
# ============================================================

def convert_to_3channel_rgb(image_gray: np.ndarray) -> np.ndarray:
    """
    Convert grayscale image to 3-channel RGB by copying values to all channels.
    
    Parameters
    ----------
    image_gray : (H, W) uint8 or float grayscale image
    
    Returns
    -------
    image_rgb : (H, W, 3) 3-channel image
    """
    if len(image_gray.shape) == 2:
        # Stack grayscale 3 times to create RGB
        image_rgb = np.stack([image_gray, image_gray, image_gray], axis=-1)
        return image_rgb
    else:
        return image_gray


# ======================================================================
# --- notebook cell 13 ---
# ======================================================================

# ============================================================
# SECTION 5.2: Image Resizing
# ============================================================

def resize_image(image: np.ndarray, target_size: tuple = (224, 224), interpolation: str = 'bilinear') -> np.ndarray:
    """
    Resize image to target size using bilinear interpolation.
    
    Parameters
    ----------
    image : (H, W) or (H, W, C) array
    target_size : (height, width) tuple
    interpolation : 'bilinear' (default) or 'nearest'
    
    Returns
    -------
    resized_image : Array resized to target_size
    """
    pil_image = Image.fromarray(image)
    
    if interpolation == 'bilinear':
        interp = Image.BILINEAR
    else:
        interp = Image.NEAREST
    
    resized_pil = pil_image.resize((target_size[1], target_size[0]), interp)
    resized_array = np.array(resized_pil)
    
    return resized_array


# ======================================================================
# --- notebook cell 15 ---
# ======================================================================

# ============================================================
# SECTION 5.3: Pixel Intensity Scaling (÷255)
# ============================================================

def scale_pixels(image: np.ndarray) -> np.ndarray:
    """
    Scale pixel values to [0, 1] by dividing by 255.

    Uses a fixed global divisor (not per-image min-max), preserving
    relative pressure intensity across images.

    Parameters
    ----------
    image : np.ndarray
        Input image (uint8 or float in [0, 255])

    Returns
    -------
    scaled_image : np.ndarray float32
        Pixel values in [0, 1]
    """
    return image.astype(np.float32) / 255.0


# ======================================================================
# --- notebook cell 17 ---
# ======================================================================

# ============================================================
# SECTION 7: Complete Pipeline Integration
# ============================================================

def preprocess_foot_image(image_path: str, output_dir: str = None, target_size: tuple = (224, 224), save_final: bool = False):
    """
    Complete preprocessing pipeline for foot images.

    Input: Raw footprint image (RGB, variable size)
    Output: Preprocessed image ready for CNN (3-channel, 224×224, scaled [0,1])

    Flow:
    1. Segmentation (HMRF-EM) → Mask
    2. Apply Dilation → Extended segmentation
    3. L-R Separation + Square Crop → Two square images
    4. Grayscale + CLAHE → Enhanced grayscale
    5. 3-Channel Conversion → RGB
    6. Resizing (224×224) → Standard size
    7. Pixel Intensity Scaling (÷255) → [0, 1]
    """
    print("=" * 80)
    print(f"  COMPLETE IMAGE PREPROCESSING PIPELINE")
    print("=" * 80)

    # Step 1: Load and Segment
    print("\n[Step 1] Image Segmentation (HMRF-EM)...")
    img_pil = Image.open(image_path).convert("RGB")
    image_rgb = np.array(img_pil)

    image_ydbdr = rgb_to_ydbdr(image_rgb)
    labels = hmrf_em_segmentation(image_ydbdr, K=3, beta=1.5)
    foot_label = identify_foot_label(labels, image_ydbdr)
    foot_mask = create_foot_mask(labels, foot_label)
    pure_sole = get_pure_sole_image(image_rgb, foot_mask, background="black")

    # Step 2: Morphological Dilation
    print("\n[Step 2] Morphological Dilation...")
    merged_mask, _ = apply_morphological_dilation(pure_sole, output_dir=output_dir)

    # Step 3: L-R Separation & Square Crop
    print("\n[Step 3] L-R Separation & Square Crop...")
    foot_left, foot_right = separate_and_crop_feet(merged_mask, pure_sole, output_dir=output_dir)

    if foot_left is None or foot_right is None:
        print("Error: Failed to separate feet")
        return None

    # Step 4: Grayscale + CLAHE
    print("\n[Step 4] Grayscale & CLAHE Enhancement...")
    left_gray = convert_to_grayscale(foot_left)
    right_gray = convert_to_grayscale(foot_right)
    left_clahe = apply_clahe(left_gray, clip_limit=3.5, tile_grid_size=(8, 8))
    right_clahe = apply_clahe(right_gray, clip_limit=3.5, tile_grid_size=(8, 8))

    # Step 5: 3-Channel Conversion
    print("\n[Step 5] 3-Channel RGB Conversion...")
    left_rgb = convert_to_3channel_rgb(left_clahe)
    right_rgb = convert_to_3channel_rgb(right_clahe)

    # Step 6: Resizing
    print(f"\n[Step 6] Resizing to {target_size}...")
    left_resized = resize_image(left_rgb, target_size=target_size)
    right_resized = resize_image(right_rgb, target_size=target_size)

    # Step 7: Pixel Intensity Scaling (÷255)
    print("\n[Step 7] Pixel Intensity Scaling (÷255) → [0, 1]...")
    left_scaled = scale_pixels(left_resized)
    right_scaled = scale_pixels(right_resized)

    result = {
        'left_foot': left_scaled,
        'right_foot': right_scaled,
    }

    # Save final outputs if requested
    if save_final:
        base_name = os.path.splitext(os.path.basename(image_path))[0]

        left_output_dir  = os.path.join(output_dir, "left_foot")
        right_output_dir = os.path.join(output_dir, "right_foot")
        os.makedirs(left_output_dir,  exist_ok=True)
        os.makedirs(right_output_dir, exist_ok=True)

        left_output_path  = os.path.join(left_output_dir,  f"{base_name}_L.npy")
        right_output_path = os.path.join(right_output_dir, f"{base_name}_R.npy")

        np.save(left_output_path,  left_scaled)
        np.save(right_output_path, right_scaled)

        result['left_foot_path']  = left_output_path
        result['right_foot_path'] = right_output_path

        print(f"\n✓ Saved final outputs:")
        print(f"  Left:  {left_output_path}")
        print(f"  Right: {right_output_path}")

    print("\n" + "=" * 80)
    print(f"  ✓ Preprocessing complete!")
    print(f"  Left foot shape: {result['left_foot'].shape}, range: [{result['left_foot'].min():.3f}, {result['left_foot'].max():.3f}]")
    print(f"  Right foot shape: {result['right_foot'].shape}, range: [{result['right_foot'].min():.3f}, {result['right_foot'].max():.3f}]")
    print("=" * 80)

    return result


def batch_preprocess_images(input_folder: str, output_folder: str):
    """
    Batch process all foot images in input folder.
    Saves final preprocessed images (left_foot and right_foot) as .npy float32 [0,1].
    """
    image_paths = sorted(glob.glob(os.path.join(input_folder, "*.png")))

    if len(image_paths) == 0:
        print(f"❌ No PNG images found in {input_folder}")
        return {}

    print(f"\n{'='*80}")
    print(f"  BATCH PREPROCESSING - REAL DATASET")
    print(f"{'='*80}")
    print(f"📁 Input folder:  {input_folder}")
    print(f"📂 Output folder: {output_folder}")
    print(f"📊 Found {len(image_paths)} images to process\n")

    results = {}
    successful = 0
    failed = 0

    for idx, img_path in enumerate(image_paths, 1):
        img_name = os.path.basename(img_path)
        print(f"\n[{idx}/{len(image_paths)}] Processing: {img_name}")
        print("-" * 80)

        try:
            result = preprocess_foot_image(
                img_path,
                output_dir=output_folder,
                save_final=True
            )
            if result is not None:
                results[img_name] = result
                successful += 1
                print(f"✓ Successfully processed: {img_name}")
        except Exception as e:
            failed += 1
            print(f"✗ Error processing {img_name}:")
            print(f"  {str(e)}")
            import traceback
            traceback.print_exc()
            results[img_name] = None

    print("\n" + "=" * 80)
    print(f"  BATCH PROCESSING COMPLETE")
    print("=" * 80)
    print(f"✓ Successful: {successful}/{len(image_paths)}")
    print(f"✗ Failed:     {failed}/{len(image_paths)}")
    print(f"\n📂 Output structure:")
    print(f"  {output_folder}/")
    print(f"  ├── left_foot/  (contains name_L.npy files)")
    print(f"  └── right_foot/ (contains name_R.npy files)")
    print("=" * 80)

    return results
