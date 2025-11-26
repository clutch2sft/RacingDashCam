# Waveshare LC29H GPS/RTK HAT Setup Guide

## Hardware Requirements
- Waveshare LC29H GPS/RTK HAT
- L1/L5 dual-frequency antenna (included)
- Raspberry Pi 5 with 40-pin GPIO header
- Dual-frequency GNSS capability (GPS, BDS, GLONASS, Galileo, QZSS)

## Hardware Connection Checklist

### Physical Setup
- [ ] **Yellow Jumper Position**: Must be at **Position B** for UART mode (not USB)
  - Position A = USB mode (`/dev/ttyUSB0`)
  - Position B = UART mode (`/dev/ttyAMA0`)
- [ ] **Antenna Connection**: Connect L1/L5 antenna to IPEX connector
- [ ] **Antenna Orientation**: Place antenna facing sky (label side down)
- [ ] **HAT Installation**: Properly aligned on 40-pin GPIO header

### Pinout Reference
- RXD/TXD: UART communication pins (UART0)
- SDA/SCL: I2C communication pins (if needed)
- PPS: Pulse signal for time synchronization
- WAKEUP: Module wake-up control
- 5V/GND: Power supply (powered by Raspberry Pi 5V rail)

## Software Configuration

### 1. Enable UART on Raspberry Pi 5

Edit `/boot/firmware/config.txt`:
```bash
sudo nano /boot/firmware/config.txt
```

Add or verify these lines:
```ini
[pi5]
dtoverlay=disable-bt
enable_uart=1
```

Save and reboot:
```bash
sudo reboot
```

### 2. Verify UART Device
After reboot, verify the device exists:
```bash
ls -la /dev/ttyAMA0
```

Should show something like:
```
crw-rw---- 1 root dialout 204, 0 Nov 26 10:15 /dev/ttyAMA0
```

### 3. Add User to dialout Group
```bash
sudo usermod -a -G dialout $USER
```

Log out and log back in for this to take effect.

### 4. Install GPS Daemon (gpsd)

Install required packages:
```bash
sudo apt-get update
sudo apt-get install gpsd gpsd-clients python3-gps
```

### 5. Configure GPSD

Edit `/etc/default/gpsd`:
```bash
sudo nano /etc/default/gpsd
```

Set these parameters:
```bash
USBAUTO="false"
DEVICES="/dev/ttyAMA0"
GPSD_OPTIONS="-n"
```

**Important**: The baud rate is handled automatically by gpsd based on module detection.

### 6. Start GPSD Service

```bash
sudo systemctl daemon-reload
sudo systemctl restart gpsd
sudo systemctl status gpsd
```

### 7. Test GPS Connection

Use `gpsmon` to monitor GPS status:
```bash
gpsmon /dev/ttyAMA0
```

Look for:
- Fix status (2D or 3D)
- Number of satellites
- Latitude/Longitude/Altitude
- Speed/Heading

Use `cgps` for a simpler view:
```bash
cgps
```

## DashCam Configuration

The following settings are pre-configured for the LC29H:

```python
# config.py
self.gps_enabled = True
self.gps_device = "/dev/ttyAMA0"      # Raspberry Pi 5 UART
self.gps_baudrate = 115200             # LC29H default
self.speed_recording_enabled = False    # Set True to record only when moving
self.start_recording_speed_mph = 5.0    # Start recording at this speed
self.display_speed = False              # Show speed overlay (set True if desired)
```

## Troubleshooting

### GPS Module Not Found
```bash
dmesg | grep -i serial
dmesg | grep -i ttyAMA
```

Check that `/dev/ttyAMA0` exists and has correct permissions.

### No GPS Fix (blinking red LED)
- Ensure antenna is connected and facing sky
- Move to outdoor location with clear sky view
- Wait 30-60 seconds for cold start (first acquisition)
- Check if signal is blocked by buildings/interference

### gpsd Not Responding
```bash
# Restart gpsd
sudo systemctl restart gpsd

# Check if it's listening
sudo systemctl status gpsd

# Manual test with serial port
stty -F /dev/ttyAMA0 115200
cat /dev/ttyAMA0
```

### Connection Timeout Errors
- Verify baud rate is 115200 (not 9600)
- Check yellow jumper is in Position B
- Try `cgps` or `gpsmon` directly to verify gpsd connectivity
- Check dmesg for UART errors: `dmesg | tail -20`

### Python GPS Library Errors
```python
# Install python3-gps if not already installed
pip3 install gps3

# Or use system package
sudo apt-get install python3-gps
```

## Performance Notes

### LC29H Specifications
- **Dual-band**: L1+L5 GPS signals
- **Multi-GNSS**: GPS, BDS, GLONASS, Galileo, QZSS
- **Baud Rate**: 9600 to 3000000 bps (default: 115200)
- **Update Rate**: Up to 1Hz
- **Sensitivity**: -165 dBm (tracking)
- **Cold Start**: ~26 seconds
- **Hot Start**: ~1 second
- **Current Draw**: <40mA @ 5V

### For Racing Use
- **Speed Accuracy**: ±0.2 m/s (typical)
- **Positional Accuracy**: 1m CEP (GPS) or 0.01m (with RTK)
- **Heading Accuracy**: Better when vehicle speed >2 m/s

## Advanced Features

### RTK Correction (Centimeter-level accuracy)
To enable RTK, you need:
1. LC29H(DA) or LC29H(BS) module variant
2. NTRIP caster service (RTCM correction stream)
3. Configure NTRIP Client to receive corrections

See RTK section in Waveshare wiki for detailed setup.

### AGNSS (Assisted GNSS)
Reduces cold-start time to ~5 seconds:
- Requires QGNSS software on computer
- Download EPO (extended prediction orbit) data
- Load into module's flash memory

## Quick Start Test Script

See `python/scripts/test_gps.py` for a quick GPS connectivity test.

Run:
```bash
cd ~/RacingDashCam/python
python3 scripts/test_gps.py
```

Expected output should show GPS data updates every second with latitude, longitude, speed, etc.
