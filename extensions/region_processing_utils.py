# color_by_number_app/extensions/region_processing_utils.py
import cv2
import numpy as np
from collections import Counter

def merge_small_regions(quantized_image_bgr, palette_bgr, min_area_threshold_percent=0.1):
    """
    Merges small color regions into their largest neighbors.
    min_area_threshold_percent: Percentage of total image area. Regions smaller than this will be considered for merging.
    Returns:
        - new_quantized_image_bgr: Image with small regions merged.
        - new_palette_bgr: Updated palette reflecting only colors present in the new image.
                           (Order might change if colors are eliminated).
    """
    h, w = quantized_image_bgr.shape[:2]
    total_pixels = h * w
    min_absolute_area = (min_area_threshold_percent / 100.0) * total_pixels

    print(f"Min area for merging: {min_absolute_area} pixels ({min_area_threshold_percent}%)")

    processed_image = quantized_image_bgr.copy()
    current_palette_bgr = list(palette_bgr) # Make it a list to potentially remove colors

    # Iterate multiple times or until no small regions are left, as merging can create new small regions.
    # For simplicity, let's do a fixed number of passes or one comprehensive pass.
    # A more robust approach might involve a loop until convergence.

    for _ in range(2): # Do a couple of passes to catch some chain reactions
        unique_colors_in_image = [tuple(c) for c in np.unique(processed_image.reshape(-1, 3), axis=0)]
        
        # Map current palette colors to their indices if needed, or work with color values directly
        color_to_process_indices = [i for i, color in enumerate(current_palette_bgr) if tuple(color) in unique_colors_in_image]


        for color_idx, original_palette_idx in enumerate(color_to_process_indices):
            target_color_bgr = current_palette_bgr[original_palette_idx]
            
            # Create mask for the current color
            mask = cv2.inRange(processed_image, np.array(target_color_bgr), np.array(target_color_bgr))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                area = cv2.contourArea(contour)
                if area < min_absolute_area and area > 0: # If area is small but not zero
                    # Create a mask for this specific small contour
                    contour_mask = np.zeros((h, w), dtype=np.uint8)
                    cv2.drawContours(contour_mask, [contour], -1, 255, -1) # Filled contour

                    # Dilate this contour_mask to find neighbors
                    kernel = np.ones((3,3), np.uint8)
                    dilated_contour_mask = cv2.dilate(contour_mask, kernel, iterations=2) # Dilate a bit more to ensure overlap
                    
                    neighbor_pixels_mask = cv2.bitwise_and(dilated_contour_mask, cv2.bitwise_not(contour_mask))

                    # Find colors of neighbor pixels
                    neighbor_colors = []
                    neighbor_pixel_coords = np.where(neighbor_pixels_mask == 255)
                    
                    if neighbor_pixel_coords[0].size == 0: continue # No neighbors found (should be rare)

                    for r, c in zip(neighbor_pixel_coords[0], neighbor_pixel_coords[1]):
                        # Ensure we don't pick the color of the region itself if dilation was insufficient
                        # or if it's an isolated speck (though min_area should prevent this for true specks)
                        px_color = tuple(processed_image[r, c])
                        if px_color != tuple(target_color_bgr):
                            neighbor_colors.append(px_color)
                    
                    if not neighbor_colors:
                        # print(f"Small region of color {target_color_bgr} at area {area} has no DIFFERENT neighbors. Skipping.")
                        continue

                    # Find the most frequent neighbor color (simplest strategy)
                    # A better strategy: largest neighboring region or longest shared border
                    most_common_neighbor_color = Counter(neighbor_colors).most_common(1)[0][0]
                    
                    # Recolor the small region (defined by contour_mask)
                    processed_image[contour_mask == 255] = most_common_neighbor_color
                    # print(f"Merged small region (area {area}, color {target_color_bgr}) into color {most_common_neighbor_color}")


    # After all merging, create the new palette based on colors actually present
    final_unique_colors_bgr = np.unique(processed_image.reshape(-1, 3), axis=0)
    
    # Maintain some order if possible, or just use the unique colors
    # For simplicity, the new palette will be these unique colors.
    # The mapping of old numbers to new numbers will change.
    new_palette_bgr_final = [list(color) for color in final_unique_colors_bgr]

    # Re-quantize the image to this new final palette to ensure consistency and correct labels for numbering
    # This step is important if colors were eliminated.
    pixels_final = processed_image.reshape((-1, 3))
    
    # If no colors, return original (should not happen)
    if not new_palette_bgr_final:
        return quantized_image_bgr, palette_bgr

    # Create a "KMeans-like" object for re-labeling based on the new palette
    # This is a bit of a hack if KMeans isn't directly used here.
    # We need to map each pixel in processed_image to an index in new_palette_bgr_final.
    # A more direct way: for each pixel, find closest color in new_palette_bgr_final.
    
    temp_labels = np.zeros(pixels_final.shape[0], dtype=int)
    new_palette_np = np.array(new_palette_bgr_final, dtype=np.uint8)

    for i, color in enumerate(new_palette_np):
        # Find all pixels that match this color
        matches = np.all(pixels_final == color, axis=1)
        temp_labels[matches] = i
        
    # Construct the re-quantized image based on new palette and new labels
    remapped_image_bgr = new_palette_np[temp_labels].reshape((h, w, 3)).astype(np.uint8)

    return remapped_image_bgr, new_palette_np.tolist()