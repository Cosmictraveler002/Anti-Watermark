# OmniMark - Universal Watermark Remover

> AI-Powered Universal Watermark Remover for **Videos** and **Images**.  
> Inspired by and expanding upon [bakhtiersizhaev/seedance-watermark-remover](https://github.com/bakhtiersizhaev/seedance-watermark-remover).

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![OpenCV](https://img.shields.io/badge/opencv-4.8+-red.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)

---

## What is OmniMark?

While the original `seedance-watermark-remover` focused exclusively on corner logos and Seedance/Gemini badges in video files, **OmniMark Universal Watermark Remover** is an all-in-one studio and engine designed to remove **any watermark from any video or image**:

- **Any Position**: Corners, center marks, diagonal watermarks, bottom subtitles, top banners, timestamps, or scrolling tickers.
- **Any Media Format**: 
  - **Videos**: MP4, WebM, MOV, AVI, MKV, FLV, WMV
  - **Images**: PNG, JPG, JPEG, WEBP, BMP, TIFF
- **Multiple Watermarks**: Remove multiple logos at the same time (e.g. top-right channel logo + bottom-left username).
- **Freehand Brush & Eraser**: Paint directly over irregular, curved, or handwriting-style watermarks.
- **Lossless Audio Preservation**: Remuxes original audio streams directly using FFmpeg.
- **Two Inpainting Engines**:
  - **Fast Marching (TELEA)**: Ideal for sharp fonts, sharp corner badges, and geometric symbols.
  - **Navier-Stokes (NS)**: Ideal for smooth gradient backgrounds, natural scenes, and photographic textures.
- **Contrast-Aware Mask Refinement**: Automatically detects sharp watermark edges within the bounding box, preserving untouched background pixels.
- **Interactive Visual Studio**: A modern dark-mode browser interface featuring live video timeline scrubbing, before/after split-screen comparison, and instant client-side preview.

---

## Quick Presets Included

OmniMark comes with pre-calibrated bounding box templates for popular AI generation platforms and social media:

| Preset | Target Platform | Description |
| :--- | :--- | :--- |
| `seedance` | Seedance / Dreamina | Bottom-right / bottom-left label badge |
| `gemini` | Google Gemini AI | 4-point sparkle logo geometry template |
| `tiktok` | TikTok / Reels / Douyin | Top-right and bottom-right floating badge |
| `bottom_right` | Standard Corner Mark | Universal bottom-right corner bounding box |
| `bottom_left` | Standard Corner Mark | Universal bottom-left corner bounding box |
| `top_right` | TV / Channel Logo | Universal top-right broadcaster logo |
| `bottom_center` | Subtitles / Tickers | Full bottom subtitle and caption bar |
| `center` | Stock Previews | Center translucent watermark fill |

---

## Quick Start

### 1. Installation

Clone or open the project directory and install the requirements:

```bash
pip install -r requirements.txt
```

*(Optional)* Install [FFmpeg](https://ffmpeg.org/download.html) and ensure it is on your system PATH for lossless audio remuxing in videos.

---

### 2. Launch the Web Studio

Run the local studio server:

```bash
python server.py
```

Open your browser at `http://localhost:8080`.

- Drag and drop any video or image.
- Drag rectangles or paint with the brush tool over the watermarks.
- Click **"Preview Frame Removal"** to drag the interactive Before/After comparison slider.
- Click **"Remove & Export File"** to download the clean media.

---

### 3. Structural Project Batch Processor (`process_project.py`)

Process any project directory containing multiple videos/images with automatic anti-reflection contour masking and side-by-side verification preview snapshots:

```bash
# Process default 'Project/' directory
python process_project.py

# Process custom project directory
python process_project.py Project/ -o Project/cleaned/

# Specify preset
python process_project.py Project/ --preset gemini
```

- **Outputs**: Cleaned videos and images saved to `Project/cleaned/`.
- **Visual Verification**: Side-by-side ROI comparison snapshots automatically saved to `Project/cleaned/previews/` for instant QA.

---

### 4. Command Line Interface (CLI)

Use `cli.py` for individual or headless batch watermark removal:

#### Basic Video Clean with Anti-Reflection Navier-Stokes
```bash
python cli.py video.mp4
```

#### Using a Preset
```bash
python cli.py clip.mp4 --preset seedance -o clean_clip.mp4
python cli.py photo.png --preset gemini -o clean_photo.png
```

#### Specifying Exact Coordinates (`x,y,width,height`)
```bash
python cli.py input.mp4 -r 100,50,200,60
```

#### Removing Multiple Watermarks at Once
```bash
python cli.py input.mp4 -r 20,20,120,40 -r 850,650,150,50
```

#### Batch Processing an Entire Folder
```bash
python cli.py ./videos_folder/ --batch --preset bottom_right -o ./cleaned_videos/
```

#### CLI Flags Reference

| Flag | Argument | Description |
| :--- | :--- | :--- |
| `input` | `path` | Path to input video, image, or folder |
| `-o`, `--output` | `path` | Target output path or directory |
| `-r`, `--region` | `x,y,w,h` | Bounding box coordinates (can repeat `-r` multiple times) |
| `-p`, `--preset` | `name` | Quick preset (`seedance`, `gemini`, `tiktok`, `bottom_right`, etc.) |
| `-m`, `--method` | `telea` \| `ns` | Inpainting algorithm (default: `telea`) |
| `--radius` | `int` | Blend blur radius in pixels (default: `3`) |
| `--refine` | *flag* | Refine mask with contrast/edge thresholding |
| `--batch` | *flag* | Process all media files in the given directory |
| `--detect-only` | *flag* | Print detected watermark coordinates without processing |

---

### 4. Python API Usage

You can also import OmniMark directly into your own Python scripts:

```python
from watermark_engine import process_video, process_image

# Clean an image
process_image(
    input_path="screenshot.png",
    output_path="clean_screenshot.png",
    regions=[(800, 500, 160, 40)],
    method="telea"
)

# Clean a video with progress monitoring
def on_progress(fraction, current_frame, total_frames):
    print(f"Processing: {fraction * 100:.1f}%")

process_video(
    input_path="input.mp4",
    output_path="output_clean.mp4",
    preset="seedance",
    progress_callback=on_progress
)
```

---

## File Structure

```
Watermaker reamover/
├── watermark_engine.py    # Core removal engine, temporal detection, OpenCV inpainting
├── cli.py                 # Command line utility with multi-box and batch options
├── server.py              # Zero-dependency local studio HTTP/REST server
├── index.html             # Visual Web Studio user interface
├── app.css                # Dark-mode glassmorphic interface styles
├── app.js                 # Interactive canvas bounding box & brush controls
├── test_engine.py         # Automated test suite
├── requirements.txt       # Python dependencies (numpy, opencv-python, pillow)
└── README.md              # Project documentation
```

---

## License

MIT License. Free for personal and commercial use.
