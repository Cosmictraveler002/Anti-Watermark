#!/usr/bin/env python3
"""
OmniMark Local Studio Server
============================
Zero-dependency HTTP server bridging the web studio with the Python OpenCV engine.
"""

from __future__ import annotations

import base64
import datetime as dt
import email
import io
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import urllib.parse
import uuid
from http.server import HTTPServer, SimpleHTTPRequestHandler

import cv2
import numpy as np

import watermark_engine

PORT = 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Processing jobs state
JOBS = {}


class OmniMarkHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/download/"):
            filename = urllib.parse.unquote(path[len("/api/download/") :])
            file_path = os.path.join(OUTPUT_DIR, filename)
            if os.path.exists(file_path):
                self.send_response(200)
                if watermark_engine.is_image_file(file_path):
                    self.send_header("Content-Type", "image/png")
                else:
                    self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.send_header("Content-Length", str(os.path.getsize(file_path)))
                self.end_headers()
                with open(file_path, "rb") as f:
                    shutil.copyfileobj(f, self.wfile)
                return
            else:
                self.send_error(404, "File not found")
                return

        if path.startswith("/api/job/"):
            job_id = path[len("/api/job/") :]
            job = JOBS.get(job_id)
            if job:
                self._send_json(job)
            else:
                self.send_error(404, "Job not found")
            return

        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/upload":
            self._handle_upload()
        elif path == "/api/detect":
            self._handle_detect()
        elif path == "/api/preview":
            self._handle_preview()
        elif path == "/api/process":
            self._handle_process()
        else:
            self.send_error(404, "Endpoint not found")

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        return json.loads(body.decode("utf-8"))

    def _handle_upload(self):
        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            self._send_json({"error": "Expected multipart/form-data"}, status=400)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # Standard library zero-dependency multipart parsing (Python 3.8 - 3.13+)
        msg_data = f"Content-Type: {ctype}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
        msg = email.message_from_bytes(msg_data)

        file_payload = None
        orig_name = "upload.mp4"

        for part in msg.walk():
            cdisp = part.get("Content-Disposition", "")
            if 'filename=' in cdisp:
                m = re.search(r'filename="?([^";\r\n]+)"?', cdisp)
                if m:
                    orig_name = os.path.basename(m.group(1).strip())
                file_payload = part.get_payload(decode=True)
                break

        if file_payload is None:
            self._send_json({"error": "No file payload found"}, status=400)
            return

        uid = uuid.uuid4().hex[:8]
        saved_name = f"{uid}_{orig_name}"
        saved_path = os.path.join(UPLOAD_DIR, saved_name)

        with open(saved_path, "wb") as f:
            f.write(file_payload)

        is_video = watermark_engine.is_video_file(saved_path)
        is_image = watermark_engine.is_image_file(saved_path)

        metadata = {"file_id": saved_name, "filename": orig_name, "is_video": is_video, "is_image": is_image}

        if is_video:
            cap = cv2.VideoCapture(saved_path)
            metadata["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            metadata["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            metadata["fps"] = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
            metadata["total_frames"] = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            metadata["duration"] = metadata["total_frames"] / max(1.0, metadata["fps"])

            # Thumbnail from first frame
            ret, frame = cap.read()
            if ret:
                _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                metadata["thumbnail"] = "data:image/jpeg;base64," + base64.b64encode(buf).decode("utf-8")
            cap.release()

        elif is_image:
            img = cv2.imread(saved_path)
            if img is not None:
                h, w = img.shape[:2]
                metadata["width"] = w
                metadata["height"] = h
                metadata["total_frames"] = 1
                _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
                metadata["thumbnail"] = "data:image/jpeg;base64," + base64.b64encode(buf).decode("utf-8")

        self._send_json(metadata)

    def _handle_detect(self):
        data = self._read_json_body()
        file_id = data.get("file_id")
        file_path = os.path.join(UPLOAD_DIR, file_id)

        if not os.path.exists(file_path):
            self._send_json({"error": "File not found"}, status=404)
            return

        detected_regions = []
        detection_type = "none"

        if watermark_engine.is_video_file(file_path):
            frames, w, h, _, _ = watermark_engine.sample_video_frames(file_path, 20)
            box = watermark_engine.auto_detect_temporal_watermark(frames, w, h)
            if box:
                detected_regions.append({"x": box[0], "y": box[1], "w": box[2], "h": box[3]})
                detection_type = "temporal_corner"
        elif watermark_engine.is_image_file(file_path):
            img = cv2.imread(file_path)
            box = watermark_engine.auto_detect_gemini_sparkle(img)
            if box:
                detected_regions.append({"x": box[0], "y": box[1], "w": box[2], "h": box[3]})
                detection_type = "gemini_sparkle"

        self._send_json({"regions": detected_regions, "detection_type": detection_type})

    def _handle_preview(self):
        data = self._read_json_body()
        file_id = data.get("file_id")
        frame_idx = data.get("frame_idx", 0)
        regions_data = data.get("regions", [])
        method = data.get("method", "telea")
        radius = data.get("radius", 3)
        custom_mask_b64 = data.get("mask_base64")

        file_path = os.path.join(UPLOAD_DIR, file_id)
        if not os.path.exists(file_path):
            self._send_json({"error": "File not found"}, status=404)
            return

        frame = None
        if watermark_engine.is_video_file(file_path):
            cap = cv2.VideoCapture(file_path)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            cap.release()
        elif watermark_engine.is_image_file(file_path):
            frame = cv2.imread(file_path)

        if frame is None:
            self._send_json({"error": "Could not read frame"}, status=500)
            return

        h, w = frame.shape[:2]
        regions = [(r["x"], r["y"], r["w"], r["h"]) for r in regions_data]

        custom_mask = None
        if custom_mask_b64:
            if "," in custom_mask_b64:
                custom_mask_b64 = custom_mask_b64.split(",")[1]
            raw_mask = base64.b64decode(custom_mask_b64)
            arr = np.frombuffer(raw_mask, dtype=np.uint8)
            custom_mask = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)

        mask = watermark_engine.create_inpaint_mask((h, w), regions=regions, custom_mask=custom_mask)
        cleaned = watermark_engine.inpaint_frame(frame, mask, method=method, radius=radius)

        _, buf_orig = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        _, buf_clean = cv2.imencode(".jpg", cleaned, [cv2.IMWRITE_JPEG_QUALITY, 85])

        self._send_json(
            {
                "original": "data:image/jpeg;base64," + base64.b64encode(buf_orig).decode("utf-8"),
                "cleaned": "data:image/jpeg;base64," + base64.b64encode(buf_clean).decode("utf-8"),
            }
        )

    def _handle_process(self):
        data = self._read_json_body()
        file_id = data.get("file_id")
        regions_data = data.get("regions", [])
        method = data.get("method", "ns")
        radius = data.get("radius", 2)
        refine = data.get("refine", True)

        file_path = os.path.join(UPLOAD_DIR, file_id)
        if not os.path.exists(file_path):
            self._send_json({"error": "File not found"}, status=404)
            return

        job_id = uuid.uuid4().hex[:10]
        JOBS[job_id] = {
            "status": "processing",
            "progress": 0.0,
            "current_frame": 0,
            "total_frames": 1,
            "output_file": None,
        }

        regions = [(r["x"], r["y"], r["w"], r["h"]) for r in regions_data]

        def run_job():
            try:
                base_name = os.path.splitext(file_id)[0]
                ext = os.path.splitext(file_path)[1]
                stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
                out_name = f"{base_name}_clean_{stamp}{ext}"
                out_path = os.path.join(OUTPUT_DIR, out_name)

                if watermark_engine.is_image_file(file_path):
                    res = watermark_engine.process_image(
                        file_path,
                        output_path=out_path,
                        regions=regions,
                        method=method,
                        radius=radius,
                        refine=refine,
                    )
                    JOBS[job_id]["status"] = "completed"
                    JOBS[job_id]["progress"] = 1.0
                    JOBS[job_id]["output_file"] = os.path.basename(res)

                elif watermark_engine.is_video_file(file_path):
                    def cb(frac, cur, tot):
                        JOBS[job_id]["progress"] = round(frac, 3)
                        JOBS[job_id]["current_frame"] = cur
                        JOBS[job_id]["total_frames"] = tot

                    res = watermark_engine.process_video(
                        file_path,
                        output_path=out_path,
                        regions=regions,
                        method=method,
                        radius=radius,
                        refine=refine,
                        progress_callback=cb,
                    )
                    JOBS[job_id]["status"] = "completed"
                    JOBS[job_id]["progress"] = 1.0
                    JOBS[job_id]["output_file"] = os.path.basename(res)

            except Exception as e:
                JOBS[job_id]["status"] = "failed"
                JOBS[job_id]["error"] = str(e)

        thread = threading.Thread(target=run_job, daemon=True)
        thread.start()

        self._send_json({"job_id": job_id})


def run_server():
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, OmniMarkHandler)
    print(f"=====================================================")
    print(f" OmniMark Universal Watermark Remover Studio Running")
    print(f" URL: http://localhost:{PORT}")
    print(f"=====================================================")
    httpd.serve_forever()


if __name__ == "__main__":
    run_server()
