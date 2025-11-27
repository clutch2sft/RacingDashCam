"""
Video Recorder for Active Dash Mirror
Manages dual CSI camera capture, encoding, and file management
- Front camera (Arducam HQ CSI CAM0) for H.264 recording
- Rear camera (Arducam HQ CSI CAM1) for H.264 recording + display
"""

import time
import logging
import os
import shutil
from datetime import datetime
from threading import Thread, Event, Lock
from typing import Optional

import numpy as np

try:
    from picamera2 import Picamera2, ColourSpace
    from picamera2.encoders import H264Encoder, Quality
    from picamera2.outputs import FfmpegOutput
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    logging.warning("Picamera2 not available")


class CameraRecorder:
    """Handles a single CSI camera's recording with H.264 hardware encoding"""

    def __init__(self, camera_index: int, config, camera_config: dict, is_display_camera: bool = False):
        self.camera_index = camera_index
        self.config = config
        self.camera_config = camera_config
        self.is_display_camera = is_display_camera
        self.logger = logging.getLogger(f"Camera{camera_index}")

        # Camera settings from config
        self.width = camera_config['width']
        self.height = camera_config['height']
        self.fps = camera_config['fps']
        self.bitrate = camera_config['bitrate']
        self.prefix = camera_config['prefix']
        self.recording_enabled = camera_config['recording_enabled']

        # Camera
        self.camera = None
        self.camera_ready = False

        # Recording state
        self.recording = False
        self.encoder = None
        self.current_output_file = None
        self.current_segment_start = None
        self.video_counter = 0

        # For display camera, track frames
        self.latest_frame = None
        self.frame_lock = Lock()
        self.frame_count = 0
        # Whether the camera transform was applied in hardware (libcamera)
        self.hardware_transform_applied = False

    def init_camera(self) -> bool:
        """Initialize this CSI camera"""
        try:
            self.logger.info(f"Initializing camera {self.camera_index} ({self.prefix})...")

            if not PICAMERA2_AVAILABLE:
                raise RuntimeError("Picamera2 not available")

            # Create camera instance
            self.camera = Picamera2(camera_num=self.camera_index)

            # Configure camera based on usage
            if self.is_display_camera:
                # Display camera needs both RGB for display and YUV for encoding
                self.logger.debug(
                    f"Creating dual-stream config for display camera: "
                    f"{self.width}x{self.height}@{self.fps}fps"
                )
                camera_config = self.camera.create_video_configuration(
                    main={"size": (self.width, self.height), "format": "YUV420"},  # For encoder
                    # Explicitly request RGB output from ISP to avoid per-frame BGR->RGB swaps
                    lores={
                        "size": (self.width, self.height),
                        "format": "RGB888",
                        "colour_space": ColourSpace.Srgb,
                    },
                    controls={
                        "FrameRate": self.fps,
                    }
                )
            else:
                # Recording-only camera just needs YUV for encoding
                self.logger.debug(
                    f"Creating single-stream config for recording camera: "
                    f"{self.width}x{self.height}@{self.fps}fps"
                )
                camera_config = self.camera.create_video_configuration(
                    main={"size": (self.width, self.height), "format": "YUV420"},
                    controls={
                        "FrameRate": self.fps,
                    }
                )

            # Apply camera-specific transformations.
            # Picamera2 expects camera_config['transform'] to be a libcamera Transform
            # object (or an object with hflip/vflip/rotation attributes). Create a
            # Transform when libcamera is available, otherwise attempt to set
            # attributes on any existing transform object.
            try:
                # Build transform values from our camera_config dict
                hflip_val = bool(self.camera_config.get('hflip', False))
                vflip_val = bool(self.camera_config.get('vflip', False))
                rotation_val = int(self.camera_config.get('rotation', 0) or 0) % 360

                # Try to import libcamera Transform (only on systems with libcamera)
                try:
                    from libcamera import Transform as LibTransform  # type: ignore
                    transform_obj = LibTransform(hflip=int(hflip_val), vflip=int(vflip_val), rotation=rotation_val)
                    camera_config['transform'] = transform_obj
                    # mark that we applied the transform in hardware
                    self.hardware_transform_applied = True
                except Exception:
                    # If libcamera isn't available or construction failed, try
                    # to set attributes on an existing transform object if present
                    try:
                        existing = camera_config.get('transform') if isinstance(camera_config, dict) else None
                    except Exception:
                        existing = None

                    if existing is not None:
                        # Some CameraConfiguration implementations expose a transform
                        # object; set attributes if possible
                        try:
                            if hasattr(existing, 'hflip'):
                                setattr(existing, 'hflip', bool(hflip_val))
                            if hasattr(existing, 'vflip'):
                                setattr(existing, 'vflip', bool(vflip_val))
                            if hasattr(existing, 'rotation'):
                                setattr(existing, 'rotation', int(rotation_val))
                            camera_config['transform'] = existing
                            # if we could set attributes on the existing transform, treat as applied
                            self.hardware_transform_applied = True
                        except Exception:
                            # As a last resort, log and continue without transform
                            self.logger.debug("Could not apply camera transform on this platform")

            except Exception as e:
                self.logger.debug(f"Transform setup skipped: {e}")

            self.logger.debug(f"Configuring camera... hardware_transform_applied={self.hardware_transform_applied}")
            self.camera.configure(camera_config)

            # Set camera controls if needed
            if self.config.auto_exposure:
                self.camera.set_controls({"AeEnable": True})
            
            if self.config.auto_white_balance:
                self.camera.set_controls({"AwbEnable": True})

            self.logger.debug("Starting camera...")
            self.camera.start()

            # Let auto-exposure/white balance settle
            time.sleep(2.0)

            self.camera_ready = True
            self.logger.info(
                f"Camera {self.camera_index} initialized: "
                f"{self.width}x{self.height}@{self.fps}fps (display={self.is_display_camera})"
            )
            return True

        except Exception as e:
            self.logger.error(f"Camera {self.camera_index} initialization failed: {e}")
            if self.camera:
                try:
                    self.camera.stop()
                except Exception:
                    pass
                try:
                    self.camera.close()
                except Exception:
                    pass
                self.camera = None
            self.camera_ready = False
            return False

    def _build_output_filename(self) -> str:
        """Build an output filename for H.264"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.prefix}_{timestamp}_{self.video_counter:04d}.h264"
        self.video_counter += 1
        return os.path.join(self.config.video_current_dir, filename)

    def start_recording(self):
        """Start H.264 hardware recording from this camera"""
        if self.recording or not self.camera_ready or not self.recording_enabled:
            if not self.recording_enabled:
                self.logger.debug(f"Recording disabled for camera {self.camera_index}")
            return

        try:
            self.current_output_file = self._build_output_filename()

            self.logger.debug(
                f"Starting H264 encoding for camera {self.camera_index} "
                f"at {self.bitrate}bps -> {self.current_output_file}"
            )
            
            # Create H.264 encoder with specified bitrate
            self.encoder = H264Encoder(bitrate=self.bitrate)

            # Start encoding from the main stream
            self.camera.start_encoder(self.encoder, self.current_output_file)

            self.recording = True
            self.current_segment_start = time.time()
            self.logger.info(
                f"Recording (H.264) to: {os.path.basename(self.current_output_file)}"
            )

        except Exception as e:
            self.logger.error(f"Failed to start recording: {e}")
            self.recording = False
            self.current_output_file = None
            self.current_segment_start = None

            if self.encoder is not None and self.camera is not None:
                try:
                    self.camera.stop_encoder()
                except Exception:
                    pass
                self.encoder = None

    def stop_recording(self):
        """Stop recording"""
        if not self.recording:
            return

        try:
            self.logger.info(f"Stopping recording camera {self.camera_index}...")

            if self.camera and self.encoder:
                self.camera.stop_encoder()
                self.encoder = None

            # Archive the file
            if self.current_output_file and os.path.exists(self.current_output_file):
                archive_path = os.path.join(
                    self.config.video_archive_dir,
                    os.path.basename(self.current_output_file)
                )
                shutil.move(self.current_output_file, archive_path)
                file_size_mb = os.path.getsize(archive_path) / (1024 * 1024)
                self.logger.info(
                    f"Archived: {os.path.basename(archive_path)} ({file_size_mb:.1f}MB)"
                )

            self.recording = False
            self.current_output_file = None
            self.current_segment_start = None

        except Exception as e:
            self.logger.error(f"Error stopping recording: {e}")

    def capture_frame(self) -> Optional[np.ndarray]:
        """Capture a frame for display (only works for display camera with lores stream)"""
        if not self.camera_ready or not self.is_display_camera:
            return None

        try:
            # Capture from lores stream (RGB888 for display)
            frame = self.camera.capture_array("lores")
            
            with self.frame_lock:
                self.latest_frame = frame
                self.frame_count += 1
            
            return frame

        except Exception as e:
            self.logger.error(f"Frame capture error: {e}")
            return None

    def close(self):
        """Close camera and cleanup"""
        try:
            if self.recording:
                self.stop_recording()

            if self.camera:
                self.camera.stop()
                self.camera.close()
                self.camera = None

            self.camera_ready = False
            self.logger.info(f"Camera {self.camera_index} closed")

        except Exception as e:
            self.logger.error(f"Error closing camera: {e}")


class VideoRecorder:
    """Manages dual CSI camera recording and display"""

    def __init__(self, config, display):
        self.config = config
        self.display = display
        self.logger = logging.getLogger("VideoRecorder")

        # Camera instances
        self.front_camera = None
        self.rear_camera = None
        self.display_camera = None  # Reference to whichever camera we display

        # Threads
        self.running = False
        self.stop_event = Event()
        self.rear_capture_thread = None
        self.segment_manager_thread = None
        self.file_manager_thread = None

        # Error recovery
        self.camera_retry_count = 0

    def start(self) -> bool:
        """Start cameras and recording"""
        try:
            self.logger.info("Starting video recorder...")

            # Initialize front camera (Arducam HQ)
            if self.config.front_camera_enabled:
                front_config = self.config.get_camera_config(self.config.front_camera_index)
                self.front_camera = CameraRecorder(
                    camera_index=self.config.front_camera_index,
                    config=self.config,
                    camera_config=front_config,
                    is_display_camera=False
                )

                if not self.front_camera.init_camera():
                    if not self.config.continue_on_single_camera:
                        self.logger.error("Front camera initialization failed")
                        return False
                    else:
                        self.logger.warning("Front camera failed, continuing with rear only")
                        self.front_camera = None

            # Initialize rear camera (Arducam HQ)
            if self.config.rear_camera_enabled:
                rear_config = self.config.get_camera_config(self.config.rear_camera_index)
                self.rear_camera = CameraRecorder(
                    camera_index=self.config.rear_camera_index,
                    config=self.config,
                    camera_config=rear_config,
                    is_display_camera=True  # This camera provides display frames
                )

                if not self.rear_camera.init_camera():
                    if not self.config.continue_on_single_camera:
                        self.logger.error("Rear camera initialization failed")
                        return False
                    else:
                        self.logger.warning("Rear camera failed, continuing with front only")
                        self.rear_camera = None

            # Check that at least one camera initialized
            if not self.front_camera and not self.rear_camera:
                self.logger.error("No cameras available")
                return False

            # Set which camera we're displaying
            if self.config.display_camera_index == self.config.rear_camera_index and self.rear_camera:
                self.display_camera = self.rear_camera
            elif self.config.display_camera_index == self.config.front_camera_index and self.front_camera:
                self.display_camera = self.front_camera
            else:
                # Fallback to whichever camera is available
                self.display_camera = self.rear_camera if self.rear_camera else self.front_camera

            if not self.display_camera:
                self.logger.error("No display camera available")
                return False

            self.logger.info(f"Display camera set to: camera {self.display_camera.camera_index}")

            # Inform the display whether the camera applied transforms in hardware
            try:
                hw_applied = getattr(self.display_camera, 'hardware_transform_applied', False)
                if self.display:
                    try:
                        # call display API if available
                        self.display.set_hardware_transform_applied(hw_applied)
                    except Exception:
                        self.logger.debug("Display does not support hardware transform notification")
            except Exception:
                pass

            # Start threads
            self.running = True
            self.stop_event.clear()

            # Rear camera capture thread (for display)
            self.rear_capture_thread = Thread(
                target=self._rear_capture_loop,
                daemon=True
            )
            self.rear_capture_thread.start()

            # Segment manager thread
            self.segment_manager_thread = Thread(
                target=self._segment_manager_loop,
                daemon=True
            )
            self.segment_manager_thread.start()

            # File manager thread
            self.file_manager_thread = Thread(
                target=self._file_manager_loop,
                daemon=True
            )
            self.file_manager_thread.start()

            self.logger.info("Video recorder started successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start video recorder: {e}")
            return False

    def stop(self):
        """Stop recording and cleanup"""
        self.logger.info("Stopping video recorder...")
        self.running = False
        self.stop_event.set()

        # Stop recording
        self.stop_recording()

        # Wait for threads
        if self.rear_capture_thread:
            self.rear_capture_thread.join(timeout=2.0)

        if self.segment_manager_thread:
            self.segment_manager_thread.join(timeout=2.0)

        if self.file_manager_thread:
            self.file_manager_thread.join(timeout=5.0)

        # Close cameras
        if self.rear_camera:
            self.rear_camera.close()

        if self.front_camera:
            self.front_camera.close()

        self.logger.info("Video recorder stopped")

    def start_recording(self):
        """Start recording on cameras that have recording enabled"""
        any_recording = False

        # Front camera recording
        if self.front_camera and self.config.front_camera_recording_enabled:
            self.front_camera.start_recording()
            any_recording = any_recording or self.front_camera.recording

        # Rear camera recording
        if self.rear_camera and self.config.rear_camera_recording_enabled:
            self.rear_camera.start_recording()
            any_recording = any_recording or self.rear_camera.recording

        # Update display REC indicator
        self.display.set_recording(any_recording)

    def stop_recording(self):
        """Stop recording on all cameras"""
        if self.rear_camera and self.rear_camera.recording:
            self.rear_camera.stop_recording()

        if self.front_camera and self.front_camera.recording:
            self.front_camera.stop_recording()

        self.display.set_recording(False)

    def _rear_capture_loop(self):
        """Capture frames from display camera and send to display"""
        if not self.display_camera:
            self.logger.error("No display camera available")
            return

        target_fps = self.display_camera.fps
        frame_interval = 1.0 / max(1, target_fps)
        
        self.logger.info(f"Starting capture loop for camera {self.display_camera.camera_index} at {target_fps}fps")
        
        while self.running and not self.stop_event.is_set():
            try:
                if self.display_camera.camera_ready:
                    frame = self.display_camera.capture_frame()
                    if frame is not None:
                        self.display.update_frame(frame)

                time.sleep(frame_interval)

            except Exception as e:
                self.logger.error(f"Display capture loop error: {e}")
                if not self._recover_cameras():
                    break

    def _segment_manager_loop(self):
        """Manage video segment rotation"""
        while self.running and not self.stop_event.is_set():
            try:
                ref_cam = None

                # Use front camera as reference if recording
                if (
                    self.front_camera
                    and self.config.front_camera_recording_enabled
                    and self.front_camera.recording
                ):
                    ref_cam = self.front_camera
                # Otherwise use rear camera
                elif (
                    self.rear_camera
                    and self.config.rear_camera_recording_enabled
                    and self.rear_camera.recording
                ):
                    ref_cam = self.rear_camera

                if ref_cam and ref_cam.current_segment_start:
                    elapsed = time.time() - ref_cam.current_segment_start
                    if elapsed >= self.config.video_segment_duration:
                        self.logger.info("Rotating video segments...")
                        self.stop_recording()
                        time.sleep(0.5)
                        self.start_recording()

                time.sleep(1.0)

            except Exception as e:
                self.logger.error(f"Segment manager error: {e}")

    def _file_manager_loop(self):
        """Manage disk space and cleanup"""
        check_interval = 60.0

        while self.running and not self.stop_event.wait(check_interval):
            try:
                self._check_disk_space()
            except Exception as e:
                self.logger.error(f"File manager error: {e}")

    def _check_disk_space(self):
        """Check disk space and cleanup if needed"""
        try:
            stat = shutil.disk_usage(self.config.video_dir)
            total = stat.total
            used = stat.used
            free = stat.free

            usage_percent = used / total
            free_gb = free / (1024 ** 3)

            if (
                usage_percent > self.config.disk_high_water_mark
                or free_gb < self.config.keep_minimum_gb
            ):
                self.logger.warning(
                    f"Disk usage high: {usage_percent*100:.1f}% used, "
                    f"{free_gb:.1f}GB free"
                )
                self._cleanup_old_files()

        except Exception as e:
            self.logger.error(f"Failed to check disk space: {e}")

    def _cleanup_old_files(self):
        """Delete oldest archived H.264 files"""
        try:
            archive_dir = self.config.video_archive_dir
            files = []

            for filename in os.listdir(archive_dir):
                filepath = os.path.join(archive_dir, filename)
                if os.path.isfile(filepath) and filename.endswith(".h264"):
                    mtime = os.path.getmtime(filepath)
                    files.append((mtime, filepath))

            files.sort()

            if not files:
                return

            deleted_count = 0
            deleted_size = 0

            for mtime, filepath in files:
                stat = shutil.disk_usage(self.config.video_dir)
                usage_percent = stat.used / stat.total
                free_gb = stat.free / (1024 ** 3)

                if (
                    usage_percent <= (self.config.disk_high_water_mark - 0.05)
                    and free_gb >= self.config.keep_minimum_gb
                ):
                    break

                file_size = os.path.getsize(filepath)
                os.remove(filepath)
                deleted_count += 1
                deleted_size += file_size

                self.logger.info(f"Deleted: {os.path.basename(filepath)}")

            if deleted_count > 0:
                deleted_mb = deleted_size / (1024 * 1024)
                self.logger.info(
                    f"Cleanup: deleted {deleted_count} files ({deleted_mb:.1f}MB)"
                )

        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")

    def _recover_cameras(self) -> bool:
        """Attempt to recover from camera errors"""
        self.logger.warning("Attempting camera recovery...")
        self.camera_retry_count += 1

        if self.camera_retry_count > self.config.camera_retry_attempts:
            self.logger.error("Camera recovery failed after maximum retries")

            if self.config.camera_failure_reboot:
                self.logger.critical("Rebooting system...")
                os.system("sudo reboot")

            return False

        # Try to reinitialize display camera
        if self.display_camera:
            self.display_camera.close()
            time.sleep(2.0)
            
            camera_config = self.config.get_camera_config(self.display_camera.camera_index)
            if not self.display_camera.init_camera():
                return False

        self.camera_retry_count = 0
        return True

    def get_stats(self) -> dict:
        """Get recorder statistics"""
        stats = {}

        if self.rear_camera:
            stats.update({
                "rear_camera_ready": self.rear_camera.camera_ready,
                "rear_recording": self.rear_camera.recording,
                "rear_frames": self.rear_camera.frame_count,
            })

        if self.front_camera:
            stats.update({
                "front_camera_ready": self.front_camera.camera_ready,
                "front_recording": self.front_camera.recording,
            })

        return stats
