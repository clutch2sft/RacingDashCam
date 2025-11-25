"""
Example: Integrating CAN Bus into Active Dash Mirror

This shows how to add the Camaro CAN bus interface to your dashcam.py main file.
"""

# In dashcam.py, add these imports at the top:
from camarocanbus import CamaroCANBus, CANChannel

# In the DashcamSystem.__init__() method, add:
class DashcamSystem:
    def __init__(self):
        # ... existing code ...
        self.canbus = None  # Add this line
        
# In the DashcamSystem.start() method, after GPS initialization:
def start(self):
    # ... existing GPS code ...
    
    # Initialize CAN bus (if enabled)
    if self.config.canbus_enabled:
        self.logger.info("Starting CAN bus...")
        try:
            self.canbus = CamaroCANBus(
                self.config, 
                channel=CANChannel.CAN0
            )
            if not self.canbus.start():
                if self.config.canbus_required:  # Add this to config if needed
                    raise RuntimeError("CAN bus is required but failed to start")
                else:
                    self.logger.warning("CAN bus failed to start, continuing without CAN")
                    self.canbus = None
        except Exception as e:
            self.logger.error(f"CAN bus initialization error: {e}")
            self.canbus = None
    else:
        self.logger.info("CAN bus disabled in configuration")
        self.canbus = None
    
    # ... rest of start method ...

# In the DashcamSystem.stop() method, add before GPS stop:
def stop(self):
    # ... existing code ...
    
    if self.canbus:
        self.logger.info("Stopping CAN bus...")
        try:
            self.canbus.stop()
        except Exception as e:
            self.logger.error(f"Error stopping CAN bus: {e}")
    
    # ... rest of stop method ...

# In the DashcamSystem._main_loop() method, add CAN data updates:
def _main_loop(self):
    status_interval = 30.0
    last_status_time = time.time()
    
    try:
        while self.running:
            time.sleep(1.0)
            
            # Update CAN data to display if available
            if self.canbus and self.display and self.config.display_canbus_data:
                try:
                    vehicle_data = self.canbus.get_vehicle_data()
                    
                    # You can pass this to display for overlay
                    # self.display.update_canbus_data(vehicle_data)
                    
                    # Or use speed from CAN instead of GPS
                    if vehicle_data.vehicle_speed is not None:
                        speed_mph = vehicle_data.vehicle_speed * 0.621371
                        self.display.update_gps_data(speed_mph)
                        
                except Exception as e:
                    self.logger.debug(f"Error updating CAN display: {e}")
            
            # ... rest of main loop ...

# In the DashcamSystem._log_configuration() method, add:
def _log_configuration(self):
    # ... existing logging ...
    
    self.logger.info(f"  CAN Bus: {'Enabled' if self.config.canbus_enabled else 'Disabled'}")
    if self.config.canbus_enabled:
        self.logger.info(f"    Channel: {self.config.canbus_channel}")
        self.logger.info(f"    Bitrate: {self.config.canbus_bitrate} bps")
        self.logger.info(f"    Vehicle: {self.config.canbus_vehicle_type}")

# In the DashcamSystem._log_status() method, add:
def _log_status(self):
    # ... existing status logging ...
    
    # CAN bus stats
    if self.canbus:
        try:
            can_stats = self.canbus.get_stats()
            if can_stats['connected']:
                vehicle_data = self.canbus.get_vehicle_data()
                self.logger.info(
                    f"CAN: RPM={vehicle_data.rpm or 0}, "
                    f"Speed={vehicle_data.vehicle_speed or 0:.1f} kph, "
                    f"Temp={vehicle_data.coolant_temp or 0:.1f}°C, "
                    f"Messages RX={can_stats['messages_received']}"
                )
            else:
                self.logger.warning("CAN: Not connected")
        except Exception as e:
            self.logger.debug(f"CAN status error: {e}")


"""
Example: Using CAN data for conditional recording

You can use CAN bus data to control recording. For example, only record when:
- Engine is running (RPM > 0)
- Vehicle is moving (speed > threshold)
- Engine temperature is normal
"""

# Add this method to DashcamSystem class:
def _should_record(self) -> bool:
    """Determine if we should be recording based on conditions"""
    
    # If CAN is enabled, use engine state
    if self.canbus and self.canbus.is_engine_running():
        return True
    
    # Fallback to GPS speed if available
    if self.gps and self.config.speed_recording_enabled:
        gps_status = self.gps.get_status()
        if gps_status['has_fix']:
            return gps_status['speed_mph'] > self.config.start_recording_speed_mph
    
    # Default: always record
    return True

# Then in _main_loop(), use it:
def _main_loop(self):
    while self.running:
        time.sleep(1.0)
        
        # Check if we should be recording
        should_record = self._should_record()
        is_recording = self.recorder.get_stats().get('front_recording', False) or \
                      self.recorder.get_stats().get('rear_recording', False)
        
        if should_record and not is_recording:
            self.logger.info("Starting recording (conditions met)")
            self.recorder.start_recording()
        elif not should_record and is_recording:
            self.logger.info("Stopping recording (conditions not met)")
            self.recorder.stop_recording()


"""
Example: Logging CAN data to CSV file

To create a log of CAN data alongside your videos:
"""

import csv
from datetime import datetime

class CANDataLogger:
    """Log CAN bus data to CSV file"""
    
    def __init__(self, log_dir, canbus):
        self.log_dir = log_dir
        self.canbus = canbus
        self.csv_file = None
        self.csv_writer = None
        
    def start(self):
        """Start logging CAN data"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"canbus_{timestamp}.csv"
        filepath = os.path.join(self.log_dir, filename)
        
        self.csv_file = open(filepath, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        
        # Write header
        self.csv_writer.writerow([
            'timestamp', 'rpm', 'speed_mph', 'coolant_temp_f',
            'throttle_pos', 'fuel_level', 'battery_voltage', 'gear'
        ])
        
    def log(self):
        """Log current CAN data"""
        if not self.csv_writer:
            return
        
        data = self.canbus.get_vehicle_data()
        self.csv_writer.writerow([
            time.time(),
            data.rpm,
            data.vehicle_speed * 0.621371 if data.vehicle_speed else None,
            data.coolant_temp * 9/5 + 32 if data.coolant_temp else None,
            data.throttle_position,
            data.fuel_level,
            data.battery_voltage,
            data.transmission_gear
        ])
        
    def stop(self):
        """Stop logging"""
        if self.csv_file:
            self.csv_file.close()


"""
Example: Debug mode - Monitor all CAN traffic

To see all CAN messages and identify new IDs:
"""

# Add this to your dashcam.py for debugging:
if self.config.canbus_debug_mode:  # Add this config option
    from canbus import CANBusMonitor
    
    self.can_monitor = CANBusMonitor(self.canbus.canbus)
    self.can_monitor.start_monitoring()
    
    # After running for a while:
    self.can_monitor.print_summary()  # Shows all message IDs and counts