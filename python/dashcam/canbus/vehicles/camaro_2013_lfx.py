"""
2013 Camaro LFX Engine ECU CAN Bus Interface
Vehicle-specific implementation for GM HS-CAN (High Speed CAN)

CAN Bus Details:
- Bitrate: 500 kbps (standard GM HS-CAN)
- Protocol: ISO 15765-4 (CAN 2.0B)
- 11-bit standard identifiers
"""

import logging
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from canbus import CANBusInterface, CANChannel, CANMessage


@dataclass
class CamaroVehicleData:
    """Container for Camaro vehicle data from CAN bus"""
    # Engine data
    rpm: Optional[int] = None
    coolant_temp: Optional[float] = None  # Celsius
    oil_pressure: Optional[float] = None  # kPa
    throttle_position: Optional[float] = None  # Percent
    manifold_pressure: Optional[float] = None  # kPa
    intake_air_temp: Optional[float] = None  # Celsius
    
    # Speed and transmission
    vehicle_speed: Optional[float] = None  # km/h
    transmission_gear: Optional[int] = None
    
    # Fuel system
    fuel_level: Optional[float] = None  # Percent
    fuel_flow_rate: Optional[float] = None  # L/h
    
    # Fuel consumption tracking
    fuel_consumed_liters: float = 0.0  # Total fuel consumed since reset (liters)
    last_fuel_update_time: Optional[float] = None  # Timestamp of last fuel flow update
    
    # Battery/electrical
    battery_voltage: Optional[float] = None  # Volts
    
    # Diagnostic
    mil_status: bool = False  # Malfunction Indicator Lamp (Check Engine)
    dtc_count: int = 0  # Diagnostic Trouble Code count
    
    # Timestamps
    last_update: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'rpm': self.rpm,
            'coolant_temp_c': self.coolant_temp,
            'coolant_temp_f': self.coolant_temp * 9/5 + 32 if self.coolant_temp else None,
            'oil_pressure_kpa': self.oil_pressure,
            'oil_pressure_psi': self.oil_pressure * 0.145038 if self.oil_pressure else None,
            'throttle_position': self.throttle_position,
            'manifold_pressure': self.manifold_pressure,
            'intake_air_temp_c': self.intake_air_temp,
            'intake_air_temp_f': self.intake_air_temp * 9/5 + 32 if self.intake_air_temp else None,
            'vehicle_speed_kph': self.vehicle_speed,
            'vehicle_speed_mph': self.vehicle_speed * 0.621371 if self.vehicle_speed else None,
            'transmission_gear': self.transmission_gear,
            'fuel_level_percent': self.fuel_level,
            'fuel_flow_rate': self.fuel_flow_rate,
            'fuel_consumed_liters': self.fuel_consumed_liters,
            'fuel_consumed_gallons': self.fuel_consumed_liters / 3.78541 if self.fuel_consumed_liters else 0.0,
            'battery_voltage': self.battery_voltage,
            'mil_status': self.mil_status,
            'dtc_count': self.dtc_count,
            'last_update': self.last_update
        }


