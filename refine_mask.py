#!/usr/bin/env python3
"""
Test and refine tight watermark mask to eliminate reflection/bleeding artifacts.
"""

import os
import cv2
import numpy as np

INPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Project", "hero_video.mp4")
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Project", "hero_video_clean.mp4")
COMPARISON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Project", "hero_video_comparison_tight.png")


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

    # Threshold for bright strokes (sparkle outline & bar)
    _, binary = cv2.threshold(gray_roi, 50, 255, cv2.THRESH_BINARY)

    # Find external contours
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter for the sparkle: it has roughly square bounding box (aspect ratio 0.6 - 1.5)
    # and is located below the barbell bar (cy > bh * 0.25)
    candidate_sparkles = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 50:
            continue
        cx, cy, cw, ch = cv2.boundingRect(cnt)
        aspect = cw / float(ch) if ch > 0 else 0
        centroid_y = cy + ch / 2.0
        
        # Sparkle is roughly symmetric (aspect 0.65 - 1.45) and below the top bar (centroid_y > 20px)
        if 0.6 <= aspect <= 1.5 and centroid_y > (bh * 0.20):
            candidate_sparkles.append((area, cnt))

    if candidate_sparkles:
        # Pick the largest candidate matching the sparkle geometry
        candidate_sparkles.sort(key=lambda x: x[0], reverse=True)
        sparkle_cnt = candidate_sparkles[0][1]

        sparkle_roi_mask = np.zeros_like(binary)
        cv2.drawContours(sparkle_roi_mask, [sparkle_cnt], -1, 255, thickness=cv2.FILLED)

        # Dilate 3 pixels to fully cover the top and bottom sharp tips and anti-aliased edges
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        sparkle_roi_mask = cv2.dilate(sparkle_roi_mask, kernel, iterations=1)

        mask[by : by + bh, bx : bx + bw] = sparkle_roi_mask
    else:
        # Fallback to diamond in lower-middle of ROI
        cx, cy = bx + bw // 2, by + int(bh * 0.62)
        radius = int(min(bw, bh) * 0.32)
        cv2.circle(mask, (cx, cy), radius, 255, -1)

    return mask


def refine_and_process():
    cap = cv2.VideoCapture(INPUT_PATH)
    ret, first_frame = cap.read()
    if not ret:
        print("Cannot read video")
        return

    h, w = first_frame.shape[:2]
    search_box = (1670, 853, 124, 86)

    # Build tight mask
    tight_mask = create_tight_sparkle_mask(first_frame, search_box)

    # Compare TELEA vs Navier-Stokes with tight mask
    clean_telea = cv2.inpaint(first_frame, tight_mask, 3, cv2.INPAINT_TELEA)
    clean_ns = cv2.inpaint(first_frame, tight_mask, 3, cv2.INPAINT_NS)

    # Crop close-up for comparison
    bx, by, bw, bh = search_box
    pad = 40
    crop_x1 = max(0, bx - pad)
    crop_y1 = max(0, by - pad)
    crop_x2 = min(w, bx + bw + pad)
    crop_y2 = min(h, by + bh + pad)

    orig_crop = first_frame[crop_y1:crop_y2, crop_x1:crop_x2]
    telea_crop = clean_telea[crop_y1:crop_y2, crop_x1:crop_x2]
    ns_crop = clean_ns[crop_y1:crop_y2, crop_x1:crop_x2]
    mask_crop = cv2.cvtColor(tight_mask[crop_y1:crop_y2, crop_x1:crop_x2], cv2.COLOR_GRAY2BGR)

    # Row of: Original | Mask | Telea (Tight) | NS (Tight)
    comparison = np.hstack([orig_crop, mask_crop, telea_crop, ns_crop])
    cv2.imwrite(COMPARISON_PATH, comparison)
    print(f"Saved tight mask comparison preview to: {COMPARISON_PATH}")

    # Now process the entire video with the optimal tight mask
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(OUTPUT_PATH, fourcc, fps, (w, h))

    # Reset video to frame 0
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    frame_idx = 0

    print("Processing video with tight mask (zero reflection)...")
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Inpaint with Navier-Stokes on tight mask
        cleaned = cv2.inpaint(frame, tight_mask, 2, cv2.INPAINT_NS)
        writer.write(cleaned)

        frame_idx += 1
        if frame_idx % 20 == 0 or frame_idx == total_frames:
            pct = int((frame_idx / total_frames) * 100)
            print(f"Progress: {pct}% ({frame_idx}/{total_frames})")

    cap.release()
    writer.release()
    print(f"Successfully generated clean video without reflection: {OUTPUT_PATH}")


if __name__ == "__main__":
    refine_and_process()
