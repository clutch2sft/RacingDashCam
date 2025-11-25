"""
Video Display Handler for Active Dash Mirror
Direct framebuffer output with overlay rendering for dual CSI cameras
"""

import time
import logging
import numpy as np
from datetime import datetime
from threading import Thread, Event, Lock
from typing import Optional
from PIL import Image, ImageDraw, ImageFont


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
        
        # GPS data (optional)
        self.current_speed = None
        self.gps_lock = Lock()
        
        # Display thread
        self.running = False
        self.thread = None
        self.stop_event = Event()
        
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
                
                # Apply mirror mode if enabled
                if self.mirror_mode and frame.size > 0:
                    frame = np.fliplr(frame)
                
                # Add overlay if enabled
                if self.config.overlay_enabled:
                    frame = self._add_overlay(frame)
                
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
        """Add overlay information to frame"""
        # Convert to PIL Image for easier text rendering
        img = Image.fromarray(frame)
        draw = ImageDraw.Draw(img, 'RGBA')
        
        # Update blink state for recording indicator
        current_time = time.time()
        if current_time - self.last_blink_time >= self.config.rec_indicator_blink_rate:
            self.rec_blink_state = not self.rec_blink_state
            self.last_blink_time = current_time
        
        # Draw time
        time_str = datetime.now().strftime(self.config.overlay_time_format)
        self._draw_text_with_bg(
            draw, 
            time_str, 
            self.config.overlay_time_pos,
            self.config.overlay_font_color,
            self.font
        )
        
        # Draw date (below time)
        if hasattr(self.config, 'overlay_date_pos'):
            date_str = datetime.now().strftime(self.config.overlay_date_format)
            self._draw_text_with_bg(
                draw,
                date_str,
                self.config.overlay_date_pos,
                self.config.overlay_font_color,
                self.font_small
            )
        
        # Draw GPS speed if available
        if self.config.display_speed and hasattr(self.config, 'overlay_speed_pos'):
            with self.gps_lock:
                if self.current_speed is not None:
                    if self.config.speed_unit == "mph":
                        speed_text = f"{self.current_speed:.0f} MPH"
                    else:
                        speed_kph = self.current_speed * 1.60934
                        speed_text = f"{speed_kph:.0f} KPH"
                    
                    self._draw_text_with_bg(
                        draw,
                        speed_text,
                        self.config.overlay_speed_pos,
                        self.config.overlay_font_color,
                        self.font
                    )
        
        # Draw recording indicator
        if self.recording:
            # Blink or solid
            if not self.config.rec_indicator_blink or self.rec_blink_state:
                rec_x, rec_y = self.config.overlay_rec_indicator_pos
                
                # Adjust position to right-align
                text_bbox = draw.textbbox((0, 0), self.config.rec_indicator_text, font=self.font)
                text_width = text_bbox[2] - text_bbox[0]
                rec_x -= text_width
                
                self._draw_text_with_bg(
                    draw, 
                    self.config.rec_indicator_text, 
                    (rec_x, rec_y),
                    self.config.rec_indicator_color,
                    self.font
                )
        
        # Convert back to numpy array
        return np.array(img)
    
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
    
    def _write_frame(self, frame: np.ndarray):
        """Write frame to framebuffer as 16-bit RGB565"""
        try:
            # 1) Resize to framebuffer resolution if needed
            if frame.shape[0] != self.height or frame.shape[1] != self.width:
                img = Image.fromarray(frame)
                img = img.resize((self.width, self.height), Image.BILINEAR)
                frame = np.array(img)

            # 2) Ensure 8-bit channels
            if frame.dtype != np.uint8:
                frame = frame.astype(np.uint8)

            # Picamera2 returns RGB, so no need to convert from BGR

            # 3) Split into channels as uint16 for math
            r = frame[:, :, 0].astype(np.uint16)
            g = frame[:, :, 1].astype(np.uint16)
            b = frame[:, :, 2].astype(np.uint16)

            # 4) Pack to RGB565: 5 bits R, 6 bits G, 5 bits B
            r5 = (r >> 3) & 0x1F       # top 5 bits
            g6 = (g >> 2) & 0x3F       # top 6 bits
            b5 = (b >> 3) & 0x1F       # top 5 bits

            rgb565 = (r5 << 11) | (g6 << 5) | b5  # shape (H, W), dtype=uint16

            # 5) Convert to bytes (little-endian on Pi)
            buf = rgb565.tobytes()

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
