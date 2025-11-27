# GPU Display Notes (Pi 5 + Arducam)

Working notes on exploring GPU-accelerated display/overlays for the dashcam. Current implementation is CPU blit into a DRM dumb buffer; no GPU composition yet.

## What we measured/observed
- Capture config (display camera): `lores` stream is `BGR888` 1920x1080 @ 15 fps with 6 buffers; `main` is `YUV420` 1920x1080 for encoding.
- Display path (`python/dashcam/platforms/pi5_arducam/video_display_drmkms.py`) takes a NumPy frame and packs RGB → XRGB8888 into a mapped dumb buffer; no dmabuf import or GL usage.
- Picamera2 build exposes `make_buffer/make_array` only; `export_buffer` is missing. Probe shows `lores` arrays as `(1080, 1920, 3) uint8`.
- Runtime timings (steady state) at 15 fps: overlay ~2 ms, blend ~1 ms, blit ~4–5 ms, “other” ~59–61 ms (matches 15 fps cadence). First frame spike is numba JIT.
- Buffering: 6 buffers per stream implies at least triple buffering in the capture path; can add a frame of latency if fences are loose.

## Implications for GPU work
- Without `export_buffer`, there is no direct dmabuf path from picamera2 → GL/DRM in Python; current path requires a CPU copy/upload.
- GPU can still help for overlays and composition, but to get zero-copy and cut a frame of cost we need dmabuf export/import.
- The biggest latency anchor is the 15 fps cadence and buffering; CPU overlay/blit is not the dominant cost once warmed.

## Future options
1) Upgrade picamera2/libcamera to a build with `export_buffer` (dmabuf) support, then import PRIME fds into GL ES via EGL/gbm and render a textured quad + overlays with blending.
2) Add a small native helper (C/Cython) to export libcamera buffers to fds for Python if upgrading is impractical.
3) Interim: keep one copy/upload and move to GL ES for composition/overlays; still frees CPU, but not zero-copy.
4) Reduce buffering if stable (double-buffer display path) and fence explicitly to avoid hidden queuing.

## Useful probes/commands
- Picamera2 dmabuf check (current result: `export_buffer` missing):
  - `Attrs with 'buffer': ['make_buffer']`
  - `export_buffer(lores)` → AttributeError
  - `lores array: (1080, 1920, 3) uint8`
- Frame characteristics to log in display loop to confirm stream: shape/dtype after `update_frame` or at `_display_loop` entry.

## When revisiting
- Decide whether to chase dmabuf support (upgrade vs helper).
- If dmabuf is available: switch display to main YUV420 or lores dmabuf, import into GL, render fullscreen quad, draw translucent HUD with blending, present via DRM/KMS.
- Instrument glass-to-glass: timestamps at capture, pre-submit, and pageflip; test double vs triple buffering and vsync behavior.

## Future GPU vision use case: yellow flag detection
- Goal: on-device marshal flag detection on the front feed to warn the driver about yellow conditions.
- Model: tiny detector (YOLOv5n/YOLOv8n/MobileNet-SSD) trained on yellow flags; optionally add a simple motion cue (optical flow or bounding box delta) to boost confidence for waving vs static.
- Runtime: run at reduced input size (e.g., 416–512 px wide), batch=1, quantized (FP16/INT8) via ONNX Runtime or OpenCV DNN with Vulkan; target <10–15 ms per frame to coexist with the current pipeline.
- Data: collect/curate marshal flag clips from onboard footage; include lighting/rain/motion-blur augmentations and negatives (cones, hi-vis vests, banners) to suppress false positives.
- Alerting: debounce over N consecutive frames before alert; add cooldown and confidence threshold; output could be HUD overlay, short beep, and/or CAN message.
- Integration path: prototype offline on recorded laps to measure false alarms and FPS; if acceptable, gate live alerts behind thresholds and keep preprocessing minimal to avoid extra CPU copies.
