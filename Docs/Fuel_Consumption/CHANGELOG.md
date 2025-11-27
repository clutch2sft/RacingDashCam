# Fuel Consumption Feature - Detailed Changelog

## Overview
Added real-time fuel consumption tracking from CAN bus 0x3D1 message with automatic reset on refueling and safety margin calculations.

---

## File: `config.py`

### Added Configuration Section (after line ~168)
```python
# ==========================================
# Fuel Consumption Configuration  
# ==========================================
```

### New Configuration Variables
| Variable | Default | Purpose |
|----------|---------|---------|
| `display_fuel_consumed` | `True` | Enable/disable fuel display overlay |
| `fuel_overlay_position` | `(20, 140)` | Screen position (x, y) for fuel text |
| `fuel_flow_conversion_factor` | `0.01` | **MUST CALIBRATE** - Converts raw CAN to L/h |
| `fuel_safety_margin` | `1.025` | 2.5% over-reporting to prevent empty tank |
| `fuel_auto_reset_enabled` | `True` | Auto-reset when tank refilled |
| `fuel_auto_reset_threshold` | `95.0` | Fuel level % to trigger reset |
| `fuel_auto_reset_duration` | `5.0` | Seconds above threshold before reset |
| `fuel_display_unit` | `"gallons"` | Display unit ("gallons" or "liters") |
| `fuel_display_decimals` | `3` | Decimal precision (0.001 gal) |

### Configuration Example
```python
self.display_fuel_consumed = True
self.fuel_overlay_position = (20, 140)
self.fuel_flow_conversion_factor = 0.01  # ADJUST AFTER TESTING
self.fuel_safety_margin = 1.025
self.fuel_auto_reset_enabled = True
self.fuel_auto_reset_threshold = 95.0
self.fuel_auto_reset_duration = 5.0
self.fuel_display_unit = "gallons"
self.fuel_display_decimals = 3
```

---

## File: `camaro_2013_lfx.py`

### Modified: `CamaroVehicleData` dataclass

#### Added Fields
```python
fuel_consumed_liters: float = 0.0  # Cumulative fuel consumed (liters)
last_fuel_update_time: Optional[float] = None  # Timestamp for delta calculation
```

#### Modified: `to_dict()` method
Added fuel consumption data to dictionary output:
```python
'fuel_consumed_liters': self.fuel_consumed_liters,
'fuel_consumed_gallons': self.fuel_consumed_liters / 3.78541 if self.fuel_consumed_liters else 0.0,
```

### Modified: `CamaroCANBus.__init__()`

#### Added Instance Variables
```python
self._fuel_reset_timer_start = None  # Track auto-reset timer state
```

### Modified: `_handle_fuel_system()` method

#### Complete Rewrite - New Logic
**Before**:
```python
def _handle_fuel_system(self, msg: CANMessage):
    if len(msg.data) >= 1:
        self.vehicle_data.fuel_level = (msg.data[0] / 255.0) * 100.0
    if len(msg.data) >= 3:
        flow_raw = (msg.data[1] << 8) | msg.data[2]
        self.vehicle_data.fuel_flow_rate = flow_raw / 100.0
    self.vehicle_data.last_update = time.time()
```

