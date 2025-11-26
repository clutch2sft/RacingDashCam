"""
GPS Handler for Active Dash Mirror
Handles GPS communication and data logging
"""

import time
import logging
import json
import os
import subprocess
from datetime import datetime, timezone
from threading import Thread, Event
from typing import Optional, Dict

try:
    import gps
    import serial
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
        self.last_data_time = time.time()
        
        # Time synchronization
        self.last_time_sync = time.time()
        self.time_sync_count = 0
        self.ntp_service = None  # Will be detected on startup
        
    def start(self):
        """Start GPS handler"""
        if not self.enabled:
            return False
            
        try:
            # Connect to GPSD
            # Note: gpsd should be configured to listen on localhost:2947 (default)
            # and should already be monitoring the configured GPS device
            self.logger.info(f"Connecting to GPSD (device: {self.config.gps_device} @ {self.config.gps_baudrate} baud)...")
            self.session = gps.gps(mode=gps.WATCH_ENABLE | gps.WATCH_NEWSTYLE)
            
            # Open log file
            self.log_file = open(self.log_path, 'w')
            self.log_file.write('[\n')  # Start JSON array
            
            # Start processing thread
            self.running = True
            self.stop_event.clear()
            self.thread = Thread(target=self._process_loop, daemon=True)
            self.thread.start()
            
            # Detect NTP service and initialize time sync
            self._detect_ntp_service()
            if self.config.gps_time_sync_on_startup:
                self._attempt_time_sync("startup")
            
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
                        
                        # Periodic time synchronization
                        if self.config.gps_time_sync_enabled and self.has_fix:
                            elapsed = time.time() - self.last_time_sync
                            if elapsed >= self.config.gps_time_sync_update_interval:
                                self._attempt_time_sync("periodic")
                
                # Check for stale data
                if time.time() - self.last_data_time > 10.0:
                    self.logger.warning("GPS data is stale, attempting recovery...")
                    if not self._recover():
                        break
                        
            except Exception as e:
                self.logger.error(f"GPS processing error: {e}")
                if not self._recover():
                    break
    
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
    
    def _detect_ntp_service(self):
        """Detect which NTP/time service is running"""
        services = ['chrony', 'ntpd', 'systemd-timesyncd']
        
        for service in services:
            try:
                result = subprocess.run(
                    ['systemctl', 'is-active', service],
                    capture_output=True,
                    timeout=2
                )
                if result.returncode == 0:
                    self.ntp_service = service
                    self.logger.info(f"Detected NTP service: {service}")
                    
                    if service == 'systemd-timesyncd':
                        self.logger.info(
                            "systemd-timesyncd detected. GPS time will be set directly via timedatectl. "
                            "For continuous NTP sync, consider upgrading to chrony."
                        )
                    return
            except Exception as e:
                self.logger.debug(f"Could not check {service}: {e}")
        
        self.logger.warning("No NTP service detected.")
        self.ntp_service = None
    
    def _attempt_time_sync(self, reason: str = "periodic") -> bool:
        """Attempt to synchronize system time from GPS
        
        Args:
            reason: Why sync is being attempted (startup, periodic, etc.)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.config.gps_time_sync_enabled or not self.enabled:
            return False
        
        if self.config.gps_time_sync_require_fix and not self.has_fix:
            self.logger.debug(f"GPS time sync ({reason}): No fix available")
            return False
        
        if not self.timestamp:
            self.logger.debug(f"GPS time sync ({reason}): No timestamp available")
            return False
        
        try:
            # Parse GPS timestamp (format: "2025-11-26T14:30:45.123Z" or similar ISO format)
            gps_time = datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
            
            # Get current system time
            system_time = datetime.now(timezone.utc)
            time_diff = abs((gps_time - system_time).total_seconds())
            
            # Only update if difference is significant (more than 1 second)
            if time_diff < 1.0 and reason == "periodic":
                self.logger.debug(f"GPS time sync ({reason}): System time already accurate ({time_diff:.3f}s)")
                return True
            
            self.logger.info(
                f"GPS time sync ({reason}): "
                f"GPS={gps_time.isoformat()}, "
                f"System={system_time.isoformat()}, "
                f"Diff={time_diff:.1f}s"
            )
            
            # Set system time using timedatectl
            # This requires sudo or running as root
            try:
                subprocess.run(
                    ['timedatectl', 'set-time', gps_time.strftime('%Y-%m-%d %H:%M:%S')],
                    check=True,
                    capture_output=True,
                    timeout=5
                )
                self.time_sync_count += 1
                self.last_time_sync = time.time()
                self.logger.info(f"System time updated from GPS (sync #{self.time_sync_count})")
                return True
                
            except subprocess.CalledProcessError as e:
                self.logger.error(f"timedatectl failed: {e.stderr.decode() if e.stderr else e}")
                # Try alternative method with date command
                return self._set_time_with_date(gps_time)
            
        except Exception as e:
            self.logger.error(f"Failed to sync time from GPS: {e}")
            return False
    
    def _set_time_with_date(self, gps_time: datetime) -> bool:
        """Fallback method to set system time using date command
        
        Requires: sudo
        """
        try:
            # Convert to epoch timestamp
            epoch = int(gps_time.timestamp())
            subprocess.run(
                ['date', '+%s', '-s', f'@{epoch}'],
                check=True,
                capture_output=True,
                timeout=5
            )
            self.logger.info("System time updated using date command")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set time with date command: {e}")
            return False
    
    def setup_systemd_timesyncd_info(self) -> Dict:
        """Get information about systemd-timesyncd configuration
        
        With systemd-timesyncd, you cannot directly feed GPS as a time source.
        Instead, use GPS to set system time directly via timedatectl.
        
        Returns:
            Configuration information and upgrade path
        """
        config_info = {
            'service': 'systemd-timesyncd',
            'gps_integration': 'manual',
            'strategy': 'Set system time from GPS via timedatectl, let systemd-timesyncd maintain NTP',
            'automatic_sync_enabled': self.config.gps_time_sync_enabled,
            'sync_interval': self.config.gps_time_sync_update_interval,
            'advantages': [
                'Lightweight (systemd built-in)',
                'GPS provides initial accurate time',
                'systemd-timesyncd maintains NTP sync afterward'
            ],
            'limitations': [
                'systemd-timesyncd will not directly use GPS as reference',
                'Only NTP sources are used after initial time set',
                'For continuous GPS-based sync, upgrade to chrony'
            ]
        }
        
        self.logger.info(f"systemd-timesyncd info: {config_info}")
        return config_info
    
    def upgrade_to_chrony_instructions(self) -> str:
        """Get instructions for upgrading to chrony for better GPS integration"""
        instructions = """
