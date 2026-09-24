import cv2
import numpy as np

f_orig = cv2.imread(r"Project\sample_frame_96.png")
h, w = f_orig.shape[:2]

# Watermark location: (1704, 864, 72, 72)
# Tight mask
search_box = (1680, 850, 110, 100)
bx, by, bw, bh = search_box
roi = f_orig[by:by+bh, bx:bx+bw]
gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

# Threshold for sparkle
_, binary = cv2.threshold(gray_roi, 35, 255, cv2.THRESH_BINARY)
contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

mask_roi = np.zeros_like(binary)
for cnt in contours:
    cx, cy, cw, ch = cv2.boundingRect(cnt)
    if cw > 25 and ch > 25 and 0.6 <= cw / float(ch) <= 1.5:
        cv2.drawContours(mask_roi, [cnt], -1, 255, thickness=cv2.FILLED)

# Dilate by 3 pixels
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
dilated_roi = cv2.dilate(mask_roi, kernel, iterations=1)

full_mask = np.zeros((h, w), dtype=np.uint8)
full_mask[by:by+bh, bx:bx+bw] = dilated_roi

# Inpaint with Telea
clean_telea = cv2.inpaint(f_orig, full_mask, inpaintRadius=2, flags=cv2.INPAINT_TELEA)
# Inpaint with NS
clean_ns = cv2.inpaint(f_orig, full_mask, inpaintRadius=2, flags=cv2.INPAINT_NS)

# Estimate surrounding background noise std
surround_roi = f_orig[by:by+bh, bx-60:bx]
bg_noise_std = np.std(surround_roi.astype(np.float32), axis=(0, 1)) # (3,)
print("Surround background noise std:", bg_noise_std)

# Grain addition to Telea
clean_telea_grain = clean_telea.copy()
np.random.seed(42)
noise = np.random.normal(0, bg_noise_std, (bh, bw, 3)).astype(np.float32)
# Only add to the mask area
mask_3d = (dilated_roi[:, :, None] > 0).astype(np.float32)
crop_telea = clean_telea[by:by+bh, bx:bx+bw].astype(np.float32)
blended = crop_telea + noise * mask_3d * 0.75
blended = np.clip(blended, 0, 255).astype(np.uint8)
clean_telea_grain[by:by+bh, bx:bx+bw] = blended

# Save comparisons for inspection
pad = 30
crop_x1 = bx - pad
crop_y1 = by - pad
crop_x2 = bx + bw + pad
crop_y2 = by + bh + pad

orig_c = f_orig[crop_y1:crop_y2, crop_x1:crop_x2]
telea_c = clean_telea[crop_y1:crop_y2, crop_x1:crop_x2]
ns_c = clean_ns[crop_y1:crop_y2, crop_x1:crop_x2]
grain_c = clean_telea_grain[crop_y1:crop_y2, crop_x1:crop_x2]

row = np.hstack([orig_c, telea_c, ns_c, grain_c])
cv2.imwrite(r"Project\compare_grain_telea.png", row)
print("Saved compare_grain_telea.png")