**After**:
```python
def _handle_fuel_system(self, msg: CANMessage):
    current_time = time.time()
    
    # Parse fuel level (byte 0)
    if len(msg.data) >= 1:
        self.vehicle_data.fuel_level = (msg.data[0] / 255.0) * 100.0
    
    # Parse fuel flow rate (bytes 1-2) and calculate consumption
    if len(msg.data) >= 3:
        # Decode with configurable conversion factor
        flow_raw = (msg.data[1] << 8) | msg.data[2]
        conversion_factor = getattr(self.config, 'fuel_flow_conversion_factor', 0.01)
        self.vehicle_data.fuel_flow_rate = flow_raw * conversion_factor  # L/h
        
        # Calculate fuel consumed since last update
        if (self.vehicle_data.last_fuel_update_time is not None and 
            self.vehicle_data.fuel_flow_rate > 0):
            
            time_delta_hours = (current_time - self.vehicle_data.last_fuel_update_time) / 3600.0
            fuel_delta = self.vehicle_data.fuel_flow_rate * time_delta_hours
            self.vehicle_data.fuel_consumed_liters += fuel_delta
            
            # Debug logging
            self.logger.debug(
                f"Fuel: flow={self.vehicle_data.fuel_flow_rate:.2f} L/h, "
                f"delta={fuel_delta:.6f} L, total={self.vehicle_data.fuel_consumed_liters:.3f} L"
            )
        
        self.vehicle_data.last_fuel_update_time = current_time
    
    # Check for auto-reset
    if getattr(self.config, 'fuel_auto_reset_enabled', False):
        self._check_fuel_auto_reset(current_time)
    
    self.vehicle_data.last_update = current_time
```

**Key Changes**:
1. Uses configurable `fuel_flow_conversion_factor` instead of hardcoded `/100.0`
2. Calculates time delta between updates (handles variable timing)
3. Accumulates fuel consumption: `total += flow_rate × time_delta`
4. Calls auto-reset check logic
5. Tracks `last_fuel_update_time` for accurate deltas
6. Adds debug logging for troubleshooting

### New Method: `_check_fuel_auto_reset()`
```python
def _check_fuel_auto_reset(self, current_time: float):
    """Auto-reset fuel consumption when tank is filled"""
```

**Logic**:
- Starts timer when fuel level >= threshold
- Cancels timer if level drops
- Resets consumption if timer completes (sustained high level)
- Logs all state changes for debugging

### New Method: `reset_fuel_consumption()`
```python
def reset_fuel_consumption(self):
    """Manually reset fuel consumption counter"""
```

**Actions**:
- Sets `fuel_consumed_liters = 0.0`
- Resets timestamp
- Cancels any active auto-reset timer
- Logs reset event

### New Method: `get_fuel_consumed_gallons()`
```python
def get_fuel_consumed_gallons(self, apply_safety_margin: bool = True) -> float:
    """Get fuel consumed in gallons with optional safety margin"""
```

**Returns**:
- Fuel consumption converted to gallons
- Applies safety margin if requested (default True)
- Used by display to show consumption

### New Method: `get_fuel_consumed_liters()`
```python
def get_fuel_consumed_liters(self, apply_safety_margin: bool = True) -> float:
    """Get fuel consumed in liters with optional safety margin"""
```

**Returns**:
- Fuel consumption in liters
- Applies safety margin if requested

### New Method: `has_valid_fuel_data()`
```python
def has_valid_fuel_data(self) -> bool:
    """Check if we have valid fuel consumption data"""
```

**Returns**:
- `True` if fuel flow data has been received and is valid
- `False` if no data available yet
- Used by display to determine if fuel should be shown

---

## File: `video_display_drmkms.py`

### Modified: `__init__()` method

#### Added Instance Variables (after line ~300)
```python
# CAN bus vehicle data
self.canbus_vehicle = None  # Will be set by set_canbus_vehicle()
self.canbus_lock = Lock()
```

### New Method: `set_canbus_vehicle()`
```python
def set_canbus_vehicle(self, canbus_vehicle):
    """Set CAN bus vehicle interface for accessing vehicle data"""
```

**Purpose**:
- Links CAN bus interface to display
- Enables display to access fuel consumption data
- Thread-safe via lock

**Usage**:
```python
display.set_canbus_vehicle(canbus)
```

### Modified: `_maybe_add_overlay()` method

#### Added Fuel Data Retrieval (after line ~695)
```python
# Get fuel consumption data if available
fuel_consumed = None
with self.canbus_lock:
    if self.canbus_vehicle and hasattr(self.canbus_vehicle, 'has_valid_fuel_data'):
        if self.canbus_vehicle.has_valid_fuel_data():
            fuel_consumed = self.canbus_vehicle.get_fuel_consumed_gallons(apply_safety_margin=True)
```

