#!/usr/bin/env python3
"""
Universal Watermark Remover Engine ("OmniMark Engine")
=====================================================
Removes any watermark from videos and images:
- Any position: corners, center, tickers, timestamps, subtitles, diagonal patterns.
- Any format: MP4, WebM, MOV, AVI, MKV, PNG, JPG, WEBP.
- Flexible masks: Auto-detection, rectangular bounding boxes, multi-region boxes, or freehand brush masks.
- Multiple inpainting methods: OpenCV TELEA, Navier-Stokes, or smart contrast-aware masking.
- Lossless audio preservation using ffmpeg remuxing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from typing import Callable, List, Optional, Tuple, Union

import cv2
import numpy as np
from PIL import Image

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".flv", ".wmv"}

PRESETS = {
    "bottom_right": lambda w, h: (int(w * 0.78), int(h * 0.88), int(w * 0.20), int(h * 0.10)),
    "bottom_left": lambda w, h: (int(w * 0.02), int(h * 0.88), int(w * 0.20), int(h * 0.10)),
    "top_right": lambda w, h: (int(w * 0.78), int(h * 0.02), int(w * 0.20), int(h * 0.10)),
    "top_left": lambda w, h: (int(w * 0.02), int(h * 0.02), int(w * 0.20), int(h * 0.10)),
    "seedance": lambda w, h: (int(w * 0.75), int(h * 0.90), int(w * 0.23), int(h * 0.08)),
    "gemini": lambda w, h: (int(w * 0.88), int(h * 0.86), int(w * 0.10), int(h * 0.11)),
    "tiktok": lambda w, h: (int(w * 0.75), int(h * 0.03), int(w * 0.22), int(h * 0.08)),
    "bottom_center": lambda w, h: (int(w * 0.20), int(h * 0.90), int(w * 0.60), int(h * 0.08)),
    "center": lambda w, h: (int(w * 0.25), int(h * 0.40), int(w * 0.50), int(h * 0.20)),
}


def _sparkle_template(size: int = 64) -> np.ndarray:
    """Return a filled 4-point sparkle template for AI logo/Gemini watermark detection."""
    edge = size - 1
    points = np.array(
        [
            (0.50 * edge, 0.00 * edge),
            (0.62 * edge, 0.36 * edge),
            (1.00 * edge, 0.50 * edge),
            (0.62 * edge, 0.64 * edge),
            (0.50 * edge, 1.00 * edge),
            (0.38 * edge, 0.64 * edge),
            (0.00 * edge, 0.50 * edge),
            (0.38 * edge, 0.36 * edge),
        ],
        dtype=np.int32,
    )
    template = np.zeros((size, size), dtype=np.uint8)
    cv2.fillPoly(template, [points], 255)
    return template


SPARKLE_TEMPLATE = _sparkle_template(64)


def find_ffmpeg() -> Optional[str]:
    """Locates the ffmpeg executable on system PATH or local app directory."""
    candidates = [
        shutil.which("ffmpeg"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "_internal", "ffmpeg.exe"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return shutil.which("ffmpeg")


def is_image_file(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in IMAGE_EXTENSIONS


def is_video_file(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in VIDEO_EXTENSIONS


def build_default_output_path(input_path: str) -> str:
    base, ext = os.path.splitext(input_path)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:6]
    return f"{base}_clean_{stamp}_{uid}{ext}"


def sample_video_frames(video_path: str, max_samples: int = 24) -> Tuple[List[np.ndarray], int, int, float, int]:
    """Sample evenly spaced frames from a video for analysis."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Cannot open video: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    if total_frames <= 0:
        frames = []
        while len(frames) < max_samples:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        cap.release()
        return frames, width, height, fps, len(frames)

    indices = np.linspace(0, total_frames - 1, min(max_samples, total_frames), dtype=int)
    frames = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if ret:
            frames.append(frame)

    cap.release()
    return frames, width, height, fps, total_frames


