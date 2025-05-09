# color_by_number_app/extensions/core_processing.py
import cv2
import numpy as np
from sklearn.cluster import KMeans
from PIL import Image, ImageDraw, ImageFont 
from io import BytesIO

try:
    from utils.image_helpers import image_to_base64, opencv_to_pil, pil_to_opencv
    from extensions.region_processing_utils import merge_small_regions
    from extensions.image_enhancement_utils import apply_post_quantization_smoothing
    from extensions.download_utils import generate_svg_content 
except ImportError: 
    print("Core Processing: Could not use relative imports, attempting direct.")
    from utils.image_helpers import image_to_base64, opencv_to_pil, pil_to_opencv
    from region_processing_utils import merge_small_regions
    from image_enhancement_utils import apply_post_quantization_smoothing
    from download_utils import generate_svg_content


class ProcessCancelledError(Exception):
    """Custom exception for a cancelled process."""
    pass

def process_image_pipeline(
    pil_image_orig_rgba, 
    params,              # Dictionary of all processing parameters
    task_id,             
    check_if_cancelled_func, 
    log_func,            
    get_font_func        
    ):

    log_func("Pipeline: Starting core image processing.")
    # --- ADD THIS DEBUG PRINT ---
    log_func(f"Pipeline: Params received by core_processing: {params}") 
    # --- END OF DEBUG PRINT ---


    # Unpack parameters
    # Use .get() for safety during unpacking here, with defaults,
    # although the KeyError suggests the key is truly missing by this point
    # if the previous debug print shows it *was* there.
    num_colors = params.get('numColors', 8) # Use .get() as a defensive measure
    if 'numColors' not in params:
        log_func("CRITICAL Pipeline: 'numColors' key is MISSING from params INSIDE core_processing.")
        # You might want to raise an error here or use a default
        # raise ValueError("numColors not found in params for core processing")

    font_size_param = params.get('fontSize', 15)
    line_sensitivity_str = params.get('lineSensitivity', 'medium')
    should_merge_small_regions = params.get('mergeSmallRegions', False)
    min_merge_area_percent = params.get('minMergeAreaPercent', 0.1)
    enable_bg_removal_flag = params.get('enableBgRemoval', False)
    selected_bg_color_rgb = params.get('selectedBgColor', None)
    bg_color_tolerance = params.get('bgColorTolerance', 30)
    enable_smoothing_flag = params.get('enableSmoothing', False)
    smoothing_ksize = params.get('smoothingKernelSize', 3)
    
    output_prefs = params.get('outputs', {})
    gen_numbers = output_prefs.get('generateNumbers', True)
    gen_line_art_png = output_prefs.get('lineArtPng', True)
    gen_line_art_svg = output_prefs.get('lineArtSvg', True)

    # ... (rest of your core_processing.py code as provided previously)
    # Ensure all subsequent direct accesses like params['someKey'] are changed to params.get('someKey', default_value)
    # or that you've confirmed the keys exist after the initial unpacking.

    img_np_rgba_original = np.array(pil_image_orig_rgba)
    original_alpha_channel_np = None
    if img_np_rgba_original.shape[2] == 4:
        original_alpha_channel_np = img_np_rgba_original[:, :, 3].copy()
        img_np_rgb_from_original = img_np_rgba_original[:, :, :3]
    else: 
        img_np_rgb_from_original = img_np_rgba_original
        if len(img_np_rgb_from_original.shape) == 2:
            img_np_rgb_from_original = cv2.cvtColor(img_np_rgb_from_original, cv2.COLOR_GRAY2RGB)

    img_cv_bgr_for_quantization = cv2.cvtColor(img_np_rgb_from_original, cv2.COLOR_RGB2BGR)
    h, w = img_cv_bgr_for_quantization.shape[:2]

    if check_if_cancelled_func(task_id): raise ProcessCancelledError("Cancelled before quantization.")
    log_func("Pipeline: Quantizing colors...")
    pixels = img_cv_bgr_for_quantization.reshape((-1, 3)).astype(np.float32)
    kmeans = KMeans(n_clusters=num_colors, random_state=42, n_init=10, tol=1e-3) # Uses the unpacked num_colors
    kmeans.fit(pixels)
    initial_palette_bgr_np = kmeans.cluster_centers_.astype(np.uint8)
    labels = kmeans.labels_
    quantized_img_content_bgr = initial_palette_bgr_np[labels].reshape((h, w, 3))
    current_processing_palette_bgr = initial_palette_bgr_np.tolist()

    if check_if_cancelled_func(task_id): raise ProcessCancelledError("Cancelled after quantization.")
    if enable_smoothing_flag:
        log_func(f"Pipeline: Applying smoothing (kernel: {smoothing_ksize})...")
        quantized_img_content_bgr = apply_post_quantization_smoothing(
            quantized_img_content_bgr, current_processing_palette_bgr, "median", smoothing_ksize
        )
    
    if check_if_cancelled_func(task_id): raise ProcessCancelledError("Cancelled after smoothing.")
    if should_merge_small_regions:
        log_func(f"Pipeline: Merging small regions (threshold: {min_merge_area_percent}%)...")
        quantized_img_content_bgr, current_processing_palette_bgr = merge_small_regions(
            quantized_img_content_bgr, current_processing_palette_bgr, min_merge_area_percent
        )
        if isinstance(current_processing_palette_bgr, np.ndarray):
            current_processing_palette_bgr = current_processing_palette_bgr.tolist()

    final_display_palette_rgb = [color[::-1] for color in current_processing_palette_bgr]

    if check_if_cancelled_func(task_id): raise ProcessCancelledError("Cancelled before alpha determination.")
    log_func("Pipeline: Determining alpha channel...")
    final_applied_alpha_pil = None
    if enable_bg_removal_flag and selected_bg_color_rgb:
        bg_color_np_rgb = np.array(selected_bg_color_rgb, dtype=np.uint8)
        diff = np.abs(img_np_rgb_from_original.astype(np.int16) - bg_color_np_rgb.astype(np.int16))
        is_background_mask = np.all(diff <= bg_color_tolerance, axis=2)
        alpha_channel_content_np = np.where(is_background_mask, 0, 255).astype(np.uint8)
        final_applied_alpha_pil = Image.fromarray(alpha_channel_content_np)
    elif original_alpha_channel_np is not None:
        final_applied_alpha_pil = Image.fromarray(original_alpha_channel_np)
    else:
        final_applied_alpha_pil = Image.new('L', (w, h), 255)
    
    log_func("Pipeline: Preparing final colored image...")
    quantized_content_pil_rgb = opencv_to_pil(quantized_img_content_bgr)
    final_output_image_pil = quantized_content_pil_rgb.convert("RGBA")
    if final_applied_alpha_pil.size == final_output_image_pil.size:
        final_output_image_pil.putalpha(final_applied_alpha_pil)
    else:
        log_func(f"Warning: Alpha/image size mismatch. Applying opaque fallback alpha.")
        fallback_alpha = Image.new('L', final_output_image_pil.size, 255)
        final_output_image_pil.putalpha(fallback_alpha)

    results = {
        "palette_rgb": final_display_palette_rgb,
        "image_width": w,
        "image_height": h,
        "quantized_image_b64": None, 
        "bg_removed_char_b64": None,
        "line_art_png_b64": None,
        "line_art_svg_content": None,
    }
    results["quantized_image_b64"] = image_to_base64(final_output_image_pil)
    results["bg_removed_char_b64"] = results["quantized_image_b64"]


    if gen_line_art_png or gen_line_art_svg:
        if check_if_cancelled_func(task_id): raise ProcessCancelledError("Cancelled before line art generation.")
        log_func("Pipeline: Generating line art...")
        line_thickness = 1
        base_min_area_for_numbering = max(30, font_size_param * font_size_param * 0.3)
        if line_sensitivity_str == 'low': line_thickness = 2; min_contour_area_for_numbering = base_min_area_for_numbering * 1.5
        elif line_sensitivity_str == 'high': min_contour_area_for_numbering = base_min_area_for_numbering * 0.7
        else: min_contour_area_for_numbering = base_min_area_for_numbering

        line_art_pil_for_png = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        draw_png = ImageDraw.Draw(line_art_pil_for_png)
        current_font = get_font_func(font_size_param) # Use passed function

        all_contours_for_svg_data = []
        all_texts_for_svg_data = []

        for i, color_bgr_val in enumerate(current_processing_palette_bgr):
            if check_if_cancelled_func(task_id): raise ProcessCancelledError("Cancelled during line art contouring.")
            mask = cv2.inRange(quantized_img_content_bgr, np.array(color_bgr_val), np.array(color_bgr_val))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            color_number_str = str(i + 1)

            for contour in contours:
                contour_area_val = cv2.contourArea(contour)
                if contour_area_val > 5:
                    all_contours_for_svg_data.append(contour)
                    if gen_line_art_png:
                        pil_contour_points = [tuple(p[0]) for p in contour]
                        if len(pil_contour_points) > 1:
                            draw_png.line(pil_contour_points + [pil_contour_points[0]], fill="black", width=line_thickness)
                
                if gen_numbers and contour_area_val > min_contour_area_for_numbering:
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"]); cy = int(M["m01"] / M["m00"])
                        if cv2.pointPolygonTest(contour, (cx, cy), False) >= 0:
                            if current_font:
                                if gen_line_art_png:
                                    try:
                                        bbox = draw_png.textbbox((cx, cy), color_number_str, font=current_font, anchor="mm")
                                        text_x = cx - (bbox[2] - bbox[0]) // 2; text_y = cy - (bbox[3] - bbox[1]) // 2
                                        draw_png.text((text_x, text_y), color_number_str, fill="black", font=current_font)
                                    except Exception as font_exc: log_func(f"Error drawing text for PNG: {font_exc}")
                            if gen_line_art_svg:
                                all_texts_for_svg_data.append({'text': color_number_str, 'x': cx, 'y': cy, 'size': font_size_param})
        
        if gen_line_art_png:
            results["line_art_png_b64"] = image_to_base64(line_art_pil_for_png)
        if gen_line_art_svg:
            results["line_art_svg_content"] = generate_svg_content(w, h, all_contours_for_svg_data, all_texts_for_svg_data if gen_numbers else [])

    log_func("Pipeline: Core processing finished.")
    return results