import os
import sys
from watermark_engine import process_video

input_path = os.path.join(os.path.dirname(__file__), "Project", "Barber_cutting_client's_hair_1080p_20260923221234.mp4")
output_path = os.path.join(os.path.dirname(__file__), "Project", "Barber_cutting_client's_hair_1080p_20260923221234_clean.mp4")

print(f"Processing input file: {input_path}")

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def print_progress(fraction: float, current: int, total: int):
    pct = int(fraction * 100)
    bar_len = 30
    filled = int(bar_len * fraction)
    bar = "=" * filled + "-" * (bar_len - filled)
    sys.stdout.write(f"\r[{bar}] {pct}% ({current}/{total} frames)")
    sys.stdout.flush()
    if current >= total:
        sys.stdout.write("\n")

if __name__ == "__main__":
    res = process_video(input_path, output_path=output_path, progress_callback=print_progress)
    print(f"\nDone! Clean video saved to: {res}")
