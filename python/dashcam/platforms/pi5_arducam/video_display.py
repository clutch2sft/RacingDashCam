"""
Video Display Handler for Active Dash Mirror
Direct framebuffer output with overlay rendering for dual CSI cameras
"""

import time
import logging
import os
import numpy as np
from numba import jit
from datetime import datetime
from threading import Thread, Event, Lock
from typing import Optional
from PIL import Image, ImageDraw, ImageFont


def hide_cursor():
    """Hide the Linux virtual console cursor on tty0 (framebuffer)."""
    try:
        # Redirect stderr to /dev/null to avoid noisy output if not available
        os.system("setterm -cursor off > /dev/tty0 2>/dev/null")
    except Exception:
        pass


def show_cursor():
    """Restore the Linux virtual console cursor on tty0 (framebuffer)."""
    try:
        os.system("setterm -cursor on > /dev/tty0 2>/dev/null")
    except Exception:
        pass

@jit(nopython=True, cache=True, parallel=False)
def pack_rgb565_jit(frame, output):
    """JIT-compiled RGB565 packing"""
    height, width = frame.shape[0], frame.shape[1]
    
    for y in range(height):
        for x in range(width):
            r = frame[y, x, 0]
            g = frame[y, x, 1]
            b = frame[y, x, 2]
            
            r5 = (r >> 3) & 0x1F
            g6 = (g >> 2) & 0x3F
            b5 = (b >> 3) & 0x1F
            
            output[y, x] = (r5 << 11) | (g6 << 5) | b5
