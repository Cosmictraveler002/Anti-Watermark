#!/usr/bin/env python3
"""
OmniMark CLI - Universal Watermark Remover
=========================================
Command line utility to remove any watermark from videos and images.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import time

from watermark_engine import (
    IMAGE_EXTENSIONS,
    PRESETS,
    VIDEO_EXTENSIONS,
    auto_detect_gemini_sparkle,
    auto_detect_temporal_watermark,
    build_default_output_path,
    is_image_file,
    is_video_file,
    process_image,
    process_video,
    sample_video_frames,
)


def parse_region(region_str: str):
    parts = [int(p.strip()) for p in region_str.split(",")]
    if len(parts) != 4:
        raise ValueError(f"Region must be 'x,y,w,h', got '{region_str}'")
    return tuple(parts)


def print_progress(fraction: float, current: int, total: int):
    pct = int(fraction * 100)
    bar_len = 30
    filled = int(bar_len * fraction)
    bar = "█" * filled + "-" * (bar_len - filled)
    sys.stdout.write(f"\r[{bar}] {pct}% ({current}/{total} frames)")
    sys.stdout.flush()
    if current >= total:
        sys.stdout.write("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Universal Watermark Remover (OmniMark) - Remove any watermark from videos and images.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py input.mp4
  python cli.py input.mp4 --preset seedance
  python cli.py input.mp4 --region 100,50,200,80
  python cli.py input.png -o clean.png --preset gemini
  python cli.py ./videos_dir/ --batch --preset bottom_right
        """,
    )

    parser.add_argument("input", help="Path to input video, image, or folder (when --batch is used)")
    parser.add_argument("-o", "--output", help="Path to save output clean file or folder")
    parser.add_argument("-r", "--region", action="append", help="Watermark region as 'x,y,w,h'. Can be specified multiple times.")
    parser.add_argument(
        "-p",
        "--preset",
        choices=list(PRESETS.keys()),
        help="Quick watermark preset location (e.g. seedance, gemini, tiktok, bottom_right)",
    )
    parser.add_argument(
        "-m",
        "--method",
        choices=["ns", "telea"],
        default="ns",
        help="Inpainting algorithm: 'ns' (Navier-Stokes, anti-reflection) or 'telea'. Default: ns",
    )
    parser.add_argument("--radius", type=int, default=2, help="Inpainting blend radius (default: 2)")
    parser.add_argument(
        "--no-refine",
        dest="refine",
        action="store_false",
        help="Disable automatic anti-reflection contour mask refinement",
    )
    parser.set_defaults(refine=True)
    parser.add_argument("--detect-only", action="store_true", help="Only run auto-detection and print coordinates")
    parser.add_argument("--batch", action="store_true", help="Process all media files in the specified input directory")

    args = parser.parse_args()

    # Parse any manual regions
    regions = []
    if args.region:
        for r_str in args.region:
            try:
                regions.append(parse_region(r_str))
            except ValueError as e:
                print(f"Error: {e}")
                sys.exit(1)

    # Collect files
    input_path = os.path.abspath(args.input)
    if not os.path.exists(input_path):
        print(f"Error: Input path '{input_path}' does not exist.")
        sys.exit(1)

    files_to_process = []
    if args.batch or os.path.isdir(input_path):
        all_exts = IMAGE_EXTENSIONS.union(VIDEO_EXTENSIONS)
        for ext in all_exts:
            files_to_process.extend(glob.glob(os.path.join(input_path, f"*{ext}")))
            files_to_process.extend(glob.glob(os.path.join(input_path, f"*{ext.upper()}")))
        if not files_to_process:
            print(f"No supported media files found in '{input_path}'.")
            sys.exit(0)
    else:
        files_to_process = [input_path]

    print(f"Found {len(files_to_process)} file(s) to process.")

    for idx, file_path in enumerate(files_to_process, 1):
        filename = os.path.basename(file_path)
        print(f"\n[{idx}/{len(files_to_process)}] Processing: {filename}")

        if args.detect_only:
            if is_video_file(file_path):
                frames, w, h, _, _ = sample_video_frames(file_path, 20)
                box = auto_detect_temporal_watermark(frames, w, h)
                print(f"  Video dimensions: {w}x{h}")
                print(f"  Detected watermark region: {box}")
            elif is_image_file(file_path):
                import cv2
                img = cv2.imread(file_path)
                h, w = img.shape[:2]
                box = auto_detect_gemini_sparkle(img)
                print(f"  Image dimensions: {w}x{h}")
                print(f"  Detected watermark region: {box}")
            continue

        # Determine output path
        if args.output:
            if os.path.isdir(args.output) or len(files_to_process) > 1:
                os.makedirs(args.output, exist_ok=True)
                out_path = os.path.join(args.output, os.path.basename(build_default_output_path(file_path)))
            else:
                out_path = args.output
        else:
            out_path = build_default_output_path(file_path)

        start_time = time.time()
        try:
            if is_image_file(file_path):
                res = process_image(
                    file_path,
                    output_path=out_path,
                    regions=regions if regions else None,
                    method=args.method,
                    radius=args.radius,
                    refine=args.refine,
                    preset=args.preset,
                )
                elapsed = time.time() - start_time
                print(f"  ✓ Clean image saved to: {res} ({elapsed:.2f}s)")

            elif is_video_file(file_path):
                res = process_video(
                    file_path,
                    output_path=out_path,
                    regions=regions if regions else None,
                    method=args.method,
                    radius=args.radius,
                    refine=args.refine,
                    preset=args.preset,
                    progress_callback=print_progress,
                )
                elapsed = time.time() - start_time
                print(f"  ✓ Clean video saved to: {res} ({elapsed:.2f}s)")
            else:
                print(f"  Skipping unsupported file type: {filename}")

        except Exception as e:
            print(f"  ✗ Failed processing {filename}: {e}")

    print("\nAll tasks completed.")


if __name__ == "__main__":
    main()
