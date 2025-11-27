# Fuel Consumption Tracking - Implementation Guide

## Overview
This implementation adds real-time fuel consumption tracking to your 2013 Camaro LFX dashcam system using CAN bus data from the 0x3D1 message.

## What Was Changed

### 1. `config.py` - New Configuration Section
Added a complete fuel consumption configuration section with:

```python
# Display fuel consumption on overlay
self.display_fuel_consumed = True  # Show fuel consumed since reset
self.fuel_overlay_position = (20, 140)  # Position below speed (y=140)

# Fuel calculation parameters (adjustable after testing)
self.fuel_flow_conversion_factor = 0.01  # Convert raw value to L/h (VERIFY THIS!)

# Safety margin to account for variance
self.fuel_safety_margin = 1.025  # Add 2.5% to displayed value

# Auto-reset when tank is refilled
self.fuel_auto_reset_enabled = True
self.fuel_auto_reset_threshold = 95.0  # Reset if fuel level >= 95%
self.fuel_auto_reset_duration = 5.0  # Must stay above threshold for 5 seconds

# Display formatting
self.fuel_display_unit = "gallons"  # "gallons" or "liters"
self.fuel_display_decimals = 3  # Show 3 decimal places (0.001 gal precision)
```

### 2. `camaro_2013_lfx.py` - Fuel Tracking Logic
Added comprehensive fuel tracking:

#### New Data Fields in `CamaroVehicleData`:
- `fuel_consumed_liters`: Total fuel consumed since reset (liters)
- `last_fuel_update_time`: Timestamp for calculating consumption between messages

#### Updated `_handle_fuel_system()`:
- **Calculates fuel consumption** every time 0x3D1 is received (~10 times/second)
- Uses the formula: `fuel_consumed = fuel_flow_rate (L/h) × time_delta (hours)`
- Accumulates total consumption in `fuel_consumed_liters`
- **Checks for auto-reset** when fuel level goes above threshold

#### New Methods:
- `reset_fuel_consumption()` - Manually reset the counter
- `get_fuel_consumed_gallons(apply_safety_margin)` - Get consumption in gallons with optional safety margin
- `get_fuel_consumed_liters(apply_safety_margin)` - Get consumption in liters with optional safety margin
- `has_valid_fuel_data()` - Check if we have valid fuel flow data
- `_check_fuel_auto_reset()` - Auto-reset logic when tank is filled

### 3. `video_display_drmkms.py` - Display Integration
Added fuel consumption display to overlay:

#### New Features:
- Displays fuel consumed under the speed display
- Only shows when valid fuel data is available
- Updates when fuel changes by more than 0.001 gallons
- Format: `Fuel: X.XXX gal` (or liters based on config)

#### Integration:
- Added `set_canbus_vehicle()` method to link CAN bus interface
- Overlay cache invalidation includes fuel consumption changes
- Thread-safe access to CAN bus data via lock

## How It Works

### The Math
```
0x3D1 CAN message arrives every 100ms (10 times per second)

Bytes 1-2 contain fuel flow rate (raw value)
fuel_flow_rate (L/h) = raw_value × fuel_flow_conversion_factor

Time between messages: 0.1 seconds = 0.0000277778 hours

Fuel consumed per message = fuel_flow_rate × 0.0000277778

Total fuel consumed = sum of all per-message consumption
```

### Safety Margin
The displayed value includes a 2.5% safety margin (configurable):
```
displayed_fuel = actual_fuel × 1.025
```
This helps prevent running out of gas by slightly overestimating consumption.

### Auto-Reset Logic
When fuel level stays >= 95% for 5+ seconds:
1. Timer starts when fuel level crosses threshold
2. If level drops below threshold, timer cancels
3. If timer completes (5 seconds), fuel consumption resets to 0
4. Assumes you just filled up the tank

## Testing & Calibration

### CRITICAL: Verify the Decoding
The current implementation assumes:
```python
fuel_flow_rate = ((byte1 << 8) | byte2) × 0.01  # L/h
```

**You MUST verify this is correct for your vehicle!**

### Testing Procedure

#### 1. Enable Debug Logging
Add this to your main dashcam code when starting the CAN bus:
```python
from dashcam.canbus.vehicles.camaro_2013_lfx import CamaroCANBus

canbus = CamaroCANBus(config)
canbus.start()

# Enable debug logging to see raw 0x3D1 messages
monitor = canbus.enable_debug_logging()
```

#### 2. Collect Test Data
Drive the car for a known distance and record:
- Starting fuel level (full tank is best)
- Ending fuel level
- Actual fuel consumed (use fuel gauge or refill amount)
- System's reported fuel consumed

#### 3. Calculate Calibration Factor
```python
actual_fuel_consumed = 5.0  # gallons (measured at pump)
system_reported = 4.5  # gallons (from display)

correction_factor = actual_fuel_consumed / system_reported
# Example: 5.0 / 4.5 = 1.111

# Update config.py:
self.fuel_flow_conversion_factor = 0.01 × correction_factor
```

#### 4. Verify Idle vs Cruise Values
Expected ballpark values:
- **Idle**: 0.5-1.0 gal/h (1.9-3.8 L/h)
- **Highway cruise**: 2-4 gal/h (7.6-15.1 L/h)
- **Acceleration**: 10+ gal/h (38+ L/h)

