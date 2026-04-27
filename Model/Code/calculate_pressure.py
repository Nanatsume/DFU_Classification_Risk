"""
Foot Plantar Pressure Calculation
===================================
Calculates the physical pressure distribution on the sole of the foot
based on pixel intensities of a segmented foot image.

Formulas:
  1. T = sum(im(i))
  2. Pi = im(i) / T
  3. Pressure(i) = Weight_Newtons * Pi

Assumes:
  - 1 pixel = 1 mm^2 (Calibration)
  - Resulting unit = N/mm^2 (MPa)
"""

import os
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt

def calculate_pressure_map(masked_image_path: str, weight_kg: float, 
                           gravity: float = 9.81) -> dict:
    """
    Calculate the pressure distribution from a clean segmented foot image.
    
    Parameters
    ----------
    masked_image_path : str
        Path to the segmented foot image (background must be completely black).
    weight_kg : float
        Patient's body weight in kilograms.
    gravity : float
        Acceleration due to gravity (default 9.81 m/s^2) to convert kg to Newtons.
        
    Returns
    -------
    dict containing the pressure map and analysis metrics.
    """
    print("=" * 60)
    print(f"  Pressure Calculation (Weight: {weight_kg} kg)")
    print("=" * 60)
    
    # 1. Load image and convert to Grayscale (Intensity)
    img = Image.open(masked_image_path).convert("L")
    intensity_map = np.array(img, dtype=np.float64)
    
    # Identify foot pixels (non-zero intensity)
    # Background must be zero!
    foot_mask = intensity_map > 0
    
    # 2. Total Intensity (T)
    T = np.sum(intensity_map)
    if T == 0:
        raise ValueError("Image is completely black! No foot region found.")
        
    print(f"Total Intensity (T): {T:.2f}")
    
    # 3. Pixel Coefficient (P_i)
    Pi_map = intensity_map / T
    
    # 4. Total Force in Newtons
    weight_n = weight_kg * gravity
    print(f"Total Force: {weight_n:.2f} Newtons")
    
    # 5. Calculate Pressure Map (N / mm^2)
    # Since calibration is 1 pixel = 1 mm^2, force per pixel IS the pressure in N/mm^2
    pressure_map = Pi_map * weight_n
    
    # Calculate some metrics for reporting
    max_pressure = np.max(pressure_map)
    mean_pressure = np.mean(pressure_map[foot_mask])
    contact_area_mm2 = np.sum(foot_mask)  # Since 1 px = 1 mm^2
    
    print(f"Contact Area: {contact_area_mm2} mm^2 (or pixels)")
    print(f"Mean Pressure: {mean_pressure:.5f} N/mm^2")
    print(f"Max Peak Pressure: {max_pressure:.5f} N/mm^2")
    
    return {
        "pressure_map": pressure_map,
        "intensity_map": intensity_map,
        "foot_mask": foot_mask,
        "max_pressure": max_pressure,
        "mean_pressure": mean_pressure,
        "contact_area": contact_area_mm2
    }


def visualise_pressure_heatmap(result: dict, image_name: str, save_path: str | None = None):
    """
    Generate a heatmap of the plantar pressure distribution.
    """
    pressure_map = result["pressure_map"]
    foot_mask = result["foot_mask"]
    
    # Mask out the background for plotting (set to NaN so colormap ignores it)
    plot_map = np.copy(pressure_map)
    plot_map[~foot_mask] = np.nan
    
    # Create plot
    fig, ax = plt.subplots(figsize=(8, 10))
    
    # Use 'jet' or 'turbo' colormap, standard for pressure maps
    cmap = plt.get_cmap("turbo")
    cmap.set_bad(color='black')  # set background (NaNs) to black
    
    cax = ax.imshow(plot_map, cmap=cmap, interpolation='nearest')
    ax.set_title(f"Plantar Pressure Map\nMax = {result['max_pressure']:.4f} N/mm$^2$")
    ax.axis("off")
    
    # Add colorbar
    cbar = fig.colorbar(cax, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Pressure (N/mm$^2$)', rotation=270, labelpad=15)
    
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=200, bbox_inches='tight', facecolor='black')
        print(f"Saved Heatmap → {save_path}")
    plt.show()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Calculate plantar pressure from foot image.")
    parser.add_argument("-i", "--input", type=str, required=True, 
                        help="Path to the segmented foot image (e.g., _foot_black_bg.png)")
    parser.add_argument("-w", "--weight", type=float, required=True, 
                        help="Patient's weight in kg")
    parser.add_argument("-o", "--output_dir", type=str, default=None, 
                        help="Directory to save the heatmap (defaults to input file's folder)")

    args = parser.parse_args()
    
    input_file = args.input
    patient_weight = args.weight
    
    if not os.path.exists(input_file):
        print(f"Error: Input file not found:\n{input_file}")
        print("Please check the path and try again.")
    else:
        # Determine output directory (if None, use the same directory as input)
        output_dir = args.output_dir if args.output_dir else os.path.dirname(input_file)
        os.makedirs(output_dir, exist_ok=True)
        
        # 1. Calculate pressure
        result = calculate_pressure_map(input_file, weight_kg=patient_weight)
        
        # 2. Visualise and save
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        # Clean up the name a bit 
        base_name = base_name.replace('_foot_black_bg', '')
        
        save_file = os.path.join(output_dir, f"{base_name}_pressure_heatmap.png")
        visualise_pressure_heatmap(result, base_name, save_path=save_file)
