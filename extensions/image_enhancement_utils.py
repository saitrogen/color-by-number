# color_by_number_app/extensions/image_enhancement_utils.py
import cv2
import numpy as np

def apply_post_quantization_smoothing(image_bgr, palette_bgr, method="median", ksize=3):
    """
    Applies smoothing to a BGR image that has already been quantized
    and then re-maps pixels to the closest color in the provided palette.
    """
    if not isinstance(ksize, int) or ksize % 2 == 0 or ksize < 1:
        print(f"Warning: Invalid ksize {ksize} for smoothing. Must be an odd positive integer. Defaulting to 3.")
        ksize = 3
    
    if not palette_bgr or len(palette_bgr) == 0:
        print("CRITICAL ERROR: Empty palette provided to smoothing function! Returning original image.")
        return image_bgr

    palette_np = np.array(palette_bgr, dtype=np.uint8)
    # print(f"DEBUG: Palette received in smoothing (shape {palette_np.shape}): {palette_np.tolist()}")


    smoothed_image_bgr = image_bgr.copy()
    if method == "median":
        # Median blur should output uint8 if input is uint8
        smoothed_image_bgr = cv2.medianBlur(image_bgr, ksize)
        # Just in case, ensure values are clipped if medianBlur somehow created out-of-range values
        # though this is generally not expected for cv2.medianBlur on uint8 images.
        # np.clip(smoothed_image_bgr, 0, 255, out=smoothed_image_bgr) # This might be overkill
        print(f"Applied median blur with ksize={ksize}")
    else:
        print(f"Warning: Unknown smoothing method '{method}'. Returning original image.")
        return image_bgr

    h, w = smoothed_image_bgr.shape[:2]
    reshaped_smoothed_image = smoothed_image_bgr.reshape((-1, 3))
    
    final_labels = np.zeros(reshaped_smoothed_image.shape[0], dtype=int)

    # Optimized nearest neighbor search using broadcasting for distance calculation
    # This is generally much faster than a Python loop for pixel-wise operations.
    
    # Convert reshaped image and palette to a numeric type that allows for subtraction without immediate overflow
    # and can hold squared differences. float32 or float64 is suitable.
    reshaped_smoothed_f = reshaped_smoothed_image.astype(np.float32)
    palette_f = palette_np.astype(np.float32)

    # For each pixel in reshaped_smoothed_f, calculate squared Euclidean distance to all palette colors
    # (P_x - C1_x)^2 + (P_y - C1_y)^2 + (P_z - C1_z)^2
    # (P_x - C2_x)^2 + (P_y - C2_y)^2 + (P_z - C2_z)^2
    # ...
    # This uses broadcasting:
    # reshaped_smoothed_f[:, np.newaxis, :] has shape (num_pixels, 1, 3)
    # palette_f[np.newaxis, :, :] has shape (1, num_palette_colors, 3)
    # The difference will broadcast to (num_pixels, num_palette_colors, 3)
    
    differences = reshaped_smoothed_f[:, np.newaxis, :] - palette_f[np.newaxis, :, :]
    squared_distances = np.sum(differences**2, axis=2) # Sum along the R,G,B components (axis 2)
                                                       # Result shape: (num_pixels, num_palette_colors)

    # No need for sqrt if we are just finding the minimum distance's index
    final_labels = np.argmin(squared_distances, axis=1) # Find index of min distance for each pixel (axis 1)

    # Debug prints for the first few pixels
    # if final_labels.size > 0 and reshaped_smoothed_image.shape[0] > 5 :
    #     print(f"DEBUG Smoothing: First 5 pixels original smoothed values: {reshaped_smoothed_image[:5].tolist()}")
    #     print(f"DEBUG Smoothing: First 5 labels: {final_labels[:5]}")
    #     if palette_np.size > 0:
    #          print(f"DEBUG Smoothing: Colors for first 5 labels: {palette_np[final_labels[:5]].tolist()}")
    #     else:
    #         print("DEBUG Smoothing: Palette is empty, cannot show colors for labels.")

    if palette_np.size == 0: # Should have been caught earlier, but as a safeguard
        print("CRITICAL ERROR: Palette became empty before remapping in smoothing! Returning original blurred image.")
        return smoothed_image_bgr # Or image_bgr

    remapped_image_bgr = palette_np[final_labels].reshape((h, w, 3)).astype(np.uint8)
    print("Re-snapped smoothed image to the provided palette using optimized distance.")
    
    return remapped_image_bgr