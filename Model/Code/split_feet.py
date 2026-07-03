"""
Foot Segregation and Square Cropping
======================================
Splits a segmented foot image (both feet on black background) 
into two separate, square-padded images (Left and Right).

Technique:
  1. Connected Component Analysis to find the 2 largest blobs (feet).
  2. Bounding Box extraction (tight crop).
  3. Image Pad to Square (padding smaller dimension with black to match the larger).
"""

import os
import argparse
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import label, find_objects, binary_dilation

def pad_to_square(img_array: np.ndarray) -> np.ndarray:
    """
    Pad an RGB image array with black pixels to make it a perfect square.
    """
    h, w = img_array.shape[:2]
    size = max(h, w)
    
    # Calculate padding for both sides
    pad_h_top = (size - h) // 2
    pad_h_bottom = size - h - pad_h_top
    pad_w_left = (size - w) // 2
    pad_w_right = size - w - pad_w_left
    
    # Applies zero (black) padding. Shape is (H, W, Channels)
    padded = np.pad(img_array, ((pad_h_top, pad_h_bottom), 
                                (pad_w_left, pad_w_right), 
                                (0, 0)), 
                    mode='constant', constant_values=0)
    return padded

def process_and_split(image_path: str, output_dir: str | None = None, flip_left: bool = False):
    """
    Load image, extract left and right footprint, crop tight, and pad to square.
    """
    print("=" * 60)
    print(f"  Splitting Feet (L/R) and Square Cropping")
    print("=" * 60)

    # 1. Load image and create binary mask
    img_pil = Image.open(image_path).convert("RGB")
    img_array = np.array(img_pil)
    
    # Assuming black background (pixels > 0 are foot)
    # Convert to grayscale sum to reliably find non-black pixels
    intensity = img_array.sum(axis=2)
    binary_mask = (intensity > 0).astype(np.uint8)
    
    # We use a dynamic kernel based on image size to be robust for ANY image resolution.
    # e.g., Vertical stretch = 12% of image height. Horizontal = 5px (narrow).
    img_h, img_w = img_array.shape[:2]
    dilate_h = max(10, int(img_h * 0.12))
    struct_dilate = np.ones((dilate_h, 5), dtype=bool)
    
    merged_mask = binary_dilation(binary_mask, structure=struct_dilate)
    
    # --- [เพิ่มเพื่อทำสไลด์] Bันทึกรูป Dilation ให้ผู้ใช้เห็นภาพ ---
    if output_dir is None:
        out_dir = os.path.dirname(image_path)
    else:
        out_dir = output_dir
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(image_path))[0]
    demo_path = os.path.join(out_dir, f"{base}_dilated_demo.png")
    Image.fromarray((merged_mask * 255).astype(np.uint8)).save(demo_path)
    # ----------------------------------------------------------------
    
    # 2. Connected Component Labeling
    # 8-connected structure on the merged mask
    structure = np.ones((3, 3), dtype=np.int32)
    labeled_mask, num_features = label(merged_mask, structure=structure)
    
    if num_features < 2:
        print("Error: Could not find at least 2 separate feet in the image.")
        return
        
    # 3. Find the 2 Largest Components (Area)
    # np.bincount counts pixels for each label. Exclude label 0 (background)
    component_sizes = np.bincount(labeled_mask.ravel())
    component_sizes[0] = 0  # ignore background
    
    # Get the labels of the 2 largest components
    largest_labels = np.argsort(component_sizes)[-2:]
    
    # 4. Extract Bounding Boxes using find_objects
    slices = find_objects(labeled_mask)
    
    extracted_feet = []
    
    for lbl in largest_labels:
        # slices is 0-indexed, but labels are 1-indexed
        bbox = slices[lbl - 1]
        
        # The centroid roughly or simply the bounding box exact center X
        # To decide if it is Left or Right in the image.
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
        
    # 5. Sort by X coordinate (Leftmost object = Image Left)
    extracted_feet.sort(key=lambda item: item['center_x'])
    foot_left_img  = extracted_feet[0]['square_img']
    foot_right_img = extracted_feet[1]['square_img']

    if flip_left:
        foot_left_img = foot_left_img[:, ::-1, :]
    
    # --- [เพิ่มเพื่อทำสไลด์] วาดกรอบสี่เหลี่ยมโชว์ Tight Crop & L/R Sorting ---
    demo_img = img_pil.copy()
    draw = ImageDraw.Draw(demo_img)
    
    # วาดกรอบเท้าซ้าย (สีแดง)
    yL, xL = extracted_feet[0]['bbox']
    draw.rectangle([xL.start, yL.start, xL.stop, yL.stop], outline="red", width=3)
    # วาดกรอบเท้าขวา (สีน้ำเงิน)
    yR, xR = extracted_feet[1]['bbox']
    draw.rectangle([xR.start, yR.start, xR.stop, yR.stop], outline="blue", width=3)
    
    demo_path2 = os.path.join(out_dir, f"{base}_sorting_demo.png")
    demo_img.save(demo_path2)
    print(f"Saved Sorting Demo  → {demo_path2}")
    # ----------------------------------------------------------------------
    
    print(f"Left Foot:  {foot_left_img.shape[0]}x{foot_left_img.shape[1]}")
    print(f"Right Foot: {foot_right_img.shape[0]}x{foot_right_img.shape[1]}")
    
    # 6. Save Output
    if output_dir is None:
        output_dir = os.path.dirname(image_path)
    os.makedirs(output_dir, exist_ok=True)
    
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    base_name = base_name.replace('_foot_black_bg', '')
    
    path_L = os.path.join(output_dir, f"{base_name}_L_square.png")
    path_R = os.path.join(output_dir, f"{base_name}_R_square.png")
    
    Image.fromarray(foot_left_img).save(path_L)
    Image.fromarray(foot_right_img).save(path_R)
    
    print(f"Saved Image L → {path_L}")
    print(f"Saved Image R → {path_R}")
    print("=" * 60)
    print("  Done!")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Split left and right foot and pad to square.")
    parser.add_argument("-i", "--input", type=str, required=True, 
                        help="Path to the segmented image (e.g. _foot_black_bg.png)")
    parser.add_argument("-o", "--output_dir", type=str, default=None,
                        help="Directory to save the L/R square images (optional)")
    parser.add_argument("--flip_left", action="store_true",
                        help="Horizontally flip the left foot to match right foot orientation (S2 strategy)")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}")
    else:
        process_and_split(image_path=args.input, output_dir=args.output_dir, flip_left=args.flip_left)
