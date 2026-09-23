#!/usr/bin/env python3
"""
Test Suite for OmniMark Universal Watermark Remover
===================================================
Validates core inpainting, auto-detection, and video/image processing.
"""

import os
import shutil
import tempfile
import unittest

import cv2
import numpy as np

import watermark_engine


class TestWatermarkEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="omnimark_test_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sparkle_template(self):
        """Verify sparkle template generation."""
        tmpl = watermark_engine.SPARKLE_TEMPLATE
        self.assertEqual(tmpl.shape, (64, 64))
        self.assertGreater(np.count_nonzero(tmpl), 100)

    def test_image_inpainting_telea(self):
        """Create an image with a solid color and a prominent watermark, then inpaint it."""
        h, w = 200, 300
        # Smooth gradient background
        img = np.zeros((h, w, 3), dtype=np.uint8)
        img[:, :] = (120, 80, 50)

        # Draw a bright white watermark box in bottom-right corner
        wm_x, wm_y, wm_w, wm_h = 220, 160, 60, 30
        cv2.putText(img, "LOGO", (wm_x + 5, wm_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        input_path = os.path.join(self.test_dir, "test_input.png")
        output_path = os.path.join(self.test_dir, "test_clean.png")
        cv2.imwrite(input_path, img)

        res_path = watermark_engine.process_image(
            input_path=input_path,
            output_path=output_path,
            regions=[(wm_x, wm_y, wm_w, wm_h)],
            method="telea",
            radius=3,
        )

        self.assertTrue(os.path.exists(res_path))
        clean_img = cv2.imread(res_path)
        self.assertEqual(clean_img.shape, (h, w, 3))

        # Check that the white pixels inside the watermark region have been inpainted
        roi = clean_img[wm_y : wm_y + wm_h, wm_x : wm_x + wm_w]
        # Max brightness in ROI should no longer be 255
        max_val = roi.max()
        self.assertLess(max_val, 200, f"Watermark was not inpainted, max brightness: {max_val}")

    def test_multi_region_mask_generation(self):
        """Test multi-box mask creation."""
        shape = (400, 600)
        regions = [(10, 10, 50, 50), (500, 300, 80, 60)]
        mask = watermark_engine.create_inpaint_mask(shape, regions=regions)

        self.assertEqual(mask.shape, shape)
        self.assertGreater(np.count_nonzero(mask[10:60, 10:60]), 2000)
        self.assertGreater(np.count_nonzero(mask[300:360, 500:580]), 4000)
        self.assertEqual(np.count_nonzero(mask[150:250, 200:400]), 0)

    def test_synthetic_video_processing(self):
        """Create a short synthetic video with a static corner watermark and verify processing."""
        video_path = os.path.join(self.test_dir, "synth_video.mp4")
        w, h = 320, 240
        fps = 10
        total_frames = 15

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(video_path, fourcc, fps, (w, h))

        wm_region = (240, 190, 70, 35)

        for i in range(total_frames):
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            frame[:, :] = (30, 40, 50)
            # Moving object in center
            cv2.circle(frame, (50 + i * 10, 100), 20, (0, 255, 0), -1)
            # Static watermark in bottom right
            cv2.putText(frame, "WATERMARK", (wm_region[0], wm_region[1] + 20), cv2.FONT_HERSHEY_PLAIN, 0.8, (255, 255, 255), 1)
            writer.write(frame)
        writer.release()

        # Run process_video
        output_path = os.path.join(self.test_dir, "synth_clean.mp4")
        res = watermark_engine.process_video(
            video_path,
            output_path=output_path,
            regions=[wm_region],
            method="telea",
        )

        self.assertTrue(os.path.exists(res))
        self.assertGreater(os.path.getsize(res), 1000)

        # Verify cleaned video can be opened
        cap = cv2.VideoCapture(res)
        self.assertTrue(cap.isOpened())
        ret, frame = cap.read()
        self.assertTrue(ret)
        self.assertEqual(frame.shape, (h, w, 3))
        cap.release()


if __name__ == "__main__":
    unittest.main()
