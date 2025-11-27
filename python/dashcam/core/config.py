"""
Active Dash Mirror - Configuration
All configurable settings for the dashcam system
"""

import os
from typing import Any, Dict, Tuple

import yaml


CONFIG_PATH = os.environ.get("DASHCAM_CONFIG", "/etc/dashcam/config.yaml")


class Config:
    """Central configuration for dashcam system"""

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path or CONFIG_PATH
        self._user_overrides: set[str] = set()
        self._set_defaults()
        self._load_from_yaml(self.config_path)
        self._finalize_paths()
        self._normalize_sequences()

    # ==========================================
    # Default values
    # ==========================================
    def _set_defaults(self):
        # Directory Configuration
        self.base_dir = os.environ.get("DASHCAM_BASE_DIR", "/opt/dashcam")
        self.video_dir = os.path.join(self.base_dir, "videos")
        self.video_current_dir = os.path.join(self.video_dir, "current")
        self.video_archive_dir = os.path.join(self.video_dir, "archive")
        self.log_dir = os.path.join(self.base_dir, "logs")

        # Camera Configuration - Dual CSI Setup
        self.front_camera_enabled = True
        self.front_camera_index = 0
        self.front_camera_width = 1920
        self.front_camera_height = 1080
        self.front_camera_fps = 15
        self.front_camera_recording_enabled = True

        self.rear_camera_enabled = True
        self.rear_camera_index = 1
        self.rear_camera_width = 1920
        self.rear_camera_height = 1080
        self.rear_camera_fps = 15
        self.rear_camera_recording_enabled = True

        self.display_camera_index = 1

        # Camera-specific settings
        self.front_camera_rotation = 180
        self.front_camera_hflip = False
        self.front_camera_vflip = False

        self.rear_camera_rotation = 180
        self.rear_camera_hflip = True
        self.rear_camera_vflip = False

        # Video Recording Configuration
        self.video_codec = "h264"
        self.front_camera_bitrate = 8000000
        self.rear_camera_bitrate = 8000000
        self.video_segment_duration = 60
        self.front_camera_prefix = "front"
        self.rear_camera_prefix = "rear"
        self.disk_high_water_mark = 0.75
        self.keep_minimum_gb = 10.0

        # Display Configuration
        self.display_width = 1920
        self.display_height = 1080
        self.display_fps = 15
        self.display_backend = "drm"
        self.display_drm_card = "/dev/dri/card1"
        self.display_input_is_bgr = False
        self.use_framebuffer = True
        self.framebuffer_device = "/dev/fb0"
        self.display_fullscreen = True
        self.display_mirror_mode = True

        # Overlay Configuration
        self.overlay_enabled = True
        self.overlay_time_format = "%H:%M:%S"
        self.overlay_date_format = "%Y-%m-%d"
        self.overlay_time_pos = (20, 20)
        self.overlay_date_pos = (20, 60)
        self.overlay_speed_pos = (20, 100)
        self.overlay_rec_indicator_pos = (1820, 20)
        self.overlay_font_size = 32
        self.overlay_font_color = (255, 255, 255)
        self.overlay_bg_color = (0, 0, 0)
        self.overlay_bg_alpha = 96
        self.overlay_corner_radius = 8
        self.overlay_shadow_enabled = True
        self.overlay_shadow_offset = (2, 2)
        self.overlay_shadow_alpha = 80
        self.overlay_shadow_color = (0, 0, 0)
        self.overlay_outline = True
        self.overlay_outline_color = (0, 0, 0)
        self.rec_indicator_text = "⬤ REC"
        self.rec_indicator_color = (255, 0, 0)
        self.rec_indicator_blink = False
        self.rec_indicator_blink_rate = 1.0

        # GPS Configuration
        self.gps_enabled = True
        self.gps_device = "/dev/ttyAMA0"
        self.gps_baudrate = 115200
        self.gps_timeout = 1.0
        self.gps_log_interval = 1.0
        self.display_speed = True
        self.speed_unit = "mph"
        self.speed_recording_enabled = True
        self.start_recording_speed_mph = 15.0
        self.stop_recording_delay_seconds = 120

        # CAN Bus Configuration
        self.canbus_enabled = False
        self.canbus_channel = "can0"
        self.canbus_bitrate = 500000
        self.canbus_vehicle_type = "camaro_2013_lfx"
        self.display_canbus_data = False
        self.canbus_overlay_position = (20, 140)
        self.record_canbus_data = False
        self.canbus_log_interval = 1.0

        # Fuel Consumption Configuration
        self.display_fuel_consumed = True
        self.fuel_overlay_position = (20, 140)
        self.fuel_flow_conversion_factor = 0.01
        self.fuel_safety_margin = 1.025
        self.fuel_auto_reset_enabled = True
        self.fuel_auto_reset_threshold = 95.0
        self.fuel_auto_reset_duration = 5.0
        self.fuel_display_unit = "gallons"
        self.fuel_display_decimals = 3

        # Performance Configuration
        self.camera_buffer_count = 4
        self.encoder_buffer_count = 6
        self.use_threading = True
        self.display_thread_priority = 1
        self.frame_queue_size = 2

        # Error Handling Configuration
        self.camera_retry_attempts = 3
        self.camera_retry_delay = 2.0
        self.camera_failure_reboot = False
        self.continue_on_single_camera = True
        self.gps_retry_attempts = 5
        self.gps_retry_delay = 5.0
        self.gps_required = False

        # Logging Configuration
        self.log_level = "INFO"
        self.log_max_size = 10 * 1024 * 1024
        self.log_backup_count = 5
        self.log_to_console = True
        self.log_fps = True
        self.log_dropped_frames = True

        # System Configuration
        self.startup_delay = 3.0
        self.shutdown_grace_period = 5.0
        self.watchdog_enabled = True
        self.watchdog_timeout = 30.0
        self.cpu_governor = "performance"

        # Advanced Camera Configuration
        self.auto_exposure = True
        self.auto_white_balance = True
        self.auto_focus = False
        self.exposure_time = 10000
        self.analog_gain = 1.0
        self.awb_red_gain = 1.5
        self.awb_blue_gain = 1.5
        self.contrast = 1.0
        self.brightness = 0.0
        self.saturation = 1.0
        self.sharpness = 1.0

    # ==========================================
    # YAML loading
    # ==========================================
    def _apply_value(self, attr: str, value: Any):
        setattr(self, attr, value)
        self._user_overrides.add(attr)

    def _apply_resolution(self, attr_width: str, attr_height: str, value: Any):
        if isinstance(value, (list, tuple)):
            values = list(value)
            if len(values) == 2:
                self._apply_value(attr_width, int(values[0]))
                self._apply_value(attr_height, int(values[1]))

    def _apply_section(self, data: Dict[str, Any], mapping: Dict[str, Any]):
        for key, target in mapping.items():
            if key not in data:
                continue
            value = data[key]
            if isinstance(target, dict):
                if isinstance(value, dict):
                    self._apply_section(value, target)
                continue
            if isinstance(target, tuple) and len(target) == 2:
                self._apply_resolution(target[0], target[1], value)
            else:
                self._apply_value(target, value)

    def _load_from_yaml(self, config_path: str | None):
        if not config_path or not os.path.exists(config_path):
            return

        with open(config_path, "r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}

        if not isinstance(loaded, dict):
            raise ValueError("Configuration file must contain a top-level mapping")

        mapping = {
            "paths": {
                "base_dir": "base_dir",
                "video_dir": "video_dir",
                "current_dir": "video_current_dir",
                "archive_dir": "video_archive_dir",
                "log_dir": "log_dir",
            },
            "video": {
                "codec": "video_codec",
                "front_bitrate": "front_camera_bitrate",
                "rear_bitrate": "rear_camera_bitrate",
                "segment_duration": "video_segment_duration",
                "front_prefix": "front_camera_prefix",
                "rear_prefix": "rear_camera_prefix",
                "disk_high_water_mark": "disk_high_water_mark",
                "keep_minimum_gb": "keep_minimum_gb",
            },
            "cameras": {
                "front": {
                    "enabled": "front_camera_enabled",
                    "index": "front_camera_index",
                    "resolution": ("front_camera_width", "front_camera_height"),
                    "fps": "front_camera_fps",
                    "recording_enabled": "front_camera_recording_enabled",
                    "bitrate": "front_camera_bitrate",
                    "rotation": "front_camera_rotation",
                    "hflip": "front_camera_hflip",
                    "vflip": "front_camera_vflip",
                },
                "rear": {
                    "enabled": "rear_camera_enabled",
                    "index": "rear_camera_index",
                    "resolution": ("rear_camera_width", "rear_camera_height"),
                    "fps": "rear_camera_fps",
                    "recording_enabled": "rear_camera_recording_enabled",
                    "bitrate": "rear_camera_bitrate",
                    "rotation": "rear_camera_rotation",
                    "hflip": "rear_camera_hflip",
                    "vflip": "rear_camera_vflip",
                },
                "display_camera_index": "display_camera_index",
            },
            "display": {
                "resolution": ("display_width", "display_height"),
                "fps": "display_fps",
                "backend": "display_backend",
                "drm_card": "display_drm_card",
                "input_is_bgr": "display_input_is_bgr",
                "use_framebuffer": "use_framebuffer",
                "framebuffer_device": "framebuffer_device",
                "fullscreen": "display_fullscreen",
                "mirror_mode": "display_mirror_mode",
            },
            "overlay": {
                "enabled": "overlay_enabled",
                "time_format": "overlay_time_format",
                "date_format": "overlay_date_format",
                "time_pos": "overlay_time_pos",
                "date_pos": "overlay_date_pos",
                "speed_pos": "overlay_speed_pos",
                "rec_indicator_pos": "overlay_rec_indicator_pos",
                "font_size": "overlay_font_size",
                "font_color": "overlay_font_color",
                "bg_color": "overlay_bg_color",
                "bg_alpha": "overlay_bg_alpha",
                "corner_radius": "overlay_corner_radius",
                "shadow_enabled": "overlay_shadow_enabled",
                "shadow_offset": "overlay_shadow_offset",
                "shadow_alpha": "overlay_shadow_alpha",
                "shadow_color": "overlay_shadow_color",
                "outline": "overlay_outline",
                "outline_color": "overlay_outline_color",
                "rec_indicator_text": "rec_indicator_text",
                "rec_indicator_color": "rec_indicator_color",
                "rec_indicator_blink": "rec_indicator_blink",
                "rec_indicator_blink_rate": "rec_indicator_blink_rate",
            },
            "gps": {
                "enabled": "gps_enabled",
                "device": "gps_device",
                "baudrate": "gps_baudrate",
                "timeout": "gps_timeout",
                "log_interval": "gps_log_interval",
                "display_speed": "display_speed",
                "speed_unit": "speed_unit",
                "speed_recording_enabled": "speed_recording_enabled",
                "start_recording_speed_mph": "start_recording_speed_mph",
                "stop_recording_delay_seconds": "stop_recording_delay_seconds",
                "retry_attempts": "gps_retry_attempts",
                "retry_delay": "gps_retry_delay",
                "gps_required": "gps_required",
            },
            "canbus": {
                "enabled": "canbus_enabled",
                "channel": "canbus_channel",
                "bitrate": "canbus_bitrate",
                "vehicle_type": "canbus_vehicle_type",
                "display_data": "display_canbus_data",
                "overlay_position": "canbus_overlay_position",
                "record_data": "record_canbus_data",
                "log_interval": "canbus_log_interval",
            },
            "fuel": {
                "display_fuel_consumed": "display_fuel_consumed",
                "overlay_position": "fuel_overlay_position",
                "flow_conversion_factor": "fuel_flow_conversion_factor",
                "safety_margin": "fuel_safety_margin",
                "auto_reset_enabled": "fuel_auto_reset_enabled",
                "auto_reset_threshold": "fuel_auto_reset_threshold",
                "auto_reset_duration": "fuel_auto_reset_duration",
                "display_unit": "fuel_display_unit",
                "display_decimals": "fuel_display_decimals",
            },
            "performance": {
                "camera_buffer_count": "camera_buffer_count",
                "encoder_buffer_count": "encoder_buffer_count",
                "use_threading": "use_threading",
                "display_thread_priority": "display_thread_priority",
                "frame_queue_size": "frame_queue_size",
            },
            "errors": {
                "camera_retry_attempts": "camera_retry_attempts",
                "camera_retry_delay": "camera_retry_delay",
                "camera_failure_reboot": "camera_failure_reboot",
                "continue_on_single_camera": "continue_on_single_camera",
            },
            "logging": {
                "level": "log_level",
                "max_size": "log_max_size",
                "backup_count": "log_backup_count",
                "to_console": "log_to_console",
                "log_fps": "log_fps",
                "log_dropped_frames": "log_dropped_frames",
            },
            "system": {
                "startup_delay": "startup_delay",
                "shutdown_grace_period": "shutdown_grace_period",
                "watchdog_enabled": "watchdog_enabled",
                "watchdog_timeout": "watchdog_timeout",
                "cpu_governor": "cpu_governor",
            },
            "camera_control": {
                "auto_exposure": "auto_exposure",
                "auto_white_balance": "auto_white_balance",
                "auto_focus": "auto_focus",
                "exposure_time": "exposure_time",
                "analog_gain": "analog_gain",
                "awb_red_gain": "awb_red_gain",
                "awb_blue_gain": "awb_blue_gain",
                "contrast": "contrast",
                "brightness": "brightness",
                "saturation": "saturation",
                "sharpness": "sharpness",
            },
        }

        for section, section_mapping in mapping.items():
            if section in loaded and isinstance(loaded[section], dict):
                self._apply_section(loaded[section], section_mapping)

    # ==========================================
    # Helpers
    # ==========================================
    def _finalize_paths(self):
        if "video_dir" not in self._user_overrides:
            self.video_dir = os.path.join(self.base_dir, "videos")
        if "video_current_dir" not in self._user_overrides:
            self.video_current_dir = os.path.join(self.video_dir, "current")
        if "video_archive_dir" not in self._user_overrides:
            self.video_archive_dir = os.path.join(self.video_dir, "archive")
        if "log_dir" not in self._user_overrides:
            self.log_dir = os.path.join(self.base_dir, "logs")

    def _as_tuple(self, value: Any, length: int) -> Tuple[int, ...]:
        if isinstance(value, (list, tuple)) and len(value) >= length:
            return tuple(int(value[i]) for i in range(length))
        return tuple(int(value) for _ in range(length))

    def _normalize_sequences(self):
        tuple_fields = {
            "overlay_time_pos": 2,
            "overlay_date_pos": 2,
            "overlay_speed_pos": 2,
            "overlay_rec_indicator_pos": 2,
            "overlay_font_color": 3,
            "overlay_bg_color": 3,
            "overlay_shadow_offset": 2,
            "overlay_shadow_color": 3,
            "overlay_outline_color": 3,
            "rec_indicator_color": 3,
            "canbus_overlay_position": 2,
            "fuel_overlay_position": 2,
        }
        for attr, length in tuple_fields.items():
            value = getattr(self, attr, None)
            if value is None:
                continue
            setattr(self, attr, self._as_tuple(value, length))

    # ==========================================
    # Validation and helpers
    # ==========================================
    def validate(self):
        """Validate configuration and create directories if needed"""
        os.makedirs(self.video_current_dir, exist_ok=True)
        os.makedirs(self.video_archive_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

        assert self.front_camera_width > 0, "Invalid front camera width"
        assert self.front_camera_height > 0, "Invalid front camera height"
        assert self.front_camera_fps > 0, "Invalid front camera FPS"

        assert self.rear_camera_width > 0, "Invalid rear camera width"
        assert self.rear_camera_height > 0, "Invalid rear camera height"
        assert self.rear_camera_fps > 0, "Invalid rear camera FPS"

        assert 0 < self.disk_high_water_mark < 1, "High water mark must be between 0 and 1"
        assert self.video_segment_duration > 0, "Segment duration must be positive"
        assert self.front_camera_bitrate > 0, "Front camera bitrate must be positive"
        assert self.rear_camera_bitrate > 0, "Rear camera bitrate must be positive"

        assert self.display_width > 0, "Invalid display width"
        assert self.display_height > 0, "Invalid display height"

        assert self.front_camera_enabled or self.rear_camera_enabled, "At least one camera must be enabled"

        if self.display_camera_index == 0:
            assert self.front_camera_enabled, "Display camera (front) must be enabled"
        else:
            assert self.rear_camera_enabled, "Display camera (rear) must be enabled"

        return True

    def get_camera_config(self, camera_index):
        """Get configuration dictionary for a specific camera"""
        if camera_index == self.front_camera_index:
            return {
                "index": self.front_camera_index,
                "width": self.front_camera_width,
                "height": self.front_camera_height,
                "fps": self.front_camera_fps,
                "rotation": self.front_camera_rotation,
                "hflip": self.front_camera_hflip,
                "vflip": self.front_camera_vflip,
                "bitrate": self.front_camera_bitrate,
                "prefix": self.front_camera_prefix,
                "recording_enabled": self.front_camera_recording_enabled,
            }
        if camera_index == self.rear_camera_index:
            return {
                "index": self.rear_camera_index,
                "width": self.rear_camera_width,
                "height": self.rear_camera_height,
                "fps": self.rear_camera_fps,
                "rotation": self.rear_camera_rotation,
                "hflip": self.rear_camera_hflip,
                "vflip": self.rear_camera_vflip,
                "bitrate": self.rear_camera_bitrate,
                "prefix": self.rear_camera_prefix,
                "recording_enabled": self.rear_camera_recording_enabled,
            }
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
  Backend: {self.display_backend}
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
