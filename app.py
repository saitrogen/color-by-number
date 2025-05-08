# color_by_number_app/app.py
from flask import Flask, request, jsonify, render_template
import cv2
import numpy as np
from sklearn.cluster import KMeans
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# Local imports
from utils.image_helpers import image_to_base64, opencv_to_pil, pil_to_opencv, decode_data_url
from extensions.download_utils import download_bp, generate_svg_content # Import the blueprint and SVG generator

app = Flask(__name__)
app.register_blueprint(download_bp, url_prefix='/downloads') # Register blueprint

# --- FONT CONFIGURATION ---
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "arial.ttf",
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
        print("Warning: Using default Pillow font for main processing.")
    except Exception as e:
        print(f"Could not load default Pillow font: {e}")
        FONT = None

def get_font(size):
    if FONT and hasattr(FONT, 'path'):
        try:
            return ImageFont.truetype(FONT.path, size)
        except IOError:
            return FONT
    elif FONT:
        return FONT
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

        image_data_bytes = decode_data_url(image_data_url)
        
        pil_image_orig = Image.open(BytesIO(image_data_bytes)).convert("RGBA")
        img_np_rgba = np.array(pil_image_orig)
        
        original_alpha = None
        if img_np_rgba.shape[2] == 4:
            original_alpha = img_np_rgba[:, :, 3].copy() # Make a copy
            img_np_rgb = img_np_rgba[:, :, :3]
        else:
            img_np_rgb = img_np_rgba
            if len(img_np_rgb.shape) == 2:
                 img_np_rgb = cv2.cvtColor(img_np_rgb, cv2.COLOR_GRAY2RGB)

        img_cv_bgr = cv2.cvtColor(img_np_rgb, cv2.COLOR_RGB2BGR)
        h, w = img_cv_bgr.shape[:2]

        pixels = img_cv_bgr.reshape((-1, 3))
        pixels = np.float32(pixels)
        
        kmeans = KMeans(n_clusters=num_colors, random_state=42, n_init=10)
        kmeans.fit(pixels)
        
        palette_bgr = kmeans.cluster_centers_.astype(int)
        labels = kmeans.labels_
        quantized_img_cv_bgr = palette_bgr[labels].reshape((h, w, 3)).astype(np.uint8)
        palette_rgb = [color[::-1].tolist() for color in palette_bgr]

        # --- For Quantized Image with original Alpha ---
        quantized_pil_rgb = opencv_to_pil(quantized_img_cv_bgr)
        quantized_pil_final_rgba = quantized_pil_rgb.convert("RGBA")
        if original_alpha is not None:
            quantized_pil_final_rgba.putalpha(Image.fromarray(original_alpha))
        else: # Ensure it has full alpha if no original alpha
            alpha_for_quantized = Image.new('L', quantized_pil_final_rgba.size, 255)
            quantized_pil_final_rgba.putalpha(alpha_for_quantized)


        # --- Line Art and Numbering ---
        line_art_pil_for_png = Image.new("RGBA", (w, h), (255, 255, 255, 0)) # Transparent for PNG
        draw_png = ImageDraw.Draw(line_art_pil_for_png)
        current_font = get_font(font_size_param) or ImageFont.load_default()
        min_contour_area = max(50, font_size_param * font_size_param * 0.5)

        all_contours_for_svg = [] # Store contours for SVG
        all_texts_for_svg = []    # Store text elements for SVG

        for i, color_bgr_val in enumerate(palette_bgr):
            mask = cv2.inRange(quantized_img_cv_bgr, np.array(color_bgr_val), np.array(color_bgr_val))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            color_number_str = str(i + 1)

            for contour in contours:
                if cv2.contourArea(contour) > min_contour_area:
                    all_contours_for_svg.append(contour) # Add to list for SVG

                    # Draw contour on PIL line_art_pil (for PNG)
                    pil_contour_points = [tuple(p[0]) for p in contour]
                    if len(pil_contour_points) > 1:
                        draw_png.line(pil_contour_points + [pil_contour_points[0]], fill="black", width=1)

                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        
                        if cv2.pointPolygonTest(contour, (cx, cy), False) >= 0:
                            # For PNG
                            bbox = draw_png.textbbox((cx, cy), color_number_str, font=current_font, anchor="mm")
                            text_x_png = cx - (bbox[2] - bbox[0]) // 2
                            text_y_png = cy - (bbox[3] - bbox[1]) // 2
                            draw_png.text((text_x_png, text_y_png), color_number_str, fill="black", font=current_font)
                            
                            # For SVG
                            all_texts_for_svg.append({'text': color_number_str, 'x': cx, 'y': cy, 'size': font_size_param})
        
        # --- Generate "Background Removed" Colored Character ---
        # This assumes the original alpha channel defines the character.
        # If original_alpha is None, this will be the full quantized image.
        bg_removed_colored_char_pil = quantized_pil_final_rgba.copy() # Already has alpha applied

        # --- Prepare outputs ---
        quantized_image_b64 = image_to_base64(quantized_pil_final_rgba)
        line_art_png_b64 = image_to_base64(line_art_pil_for_png)
        bg_removed_char_b64 = image_to_base64(bg_removed_colored_char_pil)

        # Generate SVG content string (can be large, consider if it should be a separate request)
        line_art_svg_content = generate_svg_content(w, h, all_contours_for_svg, all_texts_for_svg)


        return jsonify({
            "quantized_image_b64": quantized_image_b64,
            "line_art_png_b64": line_art_png_b64,
            "line_art_svg_content": line_art_svg_content, # Send SVG content directly
            "bg_removed_char_b64": bg_removed_char_b64,
            "palette_rgb": palette_rgb,
            "image_width": w, # For client-side SVG download if needed
            "image_height": h
        })

    except Exception as e:
        app.logger.error(f"Error processing image: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)