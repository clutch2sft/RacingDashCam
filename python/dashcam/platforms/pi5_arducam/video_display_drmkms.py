"""
Experimental DRM/KMS display backend for Pi 5
Bypasses fbdev/fb0 by allocating a 32-bit dumb buffer and writing via KMS.

This mirrors the public API of the existing VideoDisplay class enough to drop
in later, but is intentionally not wired up yet. It selects the first connected
HDMI connector, creates an XRGB8888 framebuffer, sets a CRTC, and blits frames
into the mapped buffer. Overlay rendering is kept minimal (time/date/speed/rec)
and reuses the cached overlay approach from the fbdev implementation.
"""

import logging
import os
import fcntl
import mmap
import ctypes
import time
from datetime import datetime
from threading import Thread, Event, Lock
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from numba import jit


# ---------------------------------------------------------------------------
# DRM/KMS definitions (ctypes bindings to libdrm)
# ---------------------------------------------------------------------------

libdrm = ctypes.CDLL("libdrm.so.2")

# ioctl bitfields (from linux/ioctl.h)
IOC_NRBITS = 8
IOC_TYPEBITS = 8
IOC_SIZEBITS = 14
IOC_DIRBITS = 2

IOC_NRSHIFT = 0
IOC_TYPESHIFT = IOC_NRSHIFT + IOC_NRBITS
IOC_SIZESHIFT = IOC_TYPESHIFT + IOC_TYPEBITS
IOC_DIRSHIFT = IOC_SIZESHIFT + IOC_SIZEBITS

IOC_NONE = 0
IOC_WRITE = 1
IOC_READ = 2


def _IOC(direction, ioc_type, nr, size):
    return (
        (direction << IOC_DIRSHIFT)
        | (ioc_type << IOC_TYPESHIFT)
        | (nr << IOC_NRSHIFT)
        | (size << IOC_SIZESHIFT)
    )


def _IOWR(ioc_type, nr, struct):
    return _IOC(IOC_READ | IOC_WRITE, ioc_type, nr, ctypes.sizeof(struct))


DRM_IOCTL_BASE = ord("d")


@jit(nopython=True, cache=True, parallel=False)
def pack_xrgb8888_jit(frame, output):
    """Pack RGB888 frame into XRGB8888 format (numba-accelerated)."""
    height, width = frame.shape[0], frame.shape[1]
    for y in range(height):
        for x in range(width):
            r = frame[y, x, 0]
            g = frame[y, x, 1]
            b = frame[y, x, 2]
            output[y, x] = (r << 16) | (g << 8) | b


