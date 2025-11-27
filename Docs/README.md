# Active Dash Mirror - Raspberry Pi 5 Dual Camera Dashcam

Complete dashcam system with dual CSI cameras, CAN bus vehicle data integration, and GPS tracking.

## Features

### Video Recording
- **Dual Arducam HQ 12.3MP cameras** (IMX477 sensor)
  - Front camera: 1080p@30fps high-quality recording
  - Rear camera: 1080p@30fps + live mirror display
- **Dual H.264 hardware encoding** - Both cameras simultaneously
- **Low-latency display** - 10-15ms glass-to-glass via framebuffer
- **Automatic file management** - Segments, rotation, cleanup
- **Mirror mode** - Horizontal flip for traditional rearview mirror

### Vehicle Integration
- **CAN bus data** - Real-time vehicle telemetry
  - Engine RPM, speed, temperature
  - Fuel level, battery voltage
  - Transmission gear, throttle position
- **Waveshare 2-CH CAN HAT Plus** - Dual MCP2515 controllers
- **Vehicle-specific modules** - 2013 Camaro LFX included
- **Extensible** - Easy to add support for other vehicles

### GPS & Location
- **LC29H dual-band GPS** - L1+L5 for fast, accurate positioning
- **Speed overlay** - Real-time speed display
- **Track logging** - JSON logs for lap reconstruction
- **Speed-based recording** - Optional trigger (e.g., only record when moving)

### Smart Features
- **Automatic storage management** - Deletes oldest files at 75% full
- **Configurable overlays** - Time, date, speed, CAN data
- **Error recovery** - Automatic camera/system recovery
- **Remote monitoring** - SSH access for logs and status

## Hardware Requirements

### Core Components
- **Raspberry Pi 5** (4GB or 8GB)
- **Pimoroni NVMe Base**
- **NVMe M.2 SSD** (256GB-1TB, 2230-2280)
  - Tested: Samsung 980, WD Black SN750, Crucial P3
- **Official Raspberry Pi 27W USB-C Power Supply** (critical!)

### Cameras
- **2x Arducam 12.3MP HQ Camera** (IMX477)
  - Front camera: Standard or narrow angle lens
  - Rear camera: 158° wide angle lens (M12 mount)
- Both connect via CSI ports (CAM0 and CAM1)

### Vehicle Interface
- **Waveshare 2-CH CAN HAT Plus**
- **OBD-II to dual-wire CAN cable** (CAN-H, CAN-L, Ground)

### Display & GPS
- **LILLIPUT 7" 1000 Nits Touch Screen** (or similar HDMI display)
- **LC29H Dual-band GPS Module** for Raspberry Pi

### Optional
- **Active Cooler** for Raspberry Pi 5 (recommended for continuous operation)
- **Case** with ventilation
- **MicroSD card** (8GB, for initial OS installation only)

## Quick Start

### Hardware Setup

CAN HAT SPI Mode Selection

The Waveshare 2-CH CAN HAT Plus supports SPI0 and SPI1.

Because:

GPS PPS requires GPIO18

SPI1 uses GPIO18 as spi1_cs

GPIO18 conflict prevents CAN from loading

You must configure the CAN HAT for SPI0 by setting the solder jumpers:

Pad	Set To
MISO	SPI0 (GPIO 9)
MOSI	SPI0 (GPIO 10)
SCK	SPI0 (GPIO 11)
CE0/CE1	SPI0 CS0/CS1 (GPIO 8/7)

### 1. Install OS to NVMe

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed instructions.

Quick version:
```bash
# Flash Raspberry Pi OS Lite (64-bit) to NVMe
# Enable SSH and configure WiFi in Raspberry Pi Imager
# Boot from NVMe and SSH in
ssh pi@dashcam.local
```

### 2. Run Installation Script

```bash
# Upload install script to Pi
scp dashcam_install.sh pi@dashcam.local:~

# SSH to Pi
ssh pi@dashcam.local

# Run install script
chmod +x dashcam_install.sh
sudo ./dashcam_install.sh

# Reboot when prompted
sudo reboot
```

### 3. Upload Application Files

```bash
# From your computer
scp *.py pi@dashcam.local:/home/pi/dashcam/

# Or use rsync for updates
rsync -av --progress *.py pi@dashcam.local:/home/pi/dashcam/
```

### 4. Start the System

```bash
# Start dashcam service
sudo systemctl start dashcam

# Check status
sudo systemctl status dashcam

# View live logs
journalctl -u dashcam -f
```

You should now see:
- Live rear camera view on display (mirror mode)
- Time and recording indicator overlay
- H.264 files appearing in `/dashcam/videos/current/`

## Quick Reference

### Service Control
```bash
sudo systemctl start dashcam        # Start dashcam
sudo systemctl stop dashcam         # Stop dashcam
sudo systemctl restart dashcam      # Restart dashcam
sudo systemctl status dashcam       # Check status
journalctl -u dashcam -f            # Live logs
```

