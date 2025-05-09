// script.js
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM fully loaded and parsed. Initializing script...");

    const imageUpload = document.getElementById('imageUpload');
    const originalImagePreview = document.getElementById('originalImagePreview');
    const numColorsInput = document.getElementById('numColors');
    const fontSizeInput = document.getElementById('fontSize');
    const lineSensitivitySelect = document.getElementById('lineSensitivity');
    const mergeSmallRegionsCheckbox = document.getElementById('mergeSmallRegions');
    const mergeOptionsDiv = document.getElementById('mergeOptions');
    const minMergeAreaPercentInput = document.getElementById('minMergeAreaPercent');

    const enableBgRemovalCheckbox = document.getElementById('enableBgRemoval');
    const bgRemovalOptionsDiv = document.getElementById('bgRemovalOptions');
    const enableSmoothingCheckbox = document.getElementById('enableSmoothing');
    const smoothingOptionsDiv = document.getElementById('smoothingOptions');
    const smoothingKernelSizeSelect = document.getElementById('smoothingKernelSize');

    const selectedBgColorInput = document.getElementById('selectedBgColor');
    const selectedColorDisplay = document.getElementById('selectedColorDisplay');
    const bgColorSwatch = document.getElementById('bgColorSwatch');
    const bgColorRgb = document.getElementById('bgColorRgb');
    const clearBgColorBtn = document.getElementById('clearBgColor');
    const bgColorToleranceInput = document.getElementById('bgColorTolerance');

    const processButton = document.getElementById('processButton');
    const loader = document.getElementById('loader');
    const errorMessage = document.getElementById('errorMessage');

    const settingsContainer = document.getElementById('settingsContainer');
    const cancelProcessButton = document.getElementById('cancelProcessButton');
    const logContainer = document.getElementById('logContainer');
    const logMessages = document.getElementById('logMessages');

    const generateNumbersCheckbox = document.getElementById('generateNumbers');
    const genColoredPreviewCheckbox = document.getElementById('genColoredPreview');
    const genBgRemovedCheckbox = document.getElementById('genBgRemoved');
    const genLineArtPngCheckbox = document.getElementById('genLineArtPng');
    const genLineArtSvgCheckbox = document.getElementById('genLineArtSvg');

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

    if (!settingsContainer) {
        console.error("CRITICAL: settingsContainer element not found after DOMContentLoaded!");
    }
    if (!imageUpload) console.error("imageUpload not found");
    if (!numColorsInput) console.error("numColorsInput not found");
    // Add more checks for crucial elements if needed

    let uploadedImageDataUrl = null;
    let currentResultData = null; 
    let currentProcessController = null;

    function setUIProcessingState(isProcessing) {
        if (!settingsContainer) {
            console.error("settingsContainer is null in setUIProcessingState! Cannot disable settings.");
        } else {
            const allSettingsInputs = settingsContainer.querySelectorAll('input, select');
            allSettingsInputs.forEach(input => {
                input.disabled = isProcessing;
            });
        }
        // Explicitly handle main action buttons outside settingsContainer if they are not within it.
        if (processButton) processButton.disabled = isProcessing;
        if (imageUpload) imageUpload.disabled = isProcessing; 
        if (cancelProcessButton) cancelProcessButton.style.display = isProcessing ? 'block' : 'none';
        if (loader) loader.style.display = isProcessing ? 'block' : 'none';
        if (logContainer) logContainer.style.display = isProcessing ? 'block' : 'none';
        
        if (isProcessing && logMessages) {
            logMessages.innerHTML = ''; 
        }
    }

    function appendLog(message) {
        if (!logMessages || !logContainer) return;
        const timestamp = new Date().toLocaleTimeString();
        logMessages.innerHTML += `[${timestamp}] ${message}<br>`;
        logContainer.scrollTop = logContainer.scrollHeight; 
    }

    if (imageUpload) {
        imageUpload.addEventListener('change', (event) => {
            const file = event.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    uploadedImageDataUrl = e.target.result;
                    if(originalImagePreview) {
                        originalImagePreview.src = uploadedImageDataUrl;
                        originalImagePreview.style.display = 'block';
                    }
                    setUIProcessingState(false); 
                    if(processButton) processButton.disabled = false;
                    if(errorMessage) errorMessage.textContent = ''; 
                    if(quantizedOutput) quantizedOutput.style.display = 'none';
                    if(bgRemovedOutput) bgRemovedOutput.style.display = 'none';
                    if(lineArtOutput) lineArtOutput.style.display = 'none';
                    currentResultData = null; 
                };
                reader.readAsDataURL(file);
            } else {
                uploadedImageDataUrl = null;
                if(originalImagePreview) originalImagePreview.style.display = 'none';
                if(processButton) processButton.disabled = true;
            }
        });
    } else {
        console.error("imageUpload element not found, 'change' listener not attached.");
    }


    if(mergeSmallRegionsCheckbox) mergeSmallRegionsCheckbox.addEventListener('change', function() {
        if(mergeOptionsDiv) mergeOptionsDiv.style.display = this.checked ? 'block' : 'none';
    });

    if(enableBgRemovalCheckbox) enableBgRemovalCheckbox.addEventListener('change', function() {
        if(bgRemovalOptionsDiv) bgRemovalOptionsDiv.style.display = this.checked ? 'block' : 'none';
        if (!this.checked) {
            if(selectedBgColorInput) selectedBgColorInput.value = ''; 
            if(selectedColorDisplay) selectedColorDisplay.style.display = 'none';
            if(bgColorSwatch) bgColorSwatch.style.backgroundColor = 'transparent';
            if(bgColorRgb) bgColorRgb.textContent = '';
        }
    });

    if(originalImagePreview) originalImagePreview.addEventListener('click', function(event) {
        if (!enableBgRemovalCheckbox || !enableBgRemovalCheckbox.checked || !uploadedImageDataUrl) return;
        // ... (eyedropper logic - seems okay, ensure all elements here are checked for null if issues persist)
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        const img = new Image();
        img.onload = () => {
            canvas.width = img.naturalWidth; 
            canvas.height = img.naturalHeight;
            ctx.drawImage(img, 0, 0, img.naturalWidth, img.naturalHeight);

            const rect = originalImagePreview.getBoundingClientRect();
            const scaleX = img.naturalWidth / rect.width;
            const scaleY = img.naturalHeight / rect.height;
            
            const xInImage = (event.clientX - rect.left) * scaleX;
            const yInImage = (event.clientY - rect.top) * scaleY;

            const finalX = Math.max(0, Math.min(Math.round(xInImage), img.naturalWidth - 1));
            const finalY = Math.max(0, Math.min(Math.round(yInImage), img.naturalHeight - 1));

            const pixelData = ctx.getImageData(finalX, finalY, 1, 1).data;
            const rgb = [pixelData[0], pixelData[1], pixelData[2]];
            
            if(selectedBgColorInput) selectedBgColorInput.value = rgb.join(',');
            if(bgColorSwatch) bgColorSwatch.style.backgroundColor = `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
            if(bgColorRgb) bgColorRgb.textContent = `RGB(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
            if(selectedColorDisplay) selectedColorDisplay.style.display = 'block';
        };
        img.src = uploadedImageDataUrl;
    });

    if(clearBgColorBtn) clearBgColorBtn.addEventListener('click', () => {
        if(selectedBgColorInput) selectedBgColorInput.value = '';
        if(selectedColorDisplay) selectedColorDisplay.style.display = 'none';
        if(bgColorSwatch) bgColorSwatch.style.backgroundColor = 'transparent';
        if(bgColorRgb) bgColorRgb.textContent = '';
    });

    if(enableSmoothingCheckbox) enableSmoothingCheckbox.addEventListener('change', function() {
        if(smoothingOptionsDiv) smoothingOptionsDiv.style.display = this.checked ? 'block' : 'none';
    });

    if (processButton) {
        processButton.addEventListener('click', async () => {
            if (!uploadedImageDataUrl) {
                if(errorMessage) errorMessage.textContent = 'Please upload an image first.';
                return;
            }
            
            setUIProcessingState(true); 
            appendLog("Starting process...");
            if(errorMessage) errorMessage.textContent = '';
            if(quantizedOutput) quantizedOutput.style.display = 'none';
            if(bgRemovedOutput) bgRemovedOutput.style.display = 'none';
            if(lineArtOutput) lineArtOutput.style.display = 'none';
            currentResultData = null;

            currentProcessController = new AbortController(); 
            const signal = currentProcessController.signal;

            try {
                // Ensure all input elements exist before accessing .value or .checked
                const payload = {
                    imageDataUrl: uploadedImageDataUrl,
                    numColors: numColorsInput ? parseInt(numColorsInput.value) : 8, // Default if input is null
                    fontSize: fontSizeInput ? parseInt(fontSizeInput.value) : 15,
                    lineSensitivity: lineSensitivitySelect ? lineSensitivitySelect.value : 'medium',
                    mergeSmallRegions: mergeSmallRegionsCheckbox ? mergeSmallRegionsCheckbox.checked : false,
                    minMergeAreaPercent: minMergeAreaPercentInput ? parseFloat(minMergeAreaPercentInput.value) : 0.1,
                    enableBgRemoval: enableBgRemovalCheckbox ? enableBgRemovalCheckbox.checked : false,
                    selectedBgColor: (enableBgRemovalCheckbox && enableBgRemovalCheckbox.checked && selectedBgColorInput && selectedBgColorInput.value) ? selectedBgColorInput.value.split(',').map(Number) : null,
                    bgColorTolerance: bgColorToleranceInput ? parseInt(bgColorToleranceInput.value) : 30,
                    enableSmoothing: enableSmoothingCheckbox ? enableSmoothingCheckbox.checked : false,
                    smoothingKernelSize: smoothingKernelSizeSelect ? parseInt(smoothingKernelSizeSelect.value) : 3,
                    outputs: {
                        generateNumbers: generateNumbersCheckbox ? generateNumbersCheckbox.checked : true,
                        coloredPreview: genColoredPreviewCheckbox ? genColoredPreviewCheckbox.checked : true,
                        bgRemoved: genBgRemovedCheckbox ? genBgRemovedCheckbox.checked : true,
                        lineArtPng: genLineArtPngCheckbox ? genLineArtPngCheckbox.checked : true,
                        lineArtSvg: genLineArtSvgCheckbox ? genLineArtSvgCheckbox.checked : true,
                    } 
                };
                
                console.log("Client payload being sent:", JSON.stringify(payload, null, 2)); // DEBUG

                const response = await fetch('/process_image', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', },
                    body: JSON.stringify(payload),
                    signal: signal 
                });

                // ... (rest of your fetch handling, it seems mostly okay) ...
                 if (signal.aborted) { 
                    appendLog("Process cancelled by user (client-side).");
                    if(errorMessage) errorMessage.textContent = "Process cancelled.";
                    return; 
                }

                if (!response.ok) {
                    let errorPayload = { error: `Server error: ${response.status}`}; 
                    try {
                        errorPayload = await response.json(); 
                    } catch (e) {
                        appendLog(`Warning: Server error response was not JSON. Status: ${response.status}`);
                    }
                    throw new Error(errorPayload.error || `Server error: ${response.status}`);
                }

                const resultData = await response.json(); 
                currentResultData = resultData; 

                appendLog("Processing complete on server.");
                if (resultData.log && Array.isArray(resultData.log)) { 
                    resultData.log.forEach(msg => appendLog(`[SERVER] ${msg}`));
                }

                if(quantizedOutput) quantizedOutput.style.display = 'none'; 
                if(bgRemovedOutput) bgRemovedOutput.style.display = 'none';
                if(lineArtOutput) lineArtOutput.style.display = 'none';

                if (resultData.quantized_image_b64 && quantizedImage && quantizedOutput) {
                    quantizedImage.src = 'data:image/png;base64,' + resultData.quantized_image_b64;
                    quantizedOutput.style.display = 'block';
                }
                if (resultData.bg_removed_char_b64 && bgRemovedImage && bgRemovedOutput) {
                    bgRemovedImage.src = 'data:image/png;base64,' + resultData.bg_removed_char_b64;
                    bgRemovedOutput.style.display = 'block';
                }
                if ((resultData.line_art_png_b64 || resultData.line_art_svg_content) && lineArtOutput) {
                    if (resultData.line_art_png_b64 && lineArtImagePng) {
                        lineArtImagePng.src = 'data:image/png;base64,' + resultData.line_art_png_b64;
                        lineArtImagePng.style.display = 'block';
                    } else if (lineArtImagePng) {
                        lineArtImagePng.style.display = 'none';
                    }
                    generateLegend(resultData.palette_rgb || []); 
                    lineArtOutput.style.display = 'block';
                }
                appendLog("Results displayed.");


            } catch (error)  {
                if (error.name === 'AbortError') {
                    appendLog("Process fetch aborted.");
                } else {
                    console.error('Error during processButton click:', error);
                    appendLog(`Error: ${error.message}`);
                    if(errorMessage) errorMessage.textContent = 'Error processing image: ' + error.message;
                }
            } finally {
                setUIProcessingState(false);
                currentProcessController = null; 
                if(processButton) processButton.disabled = !uploadedImageDataUrl; 
            }
        });
    } else {
        console.error("processButton element not found, event listener not attached.");
    }


    if(cancelProcessButton) cancelProcessButton.addEventListener('click', () => {
        if (currentProcessController) {
            appendLog("Attempting to cancel process...");
            currentProcessController.abort(); 
            if(errorMessage) errorMessage.textContent = "Process cancellation initiated...";
        }
    });

    function generateLegend(palette) { 
        if(!colorLegend) return;
        colorLegend.innerHTML = '';
        if (!palette || !Array.isArray(palette)) return; 
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
        if (!b64Data) return null; 
        try {
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
        } catch (e) {
            console.error("Error in b64toBlob: ", e);
            appendLog("Error converting base64 data for download.");
            return null;
        }
    }

    // Add null checks for download buttons before adding listeners
    if(downloadQuantizedPngBtn) downloadQuantizedPngBtn.addEventListener('click', () => {
        if (currentResultData && currentResultData.quantized_image_b64) {
            const blob = b64toBlob(currentResultData.quantized_image_b64, 'image/png');
            if(blob) triggerDownload(blob, 'quantized_preview.png');
        } else { appendLog("No quantized image data to download.");}
    });

    if(downloadBgRemovedPngBtn) downloadBgRemovedPngBtn.addEventListener('click', () => {
        if (currentResultData && currentResultData.bg_removed_char_b64) {
            const blob = b64toBlob(currentResultData.bg_removed_char_b64, 'image/png');
            if(blob) triggerDownload(blob, 'bg_removed_character.png');
        } else { appendLog("No BG removed image data to download.");}
    });

    if(downloadLineArtPngBtn) downloadLineArtPngBtn.addEventListener('click', () => {
        if (currentResultData && currentResultData.line_art_png_b64) {
            const blob = b64toBlob(currentResultData.line_art_png_b64, 'image/png');
            if(blob) triggerDownload(blob, 'line_art.png');
        } else { appendLog("No Line Art PNG data to download.");}
    });

    if(downloadLineArtSvgBtn) downloadLineArtSvgBtn.addEventListener('click', () => {
        if (currentResultData && currentResultData.line_art_svg_content) {
            const blob = new Blob([currentResultData.line_art_svg_content], { type: 'image/svg+xml' });
            triggerDownload(blob, 'line_art.svg');
        } else { appendLog("No Line Art SVG data to download.");}
    });

}); // End of DOMContentLoaded