class VideoDisplay:
    """Manages video display with overlay on framebuffer"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("VideoDisplay")
        
        # Display settings
        self.width = config.display_width
        self.height = config.display_height
        self.fps = config.display_fps
        self.mirror_mode = config.display_mirror_mode

        # Framebuffer
        self.fb_device = config.framebuffer_device if hasattr(config, 'framebuffer_device') else "/dev/fb0"
        self.fb_file = None
        
        # Frame management
        self.current_frame = None
        self.frame_lock = Lock()
        self.frame_count = 0
        # Preallocated framebuffer conversion buffer (allocated on start)
        self._rgb565 = None
        self._fb_frame_bytes = None

        # Framebuffer format detection
        self._fb_bpp = self._detect_fb_format()
        self._use_rgb565 = (self._fb_bpp == 16)
        self.logger.info(f"Framebuffer: {self._fb_bpp}-bit ({'RGB565' if self._use_rgb565 else 'BGRA32'})")

        # Performance tracking
        self.last_fps_calc = time.time()
        self.fps_frame_count = 0
        self.actual_fps = 0.0
        # Profiling accumulators (ms)
        self._prof_enabled = True
        self._prof_frames = 0
        self._prof_capture = 0.0
        self._prof_transform = 0.0
        self._prof_overlay_render = 0.0
        self._prof_blend = 0.0
        self._prof_write = 0.0
        # Breakdown of write step
        self._prof_resize = 0.0
        self._prof_pack = 0.0
        self._prof_fbwrite = 0.0
        self._prof_other = 0.0
        
        # Overlay state
        self.recording = False
        self.rec_blink_state = False
        self.last_blink_time = time.time()
        self.canbus_vehicle = None
        self.canbus_lock = Lock()

        # Overlay caching (to avoid re-rendering every frame)
        self._overlay_rgba = None  # Cached RGBA overlay as numpy array
        self._overlay_last_time_sec = None
        self._overlay_last_speed = None
        self._overlay_last_rec_state = None
        self._overlay_last_can_state = None
        self._overlay_lock = Lock()
        
        # GPS data (optional)
        self.current_speed = None
        self.gps_lock = Lock()
        
        # Display thread
        self.running = False
        self.thread = None
        self.stop_event = Event()

        # Whether the camera has applied transforms in hardware. If True,
        # the display will not re-apply rotation/hflip/vflip in software.
        self.hw_transform_applied = False
        
        # Font for overlay (will try to load, fallback to default)
        self.font = None
        self.font_small = None
        self._load_fonts()

        self._blended_overlay = None  # Cached pre-blended overlay mask

    def _detect_fb_format(self):
        """Detect framebuffer bits per pixel"""
        try:
            with open('/sys/class/graphics/fb0/bits_per_pixel', 'r') as f:
                return int(f.read().strip())
        except:
            # Default to 32-bit on Pi 5
            return 32

    def _load_fonts(self):
        """Load fonts for overlay text"""
        try:
            # Try to load a monospace font
            self.font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 
                self.config.overlay_font_size
            )
            self.font_small = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                self.config.overlay_font_size - 8
            )
            self.logger.info("Loaded DejaVu Sans Mono font")
        except:
            try:
                # Fallback to basic font
                self.font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    self.config.overlay_font_size
                )
                self.font_small = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    self.config.overlay_font_size - 8
                )
                self.logger.info("Loaded DejaVu Sans font")
            except:
                # Use default PIL font
                self.font = ImageFont.load_default()
                self.font_small = ImageFont.load_default()
                self.logger.warning("Using default PIL font")
 
    
    def start(self):
        """Start display handler"""
        try:
            # Hide virtual console cursor when display starts
            try:
                hide_cursor()
            except Exception:
                pass
            # Open framebuffer file for binary writes. Avoid mmap due to
            # observed periodic blanking on some platforms/drivers.
            try:
                # Use r+b to avoid truncation while allowing writes
                self.fb_file = open(self.fb_device, 'r+b')
            except Exception:
                # Fallback to wb if r+b not permitted
                self.fb_file = open(self.fb_device, 'wb')

            # Preallocate conversion buffer and clear screen to black
            self._rgb565 = np.zeros((self.height, self.width), dtype=np.uint16)
            self._fb_frame_bytes = self.width * self.height * 2
            black_frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            self._write_frame(black_frame)
            
            # Start display thread
            self.running = True
            self.stop_event.clear()
            self.thread = Thread(target=self._display_loop, daemon=True)
            self.thread.start()
            
            self.logger.info(
                f"Display started: {self.width}x{self.height} @ {self.fps}fps "
                f"(mirror_mode={self.mirror_mode})"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start display: {e}")
            return False
    
    def stop(self):
        """Stop display handler"""
        self.logger.info("Stopping display...")
        self.running = False
        self.stop_event.set()
        
        if self.thread:
            self.thread.join(timeout=2.0)
        
        if self.fb_file:
            # Clear screen before closing
            try:
                black_frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
                self._write_frame(black_frame)
            except:
                pass
            self.fb_file.close()
        # Restore cursor when display stops
        try:
            show_cursor()
        except Exception:
            pass

        self.logger.info(f"Display stopped (actual FPS: {self.actual_fps:.1f})")
    
    def update_frame(self, frame: np.ndarray):
        """Update the current frame to display"""
        # Store reference to latest frame (avoid copying here)
        with self.frame_lock:
            self.current_frame = frame
            self.frame_count += 1
    
    def set_recording(self, recording: bool):
        """Set recording state for indicator"""
        self.recording = recording
    
    def update_gps_data(self, speed_mph: Optional[float]):
        """Update GPS data for overlay display"""
        with self.gps_lock:
            self.current_speed = speed_mph

    def set_canbus_vehicle(self, canbus_vehicle):
        """Link CAN bus vehicle interface for overlay status/data."""
        with self.canbus_lock:
            self.canbus_vehicle = canbus_vehicle
    
    def _display_loop(self):
        """Main display loop"""
        frame_time = 1.0 / self.fps
        
        while self.running and not self.stop_event.is_set():
            loop_start = time.time()
            
            try:
                # Get current frame (measure capture retrieval time).
                # Do NOT clear `self.current_frame` so the last frame remains
                # available if the producer is momentarily late. This prevents
                # visible black frames when capture hiccups occur.
                t_get_start = time.time()
                with self.frame_lock:
                    frame = self.current_frame
                t_get_end = time.time()
                if self._prof_enabled:
                    self._prof_capture += (t_get_end - t_get_start) * 1000.0

                if frame is None:
                    # No frame yet, show black
                    frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
                
                frame = self._ensure_rgb(frame)
                
                # Apply per-camera transforms (rotation, hflip, vflip) only if
                # hardware hasn't already applied them. If hardware transform is
                # applied we skip software rotation/flips to avoid double-transform.
                t_start = time.time()
                if not getattr(self, 'hw_transform_applied', False):
                    try:
                        cam_cfg = self.config.get_camera_config(self.config.display_camera_index)
                        rotation = cam_cfg.get('rotation', 0)
                        hflip = cam_cfg.get('hflip', False)
                        vflip = cam_cfg.get('vflip', False)
                    except Exception:
                        rotation = 0
                        hflip = False
                        vflip = False

                    frame = self._apply_transform(frame, rotation, hflip, vflip, mirror_mode=self.mirror_mode)
                t_after_transform = time.time()
                if self._prof_enabled:
                    self._prof_transform += (t_after_transform - t_start) * 1000.0
                
                # Add overlay if enabled. Use cached overlay rendered only
                # when content changes (time second, GPS speed, REC state).
                if self.config.overlay_enabled:
                    now_sec = datetime.now().second
                    with self._overlay_lock:
                        with self.gps_lock:
                            cs = self.current_speed

                        rec_state = False
                        if self.recording:
                            if not self.config.rec_indicator_blink:
                                rec_state = True
                            else:
                                blink_rate = max(0.01, float(self.config.rec_indicator_blink_rate))
                                rec_state = (int(time.time() / blink_rate) % 2) == 0

                        can_status = self._get_canbus_status()

                        needs_update = (
                            self._overlay_rgba is None
                            or self._overlay_last_time_sec != now_sec
                            or (self._overlay_last_speed is None and cs is not None)
                            or (cs is not None and self._overlay_last_speed is not None and int(cs) != int(self._overlay_last_speed))
                            or self._overlay_last_rec_state != rec_state
                            or self._overlay_last_can_state != can_status
                        )

                        if needs_update:
                            t_or_start = time.time()
                            try:
                                self._overlay_rgba = self._render_overlay_rgba(rec_state, can_status)
                                # Pre-compute blended overlay regions when overlay changes
                                self._blended_overlay = self._precompute_blend_mask(self._overlay_rgba)
                            except Exception as e:
                                self.logger.debug(f"Overlay render failed: {e}")
                                self._overlay_rgba = None
                                self._blended_overlay = None
                            t_or_end = time.time()
                            if self._prof_enabled:
                                self._prof_overlay_render += (t_or_end - t_or_start) * 1000.0

                            self._overlay_last_time_sec = now_sec
                            self._overlay_last_speed = cs
                            self._overlay_last_rec_state = rec_state
                            self._overlay_last_can_state = can_status

                    # Fast blend using pre-computed mask
                    if self._blended_overlay is not None:
                        try:
                            t_bl_start = time.time()
                            frame = self._apply_blended_overlay(frame, self._blended_overlay)
                            t_bl_end = time.time()
                            if self._prof_enabled:
                                self._prof_blend += (t_bl_end - t_bl_start) * 1000.0
                        except Exception as e:
                            self.logger.debug(f"Overlay blend failed: {e}")
                
                # Write to framebuffer
                t_w_start = time.time()
                self._write_frame(frame)
                t_w_end = time.time()
                if self._prof_enabled:
                    # Keep overall write time (for backward compatibility)
                    self._prof_write += (t_w_end - t_w_start) * 1000.0
                
                # Update FPS counter and profiling frame count
                self.fps_frame_count += 1
                if self._prof_enabled:
                    self._prof_frames += 1

                if time.time() - self.last_fps_calc >= 1.0:
                    interval = time.time() - self.last_fps_calc
                    frames = self.fps_frame_count
                    self.actual_fps = frames / interval if interval > 0 else 0.0
                    # Compute per-stage averages
                    if self._prof_enabled and self._prof_frames > 0:
                        avg_transform = self._prof_transform / max(1, self._prof_frames)
                        avg_overlay = self._prof_overlay_render / max(1, self._prof_frames)
                        avg_blend = self._prof_blend / max(1, self._prof_frames)
                        avg_write = self._prof_write / max(1, self._prof_frames)
                        avg_resize = self._prof_resize / max(1, self._prof_frames)
                        avg_pack = self._prof_pack / max(1, self._prof_frames)
                        avg_fbwrite = self._prof_fbwrite / max(1, self._prof_frames)
                        # avg_other should be per-frame remainder: total ms per frame
                        avg_other = max(0.0, (interval * 1000.0) / max(1, frames) - (avg_transform + avg_overlay + avg_blend + avg_write))
                    else:
                        avg_transform = avg_overlay = avg_blend = avg_write = avg_other = 0.0

                    self.fps_frame_count = 0
                    self.last_fps_calc = time.time()
                    # Reset profiling accumulators
                    if self._prof_enabled:
                        self.logger.debug(
                            f"Display FPS: {self.actual_fps:.1f} | timings (ms/frame): "
                            f"transform={avg_transform:.1f} overlay_render={avg_overlay:.1f} "
                            f"blend={avg_blend:.1f} write={avg_write:.1f} "
                            f"(resize={avg_resize:.1f} pack={avg_pack:.1f} fb={avg_fbwrite:.1f}) "
                            f"other~={avg_other:.1f}"
                        )
                        self._prof_frames = 0
                        self._prof_transform = 0.0
                        self._prof_overlay_render = 0.0
                        self._prof_blend = 0.0
                        self._prof_write = 0.0
                        self._prof_other = 0.0
                        self._prof_resize = 0.0
                        self._prof_pack = 0.0
                        self._prof_fbwrite = 0.0
                    else:
                        if self.config.log_fps:
                            self.logger.debug(f"Display FPS: {self.actual_fps:.1f}")
                
            except Exception as e:
                self.logger.error(f"Display loop error: {e}")
            
            # Maintain target FPS
            elapsed = time.time() - loop_start
            sleep_time = frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
            elif self.config.log_dropped_frames and elapsed > frame_time * 1.5:
                self.logger.warning(f"Display frame took {elapsed*1000:.1f}ms (target: {frame_time*1000:.1f}ms)")

    def _precompute_blend_mask(self, overlay_rgba):
        """Pre-compute overlay blend regions (only when overlay changes)"""
        if overlay_rgba is None:
            return None
        
        try:
            alpha = overlay_rgba[:, :, 3]
            if not np.any(alpha):
                return None

            # Find bounding box of non-transparent regions
            ys, xs = np.where(alpha > 0)
            y0, y1 = ys.min(), ys.max()
            x0, x1 = xs.min(), xs.max()

            # Store the overlay region and blend parameters
            o_sub = overlay_rgba[y0:y1+1, x0:x1+1]
            
            return {
                'bbox': (y0, y1, x0, x1),
                'overlay': o_sub,
                'alpha': o_sub[:, :, 3].astype(np.uint16),
                'rgb': o_sub[:, :, :3].astype(np.uint16)
            }
        except Exception:
            return None

    def _apply_blended_overlay(self, frame, blend_mask):
        """Apply pre-computed overlay blend (fast path)"""
        if blend_mask is None:
            return frame
        
        try:
            y0, y1, x0, x1 = blend_mask['bbox']
            o_rgb = blend_mask['rgb']
            o_a = blend_mask['alpha']
            
            # Extract frame subregion
            f_sub = frame[y0:y1+1, x0:x1+1].astype(np.uint16)
            
            # Fast integer blend
            a_exp = o_a[:, :, None].astype(np.uint32)
            o_exp = o_rgb.astype(np.uint32)
            f_exp = f_sub.astype(np.uint32)
            
            out_sub = (a_exp * o_exp + (255 - a_exp) * f_exp + 127) // 255
            out_sub = np.clip(out_sub, 0, 255).astype(np.uint8)
            
            # Write back
            frame[y0:y1+1, x0:x1+1] = out_sub
            return frame
            
        except Exception:
            return frame


    def _add_overlay(self, frame: np.ndarray) -> np.ndarray:
        """Legacy per-frame overlay renderer kept for compatibility but
        not used by the main loop. New code renders overlay into a cached
        RGBA buffer and composites via NumPy for much better performance.
        """
        img = Image.fromarray(frame)
        draw = ImageDraw.Draw(img, 'RGBA')

        # Draw simple time text to fallback path
        time_str = datetime.now().strftime(self.config.overlay_time_format)
        self._draw_text_with_bg(draw, time_str, self.config.overlay_time_pos, self.config.overlay_font_color, self.font)
        return np.array(img)

    def _render_overlay_rgba(self, rec_state: Optional[bool] = None, can_status: Optional[tuple] = None) -> Optional[np.ndarray]:
        """Render the overlay into an RGBA numpy array. This is called
        only when overlay content changes (time second, GPS speed, REC state).
        """
        if not self.config.overlay_enabled:
            return None

        # Create transparent overlay
        img = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img, 'RGBA')

        # Time and date
        now = datetime.now()
        time_str = now.strftime(self.config.overlay_time_format)
        self._draw_text_with_bg(draw, time_str, self.config.overlay_time_pos, self.config.overlay_font_color, self.font)

        if hasattr(self.config, 'overlay_date_pos'):
            date_str = now.strftime(self.config.overlay_date_format)
            self._draw_text_with_bg(draw, date_str, self.config.overlay_date_pos, self.config.overlay_font_color, self.font_small)

        # GPS speed
        if self.config.display_speed and hasattr(self.config, 'overlay_speed_pos'):
            with self.gps_lock:
                cs = self.current_speed
            if cs is not None:
                if self.config.speed_unit == "mph":
                    speed_text = f"{cs:.0f} MPH"
                else:
                    speed_kph = cs * 1.60934
                    speed_text = f"{speed_kph:.0f} KPH"
                self._draw_text_with_bg(draw, speed_text, self.config.overlay_speed_pos, self.config.overlay_font_color, self.font)

        # REC indicator (respect blink rate)
        if rec_state is None:
            rec_state = False
            if self.recording:
                if not self.config.rec_indicator_blink:
                    rec_state = True
                else:
                    # Stateless blink based on current time
                    blink_rate = max(0.01, float(self.config.rec_indicator_blink_rate))
                    rec_state = (int(time.time() / blink_rate) % 2) == 0

        if rec_state:
            rec_x, rec_y = self.config.overlay_rec_indicator_pos
            text_bbox = draw.textbbox((0, 0), self.config.rec_indicator_text, font=self.font)
            text_width = text_bbox[2] - text_bbox[0]
            rec_x -= text_width
            self._draw_text_with_bg(draw, self.config.rec_indicator_text, (rec_x, rec_y), self.config.rec_indicator_color, self.font)

        # CAN bus status indicator (always drawn when overlay enabled)
        if can_status is None:
            can_status = self._get_canbus_status()

        if can_status:
            can_text, can_color = can_status
            can_font = self.font_small or self.font
            can_x, can_y = getattr(self.config, "overlay_can_status_pos", self.config.overlay_rec_indicator_pos)
            text_bbox = draw.textbbox((0, 0), can_text, font=can_font)
            text_width = text_bbox[2] - text_bbox[0]
            can_x -= text_width
            self._draw_text_with_bg(draw, can_text, (can_x, can_y), can_color, can_font)

        return np.array(img)

    def _get_canbus_status(self) -> tuple[str, tuple[int, int, int]]:
        """Return CAN bus status text and color for the overlay."""
        disabled_text = getattr(self.config, "canbus_status_disabled_text", "CAN OFF")
        connecting_text = getattr(self.config, "canbus_status_connecting_text", "CAN WAIT")
        connected_text = getattr(self.config, "canbus_status_connected_text", "CAN OK")
        stale_timeout = float(getattr(self.config, "canbus_status_stale_timeout", 3.0) or 3.0)

        disabled_color = (180, 180, 180)
        connecting_color = (255, 200, 0)
        connected_color = (0, 200, 0)

        if not getattr(self.config, "canbus_enabled", False):
            return (disabled_text, disabled_color)

        connected = False
        last_message_time = 0.0
        with self.canbus_lock:
            vehicle = self.canbus_vehicle

        if vehicle is not None:
            try:
                if hasattr(vehicle, "get_stats"):
                    stats = vehicle.get_stats()
                    connected = bool(stats.get("connected", False))
                    last_message_time = float(stats.get("last_message_time") or 0.0)
            except Exception:
                pass

            if not connected and hasattr(vehicle, "canbus"):
                try:
                    bus = vehicle.canbus
                    connected = bool(getattr(bus, "connected", False))
                    last_message_time = float(getattr(bus, "last_message_time", 0.0) or 0.0)
                except Exception:
                    pass

        now = time.time()
        if connected and last_message_time and now - last_message_time <= stale_timeout:
            return (connected_text, connected_color)

        return (connecting_text, connecting_color)

    def _blend_overlay(self, frame: np.ndarray, overlay_rgba: np.ndarray) -> np.ndarray:
        """Alpha-blend RGBA overlay into RGB frame using NumPy (fast)."""
        if overlay_rgba is None:
            return frame

        # Ensure shapes
        if overlay_rgba.shape[0] != frame.shape[0] or overlay_rgba.shape[1] != frame.shape[1]:
            try:
                overlay_rgba = np.array(Image.fromarray(overlay_rgba).resize((frame.shape[1], frame.shape[0])))
            except Exception:
                return frame

        # Fast path: compute bounding box of non-zero alpha in overlay and
        # blend only that rectangle. Most overlays are small (time, date,
        # REC) so this drastically reduces computation.
        try:
            alpha = overlay_rgba[:, :, 3]
            # If completely transparent, nothing to do
            if not np.any(alpha):
                return frame

            ys, xs = np.where(alpha > 0)
            y0, y1 = ys.min(), ys.max()
            x0, x1 = xs.min(), xs.max()

            # Extract subregions
            o_sub = overlay_rgba[y0:y1+1, x0:x1+1]
            f_sub = frame[y0:y1+1, x0:x1+1]

            # Convert to small uint16/uint32 intermediates for integer blend
            o_rgb = o_sub[:, :, :3].astype(np.uint16)
            o_a = o_sub[:, :, 3].astype(np.uint16)
            f_rgb = f_sub.astype(np.uint16)

            a_exp = o_a[:, :, None].astype(np.uint32)
            o_exp = o_rgb.astype(np.uint32)
            f_exp = f_rgb.astype(np.uint32)

            out_sub = (a_exp * o_exp + (255 - a_exp) * f_exp + 127) // 255
            out_sub = np.clip(out_sub, 0, 255).astype(np.uint8)

            # Write back blended subregion
            frame[y0:y1+1, x0:x1+1] = out_sub
            return frame

        except Exception:
            # Fallback to full-frame float blend if anything goes wrong
            try:
                o_rgb = overlay_rgba[:, :, :3].astype(np.float32)
                o_a = overlay_rgba[:, :, 3:].astype(np.float32) / 255.0
                f_rgb = frame.astype(np.float32)
                out = (o_a * o_rgb) + ((1.0 - o_a) * f_rgb)
                out = np.clip(out, 0, 255).astype(np.uint8)
                return out
            except Exception:
                return frame
    
    def _draw_text_with_bg(self, draw: ImageDraw.Draw, text: str, pos: tuple, 
                           color: tuple, font: ImageFont.ImageFont):
        """Draw text with semi-transparent rounded background and optional shadow/outline."""
        x, y = pos

        # Rounded panel sizing
        padding = 5
        corner_radius = getattr(self.config, "overlay_corner_radius", 8)
        bbox = draw.textbbox((x, y), text, font=font)
        bbox = (bbox[0] - padding, bbox[1] - padding, bbox[2] + padding, bbox[3] + padding)

        # Optional shadow for depth (cheap: single offset fill, no blur)
        if getattr(self.config, "overlay_shadow_enabled", False):
            shadow_offset = getattr(self.config, "overlay_shadow_offset", (2, 2))
            shadow_alpha = getattr(self.config, "overlay_shadow_alpha", 80)
            shadow_color = getattr(self.config, "overlay_shadow_color", (0, 0, 0))
            sx, sy = shadow_offset
            shadow_bbox = (bbox[0] + sx, bbox[1] + sy, bbox[2] + sx, bbox[3] + sy)
            draw.rounded_rectangle(shadow_bbox, radius=corner_radius,
                                   fill=shadow_color + (shadow_alpha,))

        # Panel
        bg_color = self.config.overlay_bg_color + (self.config.overlay_bg_alpha,)
        draw.rounded_rectangle(bbox, radius=corner_radius, fill=bg_color)

        # Outline (kept thin) for legibility
        if self.config.overlay_outline:
            outline_color = self.config.overlay_outline_color
            for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)

        # Text
        draw.text((x, y), text, font=font, fill=color)

    def _apply_transform(self, frame: np.ndarray, rotation: int, hflip: bool, vflip: bool, mirror_mode: bool=False) -> np.ndarray:
        """Apply rotation and flips to a numpy RGB frame using PIL transposes.

        Rotation is applied in degrees (0/90/180/270). Flips (hflip/vflip) are
        applied after rotation. `mirror_mode` will apply an additional
        horizontal flip (useful for mirror display).
        """
        # Use NumPy operations for rotation/flips to avoid per-frame PIL conversions.
        # This significantly reduces allocations and CPU on the Pi.
        try:
            if frame is None:
                return frame

            img = frame
            # Ensure ndarray
            if not isinstance(img, np.ndarray):
                img = np.array(img)

            # Normalize rotation (0/90/180/270)
            r = int(rotation or 0) % 360
            if r != 0:
                k = (r // 90) % 4
                # np.rot90 rotates counter-clockwise k times
                img = np.rot90(img, k=k)

            if hflip:
                img = np.fliplr(img)

            if vflip:
                img = np.flipud(img)

            if mirror_mode:
                img = np.fliplr(img)

            return img

        except Exception as e:
            self.logger.debug(f"Transform failed (numpy), falling back: {e}")
            return frame

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

    def set_hardware_transform_applied(self, applied: bool):
        """Inform the display whether hardware (libcamera) applied transforms.

        When True the display will skip applying software rotation/hflip/vflip.
        """
        self.hw_transform_applied = bool(applied)
    
    def _write_frame(self, frame: np.ndarray):
        """Write frame to framebuffer in native format"""
        try:
            t_resize_start = time.time()
            if frame.shape[0] != self.height or frame.shape[1] != self.width:
                frame = self._resize_nn(frame, self.width, self.height)
            t_resize_end = time.time()

            if frame.dtype != np.uint8:
                frame = frame.astype(np.uint8)

            t_pack_start = time.time()
            
            if self._rgb565 is None:
                self._rgb565 = np.zeros((self.height, self.width), dtype=np.uint16)
            
            pack_rgb565_jit(frame, self._rgb565)
            buf = self._rgb565.astype('<u2').tobytes()
            
            t_pack_end = time.time()

            t_fb_start = time.time()
            try:
                if getattr(self, 'fb_file', None) is not None:
                    self.fb_file.seek(0)
                    self.fb_file.write(buf)
                    self.fb_file.flush()
                else:
                    with open(self.fb_device, 'wb') as f:
                        f.write(buf)
            except Exception:
                self.logger.debug("Framebuffer write failed; skipping frame write")
            t_fb_end = time.time()

            if self._prof_enabled:
                self._prof_resize += (t_resize_end - t_resize_start) * 1000.0
                self._prof_pack += (t_pack_end - t_pack_start) * 1000.0
                self._prof_fbwrite += (t_fb_end - t_fb_start) * 1000.0

        except Exception as e:
            self.logger.error(f"Failed to write frame: {e}")

    def _resize_nn(self, frame: np.ndarray, out_w: int, out_h: int) -> np.ndarray:
        """Nearest-neighbor resize using NumPy indexing. Returns a new array
        with shape (out_h, out_w, channels).
        """
        # Handle grayscale or single-channel frames by expanding dims
        if frame is None:
            return frame

        if frame.ndim == 2:
            frame = frame[:, :, None]

        src_h, src_w = frame.shape[:2]
        if src_h == out_h and src_w == out_w:
            return frame

        # Compute source indices for rows and cols
        row_idx = (np.arange(out_h) * (src_h / out_h)).astype(np.int32)
        col_idx = (np.arange(out_w) * (src_w / out_w)).astype(np.int32)

        # Clip indices to valid range
        row_idx = np.clip(row_idx, 0, src_h - 1)
        col_idx = np.clip(col_idx, 0, src_w - 1)

        # Use broadcasting to sample
        resized = frame[row_idx[:, None], col_idx]
        return resized
    
    def get_stats(self) -> dict:
        """Get display statistics"""
        return {
            'frame_count': self.frame_count,
            'recording': self.recording,
            'width': self.width,
            'height': self.height,
            'target_fps': self.fps,
            'actual_fps': self.actual_fps,
            'mirror_mode': self.mirror_mode
        }