=== UPGRADE TO CHRONY FOR FULL GPS INTEGRATION ===

Current: systemd-timesyncd (can set time, but no continuous GPS sync)
Recommended: chrony (continuous GPS + NTP hybrid)

INSTALLATION:
  sudo apt-get update
  sudo apt-get install chrony

DISABLE systemd-timesyncd:
  sudo systemctl disable systemd-timesyncd
  sudo systemctl mask systemd-timesyncd

START chrony:
  sudo systemctl enable chrony
  sudo systemctl start chrony

VERIFY:
  timedatectl status        # Should show "NTP service: chronyd"
  chronyc tracking          # Check sync status
  chronyc sources           # See all time sources (will include GPS)

After upgrading, the dashcam code will automatically configure GPS
as a Chrony reference clock for continuous high-precision timing.
"""
        return instructions
    
    def setup_chrony_gps_integration(self) -> bool:
        """Configure chrony to use GPS as a reference clock
        
        Requires: chrony installed and sudo access
        
        Returns:
            True if successful
        """
        if self.ntp_service != 'chrony':
            self.logger.warning("Chrony is not the active NTP service")
            return False
        
        try:
            # Check if chrony config already has GPS refclock
            with open('/etc/chrony/chrony.conf', 'r') as f:
                content = f.read()
                if 'refclock SHM 0 refid GPS' in content or 'refclock PPS' in content:
                    self.logger.info("Chrony already configured with GPS")
                    return True
            
            self.logger.info("Adding GPS as Chrony refclock...")
            
            # Backup original config
            subprocess.run(
                ['sudo', 'cp', '/etc/chrony/chrony.conf', '/etc/chrony/chrony.conf.bak'],
                check=True,
                capture_output=True
            )
            
            # Create additional config file for GPS
            gps_config = """
# GPS Time Reference via GPSD
# GPSD shares GPS time via shared memory (SHM)
refclock SHM 0 refid GPS precision 1e-1 poll 4 minsamples 3
"""
            
            if self.config.gps_pps_enabled:
                gps_config += """
# PPS (Pulse Per Second) for high precision timing
refclock PPS /dev/pps0 refid PPS precision 1e-7 lock GPSD
"""
            
            # Write config
            with open('/tmp/gps_chrony.conf', 'w') as f:
                f.write(gps_config)
            
            # Move to chrony directory
            subprocess.run(
                ['sudo', 'mv', '/tmp/gps_chrony.conf', '/etc/chrony/conf.d/gps.conf'],
                check=True,
                capture_output=True
            )
            
            # Restart chrony to load new config
            subprocess.run(
                ['sudo', 'systemctl', 'restart', 'chrony'],
                check=True,
                capture_output=True,
                timeout=10
            )
            
            self.logger.info("Chrony GPS integration configured successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup Chrony GPS integration: {e}")
            return False
    
    def setup_ntpd_gps_integration(self) -> bool:
        """Configure ntpd to use GPS as a reference clock
        
        Requires: ntpd installed and sudo access
        
        Returns:
            True if successful
        """
        if self.ntp_service != 'ntpd':
            self.logger.warning("ntpd is not the active NTP service")
            return False
        
        try:
            # Check if ntpd config already has GPS
            with open('/etc/ntp.conf', 'r') as f:
                content = f.read()
                if '127.127.28.0' in content or 'refid GPS' in content:
                    self.logger.info("ntpd already configured with GPS")
                    return True
            
            self.logger.info("Adding GPS as ntpd reference clock...")
            
            # Backup original config
            subprocess.run(
                ['sudo', 'cp', '/etc/ntp.conf', '/etc/ntp.conf.bak'],
                check=True,
                capture_output=True
            )
            
            # Append GPS config to ntp.conf
            ntp_gps_config = """

# GPS Time Reference (GPSD NMEA)
# Mode 0 with magic fudge factor
server 127.127.28.0 refid GPS
fudge 127.127.28.0 time1 0.0 flag1 0
"""
            
            if self.config.gps_pps_enabled:
                ntp_gps_config += """
# PPS for high precision
server 127.127.22.0 refid PPS
fudge 127.127.22.0 flag1 1
"""
            
            # Write config
            with open('/tmp/ntp_gps.conf', 'w') as f:
                f.write(ntp_gps_config)
            
            # Append to ntp.conf
            subprocess.run(
                ['sudo', 'sh', '-c', 'cat /tmp/ntp_gps.conf >> /etc/ntp.conf'],
                check=True,
                capture_output=True
            )
            
            # Restart ntpd
            subprocess.run(
                ['sudo', 'systemctl', 'restart', 'ntp'],
                check=True,
                capture_output=True,
                timeout=10
            )
            
            self.logger.info("ntpd GPS integration configured successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup ntpd GPS integration: {e}")
            return False
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