### Monitoring
```bash
# Check cameras
rpicam-hello --list-cameras         # Should show 2 cameras (imx477)
rpicam-hello --camera 0             # Test front camera
rpicam-hello --camera 1             # Test rear camera

# Check CAN bus
ip link show can0                   # CAN0 status
candump can0                        # Monitor CAN messages

# Check GPS
cgps -s                             # GPS status
gpsmon                              # Detailed GPS info

# Check disk space
df -h /dashcam                      # Disk usage
ls -lht /dashcam/videos/archive/ | head -10   # Recent videos

# Check system
vcgencmd measure_temp               # CPU temperature
htop                                # System resources
```

### Configuration
```bash
# Edit configuration
nano /home/pi/dashcam/config.py

# Apply changes
sudo systemctl restart dashcam
```

### Manual Testing
```bash
# Stop service and run manually
sudo systemctl stop dashcam
cd /home/pi/dashcam
sudo /home/pi/dashcam/venv/bin/python dashcam.py

# Press Ctrl+C to stop
sudo systemctl start dashcam
```

## Configuration

Edit `/home/pi/dashcam/config.py` to customize settings.

### Common Adjustments

**Video Quality:**
```python
# Front camera
self.front_camera_bitrate = 8000000    # 8 Mbps (high quality)
self.front_camera_bitrate = 6000000    # 6 Mbps (balanced)
self.front_camera_bitrate = 4000000    # 4 Mbps (lower storage)

# Rear camera (same options)
self.rear_camera_bitrate = 8000000
```

**Segment Duration:**
```python
self.video_segment_duration = 30   # 30 seconds
self.video_segment_duration = 60   # 60 seconds (default)
self.video_segment_duration = 120  # 2 minutes
```

**Mirror Mode:**
```python
self.display_mirror_mode = True    # Traditional mirror (flipped)
self.display_mirror_mode = False   # Normal view
```

**Enable GPS Speed Display:**
```python
self.gps_enabled = True
self.display_speed = True
self.speed_unit = "mph"  # or "kph"
```

**Enable CAN Bus:**
```python
self.canbus_enabled = True
self.canbus_channel = "can0"
self.canbus_vehicle_type = "camaro_2013_lfx"
self.display_canbus_data = True  # Show RPM, temp, etc. on display
```

**Disk Management:**
```python
self.disk_high_water_mark = 0.75   # Start cleanup at 75% full
self.keep_minimum_gb = 10.0        # Keep 10GB free minimum
```

After changes: `sudo systemctl restart dashcam`

## File Locations

| Item | Location |
|------|----------|
| Application | `/home/pi/dashcam/` |
| Configuration | `/home/pi/dashcam/config.py` |
| Current Videos | `/dashcam/videos/current/` |
| Archived Videos | `/dashcam/videos/archive/` |
| Logs | `/dashcam/logs/` |
| Service File | `/etc/systemd/system/dashcam.service` |
| Virtual Environment | `/home/pi/dashcam/venv/` |

### Video Files

Format: `<camera>_YYYYMMDD_HHMMSS_####.h264`

Examples:
- `front_20241125_143052_0001.h264`
- `rear_20241125_143052_0001.h264`

Files rotate every 60 seconds by default.

## Video Playback

H.264 raw files can be played with:

**VLC Media Player** (easiest):
```bash
vlc /dashcam/videos/archive/front_*.h264
```

**ffplay**:
```bash
ffplay /dashcam/videos/archive/front_20241125_143052_0001.h264
```

**Convert to MP4** (for compatibility):
```bash
ffmpeg -i input.h264 -c:v copy output.mp4
```

## Expected Performance

### Video Quality
- **Resolution**: 1920x1080 (both cameras)
- **Frame rate**: 30fps (both cameras)
- **Bitrate**: 8 Mbps per camera (configurable)
- **Codec**: H.264 (hardware accelerated)

### File Sizes (8 Mbps per camera)
| Time | Single Camera | Dual Cameras |
|------|---------------|--------------|
| 1 min | ~60 MB | ~120 MB |
| 1 hour | ~3.6 GB | ~7.2 GB |
| 1 day | ~86 GB | ~172 GB |

### Storage Examples
| SSD Size | Recording Time (Dual 1080p) |
|----------|----------------------------|
| 256 GB | ~1.5 days |
| 512 GB | ~3 days |
| 1 TB | ~6 days |

With automatic cleanup at 75%, multiply by 0.75 for effective capacity.

### System Performance
- **Boot time**: ~15-20 seconds to recording
- **Display latency**: 10-15ms glass-to-glass
- **CPU usage**: 30-40% (distributed across cores)
- **Power consumption**: ~12-15W (with display)
- **Temperature**: 50-65°C (with adequate cooling)

## Troubleshooting

