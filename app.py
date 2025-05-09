# color_by_number_app/app.py

from flask import Flask, request, jsonify, render_template
import cv2
import numpy as np
from sklearn.cluster import KMeans
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# Local imports
from utils.image_helpers import image_to_base64, opencv_to_pil, pil_to_opencv, decode_data_url
from extensions.download_utils import download_bp, generate_svg_content
from extensions.region_processing_utils import merge_small_regions
from extensions.image_enhancement_utils import apply_post_quantization_smoothing

app = Flask(__name__)
app.register_blueprint(download_bp, url_prefix='/downloads')

# --- FONT CONFIGURATION ---
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 
    "arial.ttf", 
    "C:\\Windows\\Fonts\\arial.ttf", 
    "/Library/Fonts/Arial.ttf", 
    "/System/Library/Fonts/Supplemental/Arial.ttf"
]
DEFAULT_FONT_SIZE = 15
FONT = None
for path in FONT_PATHS:
    try:
        FONT = ImageFont.truetype(path, DEFAULT_FONT_SIZE)
        print(f"Loaded font for main processing: {path}")
        break
    except IOError:
        pass
if FONT is None:
    try:
        FONT = ImageFont.load_default()
        print("Warning: Using default Pillow font for main processing (text might be small).")
    except Exception as e:
        print(f"Critical: Could not load any specified fonts or default Pillow font: {e}")
        FONT = None

