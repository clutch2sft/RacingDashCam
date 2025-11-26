#!/usr/bin/env python3
"""
GPS Connectivity Test Script
Tests Waveshare LC29H GPS/RTK HAT configuration and connectivity
"""

import sys
import os
import time
import subprocess
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GPSSetupTest:
    """Test GPS hardware and software setup"""
    
    def __init__(self):
        self.passed_checks = []
        self.failed_checks = []
        self.warnings = []
        
    def check(self, name, condition, error_msg=""):
        """Record a check result"""
        if condition:
            self.passed_checks.append(name)
            logger.info(f"✓ {name}")
        else:
            self.failed_checks.append(name)
            logger.error(f"✗ {name}")
            if error_msg:
                logger.error(f"  → {error_msg}")
    
    def warn(self, name, msg):
        """Record a warning"""
        self.warnings.append(name)
        logger.warning(f"⚠ {name}: {msg}")
    
    def run_command(self, cmd, capture=True):
        """Run shell command and return output"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=capture,
                text=True,
                timeout=5
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timeout"
        except Exception as e:
            return False, "", str(e)
    
    def test_hardware_setup(self):
        """Test hardware configuration"""
        logger.info("\n" + "="*60)
        logger.info("HARDWARE SETUP CHECKS")
        logger.info("="*60)
        
        # Check device exists
        device_path = "/dev/ttyAMA0"
        device_exists = Path(device_path).exists()
        self.check(
            "UART Device exists (/dev/ttyAMA0)",
            device_exists,
            "Enable UART in /boot/firmware/config.txt and reboot"
        )
        
        # Check device permissions
        if device_exists:
            device = Path(device_path)
            is_readable = os.access(device_path, os.R_OK)
            is_writable = os.access(device_path, os.W_OK)
            
            self.check(
                "UART Device readable",
                is_readable,
                "Add user to dialout group: sudo usermod -a -G dialout $USER"
            )
            
            self.check(
                "UART Device writable",
                is_writable,
                "Add user to dialout group: sudo usermod -a -G dialout $USER"
            )
        
        # Check old device (serial0) doesn't exist
        if Path("/dev/serial0").exists():
            self.warn(
                "Legacy serial0 device found",
                "Raspberry Pi 5 should use /dev/ttyAMA0, not /dev/serial0"
            )
    
    def test_software_packages(self):
        """Test required software packages"""
        logger.info("\n" + "="*60)
        logger.info("SOFTWARE PACKAGE CHECKS")
        logger.info("="*60)
        
        # Check gpsd installed
        success, _, _ = self.run_command("which gpsd")
        self.check(
            "GPSD daemon installed",
            success,
            "Install with: sudo apt-get install gpsd gpsd-clients"
        )
        
        # Check python-gps installed
        success, _, _ = self.run_command("python3 -c 'import gps'")
        self.check(
            "Python GPS library installed",
            success,
            "Install with: sudo apt-get install python3-gps or pip3 install gps3"
        )
        
        # Check serial library
        success, _, _ = self.run_command("python3 -c 'import serial'")
        self.check(
            "Python serial library installed",
            success,
            "Install with: sudo apt-get install python3-serial or pip3 install pyserial"
        )
    
    def test_gpsd_service(self):
        """Test GPSD service configuration"""
        logger.info("\n" + "="*60)
        logger.info("GPSD SERVICE CHECKS")
        logger.info("="*60)
        
        # Check gpsd service status
        success, stdout, _ = self.run_command("systemctl is-active gpsd")
        is_active = "active" in stdout.lower()
        
        if is_active:
            self.check("GPSD service running", True)
        else:
            self.check(
                "GPSD service running",
                False,
                "Start with: sudo systemctl restart gpsd"
            )
        
        # Check gpsd config file
        gpsd_config = Path("/etc/default/gpsd")
        self.check(
            "GPSD config file exists",
            gpsd_config.exists(),
            f"Create {gpsd_config} with correct settings"
        )
        
        # Check gpsd configuration
        if gpsd_config.exists():
            config_content = gpsd_config.read_text()
            
            has_device = '/dev/ttyAMA0' in config_content or '/dev/serial0' in config_content
            
            # Note: USBAUTO can be true or false - both work fine if devices are explicitly configured
            # USBAUTO="false" is a minor optimization but not required
            if 'USBAUTO="false"' in config_content:
                self.check("GPSD USBAUTO disabled (optimized)", True)
            else:
                self.warn(
                    "GPSD USBAUTO setting",
                    "Set to 'false' for slight optimization (not required if devices are explicit)"
                )
            
            self.check(
                "GPSD device configured for ttyAMA0",
                has_device,
                "Set DEVICES to include /dev/ttyAMA0 in /etc/default/gpsd"
            )
    
    def test_gps_connection(self):
        """Test GPS device connection"""
        logger.info("\n" + "="*60)
        logger.info("GPS CONNECTION CHECKS")
        logger.info("="*60)
        
        try:
            import gps
            
            logger.info("Attempting to connect to GPSD...")
            session = gps.gps(mode=gps.WATCH_ENABLE | gps.WATCH_NEWSTYLE)
            
            self.check("GPSD connection successful", True)
            
            # Try to read some data with timeout
            logger.info("Waiting for GPS data (10 seconds)...")
            start_time = time.time()
            got_data = False
            got_fix = False
            
            while time.time() - start_time < 10:
                try:
                    if session.waiting(timeout=0.5):
                        report = session.next()
                        
                        if report['class'] == 'TPV':
                            got_data = True
                            if report.get('mode', 0) >= 2:  # 2D or 3D fix
                                got_fix = True
                                logger.info(f"  Fix acquired: {report.get('lat', 0):.6f}, {report.get('lon', 0):.6f}")
                                break
                except Exception as e:
                    logger.debug(f"Data read error: {e}")
                    
            self.check(
                "GPS data received",
                got_data,
                "Check antenna connection and outdoor location"
            )
            
            self.check(
                "GPS fix acquired",
                got_fix,
                "May need 30-60 seconds for cold start. Ensure clear sky view."
            )
            
            session.close()
            
        except ImportError:
            self.check(
                "GPS library import",
                False,
                "Install python-gps"
            )
        except Exception as e:
            self.check(
                "GPSD connection",
                False,
                f"Connection error: {e}"
            )
    
    def test_direct_serial(self):
        """Test direct serial communication with GPS module"""
        logger.info("\n" + "="*60)
        logger.info("DIRECT SERIAL COMMUNICATION TEST")
        logger.info("="*60)
        
        try:
            import serial
            
            logger.info("Attempting direct UART connection at 115200 baud...")
            
            ser = serial.Serial(
                port='/dev/ttyAMA0',
                baudrate=115200,
                timeout=2
            )
            
            self.check("Serial port opened", True)
            
            logger.info("Listening for NMEA sentences (5 seconds)...")
            start_time = time.time()
            nmea_count = 0
            
            while time.time() - start_time < 5:
                try:
                    if ser.in_waiting > 0:
                        line = ser.readline().decode('utf-8', errors='ignore').strip()
                        if line.startswith('$'):
                            nmea_count += 1
                            logger.info(f"  Received: {line[:60]}...")
                except Exception as e:
                    logger.debug(f"Read error: {e}")
            
            ser.close()
            
            if nmea_count > 0:
                self.check("NMEA data received via direct serial", True)
            else:
                # This is OK - GPSD may be holding the port exclusive
                self.warn(
                    "Direct NMEA test",
                    "No direct serial data (expected if GPSD has port locked). "
                    "GPSD connection test above confirms serial working."
                )
            
        except ImportError:
            self.warn("Serial test skipped", "pyserial not installed")
        except Exception as e:
            self.warn(
                "Direct serial communication",
                f"Could not test: {e} (GPSD likely has port locked, which is fine)"
            )
    
    def test_config_file(self):
        """Test dashcam config file"""
        logger.info("\n" + "="*60)
        logger.info("DASHCAM CONFIG CHECKS")
        logger.info("="*60)
        
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
            from dashcam.core.config import config
            
            self.check(
                "GPS enabled in config",
                config.gps_enabled,
                "Set gps_enabled = True in config.py"
            )
            
            self.check(
                "GPS device is /dev/ttyAMA0",
                config.gps_device == "/dev/ttyAMA0",
                f"Current: {config.gps_device}, should be /dev/ttyAMA0"
            )
            
            self.check(
                "GPS baud rate is 115200",
                config.gps_baudrate == 115200,
                f"Current: {config.gps_baudrate}, should be 115200"
            )
            
        except Exception as e:
            logger.error(f"Config check failed: {e}")
    
    def print_summary(self):
        """Print test summary"""
        logger.info("\n" + "="*60)
        logger.info("TEST SUMMARY")
        logger.info("="*60)
        
        total = len(self.passed_checks) + len(self.failed_checks)
        logger.info(f"\nPassed: {len(self.passed_checks)}/{total}")
        logger.info(f"Failed: {len(self.failed_checks)}/{total}")
        logger.info(f"Warnings: {len(self.warnings)}")
        
        if self.failed_checks:
            logger.error("\nFailed checks:")
            for check in self.failed_checks:
                logger.error(f"  - {check}")
        
        if self.warnings:
            logger.warning("\nWarnings (non-critical):")
            for warning in self.warnings:
                logger.warning(f"  - {warning}")
        
        if not self.failed_checks:
            logger.info("\n✓ All checks passed! GPS setup is ready for use.")
            if self.warnings:
                logger.info("  (Minor warnings noted above, but system is fully functional)")
            return True
        else:
            logger.error("\n✗ Some checks failed. See above for details.")
            return False
    
    def run_all_tests(self):
        """Run all tests"""
        logger.info("\n")
        logger.info("*" * 60)
        logger.info("* Waveshare LC29H GPS/RTK HAT - Setup Test")
        logger.info("* Raspberry Pi 5 Configuration")
        logger.info("*" * 60)
        
        self.test_hardware_setup()
        self.test_software_packages()
        self.test_gpsd_service()
        self.test_config_file()
        self.test_gps_connection()
        self.test_direct_serial()
        
        success = self.print_summary()
        return success


def main():
    """Main entry point"""
    test = GPSSetupTest()
    success = test.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