class CamaroCANBus:
    """
    2013 Camaro LFX CAN Bus Interface
    
    GM HS-CAN Message IDs (common across GM vehicles):
    - 0x0C9: Engine RPM and Vehicle Speed
    - 0x0F1: Coolant Temperature
    - 0x110: Engine Operating Data
    - 0x1E9: Transmission Data
    - 0x3D1: Fuel System Data
    - 0x4C1: Body Control Module Data
    
    Note: Exact IDs may vary by model year and configuration.
    Use CAN bus monitor to verify actual IDs for your vehicle.
    """
    
    # GM HS-CAN Message IDs (starting point - verify with your vehicle)
    MSG_ENGINE_RPM_SPEED = 0x0C9
    MSG_ENGINE_COOLANT = 0x0F1
    MSG_ENGINE_DATA = 0x110
    MSG_TRANSMISSION = 0x1E9
    MSG_FUEL_SYSTEM = 0x3D1
    MSG_BCM_DATA = 0x4C1
    
    def __init__(self, config, channel: CANChannel = CANChannel.CAN0):
        """
        Initialize Camaro CAN bus interface
        
        Args:
            config: System configuration
            channel: CAN channel to use (default CAN0)
        """
        self.config = config
        self.logger = logging.getLogger("CamaroCANBus")
        
        # CAN bus interface (500 kbps for GM HS-CAN)
        self.canbus = CANBusInterface(config, channel=channel, bitrate=500000)
        
        # Vehicle data
        self.vehicle_data = CamaroVehicleData()
        
        # Fuel auto-reset tracking
        self._fuel_reset_timer_start = None  # Track when fuel level went above threshold
        self._fuel_was_below_threshold = False  # Track if we've been below threshold (driven)
        
        # State
        self.started = False
        
    def start(self) -> bool:
        """Start CAN bus and register message handlers"""
        try:
            self.logger.info("Starting Camaro CAN bus interface...")
            
            # Start CAN bus
            if not self.canbus.start():
                return False
            
            # Register message handlers
            self._register_handlers()
            
            # Set up CAN filters for the messages we care about
            self._setup_filters()
            
            self.started = True
            self.logger.info("Camaro CAN bus interface started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start Camaro CAN interface: {e}")
            return False
    
    def stop(self):
        """Stop CAN bus"""
        self.logger.info("Stopping Camaro CAN bus interface...")
        self.started = False
        self.canbus.stop()
        self.logger.info("Camaro CAN bus interface stopped")
    
    def _register_handlers(self):
        """Register handlers for Camaro-specific CAN messages"""
        self.canbus.register_handler(self.MSG_ENGINE_RPM_SPEED, self._handle_engine_rpm_speed)
        self.canbus.register_handler(self.MSG_ENGINE_COOLANT, self._handle_coolant_temp)
        self.canbus.register_handler(self.MSG_ENGINE_DATA, self._handle_engine_data)
        self.canbus.register_handler(self.MSG_TRANSMISSION, self._handle_transmission)
        self.canbus.register_handler(self.MSG_FUEL_SYSTEM, self._handle_fuel_system)
        self.canbus.register_handler(self.MSG_BCM_DATA, self._handle_bcm_data)
        
        self.logger.info("Registered message handlers for Camaro CAN IDs")
    
    def _setup_filters(self):
        """Set up CAN filters for Camaro messages"""
        # Filter for only the messages we care about
        filters = [
            {"can_id": self.MSG_ENGINE_RPM_SPEED, "can_mask": 0x7FF},
            {"can_id": self.MSG_ENGINE_COOLANT, "can_mask": 0x7FF},
            {"can_id": self.MSG_ENGINE_DATA, "can_mask": 0x7FF},
            {"can_id": self.MSG_TRANSMISSION, "can_mask": 0x7FF},
            {"can_id": self.MSG_FUEL_SYSTEM, "can_mask": 0x7FF},
            {"can_id": self.MSG_BCM_DATA, "can_mask": 0x7FF},
        ]
        
        self.canbus.set_filters(filters)
        self.logger.info("Set up CAN filters for Camaro messages")
    
    def _handle_engine_rpm_speed(self, msg: CANMessage):
        """
        Handle engine RPM and vehicle speed message
        
        Typical format (GM):
        Byte 0-1: Engine RPM (RPM = value / 4)
        Byte 2-3: Vehicle Speed (km/h)
        """
        try:
            if len(msg.data) >= 4:
                # Engine RPM (bytes 0-1, big-endian)
                rpm_raw = (msg.data[0] << 8) | msg.data[1]
                self.vehicle_data.rpm = int(rpm_raw / 4)
                
                # Vehicle speed (bytes 2-3, big-endian)
                speed_raw = (msg.data[2] << 8) | msg.data[3]
                self.vehicle_data.vehicle_speed = speed_raw / 100.0
                
                self.vehicle_data.last_update = time.time()
                
        except Exception as e:
            self.logger.error(f"Error parsing RPM/Speed message: {e}")
    
    def _handle_coolant_temp(self, msg: CANMessage):
        """
        Handle coolant temperature message
        
        Typical format (GM):
        Byte 0: Coolant temp (Celsius = value - 40)
        """
        try:
            if len(msg.data) >= 1:
                self.vehicle_data.coolant_temp = msg.data[0] - 40
                self.vehicle_data.last_update = time.time()
                
        except Exception as e:
            self.logger.error(f"Error parsing coolant temp message: {e}")
    
    def _handle_engine_data(self, msg: CANMessage):
        """
        Handle engine operating data message
        
        Typical format (GM):
        Byte 0: Throttle position (percent)
        Byte 1: Manifold pressure (kPa)
        Byte 2: Intake air temp (Celsius = value - 40)
        """
        try:
            if len(msg.data) >= 3:
                self.vehicle_data.throttle_position = (msg.data[0] / 255.0) * 100.0
                self.vehicle_data.manifold_pressure = msg.data[1]
                self.vehicle_data.intake_air_temp = msg.data[2] - 40
                self.vehicle_data.last_update = time.time()
                
        except Exception as e:
            self.logger.error(f"Error parsing engine data message: {e}")
    
    def _handle_transmission(self, msg: CANMessage):
        """
        Handle transmission data message
        
        Typical format (GM):
        Byte 0: Current gear
        """
        try:
            if len(msg.data) >= 1:
                gear = msg.data[0]
                # Gear 0 = Park/Neutral, 1-6 = gears
                self.vehicle_data.transmission_gear = gear if gear <= 6 else None
                self.vehicle_data.last_update = time.time()
                
        except Exception as e:
            self.logger.error(f"Error parsing transmission message: {e}")
    
    def _handle_fuel_system(self, msg: CANMessage):
        """
        Handle fuel system data message
        
        Typical format (GM):
        Byte 0: Fuel level (percent = value / 2.55)
        Byte 1-2: Fuel flow rate
        """
        try:
            current_time = time.time()
            
            # Parse fuel level
            if len(msg.data) >= 1:
                self.vehicle_data.fuel_level = (msg.data[0] / 255.0) * 100.0
            
            # Parse fuel flow rate and calculate consumption
            if len(msg.data) >= 3:
                # Decode fuel flow rate
                flow_raw = (msg.data[1] << 8) | msg.data[2]
                # Apply conversion factor from config (adjustable for testing)
                conversion_factor = getattr(
                    self.config, 
                    'fuel_flow_conversion_factor', 
                    0.01  # Default fallback
                )
                self.vehicle_data.fuel_flow_rate = flow_raw * conversion_factor  # L/h
                
                # Calculate fuel consumed since last update
                if (self.vehicle_data.last_fuel_update_time is not None and 
                    self.vehicle_data.fuel_flow_rate is not None and
                    self.vehicle_data.fuel_flow_rate > 0):
                    
                    # Time elapsed since last update (in hours)
                    time_delta_hours = (current_time - self.vehicle_data.last_fuel_update_time) / 3600.0
                    
                    # Fuel consumed in this interval (liters)
                    fuel_delta = self.vehicle_data.fuel_flow_rate * time_delta_hours
                    
                    # Add to cumulative total
                    self.vehicle_data.fuel_consumed_liters += fuel_delta
                    
                    self.logger.debug(
                        f"Fuel: flow={self.vehicle_data.fuel_flow_rate:.2f} L/h, "
                        f"delta={fuel_delta:.6f} L, total={self.vehicle_data.fuel_consumed_liters:.3f} L"
                    )
                
                # Update timestamp for next calculation
                self.vehicle_data.last_fuel_update_time = current_time
            
            # Check for auto-reset when fuel tank is filled
            if getattr(self.config, 'fuel_auto_reset_enabled', False):
                self._check_fuel_auto_reset(current_time)
                
            self.vehicle_data.last_update = current_time
                
        except Exception as e:
            self.logger.error(f"Error parsing fuel system message: {e}")
    
    def _handle_bcm_data(self, msg: CANMessage):
        """
        Handle Body Control Module data message
        
        Typical format (GM):
        Byte 0: Various status bits including MIL
        Byte 4-5: Battery voltage (Volts = value / 1000)
        """
        try:
            if len(msg.data) >= 1:
                # Check MIL status (bit 0 of byte 0)
                self.vehicle_data.mil_status = bool(msg.data[0] & 0x01)
            
            if len(msg.data) >= 6:
                voltage_raw = (msg.data[4] << 8) | msg.data[5]
                self.vehicle_data.battery_voltage = voltage_raw / 1000.0
                
            self.vehicle_data.last_update = time.time()
                
        except Exception as e:
            self.logger.error(f"Error parsing BCM data message: {e}")
    
    def _check_fuel_auto_reset(self, current_time: float):
        """
        Check if fuel consumption should be auto-reset based on fuel level
        
        Requires fuel level to transition from below threshold to above threshold,
        then stay above threshold for configured duration. This prevents false
        resets when starting the car with a full tank.
        """
        threshold = getattr(self.config, 'fuel_auto_reset_threshold', 95.0)
        duration = getattr(self.config, 'fuel_auto_reset_duration', 5.0)
        
        if self.vehicle_data.fuel_level is not None:
            # Track if we've ever been below the threshold (i.e., we've driven)
            if self.vehicle_data.fuel_level < threshold:
                self._fuel_was_below_threshold = True
                # Cancel any active timer since we're below threshold
                if self._fuel_reset_timer_start is not None:
                    self.logger.debug(
                        f"Fuel level dropped to {self.vehicle_data.fuel_level:.1f}% - "
                        f"canceling auto-reset timer"
                    )
                    self._fuel_reset_timer_start = None
            
            # Only consider reset if we've previously been below threshold
            # This ensures we detect the TRANSITION from low to high (refueling)
            elif self.vehicle_data.fuel_level >= threshold and self._fuel_was_below_threshold:
                # Fuel level is above threshold AND we've driven before
                if self._fuel_reset_timer_start is None:
                    # Start the timer - detected potential refueling
                    self._fuel_reset_timer_start = current_time
                    self.logger.info(
                        f"Fuel level at {self.vehicle_data.fuel_level:.1f}% after being below "
                        f"{threshold:.1f}% - starting auto-reset timer ({duration:.1f}s)"
                    )
                elif (current_time - self._fuel_reset_timer_start) >= duration:
                    # Timer has elapsed - confirmed refueling, reset fuel consumption
                    old_consumed = self.vehicle_data.fuel_consumed_liters
                    self.reset_fuel_consumption()
                    # Also reset the "was below" flag so we need another transition
                    self._fuel_was_below_threshold = False
                    self.logger.info(
                        f"Auto-reset fuel consumption triggered "
                        f"(was {old_consumed:.3f} L, fuel level {self.vehicle_data.fuel_level:.1f}%)"
                    )
    
    def reset_fuel_consumption(self):
        """Manually reset fuel consumption counter"""
        self.vehicle_data.fuel_consumed_liters = 0.0
        self.vehicle_data.last_fuel_update_time = time.time()
        self._fuel_reset_timer_start = None
        # Don't reset _fuel_was_below_threshold on manual reset
        # This allows manual reset even with full tank
        self.logger.info("Fuel consumption counter reset to 0.0 L")
    
    def get_fuel_consumed_gallons(self, apply_safety_margin: bool = True) -> float:
        """
        Get fuel consumed in gallons
        
        Args:
            apply_safety_margin: If True, apply safety margin from config
            
        Returns:
            Fuel consumed in gallons
        """
        liters = self.vehicle_data.fuel_consumed_liters
        gallons = liters / 3.78541  # Convert L to gallons
        
        if apply_safety_margin:
            safety_margin = getattr(self.config, 'fuel_safety_margin', 1.025)
            gallons *= safety_margin
        
        return gallons
    
    def get_fuel_consumed_liters(self, apply_safety_margin: bool = True) -> float:
        """
        Get fuel consumed in liters
        
        Args:
            apply_safety_margin: If True, apply safety margin from config
            
        Returns:
            Fuel consumed in liters
        """
        liters = self.vehicle_data.fuel_consumed_liters
        
        if apply_safety_margin:
            safety_margin = getattr(self.config, 'fuel_safety_margin', 1.025)
            liters *= safety_margin
        
        return liters
    
    def has_valid_fuel_data(self) -> bool:
        """Check if we have valid fuel consumption data"""
        return (
            self.vehicle_data.last_fuel_update_time is not None and
            self.vehicle_data.fuel_flow_rate is not None
        )
    
    def get_vehicle_data(self) -> CamaroVehicleData:
        """Get current vehicle data"""
        return self.vehicle_data
    
    def get_rpm(self) -> Optional[int]:
        """Get engine RPM"""
        return self.vehicle_data.rpm
    
    def get_speed_mph(self) -> Optional[float]:
        """Get vehicle speed in MPH"""
        if self.vehicle_data.vehicle_speed is not None:
            return self.vehicle_data.vehicle_speed * 0.621371
        return None
    
    def get_coolant_temp_f(self) -> Optional[float]:
        """Get coolant temperature in Fahrenheit"""
        if self.vehicle_data.coolant_temp is not None:
            return self.vehicle_data.coolant_temp * 9/5 + 32
        return None
    
    def is_engine_running(self) -> bool:
        """Check if engine is running (RPM > 0)"""
        return self.vehicle_data.rpm is not None and self.vehicle_data.rpm > 0
    
    def get_stats(self) -> dict:
        """Get CAN bus statistics"""
        stats = self.canbus.get_stats()
        stats['vehicle_data'] = self.vehicle_data.to_dict()
        stats['engine_running'] = self.is_engine_running()
        return stats
    
    def enable_debug_logging(self):
        """Enable debug logging for all CAN messages"""
        from canbus import CANBusMonitor
        
        monitor = CANBusMonitor(self.canbus)
        monitor.start_monitoring()
        
        self.logger.info("CAN bus debug monitoring enabled")
        return monitor


# Helper function to create Camaro CAN bus instance
def create_camaro_canbus(config, channel: CANChannel = CANChannel.CAN0) -> CamaroCANBus:
    """
    Create and return a Camaro CAN bus interface
    
    Args:
        config: System configuration
        channel: CAN channel to use
        
    Returns:
        Configured CamaroCANBus instance
    """
    return CamaroCANBus(config, channel=channel)