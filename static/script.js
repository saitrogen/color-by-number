const imageUpload = document.getElementById('imageUpload');
const originalImagePreview = document.getElementById('originalImagePreview');
const numColorsInput = document.getElementById('numColors');
const fontSizeInput = document.getElementById('fontSize');
const lineSensitivitySelect = document.getElementById('lineSensitivity');
const mergeSmallRegionsCheckbox = document.getElementById('mergeSmallRegions');
const mergeOptionsDiv = document.getElementById('mergeOptions');
const minMergeAreaPercentInput = document.getElementById('minMergeAreaPercent');

// Background Removal Elements
const enableBgRemovalCheckbox = document.getElementById('enableBgRemoval');
const bgRemovalOptionsDiv = document.getElementById('bgRemovalOptions'); // Changed from bgColorPickerHelp
const enableSmoothingCheckbox = document.getElementById('enableSmoothing');
const smoothingOptionsDiv = document.getElementById('smoothingOptions');
const smoothingKernelSizeSelect = document.getElementById('smoothingKernelSize');


const selectedBgColorInput = document.getElementById('selectedBgColor');
const selectedColorDisplay = document.getElementById('selectedColorDisplay');
const bgColorSwatch = document.getElementById('bgColorSwatch');
const bgColorRgb = document.getElementById('bgColorRgb');
const clearBgColorBtn = document.getElementById('clearBgColor');
const bgColorToleranceInput = document.getElementById('bgColorTolerance'); // New

const processButton = document.getElementById('processButton');
const loader = document.getElementById('loader');
const errorMessage = document.getElementById('errorMessage');

const quantizedOutput = document.getElementById('quantizedOutput');
const quantizedImage = document.getElementById('quantizedImage');
const bgRemovedOutput = document.getElementById('bgRemovedOutput');
const bgRemovedImage = document.getElementById('bgRemovedImage');
const lineArtOutput = document.getElementById('lineArtOutput');
const lineArtImagePng = document.getElementById('lineArtImagePng'); 
const colorLegend = document.getElementById('colorLegend');

const downloadQuantizedPngBtn = document.getElementById('downloadQuantizedPng');
const downloadBgRemovedPngBtn = document.getElementById('downloadBgRemovedPng');
const downloadLineArtPngBtn = document.getElementById('downloadLineArtPng');
const downloadLineArtSvgBtn = document.getElementById('downloadLineArtSvg');

let uploadedImageDataUrl = null;
let currentResultData = null; 

imageUpload.addEventListener('change', (event) => {
    const file = event.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            uploadedImageDataUrl = e.target.result;
            originalImagePreview.src = uploadedImageDataUrl;
            originalImagePreview.style.display = 'block';
            processButton.disabled = false;
            errorMessage.textContent = ''; 
            quantizedOutput.style.display = 'none';
            bgRemovedOutput.style.display = 'none';
            lineArtOutput.style.display = 'none';
            currentResultData = null; 
        };
        reader.readAsDataURL(file);
    } else {
        uploadedImageDataUrl = null;
        originalImagePreview.style.display = 'none';
        processButton.disabled = true;
    }
});

mergeSmallRegionsCheckbox.addEventListener('change', function() {
    mergeOptionsDiv.style.display = this.checked ? 'block' : 'none';
});

// Toggle BG removal options visibility
enableBgRemovalCheckbox.addEventListener('change', function() {
    bgRemovalOptionsDiv.style.display = this.checked ? 'block' : 'none';
    if (!this.checked) {
        selectedBgColorInput.value = ''; // Clear selected color if feature is disabled
        selectedColorDisplay.style.display = 'none';
        bgColorSwatch.style.backgroundColor = 'transparent';
        bgColorRgb.textContent = '';
    }
});