If your values are way off (10x or 100x), the conversion factor needs adjustment.

### Common Issues

**Issue**: Fuel consumption shows 0.000
- **Cause**: 0x3D1 not being received or decoded incorrectly
- **Fix**: Enable debug logging, verify message is arriving
- **Check**: `has_valid_fuel_data()` returns True

**Issue**: Values are 10x or 100x too high/low
- **Cause**: Conversion factor is wrong
- **Fix**: Adjust `fuel_flow_conversion_factor` in config.py
- **Test**: Compare with actual fuel consumption

**Issue**: Auto-reset not working
- **Cause**: Fuel level never reaches threshold, or duration too short
- **Fix**: Lower `fuel_auto_reset_threshold` to 90% or reduce `fuel_auto_reset_duration` to 3 seconds
- **Check**: Watch logs for "starting auto-reset timer" messages

**Issue**: Display doesn't show fuel
- **Cause**: CAN bus not linked to display
- **Fix**: Make sure main code calls `display.set_canbus_vehicle(canbus)`

## Integration with Main Code

In your main dashcam startup code (likely `__main__.py` or similar):

```python
# After creating display and CAN bus:
from dashcam.core.config import config
from dashcam.platforms.pi5_arducam.video_display_drmkms import create_display
from dashcam.canbus.vehicles.camaro_2013_lfx import CamaroCANBus

# Create display
display = create_display(config, card_path=config.display_drm_card)

# Create and start CAN bus
if config.canbus_enabled:
    canbus = CamaroCANBus(config)
    canbus.start()
    
    # Link CAN bus to display for fuel consumption overlay
    display.set_canbus_vehicle(canbus)
    
    print(f"CAN bus started - fuel tracking enabled")
```

## Configuration Options

### Display Control
```python
# Show or hide fuel consumption
config.display_fuel_consumed = True

# Position on screen (x, y from top-left)
config.fuel_overlay_position = (20, 140)  # Below speed

# Units
config.fuel_display_unit = "gallons"  # or "liters"
config.fuel_display_decimals = 3  # 0.001 precision
```

### Calculation Tuning
```python
# Conversion factor (adjust after testing!)
config.fuel_flow_conversion_factor = 0.01

# Safety margin (2.5% = 1.025)
config.fuel_safety_margin = 1.025
```

### Auto-Reset Behavior
```python
# Enable/disable auto-reset
config.fuel_auto_reset_enabled = True

# Fuel level threshold to trigger reset
config.fuel_auto_reset_threshold = 95.0  # 95%

# How long level must stay high
config.fuel_auto_reset_duration = 5.0  # 5 seconds
```

## Manual Reset

You can manually reset fuel consumption programmatically:
```python
canbus.reset_fuel_consumption()
```

Or create a button/command in your UI to trigger this.

## Data Access

Get current fuel consumption data:
```python
# Check if we have valid data
if canbus.has_valid_fuel_data():
    # Get consumption with safety margin
    gallons = canbus.get_fuel_consumed_gallons(apply_safety_margin=True)
    liters = canbus.get_fuel_consumed_liters(apply_safety_margin=True)
    
    # Get without safety margin (actual value)
    actual_gallons = canbus.get_fuel_consumed_gallons(apply_safety_margin=False)
    
    print(f"Fuel consumed: {gallons:.3f} gal ({liters:.3f} L)")
    print(f"Actual: {actual_gallons:.3f} gal")

# Get all vehicle data including fuel
data = canbus.get_vehicle_data()
print(f"Fuel level: {data.fuel_level}%")
print(f"Fuel flow rate: {data.fuel_flow_rate} L/h")
print(f"Total consumed: {data.fuel_consumed_liters} L")
```

## File Placement

Place the updated files in your project:
```
python/dashcam/
├── core/
│   └── config.py              # Updated config
├── platforms/
│   └── pi5_arducam/
│       └── video_display_drmkms.py  # Updated display
└── canbus/
    └── vehicles/
        └── camaro_2013_lfx.py  # Updated CAN interface
```

## Next Steps

1. **Deploy the files** to your Raspberry Pi
2. **Enable CAN bus** in config.py:
   ```python
   self.canbus_enabled = True
   self.display_fuel_consumed = True
   ```
3. **Test with car running** - verify fuel consumption appears on display
4. **Collect calibration data** - drive and compare with actual fuel usage
5. **Adjust conversion factor** in config.py based on test results
6. **Monitor auto-reset** - fill tank and verify it resets properly

## Troubleshooting Commands

```bash
# Check CAN bus is working
candump can0

# Filter for 0x3D1 messages
candump can0 | grep "3D1"

# Monitor fuel consumption in logs
tail -f /opt/dashcam/logs/dashcam.log | grep -i fuel
```

## Summary

- ✅ Fuel consumption tracked from 0x3D1 CAN message (100ms intervals)
- ✅ Displayed on screen under MPH (only when valid data available)
- ✅ 2.5% safety margin applied to displayed value
- ✅ Auto-reset when tank is filled (fuel level >= 95% for 5 seconds)
- ✅ Manual reset option available
- ✅ Configurable units (gallons/liters), precision, and conversion factor
- ⚠️ **Must verify and calibrate conversion factor with real-world testing**

The system is ready to test! Start with the default `fuel_flow_conversion_factor = 0.01` and adjust based on actual results.
