#!/usr/bin/env python3
"""Quick DRM/KMS display sanity check.

Starts DrmKmsDisplay, pushes frames for a short duration, and reports the
producer FPS. Useful to verify 32-bit path and color output without running
the full app.
"""
import os
import sys
import time
import threading
import logging
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dashcam.core.config import config as default_config
from dashcam.platforms.pi5_arducam.video_display_drmkms import DrmKmsDisplay

logging.basicConfig(level=logging.INFO)

DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 15


def make_test_frame(width: int, height: int, t: float) -> np.ndarray:
    """Generate a simple color pattern that shifts over time."""
    # Use wider types for math to avoid overflow errors on large t
    x = np.linspace(0, 255, width, dtype=np.uint32)
    y = np.linspace(0, 255, height, dtype=np.uint32)
    xv, yv = np.meshgrid(x, y)
    t30 = np.uint32(int(t * 30) % 256)
    t60 = np.uint32(int(t * 60) % 256)
    t90 = np.uint32(int(t * 90) % 256)
    r = (xv + t30) % 256
    g = (yv + t60) % 256
    b = ((xv // 2) + (yv // 2) + t90) % 256
    frame = np.stack([r, g, b], axis=2).astype(np.uint8)
    return frame


def main():
    config = default_config
    config.display_backend = "drm"
    card_path = getattr(config, "display_drm_card", "/dev/dri/card1")

    display = DrmKmsDisplay(config, card_path=card_path)
    if not display.start():
        print("Failed to start DRM/KMS display")
        sys.exit(1)

    stop_event = threading.Event()
    frame_counter = {"count": 0}

    def producer():
        fps = max(1, int(config.display_fps or 30))
        interval = 1.0 / fps
        while not stop_event.is_set():
            t = time.time()
            frame = make_test_frame(display.width, display.height, t)
            display.update_frame(frame)
            frame_counter["count"] += 1
            time.sleep(interval)

    prod_thread = threading.Thread(target=producer, daemon=True)
    prod_thread.start()

    print(f"Running DRM/KMS display test for {DURATION}s on {card_path} ({display.width}x{display.height} @ {config.display_fps}fps target)")
    start = time.time()
    last_count = 0
    try:
        while time.time() - start < DURATION:
            time.sleep(1.0)
            sent = frame_counter["count"] - last_count
            last_count = frame_counter["count"]
            print(f"+{sent} frames pushed in last second")
    finally:
        stop_event.set()
        prod_thread.join(timeout=1.0)
        display.stop()
        elapsed = max(1e-3, time.time() - start)
        total = frame_counter["count"]
        print(f"Total frames: {total} over {elapsed:.1f}s (~{total/elapsed:.1f} fps sent)")


if __name__ == "__main__":
    main()
