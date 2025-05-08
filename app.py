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

app = Flask(__name__)
app.register_blueprint(download_bp, url_prefix='/downloads') 

# --- FONT CONFIGURATION (ensure this is working) ---
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
    if FONT and hasattr(FONT, 'path') and FONT.path: # Check if it's a truetype font with a path
        try:
            return ImageFont.truetype(FONT.path, size)
        except IOError:
            print(f"Warning: Could not reload font {FONT.path} at size {size}. Falling back.")
            return FONT # Fallback to default size if custom size fails
    elif FONT: # If it's the default Pillow font
        return FONT # Default Pillow font doesn't support easy resizing this way
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
        num_colors = int(data.get('numColors', 8))
        font_size_param = int(data.get('fontSize', DEFAULT_FONT_SIZE))

        image_data_bytes = decode_data_url(image_data_url)
        
        pil_image_orig = Image.open(BytesIO(image_data_bytes)).convert("RGBA")
        img_np_rgba = np.array(pil_image_orig)
        
        original_alpha = None
        if img_np_rgba.shape[2] == 4:
            original_alpha = img_np_rgba[:, :, 3].copy()
            img_np_rgb = img_np_rgba[:, :, :3]
        else:
            img_np_rgb = img_np_rgba
            if len(img_np_rgb.shape) == 2:
                 img_np_rgb = cv2.cvtColor(img_np_rgb, cv2.COLOR_GRAY2RGB)

        img_cv_bgr = cv2.cvtColor(img_np_rgb, cv2.COLOR_RGB2BGR)
        h, w = img_cv_bgr.shape[:2]

        pixels = img_cv_bgr.reshape((-1, 3))
        pixels = np.float32(pixels)
        
        kmeans = KMeans(n_clusters=num_colors, random_state=42, n_init=10, tol=1e-3) # added tol for stability
        kmeans.fit(pixels)
        
        palette_bgr = kmeans.cluster_centers_.astype(np.uint8) # uint8 is better for image data
        labels = kmeans.labels_
        quantized_img_cv_bgr = palette_bgr[labels].reshape((h, w, 3)).astype(np.uint8)
        palette_rgb = [color[::-1].tolist() for color in palette_bgr] # BGR to RGB

        quantized_pil_rgb = opencv_to_pil(quantized_img_cv_bgr)
        quantized_pil_final_rgba = quantized_pil_rgb.convert("RGBA")
        if original_alpha is not None:
            quantized_pil_final_rgba.putalpha(Image.fromarray(original_alpha))
        else:
            alpha_for_quantized = Image.new('L', quantized_pil_final_rgba.size, 255)
            quantized_pil_final_rgba.putalpha(alpha_for_quantized)

        # --- Line Art and Numbering ---
        # Create a white canvas for line art (PNG)
        line_art_pil_for_png = Image.new("RGBA", (w, h), (255, 255, 255, 255)) # Opaque white background for PNG
        draw_png = ImageDraw.Draw(line_art_pil_for_png)
        
        # Create a black and white edge map
        # This will form the basis of our "thinner" lines
        edge_map_cv = np.zeros((h, w), dtype=np.uint8)

        # Iterate through each color region to find its boundaries against OTHERS
        for i in range(num_colors):
            # Mask for the current color
            current_color_mask = cv2.inRange(quantized_img_cv_bgr, palette_bgr[i], palette_bgr[i])
            
            # Dilate this mask slightly to find its immediate neighbors
            dilated_mask = cv2.dilate(current_color_mask, np.ones((3,3), np.uint8), iterations=1)
            
            # Find where the dilated mask is, but the original mask is not (this is the boundary)
            boundary = cv2.subtract(dilated_mask, current_color_mask)
            
            # Add these boundary pixels to our edge_map_cv
            # We only want edges between DIFFERENT colors.
            # So, where 'boundary' is active, check if the pixel in 'quantized_img_cv_bgr'
            # is NOT the current color 'palette_bgr[i]'.
            # This is a bit tricky. A simpler way is to get all contours and draw them thinly.

            # Let's try a Canny edge detector on the quantized image,
            # as it's good at finding edges between distinct regions.
            # Convert quantized to grayscale for Canny
            gray_quantized = cv2.cvtColor(quantized_img_cv_bgr, cv2.COLOR_BGR2GRAY)
            # Apply Canny edge detection. Adjust thresholds as needed.
            # Lower thresholds detect more (potentially noisy) edges.
            # Higher thresholds detect stronger edges.
            edges_cv = cv2.Canny(gray_quantized, threshold1=30, threshold2=100) # Experiment with these values

            # 'edges_cv' is now a binary image with 1-pixel thick edges (mostly)
            # Convert this to a PIL image and draw it onto line_art_pil_for_png
            # Invert Canny output: lines are black (0), background is white (255)
            inverted_edges_cv = cv2.bitwise_not(edges_cv)
            pil_edges = opencv_to_pil(cv2.cvtColor(inverted_edges_cv, cv2.COLOR_GRAY2RGB)).convert("RGBA")

            # Paste the edges onto the white canvas.
            # We need to make white in pil_edges transparent so only black lines are drawn.
            edge_data = pil_edges.getdata()
            newData = []
            for item in edge_data:
                # if black (line), keep it opaque black. if white (background), make it transparent.
                if item[0] == 0 and item[1] == 0 and item[2] == 0: # Black pixel
                    newData.append((0, 0, 0, 255)) # Opaque black
                else: # White pixel or other
                    newData.append((255, 255, 255, 0)) # Transparent
            
            pil_edges_transparent_bg = Image.new("RGBA", pil_edges.size)
            pil_edges_transparent_bg.putdata(newData)
            
            line_art_pil_for_png.paste(pil_edges_transparent_bg, (0,0), pil_edges_transparent_bg)
            
        # --- Number Placement (remains mostly the same logic) ---
        current_font = get_font(font_size_param) or ImageFont.load_default()
        min_contour_area_for_numbering = max(50, font_size_param * font_size_param * 1.0) # Area slightly larger for numbers

        all_contours_for_svg = [] # Still based on original color regions for SVG structure
        all_texts_for_svg = []    

        for i, color_bgr_val in enumerate(palette_bgr):
            mask = cv2.inRange(quantized_img_cv_bgr, np.array(color_bgr_val), np.array(color_bgr_val))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            color_number_str = str(i + 1)

            for contour in contours:
                # For SVG, we still use the full region contours
                if cv2.contourArea(contour) > 10: # Minimal area for SVG paths
                     all_contours_for_svg.append(contour)

                if cv2.contourArea(contour) > min_contour_area_for_numbering:
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        
                        if cv2.pointPolygonTest(contour, (cx, cy), False) >= 0:
                            # Draw number on the line_art_pil_for_png (which now has Canny edges)
                            try:
                                bbox = draw_png.textbbox((cx, cy), color_number_str, font=current_font, anchor="mm")
                                text_x_png = cx - (bbox[2] - bbox[0]) // 2
                                text_y_png = cy - (bbox[3] - bbox[1]) // 2
                                draw_png.text((text_x_png, text_y_png), color_number_str, fill="black", font=current_font)
                            except Exception as e_font:
                                print(f"Error drawing text with Pillow: {e_font}")
                                # Fallback: draw with OpenCV on a temporary canvas if Pillow fails
                                temp_cv_img_for_text = np.array(line_art_pil_for_png.convert("RGB"))
                                temp_cv_img_for_text = cv2.cvtColor(temp_cv_img_for_text, cv2.COLOR_RGB2BGR)
                                cv2.putText(temp_cv_img_for_text, color_number_str, (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, font_size_param / 25.0, (0,0,0), 1, cv2.LINE_AA)
                                line_art_pil_for_png = opencv_to_pil(temp_cv_img_for_text).convert("RGBA")
                                draw_png = ImageDraw.Draw(line_art_pil_for_png) # Re-init draw object
                            
                            all_texts_for_svg.append({'text': color_number_str, 'x': cx, 'y': cy, 'size': font_size_param})
        
        # --- Prepare outputs ---
        bg_removed_colored_char_pil = quantized_pil_final_rgba.copy()

        quantized_image_b64 = image_to_base64(quantized_pil_final_rgba)
        line_art_png_b64 = image_to_base64(line_art_pil_for_png)
        bg_removed_char_b64 = image_to_base64(bg_removed_colored_char_pil)
        line_art_svg_content = generate_svg_content(w, h, all_contours_for_svg, all_texts_for_svg)

        return jsonify({
            "quantized_image_b64": quantized_image_b64,
            "line_art_png_b64": line_art_png_b64,
            "line_art_svg_content": line_art_svg_content,
            "bg_removed_char_b64": bg_removed_char_b64,
            "palette_rgb": palette_rgb,
            "image_width": w,
            "image_height": h
        })

    except Exception as e:
        app.logger.error(f"Error processing image: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)