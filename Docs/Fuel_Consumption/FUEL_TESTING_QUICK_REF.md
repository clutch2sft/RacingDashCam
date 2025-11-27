# Fuel Consumption - Quick Testing Reference

## Initial Deployment Checklist

### 1. Update Config
```python
# In config.py, set:
self.canbus_enabled = True
self.display_fuel_consumed = True
```

### 2. Verify Files Are In Place
```bash
# Check all three files are updated:
ls -l python/dashcam/core/config.py
ls -l python/dashcam/canbus/vehicles/camaro_2013_lfx.py  
ls -l python/dashcam/platforms/pi5_arducam/video_display_drmkms.py
```

### 3. Link CAN Bus to Display in Main Code
```python
display.set_canbus_vehicle(canbus)
```

## Quick Validation Tests

### Test 1: Is 0x3D1 Being Received?
```bash
# Run this on the Pi while car is running:
candump can0 | grep "3D1"

# Should see messages like:
# can0  3D1  [8]  XX XX XX XX XX XX XX XX
# Arriving ~10 times per second
```

### Test 2: Does Display Show Fuel?
- Start the car
- Look at screen
- Should see (below speed): `Fuel: 0.000 gal`
- Drive for 30 seconds
- Value should increase (if not, see troubleshooting below)

### Test 3: Check Fuel Flow Values
```bash
# In your Python code or logs, look for:
# "Fuel: flow=X.XX L/h"

# Expected ranges:
# Idle:          1.9 - 3.8 L/h   (0.5 - 1.0 gal/h)
# Cruise (60mph): 7.6 - 15.1 L/h  (2.0 - 4.0 gal/h)  
# Acceleration:  38+ L/h          (10+ gal/h)
```

## Troubleshooting Quick Fixes

### Problem: Display shows "Fuel: 0.000 gal" and never changes

**Check 1**: Is CAN bus receiving data?
```bash
candump can0 | grep "3D1"
```
- If NO output → CAN bus hardware issue or wrong bitrate
- If YES output → Continue to Check 2

**Check 2**: Is display linked to CAN bus?
```python
# In your main code, verify you have:
display.set_canbus_vehicle(canbus)
```

**Check 3**: Enable debug logging
```python
# Add to startup code:
import logging
logging.getLogger("CamaroCANBus").setLevel(logging.DEBUG)
```
Look for: `"Fuel: flow=X.XX L/h, delta=X.XXXXXX L, total=X.XXX L"`

### Problem: Fuel consumption way too high or too low

**Quick Fix**: Adjust conversion factor in config.py

```python
# If 10x too high:
self.fuel_flow_conversion_factor = 0.001  # Was 0.01

# If 10x too low:  
self.fuel_flow_conversion_factor = 0.1  # Was 0.01

# If 100x wrong, you may need to look at the raw CAN data
```

### Problem: Auto-reset not triggering when tank is filled

**Quick Fix**: Lower threshold or reduce duration
```python
self.fuel_auto_reset_threshold = 90.0  # Was 95.0
self.fuel_auto_reset_duration = 3.0    # Was 5.0
```

**Check logs for**:
```
"Fuel level at XX.X% - starting auto-reset timer"
"Auto-reset fuel consumption triggered"
```

## Calibration Test Procedure

### Option 1: Full Tank Test (Most Accurate)
1. Fill tank completely
2. Note odometer reading: ___________
3. Reset fuel consumption: `canbus.reset_fuel_consumption()`
4. Drive normally for 50-100 miles
5. Fill tank again, note gallons added: ___________
6. System reported gallons: ___________
7. Calculate factor:
   ```
   correction = actual_gallons / reported_gallons
   new_factor = 0.01 × correction
   ```

### Option 2: Quick Highway Test
1. Reset fuel consumption at start of highway on-ramp
2. Drive steady 60-65 mph for exactly 30 miles
3. Note system reported fuel consumption: ___________
4. Estimate actual consumption:
   ```
   # Camaro LFX V6 highway MPG: ~27 MPG
   expected_fuel = 30 miles / 27 MPG = 1.11 gallons
   ```
5. Compare and adjust factor

## Expected Values Reference

