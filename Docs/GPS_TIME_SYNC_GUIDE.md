# GPS Time Synchronization Guide

## Overview

The dashcam system integrates GPS for high-precision time synchronization. Since **chrony** is now installed during system setup, the dashcam provides continuous GPS-based time correction with automatic system time updates.

### Key Features

- **Automatic Time Sync**: System time is synchronized from GPS on startup and periodically thereafter
- **Chrony Integration**: GPS acts as a reference clock for NTP, providing microsecond-level accuracy
- **Fallback Support**: If chrony is not available, GPS time is still set manually via `timedatectl`
- **PPS Support**: Hardware PPS (Pulse Per Second) ready for sub-microsecond accuracy (requires wiring)

---

## System Architecture

### Time Sync Flow

```
LC29H GPS Module
    ↓ (UART: /dev/ttyAMA0)
GPSD Daemon (gpsd)
    ↓ (Shared Memory)
Chrony (Reference Clock)
    ↓
System Time (timedatectl)
    ↓
Dashcam Application & Video Timestamps
```

### What You Get

- **On Startup**: GPS time is set to system clock automatically (if fix available)
- **Every 5 minutes**: System time is checked and adjusted if drift exceeds 1 second
- **Video Timestamps**: All recordings use highly accurate system time
- **Video Metadata**: GPS coordinates and speed are embedded in video overlays

---

## Configuration

All GPS time sync settings are in `/home/greggc/RacingDashCam/python/dashcam/core/config.py`:

```python
# GPS-based time synchronization
self.gps_time_sync_enabled = True          # Enable GPS time sync
self.gps_time_sync_on_startup = True       # Set time from GPS on startup
self.gps_time_sync_update_interval = 300.0 # Update every 5 minutes
self.gps_time_sync_require_fix = True      # Only sync if we have valid GPS fix

# PPS (Pulse Per Second) support for precise timing
self.gps_pps_enabled = False               # Enable if PPS pin is wired
self.gps_pps_gpio = 27                     # GPIO pin for PPS signal
self.gps_pps_device = "/dev/pps0"          # PPS device for chrony

# System time source configuration
self.ntp_service = "auto"                  # Auto-detect: chrony, ntpd, or systemd-timesyncd
self.gps_chrony_refclock = True            # Add GPS as refclock to chrony
```

### Key Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `gps_time_sync_enabled` | `True` | Enable/disable GPS time synchronization |
| `gps_time_sync_on_startup` | `True` | Set system time from GPS on startup |
| `gps_time_sync_update_interval` | `300.0` | How often to check GPS time (seconds) |
| `gps_time_sync_require_fix` | `True` | Only sync if GPS has a valid 2D/3D fix |
| `gps_pps_enabled` | `False` | Enable PPS for microsecond accuracy |

---

## Current System Status

Your system is configured with:

- ✅ **Chrony installed** - High-precision NTP daemon
- ✅ **GPSD running** - GPS data daemon on `/dev/ttyAMA0`
- ✅ **GPS time sync enabled** - Automatic startup + periodic sync
- ⚠️ **PPS disabled** - (Optional, requires PPS GPIO wiring)

### Verify Chrony is Running

```bash
# Check service status
timedatectl status

# Expected output:
#   NTP service: chronyd
#   RTC in local TZ: no
#   Time synchronization is on
```

### Check Chrony Time Sources

```bash
# View current time source status
chronyc tracking

# View all time sources (will show GPS when available)
chronyc sources

# Example output:
#   GPS SHM0  (Reference)
#   internet NTP servers
```

---

## GPS Time Sync Operations

### GPS Handler Methods

The `GPSHandler` class provides several methods for time synchronization:

#### 1. Automatic Startup Sync

When the dashcam starts:
```python
# In gps_handler.py start() method:
if self.config.gps_time_sync_on_startup:
    self._attempt_time_sync("startup")
```

This occurs immediately after GPS connection is established, if a valid GPS fix is available.

#### 2. Periodic Sync (Main Loop)

During normal operation, time is synchronized every 5 minutes:
```python
# In gps_handler.py _process_loop() method:
if self.config.gps_time_sync_enabled and self.has_fix:
    elapsed = time.time() - self.last_time_sync
    if elapsed >= self.config.gps_time_sync_update_interval:
        self._attempt_time_sync("periodic")
```

#### 3. Manual Sync (Programmatic)