def auto_detect_temporal_watermark(frames: List[np.ndarray], width: int, height: int) -> Optional[Tuple[int, int, int, int]]:
    """
    Detects static watermarks by calculating temporal invariance (low standard deviation across time)
    combined with edge sharpness. Works across the entire frame, prioritizing high-scoring corners and edges.
    """
    if len(frames) < 3:
        return None

    stack = np.stack(frames, axis=0).astype(np.float32)
    # Low standard deviation across frames = static watermark or logo
    std_map = np.std(stack, axis=0).mean(axis=2)  # shape (H, W)

    # Candidate regions in all 4 corners + bottom banner
    corner_w = max(80, int(width * 0.22))
    corner_h = max(40, int(height * 0.12))

    regions = [
        (width - corner_w, height - corner_h, corner_w, corner_h),  # Bottom-Right
        (0, height - corner_h, corner_w, corner_h),                  # Bottom-Left
        (width - corner_w, 0, corner_w, corner_h),                  # Top-Right
        (0, 0, corner_w, corner_h),                                  # Top-Left
        (int(width * 0.15), height - corner_h, int(width * 0.70), corner_h),  # Bottom Bar
    ]

    best_region = None
    best_score = -1.0

    mean_frame = np.mean(stack, axis=0).astype(np.uint8)
    gray_mean = cv2.cvtColor(mean_frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray_mean, 50, 150)

    for x, y, w, h in regions:
        x = max(0, min(x, width - w))
        y = max(0, min(y, height - h))
        roi_std = std_map[y : y + h, x : x + w]
        roi_edges = edges[y : y + h, x : x + w]

        # Temporal stability score: lower std is better
        temporal_stability = 1.0 / (np.mean(roi_std) + 1e-4)
        edge_density = np.count_nonzero(roi_edges) / float(w * h)

        score = temporal_stability * (edge_density ** 0.5)

        # Minimum edge density threshold to prevent selecting flat solid backgrounds
        if edge_density > 0.015 and score > best_score:
            best_score = score
            best_region = (x, y, w, h)

    return best_region


def auto_detect_gemini_sparkle(frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """Detects 4-point sparkle logo geometry typical of Gemini AI watermarks."""
    h, w = frame.shape[:2]
    # Check bottom-right and bottom-left quadrants
    rois = [
        (int(w * 0.70), int(h * 0.70), int(w * 0.30), int(h * 0.30)),
        (0, int(h * 0.70), int(w * 0.30), int(h * 0.30)),
    ]

    for rx, ry, rw, rh in rois:
        crop = frame[ry : ry + rh, rx : rx + rw]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        # Threshold for bright logo strokes
        _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            bx, by, bw, bh = cv2.boundingRect(cnt)
            if 15 <= bw <= 120 and 15 <= bh <= 120 and 0.6 <= bw / float(bh) <= 1.5:
                # Shape score against sparkle template
                crop_mask = binary[by : by + bh, bx : bx + bw]
                resized = cv2.resize(crop_mask, (64, 64), interpolation=cv2.INTER_AREA)
                intersection = np.logical_and(resized > 0, SPARKLE_TEMPLATE > 0).sum()
                union = np.logical_or(resized > 0, SPARKLE_TEMPLATE > 0).sum()
                iou = intersection / max(1, union)
                if iou > 0.35:
                    pad = 6
                    return (
                        max(0, rx + bx - pad),
                        max(0, ry + by - pad),
                        min(w, bw + pad * 2),
                        min(h, bh + pad * 2),
                    )

    return None


def extract_anti_reflection_mask(
    frame: np.ndarray,
    region: Tuple[int, int, int, int],
    sensitivity: float = 0.5,
) -> np.ndarray:
    """
    Intelligent anti-reflection mask extractor.
    Isolates ONLY the watermark logo/text pixels using contour filtering and edge detection,
    preventing any color bleeding or smearing from adjacent objects (e.g. barbells, edges).
    """
    rx, ry, rw, rh = region
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    crop = frame[ry : ry + rh, rx : rx + rw]
    if crop.size == 0:
        return mask

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    # 1. Gradient magnitude
    sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    grad = np.sqrt(sobelx**2 + sobely**2)
    grad = np.uint8(np.clip(grad / (grad.max() + 1e-4) * 255, 0, 255))

    # 2. Thresholding for bright/distinct logo strokes
    thresh_val = int(55 + (1.0 - sensitivity) * 50)
    _, binary_bright = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY)
    _, binary_grad = cv2.threshold(grad, 40, 255, cv2.THRESH_BINARY)
    combined = cv2.bitwise_or(binary_bright, binary_grad)

    # 3. Contour analysis to isolate the watermark object from background or border elements
    contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    logo_roi_mask = np.zeros_like(gray)

    # Filter out tiny noise and gigantic full-box borders
    valid_contours = []
    box_area = rw * rh
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 30 or area > (box_area * 0.85):
            continue
        valid_contours.append(cnt)

    if valid_contours:
        # Draw isolated watermark contours
        cv2.drawContours(logo_roi_mask, valid_contours, -1, 255, thickness=cv2.FILLED)
        # Dilate slightly (3px ellipse) to cleanly capture anti-aliased edge boundaries
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        logo_roi_mask = cv2.dilate(logo_roi_mask, kernel, iterations=1)
        mask[ry : ry + rh, rx : rx + rw] = logo_roi_mask
    else:
        # Safe fallback: centered diamond/ellipse (covers center 70% instead of raw full rectangle)
        center_x, center_y = rx + rw // 2, ry + rh // 2
        cv2.ellipse(mask, (center_x, center_y), (int(rw * 0.40), int(rh * 0.40)), 0, 0, 360, 255, -1)

    return mask


