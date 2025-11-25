"""
Video Display Handler for Active Dash Mirror
Direct framebuffer output with overlay rendering for dual CSI cameras
"""

import time
import logging
import os
import numpy as np
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
        
        # Performance tracking
        self.last_fps_calc = time.time()
        self.fps_frame_count = 0
        self.actual_fps = 0.0
        
        # Overlay state
        self.recording = False
        self.rec_blink_state = False
        self.last_blink_time = time.time()

        # Overlay caching (to avoid re-rendering every frame)
        self._overlay_rgba = None  # Cached RGBA overlay as numpy array
        self._overlay_last_time_sec = None
        self._overlay_last_speed = None
        self._overlay_last_rec_state = None
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
            # Open framebuffer
            self.fb_file = open(self.fb_device, 'wb')
            
            # Clear screen to black
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
    
    def _display_loop(self):
        """Main display loop"""
        frame_time = 1.0 / self.fps
        
        while self.running and not self.stop_event.is_set():
            loop_start = time.time()
            
            try:
                # Get current frame
                with self.frame_lock:
                    if self.current_frame is not None:
                        frame = self.current_frame.copy()
                    else:
                        # No frame yet, show black
                        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
                
                # Apply per-camera transforms (rotation, hflip, vflip) only if
                # hardware hasn't already applied them. If hardware transform is
                # applied we skip software rotation/flips to avoid double-transform.
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
                
                # Add overlay if enabled. Use cached overlay rendered only
                # when content changes (time second, GPS speed, REC state).
                if self.config.overlay_enabled:
                    now_sec = datetime.now().second
                    with self._overlay_lock:
                        with self.gps_lock:
                            cs = self.current_speed

                        # Calculate current rec state (stateless blink)
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
                            or (cs is not None and self._overlay_last_speed is not None and int(cs) != int(self._overlay_last_speed))
                            or self._overlay_last_rec_state != rec_state
                        )

                        if needs_update:
                            try:
                                self._overlay_rgba = self._render_overlay_rgba()
                            except Exception as e:
                                self.logger.debug(f"Overlay render failed: {e}")
                                self._overlay_rgba = None

                            self._overlay_last_time_sec = now_sec
                            self._overlay_last_speed = cs
                            self._overlay_last_rec_state = rec_state

                    # Composite overlay (fast NumPy blend)
                    try:
                        frame = self._blend_overlay(frame, self._overlay_rgba)
                    except Exception as e:
                        self.logger.debug(f"Overlay blend failed: {e}")
                
                # Write to framebuffer
                self._write_frame(frame)
                
                # Update FPS counter
                self.fps_frame_count += 1
                if time.time() - self.last_fps_calc >= 1.0:
                    self.actual_fps = self.fps_frame_count / (time.time() - self.last_fps_calc)
                    self.fps_frame_count = 0
                    self.last_fps_calc = time.time()
                    
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

    def _render_overlay_rgba(self) -> Optional[np.ndarray]:
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

        return np.array(img)

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

        # Separate channels
        o_rgb = overlay_rgba[:, :, :3].astype(np.float32)
        o_a = overlay_rgba[:, :, 3:].astype(np.float32) / 255.0

        f_rgb = frame.astype(np.float32)

        # Composite: out = o_a*o_rgb + (1-o_a)*f_rgb
        out = (o_a * o_rgb) + ((1.0 - o_a) * f_rgb)
        out = np.clip(out, 0, 255).astype(np.uint8)
        return out
    
    def _draw_text_with_bg(self, draw: ImageDraw.Draw, text: str, pos: tuple, 
                           color: tuple, font: ImageFont.ImageFont):
        """Draw text with semi-transparent background and optional outline"""
        x, y = pos
        
        # Draw outline if enabled
        if self.config.overlay_outline:
            outline_color = self.config.overlay_outline_color
            for dx, dy in [(-1,-1), (-1,1), (1,-1), (1,1), (-1,0), (1,0), (0,-1), (0,1)]:
                draw.text((x+dx, y+dy), text, font=font, fill=outline_color)
        
        # Get text bounding box
        bbox = draw.textbbox((x, y), text, font=font)
        
        # Add padding
        padding = 5
        bbox = (bbox[0] - padding, bbox[1] - padding, 
                bbox[2] + padding, bbox[3] + padding)
        
        # Draw background
        bg_color = self.config.overlay_bg_color + (self.config.overlay_bg_alpha,)
        draw.rectangle(bbox, fill=bg_color)
        
        # Draw text
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

    def set_hardware_transform_applied(self, applied: bool):
        """Inform the display whether hardware (libcamera) applied transforms.

        When True the display will skip applying software rotation/hflip/vflip.
        """
        self.hw_transform_applied = bool(applied)
    
    def _write_frame(self, frame: np.ndarray):
        """Write frame to framebuffer as 16-bit RGB565"""
        try:
            # 1) Resize to framebuffer resolution if needed using a fast
            # nearest-neighbor NumPy sampler to avoid PIL allocations.
            if frame.shape[0] != self.height or frame.shape[1] != self.width:
                frame = self._resize_nn(frame, self.width, self.height)

            # 2) Ensure 8-bit channels
            if frame.dtype != np.uint8:
                frame = frame.astype(np.uint8)

            # 3) Split into channels as uint16 for math
            r = frame[:, :, 0].astype(np.uint16)
            g = frame[:, :, 1].astype(np.uint16)
            b = frame[:, :, 2].astype(np.uint16)

            # 4) Pack to RGB565: 5 bits R, 6 bits G, 5 bits B
            r5 = (r >> 3) & 0x1F       # top 5 bits
            g6 = (g >> 2) & 0x3F       # top 6 bits
            b5 = (b >> 3) & 0x1F       # top 5 bits

            rgb565 = ((r5 << 11) | (g6 << 5) | b5).astype(np.uint16)

            # 5) Convert to bytes (force little-endian uint16 byte order)
            buf = rgb565.astype('<u2').tobytes()

            expected_bytes = self.width * self.height * 2
            if len(buf) != expected_bytes:
                # Safety clamp if something goes weird
                buf = buf[:expected_bytes]

            # 6) Write to framebuffer
            self.fb_file.seek(0)
            self.fb_file.write(buf)
            self.fb_file.flush()

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
