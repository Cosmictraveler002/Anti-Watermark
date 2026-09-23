#!/usr/bin/env python3
"""
Clean Hero Video - Dedicated Execution Script (High Quality, Anti-Reflection)
=============================================================================
Removes the 4-point Gemini AI sparkle watermark from Project/hero_video.mp4
using a precision contour mask that isolates ONLY the logo pixels, completely
eliminating any reflection or color-bleed from the barbell bar.
"""

import os
import sys
import time
import cv2
import numpy as np

import watermark_engine

INPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Project", "hero_video.mp4")
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Project", "hero_video_clean.mp4")
BEFORE_AFTER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Project", "hero_video_comparison.png")


def create_tight_sparkle_mask(frame: np.ndarray, search_box=(1670, 853, 124, 86)) -> np.ndarray:
    """
    Creates a pixel-perfect mask of ONLY the sparkle logo,
    capturing all 4 tips completely while excluding the barbell bar and dark background.
    """
    h, w = frame.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)

    bx, by, bw, bh = search_box
    roi = frame[by : by + bh, bx : bx + bw]
    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    # Threshold for bright strokes
    _, binary = cv2.threshold(gray_roi, 50, 255, cv2.THRESH_BINARY)

    # Find external contours
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    candidate_sparkles = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 50:
            continue
        cx, cy, cw, ch = cv2.boundingRect(cnt)
        aspect = cw / float(ch) if ch > 0 else 0
        centroid_y = cy + ch / 2.0
        
        # Sparkle has aspect ratio ~ 1.0 (symmetric 4-pointed star) and centroid below the bar
        if 0.6 <= aspect <= 1.5 and centroid_y > (bh * 0.20):
            candidate_sparkles.append((area, cnt))

    if candidate_sparkles:
        candidate_sparkles.sort(key=lambda x: x[0], reverse=True)
        sparkle_cnt = candidate_sparkles[0][1]

        sparkle_roi_mask = np.zeros_like(binary)
        cv2.drawContours(sparkle_roi_mask, [sparkle_cnt], -1, 255, thickness=cv2.FILLED)

        # Dilate 3 pixels to fully cover the sharp tips and anti-aliased edge boundaries
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        sparkle_roi_mask = cv2.dilate(sparkle_roi_mask, kernel, iterations=1)

        mask[by : by + bh, bx : bx + bw] = sparkle_roi_mask
    else:
        # Fallback to diamond
        cx, cy = bx + bw // 2, by + int(bh * 0.62)
        radius = int(min(bw, bh) * 0.32)
        cv2.circle(mask, (cx, cy), radius, 255, -1)

    return mask


def main():
    if not os.path.exists(INPUT_PATH):
        print(f"Error: Input video not found at: {INPUT_PATH}")
        sys.exit(1)

    cap = cv2.VideoCapture(INPUT_PATH)
    if not cap.isOpened():
        print(f"Error: Unable to open video: {INPUT_PATH}")
        sys.exit(1)

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"=== Video Information ===")
    print(f"Source: {INPUT_PATH}")
    print(f"Resolution: {width} x {height}")
    print(f"FPS: {fps:.2f}")
    print(f"Total Frames: {total_frames} (~{total_frames/fps:.1f}s)")

    # Read first frame
    ret, first_frame = cap.read()
    if not ret or first_frame is None:
        print("Error: Could not read first frame.")
        sys.exit(1)

    # Search region where sparkle is located
    search_box = (1670, 853, 124, 86)
    
    # 1. Build tight contour mask (isolates ONLY logo strokes, ignores bar and background)
    print("Generating precision contour mask (excluding barbell bar and background)...")
    tight_mask = create_tight_sparkle_mask(first_frame, search_box)
    mask_pixel_count = np.count_nonzero(tight_mask)
    print(f"Mask active pixels: {mask_pixel_count} (tight logo contour)")

    # Inpaint using Navier-Stokes with radius 2 for smooth texture matching without light bleed
    cleaned_frame = cv2.inpaint(first_frame, tight_mask, inpaintRadius=2, flags=cv2.INPAINT_NS)

    # Save side-by-side ROI comparison preview: Original | Mask Outline | Cleaned (No Reflection)
    bx, by, bw, bh = search_box
    pad = 40
    crop_x1 = max(0, bx - pad)
    crop_y1 = max(0, by - pad)
    crop_x2 = min(width, bx + bw + pad)
    crop_y2 = min(height, by + bh + pad)

    orig_crop = first_frame[crop_y1:crop_y2, crop_x1:crop_x2].copy()
    clean_crop = cleaned_frame[crop_y1:crop_y2, crop_x1:crop_x2]
    
    # Highlight the tight mask contour on original for visual inspection
    mask_roi = tight_mask[crop_y1:crop_y2, crop_x1:crop_x2]
    contours, _ = cv2.findContours(mask_roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contour_preview = orig_crop.copy()
    cv2.drawContours(contour_preview, contours, -1, (0, 255, 255), 1)

    comparison = np.hstack([orig_crop, contour_preview, clean_crop])
    cv2.imwrite(BEFORE_AFTER_PATH, comparison)
    print(f"Saved side-by-side ROI comparison preview: {BEFORE_AFTER_PATH}")

    # 2. Process complete video
    print("\nProcessing video frames with anti-reflection inpainting...")
    start_time = time.time()

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(OUTPUT_PATH, fourcc, fps, (width, height))

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        cleaned = cv2.inpaint(frame, tight_mask, inpaintRadius=2, flags=cv2.INPAINT_NS)
        writer.write(cleaned)

        frame_idx += 1
        if frame_idx % 10 == 0 or frame_idx == total_frames:
            pct = int((frame_idx / total_frames) * 100)
            bar = "█" * (pct // 4) + "-" * (25 - (pct // 4))
            sys.stdout.write(f"\r[{bar}] {pct}% ({frame_idx}/{total_frames} frames)")
            sys.stdout.flush()

    cap.release()
    writer.release()

    elapsed = time.time() - start_time
    print(f"\n\nProcessing complete in {elapsed:.1f}s!")
    print(f"Clean output saved to: {OUTPUT_PATH}")
    if os.path.exists(OUTPUT_PATH):
        print(f"File size: {os.path.getsize(OUTPUT_PATH) / (1024*1024):.2f} MB")


if __name__ == "__main__":
    main()