class drm_mode_create_dumb(ctypes.Structure):
    _fields_ = [
        ("height", ctypes.c_uint32),
        ("width", ctypes.c_uint32),
        ("bpp", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("handle", ctypes.c_uint32),
        ("pitch", ctypes.c_uint32),
        ("size", ctypes.c_uint64),
    ]


class drm_mode_map_dumb(ctypes.Structure):
    _fields_ = [
        ("handle", ctypes.c_uint32),
        ("pad", ctypes.c_uint32),
        ("offset", ctypes.c_uint64),
    ]


class drm_mode_destroy_dumb(ctypes.Structure):
    _fields_ = [
        ("handle", ctypes.c_uint32),
        ("pad", ctypes.c_uint32),
    ]


DRM_IOCTL_MODE_CREATE_DUMB = _IOWR(DRM_IOCTL_BASE, 0xB2, drm_mode_create_dumb)
DRM_IOCTL_MODE_MAP_DUMB = _IOWR(DRM_IOCTL_BASE, 0xB3, drm_mode_map_dumb)
DRM_IOCTL_MODE_DESTROY_DUMB = _IOWR(DRM_IOCTL_BASE, 0xB4, drm_mode_destroy_dumb)

# FourCC for XRGB8888
DRM_FORMAT_XRGB8888 = 0x34325258  # "XR24" little endian

# DRM mode structs (from xf86drmMode.h)


class drm_mode_modeinfo(ctypes.Structure):
    _fields_ = [
        ("clock", ctypes.c_uint32),
        ("hdisplay", ctypes.c_uint16),
        ("hsync_start", ctypes.c_uint16),
        ("hsync_end", ctypes.c_uint16),
        ("htotal", ctypes.c_uint16),
        ("hskew", ctypes.c_uint16),
        ("vdisplay", ctypes.c_uint16),
        ("vsync_start", ctypes.c_uint16),
        ("vsync_end", ctypes.c_uint16),
        ("vtotal", ctypes.c_uint16),
        ("vscan", ctypes.c_uint16),
        ("vrefresh", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("type", ctypes.c_uint32),
        ("name", ctypes.c_char * 32),
    ]


class drm_mode_res(ctypes.Structure):
    _fields_ = [
        ("count_fbs", ctypes.c_int),
        ("fbs", ctypes.POINTER(ctypes.c_uint32)),
        ("count_crtcs", ctypes.c_int),
        ("crtcs", ctypes.POINTER(ctypes.c_uint32)),
        ("count_connectors", ctypes.c_int),
        ("connectors", ctypes.POINTER(ctypes.c_uint32)),
        ("count_encoders", ctypes.c_int),
        ("encoders", ctypes.POINTER(ctypes.c_uint32)),
        ("min_width", ctypes.c_uint32),
        ("max_width", ctypes.c_uint32),
        ("min_height", ctypes.c_uint32),
        ("max_height", ctypes.c_uint32),
    ]


class drm_mode_encoder(ctypes.Structure):
    _fields_ = [
        ("encoder_id", ctypes.c_uint32),
        ("encoder_type", ctypes.c_uint32),
        ("crtc_id", ctypes.c_uint32),
        ("possible_crtcs", ctypes.c_uint32),
        ("possible_clones", ctypes.c_uint32),
    ]


class drm_mode_connector(ctypes.Structure):
    _fields_ = [
        ("connector_id", ctypes.c_uint32),
        ("encoder_id", ctypes.c_uint32),
        ("connector_type", ctypes.c_uint32),
        ("connector_type_id", ctypes.c_uint32),
        ("connection", ctypes.c_uint32),
        ("mmWidth", ctypes.c_uint32),
        ("mmHeight", ctypes.c_uint32),
        ("subpixel", ctypes.c_uint32),
        ("count_modes", ctypes.c_int),
        ("modes", ctypes.POINTER(drm_mode_modeinfo)),
        ("count_props", ctypes.c_int),
        ("props", ctypes.POINTER(ctypes.c_uint32)),
        ("prop_values", ctypes.POINTER(ctypes.c_uint64)),
        ("count_encoders", ctypes.c_int),
        ("encoders", ctypes.POINTER(ctypes.c_uint32)),
    ]


class drm_mode_crtc(ctypes.Structure):
    _fields_ = [
        ("crtc_id", ctypes.c_uint32),
        ("buffer_id", ctypes.c_uint32),
        ("x", ctypes.c_uint32),
        ("y", ctypes.c_uint32),
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("mode_valid", ctypes.c_int),
        ("mode", drm_mode_modeinfo),
        ("gamma_size", ctypes.c_int),
    ]


# libdrm function prototypes we use
libdrm.drmModeGetResources.restype = ctypes.POINTER(drm_mode_res)
libdrm.drmModeFreeResources.argtypes = [ctypes.POINTER(drm_mode_res)]

libdrm.drmModeGetConnector.restype = ctypes.POINTER(drm_mode_connector)
libdrm.drmModeGetConnector.argtypes = [ctypes.c_int, ctypes.c_uint32]
libdrm.drmModeFreeConnector.argtypes = [ctypes.POINTER(drm_mode_connector)]

libdrm.drmModeGetEncoder.restype = ctypes.POINTER(drm_mode_encoder)
libdrm.drmModeGetEncoder.argtypes = [ctypes.c_int, ctypes.c_uint32]
libdrm.drmModeFreeEncoder.argtypes = [ctypes.POINTER(drm_mode_encoder)]

libdrm.drmModeGetCrtc.restype = ctypes.POINTER(drm_mode_crtc)
libdrm.drmModeGetCrtc.argtypes = [ctypes.c_int, ctypes.c_uint32]
libdrm.drmModeFreeCrtc.argtypes = [ctypes.POINTER(drm_mode_crtc)]

libdrm.drmModeAddFB2.argtypes = [
    ctypes.c_int,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.c_uint32,
]
libdrm.drmModeAddFB2.restype = ctypes.c_int

libdrm.drmModeRmFB.argtypes = [ctypes.c_int, ctypes.c_uint32]
libdrm.drmModeSetCrtc.argtypes = [
    ctypes.c_int,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.c_int,
    ctypes.POINTER(drm_mode_modeinfo),
]
libdrm.drmModeSetCrtc.restype = ctypes.c_int


class DrmKmsDisplay:
    """Direct DRM/KMS display using a 32-bit dumb buffer (bypasses fb0)."""

    def __init__(self, config, card_path: str = "/dev/dri/card1"):
        self.config = config
        self.card_path = card_path
        self.logger = logging.getLogger("DrmKmsDisplay")

        self.fd = None
        self.connector_id = None
        self.crtc_id = None
        self.mode = None
        self._fallback_mode = None
        self._fallback_crtc = None

        self.fb_id = None
        self.handle = None
        self.pitch = None
        self.size = None
        self.mmap_obj = None
        self.map_offset = None
        self._mapped_u32 = None
        self._pitch_pixels = None
        self._xrgb_buffer = None

        self.width = None
        self.height = None

        self.running = False
        self.thread = None
        self.stop_event = Event()

        self.frame_lock = Lock()
        self.current_frame = None

        # Whether the capture path already applied rotation/flip in hardware
        self.hw_transform_applied = False

        # Profiling and FPS tracking (glass-to-glass style markers)
        self._prof_enabled = True
        self._prof_frames = 0
        self._prof_capture = 0.0
        self._prof_transform = 0.0
        self._prof_overlay_render = 0.0
        self._prof_blend = 0.0
        self._prof_blit = 0.0
        self._prof_other = 0.0
        self.frame_count = 0
        self.fps_frame_count = 0
        self.actual_fps = 0.0
        self.last_fps_calc = time.time()

        # Overlay reuse from fb0 path
        self.font = None
        self.font_small = None
        self._overlay_rgba = None
        self._overlay_last_time_sec = None
        self._overlay_last_speed = None
        self._overlay_last_rec_state = None
        self._overlay_lock = Lock()
        self._blended_overlay = None
        self.recording = False
        self.current_speed = None
        self.gps_lock = Lock()

        # CAN bus vehicle data
        self.canbus_vehicle = None  # Will be set by set_canbus_vehicle()
        self.canbus_lock = Lock()

        self._load_fonts()

    # ------------------------------------------------------------------ DRM init/cleanup
    def _open_device(self):
        self.fd = os.open(self.card_path, os.O_RDWR | os.O_CLOEXEC)

    def _choose_connector_and_mode(self):
        res = libdrm.drmModeGetResources(self.fd)
        if not res:
            raise RuntimeError("drmModeGetResources failed")
        try:
            for i in range(res.contents.count_connectors):
                conn_id = res.contents.connectors[i]
                conn = libdrm.drmModeGetConnector(self.fd, conn_id)
                if not conn:
                    continue
                try:
                    if conn.contents.connection != 1:  # DRM_MODE_CONNECTED
                        continue
                    if conn.contents.count_modes <= 0:
                        continue
                    mode = conn.contents.modes[0]
                    encoder_id = conn.contents.encoder_id
                    if encoder_id == 0 and conn.contents.count_encoders > 0:
                        encoder_id = conn.contents.encoders[0]
                    enc = libdrm.drmModeGetEncoder(self.fd, encoder_id)
                    if not enc:
                        continue
                    try:
                        # Choose a valid CRTC: prefer encoder's crtc_id, otherwise pick from possible_crtcs bitmask
                        crtc_id = enc.contents.crtc_id
                        if crtc_id == 0:
                            mask = enc.contents.possible_crtcs
                            for c in range(res.contents.count_crtcs):
                                if mask & (1 << c):
                                    crtc_id = res.contents.crtcs[c]
                                    break
                        if crtc_id == 0:
                            continue
                        # Save current CRTC (for fallback mode if needed)
                        current_crtc = libdrm.drmModeGetCrtc(self.fd, crtc_id)
                        if current_crtc:
                            self._fallback_crtc = current_crtc
                            if current_crtc.contents.mode_valid:
                                self._fallback_mode = current_crtc.contents.mode

                        self.connector_id = conn_id
                        self.crtc_id = crtc_id
                        self.mode = mode
                        self.width = mode.hdisplay
                        self.height = mode.vdisplay
                        return
                    finally:
                        libdrm.drmModeFreeEncoder(enc)
                finally:
                    libdrm.drmModeFreeConnector(conn)
        finally:
            libdrm.drmModeFreeResources(res)
        raise RuntimeError("No connected DRM connector with a usable mode/CRTC")

    def _create_dumb_buffer(self):
        create = drm_mode_create_dumb()
        create.width = self.width
        create.height = self.height
        create.bpp = 32
        create.flags = 0
        fcntl.ioctl(self.fd, DRM_IOCTL_MODE_CREATE_DUMB, create)
        self.handle = create.handle
        self.pitch = create.pitch
        self.size = create.size

        handles = (ctypes.c_uint32 * 4)()
        pitches = (ctypes.c_uint32 * 4)()
        offsets = (ctypes.c_uint32 * 4)()
        handles[0] = self.handle
        pitches[0] = self.pitch
        offsets[0] = 0
        fb_id = ctypes.c_uint32()
        ret = libdrm.drmModeAddFB2(
            self.fd,
            self.width,
            self.height,
            DRM_FORMAT_XRGB8888,
            handles,
            pitches,
            offsets,
            ctypes.byref(fb_id),
            0,
        )
        if ret != 0:
            raise RuntimeError(f"drmModeAddFB2 failed ({ret})")
        self.fb_id = fb_id.value

        m = drm_mode_map_dumb()
        m.handle = self.handle
        fcntl.ioctl(self.fd, DRM_IOCTL_MODE_MAP_DUMB, m)
        self.map_offset = m.offset
        self.mmap_obj = mmap.mmap(
            self.fd, self.size, mmap.MAP_SHARED, mmap.PROT_WRITE, offset=self.map_offset
        )
        self._init_mmap_views()

    def _set_crtc(self):
        conn_array = (ctypes.c_uint32 * 1)()
        conn_array[0] = self.connector_id
        ret = libdrm.drmModeSetCrtc(
            self.fd,
            self.crtc_id,
            self.fb_id,
            0,
            0,
            conn_array,
            1,
            ctypes.byref(self.mode),
        )
        if ret != 0:
            # Try fallback to current crtc mode if available
            if self._fallback_mode is not None:
                self.logger.debug(
                    f"drmModeSetCrtc failed ({ret}), retrying with existing CRTC mode"
                )
                ret2 = libdrm.drmModeSetCrtc(
                    self.fd,
                    self.crtc_id,
                    self.fb_id,
                    0,
                    0,
                    conn_array,
                    1,
                    ctypes.byref(self._fallback_mode),
                )
                if ret2 == 0:
                    # Update width/height to fallback mode to keep sizing consistent
                    self.width = self._fallback_mode.hdisplay
                    self.height = self._fallback_mode.vdisplay
                    return
                ret = ret2
            raise RuntimeError(f"drmModeSetCrtc failed ({ret})")

    def _init_mmap_views(self):
        """Create NumPy views over the mapped dumb buffer for fast writes."""
        try:
            if self.mmap_obj is None or self.pitch is None or self.height is None:
                return
            # pitch is bytes per line; convert to pixels (uint32 per pixel)
            self._pitch_pixels = max(1, self.pitch // 4)
            self._mapped_u32 = np.ndarray(
                (self.height, self._pitch_pixels),
                dtype=np.uint32,
                buffer=self.mmap_obj,
            )
            # Scratch buffer for packed XRGB8888
            self._xrgb_buffer = np.empty((self.height, self.width), dtype=np.uint32)
        except Exception as exc:
            self.logger.debug(f"Failed to init mmap views: {exc}")
            self._mapped_u32 = None
            self._xrgb_buffer = None
            self._pitch_pixels = None

    def start(self):
        """Start KMS display."""
        try:
            self._open_device()
            self._choose_connector_and_mode()
            self.logger.info(
                f"DRM connector={self.connector_id} crtc={self.crtc_id} "
                f"mode={self.mode.hdisplay}x{self.mode.vdisplay}@{self.mode.vrefresh}Hz "
                f"(pitch request later)"
            )
            self._create_dumb_buffer()
            self._set_crtc()
            # Rebuild views if mode fallback adjusted geometry
            self._init_mmap_views()

            self.running = True
            self.stop_event.clear()
            self.thread = Thread(target=self._display_loop, daemon=True)
            self.thread.start()
            self.logger.info(
                f"DRM/KMS display started: {self.width}x{self.height} @ {self.mode.vrefresh}Hz (card={self.card_path})"
            )
            return True
        except Exception as exc:
            self.logger.error(f"Failed to start DRM/KMS display: {exc}")
            self._cleanup()
            return False

    def stop(self):
        """Stop display and clean up resources."""
        self.running = False
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2.0)
        self._cleanup()

    def _cleanup(self):
        try:
            if self.mmap_obj:
                self.mmap_obj.close()
        finally:
            self.mmap_obj = None
            self._mapped_u32 = None
            self._xrgb_buffer = None
            self._pitch_pixels = None

        if self.fb_id and self.fd:
            try:
                libdrm.drmModeRmFB(self.fd, self.fb_id)
            except Exception:
                pass
        self.fb_id = None

        if self.handle and self.fd:
            try:
                destroy = drm_mode_destroy_dumb()
                destroy.handle = self.handle
                fcntl.ioctl(self.fd, DRM_IOCTL_MODE_DESTROY_DUMB, destroy)
            except Exception:
                pass
        self.handle = None

        if self.fd:
            try:
                os.close(self.fd)
            except Exception:
                pass
        self.fd = None
        self._blended_overlay = None

    # ------------------------------------------------------------------ Public API parity
    def update_frame(self, frame: np.ndarray):
        with self.frame_lock:
            self.current_frame = frame
            self.frame_count += 1

    def set_recording(self, recording: bool):
        self.recording = recording

    def update_gps_data(self, speed_mph: Optional[float]):
        with self.gps_lock:
            self.current_speed = speed_mph

    def set_canbus_vehicle(self, canbus_vehicle):
        """Set CAN bus vehicle interface for accessing vehicle data."""
        with self.canbus_lock:
            self.canbus_vehicle = canbus_vehicle

    def set_hardware_transform_applied(self, applied: bool):
        """Inform display that capture already applied rotation/flip."""
        self.hw_transform_applied = bool(applied)

    def get_stats(self) -> dict:
        target_fps = getattr(self.config, "display_fps", None)
        try:
            if not target_fps and self.mode:
                target_fps = getattr(self.mode, "vrefresh", None)
        except Exception:
            target_fps = None

        return {
            "frame_count": self.frame_count,
            "recording": self.recording,
            "width": self.width,
            "height": self.height,
            "target_fps": target_fps,
            "actual_fps": self.actual_fps,
            "mirror_mode": getattr(self.config, "display_mirror_mode", False),
        }

    # ------------------------------------------------------------------ Display loop
    def _display_loop(self):
        target_frame_time = 1.0 / max(1, int(self.config.display_fps or 30))
        while self.running and not self.stop_event.is_set():
            loop_start = time.time()
            try:
                t_get_start = time.time()
                with self.frame_lock:
                    frame = self.current_frame
                t_get_end = time.time()
                if self._prof_enabled:
                    self._prof_capture += (t_get_end - t_get_start) * 1000.0
                if frame is None:
                    time.sleep(0.01)
                    continue

                frame = self._ensure_rgb(frame)

                if not self.hw_transform_applied:
                    t_tf_start = time.time()
                    try:
                        cam_cfg = self.config.get_camera_config(
                            getattr(self.config, "display_camera_index", 1)
                        )
                        rotation = cam_cfg.get("rotation", 0)
                        hflip = cam_cfg.get("hflip", False)
                        vflip = cam_cfg.get("vflip", False)
                    except Exception:
                        rotation = getattr(self.config, "rear_camera_rotation", 0)
                        hflip = getattr(self.config, "rear_camera_hflip", False)
                        vflip = getattr(self.config, "rear_camera_vflip", False)

                    frame = self._apply_transform(
                        frame,
                        rotation,
                        hflip,
                        vflip,
                        getattr(self.config, "display_mirror_mode", False),
                    )
                    t_tf_end = time.time()
                    if self._prof_enabled:
                        self._prof_transform += (t_tf_end - t_tf_start) * 1000.0

                if self.config.overlay_enabled:
                    frame, render_ms, blend_ms = self._maybe_add_overlay(frame)
                    if self._prof_enabled:
                        self._prof_overlay_render += render_ms
                        self._prof_blend += blend_ms

                t_blit_start = time.time()
                self._blit_frame(frame)
                t_blit_end = time.time()
                if self._prof_enabled:
                    self._prof_blit += (t_blit_end - t_blit_start) * 1000.0
            except Exception as exc:
                self.logger.debug(f"DRM display loop error: {exc}")

            if self._prof_enabled:
                self._prof_frames += 1
                self.fps_frame_count += 1
                if time.time() - self.last_fps_calc >= 1.0:
                    interval = time.time() - self.last_fps_calc
                    frames = self.fps_frame_count
                    self.actual_fps = frames / interval if interval > 0 else 0.0
                    if self._prof_frames > 0:
                        avg_capture = self._prof_capture / max(1, self._prof_frames)
                        avg_transform = self._prof_transform / max(1, self._prof_frames)
                        avg_overlay = self._prof_overlay_render / max(1, self._prof_frames)
                        avg_blend = self._prof_blend / max(1, self._prof_frames)
                        avg_blit = self._prof_blit / max(1, self._prof_frames)
                        avg_other = max(
                            0.0,
                            (interval * 1000.0) / max(1, frames) - (avg_capture + avg_transform + avg_overlay + avg_blend + avg_blit),
                        )
                        self.logger.debug(
                            f"DRM Display FPS: {self.actual_fps:.1f} | timings (ms/frame): "
                            f"capture={avg_capture:.1f} transform={avg_transform:.1f} "
                            f"overlay={avg_overlay:.1f} blend={avg_blend:.1f} blit={avg_blit:.1f} other~={avg_other:.1f}"
                        )
                    self.fps_frame_count = 0
                    self.last_fps_calc = time.time()
                    self._prof_frames = 0
                    self._prof_capture = 0.0
                    self._prof_transform = 0.0
                    self._prof_overlay_render = 0.0
                    self._prof_blend = 0.0
                    self._prof_blit = 0.0
                    self._prof_other = 0.0

            elapsed = time.time() - loop_start
            sleep_time = target_frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _blit_frame(self, frame: np.ndarray):
        if self.mmap_obj is None:
            return
        if frame.shape[0] != self.height or frame.shape[1] != self.width:
            frame = self._resize_nn(frame, self.width, self.height)
        if frame.dtype != np.uint8:
            frame = frame.astype(np.uint8)

        if self._xrgb_buffer is None or self._xrgb_buffer.shape[0] != self.height or self._xrgb_buffer.shape[1] != self.width:
            self._xrgb_buffer = np.empty((self.height, self.width), dtype=np.uint32)

        # Convert RGB888 -> XRGB8888 using numba and copy directly into mapped view
        pack_xrgb8888_jit(frame, self._xrgb_buffer)

        if self._mapped_u32 is not None and self._pitch_pixels and self._pitch_pixels >= self.width:
            try:
                self._mapped_u32[:, : self.width] = self._xrgb_buffer
                return
            except Exception:
                # Fall back to byte copy path
                pass

        # Fallback path when NumPy view is unavailable
        xrgb_bytes = self._xrgb_buffer.tobytes()
        if self.pitch and self.pitch != self.width * 4:
            row_bytes = self.width * 4
            for y in range(self.height):
                start = y * self.pitch
                end = start + row_bytes
                row_start = y * row_bytes
                self.mmap_obj[start:end] = xrgb_bytes[row_start:row_start + row_bytes]
        else:
            self.mmap_obj[: len(xrgb_bytes)] = xrgb_bytes

    # ------------------------------------------------------------------ Overlay helpers (trimmed)
    def _maybe_add_overlay(self, frame: np.ndarray):
        """Update cached overlay when needed and blend using a precomputed mask.

        Returns the frame plus render/blend timings in milliseconds for profiling.
        """
        render_ms = 0.0
        blend_ms = 0.0
        now_sec = datetime.now().second
        with self._overlay_lock:
            with self.gps_lock:
                cs = self.current_speed
            
            # Get fuel consumption data if available
            fuel_consumed = None
            with self.canbus_lock:
                if self.canbus_vehicle and hasattr(self.canbus_vehicle, 'has_valid_fuel_data'):
                    if self.canbus_vehicle.has_valid_fuel_data():
                        fuel_consumed = self.canbus_vehicle.get_fuel_consumed_gallons(apply_safety_margin=True)

            rec_state = False
            if self.recording:
                if not self.config.rec_indicator_blink:
                    rec_state = True
                else:
                    blink_rate = max(0.01, float(self.config.rec_indicator_blink_rate))
                    rec_state = (int(time.time() / blink_rate) % 2) == 0

            needs_update = (
                self._overlay_rgba is None
                or self._overlay_last_time_sec != now_sec
                or (self._overlay_last_speed is None and cs is not None)
                or (
                    cs is not None
                    and self._overlay_last_speed is not None
                    and int(cs) != int(self._overlay_last_speed)
                )
                or self._overlay_last_rec_state != rec_state
                or (fuel_consumed is not None and 
                    (not hasattr(self, '_overlay_last_fuel') or 
                     abs((fuel_consumed - (self._overlay_last_fuel or 0))) > 0.001))
            )

            if needs_update:
                t_or_start = time.time()
                try:
                    self._overlay_rgba = self._render_overlay_rgba(rec_state)
                    self._blended_overlay = self._precompute_blend_mask(self._overlay_rgba)
                except Exception:
                    self._overlay_rgba = None
                    self._blended_overlay = None
                self._overlay_last_time_sec = now_sec
                self._overlay_last_speed = cs
                self._overlay_last_rec_state = rec_state
                self._overlay_last_fuel = fuel_consumed
                render_ms = (time.time() - t_or_start) * 1000.0

            blend_mask = self._blended_overlay

        if blend_mask is not None:
            t_bl_start = time.time()
            frame = self._apply_blended_overlay(frame, blend_mask)
            blend_ms = (time.time() - t_bl_start) * 1000.0

        return frame, render_ms, blend_ms

    def _precompute_blend_mask(self, overlay_rgba):
        """Pre-compute blend region once when overlay content changes."""
        if overlay_rgba is None:
            return None
        try:
            alpha = overlay_rgba[:, :, 3]
            if not np.any(alpha):
                return None
            ys, xs = np.where(alpha > 0)
            y0, y1 = ys.min(), ys.max()
            x0, x1 = xs.min(), xs.max()
            o_sub = overlay_rgba[y0 : y1 + 1, x0 : x1 + 1]
            return {
                "bbox": (y0, y1, x0, x1),
                "overlay": o_sub,
                "alpha": o_sub[:, :, 3].astype(np.uint16),
                "rgb": o_sub[:, :, :3].astype(np.uint16),
            }
        except Exception:
            return None

    def _apply_blended_overlay(self, frame, blend_mask):
        """Apply cached overlay mask without recomputing bounding boxes."""
        if blend_mask is None:
            return frame
        try:
            y0, y1, x0, x1 = blend_mask["bbox"]
            o_rgb = blend_mask["rgb"]
            o_a = blend_mask["alpha"]
            f_sub = frame[y0 : y1 + 1, x0 : x1 + 1].astype(np.uint16)

            a_exp = o_a[:, :, None].astype(np.uint32)
            o_exp = o_rgb.astype(np.uint32)
            f_exp = f_sub.astype(np.uint32)
            out_sub = (a_exp * o_exp + (255 - a_exp) * f_exp + 127) // 255
            out_sub = np.clip(out_sub, 0, 255).astype(np.uint8)
            frame[y0 : y1 + 1, x0 : x1 + 1] = out_sub
            return frame
        except Exception:
            return frame

    def _render_overlay_rgba(self, rec_state: bool) -> Optional[np.ndarray]:
        if not self.config.overlay_enabled:
            return None
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img, "RGBA")

        now = datetime.now()
        time_str = now.strftime(self.config.overlay_time_format)
        self._draw_text_with_bg(draw, time_str, self.config.overlay_time_pos, self.config.overlay_font_color, self.font)

        if hasattr(self.config, "overlay_date_pos"):
            date_str = now.strftime(self.config.overlay_date_format)
            self._draw_text_with_bg(draw, date_str, self.config.overlay_date_pos, self.config.overlay_font_color, self.font_small)

        if self.config.display_speed and hasattr(self.config, "overlay_speed_pos"):
            with self.gps_lock:
                cs = self.current_speed
            if cs is not None:
                if self.config.speed_unit == "mph":
                    speed_text = f"{cs:.0f} MPH"
                else:
                    speed_text = f"{cs * 1.60934:.0f} KPH"
                self._draw_text_with_bg(draw, speed_text, self.config.overlay_speed_pos, self.config.overlay_font_color, self.font)
        
        # Display fuel consumption if enabled and available
        if getattr(self.config, 'display_fuel_consumed', False):
            with self.canbus_lock:
                if self.canbus_vehicle and hasattr(self.canbus_vehicle, 'has_valid_fuel_data'):
                    if self.canbus_vehicle.has_valid_fuel_data():
                        # Get fuel consumed with safety margin
                        fuel_consumed = self.canbus_vehicle.get_fuel_consumed_gallons(apply_safety_margin=True)
                        
                        # Format based on config
                        decimals = getattr(self.config, 'fuel_display_decimals', 3)
                        if getattr(self.config, 'fuel_display_unit', 'gallons') == 'gallons':
                            fuel_text = f"Fuel: {fuel_consumed:.{decimals}f} gal"
                        else:
                            fuel_liters = self.canbus_vehicle.get_fuel_consumed_liters(apply_safety_margin=True)
                            fuel_text = f"Fuel: {fuel_liters:.{decimals}f} L"
                        
                        # Position fuel display below speed
                        fuel_pos = getattr(self.config, 'fuel_overlay_position', (20, 140))
                        self._draw_text_with_bg(draw, fuel_text, fuel_pos, self.config.overlay_font_color, self.font)

        if rec_state:
            rec_x, rec_y = self.config.overlay_rec_indicator_pos
            text_bbox = draw.textbbox((0, 0), self.config.rec_indicator_text, font=self.font)
            text_width = text_bbox[2] - text_bbox[0]
            rec_x -= text_width
            self._draw_text_with_bg(draw, self.config.rec_indicator_text, (rec_x, rec_y), self.config.rec_indicator_color, self.font)

        return np.array(img)

    def _blend_overlay(self, frame: np.ndarray, overlay_rgba: np.ndarray) -> np.ndarray:
        if overlay_rgba is None:
            return frame
        if overlay_rgba.shape[0] != frame.shape[0] or overlay_rgba.shape[1] != frame.shape[1]:
            overlay_rgba = np.array(Image.fromarray(overlay_rgba).resize((frame.shape[1], frame.shape[0])))
        alpha = overlay_rgba[:, :, 3]
        if not np.any(alpha):
            return frame
        ys, xs = np.where(alpha > 0)
        y0, y1 = ys.min(), ys.max()
        x0, x1 = xs.min(), xs.max()
        o_sub = overlay_rgba[y0 : y1 + 1, x0 : x1 + 1]
        f_sub = frame[y0 : y1 + 1, x0 : x1 + 1]

        o_rgb = o_sub[:, :, :3].astype(np.uint16)
        o_a = o_sub[:, :, 3].astype(np.uint16)
        f_rgb = f_sub.astype(np.uint16)
        a_exp = o_a[:, :, None].astype(np.uint32)
        o_exp = o_rgb.astype(np.uint32)
        f_exp = f_rgb.astype(np.uint32)
        out_sub = (a_exp * o_exp + (255 - a_exp) * f_exp + 127) // 255
        out_sub = np.clip(out_sub, 0, 255).astype(np.uint8)
        frame[y0 : y1 + 1, x0 : x1 + 1] = out_sub
        return frame

    def _draw_text_with_bg(self, draw: ImageDraw.Draw, text: str, pos: tuple, color: tuple, font: ImageFont.ImageFont):
        x, y = pos

        # Rounded panel sizing
        padding = 5
        corner_radius = getattr(self.config, "overlay_corner_radius", 8)
        bbox = draw.textbbox((x, y), text, font=font)
        bbox = (bbox[0] - padding, bbox[1] - padding, bbox[2] + padding, bbox[3] + padding)

        # Optional shadow
        if getattr(self.config, "overlay_shadow_enabled", False):
            shadow_offset = getattr(self.config, "overlay_shadow_offset", (2, 2))
            shadow_alpha = getattr(self.config, "overlay_shadow_alpha", 80)
            shadow_color = getattr(self.config, "overlay_shadow_color", (0, 0, 0))
            sx, sy = shadow_offset
            shadow_bbox = (bbox[0] + sx, bbox[1] + sy, bbox[2] + sx, bbox[3] + sy)
            draw.rounded_rectangle(shadow_bbox, radius=corner_radius, fill=shadow_color + (shadow_alpha,))

        # Panel
        bg_color = self.config.overlay_bg_color + (self.config.overlay_bg_alpha,)
        draw.rounded_rectangle(bbox, radius=corner_radius, fill=bg_color)

        # Outline for legibility
        if self.config.overlay_outline:
            outline_color = self.config.overlay_outline_color
            for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)

        draw.text((x, y), text, font=font, fill=color)

    # ------------------------------------------------------------------ Helpers
    def _ensure_rgb(self, frame: np.ndarray) -> np.ndarray:
        """Convert BGR input to RGB if configured."""
        try:
            if (
                getattr(self.config, "display_input_is_bgr", False)
                and isinstance(frame, np.ndarray)
                and frame.ndim == 3
                and frame.shape[2] == 3
            ):
                return frame[:, :, ::-1]
        except Exception:
            pass
        return frame

    def _load_fonts(self):
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", self.config.overlay_font_size)
            self.font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", self.config.overlay_font_size - 8)
        except Exception:
            self.font = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
            self.logger.warning("Using default PIL font for DRM/KMS overlay")

    def _resize_nn(self, frame: np.ndarray, out_w: int, out_h: int) -> np.ndarray:
        """Nearest-neighbor resize using NumPy indexing (no PIL overhead)."""
        if frame is None:
            return frame
        if frame.ndim == 2:
            frame = frame[:, :, None]
        src_h, src_w = frame.shape[:2]
        if src_h == out_h and src_w == out_w:
            return frame
        row_idx = (np.arange(out_h) * (src_h / out_h)).astype(np.int32)
        col_idx = (np.arange(out_w) * (src_w / out_w)).astype(np.int32)
        row_idx = np.clip(row_idx, 0, src_h - 1)
        col_idx = np.clip(col_idx, 0, src_w - 1)
        return frame[row_idx[:, None], col_idx]

    def _apply_transform(self, frame: np.ndarray, rotation: int, hflip: bool, vflip: bool, mirror_mode: bool = False) -> np.ndarray:
        try:
            if frame is None:
                return frame
            img = frame
            if not isinstance(img, np.ndarray):
                img = np.array(img)
            r = int(rotation or 0) % 360
            if r != 0:
                k = (r // 90) % 4
                img = np.rot90(img, k=k)
            if hflip:
                img = np.fliplr(img)
            if vflip:
                img = np.flipud(img)
            if mirror_mode:
                img = np.fliplr(img)
            return img
        except Exception:
            return frame


# Convenience factory to avoid touching existing wiring yet
def create_display(config, card_path: str = "/dev/dri/card1") -> DrmKmsDisplay:
    return DrmKmsDisplay(config, card_path=card_path)
