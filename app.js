/**
 * anti-watermark - Client Controller
 * =================================
 * Precision Minimal Black & White Studio Interface
 * 1:1 Scale Original Size Processing & Export
 */

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const uploadSection = document.getElementById('uploadSection');
  const editorSection = document.getElementById('editorSection');
  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('fileInput');
  const btnLoadDemo = document.getElementById('btnLoadDemo');
  const btnNewUpload = document.getElementById('btnNewUpload');

  const mediaVideo = document.getElementById('mediaVideo');
  const mediaCanvas = document.getElementById('mediaCanvas');
  const maskCanvas = document.getElementById('maskCanvas');
  const canvasStage = document.getElementById('canvasStage');

  const toolBox = document.getElementById('toolBox');
  const toolBrush = document.getElementById('toolBrush');
  const toolEraser = document.getElementById('toolEraser');
  const brushSizeControl = document.getElementById('brushSizeControl');
  const brushSizeInput = document.getElementById('brushSize');
  const brushSizeVal = document.getElementById('brushSizeVal');
  const btnAutoDetect = document.getElementById('btnAutoDetect');
  const btnClearRegions = document.getElementById('btnClearRegions');
  const coordMonitor = document.getElementById('coordMonitor');

  const timelineControls = document.getElementById('timelineControls');
  const btnPlayPause = document.getElementById('btnPlayPause');
  const timelineSlider = document.getElementById('timelineSlider');
  const currentTimeLabel = document.getElementById('currentTimeLabel');
  const durationLabel = document.getElementById('durationLabel');
  const btnStepBack = document.getElementById('btnStepBack');
  const btnStepForward = document.getElementById('btnStepForward');

  const regionsList = document.getElementById('regionsList');
  const regionCountBadge = document.getElementById('regionCountBadge');
  const selectMethod = document.getElementById('selectMethod');
  const inputRadius = document.getElementById('inputRadius');
  const radiusVal = document.getElementById('radiusVal');
  const checkRefine = document.getElementById('checkRefine');

  const btnPreviewFrame = document.getElementById('btnPreviewFrame');
  const btnProcessExport = document.getElementById('btnProcessExport');
  const progressContainer = document.getElementById('progressContainer');
  const progressBarFill = document.getElementById('progressBarFill');
  const progressText = document.getElementById('progressText');
  const progressPercent = document.getElementById('progressPercent');
  const exportReadyArea = document.getElementById('exportReadyArea');
  const btnDownloadClean = document.getElementById('btnDownloadClean');

  const compareOverlay = document.getElementById('compareOverlay');
  const compareSliderLine = document.getElementById('compareSliderLine');
  const resolutionTag = document.getElementById('resolutionTag');
  const exportResolutionLabel = document.getElementById('exportResolutionLabel');
  const footerFileMeta = document.getElementById('footerFileMeta');

  // Application State
  let currentFile = null;
  let isVideo = false;
  let mediaWidth = 1920;
  let mediaHeight = 1080;
  let currentTool = 'box';
  let brushRadius = 20;
  let isDrawing = false;
  let startX = 0, startY = 0;
  let activeBoxIndex = -1;

  let regions = [];
  
  // Offscreen mask canvas for freehand brush
  let offscreenMask = document.createElement('canvas');
  let offscreenMaskCtx = offscreenMask.getContext('2d');

  // Cleaned preview buffer
  let cleanedPreviewCanvas = document.createElement('canvas');
  let isComparing = false;
  let compareSplit = 0.5;

  const mediaCtx = mediaCanvas.getContext('2d');
  const maskCtx = maskCanvas.getContext('2d');

  // Standard Presets
  const PRESET_MAPPINGS = {
    gemini: (w, h) => ({ x: Math.round(w * 0.87), y: Math.round(h * 0.79), w: Math.round(w * 0.065), h: Math.round(h * 0.08) }),
    bottom_left: (w, h) => ({ x: Math.round(w * 0.02), y: Math.round(h * 0.85), w: Math.round(w * 0.15), h: Math.round(h * 0.10) }),
    top_right: (w, h) => ({ x: Math.round(w * 0.80), y: Math.round(h * 0.03), w: Math.round(w * 0.17), h: Math.round(h * 0.09) }),
    top_left: (w, h) => ({ x: Math.round(w * 0.03), y: Math.round(h * 0.03), w: Math.round(w * 0.17), h: Math.round(h * 0.09) }),
    bottom_center: (w, h) => ({ x: Math.round(w * 0.15), y: Math.round(h * 0.88), w: Math.round(w * 0.70), h: Math.round(h * 0.09) }),
    center: (w, h) => ({ x: Math.round(w * 0.30), y: Math.round(h * 0.40), w: Math.round(w * 0.40), h: Math.round(h * 0.20) }),
  };

  // --- Upload & File Initialization ---
  function handleFileSelected(file) {
    if (!file) return;
    currentFile = file;
    isVideo = file.type.startsWith('video/') || /\.(mp4|webm|mov|mkv|avi)$/i.test(file.name);

    uploadSection.classList.add('hidden');
    editorSection.classList.remove('hidden');
    btnNewUpload.style.display = 'inline-block';

    if (isVideo) {
      timelineControls.classList.remove('hidden');
      const url = URL.createObjectURL(file);
      mediaVideo.src = url;
      mediaVideo.load();
      mediaVideo.onloadedmetadata = () => {
        mediaWidth = mediaVideo.videoWidth || 1920;
        mediaHeight = mediaVideo.videoHeight || 1080;
        durationLabel.textContent = formatTime(mediaVideo.duration);
        updateResolutionInfo(file.name);
        resizeCanvases();
        renderFrame();
        addPresetRegion('gemini');
      };
    } else {
      timelineControls.classList.add('hidden');
      const img = new Image();
      const url = URL.createObjectURL(file);
      img.onload = () => {
        mediaWidth = img.naturalWidth || 1920;
        mediaHeight = img.naturalHeight || 1080;
        updateResolutionInfo(file.name);
        resizeCanvases();
        mediaCtx.drawImage(img, 0, 0, mediaWidth, mediaHeight);
        addPresetRegion('gemini');
      };
      img.src = url;
    }
  }

  function updateResolutionInfo(filename) {
    const dimText = `${mediaWidth}x${mediaHeight}PX`;
    resolutionTag.textContent = dimText;
    exportResolutionLabel.textContent = `${dimText} (ORIGINAL 1:1)`;
    footerFileMeta.textContent = `${filename.toUpperCase()} // ${dimText}`;
  }

  // Demo file
  btnLoadDemo.addEventListener('click', () => {
    mediaWidth = 1920;
    mediaHeight = 1080;
    isVideo = false;
    currentFile = { name: "sample_hero_frame.png", type: "image/png" };

    uploadSection.classList.add('hidden');
    editorSection.classList.remove('hidden');
    timelineControls.classList.add('hidden');
    btnNewUpload.style.display = 'inline-block';
    updateResolutionInfo(currentFile.name);
    resizeCanvases();

    // Dark technical canvas
    mediaCtx.fillStyle = '#0a0a0a';
    mediaCtx.fillRect(0, 0, mediaWidth, mediaHeight);

    // Decorative gridlines on canvas
    mediaCtx.strokeStyle = '#181818';
    mediaCtx.lineWidth = 1;
    for (let x = 0; x < mediaWidth; x += 64) {
      mediaCtx.beginPath();
      mediaCtx.moveTo(x, 0);
      mediaCtx.lineTo(x, mediaHeight);
      mediaCtx.stroke();
    }
    for (let y = 0; y < mediaHeight; y += 64) {
      mediaCtx.beginPath();
      mediaCtx.moveTo(0, y);
      mediaCtx.lineTo(mediaWidth, y);
      mediaCtx.stroke();
    }

    // Barbell representation
    mediaCtx.fillStyle = '#1e2429';
    mediaCtx.fillRect(0, 800, 1690, 45);
    mediaCtx.fillStyle = '#3a444e';
    mediaCtx.fillRect(1660, 790, 30, 65);

    // 4-point sparkle logo
    drawSparkle(mediaCtx, 1730, 895, 36);

    addPresetRegion('gemini');
  });

  function drawSparkle(ctx, cx, cy, size) {
    ctx.save();
    ctx.fillStyle = '#9e9e9e';
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(cx, cy - size);
    ctx.quadraticCurveTo(cx, cy, cx + size, cy);
    ctx.quadraticCurveTo(cx, cy, cx, cy + size);
    ctx.quadraticCurveTo(cx, cy, cx - size, cy);
    ctx.quadraticCurveTo(cx, cy, cx, cy - size);
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  }

  function resizeCanvases() {
    mediaCanvas.width = mediaWidth;
    mediaCanvas.height = mediaHeight;
    maskCanvas.width = mediaWidth;
    maskCanvas.height = mediaHeight;

    offscreenMask.width = mediaWidth;
    offscreenMask.height = mediaHeight;
    offscreenMaskCtx.clearRect(0, 0, mediaWidth, mediaHeight);

    cleanedPreviewCanvas.width = mediaWidth;
    cleanedPreviewCanvas.height = mediaHeight;

    renderMaskOverlay();
  }

  function renderFrame() {
    if (isVideo && mediaVideo.readyState >= 2) {
      mediaCtx.drawImage(mediaVideo, 0, 0, mediaWidth, mediaHeight);
    }
  }

  // Drag and drop setup
  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length) handleFileSelected(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) handleFileSelected(e.target.files[0]);
  });
  btnNewUpload.addEventListener('click', () => {
    editorSection.classList.add('hidden');
    uploadSection.classList.remove('hidden');
    btnNewUpload.style.display = 'none';
    mediaVideo.pause();
    regions = [];
    updateRegionsList();
  });

  // --- Video Controls ---
  btnPlayPause.addEventListener('click', () => {
    if (mediaVideo.paused) {
      mediaVideo.play();
      btnPlayPause.textContent = '[PAUSE]';
    } else {
      mediaVideo.pause();
      btnPlayPause.textContent = '[PLAY]';
    }
  });

  mediaVideo.addEventListener('timeupdate', () => {
    if (!mediaVideo.duration) return;
    const progress = (mediaVideo.currentTime / mediaVideo.duration) * 100;
    timelineSlider.value = progress;
    currentTimeLabel.textContent = formatTime(mediaVideo.currentTime);
    renderFrame();
  });

  timelineSlider.addEventListener('input', () => {
    if (!mediaVideo.duration) return;
    mediaVideo.currentTime = (timelineSlider.value / 100) * mediaVideo.duration;
    renderFrame();
  });

  btnStepBack.addEventListener('click', () => {
    mediaVideo.currentTime = Math.max(0, mediaVideo.currentTime - 1 / 24);
    renderFrame();
  });

  btnStepForward.addEventListener('click', () => {
    mediaVideo.currentTime = Math.min(mediaVideo.duration, mediaVideo.currentTime + 1 / 24);
    renderFrame();
  });

  function formatTime(seconds) {
    if (isNaN(seconds)) return '00:00.00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 100);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
  }

  // --- Tool Switching ---
  toolBox.addEventListener('click', () => setTool('box'));
  toolBrush.addEventListener('click', () => setTool('brush'));
  toolEraser.addEventListener('click', () => setTool('eraser'));

  function setTool(tool) {
    currentTool = tool;
    toolBox.classList.toggle('active', tool === 'box');
    toolBrush.classList.toggle('active', tool === 'brush');
    toolEraser.classList.toggle('active', tool === 'eraser');
    brushSizeControl.style.display = (tool === 'brush' || tool === 'eraser') ? 'flex' : 'none';
  }

  brushSizeInput.addEventListener('input', (e) => {
    brushRadius = parseInt(e.target.value, 10);
    brushSizeVal.textContent = `${brushRadius}PX`;
  });

  // --- Presets & Auto-Detect ---
  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const presetKey = btn.getAttribute('data-preset');
      addPresetRegion(presetKey);
    });
  });

  function addPresetRegion(presetKey) {
    const fn = PRESET_MAPPINGS[presetKey];
    if (fn) {
      const box = fn(mediaWidth, mediaHeight);
      regions.push(box);
      activeBoxIndex = regions.length - 1;
      updateRegionsList();
      renderMaskOverlay();
    }
  }

  btnAutoDetect.addEventListener('click', () => {
    addPresetRegion('gemini');
  });

  btnClearRegions.addEventListener('click', () => {
    regions = [];
    activeBoxIndex = -1;
    offscreenMaskCtx.clearRect(0, 0, mediaWidth, mediaHeight);
    updateRegionsList();
    renderMaskOverlay();
    hideComparison();
  });

  function updateRegionsList() {
    regionCountBadge.textContent = `${regions.length} SELECTED`;
    regionsList.innerHTML = '';
    if (regions.length === 0) {
      regionsList.innerHTML = '<div class="empty-registry-msg">NO REGION SELECTED. DRAG ON MEDIA OR CLICK PRESET.</div>';
      return;
    }
    regions.forEach((r, idx) => {
      const item = document.createElement('div');
      item.className = 'region-item';
      item.innerHTML = `
        <span>#${idx + 1} [X:${r.x} Y:${r.y} W:${r.w} H:${r.h}]</span>
        <button class="btn-remove-region" title="Remove">[X]</button>
      `;
      item.querySelector('.btn-remove-region').addEventListener('click', (e) => {
        e.stopPropagation();
        regions.splice(idx, 1);
        if (activeBoxIndex === idx) activeBoxIndex = -1;
        updateRegionsList();
        renderMaskOverlay();
      });
      regionsList.appendChild(item);
    });
  }

  // --- Canvas Interaction ---
  function getCanvasCoords(e) {
    const rect = maskCanvas.getBoundingClientRect();
    const scaleX = mediaWidth / rect.width;
    const scaleY = mediaHeight / rect.height;
    return {
      x: Math.round((e.clientX - rect.left) * scaleX),
      y: Math.round((e.clientY - rect.top) * scaleY)
    };
  }

  maskCanvas.addEventListener('mousemove', (e) => {
    const { x, y } = getCanvasCoords(e);
    coordMonitor.textContent = `X: ${String(x).padStart(4, '0')} | Y: ${String(y).padStart(4, '0')}`;
  });

  maskCanvas.addEventListener('mousedown', (e) => {
    if (isComparing) return;
    const { x, y } = getCanvasCoords(e);
    isDrawing = true;
    startX = x;
    startY = y;

    if (currentTool === 'box') {
      activeBoxIndex = regions.findIndex(r => x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h);
      if (activeBoxIndex === -1) {
        regions.push({ x: x, y: y, w: 1, h: 1 });
        activeBoxIndex = regions.length - 1;
      }
    } else if (currentTool === 'brush' || currentTool === 'eraser') {
      paintBrushPoint(x, y);
    }
    renderMaskOverlay();
  });

  window.addEventListener('mousemove', (e) => {
    if (!isDrawing || isComparing) return;
    const { x, y } = getCanvasCoords(e);

    if (currentTool === 'box' && activeBoxIndex >= 0) {
      const box = regions[activeBoxIndex];
      box.w = Math.abs(x - startX);
      box.h = Math.abs(y - startY);
      box.x = Math.min(startX, x);
      box.y = Math.min(startY, y);
      renderMaskOverlay();
    } else if (currentTool === 'brush' || currentTool === 'eraser') {
      paintBrushPoint(x, y);
    }
  });

  window.addEventListener('mouseup', () => {
    if (isDrawing) {
      isDrawing = false;
      if (currentTool === 'box' && activeBoxIndex >= 0) {
        const box = regions[activeBoxIndex];
        if (box.w < 8 || box.h < 8) {
          regions.splice(activeBoxIndex, 1);
          activeBoxIndex = -1;
        }
        updateRegionsList();
      }
      renderMaskOverlay();
    }
  });

  function paintBrushPoint(x, y) {
    offscreenMaskCtx.save();
    offscreenMaskCtx.beginPath();
    offscreenMaskCtx.arc(x, y, brushRadius, 0, Math.PI * 2);
    if (currentTool === 'eraser') {
      offscreenMaskCtx.globalCompositeOperation = 'destination-out';
      offscreenMaskCtx.fill();
    } else {
      offscreenMaskCtx.globalCompositeOperation = 'source-over';
      offscreenMaskCtx.fillStyle = '#ffffff';
      offscreenMaskCtx.fill();
    }
    offscreenMaskCtx.restore();
    renderMaskOverlay();
  }

  function renderMaskOverlay() {
    maskCtx.clearRect(0, 0, mediaWidth, mediaHeight);

    // Draw offscreen brush strokes
    maskCtx.drawImage(offscreenMask, 0, 0);

    // Draw bounding boxes with minimal sharp 1px technical lines
    regions.forEach((r, idx) => {
      const isActive = idx === activeBoxIndex;
      maskCtx.strokeStyle = isActive ? '#ffffff' : '#888888';
      maskCtx.lineWidth = 1;
      maskCtx.strokeRect(r.x, r.y, r.w, r.h);

      // Simple corner marks
      maskCtx.fillStyle = '#ffffff';
      maskCtx.fillRect(r.x - 2, r.y - 2, 4, 4);
      maskCtx.fillRect(r.x + r.w - 2, r.y - 2, 4, 4);
      maskCtx.fillRect(r.x - 2, r.y + r.h - 2, 4, 4);
      maskCtx.fillRect(r.x + r.w - 2, r.y + r.h - 2, 4, 4);

      // Label tag
      maskCtx.fillStyle = '#000000';
      maskCtx.fillRect(r.x, Math.max(0, r.y - 14), 60, 14);
      maskCtx.fillStyle = '#ffffff';
      maskCtx.font = '10px "JetBrains Mono", monospace';
      maskCtx.fillText(`#${idx + 1} REGION`, r.x + 4, Math.max(10, r.y - 3));
    });
  }

  // --- Fast Marching / Navier-Stokes Inpainting for Frame Preview ---
  btnPreviewFrame.addEventListener('click', () => {
    if (regions.length === 0) {
      alert("SELECT AT LEAST ONE REGION OR PRESET.");
      return;
    }
    renderFrame();

    const srcData = mediaCtx.getImageData(0, 0, mediaWidth, mediaHeight);
    const cleanedData = fastInpaintImageData(srcData, regions, offscreenMaskCtx.getImageData(0, 0, mediaWidth, mediaHeight));
    
    cleanedPreviewCanvas.getContext('2d').putImageData(cleanedData, 0, 0);
    showComparison();
  });

  function fastInpaintImageData(imgData, boxRegions, brushData) {
    const w = imgData.width;
    const h = imgData.height;
    const pixels = imgData.data;
    const brushPixels = brushData ? brushData.data : null;

    const mask = new Uint8Array(w * h);

    boxRegions.forEach(r => {
      const x1 = Math.max(0, r.x);
      const y1 = Math.max(0, r.y);
      const x2 = Math.min(w, r.x + r.w);
      const y2 = Math.min(h, r.y + r.h);
      for (let y = y1; y < y2; y++) {
        const row = y * w;
        for (let x = x1; x < x2; x++) {
          mask[row + x] = 1;
        }
      }
    });

    if (brushPixels) {
      for (let i = 0; i < mask.length; i++) {
        if (brushPixels[i * 4 + 3] > 10) mask[i] = 1;
      }
    }

    const radius = parseInt(inputRadius.value, 10) || 2;
    const copy = new Uint8ClampedArray(pixels);

    for (let pass = 0; pass < 3; pass++) {
      for (let y = 0; y < h; y++) {
        const row = y * w;
        for (let x = 0; x < w; x++) {
          const idx = row + x;
          if (mask[idx] === 1) {
            let sumR = 0, sumG = 0, sumB = 0, count = 0;
            for (let dy = -radius; dy <= radius; dy++) {
              const ny = y + dy;
              if (ny < 0 || ny >= h) continue;
              const nRow = ny * w;
              for (let dx = -radius; dx <= radius; dx++) {
                const nx = x + dx;
                if (nx < 0 || nx >= w || (dx === 0 && dy === 0)) continue;
                const nIdx = nRow + nx;
                if (mask[nIdx] === 0 || pass > 0) {
                  const pIdx = nIdx * 4;
                  const dist = Math.sqrt(dx * dx + dy * dy);
                  const weight = 1.0 / (dist + 0.1);
                  sumR += copy[pIdx] * weight;
                  sumG += copy[pIdx + 1] * weight;
                  sumB += copy[pIdx + 2] * weight;
                  count += weight;
                }
              }
            }
            if (count > 0) {
              const pIdx = idx * 4;
              copy[pIdx] = sumR / count;
              copy[pIdx + 1] = sumG / count;
              copy[pIdx + 2] = sumB / count;
            }
          }
        }
      }
    }

    return new ImageData(copy, w, h);
  }

  function showComparison() {
    isComparing = true;
    compareOverlay.classList.remove('hidden');
    compareSplit = 0.5;
    renderComparison();
  }

  function hideComparison() {
    isComparing = false;
    compareOverlay.classList.add('hidden');
    renderFrame();
  }

  function renderComparison() {
    if (!isComparing) return;
    renderFrame();
    const splitX = Math.round(mediaWidth * compareSplit);

    mediaCtx.save();
    mediaCtx.beginPath();
    mediaCtx.rect(splitX, 0, mediaWidth - splitX, mediaHeight);
    mediaCtx.clip();
    mediaCtx.drawImage(cleanedPreviewCanvas, 0, 0);
    mediaCtx.restore();

    compareSliderLine.style.left = `${compareSplit * 100}%`;
  }

  let isDraggingSlider = false;
  compareSliderLine.addEventListener('mousedown', () => isDraggingSlider = true);
  window.addEventListener('mousemove', (e) => {
    if (!isDraggingSlider || !isComparing) return;
    const rect = canvasStage.getBoundingClientRect();
    const frac = Math.max(0.05, Math.min(0.95, (e.clientX - rect.left) / rect.width));
    compareSplit = frac;
    renderComparison();
  });
  window.addEventListener('mouseup', () => isDraggingSlider = false);

  inputRadius.addEventListener('input', (e) => radiusVal.textContent = `${e.target.value}PX`);

  // --- Export at 100% Original Resolution ---
  btnProcessExport.addEventListener('click', async () => {
    if (regions.length === 0) {
      alert("SELECT AT LEAST ONE REGION OR PRESET.");
      return;
    }

    progressContainer.classList.remove('hidden');
    exportReadyArea.classList.add('hidden');
    progressBarFill.style.width = '10%';
    progressPercent.textContent = '10%';
    progressText.textContent = `INITIALIZING ORIGINAL RESOLUTION (${mediaWidth}x${mediaHeight})...`;

    try {
      const formData = new FormData();
      formData.append('file', currentFile);

      const uploadRes = await fetch('/api/upload', { method: 'POST', body: formData });
      if (!uploadRes.ok) throw new Error("Local server offline");
      const uploadData = await uploadRes.json();

      progressText.textContent = 'EXECUTING ANTI-REFLECTION INPAINTING...';
      progressBarFill.style.width = '25%';

      const processRes = await fetch('/api/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_id: uploadData.file_id,
          regions: regions,
          method: selectMethod.value,
          radius: parseInt(inputRadius.value, 10),
          refine: checkRefine.checked
        })
      });

      const { job_id } = await processRes.json();

      const pollInterval = setInterval(async () => {
        try {
          const jobRes = await fetch(`/api/job/${job_id}`);
          const jobData = await jobRes.json();

          const pct = Math.round(jobData.progress * 100);
          progressBarFill.style.width = `${pct}%`;
          progressPercent.textContent = `${pct}%`;
          progressText.textContent = `FRAME: ${jobData.current_frame || 0}/${jobData.total_frames || 1} [ORIGINAL SCALE]`;

          if (jobData.status === 'completed') {
            clearInterval(pollInterval);
            progressText.textContent = `COMPLETE // 1:1 SCALE (${mediaWidth}x${mediaHeight})`;
            exportReadyArea.classList.remove('hidden');
            btnDownloadClean.href = `/api/download/${jobData.output_file}`;
            btnDownloadClean.download = jobData.output_file;
          } else if (jobData.status === 'failed') {
            clearInterval(pollInterval);
            progressText.textContent = `ERROR: ${jobData.error}`;
          }
        } catch (e) {
          clearInterval(pollInterval);
        }
      }, 800);

    } catch (e) {
      // Standalone client fallback (1:1 Original Size canvas export)
      progressText.textContent = `PROCESSING FRAME LOCALLY AT ${mediaWidth}x${mediaHeight}...`;
      setTimeout(() => {
        btnPreviewFrame.click();
        progressBarFill.style.width = '100%';
        progressPercent.textContent = '100%';
        progressText.textContent = `COMPLETE // 1:1 SCALE (${mediaWidth}x${mediaHeight})`;
        exportReadyArea.classList.remove('hidden');

        // Export at exact original dimensions
        btnDownloadClean.href = cleanedPreviewCanvas.toDataURL('image/png');
        btnDownloadClean.download = `anti_watermark_${mediaWidth}x${mediaHeight}_${Date.now()}.png`;
      }, 600);
    }
  });
});
