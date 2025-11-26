"""
Active Dash Mirror - Configuration
All configurable settings for the dashcam system
"""

import os

class Config:
    """Central configuration for dashcam system"""
    
    def __init__(self):
        # ==========================================
        # Directory Configuration
        # ==========================================
        # Base directory can be overridden with the DASHCAM_BASE_DIR env var
        self.base_dir = os.environ.get("DASHCAM_BASE_DIR", "/opt/dashcam")

        # Video and log directories are located under the base directory
        self.video_dir = os.path.join(self.base_dir, "videos")
        self.video_current_dir = os.path.join(self.video_dir, "current")
        self.video_archive_dir = os.path.join(self.video_dir, "archive")
        self.log_dir = os.path.join(self.base_dir, "logs")
        
        # ==========================================
        # Camera Configuration - Dual CSI Setup
        # ==========================================
        # Front camera (Arducam HQ 12.3MP) - CSI CAM0 - Picamera2 index 0
        # High-quality camera for front recording
        self.front_camera_enabled = True
        self.front_camera_index = 0  # CAM0 (closer to USB-C port)
        self.front_camera_width = 1920
        self.front_camera_height = 1080
        self.front_camera_fps = 15
        self.front_camera_recording_enabled = True
        
        # Rear camera (Arducam HQ 12.3MP) - CSI CAM1 - Picamera2 index 1
        # Wide angle (158°) camera for rearview mirror display
        self.rear_camera_enabled = True
        self.rear_camera_index = 1  # CAM1 (closer to HDMI port)
        self.rear_camera_width = 1920  # HQ camera can do 1920x1080
        self.rear_camera_height = 1080
        self.rear_camera_fps = 15  # Reduced default to 15fps for performance
        self.rear_camera_recording_enabled = True  # Enable recording from rear
        
        # Display configuration - shows rear camera on screen
        self.display_camera_index = 1  # Show rear camera (mirror view)
        
        # Camera-specific settings
        # Front Arducam HQ settings
        self.front_camera_rotation = 180  # Adjust if camera is mounted rotated
        self.front_camera_hflip = False
        self.front_camera_vflip = False
        
        # Arducam HQ settings
        self.rear_camera_rotation = 180  # Adjust if needed
        self.rear_camera_hflip = True
        self.rear_camera_vflip = False
        
        # ==========================================
        # Video Recording Configuration
        # ==========================================
        self.video_codec = "h264"
        
        # Front camera recording (1080p high quality)
        self.front_camera_bitrate = 8000000  # 8 Mbps for 1080p
        
        # Rear camera recording (1080p)
        self.rear_camera_bitrate = 8000000  # 8 Mbps for 1080p
        
        # Segment settings
        self.video_segment_duration = 60  # 60 seconds per file
        
        # File naming
        self.front_camera_prefix = "front"  # front_YYYYMMDD_HHMMSS_####.h264
        self.rear_camera_prefix = "rear"    # rear_YYYYMMDD_HHMMSS_####.h264
        
        # File management
        self.disk_high_water_mark = 0.75  # Start cleanup at 75% full
        self.keep_minimum_gb = 10.0  # Always keep 10GB free (dual 1080p needs more)
        
        # ==========================================
        # Display Configuration
        # ==========================================
        self.display_width = 1920
        self.display_height = 1080
        self.display_fps = 15  # Lower default to 15fps for reduced CPU usage
        
        # Display format (for direct framebuffer rendering)
        self.use_framebuffer = True  # Direct rendering to /dev/fb0
        self.framebuffer_device = "/dev/fb0"
        
        # Display transformations
        self.display_fullscreen = True
        self.display_mirror_mode = True  # True for traditional mirror (flipped)
        
        # ==========================================
        # Overlay Configuration
        # ==========================================
        self.overlay_enabled = True
        self.overlay_time_format = "%H:%M:%S"  # 24-hour format
        self.overlay_date_format = "%Y-%m-%d"
        
        # Overlay positions (from top-left)
        self.overlay_time_pos = (20, 20)  # Top-left
        self.overlay_date_pos = (20, 60)  # Below time
        self.overlay_speed_pos = (20, 100)  # Below date (when GPS enabled)
        self.overlay_rec_indicator_pos = (1820, 20)  # Top-right
        
        # Overlay styling
        self.overlay_font_size = 32
        self.overlay_font_color = (255, 255, 255)  # White
        self.overlay_bg_color = (0, 0, 0)  # Black background
        self.overlay_bg_alpha = 128  # Semi-transparent
        self.overlay_outline = True  # Add outline for better visibility
        self.overlay_outline_color = (0, 0, 0)  # Black outline
        
        # Recording indicator
        self.rec_indicator_text = "⬤ REC"
        self.rec_indicator_color = (255, 0, 0)  # Red
        self.rec_indicator_blink = False
        self.rec_indicator_blink_rate = 1.0  # Seconds
        
        # ==========================================
        # GPS Configuration
        # ==========================================
        self.gps_enabled = True  # Enable when GPS module is connected
        # Waveshare LC29H GPS/RTK HAT on Raspberry Pi 5
        # Use /dev/ttyAMA0 for Pi 5 (not /dev/serial0)
        # Yellow jumper must be at position B for UART mode
        self.gps_device = "/dev/ttyAMA0"  # LC29H on UART (Pi 5)
        self.gps_baudrate = 115200  # LC29H default baud rate (not 9600)
        self.gps_timeout = 1.0
        self.gps_log_interval = 1.0  # Log GPS data every second
        
        # GPS display
        self.display_speed = True  # Show speed on overlay
        self.speed_unit = "mph"  # "mph" or "kph"
        
        # Speed-based recording (when GPS is enabled)
        self.speed_recording_enabled = False  # Set True to only record when moving
        self.start_recording_speed_mph = 5.0  # Start recording above 5 mph
        self.stop_recording_delay_seconds = 120  # Keep recording 2 min after stopping
        
        # ==========================================
        # CAN Bus Configuration
        # ==========================================
        self.canbus_enabled = False  # Enable CAN bus interface
        self.canbus_channel = "can0"  # CAN channel for vehicle data (can0 or can1)
        self.canbus_bitrate = 500000  # 500 kbps for GM HS-CAN
        self.canbus_vehicle_type = "camaro_2013_lfx"  # Vehicle-specific implementation
        
        # CAN data overlay
        self.display_canbus_data = False  # Show CAN data on display
        self.canbus_overlay_position = (20, 140)  # Position for CAN data overlay
        
        # CAN data recording
        self.record_canbus_data = False  # Log CAN data to file
        self.canbus_log_interval = 1.0  # Log CAN data every second
        
        # ==========================================
        # Performance Configuration
        # ==========================================
        # Buffer sizes
        self.camera_buffer_count = 4  # Number of buffers for camera
        self.encoder_buffer_count = 6  # Number of buffers for encoder
        
        # Threading
        self.use_threading = True  # Use separate threads for cameras
        self.display_thread_priority = 1  # Higher priority for display smoothness
        
        # Queue sizes
        self.frame_queue_size = 2  # Small queue for low latency
        
        # ==========================================
        # Error Handling Configuration
        # ==========================================
        # Camera recovery
        self.camera_retry_attempts = 3
        self.camera_retry_delay = 2.0  # Seconds between retries
        self.camera_failure_reboot = False  # Set True for production
        
        # If one camera fails, continue with the other
        self.continue_on_single_camera = True
        
        # GPS recovery
        self.gps_retry_attempts = 5
        self.gps_retry_delay = 5.0  # Seconds between retries
        self.gps_required = False  # Set True if GPS is mandatory
        
        # ==========================================
        # Logging Configuration
        # ==========================================
        self.log_level = "INFO"  # DEBUG, INFO, WARNING, ERROR
        self.log_max_size = 10 * 1024 * 1024  # 10MB
        self.log_backup_count = 5
        self.log_to_console = True  # Also log to console
        
        # Performance logging
        self.log_fps = True  # Log actual FPS achieved
        self.log_dropped_frames = True  # Log if frames are dropped
        
        # ==========================================
        # System Configuration
        # ==========================================
        self.startup_delay = 3.0  # Wait 3 seconds before starting cameras
        self.shutdown_grace_period = 5.0  # Time to finish recording on shutdown
        
        # Watchdog
        self.watchdog_enabled = True
        self.watchdog_timeout = 30.0  # Restart if no activity for 30 seconds
        
        # Power management
        self.cpu_governor = "performance"  # Set CPU governor for best performance
        
        # ==========================================
        # Advanced Camera Configuration
        # ==========================================
        # Picamera2 control settings
        self.auto_exposure = True
        self.auto_white_balance = True
        self.auto_focus = False  # Fixed focus lenses
        
        # Exposure settings (when auto_exposure = False)
        self.exposure_time = 10000  # Microseconds
        self.analog_gain = 1.0
        
        # White balance (when auto_white_balance = False)
        self.awb_red_gain = 1.5
        self.awb_blue_gain = 1.5
        
        # Image quality
        self.contrast = 1.0
        self.brightness = 0.0
        self.saturation = 1.0
        self.sharpness = 1.0
        
    def validate(self):
        """Validate configuration and create directories if needed"""
        # Create directories if they don't exist
        os.makedirs(self.video_current_dir, exist_ok=True)
        os.makedirs(self.video_archive_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Validate camera settings
        assert self.front_camera_width > 0, "Invalid front camera width"
        assert self.front_camera_height > 0, "Invalid front camera height"
        assert self.front_camera_fps > 0, "Invalid front camera FPS"
        
        assert self.rear_camera_width > 0, "Invalid rear camera width"
        assert self.rear_camera_height > 0, "Invalid rear camera height"
        assert self.rear_camera_fps > 0, "Invalid rear camera FPS"
        
        # Validate recording settings
        assert 0 < self.disk_high_water_mark < 1, "High water mark must be between 0 and 1"
        assert self.video_segment_duration > 0, "Segment duration must be positive"
        assert self.front_camera_bitrate > 0, "Front camera bitrate must be positive"
        assert self.rear_camera_bitrate > 0, "Rear camera bitrate must be positive"
        
        # Validate display settings
        assert self.display_width > 0, "Invalid display width"
        assert self.display_height > 0, "Invalid display height"
        
        # Validate at least one camera is enabled
        assert self.front_camera_enabled or self.rear_camera_enabled, \
            "At least one camera must be enabled"
        
        # Validate display camera is enabled
        if self.display_camera_index == 0:
            assert self.front_camera_enabled, "Display camera (front) must be enabled"
        else:
            assert self.rear_camera_enabled, "Display camera (rear) must be enabled"
        
        return True
    
    def get_camera_config(self, camera_index):
        """Get configuration dictionary for a specific camera"""
        if camera_index == self.front_camera_index:
            return {
                'index': self.front_camera_index,
                'width': self.front_camera_width,
                'height': self.front_camera_height,
                'fps': self.front_camera_fps,
                'rotation': self.front_camera_rotation,
                'hflip': self.front_camera_hflip,
                'vflip': self.front_camera_vflip,
                'bitrate': self.front_camera_bitrate,
                'prefix': self.front_camera_prefix,
                'recording_enabled': self.front_camera_recording_enabled,
            }
        elif camera_index == self.rear_camera_index:
            return {
                'index': self.rear_camera_index,
                'width': self.rear_camera_width,
                'height': self.rear_camera_height,
                'fps': self.rear_camera_fps,
                'rotation': self.rear_camera_rotation,
                'hflip': self.rear_camera_hflip,
                'vflip': self.rear_camera_vflip,
                'bitrate': self.rear_camera_bitrate,
                'prefix': self.rear_camera_prefix,
                'recording_enabled': self.rear_camera_recording_enabled,
            }
        else:
            raise ValueError(f"Invalid camera index: {camera_index}")
    
    def __str__(self):
        """String representation for debugging"""
        return f"""
Active Dash Mirror Configuration
=================================
Cameras:
  Front (Arducam HQ): {self.front_camera_width}x{self.front_camera_height}@{self.front_camera_fps}fps
                      Recording: {self.front_camera_recording_enabled}
  Rear (Arducam HQ): {self.rear_camera_width}x{self.rear_camera_height}@{self.rear_camera_fps}fps
                     Recording: {self.rear_camera_recording_enabled}
Display:
  Resolution: {self.display_width}x{self.display_height}
  Camera: {'Rear' if self.display_camera_index == 1 else 'Front'}
  Mirror Mode: {self.display_mirror_mode}
Recording:
  Front Bitrate: {self.front_camera_bitrate/1000000:.1f} Mbps
  Rear Bitrate: {self.rear_camera_bitrate/1000000:.1f} Mbps
  Segment Duration: {self.video_segment_duration}s
GPS:
  Enabled: {self.gps_enabled}
  Speed Recording: {self.speed_recording_enabled}
Storage:
  Video Directory: {self.video_dir}
  Keep Free: {self.keep_minimum_gb} GB
"""


# Global config instance
config = Config()
