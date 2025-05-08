const imageUpload = document.getElementById('imageUpload');
const originalImagePreview = document.getElementById('originalImagePreview');
const numColorsInput = document.getElementById('numColors');
const fontSizeInput = document.getElementById('fontSize');
const lineSensitivitySelect = document.getElementById('lineSensitivity'); // New
const mergeSmallRegionsCheckbox = document.getElementById('mergeSmallRegions');
const mergeOptionsDiv = document.getElementById('mergeOptions');
const minMergeAreaPercentInput = document.getElementById('minMergeAreaPercent');
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
        const response = await fetch('/process_image', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', },
            body: JSON.stringify({
                imageDataUrl: uploadedImageDataUrl,
                numColors: parseInt(numColorsInput.value),
                fontSize: parseInt(fontSizeInput.value),
                lineSensitivity: lineSensitivitySelect.value, // Send line sensitivity
                mergeSmallRegions: mergeSmallRegionsCheckbox.checked,
                minMergeAreaPercent: parseFloat(minMergeAreaPercentInput.value)
            }),
        });

        if (!response.ok) {
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

function generateLegend(palette) {
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

function triggerDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function b64toBlob(b64Data, contentType='', sliceSize=512) {
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
