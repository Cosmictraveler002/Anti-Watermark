import cv2
import numpy as np
import os
import json

video_path = os.path.join(os.path.dirname(__file__), "Project", "Barber_cutting_client's_hair_1080p_20260923221234.mp4")
out_dir = os.path.join(os.path.dirname(__file__), "Project")

cap = cv2.VideoCapture(video_path)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
fps = cap.get(cv2.CAP_PROP_FPS)

print(f"Video info: {width}x{height}, {fps} fps, {total_frames} frames")

# Read frame 0, 50, 100, 150
frames = []
indices = [0, total_frames // 4, total_frames // 2, 3 * total_frames // 4]
saved_frames = {}

for idx in range(total_frames):
    ret, frame = cap.read()
    if not ret:
        break
    if idx in indices:
        f_name = os.path.join(out_dir, f"sample_frame_{idx}.png")
        cv2.imwrite(f_name, frame)
        saved_frames[idx] = f_name
        frames.append(frame)
cap.release()

print(f"Saved sample frames: {saved_frames}")

# Check 4 corners and bottom center to see where static or high contrast logo exists
# Compare frame[0] and frame[-1] difference in corners
if len(frames) >= 2:
    f1 = frames[0]
    f2 = frames[-1]
    diff = cv2.absdiff(f1, f2)
    gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    
    # Static elements will have very low difference between frames, but high contrast against background
    # Let's check std deviation across frames
    stack = np.stack(frames, axis=0) # (N, H, W, C)
    std_map = np.std(stack.astype(np.float32), axis=0).mean(axis=2) # (H, W)
    
    # Also save corner crops of frame 0:
    # Top-Left, Top-Right, Bottom-Left, Bottom-Right
    corners = {
        "top_left": (0, 0, int(width * 0.3), int(height * 0.2)),
        "top_right": (int(width * 0.7), 0, int(width * 0.3), int(height * 0.2)),
        "bottom_left": (0, int(height * 0.8), int(width * 0.3), int(height * 0.2)),
        "bottom_right": (int(width * 0.7), int(height * 0.8), int(width * 0.3), int(height * 0.2)),
        "bottom_center": (int(width * 0.3), int(height * 0.85), int(width * 0.4), int(height * 0.15)),
    }
    
    for name, (x, y, w, h) in corners.items():
        crop = f1[y:y+h, x:x+w]
        std_crop = std_map[y:y+h, x:x+w]
        mean_std = float(np.mean(std_crop))
        cv2.imwrite(os.path.join(out_dir, f"corner_{name}.png"), crop)
        print(f"Corner {name} (x={x}, y={y}, w={w}, h={h}): mean temporal std = {mean_std:.2f}")

print("Analysis script finished successfully.")
