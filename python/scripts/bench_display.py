#!/usr/bin/env python3
"""Benchmark display performance: measures process CPU% and display FPS.

Usage: python3 python/scripts/bench_display.py [duration_seconds]
"""
import time
import os
import sys
import threading
import numpy as np
import logging

# Add workspace to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dashcam.platforms.pi5_arducam.video_display import VideoDisplay
from dashcam.core.config import config as default_config

logging.basicConfig(level=logging.INFO)

DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 15

# Helper to read /proc stats
def read_proc_stat():
    with open('/proc/stat', 'r') as f:
        for line in f:
            if line.startswith('cpu '):
                parts = line.split()[1:]
                vals = [int(x) for x in parts]
                return sum(vals)
    return 0

def read_proc_self_utime_stime_ticks():
    # /proc/self/stat fields: utime is 14, stime is 15 (1-based)
    with open('/proc/self/stat', 'r') as f:
        s = f.read()
    parts = s.split()
    utime = int(parts[13])
    stime = int(parts[14])
    return utime + stime

# Prepare config copy to avoid mutating global unexpectedly
config = default_config
# Use framebuffer -> /dev/null to avoid permission issues
config.framebuffer_device = '/dev/null'

display = VideoDisplay(config)

# Start display (it will open /dev/null and spawn thread)
if not display.start():
    print('Failed to start display')
    sys.exit(1)

# Producer thread: push a static frame at camera/display fps
stop_event = threading.Event()

def producer():
    h = display.height
    w = display.width
    fps = max(1, int(display.fps))
    interval = 1.0 / fps
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    while not stop_event.is_set():
        display.update_frame(frame)
        time.sleep(interval)

prod_thread = threading.Thread(target=producer, daemon=True)
prod_thread.start()

# Measurement loop
clk_tck = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
start_sys = read_proc_stat()
start_proc = read_proc_self_utime_stime_ticks()
start_time = time.time()

samples = []
print(f'Running benchmark for {DURATION}s (display {display.width}x{display.height} @ {display.fps}fps)')

try:
    last_sys = start_sys
    last_proc = start_proc
    t0 = start_time
    while time.time() - start_time < DURATION:
        time.sleep(1.0)
        now_sys = read_proc_stat()
        now_proc = read_proc_self_utime_stime_ticks()
        dt_sys = (now_sys - last_sys) / float(clk_tck)
        dt_proc = (now_proc - last_proc) / float(clk_tck)
        # CPU usage percent of all cores combined
        cpu_percent = 0.0
        if dt_sys > 0:
            cpu_percent = (dt_proc / dt_sys) * 100.0
        stats = display.get_stats()
        actual_fps = stats.get('actual_fps', 0.0)
        samples.append((cpu_percent, actual_fps))
        print(f"Elapsed {int(time.time()-t0)}s: CPU%={cpu_percent:.1f}  display_fps={actual_fps:.1f}")
        last_sys = now_sys
        last_proc = now_proc

finally:
    stop_event.set()
    prod_thread.join(timeout=1.0)
    display.stop()

# Summary
if samples:
    avg_cpu = sum(s[0] for s in samples) / len(samples)
    avg_fps = sum(s[1] for s in samples) / len(samples)
    print('\nSummary:')
    print(f'  Average CPU%: {avg_cpu:.1f}')
    print(f'  Average display FPS: {avg_fps:.1f}')
else:
    print('No samples collected')
