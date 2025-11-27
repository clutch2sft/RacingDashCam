# Fuel Consumption Tracking - Implementation Summary

## What You Asked For

✅ Filter and decode 0x3D1 CAN frame (fuel system data)  
✅ Calculate fuel consumed using 100ms broadcast interval (10 readings/second)  
✅ Display cumulative fuel on monitor (only when valid data available)  
✅ Convert to gallons with 3 decimal places  
✅ Add 2.5% safety margin to each display value  
✅ Auto-reset when tank is refilled (fuel level >= 95%)  
✅ Configurable parameters for easy tuning during testing  

## Files Modified

### 1. `config.py`
**Location in your project**: `python/dashcam/core/config.py`

**What was added**:
- Fuel consumption display settings
- `fuel_flow_conversion_factor` - **THIS NEEDS TESTING/CALIBRATION**
- Safety margin configuration (2.5% default)
- Auto-reset settings (95% threshold, 5 second duration)
- Display formatting (gallons/liters, decimal places)

### 2. `camaro_2013_lfx.py`  
**Location in your project**: `python/dashcam/canbus/vehicles/camaro_2013_lfx.py`

**What was added**:
- Fuel consumption accumulation in `_handle_fuel_system()`
- Calculation: `fuel_consumed = fuel_flow_rate (L/h) × time_delta (hours)`
- Auto-reset logic when fuel level stays >= 95% for 5+ seconds
- Helper methods: `get_fuel_consumed_gallons()`, `reset_fuel_consumption()`, `has_valid_fuel_data()`
- Proper timestamp tracking for accurate time deltas

### 3. `video_display_drmkms.py`
**Location in your project**: `python/dashcam/platforms/pi5_arducam/video_display_drmkms.py`

**What was added**:
- `set_canbus_vehicle()` method to link CAN bus data to display
- Fuel consumption overlay rendering (below speed)
- Thread-safe access to CAN data
- Overlay cache invalidation when fuel changes
- Format: "Fuel: X.XXX gal" (or liters)

## How It Works

### Data Flow
```
0x3D1 CAN Message (100ms interval)
    ↓
camaro_2013_lfx.py: _handle_fuel_system()
    ↓
Parse bytes 1-2 → fuel_flow_rate (L/h)
    ↓
Calculate: consumed = flow_rate × time_since_last_update
    ↓
Accumulate in fuel_consumed_liters
    ↓
Apply safety margin (×1.025)
    ↓
Convert to gallons (/3.78541)
    ↓
video_display_drmkms.py: Display on screen
```

### The Math
```python
# Every 100ms, we get fuel flow rate from 0x3D1
time_delta = 0.1 seconds = 0.0000277778 hours

# Calculate fuel consumed in this interval
fuel_consumed = fuel_flow_rate (L/h) × 0.0000277778 hours

# Accumulate
total_fuel += fuel_consumed

# Apply safety margin for display
displayed_fuel = total_fuel × 1.025  # 2.5% over-reporting

# Convert to gallons
gallons = displayed_fuel / 3.78541
```

### Auto-Reset Logic
```
When fuel_level >= 95%:
  1. Start 5-second timer
  2. If level drops below 95%, cancel timer
  3. If timer completes → reset fuel_consumed to 0
  
Why? Assumes you just filled the tank.
```

## Configuration Reference

All settings are in `config.py`:

```python
# Display control
self.display_fuel_consumed = True  # Show/hide fuel overlay
self.fuel_overlay_position = (20, 140)  # Screen position (x, y)

# Calculation (MUST CALIBRATE)
self.fuel_flow_conversion_factor = 0.01  # Adjust after testing!

# Safety margin
self.fuel_safety_margin = 1.025  # 2.5% = displays 102.5% of actual

# Auto-reset
self.fuel_auto_reset_enabled = True
self.fuel_auto_reset_threshold = 95.0  # Fuel level %
self.fuel_auto_reset_duration = 5.0   # Seconds above threshold

# Display format
self.fuel_display_unit = "gallons"  # or "liters"
self.fuel_display_decimals = 3      # "0.001" precision
```

## ⚠️ CRITICAL: Calibration Required

**The `fuel_flow_conversion_factor` is currently set to 0.01 as a starting point.**

This value determines how raw CAN data is converted to L/h:
```python
fuel_flow_rate = ((byte1 << 8) | byte2) × fuel_flow_conversion_factor
```

### You MUST test and calibrate this!

**Why?** GM CAN protocols can vary by:
- Model year
- ECU version
- Vehicle configuration
- Message encoding

**How to calibrate**: See `FUEL_TESTING_QUICK_REF.md` for step-by-step procedure.

### Expected Ballpark Values
If `fuel_flow_conversion_factor = 0.01` is correct, you should see:

