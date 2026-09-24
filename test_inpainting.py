import cv2
import numpy as np
import os

sample_files = [
    r"Project\sample_frame_0.png",
    r"Project\sample_frame_48.png",
    r"Project\sample_frame_96.png",
    r"Project\sample_frame_144.png"
]

img = cv2.imread(sample_files[0])
h, w = img.shape[:2]

# The watermark is at (1704, 864, 72, 72)
# Let's extract the mask accurately from the difference between the watermark and surrounding background
# On frame 0:
crop = cv2.imread(sample_files[0])[864:864+72, 1704:1704+72]
gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

# The watermark interior is > 20, but the dark border is around the edge.
# If we threshold > 15:
_, raw_mask = cv2.threshold(gray, 15, 255, cv2.THRESH_BINARY)
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
closed_mask = cv2.morphologyEx(raw_mask, cv2.MORPH_CLOSE, kernel)

# Dilate by 3, 4, 5 pixels to test which one completely covers the dark shadow border
dilated_3 = cv2.dilate(closed_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), iterations=2)
dilated_4 = cv2.dilate(closed_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), iterations=3)

# Test on frame 96 (which has the background lighting)
f96 = cv2.imread(sample_files[2])

for d_name, d_mask in [("dil3", dilated_3), ("dil4", dilated_4)]:
    full_mask = np.zeros((h, w), dtype=np.uint8)
    full_mask[864:864+72, 1704:1704+72] = d_mask
    
    for method_name, method_flag in [("telea", cv2.INPAINT_TELEA), ("ns", cv2.INPAINT_NS)]:
        for rad in [1, 2, 3]:
            res = cv2.inpaint(f96, full_mask, inpaintRadius=rad, flags=method_flag)
            crop_res = res[840:960, 1680:1800]
            out_file = f"Project\\eval_{d_name}_{method_name}_r{rad}.png"
            cv2.imwrite(out_file, crop_res)

print("Evaluation images saved.")