def get_font(size):
    if FONT and hasattr(FONT, 'path') and FONT.path:
        try:
            return ImageFont.truetype(FONT.path, size)
        except IOError:
            # print(f"Warning: Could not load font {FONT.path} at size {size}. Falling back to default size.")
            return FONT
    elif FONT:
        return FONT
    # print(f"Warning: No valid font object available for get_font(size={size}).")
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process_image', methods=['POST'])
def process_image_route():
    try:
        data = request.get_json()
        image_data_url = data['imageDataUrl']
        num_colors = int(data.get('numColors', 8))
        font_size_param = int(data.get('fontSize', DEFAULT_FONT_SIZE))
        
        line_sensitivity_str = data.get('lineSensitivity', 'medium')
        should_merge_small_regions = data.get('mergeSmallRegions', False)
        min_merge_area_percent = float(data.get('minMergeAreaPercent', 0.1))
        
        enable_bg_removal_flag = data.get('enableBgRemoval', False)
        selected_bg_color_rgb = data.get('selectedBgColor', None)
        bg_color_tolerance = int(data.get('bgColorTolerance', 30))

        enable_smoothing_flag = data.get('enableSmoothing', False)
        smoothing_ksize = int(data.get('smoothingKernelSize', 3))

        image_data_bytes = decode_data_url(image_data_url)
        
        pil_image_orig = Image.open(BytesIO(image_data_bytes)).convert("RGBA")
        img_np_rgba_original = np.array(pil_image_orig) # Keep original RGBA for reference
        
        original_alpha_channel_np = None # Alpha from the input image
        if img_np_rgba_original.shape[2] == 4:
            original_alpha_channel_np = img_np_rgba_original[:, :, 3].copy()
            img_np_rgb_from_original = img_np_rgba_original[:, :, :3]
        else:
            img_np_rgb_from_original = img_np_rgba_original
            if len(img_np_rgb_from_original.shape) == 2:
                 img_np_rgb_from_original = cv2.cvtColor(img_np_rgb_from_original, cv2.COLOR_GRAY2RGB)

        img_cv_bgr_for_quantization = cv2.cvtColor(img_np_rgb_from_original, cv2.COLOR_RGB2BGR)
        h, w = img_cv_bgr_for_quantization.shape[:2]

        # 1. Color Quantization
        pixels = img_cv_bgr_for_quantization.reshape((-1, 3)).astype(np.float32)
        kmeans = KMeans(n_clusters=num_colors, random_state=42, n_init=10, tol=1e-3)
        kmeans.fit(pixels)
        initial_palette_bgr_np = kmeans.cluster_centers_.astype(np.uint8)
        labels = kmeans.labels_
        # This is the first version of our quantized image content
        quantized_img_content_bgr = initial_palette_bgr_np[labels].reshape((h, w, 3))

        # The palette that corresponds to quantized_img_content_bgr
        current_processing_palette_bgr = initial_palette_bgr_np.tolist() 
        
        # 1.5 Apply Post-Quantization Smoothing if enabled
        if enable_smoothing_flag:
            print(f"Applying post-quantization smoothing with kernel size: {smoothing_ksize}")
            # Smoothing uses the current content and its corresponding palette
            quantized_img_content_bgr = apply_post_quantization_smoothing(
                quantized_img_content_bgr, 
                current_processing_palette_bgr, 
                method="median", 
                ksize=smoothing_ksize
            )
            # The palette (current_processing_palette_bgr) is NOT changed by smoothing itself,
            # as smoothing re-snaps to the provided palette.
        
        # 2. (Optional) Merge Small Regions
        if should_merge_small_regions:
            print(f"Attempting to merge small regions with threshold: {min_merge_area_percent}%")
            # Merging takes the current image content and its palette,
            # and can return modified content AND a modified (potentially smaller) palette.
            quantized_img_content_bgr, current_processing_palette_bgr = merge_small_regions(
                quantized_img_content_bgr, 
                current_processing_palette_bgr,
                min_merge_area_percent
            )
            print(f"Region merging complete. New final palette size: {len(current_processing_palette_bgr)}")
            if isinstance(current_processing_palette_bgr, np.ndarray): # Ensure it's a list for consistency
                current_processing_palette_bgr = current_processing_palette_bgr.tolist()

        # `quantized_img_content_bgr` now holds the final BGR pixel data after all content processing.
        # `current_processing_palette_bgr` is the final BGR palette corresponding to this content.
        final_display_palette_rgb = [color[::-1] for color in current_processing_palette_bgr] # For legend

        # --- Determine the Alpha Channel to Apply ---
        final_applied_alpha_pil = None
        if enable_bg_removal_flag and selected_bg_color_rgb:
            print(f"BG Removal: Using selected color {selected_bg_color_rgb} with tolerance {bg_color_tolerance}")
            bg_color_np_rgb = np.array(selected_bg_color_rgb, dtype=np.uint8)
            # Compare against the original RGB image data for accuracy
            diff = np.abs(img_np_rgb_from_original.astype(np.int16) - bg_color_np_rgb.astype(np.int16))
            is_background_mask = np.all(diff <= bg_color_tolerance, axis=2)
            alpha_channel_content_np = np.where(is_background_mask, 0, 255).astype(np.uint8)
            final_applied_alpha_pil = Image.fromarray(alpha_channel_content_np)
        elif original_alpha_channel_np is not None:
            print("BG Removal: Using original alpha channel from input image.")
            final_applied_alpha_pil = Image.fromarray(original_alpha_channel_np)
        else:
            print("BG Removal: No specific removal, using full opaque alpha.")
            final_applied_alpha_pil = Image.new('L', (w, h), 255)
        
        # --- Create Final RGBA Output Image (Colored Preview / BG Removed) ---
        quantized_content_pil_rgb = opencv_to_pil(quantized_img_content_bgr)
        final_output_image_pil = quantized_content_pil_rgb.convert("RGBA")

        if final_applied_alpha_pil.size == final_output_image_pil.size:
            final_output_image_pil.putalpha(final_applied_alpha_pil)
        else:
            print(f"Warning: Alpha channel size {final_applied_alpha_pil.size} mismatch with image content size {final_output_image_pil.size}. Applying opaque fallback alpha.")
            fallback_alpha = Image.new('L', final_output_image_pil.size, 255)
            final_output_image_pil.putalpha(fallback_alpha)

        # --- Line Art and Numbering ---
        line_thickness = 1
        base_min_area_for_numbering = max(30, font_size_param * font_size_param * 0.3) 
        if line_sensitivity_str == 'low':
            line_thickness = 2
            min_contour_area_for_numbering = base_min_area_for_numbering * 1.5 
        elif line_sensitivity_str == 'high':
            min_contour_area_for_numbering = base_min_area_for_numbering * 0.7
        else: # Medium
            min_contour_area_for_numbering = base_min_area_for_numbering

        line_art_pil_for_png = Image.new("RGBA", (w, h), (255, 255, 255, 0)) # Transparent BG
        draw_png = ImageDraw.Draw(line_art_pil_for_png)
        current_font = get_font(font_size_param)
        if current_font is None:
            print("CRITICAL: No font available for drawing text. Numbers will be missing.")

        all_contours_for_svg = []
        all_texts_for_svg = []

        # Iterate through the final palette (current_processing_palette_bgr) for numbering
        for i, color_bgr_val in enumerate(current_processing_palette_bgr):
            # Create mask from the final processed content (quantized_img_content_bgr)
            mask = cv2.inRange(quantized_img_content_bgr, np.array(color_bgr_val), np.array(color_bgr_val))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            color_number_str = str(i + 1)

            for contour in contours:
                contour_area_val = cv2.contourArea(contour)
                if contour_area_val > 5: # Threshold for drawing lines
                    all_contours_for_svg.append(contour)
                    pil_contour_points = [tuple(p[0]) for p in contour]
                    if len(pil_contour_points) > 1:
                        draw_png.line(pil_contour_points + [pil_contour_points[0]], fill="black", width=line_thickness)

                if contour_area_val > min_contour_area_for_numbering: # Threshold for placing numbers
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        if cv2.pointPolygonTest(contour, (cx, cy), False) >= 0:
                            if current_font:
                                try: # Add try-except for text drawing as it can be sensitive to font issues
                                    bbox = draw_png.textbbox((cx, cy), color_number_str, font=current_font, anchor="mm")
                                    text_x_png = cx - (bbox[2] - bbox[0]) // 2
                                    text_y_png = cy - (bbox[3] - bbox[1]) // 2
                                    draw_png.text((text_x_png, text_y_png), color_number_str, fill="black", font=current_font)
                                except Exception as font_exc:
                                    print(f"Error drawing text for number {color_number_str}: {font_exc}")

                            all_texts_for_svg.append({'text': color_number_str, 'x': cx, 'y': cy, 'size': font_size_param})
        
        # --- Prepare outputs ---
        quantized_image_b64 = image_to_base64(final_output_image_pil)
        # The "BG Removed Character" is essentially the same as the "Colored Preview" 
        # now that background removal directly affects the alpha of the preview.
        bg_removed_char_b64 = quantized_image_b64 
        
        line_art_png_b64 = image_to_base64(line_art_pil_for_png)
        line_art_svg_content = generate_svg_content(w, h, all_contours_for_svg, all_texts_for_svg)

        return jsonify({
            "quantized_image_b64": quantized_image_b64,
            "line_art_png_b64": line_art_png_b64,
            "line_art_svg_content": line_art_svg_content,
            "bg_removed_char_b64": bg_removed_char_b64,
            "palette_rgb": final_display_palette_rgb, # Use the palette corresponding to the final image content
            "image_width": w,
            "image_height": h
        })

    except Exception as e:
        app.logger.error(f"Error processing image: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)