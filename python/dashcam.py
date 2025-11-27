#!/usr/bin/env python3
"""
Active Dash Mirror - Main Application
Raspberry Pi 5 Dashcam System with Dual CSI Cameras
"""

import sys
import os
import signal
import logging
import time
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Use package-qualified imports so the script works when executed
# from the `python/` directory or via systemd with the repo mounted
from dashcam.core.config import config
from dashcam.core.gps_handler import GPSHandler


class DashcamSystem:
    """Main dashcam system coordinator"""
    
    def __init__(self):
        self.config = config
        self.logger = None
        self.running = False
        
        # Components
        self.display = None
        self.recorder = None
        self.gps = None
        self.next_gps_retry = 0.0
        
        # Setup logging
        self._setup_logging()
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _setup_logging(self):
        """Configure logging system"""
        # Validate config
        self.config.validate()
        
        # Create logger
        self.logger = logging.getLogger()
        self.logger.setLevel(getattr(logging, self.config.log_level))
        
        # Console handler (if enabled)
        if self.config.log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
        
        # File handler with rotation
        log_file = os.path.join(
            self.config.log_dir,
            f"dashcam_{datetime.now().strftime('%Y%m%d')}.log"
        )
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=self.config.log_max_size,
            backupCount=self.config.log_backup_count
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        self.logger.info("=" * 60)
        self.logger.info("Active Dash Mirror - Starting")
        self.logger.info("Dual CSI Camera System")
        self.logger.info("=" * 60)
    
    def start(self):
        """Start dashcam system"""
        try:
            self.logger.info("Initializing dashcam system...")
            
            # Startup delay (let system stabilize)
            if self.config.startup_delay > 0:
                self.logger.info(f"Waiting {self.config.startup_delay}s for system to stabilize...")
                time.sleep(self.config.startup_delay)
            
            # Log configuration
            self._log_configuration()
            
            # Initialize display (import lazily to avoid circular imports)
            self.logger.info("Starting display...")
            backend = getattr(self.config, "display_backend", "fbdev")
            try:
                if backend == "drm":
                    from dashcam.platforms.pi5_arducam.video_display_drmkms import DrmKmsDisplay

                    card_path = getattr(self.config, "display_drm_card", "/dev/dri/card1")
                    self.logger.info(f"Using DRM/KMS display backend (card={card_path})")
                    self.display = DrmKmsDisplay(self.config, card_path=card_path)
                else:
                    from dashcam.platforms.pi5_arducam.video_display import VideoDisplay

                    self.logger.info("Using fbdev display backend (/dev/fb0)")
                    self.display = VideoDisplay(self.config)
            except Exception as e:
                self.logger.error(f"Failed to initialize display backend '{backend}': {e}")
                raise

            if not self.display.start():
                raise RuntimeError("Failed to start display")
            
            # Initialize GPS (if enabled)
            if self.config.gps_enabled:
                self.logger.info("Starting GPS...")
                self.gps = GPSHandler(self.config)
                if not self.gps.start():
                    if self.config.gps_required:
                        raise RuntimeError("GPS is required but failed to start")
                    else:
                        self.logger.warning("GPS failed to start, will retry in background")
                        self.gps = None
                        self.next_gps_retry = time.time() + self.config.gps_retry_delay
            else:
                self.logger.info("GPS disabled in configuration")
                self.gps = None
            
            # Link GPS to display if both are available
            if self.gps and self.display:
                self.logger.info("Linking GPS to display for speed overlay")
            
            # Initialize video recorder (import lazily to avoid circular imports)
            self.logger.info("Starting video recorder...")
            from dashcam.platforms.pi5_arducam.video_recorder import VideoRecorder
            self.recorder = VideoRecorder(self.config, self.display)
            if not self.recorder.start():
                raise RuntimeError("Failed to start video recorder")
            
            # Start recording (if cameras are configured to record)
            self.logger.info("Starting recording...")
            self.recorder.start_recording()
            
            self.running = True
            self.logger.info("Dashcam system started successfully")
            self.logger.info("=" * 60)
            
            # Main loop
            self._main_loop()
            
        except Exception as e:
            self.logger.error(f"Failed to start dashcam system: {e}", exc_info=True)
            self.stop()
            return False
    
    def stop(self):
        """Stop dashcam system"""
        if not self.running:
            return
        
        self.logger.info("=" * 60)
        self.logger.info("Shutting down dashcam system...")
        self.running = False
        
        # Stop components in reverse order
        if self.recorder:
            self.logger.info("Stopping video recorder...")
            try:
                self.recorder.stop()
            except Exception as e:
                self.logger.error(f"Error stopping recorder: {e}")
        
        if self.gps:
            self.logger.info("Stopping GPS...")
            try:
                self.gps.stop()
            except Exception as e:
                self.logger.error(f"Error stopping GPS: {e}")
        
        if self.display:
            self.logger.info("Stopping display...")
            try:
                self.display.stop()
            except Exception as e:
                self.logger.error(f"Error stopping display: {e}")
        
        self.logger.info("Dashcam system stopped")
        self.logger.info("=" * 60)
    
    def _main_loop(self):
        """Main monitoring loop"""
        status_interval = 30.0  # Log status every 30 seconds
        last_status_time = time.time()
        
        try:
            while self.running:
                time.sleep(1.0)
                
                # Retry GPS startup if it failed or stopped
                if (
                    self.config.gps_enabled and 
                    (self.gps is None or not getattr(self.gps, 'running', False))
                ):
                    if time.time() >= self.next_gps_retry:
                        self.logger.info("Attempting to (re)start GPS...")
                        self.gps = GPSHandler(self.config)
                        if self.gps.start():
                            self.logger.info("GPS (re)started successfully")
                            self.next_gps_retry = 0.0
                        else:
                            self.logger.warning(
                                f"GPS start retry failed; will retry in {self.config.gps_retry_delay}s"
                            )
                            self.gps = None
                            self.next_gps_retry = time.time() + self.config.gps_retry_delay
                
                # Update GPS data to display if available
                if self.gps and self.display and self.config.display_speed:
                    try:
                        gps_status = self.gps.get_status()
                        if gps_status['has_fix']:
                            self.display.update_gps_data(gps_status['speed_mph'])
                        else:
                            self.display.update_gps_data(None)
                    except Exception as e:
                        self.logger.debug(f"Error updating GPS display: {e}")
                
                # Periodic status logging
                if time.time() - last_status_time >= status_interval:
                    self._log_status()
                    last_status_time = time.time()
                
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        except Exception as e:
            self.logger.error(f"Main loop error: {e}", exc_info=True)
        finally:
            self.stop()
    
    def _signal_handler(self, signum, frame):
        """Handle system signals"""
        self.logger.info(f"Received signal {signum}")
        self.running = False
    
    def _log_configuration(self):
        """Log current configuration"""
        self.logger.info("Configuration:")
        self.logger.info(f"  Display: {self.config.display_width}x{self.config.display_height} @ {self.config.display_fps}fps")
        self.logger.info(f"  Mirror Mode: {self.config.display_mirror_mode}")
        
        # Front camera config
        if self.config.front_camera_enabled:
            self.logger.info(
                f"  Front Camera: {self.config.front_camera_width}x{self.config.front_camera_height} "
                f"@ {self.config.front_camera_fps}fps"
            )
            self.logger.info(f"    Recording: {self.config.front_camera_recording_enabled}")
            if self.config.front_camera_recording_enabled:
                self.logger.info(f"    Bitrate: {self.config.front_camera_bitrate/1000000:.1f}Mbps")
        
        # Rear camera config
        if self.config.rear_camera_enabled:
            self.logger.info(
                f"  Rear Camera: {self.config.rear_camera_width}x{self.config.rear_camera_height} "
                f"@ {self.config.rear_camera_fps}fps"
            )
            self.logger.info(f"    Recording: {self.config.rear_camera_recording_enabled}")
            if self.config.rear_camera_recording_enabled:
                self.logger.info(f"    Bitrate: {self.config.rear_camera_bitrate/1000000:.1f}Mbps")
        
        self.logger.info(f"  Video Codec: {self.config.video_codec}")
        self.logger.info(f"  Segment Duration: {self.config.video_segment_duration}s")
        self.logger.info(f"  Storage: {self.config.video_dir}")
        self.logger.info(f"  Minimum Free Space: {self.config.keep_minimum_gb}GB")
        self.logger.info(f"  Logs: {self.config.log_dir}")
        self.logger.info(f"  GPS: {'Enabled' if self.config.gps_enabled else 'Disabled'}")
        
        if self.config.gps_enabled and self.config.speed_recording_enabled:
            self.logger.info(f"  Speed Recording: Start at {self.config.start_recording_speed_mph} mph")
        elif self.config.front_camera_recording_enabled or self.config.rear_camera_recording_enabled:
            self.logger.info(f"  Recording Mode: Continuous")
    
    def _log_status(self):
        """Log current system status"""
        try:
            # Recorder stats
            if self.recorder:
                rec_stats = self.recorder.get_stats()
                status_parts = []
                
                if 'front_camera_ready' in rec_stats:
                    status_parts.append(f"Front={'ON' if rec_stats['front_camera_ready'] else 'OFF'}")
                    if rec_stats.get('front_recording'):
                        status_parts.append("F_REC=✓")
                
                if 'rear_camera_ready' in rec_stats:
                    status_parts.append(f"Rear={'ON' if rec_stats['rear_camera_ready'] else 'OFF'}")
                    if rec_stats.get('rear_recording'):
                        status_parts.append("R_REC=✓")
                
                if 'rear_frames' in rec_stats:
                    status_parts.append(f"Frames={rec_stats['rear_frames']}")
                
                if status_parts:
                    self.logger.info(f"Status: {', '.join(status_parts)}")
            
            # Display stats
            if self.display:
                disp_stats = self.display.get_stats()
                self.logger.debug(
                    f"Display: {disp_stats['frame_count']} frames, "
                    f"FPS: {disp_stats['actual_fps']:.1f}/{disp_stats['target_fps']}"
                )
            
            # GPS stats
            if self.gps:
                try:
                    gps_stats = self.gps.get_status()
                    if gps_stats['has_fix']:
                        self.logger.info(
                            f"GPS: {gps_stats['speed_mph']:.1f} mph, "
                            f"Position: {gps_stats['latitude']:.6f}, {gps_stats['longitude']:.6f}"
                        )
                    else:
                        self.logger.debug("GPS: No fix")
                except Exception as e:
                    self.logger.debug(f"GPS status error: {e}")
            
        except Exception as e:
            self.logger.error(f"Failed to log status: {e}")


def main():
    """Main entry point"""
    print("=" * 60)
    print("Active Dash Mirror")
    print("Raspberry Pi 5 Dashcam System")
    print("Dual CSI Camera Setup")
    print("=" * 60)
    print()
    
    # Check if running as root (needed for framebuffer access)
    if os.geteuid() != 0:
        print("WARNING: Not running as root. Framebuffer access may fail.")
        print("Consider running with: sudo python3 dashcam.py")
        print()
    
    # Create system
    system = DashcamSystem()
    
    # Setup signal handlers for graceful shutdown
    def handle_signal(signum, frame):
        """Handle termination signals"""
        try:
            if system:
                system.stop()
        finally:
            sys.exit(0)
    
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    
    # Start the system
    try:
        system.start()
    except KeyboardInterrupt:
        print("\nShutdown requested...")
        system.stop()
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        system.stop()
        sys.exit(1)
    
    print()
    print("=" * 60)
    print("Active Dash Mirror - Stopped")
    print("=" * 60)
    sys.exit(0)


if __name__ == "__main__":
    main()
