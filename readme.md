
## Setup and Installation

1.  **Clone the Repository:**
    ```bash
    git clone <https://github.com/saitrogen/color-by-number>
    cd color_by_number_app
    ```

2.  **Create and Activate a Python Virtual Environment:**
    (Recommended to keep dependencies isolated)
    ```bash
    python -m venv venv
    ```
    *   On Windows:
        ```bash
        venv\Scripts\activate
        ```
    *   On macOS/Linux:
        ```bash
        source venv/bin/activate
        ```

3.  **Install Dependencies:**
    Make sure you have Python 3 and pip installed.
    ```bash
    pip install -r requirements.txt
    ```
    This will install Flask, OpenCV, Scikit-learn, Pillow, NumPy, and their dependencies as specified in `requirements.txt`.

    *Note on Fonts:* The application attempts to load common system fonts (like DejaVu Sans or Arial) for drawing numbers. If you encounter issues with text rendering or see warnings about fonts not being found, ensure one of these fonts is installed on your system, or modify the `FONT_PATHS` list in `app.py` to point to a valid `.ttf` font file.

4.  **Run the Flask Application:**
    ```bash
    python app.py
    ```

5.  **Access the Application:**
    Open your web browser and navigate to `http://127.0.0.1:5000/`.

## How to Use

1.  **Upload an Image:** Click the "Upload Image" button and select an image file (PNG with transparency is recommended if you want the "BG Removed Character" to work as expected based on original alpha). A small preview of the uploaded image will appear.
2.  **Configure Settings:**
    *   **Number of Colors:** Choose how many dominant colors the final image should have. Fewer colors mean a simpler result.
    *   **Line Detail:** Select "Low," "Medium," or "High" to influence the Canny edge detection thresholds for line art generation.
    *   **Number Font Size:** Set the desired size for the numbers placed on the line art.
    *   **(Advanced) Merge small regions:**
        *   Check the box to enable this feature.
        *   If enabled, set the "Min area to keep (%)": Regions smaller than this percentage of the total image area will be merged into their neighbors.
3.  **Generate:** Click the "Generate Color by Number" button.
4.  **View Outputs:**
    *   **Colored Preview:** Shows the image reduced to the specified (or resulting, if merged) number of colors.
    *   **BG Removed Character:** If the original image had an alpha channel, this shows the colored character with that transparency preserved. Otherwise, it will be similar to the Colored Preview.
    *   **Line Art with Numbers:** Displays the generated line art with numbers and the corresponding color legend.
5.  **Download:** Use the download buttons beneath each output to save the images as PNG or SVG (for line art).

## Workflow Overview

1.  **Client-Side (Browser):**
    *   User uploads an image and sets parameters.
    *   Image data (as base64) and settings are sent to the Flask backend via a `fetch` POST request.
2.  **Server-Side (Python/Flask):**
    *   Receives the image and parameters.
    *   **Initial Color Quantization:** Reduces image colors using K-Means.
    *   **(Optional) Region Merging:** If enabled, identifies and merges small color regions into larger neighbors, updating the image and effective color palette.
    *   **Line Art Generation:** Applies Canny edge detection to the (potentially merged) quantized image to create thin lines.
    *   **Number Placement:** Calculates positions (improved centroid logic) within each final color region and prepares number data.
    *   **Output Preparation:** Generates base64 encoded PNGs for previews and the line art, and an SVG string for the line art structure.
    *   Sends all processed data back to the client as a JSON response.
3.  **Client-Side (Browser):**
    *   Receives the JSON response.
    *   Displays the generated images and the color legend.
    *   Enables download buttons, which use JavaScript to trigger file downloads from the received data.

## Potential Future Improvements

*   **More Sophisticated Background Removal:** Implement options for user-selected background color removal or integrate a dedicated background removal library (e.g., `transparent-background`).
*   **Advanced Number Placement:** Explore algorithms like "Pole of Inaccessibility" for more optimal number positioning within complex shapes.
*   **Interactive Canny Threshold Adjustment:** Allow users to fine-tune Canny thresholds with sliders and a live preview of the line art.
*   **Vectorized SVG Line Art:** Implement true vectorization of the Canny edges (e.g., using a `potrace` wrapper) for scalable SVG line art.
*   **User-Selectable Font:** Allow users to choose from a list of available fonts or upload their own.
*   **Performance Optimization:** For very large images, consider offloading processing to a task queue (e.g., Celery) to prevent HTTP timeouts and improve responsiveness.
*   **UI/UX Enhancements:**
    *   Zoom/pan functionality for output images.
    *   More detailed progress indicators during processing.
    *   A "reset settings" button.
*   **Saving/Loading Configurations:** Allow users to save their preferred settings.

## Contributing

Contributions are welcome! Please feel free to fork the repository, make changes, and submit a pull request. If you find any bugs or have feature suggestions, please open an issue.

## License