### Fuel Flow Rate (L/h)
| Condition | Range (L/h) | Range (gal/h) |
|-----------|-------------|---------------|
| Idle      | 1.9 - 3.8   | 0.5 - 1.0     |
| 30 mph    | 5.7 - 7.6   | 1.5 - 2.0     |
| 60 mph    | 7.6 - 15.1  | 2.0 - 4.0     |
| Acceleration | 38+      | 10+           |

### Typical Consumption
| Trip Type | Distance | Expected Fuel |
|-----------|----------|---------------|
| City (20 MPG) | 20 miles | 1.0 gal |
| Highway (27 MPG) | 50 miles | 1.85 gal |
| Mixed (23 MPG) | 30 miles | 1.3 gal |

## Config.py Quick Reference

```python
# Essential settings for fuel tracking
self.canbus_enabled = True
self.display_fuel_consumed = True
self.fuel_flow_conversion_factor = 0.01  # ADJUST AFTER TESTING
self.fuel_safety_margin = 1.025  # 2.5% over-reporting
self.fuel_display_unit = "gallons"
self.fuel_display_decimals = 3

# Auto-reset when refueling
self.fuel_auto_reset_enabled = True
self.fuel_auto_reset_threshold = 95.0  # %
self.fuel_auto_reset_duration = 5.0    # seconds
```

## Python Console Quick Tests

```python
# In Python console or test script:

from dashcam.canbus.vehicles.camaro_2013_lfx import CamaroCANBus
from dashcam.core.config import config

canbus = CamaroCANBus(config)
canbus.start()

# Check if data is valid
print(f"Has valid fuel data: {canbus.has_valid_fuel_data()}")

# Get current values
if canbus.has_valid_fuel_data():
    print(f"Fuel consumed: {canbus.get_fuel_consumed_gallons():.3f} gal")
    print(f"Fuel flow rate: {canbus.vehicle_data.fuel_flow_rate:.2f} L/h")
    print(f"Fuel level: {canbus.vehicle_data.fuel_level:.1f}%")

# Manual reset
canbus.reset_fuel_consumption()
print("Fuel consumption reset!")

# Get stats
stats = canbus.get_stats()
print(f"CAN bus stats: {stats}")
```

## Logging Commands

```bash
# Watch fuel consumption updates in real-time
tail -f /opt/dashcam/logs/dashcam.log | grep "Fuel:"

# Check for auto-reset events
tail -f /opt/dashcam/logs/dashcam.log | grep -i "auto-reset"

# Monitor all CAN messages
candump -l can0  # Logs to candump-YYYY-MM-DD_HHMMSS.log
```

## Common Conversion Factor Values

Based on GM HS-CAN, these are typical:

| Factor | Flow at Idle | Flow at 60mph | Likely Accuracy |
|--------|--------------|---------------|-----------------|
| 0.001  | 0.19-0.38 L/h | 0.76-1.51 L/h | Too low (100x off) |
| 0.01   | 1.9-3.8 L/h   | 7.6-15.1 L/h  | Good starting point |
| 0.1    | 19-38 L/h     | 76-151 L/h    | Too high (10x off) |

After initial testing, fine-tune:
```python
# Example calibration adjustments:
self.fuel_flow_conversion_factor = 0.0095  # 5% lower
self.fuel_flow_conversion_factor = 0.0105  # 5% higher
self.fuel_flow_conversion_factor = 0.0115  # 15% higher
```

## Emergency Manual Reset

If auto-reset isn't working and you need to reset manually:

### Via Python:
```python
canbus.reset_fuel_consumption()
```

### Via systemd service restart:
```bash
sudo systemctl restart dashcam
```
(Resets on every power cycle anyway)

## Success Indicators

✅ **System is working if you see**:
- Display shows "Fuel: X.XXX gal" (not 0.000)
- Value increases while driving
- Value increases faster during acceleration
- Auto-reset triggers when you fill tank
- After 30 miles highway driving, shows ~1.1 gallons (±20%)

❌ **System has issues if**:
- Display always shows 0.000
- Value never changes
- Value is 10x or 100x wrong
- Auto-reset never triggers even when tank is full

## Contact Info / Next Steps

After initial testing:
1. Record your calibration factor: ___________
2. Note any issues observed: ___________
3. Test auto-reset with tank fill: Y / N
4. Compare 50-mile trip with actual fuel: Actual _____ vs Reported _____

Update config.py with your calibrated factor and enjoy accurate fuel tracking!