// Eyedropper functionality for original image preview
originalImagePreview.addEventListener('click', function(event) {
    if (!enableBgRemovalCheckbox.checked || !uploadedImageDataUrl) return;

    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const img = new Image();
    img.onload = () => {
        canvas.width = img.naturalWidth; // Use naturalWidth/Height for correct scaling
        canvas.height = img.naturalHeight;
        ctx.drawImage(img, 0, 0, img.naturalWidth, img.naturalHeight);

        const rect = originalImagePreview.getBoundingClientRect();
        // Calculate scaling factor based on displayed size vs natural size
        const scaleX = img.naturalWidth / rect.width;
        const scaleY = img.naturalHeight / rect.height;
        
        const xInImage = (event.clientX - rect.left) * scaleX;
        const yInImage = (event.clientY - rect.top) * scaleY;

        // Ensure coordinates are within image bounds
        const finalX = Math.max(0, Math.min(Math.round(xInImage), img.naturalWidth - 1));
        const finalY = Math.max(0, Math.min(Math.round(yInImage), img.naturalHeight - 1));

        const pixelData = ctx.getImageData(finalX, finalY, 1, 1).data;
        const rgb = [pixelData[0], pixelData[1], pixelData[2]];
        
        selectedBgColorInput.value = rgb.join(',');
        bgColorSwatch.style.backgroundColor = `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
        bgColorRgb.textContent = `RGB(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
        selectedColorDisplay.style.display = 'block';
    };
    img.src = uploadedImageDataUrl;
});

clearBgColorBtn.addEventListener('click', () => {
    selectedBgColorInput.value = '';
    selectedColorDisplay.style.display = 'none';
    bgColorSwatch.style.backgroundColor = 'transparent';
    bgColorRgb.textContent = '';
});

// event listener for the smoothing checkbox
enableSmoothingCheckbox.addEventListener('change', function() {
    smoothingOptionsDiv.style.display = this.checked ? 'block' : 'none';
});


processButton.addEventListener('click', async () => {
    if (!uploadedImageDataUrl) {
        errorMessage.textContent = 'Please upload an image first.';
        return;
    }

    loader.style.display = 'block';
    processButton.disabled = true;
    errorMessage.textContent = '';
    quantizedOutput.style.display = 'none';
    bgRemovedOutput.style.display = 'none';
    lineArtOutput.style.display = 'none';
    currentResultData = null;

    try {
        const payload = {
            imageDataUrl: uploadedImageDataUrl,
            numColors: parseInt(numColorsInput.value),
            fontSize: parseInt(fontSizeInput.value),
            lineSensitivity: lineSensitivitySelect.value,
            mergeSmallRegions: mergeSmallRegionsCheckbox.checked,
            minMergeAreaPercent: parseFloat(minMergeAreaPercentInput.value),
            enableBgRemoval: enableBgRemovalCheckbox.checked,
            selectedBgColor: selectedBgColorInput.value ? selectedBgColorInput.value.split(',').map(Number) : null,
            bgColorTolerance: parseInt(bgColorToleranceInput.value), // Send tolerance
            enableSmoothing: enableSmoothingCheckbox.checked, // New
            smoothingKernelSize: parseInt(smoothingKernelSizeSelect.value) // New
        };
        
        // Only include selectedBgColor if enableBgRemoval is checked and a color is selected
        if (!enableBgRemovalCheckbox.checked || !selectedBgColorInput.value) {
            payload.selectedBgColor = null; // Ensure it's null if not fully enabled/selected
        }


        const response = await fetch('/process_image', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', },
            body: JSON.stringify(payload),
        });

        if (!response.ok) { /* ... (existing error handling from your file) ... */ 
            let errorPayload;
            try {
                errorPayload = await response.json(); 
            } catch (e) {
                errorPayload = { error: `Server error: ${response.status} (Response not JSON)` };
            }
            throw new Error(errorPayload.error || `Server error: ${response.status}`);
        }


        const resultData = await response.json(); 
        currentResultData = resultData; 

        quantizedImage.src = 'data:image/png;base64,' + resultData.quantized_image_b64;
        bgRemovedImage.src = 'data:image/png;base64,' + resultData.bg_removed_char_b64; 
        lineArtImagePng.src = 'data:image/png;base64,' + resultData.line_art_png_b64;
        
        quantizedOutput.style.display = 'block';
        bgRemovedOutput.style.display = 'block'; 
        lineArtOutput.style.display = 'block';

        generateLegend(resultData.palette_rgb);

    } catch (error)  {
        console.error('Error:', error);
        errorMessage.textContent = 'Error processing image: ' + error.message;
    } finally {
        loader.style.display = 'none';
        if (uploadedImageDataUrl) { 
            processButton.disabled = false;
        }
    }
});

function generateLegend(palette) { /* ... (existing logic from your file) ... */ 
    colorLegend.innerHTML = '';
    palette.forEach((color_rgb, index) => {
        const item = document.createElement('div');
        item.className = 'legend-item';
        const colorBox = document.createElement('div');
        colorBox.className = 'legend-color';
        colorBox.style.backgroundColor = `rgb(${color_rgb[0]}, ${color_rgb[1]}, ${color_rgb[2]})`;
        const numberText = document.createElement('span');
        numberText.textContent = index + 1;
        item.appendChild(colorBox);
        item.appendChild(numberText);
        colorLegend.appendChild(item);
    });
}

function triggerDownload(blob, filename) { /* ... (existing logic from your file) ... */ 
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function b64toBlob(b64Data, contentType='', sliceSize=512) { /* ... (existing logic from your file) ... */ 
    const byteCharacters = atob(b64Data);
    const byteArrays = [];
    for (let offset = 0; offset < byteCharacters.length; offset += sliceSize) {
        const slice = byteCharacters.slice(offset, offset + sliceSize);
        const byteNumbers = new Array(slice.length);
        for (let i = 0; i < slice.length; i++) {
            byteNumbers[i] = slice.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        byteArrays.push(byteArray);
    }
    return new Blob(byteArrays, {type: contentType});
}

// Download button event listeners (should be the same as your existing file)
downloadQuantizedPngBtn.addEventListener('click', () => { /* ... */ });
downloadBgRemovedPngBtn.addEventListener('click', () => { /* ... */ });
downloadLineArtPngBtn.addEventListener('click', () => { /* ... */ });
downloadLineArtSvgBtn.addEventListener('click', () => { /* ... */ });

// Make sure to copy the content of your download button listeners here if they were not fully included in the prompt
downloadQuantizedPngBtn.addEventListener('click', () => {
    if (currentResultData && currentResultData.quantized_image_b64) {
        const blob = b64toBlob(currentResultData.quantized_image_b64, 'image/png');
        triggerDownload(blob, 'quantized_preview.png');
    }
});

downloadBgRemovedPngBtn.addEventListener('click', () => {
    if (currentResultData && currentResultData.bg_removed_char_b64) {
        const blob = b64toBlob(currentResultData.bg_removed_char_b64, 'image/png');
        triggerDownload(blob, 'bg_removed_character.png');
    }
});

downloadLineArtPngBtn.addEventListener('click', () => {
    if (currentResultData && currentResultData.line_art_png_b64) {
        const blob = b64toBlob(currentResultData.line_art_png_b64, 'image/png');
        triggerDownload(blob, 'line_art.png');
    }
});

downloadLineArtSvgBtn.addEventListener('click', () => {
    if (currentResultData && currentResultData.line_art_svg_content) {
        const blob = new Blob([currentResultData.line_art_svg_content], { type: 'image/svg+xml' });
        triggerDownload(blob, 'line_art.svg');
    }
});