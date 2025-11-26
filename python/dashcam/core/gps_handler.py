"""
GPS Handler for Active Dash Mirror
Handles GPS communication and data logging
"""

import time
import logging
import json
import os
from datetime import datetime
from threading import Thread, Event
from typing import Optional, Dict

try:
    import gps
    GPS_AVAILABLE = True
except ImportError:
    GPS_AVAILABLE = False
    logging.warning("GPS libraries not available")


class GPSHandler:
    """Manages GPS communication and data logging"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("GPSHandler")
        
        if not config.gps_enabled:
            self.logger.info("GPS is disabled in configuration")
            self.enabled = False
            return
            
        if not GPS_AVAILABLE:
            self.logger.error("GPS libraries not installed")
            self.enabled = False
            return
            
        self.enabled = True
        self.session = None
        self.running = False
        self.thread = None
        self.stop_event = Event()
        
        # GPS data
        self.latitude = 0.0
        self.longitude = 0.0
        self.speed_mph = 0.0
        self.speed_kph = 0.0
        self.altitude = 0.0
        self.heading = 0.0
        self.fix_quality = 0
        self.satellites = 0
        self.timestamp = None
        self.has_fix = False
        
        # Logging
        self.log_file = None
        self.log_path = os.path.join(config.log_dir, f"gps_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        # Recovery
        self.retry_count = 0
        self.last_data_time = None
        
    def start(self):
        """Start GPS handler"""
        if not self.enabled:
            return False
            
        try:
            # Connect to GPSD with retries in case the daemon isn't ready yet
            attempts = max(1, int(self.config.gps_retry_attempts))
            for attempt in range(1, attempts + 1):
                try:
                    # Note: gpsd should be configured to listen on localhost:2947 (default)
                    # and should already be monitoring the configured GPS device
                    self.logger.info(
                        f"Connecting to GPSD (device: {self.config.gps_device} @ {self.config.gps_baudrate} baud)... "
                        f"[attempt {attempt}/{attempts}]"
                    )
                    self.session = gps.gps(mode=gps.WATCH_ENABLE | gps.WATCH_NEWSTYLE)
                    break
                except Exception as e:
                    self.logger.warning(f"GPSD connection attempt {attempt}/{attempts} failed: {e}")
                    if attempt >= attempts:
                        raise
                    time.sleep(self.config.gps_retry_delay)
            
            # Reset runtime state for a fresh start
            self.retry_count = 0
            self.last_data_time = None
            
            # Open log file
            self.log_file = open(self.log_path, 'w')
            self.log_file.write('[\n')  # Start JSON array
            
            # Start processing thread
            self.running = True
            self.stop_event.clear()
            self.thread = Thread(target=self._process_loop, daemon=True)
            self.thread.start()
            
            self.logger.info("GPS handler started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start GPS: {e}")
            self.logger.error("Ensure GPSD is running and configured with the correct device")
            return False
    
    def stop(self):
        """Stop GPS handler"""
        if not self.enabled or not self.running:
            return
            
        self.logger.info("Stopping GPS handler...")
        self.running = False
        self.stop_event.set()
        
        if self.thread:
            self.thread.join(timeout=5.0)
            
        if self.log_file:
            self.log_file.write('\n]')  # Close JSON array
            self.log_file.close()
            
        if self.session:
            self.session.close()
            
        self.logger.info("GPS handler stopped")
    
    def _process_loop(self):
        """Main GPS processing loop"""
        first_entry = True
        try:
            while self.running and not self.stop_event.is_set():
                try:
                    # Read GPS data with timeout
                    if self.session.waiting(timeout=1.0):
                        report = self.session.next()
                        
                        if report['class'] == 'TPV':
                            # Time-Position-Velocity report
                            self._update_from_tpv(report)
                            self.last_data_time = time.time()
                            
                            # Log data
                            if time.time() % self.config.gps_log_interval < 0.1:
                                self._log_data(first_entry)
                                first_entry = False
                    
                    # Check for stale data only after we have seen at least one report
                    if self.last_data_time and (time.time() - self.last_data_time > 10.0):
                        self.logger.warning("GPS data is stale, attempting recovery...")
                        if not self._recover():
                            break
                            
                except Exception as e:
                    self.logger.error(f"GPS processing error: {e}")
                    if not self._recover():
                        break
        finally:
            # Ensure running flag reflects thread state if we exit unexpectedly
            self.running = False
    
    def _update_from_tpv(self, report: Dict):
        """Update GPS data from TPV report"""
        self.timestamp = report.get('time', None)
        self.latitude = report.get('lat', 0.0)
        self.longitude = report.get('lon', 0.0)
        
        # Speed in m/s, convert to mph and kph
        speed_ms = report.get('speed', 0.0)
        self.speed_kph = speed_ms * 3.6
        self.speed_mph = speed_ms * 2.23694
        
        self.altitude = report.get('alt', 0.0)
        self.heading = report.get('track', 0.0)
        
        # Fix quality
        mode = report.get('mode', 0)
        self.has_fix = mode >= 2  # 2D or 3D fix
        self.fix_quality = mode
    
    def _log_data(self, first_entry: bool):
        """Log GPS data to file"""
        if not self.log_file:
            return
            
        data = {
            'timestamp': self.timestamp or datetime.now().isoformat(),
            'latitude': self.latitude,
            'longitude': self.longitude,
            'speed_mph': round(self.speed_mph, 2),
            'speed_kph': round(self.speed_kph, 2),
            'altitude': round(self.altitude, 2),
            'heading': round(self.heading, 2),
            'fix': self.has_fix,
            'quality': self.fix_quality,
            'satellites': self.satellites
        }
        
        try:
            if not first_entry:
                self.log_file.write(',\n')
            json.dump(data, self.log_file, indent=2)
            self.log_file.flush()
        except Exception as e:
            self.logger.error(f"Failed to log GPS data: {e}")
    
    def _recover(self) -> bool:
        """Attempt to recover GPS connection"""
        self.retry_count += 1
        
        if self.retry_count > self.config.gps_retry_attempts:
            self.logger.error("GPS recovery failed after maximum retries")
            return False
            
        self.logger.info(f"GPS recovery attempt {self.retry_count}/{self.config.gps_retry_attempts}")
        
        try:
            # Close existing session
            if self.session:
                self.session.close()
                
            time.sleep(self.config.gps_retry_delay)
            
            # Try to reconnect
            self.session = gps.gps(mode=gps.WATCH_ENABLE | gps.WATCH_NEWSTYLE)
            self.retry_count = 0
            self.last_data_time = None
            self.logger.info("GPS recovered successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"GPS recovery failed: {e}")
            return False
    
    def should_record(self) -> bool:
        """Check if recording should be active based on speed"""
        if not self.config.speed_recording_enabled or not self.enabled:
            return True  # Always record if speed-based recording is disabled
            
        if not self.has_fix:
            return True  # Record if no GPS fix (safety fallback)
            
        return self.speed_mph >= self.config.start_recording_speed_mph
    
    def get_status(self) -> Dict:
        """Get current GPS status"""
        return {
            'enabled': self.enabled,
            'has_fix': self.has_fix,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'speed_mph': self.speed_mph,
            'altitude': self.altitude,
            'heading': self.heading,
            'satellites': self.satellites
        }
    
    def get_overlay_data(self) -> Optional[str]:
        """Get GPS data formatted for overlay display"""
        if not self.enabled or not self.has_fix:
            return None
            
        return f"{self.speed_mph:.0f} MPH | {self.latitude:.6f}, {self.longitude:.6f}"
