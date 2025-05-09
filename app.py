# color_by_number_app/app.py

from flask import Flask, request, jsonify, render_template
from PIL import Image , ImageFont 
from io import BytesIO
import uuid
import time 

from utils.image_helpers import decode_data_url 
from extensions.download_utils import download_bp 
from extensions.core_processing import process_image_pipeline, ProcessCancelledError


CANCELLED_TASKS = {}
app = Flask(__name__)
app.register_blueprint(download_bp, url_prefix='/downloads')

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 
    "arial.ttf", "C:\\Windows\\Fonts\\arial.ttf", 
    "/Library/Fonts/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"
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
        FONT = ImageFont.load_default(); 
        print("Warning: Using default Pillow font.")
    except Exception as e: 
        print(f"Critical: No fonts loadable: {e}"); 
        FONT = None

def get_font_for_core(size): 
    if FONT and hasattr(FONT, 'path') and FONT.path:
        try: return ImageFont.truetype(FONT.path, size)
        except IOError: return FONT
    elif FONT: return FONT
    return None

def check_if_cancelled(task_id):
    return CANCELLED_TASKS.get(task_id, False)

@app.route('/cancel_task/<task_id>', methods=['POST'])
def cancel_task_route(task_id):
    if task_id:
        CANCELLED_TASKS[task_id] = True
        print(f"Task {task_id} marked for cancellation by API call.")
        return jsonify({"message": f"Task {task_id} cancellation requested."}), 200
    return jsonify({"error": "No task_id provided"}), 400

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process_image', methods=['POST'])
def process_image_route():
    task_id = str(uuid.uuid4())
    CANCELLED_TASKS[task_id] = False
    
    processing_log_from_core = []
    def log_to_list(message): 
        print(f"[Task {task_id}] {message}") 
        processing_log_from_core.append(message)

    try:
        log_to_list("App: Received image processing request.")
        params = request.get_json() 
        log_to_list(f"App: Raw params from client: {params}") # <<<<< DEBUGGING LINE

        if not params: # Handle case where JSON might be malformed or empty
            log_to_list("App: Error - No JSON data received in request.")
            return jsonify({"error": "No JSON data received", "log": processing_log_from_core}), 400
        
        image_data_url = params.get('imageDataUrl') # Use .get() for safety
        if not image_data_url:
            log_to_list("App: Error - 'imageDataUrl' missing in request.")
            return jsonify({"error": "'imageDataUrl' is missing", "log": processing_log_from_core}), 400

        image_data_bytes = decode_data_url(image_data_url)
        pil_image_orig_rgba = Image.open(BytesIO(image_data_bytes)).convert("RGBA")

        log_to_list("App: Handing off to core processing pipeline...")

        pipeline_results = process_image_pipeline(
            pil_image_orig_rgba,
            params, 
            task_id,
            check_if_cancelled, 
            log_to_list,        
            get_font_for_core   
        )
        log_to_list("App: Core processing pipeline finished.")

        output_prefs = params.get('outputs', {}) # Use .get() for safety
        response_data = {
            "palette_rgb": pipeline_results.get("palette_rgb"),
            "image_width": pipeline_results.get("image_width"),
            "image_height": pipeline_results.get("image_height"),
            "log": processing_log_from_core,
            "task_id": task_id
        }

        if pipeline_results.get("quantized_image_b64"):
            response_data["quantized_image_b64"] = pipeline_results.get("quantized_image_b64")
            response_data["bg_removed_char_b64"] = pipeline_results.get("bg_removed_char_b64")

        if pipeline_results.get("line_art_png_b64"):
            response_data["line_art_png_b64"] = pipeline_results.get("line_art_png_b64")
        
        if pipeline_results.get("line_art_svg_content"):
            response_data["line_art_svg_content"] = pipeline_results.get("line_art_svg_content")
        
        return jsonify(response_data)

    except ProcessCancelledError as pce:
        log_to_list(f"App: Process cancelled: {str(pce)}")
        return jsonify({"error": str(pce), "status": "cancelled", "log": processing_log_from_core}), 499
    except Exception as e:
        log_message_fallback = lambda msg: print(f"[Task {task_id} Fallback Log] {msg}")
        current_log_ref = processing_log_from_core if 'processing_log_from_core' in locals() and processing_log_from_core is not None else []
        error_message = f"App: Error processing image: {str(e)}"
        if current_log_ref is not None: 
            current_log_ref.append(error_message)
        else: 
            log_message_fallback(error_message)
        
        app.logger.error(f"[Task {task_id}] Error in /process_image: {e}", exc_info=True) # More detailed server log
        return jsonify({"error": str(e), "log": current_log_ref}), 500
    finally:
        if task_id in CANCELLED_TASKS:
            del CANCELLED_TASKS[task_id]
            print(f"Task {task_id} cleaned up from CANCELLED_TASKS.")

if __name__ == '__main__':
    app.run(debug=True)