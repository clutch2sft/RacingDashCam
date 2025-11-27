# Auto-Reset Logic Fix - State Transition Detection

## The Problem You Identified

**Your Question**: "What happens when the fuel is at 100% and decreasing?"

You correctly identified a **major flaw** in the original auto-reset logic!

### Original (Broken) Logic:
```
If fuel_level >= 95%:
    Start 5-second timer
    If timer completes → RESET
```

### The Problem:
```
1. You fill tank to 100%
2. Park car overnight
3. Next morning, start car (fuel still 100%)
4. Timer starts...
5. 5 seconds pass → RESET! ❌
6. Start driving with counter at 0.000
7. Never see actual consumption from this tank!
```

The system would reset **every time you start with a full tank**, not just when you **refill** the tank.

## The Fix - State Transition Detection

### New Logic:
```python
# Track two pieces of state:
1. Has fuel level been BELOW 95%? (i.e., have we driven?)
2. Is fuel level currently ABOVE 95%?

# Reset only when:
- Fuel WAS below 95% (we've been driving) ✓
- Then fuel GOES TO above 95% (we just filled up) ✓  
- Stays above 95% for 5 seconds (not a sensor glitch) ✓
```

### How It Works:

```
Scenario 1: Normal Refueling (CORRECT - Should Reset)
-------------------------------------------------------
Time    Fuel Level    _fuel_was_below_threshold    Action
------  ------------  ----------------------------  ------
00:00   100%          False (just started)         No reset (haven't driven yet)
00:30   99%           True (set when <95%)         No reset (below threshold)
01:00   95%           True                         No reset (below threshold)
02:00   60%           True                         No reset (below threshold)
03:00   30%           True                         No reset (driving)
04:00   [REFUEL TO 100%]
04:01   100%          True                         Timer starts!
04:06   100%          True                         RESET! ✓ (5 seconds elapsed)
04:06   100%          False (reset after trigger)  Ready for next cycle

Scenario 2: Start With Full Tank (CORRECT - No Reset)
-----------------------------------------------------
Time    Fuel Level    _fuel_was_below_threshold    Action
------  ------------  ----------------------------  ------
00:00   100%          False (just started)         No reset (haven't driven)
00:05   100%          False                        No reset (no state change)
00:30   99%           True (set when drops)        No reset (below threshold)
01:00   95%           True                         No reset (below threshold)

Scenario 3: Top-Off (5 gallons added at 70%)
--------------------------------------------
Time    Fuel Level    _fuel_was_below_threshold    Action
------  ------------  ----------------------------  ------
00:00   70%           True                         No reset (below threshold)
00:01   [ADD 5 GAL]
00:02   96%           True                         Timer starts!
00:07   96%           True                         RESET! ✓ (5 seconds elapsed)
```

## Code Implementation

### Added State Variable:
```python
self._fuel_was_below_threshold = False  # Track if we've driven
```

### Updated Auto-Reset Logic:
```python
def _check_fuel_auto_reset(self, current_time: float):
    threshold = 95.0  # From config
    
    if fuel_level < threshold:
        # We're driving - mark that we've been below threshold
        self._fuel_was_below_threshold = True
        # Cancel any active timer
        self._fuel_reset_timer_start = None
    
    elif fuel_level >= threshold and self._fuel_was_below_threshold:
        # Key change: AND condition requires we've been below threshold
        if self._fuel_reset_timer_start is None:
            # Start timer - detected potential refueling
            self._fuel_reset_timer_start = current_time
        elif (current_time - self._fuel_reset_timer_start) >= 5.0:
            # Timer completed - confirmed refueling
            self.reset_fuel_consumption()
            # Reset the flag - need another transition for next reset
            self._fuel_was_below_threshold = False
```

## State Diagram

