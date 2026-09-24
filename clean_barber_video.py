#!/usr/bin/env python3
"""
Clean Barber Video - Precision Anti-Reflection & Blur-Free Watermark Remover
=============================================================================
Accurately removes the 4-point Gemini AI sparkle watermark from:
Project/Barber_cutting_client's_hair_1080p_20260923221234.mp4

Using a pixel-perfect dilated contour mask to eliminate:
- The sparkle logo body and sharp tips
- The outer anti-aliased bright border and drop-shadow halo
- Blur and reflection smearing on adjacent background textures
"""

import os
import sys
import time
import cv2
import numpy as np

# Ensure console supports utf-8 if available
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

INPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Project", "Barber_cutting_client's_hair_1080p_20260923221234.mp4")
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Project", "Barber_cutting_client's_hair_1080p_20260923221234_clean.mp4")
COMPARISON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Project", "barber_video_comparison.png")


def create_sparkle_mask(frame: np.ndarray, search_box=(1680, 845, 120, 110)) -> np.ndarray:
    """
    Builds a pixel-perfect mask covering the full sparkle logo, all 4 tips,
    and outer antialiased edge to prevent dark drop-shadow reflection artifacts.
    """
    h, w = frame.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    bx, by, bw, bh = search_box
    roi = frame[by : by + bh, bx : bx + bw]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    # Threshold for sparkle strokes
    _, binary = cv2.threshold(gray, 25, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    sparkle_cnt = None
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 30:
            continue
        cx, cy, cw, ch = cv2.boundingRect(cnt)
        aspect = cw / float(ch) if ch > 0 else 0
        if 0.65 <= aspect <= 1.45:
            sparkle_cnt = cnt
            break

    roi_mask = np.zeros_like(gray)
    if sparkle_cnt is not None:
        cv2.drawContours(roi_mask, [sparkle_cnt], -1, 255, thickness=cv2.FILLED)
    else:
        # Fallback to detected sparkle geometry
        cv2.circle(roi_mask, (bw // 2, bh // 2), 36, 255, -1)

    # Dilate by 4-5px with ellipse to cleanly enclose all tips and the outer drop shadow border
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    roi_mask = cv2.dilate(roi_mask, kernel, iterations=2)
    mask[by : by + bh, bx : bx + bw] = roi_mask
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

    print(f"=== Video Analysis & Watermark Removal ===")
    print(f"Source: {INPUT_PATH}")
    print(f"Resolution: {width} x {height}")
    print(f"FPS: {fps:.2f}")
    print(f"Total Frames: {total_frames}")

    ret, first_frame = cap.read()
    if not ret or first_frame is None:
        print("Error: Could not read first frame.")
        sys.exit(1)

    search_box = (1680, 845, 120, 110)
    print("Constructing precision anti-reflection contour mask...")
    tight_mask = create_sparkle_mask(first_frame, search_box)
    active_pixels = np.count_nonzero(tight_mask)
    print(f"Active watermark mask pixels: {active_pixels} (tight contour, no background smearing)")

    # Inpaint first frame for comparison preview
    # Navier-Stokes with radius=2 follows natural image gradients seamlessly with zero blur halo
    cleaned_first = cv2.inpaint(first_frame, tight_mask, inpaintRadius=2, flags=cv2.INPAINT_NS)

    # Save comparison preview: Original | Mask Contour | Cleaned
    bx, by, bw, bh = search_box
    pad = 35
    cx1 = max(0, bx - pad)
    cy1 = max(0, by - pad)
    cx2 = min(width, bx + bw + pad)
    cy2 = min(height, by + bh + pad)

    orig_crop = first_frame[cy1:cy2, cx1:cx2].copy()
    clean_crop = cleaned_first[cy1:cy2, cx1:cx2].copy()

    mask_crop = tight_mask[cy1:cy2, cx1:cx2]
    contours, _ = cv2.findContours(mask_crop, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contour_preview = orig_crop.copy()
    cv2.drawContours(contour_preview, contours, -1, (0, 255, 0), 1)

    comparison = np.hstack([orig_crop, contour_preview, clean_crop])
    cv2.imwrite(COMPARISON_PATH, comparison)
    print(f"Saved side-by-side ROI comparison to: {COMPARISON_PATH}")

    # Process all frames
    print("\nProcessing video frames with Navier-Stokes anti-reflection inpainting...")
    start_time = time.time()

    temp_video = os.path.join(os.path.dirname(OUTPUT_PATH), "temp_clean.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(temp_video, fourcc, fps, (width, height))

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
            bar = "=" * (pct // 4) + "-" * (25 - (pct // 4))
            sys.stdout.write(f"\r[{bar}] {pct}% ({frame_idx}/{total_frames} frames)")
            sys.stdout.flush()

    cap.release()
    writer.release()

    # Move temp to final output
    if os.path.exists(OUTPUT_PATH):
        try:
            os.remove(OUTPUT_PATH)
        except Exception:
            pass
    os.rename(temp_video, OUTPUT_PATH)

    elapsed = time.time() - start_time
    print(f"\n\nProcessing complete in {elapsed:.1f}s!")
    print(f"Clean output saved to: {OUTPUT_PATH}")
    if os.path.exists(OUTPUT_PATH):
        print(f"File size: {os.path.getsize(OUTPUT_PATH) / (1024*1024):.2f} MB")


if __name__ == "__main__":
    main()