#### Modified Overlay Cache Invalidation (line ~705)
Added fuel consumption to cache invalidation logic:
```python
needs_update = (
    # ... existing conditions ...
    or (fuel_consumed is not None and 
        (not hasattr(self, '_overlay_last_fuel') or 
         abs((fuel_consumed - (self._overlay_last_fuel or 0))) > 0.001))
)
```

**Logic**:
- Overlay regenerates when fuel changes by > 0.001 gallons
- Prevents unnecessary redraws for tiny changes
- Balances accuracy with performance

#### Added Fuel Tracking to Cache (line ~723)
```python
self._overlay_last_fuel = fuel_consumed
```

### Modified: `_render_overlay_rgba()` method

#### Added Fuel Display Logic (after speed display, line ~793)
```python
# Display fuel consumption if enabled and available
if getattr(self.config, 'display_fuel_consumed', False):
    with self.canbus_lock:
        if self.canbus_vehicle and hasattr(self.canbus_vehicle, 'has_valid_fuel_data'):
            if self.canbus_vehicle.has_valid_fuel_data():
                # Get fuel with safety margin
                fuel_consumed = self.canbus_vehicle.get_fuel_consumed_gallons(apply_safety_margin=True)
                
                # Format based on config
                decimals = getattr(self.config, 'fuel_display_decimals', 3)
                if getattr(self.config, 'fuel_display_unit', 'gallons') == 'gallons':
                    fuel_text = f"Fuel: {fuel_consumed:.{decimals}f} gal"
                else:
                    fuel_liters = self.canbus_vehicle.get_fuel_consumed_liters(apply_safety_margin=True)
                    fuel_text = f"Fuel: {fuel_liters:.{decimals}f} L"
                
                # Draw fuel consumption below speed
                fuel_pos = getattr(self.config, 'fuel_overlay_position', (20, 140))
                self._draw_text_with_bg(draw, fuel_text, fuel_pos, self.config.overlay_font_color, self.font)
```

**Features**:
- Only displays if `display_fuel_consumed = True`
- Only displays if valid fuel data available
- Respects configured unit (gallons/liters)
- Respects configured decimal precision
- Uses same styling as other overlays (font, background, outline)
- Positioned below speed display (configurable)

---

## Integration Requirements

### Main Application Code Changes Required

In your main dashcam startup code (typically `__main__.py` or similar):

```python
# After creating display:
display = create_display(config, card_path=config.display_drm_card)

# After starting CAN bus:
if config.canbus_enabled:
    canbus = CamaroCANBus(config)
    canbus.start()
    
    # NEW: Link CAN bus to display
    display.set_canbus_vehicle(canbus)
```

**This line is REQUIRED for fuel display to work**:
```python
display.set_canbus_vehicle(canbus)
```

---

## Testing & Calibration Notes

### Initial Configuration
```python
# In config.py, enable these:
self.canbus_enabled = True
self.display_fuel_consumed = True
```

### Calibration Parameter
**Most Important**: `fuel_flow_conversion_factor = 0.01`

This MUST be calibrated with real-world testing:
1. Fill tank completely
2. Reset fuel consumption
3. Drive 50-100 miles normally
4. Refill tank and note actual gallons added
5. Compare to system's reported consumption
6. Adjust factor: `new_factor = 0.01 × (actual_gallons / reported_gallons)`

### Expected Values (if factor is correct)
- Idle: 0.5-1.0 gal/h (1.9-3.8 L/h)
- 60 mph cruise: 2.0-4.0 gal/h (7.6-15.1 L/h)
- Acceleration: 10+ gal/h (38+ L/h)

### Debug Logging
Enable debug logging to see calculations:
```python
logging.getLogger("CamaroCANBus").setLevel(logging.DEBUG)
```

Look for messages like:
```
Fuel: flow=2.34 L/h, delta=0.000065 L, total=0.123 L
```

---

## Summary of Changes