You can manually trigger time sync:
```python
gps_handler = GPSHandler(config)
gps_handler.start()
success = gps_handler._attempt_time_sync("manual")
```

### How Sync Works

1. **Timestamp Extraction**: GPS timestamp is extracted from GPSD TPV (Time-Position-Velocity) report
2. **Comparison**: GPS time is compared to system time
3. **Update Decision**:
   - If startup sync: Always update (get accurate time immediately)
   - If periodic sync: Only update if drift > 1 second
4. **System Update**: `timedatectl set-time` or `date` command updates system clock
5. **Logging**: Sync event and accuracy are logged

---

## Chrony Integration

### Automatic GPS Refclock Configuration

If you call the setup method (for future upgrades):

```python
gps_handler.setup_chrony_gps_integration()
```

This automatically:
1. Backs up existing `/etc/chrony/chrony.conf`
2. Creates `/etc/chrony/conf.d/gps.conf` with:
   - GPS SHM reference clock (from GPSD)
   - Optional PPS reference (if wired)
3. Restarts chrony to load new configuration

### Chrony Configuration for GPS

The GPS configuration for chrony looks like this:

```
# GPS Time Reference via GPSD
# GPSD shares GPS time via shared memory (SHM)
refclock SHM 0 refid GPS precision 1e-1 poll 4 minsamples 3

# PPS (Pulse Per Second) for high precision timing
refclock PPS /dev/pps0 refid PPS precision 1e-7 lock GPSD
```

- **SHM 0**: Shared memory segment 0 (standard GPSD clock)
- **Precision 1e-1**: ~100ms accuracy from NMEA sentences
- **Precision 1e-7**: ~1 microsecond accuracy from PPS signal

---

## Troubleshooting

### GPS Time Not Syncing

**Check logs:**
```bash
journalctl -u dashcam -f
# Look for "GPS time sync" messages
```

**Common Issues:**

1. **"No fix available"**
   - GPS doesn't have satellite lock yet
   - Check GPS antenna placement
   - Wait 30+ seconds for initial fix
   - Run: `gpspipe -w -n 5`

2. **"timedatectl failed"**
   - System time may be read-only
   - Check if running as root: `whoami`
   - Verify `/etc/adjtime` permissions

3. **"No timestamp available"**
   - GPS fix exists but timestamp missing
   - Check GPS module is working: `gpsctl -f`

### Verify GPS is Working

```bash
# Check GPS device
ls -l /dev/ttyAMA0

# Test GPS data with gpspipe
gpspipe -r -n 10

# Expected: Raw NMEA sentences like:
# $GPRMC,120520.487,A,4717.1298,N,00833.9157,E,0.0,0.0,...

# Check GPSD is running
systemctl status gpsd

# View current GPS status
gpspipe -w -n 5
```

### Check Chrony Status

```bash
# See current synchronization status
chronyc tracking

# Check all sources (should include GPS when available)
chronyc sources

# Monitor in real-time
chronyc tracking -p

# Restart chrony if needed
sudo systemctl restart chrony
```

### Manual Time Set

If automatic sync isn't working:

```bash
# Set time manually from GPS
# First, get current GPS time:
gpspipe -w -n 1 | grep GPRMC

# Extract time from output and set:
sudo timedatectl set-time "2025-11-26 14:30:45"

# Verify
timedatectl status
date
```

---

## Advanced: PPS (Pulse Per Second)

### What is PPS?

PPS is a 1Hz clock pulse from the GPS module with microsecond-level accuracy. It provides far better timing than NMEA sentences alone.

### Hardware Setup

To enable PPS support:

1. **Identify PPS Output Pin** on LC29H module (check datasheet)
2. **Wire to GPIO 27** (configurable in config.py):
   ```
   LC29H PPS Out → GPIO 27 (pin 36 on Pi 5)
   GND → GND
   ```
3. **Set config option**:
   ```python
   self.gps_pps_enabled = True  # In config.py
   self.gps_pps_gpio = 27       # Adjust if needed
   ```

### Software Setup

Once wired, chrony automatically:
1. Detects PPS via `pps-gpio` kernel module
2. Creates `/dev/pps0` device
3. Uses it as a reference clock with 1-microsecond precision

### Load PPS GPIO Module

```bash
# Load the kernel module
sudo modprobe pps-gpio

# Make it permanent (add to /etc/modules)
echo "pps-gpio" | sudo tee -a /etc/modules

# Verify
lsmod | grep pps_gpio
ls -l /dev/pps0
```