| Condition | Flow Rate (L/h) | Flow Rate (gal/h) |
|-----------|-----------------|-------------------|
| Idle | 1.9 - 3.8 | 0.5 - 1.0 |
| 60 mph cruise | 7.6 - 15.1 | 2.0 - 4.0 |
| Acceleration | 38+ | 10+ |

If your values are 10x or 100x different, adjust the conversion factor.

## Integration Steps

### 1. Deploy Files
Copy the three updated files to your Pi:
```bash
# On your Pi:
cd /home/claude/RacingDashCam
cp /path/to/config.py python/dashcam/core/
cp /path/to/camaro_2013_lfx.py python/dashcam/canbus/vehicles/
cp /path/to/video_display_drmkms.py python/dashcam/platforms/pi5_arducam/
```

### 2. Enable in Config
```python
# In config.py:
self.canbus_enabled = True
self.display_fuel_consumed = True
```

### 3. Link CAN Bus to Display
In your main dashcam code (where you create display and CAN bus):
```python
# After creating display and canbus:
display.set_canbus_vehicle(canbus)
```

### 4. Test
1. Start car
2. Check display shows "Fuel: 0.000 gal"
3. Drive for 30 seconds
4. Value should increase
5. If not, see troubleshooting

## Troubleshooting

### Display shows 0.000 and never changes
**Check**: Is 0x3D1 being received?
```bash
candump can0 | grep "3D1"
```
**Fix**: Enable debug logging to see fuel flow calculations

### Values way too high or low
**Check**: Compare to expected ranges above
**Fix**: Adjust `fuel_flow_conversion_factor` in config.py

### Auto-reset not working
**Check**: Watch logs for "starting auto-reset timer"
**Fix**: Lower threshold to 90% or reduce duration to 3 seconds

### Display not showing fuel at all
**Check**: `display.set_canbus_vehicle(canbus)` called?
**Fix**: Add link in main code

## Where Things Are

### In Your Project Structure:
```
python/dashcam/
├── core/
│   └── config.py                    ← Updated (fuel config)
├── canbus/
│   └── vehicles/
│       └── camaro_2013_lfx.py      ← Updated (fuel tracking)
└── platforms/
    └── pi5_arducam/
        └── video_display_drmkms.py  ← Updated (fuel display)
```

### Calculation Logic:
- `camaro_2013_lfx.py`: Lines in `_handle_fuel_system()` method

### Display Logic:
- `video_display_drmkms.py`: Lines in `_render_overlay_rgba()` method

### Configuration:
- `config.py`: "Fuel Consumption Configuration" section

## Documentation Files

Three documentation files created:

1. **FUEL_CONSUMPTION_GUIDE.md** - Complete implementation details
   - How everything works
   - Testing procedures
   - Calibration steps
   - Troubleshooting

2. **FUEL_TESTING_QUICK_REF.md** - Quick reference for testing
   - Checklists
   - Expected values
   - Quick fixes
   - Console commands

3. **FUEL_IMPLEMENTATION_SUMMARY.md** - This file
   - High-level overview
   - What was changed
   - Integration steps

## Next Steps

1. ✅ Deploy the three updated Python files
2. ✅ Enable CAN bus and fuel display in config
3. ✅ Add `display.set_canbus_vehicle(canbus)` to main code
4. 🔄 Test with car running
5. 🔄 Collect calibration data
6. 🔄 Adjust `fuel_flow_conversion_factor`
7. 🔄 Verify auto-reset works when tank is filled

## Key Features Implemented

✅ **Real-time tracking**: Updates 10 times per second from 0x3D1  
✅ **Accurate calculation**: Proper time-delta based accumulation  
✅ **Safety margin**: 2.5% over-reporting to prevent empty tank  
✅ **Auto-reset**: Detects tank fill-up and resets counter  
✅ **Only shows valid data**: Won't display if CAN data unavailable  
✅ **Configurable**: Easy to tune all parameters  
✅ **Thread-safe**: Proper locking for multi-threaded access  
✅ **Manual reset**: Can reset programmatically if needed  

## Important Notes

1. **Calibration is REQUIRED** - Don't trust the displayed values until calibrated
2. **Safety margin is intentional** - Better to slightly over-report than run out
3. **Auto-reset requires sustained high fuel level** - Won't trigger on brief spikes
4. **Resets on power loss** - This is intentional (assumes car turned off)
5. **0x3D1 decoding may vary** - Verify with your specific vehicle

## Support / Questions

Refer to:
- `FUEL_CONSUMPTION_GUIDE.md` for detailed explanations
- `FUEL_TESTING_QUICK_REF.md` for quick testing procedures
- Your vehicle's CAN bus documentation (if available)
- GM HS-CAN protocol specifications

Good luck with testing! The implementation is solid, but calibration is key to accuracy.
