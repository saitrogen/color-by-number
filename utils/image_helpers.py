# color_by_number_app/utils/image_helpers.py
import base64
from io import BytesIO
from PIL import Image
import numpy as np
import cv2

def image_to_base64(img_pil, format="PNG"):
    buffered = BytesIO()
    img_pil.save(buffered, format=format)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def opencv_to_pil(opencv_image):
    color_converted = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2RGB)
    return Image.fromarray(color_converted)

def pil_to_opencv(pil_image):
    numpy_image = np.array(pil_image)
    if pil_image.mode == 'RGBA':
        return cv2.cvtColor(numpy_image, cv2.COLOR_RGBA2BGRA)
    elif pil_image.mode == 'RGB':
        return cv2.cvtColor(numpy_image, cv2.COLOR_RGB2BGR)
    else: # Grayscale etc.
        return cv2.cvtColor(numpy_image, cv2.COLOR_GRAY2BGR) # Or handle other modes

def decode_data_url(data_url_string):
    header, encoded = data_url_string.split(",", 1)
    image_data_bytes = base64.b64decode(encoded)
    return image_data_bytes