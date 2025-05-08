
from flask import Flask, request, jsonify, render_template
import cv2
import numpy as np
from sklearn.cluster import KMeans
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

# --- Configuration ---
# Attempt to load a commonly available font. Adjust path if needed.
# On Linux, common paths: /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
# On Windows: C:\Windows\Fonts\arial.ttf
# On macOS: /Library/Fonts/Arial.ttf or /System/Library/Fonts/Supplemental/Arial.ttf
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", # Common on Linux
    "arial.ttf", # Common on Windows (often found in system path or current dir)
    "/Library/Fonts/Arial.ttf", # Common on macOS
    "/System/Library/Fonts/Supplemental/Arial.ttf" # Another macOS location
]
DEFAULT_FONT_SIZE = 15
FONT = None

for path in FONT_PATHS:
    try:
        FONT = ImageFont.truetype(path, DEFAULT_FONT_SIZE)
        print(f"Loaded font: {path}")
        break
    except IOError:
        print(f"Could not load font: {path}")

if FONT is None:
    print("Warning: Could not load any specified fonts. Using Pillow's default font, which might be small.")
    try:
        FONT = ImageFont.load_default() # Fallback to Pillow's default
    except Exception as e:
        print(f"Could not load default Pillow font: {e}")
        # As a last resort, text drawing might fail or use a very basic internal font
        FONT = None


def get_font(size):
    if FONT and hasattr(FONT, 'path'): # Check if it's a truetype font with a path
        try:
            return ImageFont.truetype(FONT.path, size)
        except IOError:
            return FONT # Fallback to default size if custom size fails
    elif FONT: # If it's the default Pillow font
        return FONT # Default Pillow font doesn't support easy resizing this way
    return None

def image_to_base64(img_pil):
    buffered = BytesIO()
    img_pil.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def opencv_to_pil(opencv_image):
    # OpenCV uses BGR, Pillow uses RGB
    color_converted = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2RGB)
    return Image.fromarray(color_converted)

def pil_to_opencv(pil_image):
    # Pillow uses RGB, OpenCV uses BGR
    numpy_image = np.array(pil_image)
    return cv2.cvtColor(numpy_image, cv2.COLOR_RGB2BGR)

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

        # Decode base64 image
        header, encoded = image_data_url.split(",", 1)
        image_data_bytes = base64.b64decode(encoded)
        
        # Read image with Pillow to handle transparency better initially
        pil_image_orig = Image.open(BytesIO(image_data_bytes)).convert("RGBA")
        img_np_rgba = np.array(pil_image_orig)
        
        # Separate alpha channel if present
        alpha_channel = None
        if img_np_rgba.shape[2] == 4:
            alpha_channel = img_np_rgba[:, :, 3]
            img_np_rgb = img_np_rgba[:, :, :3] # Work with RGB for quantization
        else:
            img_np_rgb = img_np_rgba # Already RGB or Grayscale (will be converted to RGB)
            if len(img_np_rgb.shape) == 2: # Grayscale
                 img_np_rgb = cv2.cvtColor(img_np_rgb, cv2.COLOR_GRAY2RGB)


        # OpenCV image (for processing, OpenCV uses BGR)
        img_cv = cv2.cvtColor(img_np_rgb, cv2.COLOR_RGB2BGR)
        
        h, w = img_cv.shape[:2]

        # 1. Color Quantization using K-Means
        pixels = img_cv.reshape((-1, 3))
        pixels = np.float32(pixels)
        
        kmeans = KMeans(n_clusters=num_colors, random_state=42, n_init=10)
        kmeans.fit(pixels)
        
        palette_bgr = kmeans.cluster_centers_.astype(int)
        labels = kmeans.labels_
        
        quantized_img_cv_bgr = palette_bgr[labels].reshape((h, w, 3)).astype(np.uint8)

        # Convert palette to RGB for frontend
        palette_rgb = [color[::-1].tolist() for color in palette_bgr] # BGR to RGB

        # Create PIL version of quantized image (for drawing text)
        quantized_pil_rgb = opencv_to_pil(quantized_img_cv_bgr)
        
        # If original had alpha, re-apply it or make a new one
        if alpha_channel is not None:
            quantized_pil_rgba = quantized_pil_rgb.convert("RGBA")
            quantized_pil_rgba.putalpha(Image.fromarray(alpha_channel))
        else:
            quantized_pil_rgba = quantized_pil_rgb.convert("RGBA") # Ensure it has an alpha channel


        # 2. Generate Line Art and Numbers
        line_art_pil = Image.new("RGBA", (w, h), (255, 255, 255, 0)) # Transparent background
        draw = ImageDraw.Draw(line_art_pil)
        current_font = get_font(font_size_param) or ImageFont.load_default() # Fallback if custom fails

        min_contour_area = max(50, font_size_param * font_size_param * 0.5) # Adjust as needed

        processed_regions_for_color = [False] * num_colors

        for i, color_bgr in enumerate(palette_bgr):
            # Create a mask for the current color in the quantized BGR image
            lower_bound = np.array(color_bgr, dtype=np.uint8)
            upper_bound = np.array(color_bgr, dtype=np.uint8)
            mask = cv2.inRange(quantized_img_cv_bgr, lower_bound, upper_bound)
            
            # Find contours
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            color_number = i + 1

            for contour in contours:
                if cv2.contourArea(contour) > min_contour_area: # Filter small regions
                    # Draw contour lines (black)
                    cv2.drawContours(img_cv, [contour], -1, (0,0,0), 1) # Draw on a copy for line art only
                    
                    # Draw contour on PIL line_art_pil (which is RGBA)
                    # For PIL, contour points need to be a flat list of (x,y) tuples
                    pil_contour_points = [tuple(p[0]) for p in contour]
                    if len(pil_contour_points) > 1: # Need at least 2 points to draw a line
                        draw.line(pil_contour_points + [pil_contour_points[0]], fill="black", width=1)

                    # Find a point to place the number (centroid)
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        
                        # Check if point is inside contour (helps with C-shapes)
                        # and far enough from edges
                        if cv2.pointPolygonTest(contour, (cx, cy), False) >= 0:
                             # Draw number text on PIL image
                            text = str(color_number)
                            bbox = draw.textbbox((cx, cy), text, font=current_font, anchor="mm")
                            text_width = bbox[2] - bbox[0]
                            text_height = bbox[3] - bbox[1]
                            
                            # Center text
                            text_x = cx - text_width // 2
                            text_y = cy - text_height // 2
                            
                            draw.text((text_x, text_y), text, fill="black", font=current_font)


        # Convert final images to base64
        quantized_image_b64 = image_to_base64(quantized_pil_rgba)
        line_art_image_b64 = image_to_base64(line_art_pil)

        return jsonify({
            "quantized_image_b64": quantized_image_b64,
            "line_art_image_b64": line_art_image_b64,
            "palette_rgb": palette_rgb
        })

    except Exception as e:
        app.logger.error(f"Error processing image: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)