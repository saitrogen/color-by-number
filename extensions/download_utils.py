# color_by_number_app/extensions/download_utils.py
from flask import Blueprint, Response, jsonify, request
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
from io import BytesIO
import base64
from utils.image_helpers import decode_data_url, opencv_to_pil, pil_to_opencv # Assuming image_helpers.py is in a 'utils' directory

# --- FONT CONFIGURATION (can be shared or moved to a config file) ---
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf"
]
DEFAULT_FONT_SIZE_SVG = 15 # Can be different for SVG
FONT_SVG = None
for path in FONT_PATHS:
    try:
        FONT_SVG = ImageFont.truetype(path, DEFAULT_FONT_SIZE_SVG) # Used for text metrics
        print(f"Loaded font for SVG metrics: {path}")
        break
    except IOError:
        pass
if FONT_SVG is None:
    try:
        FONT_SVG = ImageFont.load_default()
        print("Warning: Using default Pillow font for SVG text metrics.")
    except Exception:
        FONT_SVG = None # No font, metrics will be rough estimates


download_bp = Blueprint('download_utils', __name__)

def get_font_for_svg_metrics(size):
    if FONT_SVG and hasattr(FONT_SVG, 'path'):
        try:
            return ImageFont.truetype(FONT_SVG.path, size)
        except IOError:
            return FONT_SVG
    elif FONT_SVG:
        return FONT_SVG
    return None

def contours_to_svg_paths(contours, stroke_color="black", stroke_width=1):
    paths = []
    for contour in contours:
        if len(contour) < 2: continue # Need at least 2 points for a path
        path_data = "M " + " ".join(f"{p[0][0]},{p[0][1]}" for p in contour) + " Z" # Z to close path
        paths.append(f'<path d="{path_data}" stroke="{stroke_color}" stroke-width="{stroke_width}" fill="none" />')
    return "\n".join(paths)

def generate_svg_content(width, height, contours_data, texts_data, font_family="Arial, sans-serif"):
    """
    Generates SVG content.
    contours_data: list of contour arrays (from cv2.findContours)
    texts_data: list of dicts e.g. [{'text': '1', 'x': 50, 'y': 50, 'size': 12}]
    """
    svg_paths = contours_to_svg_paths(contours_data)
    
    svg_texts = []
    for t_data in texts_data:
        # Simple centering for SVG text, might need refinement
        # For more accurate SVG text placement, consider using text-anchor="middle" and dominant-baseline="middle"
        # However, x,y in SVG <text> typically refers to the bottom-left of the first char by default.
        # We will use x,y as the center from OpenCV and adjust with dominant-baseline and text-anchor.
        svg_texts.append(
            f'<text x="{t_data["x"]}" y="{t_data["y"]}" font-family="{font_family}" font-size="{t_data["size"]}" '
            f'fill="black" text-anchor="middle" dominant-baseline="middle">{t_data["text"]}</text>'
        )
    
    svg_content = f"""<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
    <rect width="100%" height="100%" fill="white"/> <!-- Optional white background -->
    {svg_paths}
    {("".join(svg_texts))}
</svg>"""
    return svg_content


# Note: The main processing logic (quantization, contour finding) will still be in app.py
# This blueprint will primarily handle requests related to formatting and downloading
# processed data. For simplicity, if we pass the processed data (contours, texts)
# to these endpoints, it can work.

# If you want to re-run parts of the processing (e.g., just generate SVG from existing quantized data),
# then these functions would need access to more intermediate data or re-run parts of the pipeline.
# For now, let's assume the main `process_image` in `app.py` calculates everything needed.
# The frontend will then make separate requests for downloads, passing necessary identifiers or data.

# This is a placeholder. Ideally, you'd store intermediate results (like contours and text positions)
# from the main processing step and retrieve them here, or pass them directly from the client
# if they are small enough.
# For now, we'll just make it an example that it could be called.
# A more robust solution involves session storage or temporary file storage for processed data.

@download_bp.route('/download_svg', methods=['POST'])
def download_svg():
    data = request.get_json()
    # These would ideally come from a stored processing result or be re-calculated
    # For this example, we'll assume they are passed (which is not ideal for large data)
    # Or, this endpoint would re-run the contour and text finding part if needed
    # based on the original image and parameters.

    # Simplified: Assume client sends necessary data for SVG generation
    # This is NOT how it should be in a final app for efficiency.
    # This data should ideally be retrieved from app.py's processing.
    width = data.get('width')
    height = data.get('height')
    # contours_data and texts_data would be complex to send from client.
    # This endpoint demonstrates SVG generation.
    # A better flow: process_image in app.py saves contours and texts.
    # Client gets a session_id. Download endpoints use session_id to get data.

    # For now, let's just return a dummy SVG for the structure.
    dummy_contours = [np.array([[[10,10]],[[100,10]],[[100,100]],[[10,100]]], dtype=np.int32)]
    dummy_texts = [{'text':'1', 'x':55, 'y':55, 'size':15}]
    
    svg_string = generate_svg_content(width or 300, height or 300, dummy_contours, dummy_texts)

    return Response(
        svg_string,
        mimetype="image/svg+xml",
        headers={"Content-disposition": "attachment; filename=color_by_number.svg"}
    )

# PNG download is simpler as it's often just returning a base64 decoded image
@download_bp.route('/download_png', methods=['POST'])
def download_png():
    data = request.get_json()
    image_b64 = data.get('imageDataB64') # Base64 string of the PNG
    filename = data.get('filename', 'image.png')

    if not image_b64:
        return jsonify({"error": "No image data provided"}), 400

    try:
        # The image_b64 should be just the data part, without "data:image/png;base64,"
        if ',' in image_b64:
            header, image_b64 = image_b64.split(",", 1)

        image_bytes = base64.b64decode(image_b64)
        
        return Response(
            BytesIO(image_bytes), # Flask Response can take a file-like object
            mimetype="image/png",
            headers={"Content-disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        print(f"Error decoding/sending PNG: {e}")
        return jsonify({"error": "Failed to process PNG data"}), 500