```
     [System Start]
           |
           v
    ┌──────────────┐
    │ _was_below   │
    │   = False    │
    │ (Not Driven) │
    └──────┬───────┘
           │
           │ Fuel < 95%
           v
    ┌──────────────┐
    │ _was_below   │
    │   = True     │<───────────┐
    │  (Driving)   │            │
    └──────┬───────┘            │
           │                    │
           │ Fuel >= 95%        │
           v                    │
    ┌──────────────┐            │
    │ Timer Start  │            │
    │ (5 seconds)  │            │
    └──────┬───────┘            │
           │                    │
           │ Timer Complete     │
           v                    │
    ┌──────────────┐            │
    │   RESET!     │            │
    │ _was_below   │            │
    │   = False    │────────────┘
    └──────────────┘
    
    Reset requires cycle through "Driving" state
```

## Why This Works

### Prevents False Resets:
- Starting with full tank → No reset (never drove)
- Parking with full tank overnight → No reset (flag stays False from previous reset)
- Restarting after short stop with full tank → No reset

### Detects Real Refueling:
- Drove down to 50% → Flag = True
- Fill up to 100% → Detects transition → Reset ✓
- Top off from 80% to 100% → Detects transition → Reset ✓
- Emergency splash (60% → 75%) → No reset (< 95%, but flag ready for next time)

## Edge Cases Handled

### Edge Case 1: What if you never get below 95%?
**Scenario**: You always fill up when gauge shows 95% or above
**Result**: No automatic resets
**Solution**: Use manual reset: `canbus.reset_fuel_consumption()`

### Edge Case 2: What if fuel sensor glitches?
**Scenario**: Fuel level spikes to 100% for 1 second then drops
**Result**: No reset (timer is 5 seconds)
**Why**: The 5-second duration prevents sensor glitches from triggering resets

### Edge Case 3: What if you top off frequently?
**Scenario**: Fill from 90% → 98% → drive → 90% → 98%
**Result**: Resets each time you top off above 95%
**Why**: Each drive below 95% sets the flag, allowing next fill-up to reset

### Edge Case 4: Manual reset with full tank
**Scenario**: You manually reset when tank is 100%
**Result**: Manual reset works, but flag stays False
**Why**: Manual reset doesn't change the flag, preventing auto-reset loop

## Configuration Options

You can tune the behavior:

```python
# In config.py:

# Threshold - higher = less sensitive to top-offs
self.fuel_auto_reset_threshold = 95.0  # or 98.0 for "really full" only

# Duration - longer = more glitch-resistant
self.fuel_auto_reset_duration = 5.0  # or 10.0 to be extra sure

# Disable if you prefer manual reset only
self.fuel_auto_reset_enabled = False
```

## Logging

The system logs all state changes for debugging:

```
# When you drop below threshold:
DEBUG: Fuel level dropped to 92.3% - canceling auto-reset timer

# When you fill up after driving:
INFO: Fuel level at 98.5% after being below 95.0% - starting auto-reset timer (5.0s)

# When reset triggers:
INFO: Auto-reset fuel consumption triggered (was 12.345 L, fuel level 98.5%)
```

## Testing the Fix

### Test 1: Normal Operation
1. Start with full tank (100%)
2. Drive until 50%
3. Fill tank back to 100%
4. Wait 5 seconds
5. **Expected**: Counter resets to 0.000 ✓

### Test 2: Start With Full Tank
1. Fill tank to 100%
2. Turn off car overnight
3. Next day, start car (still 100%)
4. Wait 5 seconds, 10 seconds, 1 minute
5. **Expected**: Counter does NOT reset ✓

### Test 3: Top-Off
1. Drive to 85%
2. Add 3 gallons (now at 98%)
3. Wait 5 seconds
4. **Expected**: Counter resets to 0.000 ✓

### Test 4: Fuel Sensor Glitch
1. Driving at 70%
2. Sensor momentarily shows 100% for 1 second
3. Returns to 70%
4. **Expected**: Counter does NOT reset ✓

## Manual Override

You can always manually reset regardless of fuel level:

```python
# In your code or console:
canbus.reset_fuel_consumption()
```

This bypasses all the state tracking and immediately resets to 0.000.

## Summary

**Original Problem**: Reset every time you started with full tank  
**Root Cause**: No state tracking - couldn't detect "refueling event" vs "already full"  
**Fix**: Track if we've been below threshold, only reset on low→high transition  
**Result**: Only resets when you actually refuel, not when you start with full tank  

The fix makes the auto-reset feature actually useful instead of broken!