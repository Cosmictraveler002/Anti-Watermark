#!/usr/bin/env python3
"""
OmniMark Project Processor
==========================
Structural batch watermark remover for entire project directories.
Automates watermark detection, anti-reflection contour masking,
Navier-Stokes inpainting, lossless audio remuxing, and preview generation.

Usage:
  python process_project.py Project/
  python process_project.py /path/to/folder -o /path/to/cleaned/
  python process_project.py Project/ --preset gemini
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import watermark_engine


def print_banner():
    print("=" * 65)
    print("  OmniMark - Universal Project Watermark Remover")
    print("  Engine: Anti-Reflection Contour Masking + Navier-Stokes")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(
        description="Batch remove watermarks from an entire project directory with anti-reflection inpainting.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default="Project",
        help="Path to project directory containing videos and images (default: 'Project')",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Destination directory for cleaned files (default: <directory>/cleaned/)",
    )
    parser.add_argument(
        "-p",
        "--preset",
        choices=list(watermark_engine.PRESETS.keys()),
        default="gemini",
        help="Watermark preset location (default: gemini)",
    )
    parser.add_argument(
        "-m",
        "--method",
        choices=["ns", "telea"],
        default="ns",
        help="Inpainting method: 'ns' (Navier-Stokes, anti-reflection) or 'telea'. Default: ns",
    )
    parser.add_argument(
        "--radius",
        type=int,
        default=2,
        help="Inpainting blend radius in pixels (default: 2)",
    )
    parser.add_argument(
        "--no-previews",
        action="store_true",
        help="Disable automatic side-by-side verification preview image generation",
    )

    args = parser.parse_args()
    target_dir = os.path.abspath(args.directory)

    if not os.path.exists(target_dir):
        print(f"Error: Directory '{target_dir}' does not exist.")
        sys.exit(1)

    output_dir = os.path.abspath(args.output) if args.output else os.path.join(target_dir, "cleaned")
    preview_dir = os.path.join(output_dir, "previews")

    print_banner()
    print(f"Target Directory: {target_dir}")
    print(f"Output Directory: {output_dir}")
    print(f"Preset / Model:   {args.preset}")
    print(f"Inpainting Engine: {args.method.upper()} (Radius: {args.radius}px, Anti-Reflection: ON)")
    print(f"Verification:     {'Side-by-side previews in ' + preview_dir if not args.no_previews else 'Disabled'}")
    print("-" * 65)

    current_file_idx = [0]
    total_file_count = [0]
    file_start_time = [time.time()]

    def on_file(filename: str, idx: int, total: int):
        current_file_idx[0] = idx
        total_file_count[0] = total
        file_start_time[0] = time.time()
        print(f"\n[{idx}/{total}] Processing: {filename}")

    def on_frame(fraction: float, cur: int, tot: int):
        pct = int(fraction * 100)
        bar_len = 25
        filled = int(bar_len * fraction)
        bar = "█" * filled + "-" * (bar_len - filled)
        sys.stdout.write(f"\r    [{bar}] {pct}% ({cur}/{tot} frames)")
        sys.stdout.flush()
        if cur >= tot:
            elapsed = time.time() - file_start_time[0]
            sys.stdout.write(f"  ✓ Done ({elapsed:.1f}s)\n")

    results = watermark_engine.batch_process_project(
        project_dir=target_dir,
        output_dir=output_dir,
        preset=args.preset,
        method=args.method,
        radius=args.radius,
        refine=True,
        create_previews=not args.no_previews,
        file_callback=on_file,
        frame_callback=on_frame,
    )

    print("\n" + "=" * 65)
    print("  PROJECT BATCH SUMMARY")
    print("=" * 65)
    print(f"Total media files found:     {results['total']}")
    print(f"Successfully processed:      {len(results['processed'])}")
    print(f"Failed:                      {len(results['failed'])}")
    print(f"Total time elapsed:          {results.get('elapsed_seconds', 0):.1f}s")
    print(f"Clean files saved in:        {output_dir}")
    if not args.no_previews:
        print(f"Verification previews in:    {preview_dir}")
    print("=" * 65)


if __name__ == "__main__":
    main()