### Cameras Not Detected
```bash
# Check both cameras detected
rpicam-hello --list-cameras

# Should show:
# 0 : imx477 [4056x3040] (/base/.../i2c@80000/imx477@1a)
# 1 : imx477 [4056x3040] (/base/.../i2c@88000/imx477@1a)

# Test each camera
rpicam-hello --camera 0 -t 5000   # Front camera
rpicam-hello --camera 1 -t 5000   # Rear camera
```

**If cameras not detected:**
1. Check FFC cable connections (both ends)
2. Verify `/boot/firmware/config.txt` has:
   ```
   camera_auto_detect=0
   dtoverlay=imx477,cam0
   dtoverlay=imx477,cam1
   ```
3. Reboot and check again

### CAN Bus Not Working
```bash
# Check CAN interfaces
ip link show can0
ip link show can1

# Should show: state UP

# If DOWN, bring up manually:
sudo ip link set can0 type can bitrate 500000
sudo ip link set can0 up

# Test CAN traffic
candump can0
```

### Service Won't Start
```bash
# Check detailed errors
journalctl -u dashcam -n 50 --no-pager

# Common issues:
# - Camera not detected
# - Framebuffer permission denied
# - Python package missing

# Run manually to see errors
sudo systemctl stop dashcam
sudo /home/pi/dashcam/venv/bin/python /home/pi/dashcam/dashcam.py
```

### Display Issues
```bash
# Check HDMI
tvservice -s

# Check framebuffer
ls -l /dev/fb0

# Ensure user in video group
sudo usermod -a -G video pi
```

### Disk Full
```bash
# Check space
df -h /dashcam

# Manual cleanup (deletes files older than 7 days)
find /dashcam/videos/archive/ -name "*.h264" -mtime +7 -delete

# Or lower cleanup threshold in config.py:
self.disk_high_water_mark = 0.60  # Start at 60% instead of 75%
```

## Documentation

- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - Complete hardware and software setup
- **[CANBUS_GUIDE.md](CANBUS_GUIDE.md)** - CAN bus integration details
- **[GPS_TIME_SYNC_GUIDE.md](GPS_TIME_SYNC_GUIDE.md)** - GPS time synchronization with Chrony
- **[GPS_TIME_SYNC_QUICK.md](GPS_TIME_SYNC_QUICK.md)** - GPS time sync quick reference
- **[GPS_LC29H_SETUP.md](GPS_LC29H_SETUP.md)** - LC29H GPS module setup
- **[GPS_QUICK_REFERENCE.md](GPS_QUICK_REFERENCE.md)** - GPS quick commands

## Project Structure

```
dashcam/
├── config.py              # Configuration (edit this!)
├── dashcam.py             # Main application
├── video_recorder.py      # Camera and recording management
├── video_display.py       # Display handler with overlay
├── canbus.py              # CAN bus base interface
├── camaro_canbus.py       # Vehicle-specific CAN implementation
├── gps_handler.py         # GPS integration
└── venv/                  # Python virtual environment
```

## Development

### Adding a New Vehicle

1. Copy `camaro_canbus.py` to `<your_vehicle>_canbus.py`
2. Update CAN message IDs for your vehicle
3. Update message parsing functions
4. Update `config.py`:
   ```python
   self.canbus_vehicle_type = "your_vehicle_name"
   ```
5. Import in `dashcam.py`

See [CANBUS_GUIDE.md](CANBUS_GUIDE.md) for details.

### Custom Overlays

Edit `video_display.py` to add custom overlay elements:
```python
def _add_overlay(self, frame):
    # Add your custom overlay here
    pass
```

## Support

### Check Logs
```bash
# Application logs
tail -f /dashcam/logs/dashcam_*.log

# System logs
journalctl -u dashcam -f

# System messages
dmesg | tail -50
```

### Common Issues

1. **Camera disconnect** - System automatically recovers
2. **Disk full** - Automatic cleanup at 75%
3. **GPS no fix** - Normal indoors, wait for outdoor clear sky
4. **CAN no data** - Check vehicle ignition is on

### Getting Help

Before asking for help, gather:
```bash
# System info
uname -a
vcgencmd version

# Service status
sudo systemctl status dashcam

# Recent logs
journalctl -u dashcam -n 100 --no-pager

# Camera detection
rpicam-hello --list-cameras

# CAN status
ip link show can0

# Disk space
df -h /dashcam

# Temperature
vcgencmd measure_temp
```

## License

This project is provided as-is for personal use.

## Safety Warning

⚠️ **IMPORTANT - CAN Bus Safety**:
- This system reads CAN data only (no writing)
- Do NOT send CAN messages without understanding them
- Test thoroughly before using in your primary vehicle
- Incorrect CAN messages can damage vehicle systems
- Consult your vehicle service manual

## Credits

Hardware:
- Raspberry Pi 5 by Raspberry Pi Foundation
- Arducam HQ Camera by Arducam
- Waveshare 2-CH CAN HAT by Waveshare
- NVMe Base by Pimoroni

Software:
- Picamera2 for camera interface
- python-can for CAN bus
- GPSD for GPS integration

---

**Ready to build your own Active Dash Mirror!** 🚗📹✨