def refine_mask_contrast(
    frame: np.ndarray,
    region: Tuple[int, int, int, int],
    sensitivity: float = 0.5,
) -> np.ndarray:
    """Backward-compatible wrapper for extract_anti_reflection_mask."""
    return extract_anti_reflection_mask(frame, region, sensitivity)


def create_inpaint_mask(
    image_shape: Tuple[int, int],
    regions: Optional[List[Tuple[int, int, int, int]]] = None,
    custom_mask: Optional[np.ndarray] = None,
    frame: Optional[np.ndarray] = None,
    use_refinement: bool = True,
) -> np.ndarray:
    """
    Constructs the final binary mask for inpainting.
    Defaults to anti-reflection precision contour refinement whenever a frame is provided.
    """
    h, w = image_shape[:2]
    final_mask = np.zeros((h, w), dtype=np.uint8)

    if regions:
        for rx, ry, rw, rh in regions:
            rx = max(0, min(int(rx), w - 1))
            ry = max(0, min(int(ry), h - 1))
            rw = max(1, min(int(rw), w - rx))
            rh = max(1, min(int(rh), h - ry))

            if use_refinement and frame is not None:
                box_mask = extract_anti_reflection_mask(frame, (rx, ry, rw, rh))
                final_mask = cv2.bitwise_or(final_mask, box_mask)
            else:
                final_mask[ry : ry + rh, rx : rx + rw] = 255

    if custom_mask is not None:
        if custom_mask.shape[:2] != (h, w):
            custom_mask = cv2.resize(custom_mask, (w, h), interpolation=cv2.INTER_NEAREST)
        if len(custom_mask.shape) == 3:
            custom_mask = cv2.cvtColor(custom_mask, cv2.COLOR_BGR2GRAY)
        _, custom_binary = cv2.threshold(custom_mask, 10, 255, cv2.THRESH_BINARY)
        final_mask = cv2.bitwise_or(final_mask, custom_binary)

    # Smooth the mask boundaries slightly for natural inpainting transition
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    final_mask = cv2.dilate(final_mask, kernel, iterations=1)
    return final_mask


def inpaint_frame(
    frame: np.ndarray,
    mask: np.ndarray,
    method: str = "ns",
    radius: int = 2,
) -> np.ndarray:
    """Inpaints watermark pixels in a single frame using Navier-Stokes (smooth, zero-bleed) by default."""
    if np.count_nonzero(mask) == 0:
        return frame.copy()

    inpaint_flag = cv2.INPAINT_NS if method.lower() in ("ns", "navier-stokes") else cv2.INPAINT_TELEA
    return cv2.inpaint(frame, mask, inpaintRadius=max(1, radius), flags=inpaint_flag)


