# LC29H GPS/RTK HAT - Quick Reference

## ⚡ Critical Setup Steps for Raspberry Pi 5

### 1. Hardware Verification
- [ ] Yellow jumper on LC29H board is at **Position B** (UART mode, not USB)
- [ ] Antenna connected to IPEX socket on LC29H
- [ ] LC29H HAT properly seated on 40-pin GPIO header
- [ ] No interference from other HATs

### 2. Enable UART (one-time setup)

```bash
# Edit boot config
sudo nano /boot/firmware/config.txt

# Add under [pi5] section:
[pi5]
dtoverlay=disable-bt
enable_uart=1

# Reboot
sudo reboot
```

### 3. Install GPS Software

```bash
sudo apt-get update
sudo apt-get install gpsd gpsd-clients python3-gps python3-serial
```

### 4. Configure GPSD

```bash
# Edit GPSD config
sudo nano /etc/default/gpsd

# Set these exact values:
USBAUTO="false"
DEVICES="/dev/ttyAMA0"
GPSD_OPTIONS="-n"
```

### 5. Start GPSD Service

```bash
sudo systemctl daemon-reload
sudo systemctl restart gpsd
sudo systemctl status gpsd  # Should show "active (running)"
```

### 6. Verify Setup

```bash
# Test GPSD connection
cgps

# Or with more detail
gpsmon

# Or run dashcam test
python3 scripts/test_gps.py
```

## 🔧 Configuration in DashCam

File: `python/dashcam/core/config.py`

```python
# GPS Configuration
self.gps_enabled = True                    # Enable GPS
self.gps_device = "/dev/ttyAMA0"           # Raspberry Pi 5 UART
self.gps_baudrate = 115200                 # LC29H default baud rate
self.display_speed = False                 # Set True to show speed overlay
self.speed_recording_enabled = False        # Set True to record only when moving
self.start_recording_speed_mph = 5.0        # Speed threshold for recording
```

## ⏱️ Set 10 Hz Update Rate (LC29H AA/BS)

> Only GGA/RMC output at the faster rate; other NMEA sentences stay at 1 Hz. `gpspipe -w` will still show `cycle: 1.00` for the NMEA driver—trust the TPV timestamps.

```bash
sudo systemctl stop gpsd gpsd.socket dashcam
stty -F /dev/ttyAMA0 115200 raw -echo

# Set fix interval to 100 ms (10 Hz) and verify
( printf '$PAIR050,100*22\r\n'; sleep 0.2; printf '$PAIR051*3E\r\n'; ) | sudo tee /dev/ttyAMA0 >/dev/null
# Expected ACKs: $PAIR001,050,0*3E and $PAIR051,100*23

# Save to NVM so it survives reboot
echo -n '$PQTMSAVEPAR*5A\r\n' | sudo tee /dev/ttyAMA0 >/dev/null

sudo systemctl start gpsd.socket gpsd dashcam

# Verify timing (~0.1 s steps); multiple TPVs per second is normal
gpspipe -w -n 20 | jq -r 'select(.class=="TPV") | .time'
```

## 🚗 Racing Dashboard Features

- **Real-time Speed Display**: Speed overlay on video
- **Speed-based Recording**: Auto-start/stop recording at set threshold
- **GPS Logging**: Save latitude, longitude, altitude, heading to JSON
- **Dash Telemetry**: Integrate with video for post-analysis

## ⚠️ Common Issues & Fixes

| Issue | Solution |
|-------|----------|
| `No such file: /dev/ttyAMA0` | Enable UART in `/boot/firmware/config.txt` and reboot |
| Permission denied on /dev/ttyAMA0 | `sudo usermod -a -G dialout $USER` then logout/login |
| GPSD not responding | `sudo systemctl restart gpsd` |
| No GPS fix (red LED) | Antenna outdoors, clear sky, wait 30-60 sec for cold start |
| Wrong baud rate | Config must use 115200 (not 9600) for LC29H default |
| 9600 baud connection errors | LC29H defaults to 115200, not 9600 |

## 📊 GPS Data Format

JSON log file format (`logs/gps_YYYYMMDD_HHMMSS.json`):

```json
[
  {
    "timestamp": "2025-11-26T10:15:30.123Z",
    "latitude": 34.052235,
    "longitude": -118.243683,
    "speed_mph": 45.2,
    "speed_kph": 72.8,
    "altitude": 285.5,
    "heading": 315.2,
    "fix": true,
    "quality": 3,
    "satellites": 12
  }
]
```

## 📡 Advanced Features (Optional)

### RTK Centimeter-level Positioning
Requires LC29H(DA) or LC29H(BS) variant and NTRIP caster service.
See `Docs/GPS_LC29H_SETUP.md` for detailed RTK setup.

### AGNSS (Cold Start Optimization)
Use QGNSS software to load EPO data for 5-second cold start (vs 26 seconds standard).

## 🔗 Device Specs

- **Module**: Waveshare LC29H GPS/RTK HAT
- **Interface**: UART (default) or USB
- **Baud Rate**: 9600 - 3000000 bps (115200 default)
- **Update Rate**: 1–10 Hz (GGA/RMC can run at 10 Hz), RTK may be limited by firmware
- **Accuracy**: 1m CEP (GPS), 0.01m (RTK)
- **Cold Start**: ~26 seconds
- **Hot Start**: ~1 second
- **GNSS Systems**: GPS, BDS, GLONASS, Galileo, QZSS
- **Bands**: L1+L5 dual-frequency
- **Power**: 5V (Raspberry Pi 5V rail)
- **Current**: <40mA typical

## 🧪 Test Command

Run comprehensive setup test:
```bash
cd ~/RacingDashCam/python
python3 scripts/test_gps.py
```

Expected output: All checks pass ✓