### Monitor PPS

```bash
# Check PPS signal is being detected
sudo ppstest /dev/pps0

# Should show:
# trying PPS source "/dev/pps0"
# found 1 source(s)
# source 0 - assert
```

---

## Typical Time Accuracy

| Method | Accuracy | Notes |
|--------|----------|-------|
| GPSD NMEA (SHM) | ±100ms | Good for dashcam video |
| GPSD + Chrony | ±10-50ms | Better NTP integration |
| GPS + PPS | ±1-10μs | Extreme precision |
| Internet NTP | ±10-100ms | Fallback if GPS fails |

---

## Logs and Monitoring

### GPS Time Sync Logs

Logs are written to:
- **Console**: If `log_to_console: true`
- **File**: `/var/opt/dashcam/logs/dashcam_YYYYMMDD.log`
- **Journal**: `journalctl -u dashcam`

### Log Examples

**Startup:**
```
INFO: Detected NTP service: chrony
INFO: GPS time sync (startup): GPS=2025-11-26T14:30:45.123Z, System=2025-11-26T14:30:46.456Z, Diff=1.3s
INFO: System time updated from GPS (sync #1)
```

**Periodic:**
```
DEBUG: GPS time sync (periodic): System time already accurate (0.123s)
```

**With Drift:**
```
INFO: GPS time sync (periodic): GPS=2025-11-26T14:31:45.789Z, System=2025-11-26T14:31:42.100Z, Diff=3.7s
INFO: System time updated from GPS (sync #2)
```

### Monitoring System Time

```bash
# Show current system time and NTP status
timedatectl

# Show exact system time
date '+%Y-%m-%d %H:%M:%S.%N'

# Monitor time drift in real-time
watch -n 1 'timedatectl; echo; date'

# Check dashcam logs for sync events
tail -f /var/opt/dashcam/logs/dashcam_$(date +%Y%m%d).log | grep "GPS time sync"
```

---

## Integration with Video Recording

### Automatic Timestamp Embedding

All dashcam video recordings automatically include:
- **Accurate system time** (synced from GPS)
- **Frame rate**: 15 FPS or higher maintains < 67ms per frame
- **Metadata**: GPS coordinates if available

### Video Metadata Format

Example metadata written to video:
```
Timestamp: 2025-11-26T14:30:45.123Z
GPS Position: 47.285°N, 8.566°E
Speed: 65.2 mph
Heading: 182°
Fix Quality: 2D (or 3D)
Satellites: 12
```

---

## Maintenance

### Regular Checks

```bash
# Daily: Verify GPS and chrony are running
sudo systemctl status gpsd
sudo systemctl status chrony

# Weekly: Check time sync accuracy
chronyc tracking
chronyc sources

# Monthly: Review logs for sync issues
grep "GPS time sync" /var/opt/dashcam/logs/dashcam_*.log
```

### Update Chrony

```bash
# Check for updates
sudo apt update
sudo apt upgrade chrony

# Restart after update
sudo systemctl restart chrony
```

### Reset Time Sync

If something goes wrong:

```bash
# Manual sync from GPS
sudo timedatectl set-time now  # Syncs from NTP

# Or manually from GPS:
# (get time from gpspipe and set it)

# Restart services
sudo systemctl restart gpsd
sudo systemctl restart chrony
sudo systemctl restart dashcam
```

---

## Summary

✅ **What You Have:**
- GPS on `/dev/ttyAMA0` at 115200 baud (LC29H)
- GPSD daemon sharing data via shared memory
- Chrony NTP daemon using GPS as reference
- Automatic startup and periodic time sync
- Video recordings with accurate timestamps

⚠️ **What's Optional:**
- PPS GPIO wiring (for microsecond accuracy)
- Manual chrony configuration
- Custom sync intervals

📝 **Key Files:**
- Config: `/home/greggc/RacingDashCam/python/dashcam/core/config.py`
- Handler: `/home/greggc/RacingDashCam/python/dashcam/core/gps_handler.py`
- Install: `/home/greggc/RacingDashCam/Scripts/install/v1-pi5-arducam/dashcam_install.sh`

---

## Questions or Issues?

Check the logs first:
```bash
journalctl -u dashcam -f
```

Then consult:
- `Docs/GPS_QUICK_REFERENCE.md` - Quick GPS commands
- `Docs/SETUP_GUIDE.md` - Full system setup
- `Docs/CANBUS_GUIDE.md` - CAN integration
