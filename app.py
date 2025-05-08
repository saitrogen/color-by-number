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
from extensions.region_processing_utils import merge_small_regions # Import the new function

app = Flask(__name__)
app.register_blueprint(download_bp, url_prefix='/downloads') 

# --- FONT CONFIGURATION (ensure this is working correctly on your system) ---
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", # Linux
    "arial.ttf", # Windows (if in PATH or current dir)
    "C:/Windows/Fonts/arial.ttf", # Windows explicit
    "/Library/Fonts/Arial.ttf", # macOS
    "/System/Library/Fonts/Supplemental/Arial.ttf" # macOS
]
DEFAULT_FONT_SIZE = 15
FONT = None
for path in FONT_PATHS:
    try:
        FONT = ImageFont.truetype(path, DEFAULT_FONT_SIZE)
        print(f"Loaded font for main processing: {path}")
        break
    except IOError:
        print(f"Font not found or unreadable: {path}")
        pass
if FONT is None:
    try:
        FONT = ImageFont.load_default()
        print("Warning: Using default Pillow font for main processing.")
    except Exception as e:
        print(f"Could not load default Pillow font: {e}")
        FONT = None

def get_font(size):
    if FONT and hasattr(FONT, 'path') and FONT.path:
        try:
            return ImageFont.truetype(FONT.path, size)
        except IOError:
            print(f"Warning: Could not reload font {FONT.path} at size {size}. Falling back.")
            return FONT 
    elif FONT: 
        return FONT 
    print(f"Warning: No valid font found for size {size}. Text rendering may fail or use system default.")
    return None


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process_image', methods=['POST'])
def process_image_route():
    try:
        data = request.get_json()
        image_data_url = data['imageDataUrl']
        num_colors_requested = int(data.get('numColors', 8)) # Original requested number
        font_size_param = int(data.get('fontSize', DEFAULT_FONT_SIZE))
        merge_regions_flag = data.get('mergeSmallRegions', False)
        min_merge_area_percent = float(data.get('minMergeAreaPercent', 0.1))

        # 1. Decode Image and Prepare Initial OpenCV image
        image_data_bytes = decode_data_url(image_data_url)
        pil_image_orig = Image.open(BytesIO(image_data_bytes)).convert("RGBA")
        img_np_rgba = np.array(pil_image_orig)
        
        original_alpha = None
        if img_np_rgba.shape[2] == 4:
            original_alpha = img_np_rgba[:, :, 3].copy()
            img_np_rgb = img_np_rgba[:, :, :3]
        else:
            img_np_rgb = img_np_rgba
            if len(img_np_rgb.shape) == 2: # Grayscale to RGB
                 img_np_rgb = cv2.cvtColor(img_np_rgb, cv2.COLOR_GRAY2RGB)

        img_cv_bgr = cv2.cvtColor(img_np_rgb, cv2.COLOR_RGB2BGR)
        h, w = img_cv_bgr.shape[:2]

        # 2. Initial Color Quantization
        pixels = img_cv_bgr.reshape((-1, 3))
        pixels = np.float32(pixels)
        
        # Ensure num_colors_requested is at least 2 for KMeans
        actual_num_colors_for_kmeans = max(2, num_colors_requested)
        
        kmeans = KMeans(n_clusters=actual_num_colors_for_kmeans, random_state=42, n_init=10, tol=1e-3)
        kmeans.fit(pixels)
        
        palette_bgr = kmeans.cluster_centers_.astype(np.uint8)
        labels = kmeans.labels_
        quantized_img_cv_bgr = palette_bgr[labels].reshape((h, w, 3)).astype(np.uint8)
        # palette_rgb will be derived after potential merging

        # 3. Optional: Merge Small Regions
        if merge_regions_flag:
            print(f"Attempting to merge small regions with threshold {min_merge_area_percent}%...")
            quantized_img_cv_bgr, palette_bgr_merged = merge_small_regions(
                quantized_img_cv_bgr.copy(), # Pass a copy to avoid modifying original before this step
                palette_bgr.copy(), 
                min_area_threshold_percent=min_merge_area_percent
            )
            palette_bgr = np.array(palette_bgr_merged, dtype=np.uint8) # Update main palette
            print(f"Regions merged. New palette size: {len(palette_bgr)}")
        
        # Final palette_rgb based on palette_bgr (which might have been updated by merging)
        palette_rgb = [color[::-1].tolist() for color in palette_bgr]

        # 4. Prepare Quantized Image with Alpha (for "Colored Preview" and "BG Removed")
        # This uses the (potentially merged) quantized_img_cv_bgr
        quantized_pil_rgb_final = opencv_to_pil(quantized_img_cv_bgr)
        quantized_pil_final_rgba = quantized_pil_rgb_final.convert("RGBA")
        if original_alpha is not None:
            quantized_pil_final_rgba.putalpha(Image.fromarray(original_alpha))
        else:
            alpha_for_quantized = Image.new('L', quantized_pil_final_rgba.size, 255)
            quantized_pil_final_rgba.putalpha(alpha_for_quantized)
        
        # This is also the "BG Removed Character" if original_alpha was present
        bg_removed_colored_char_pil = quantized_pil_final_rgba.copy()


        # 5. Generate Line Art (PNG) using Canny Edges
        line_art_pil_for_png = Image.new("RGBA", (w, h), (255, 255, 255, 255)) # Opaque white background
        # Canny edge detection on the (potentially merged) quantized image
        gray_quantized = cv2.cvtColor(quantized_img_cv_bgr, cv2.COLOR_BGR2GRAY)
        # Optional: Blur before Canny
        # gray_quantized_blurred = cv2.GaussianBlur(gray_quantized, (3,3), 0)
        # edges_cv = cv2.Canny(gray_quantized_blurred, threshold1=30, threshold2=100)
        edges_cv = cv2.Canny(gray_quantized, threshold1=30, threshold2=100) # Experiment with thresholds

        inverted_edges_cv = cv2.bitwise_not(edges_cv) # Lines black, bg white
        pil_edges_rgb = opencv_to_pil(cv2.cvtColor(inverted_edges_cv, cv2.COLOR_GRAY2RGB))
        
        edge_data = pil_edges_rgb.getdata()
        newData = []
        for item in edge_data:
            if item[0] == 0 and item[1] == 0 and item[2] == 0: # Black line
                newData.append((0, 0, 0, 255)) # Opaque black
            else: # White background from Canny output
                newData.append((255, 255, 255, 0)) # Transparent (so it doesn't overwrite existing white canvas)
        
        pil_edges_transparent_bg = Image.new("RGBA", pil_edges_rgb.size)
        pil_edges_transparent_bg.putdata(newData)
        
        # Paste Canny edges onto the white line art canvas
        line_art_pil_for_png.paste(pil_edges_transparent_bg, (0,0), pil_edges_transparent_bg)
        draw_png = ImageDraw.Draw(line_art_pil_for_png) # Initialize Draw object for numbers


        # 6. Number Placement (on the Canny line art)
        current_font = get_font(font_size_param) or ImageFont.load_default()
        min_contour_area_for_numbering = max(50, font_size_param * font_size_param * 1.0)

        all_contours_for_svg = [] # For SVG structure (based on color regions)
        all_texts_for_svg = []    

        # Iterate over the final palette_bgr (which may have been reduced by merging)
        for i, color_bgr_val in enumerate(palette_bgr):
            # Get mask and contours from the final (potentially merged) quantized_img_cv_bgr
            mask = cv2.inRange(quantized_img_cv_bgr, np.array(color_bgr_val), np.array(color_bgr_val))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            color_number_str = str(i + 1) # Numbers correspond to the final palette order

            for contour in contours:
                # For SVG paths, use contours of color regions
                if cv2.contourArea(contour) > 10: 
                     all_contours_for_svg.append(contour.copy()) # Use a copy

                if cv2.contourArea(contour) > min_contour_area_for_numbering:
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        
                        dist_to_edge = cv2.pointPolygonTest(contour, (float(cx), float(cy)), True)
                        tx, ty = cx, cy
                        font_size_for_check = font_size_param

                        if dist_to_edge < font_size_for_check * 0.5:
                            x_br, y_br, w_br, h_br = cv2.boundingRect(contour)
                            alt_tx, alt_ty = x_br + w_br // 2, y_br + h_br // 2
                            alt_dist_to_edge = cv2.pointPolygonTest(contour, (float(alt_tx), float(alt_ty)), True)
                            if alt_dist_to_edge > dist_to_edge and alt_dist_to_edge > font_size_for_check * 0.3:
                                tx, ty = alt_tx, alt_ty
                                dist_to_edge = alt_dist_to_edge
                        
                        if dist_to_edge > - (font_size_for_check * 0.2):
                            try:
                                bbox = draw_png.textbbox((tx, ty), color_number_str, font=current_font, anchor="mm")
                                text_x_png = tx - (bbox[2] - bbox[0]) // 2
                                text_y_png = ty - (bbox[3] - bbox[1]) // 2
                                draw_png.text((text_x_png, text_y_png), color_number_str, fill="black", font=current_font)
                                all_texts_for_svg.append({'text': color_number_str, 'x': tx, 'y': ty, 'size': font_size_param})
                            except Exception as e_font:
                                print(f"Error drawing text with Pillow: {e_font}")
                                # Fallback drawing text with OpenCV
                                temp_cv_img_for_text_np = np.array(line_art_pil_for_png.convert("RGB")) # Work on a copy
                                temp_cv_img_for_text_np = cv2.cvtColor(temp_cv_img_for_text_np, cv2.COLOR_RGB2BGR)
                                cv2.putText(temp_cv_img_for_text_np, color_number_str, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, font_size_param / 25.0, (0,0,0), 1, cv2.LINE_AA)
                                line_art_pil_for_png = opencv_to_pil(temp_cv_img_for_text_np).convert("RGBA") # Update main PIL image
                                draw_png = ImageDraw.Draw(line_art_pil_for_png) # Re-initialize Draw object on updated image
                                all_texts_for_svg.append({'text': color_number_str, 'x': tx, 'y': ty, 'size': font_size_param})
                        else:
                            print(f"Skipping number for region {color_number_str} (color {color_bgr_val}) as no good placement. Area: {cv2.contourArea(contour):.0f}, Dist: {dist_to_edge:.1f}")
        
        # 7. Prepare Final Outputs
        quantized_image_b64 = image_to_base64(quantized_pil_final_rgba)
        line_art_png_b64 = image_to_base64(line_art_pil_for_png)
        bg_removed_char_b64 = image_to_base64(bg_removed_colored_char_pil)
        line_art_svg_content = generate_svg_content(w, h, all_contours_for_svg, all_texts_for_svg)

        return jsonify({
            "quantized_image_b64": quantized_image_b64,
            "line_art_png_b64": line_art_png_b64,
            "line_art_svg_content": line_art_svg_content,
            "bg_removed_char_b64": bg_removed_char_b64,
            "palette_rgb": palette_rgb, # Final palette
            "image_width": w,
            "image_height": h
        })

    except Exception as e:
        app.logger.error(f"Error processing image: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)