### Lines Changed
- **config.py**: +35 lines (new fuel configuration section)
- **camaro_2013_lfx.py**: +150 lines (fuel tracking logic)
- **video_display_drmkms.py**: +45 lines (fuel display integration)

### New Features
1. ✅ Real-time fuel consumption tracking (10 Hz from 0x3D1)
2. ✅ Automatic reset on tank refill (configurable threshold/duration)
3. ✅ Safety margin for conservative estimates (2.5% default)
4. ✅ Display on overlay (gallons or liters, configurable precision)
5. ✅ Thread-safe multi-threaded access
6. ✅ Manual reset capability
7. ✅ Only displays when valid data available
8. ✅ Fully configurable via config.py

### Backward Compatibility
- ✅ All changes are additions (no breaking changes)
- ✅ Feature can be disabled: `display_fuel_consumed = False`
- ✅ Works without CAN bus (simply doesn't display fuel)
- ✅ No changes to existing functionality

---

## Version Information
- **Created**: 2024-11-27
- **Target Vehicle**: 2013 Camaro LFX (GM HS-CAN)
- **CAN Message**: 0x3D1 (Fuel System Data)
- **Update Rate**: 100ms (10 Hz)
- **Display Update**: Triggered on change > 0.001 gallons

---

## Known Limitations

1. **Calibration Required**: `fuel_flow_conversion_factor` must be validated
2. **Resets on Power Loss**: Fuel consumption resets when system powers off (intentional)
3. **Vehicle-Specific**: Decoding may vary for other GM vehicles
4. **No Persistence**: Does not save fuel consumption between sessions
5. **Auto-Reset May Miss Fill-ups**: If you fill tank but level doesn't reach threshold

---

## Future Enhancements (Not Implemented)

- Fuel economy calculation (MPG) using GPS speed
- Trip computer (multiple trip counters)
- Fuel consumption history/logging
- Persistent storage between sessions
- Predictive range calculation
- Fuel cost tracking

---

## Files Delivered

1. ✅ `config.py` - Updated configuration
2. ✅ `camaro_2013_lfx.py` - Updated CAN interface
3. ✅ `video_display_drmkms.py` - Updated display
4. ✅ `FUEL_CONSUMPTION_GUIDE.md` - Complete guide
5. ✅ `FUEL_TESTING_QUICK_REF.md` - Quick testing reference
6. ✅ `FUEL_IMPLEMENTATION_SUMMARY.md` - High-level summary
7. ✅ `CHANGELOG.md` - This detailed changelog

---

## UPDATE: Auto-Reset Logic Fix (v1.1)

### Problem Identified
Original auto-reset logic would reset fuel consumption every time the car was started with a full tank, not just when refueling.

### Fix Applied
Added state transition detection to require fuel level to go from below threshold (driving) to above threshold (refueling) before triggering reset.

### Changes in `camaro_2013_lfx.py`

#### Added State Tracking Variable
```python
self._fuel_was_below_threshold = False  # Track if we've driven
```

#### Modified `_check_fuel_auto_reset()` Logic
- Now requires `fuel_level < threshold` at some point before reset can trigger
- Detects the transition from "not full" → "full" (refueling event)
- Resets the flag after successful auto-reset to require another cycle

#### Updated `reset_fuel_consumption()` 
- Does NOT reset `_fuel_was_below_threshold` on manual reset
- Allows manual reset even when tank is full
- Preserves auto-reset capability for next cycle

### New Behavior

**Scenario 1: Start with full tank** → NO auto-reset ✓  
**Scenario 2: Drive then refuel** → Auto-reset after 5 seconds ✓  
**Scenario 3: Top-off from 80% to 100%** → Auto-reset after 5 seconds ✓  
**Scenario 4: Fuel sensor glitch** → NO auto-reset (5 sec duration) ✓  

### Files Updated
- `camaro_2013_lfx.py` - Fixed auto-reset logic
- `AUTO_RESET_FIX.md` - Detailed explanation of the fix