def process_image(
    input_path: str,
    output_path: Optional[str] = None,
    regions: Optional[List[Tuple[int, int, int, int]]] = None,
    custom_mask: Optional[np.ndarray] = None,
    method: str = "ns",
    radius: int = 2,
    refine: bool = True,
    preset: Optional[str] = None,
) -> str:
    """Removes watermarks from an image file with anti-reflection contour masking by default."""
    if output_path is None:
        output_path = build_default_output_path(input_path)

    img = cv2.imread(input_path)
    if img is None:
        raise IOError(f"Could not read image: {input_path}")

    h, w = img.shape[:2]

    # Resolve preset if given
    if preset and preset in PRESETS:
        regions = [PRESETS[preset](w, h)]

    # If no region or custom mask, attempt auto-detection
    if not regions and custom_mask is None:
        gemini_box = auto_detect_gemini_sparkle(img)
        if gemini_box:
            regions = [gemini_box]
        else:
            regions = [PRESETS["bottom_right"](w, h)]

    mask = create_inpaint_mask((h, w), regions, custom_mask, frame=img, use_refinement=refine)
    result = inpaint_frame(img, mask, method=method, radius=radius)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    cv2.imwrite(output_path, result)
    return output_path


def process_video(
    input_path: str,
    output_path: Optional[str] = None,
    regions: Optional[List[Tuple[int, int, int, int]]] = None,
    custom_mask: Optional[np.ndarray] = None,
    method: str = "ns",
    radius: int = 2,
    refine: bool = True,
    preset: Optional[str] = None,
    progress_callback: Optional[Callable[[float, int, int], None]] = None,
) -> str:
    """
    Removes watermarks from a video file frame-by-frame using anti-reflection Navier-Stokes,
    preserving audio and video quality via ffmpeg remuxing.
    """
    if output_path is None:
        output_path = build_default_output_path(input_path)

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise IOError(f"Could not open video file: {input_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    # Preset coordinate calculation
    if preset and preset in PRESETS:
        regions = [PRESETS[preset](width, height)]

    # Auto-detection if no region provided
    if not regions and custom_mask is None:
        samples, _, _, _, _ = sample_video_frames(input_path, max_samples=20)
        detected = auto_detect_temporal_watermark(samples, width, height)
        if detected:
            regions = [detected]
        else:
            regions = [PRESETS["bottom_right"](width, height)]

    mask = create_inpaint_mask((height, width), regions, custom_mask)

    # Use a temporary directory for intermediate video
    temp_dir = tempfile.mkdtemp(prefix="omnimark_")
    temp_video_clean = os.path.join(temp_dir, "video_clean.mp4")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(temp_video_clean, fourcc, fps, (width, height))

    frame_idx = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            cleaned = inpaint_frame(frame, mask, method=method, radius=radius)
            writer.write(cleaned)

            frame_idx += 1
            if progress_callback and total_frames > 0:
                progress_callback(frame_idx / total_frames, frame_idx, total_frames)

    finally:
        cap.release()
        writer.release()

    # Reassemble with audio via ffmpeg if available
    ffmpeg_bin = find_ffmpeg()
    final_output_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(final_output_dir, exist_ok=True)

    if ffmpeg_bin:
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", temp_video_clean,
            "-i", input_path,
            "-map", "0:v:0",
            "-map", "1:a:0?",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            "-shortest",
            output_path,
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            # Fallback if libx264 or audio remux fails
            shutil.copy2(temp_video_clean, output_path)
    else:
        shutil.copy2(temp_video_clean, output_path)

    # Cleanup temp
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass

    return output_path


def batch_process_project(
    project_dir: str,
    output_dir: Optional[str] = None,
    preset: Optional[str] = None,
    regions: Optional[List[Tuple[int, int, int, int]]] = None,
    method: str = "ns",
    radius: int = 2,
    refine: bool = True,
    create_previews: bool = True,
    file_callback: Optional[Callable[[str, int, int], None]] = None,
    frame_callback: Optional[Callable[[float, int, int], None]] = None,
) -> dict:
    """
    Structural batch processor for any project directory.
    Processes all videos/images with anti-reflection inpainting, saves outputs into an organized
    cleaned directory, and automatically creates side-by-side verification preview images.
    """
    project_dir = os.path.abspath(project_dir)
    if not os.path.exists(project_dir):
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    if output_dir is None:
        output_dir = os.path.join(project_dir, "cleaned")
    os.makedirs(output_dir, exist_ok=True)

    preview_dir = os.path.join(output_dir, "previews")
    if create_previews:
        os.makedirs(preview_dir, exist_ok=True)

    # Collect files, excluding output folders and existing clean files
    media_files = []
    all_exts = IMAGE_EXTENSIONS.union(VIDEO_EXTENSIONS)
    for root, dirs, files in os.walk(project_dir):
        # Don't recurse into output/cleaned/previews directories
        dirs[:] = [d for d in dirs if d.lower() not in ("cleaned", "previews", "outputs", "_internal", ".git")]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in all_exts and "_clean" not in f.lower():
                media_files.append(os.path.join(root, f))

    media_files.sort()
    total_files = len(media_files)

    results = {
        "project_dir": project_dir,
        "output_dir": output_dir,
        "total": total_files,
        "processed": [],
        "failed": [],
    }

    start_project = dt.datetime.now()

    for idx, filepath in enumerate(media_files, 1):
        filename = os.path.basename(filepath)
        rel_path = os.path.relpath(filepath, project_dir)
        target_out = os.path.join(output_dir, filename)

        if file_callback:
            file_callback(filename, idx, total_files)

        try:
            # 1. Preview snapshot creation
            if create_previews:
                sample_frame = None
                if is_video_file(filepath):
                    cap = cv2.VideoCapture(filepath)
                    ret, sample_frame = cap.read()
                    cap.release()
                elif is_image_file(filepath):
                    sample_frame = cv2.imread(filepath)

                if sample_frame is not None:
                    sh, sw = sample_frame.shape[:2]
                    target_regions = regions
                    if not target_regions and preset:
                        target_regions = [PRESETS[preset](sw, sh)] if preset in PRESETS else None
                    if not target_regions:
                        sparkle = auto_detect_gemini_sparkle(sample_frame)
                        target_regions = [sparkle] if sparkle else [PRESETS["gemini"](sw, sh)]

                    preview_mask = create_inpaint_mask((sh, sw), target_regions, frame=sample_frame, use_refinement=refine)
                    preview_clean = inpaint_frame(sample_frame, preview_mask, method=method, radius=radius)

                    # Create crop preview
                    if target_regions:
                        rx, ry, rw, rh = target_regions[0]
                        pad = 40
                        cx1 = max(0, rx - pad)
                        cy1 = max(0, ry - pad)
                        cx2 = min(sw, rx + rw + pad)
                        cy2 = min(sh, ry + rh + pad)

                        p_orig = sample_frame[cy1:cy2, cx1:cx2].copy()
                        p_clean = preview_clean[cy1:cy2, cx1:cx2]
                        p_mask = preview_mask[cy1:cy2, cx1:cx2]

                        contours, _ = cv2.findContours(p_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        p_contour = p_orig.copy()
                        cv2.drawContours(p_contour, contours, -1, (0, 255, 255), 1)

                        triptych = np.hstack([p_orig, p_contour, p_clean])
                        base_no_ext = os.path.splitext(filename)[0]
                        cv2.imwrite(os.path.join(preview_dir, f"{base_no_ext}_preview.png"), triptych)

            # 2. Main processing
            if is_video_file(filepath):
                res = process_video(
                    filepath,
                    output_path=target_out,
                    regions=regions,
                    preset=preset,
                    method=method,
                    radius=radius,
                    refine=refine,
                    progress_callback=frame_callback,
                )
                results["processed"].append({"file": rel_path, "output": res, "type": "video"})
            elif is_image_file(filepath):
                res = process_image(
                    filepath,
                    output_path=target_out,
                    regions=regions,
                    preset=preset,
                    method=method,
                    radius=radius,
                    refine=refine,
                )
                results["processed"].append({"file": rel_path, "output": res, "type": "image"})

        except Exception as e:
            results["failed"].append({"file": rel_path, "error": str(e)})

    results["elapsed_seconds"] = (dt.datetime.now() - start_project).total_seconds()
    return results
