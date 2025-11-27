# Active Dash Mirror - Complete Setup Guide

Complete step-by-step guide to building your Active Dash Mirror system with dual cameras, CAN bus integration, and GPS.

---

## Table of Contents

1. [Hardware Overview](#chapter-1-hardware-overview)
2. [OS Installation to NVMe](#chapter-2-os-installation-to-nvme)
3. [Hardware Assembly](#chapter-3-hardware-assembly)
4. [Software Installation](#chapter-4-software-installation)
5. [Camera Setup](#chapter-5-camera-setup)
6. [CAN Bus Setup](#chapter-6-can-bus-setup)
7. [GPS Setup](#chapter-7-gps-setup)
8. [Final Configuration](#chapter-8-final-configuration)
9. [Testing & Verification](#chapter-9-testing--verification)
10. [Troubleshooting](#chapter-10-troubleshooting)

---

## Chapter 1: Hardware Overview

### What You Need

#### Core Components
- **Raspberry Pi 5** (4GB or 8GB RAM)
- **Pimoroni NVMe Base**
- **NVMe M.2 SSD** (256GB-1TB recommended)
  - 2230, 2242, 2260, or 2280 form factor
  - Tested: Samsung 980, WD Black SN750, Crucial P3
- **Official Raspberry Pi 27W USB-C Power Supply** (⚠️ critical!)
- **MicroSD card** (8GB minimum, temporary for setup only)

#### Cameras
- **2x Arducam 12.3MP HQ Camera** with IMX477 sensor
  - Part number: B0385 (without lens) or similar
- **Front camera lens**: Standard or narrow angle
- **Rear camera lens**: 158° wide angle M12 mount
  - Arducam part: LN055 or similar fisheye lens
- **2x Camera FFC cables** (usually included with cameras)

#### CAN Bus Hardware
- **Waveshare 2-CH CAN HAT Plus**
  - Dual MCP2515 CAN controllers
  - SN65HVD230 CAN transceivers
- **OBD-II to CAN cable**
  - DB9 or bare wire to OBD-II
  - Needs: CAN-H (pin 6), CAN-L (pin 14), Ground (pin 4 or 5)

#### Display & GPS
- **HDMI Display** - LILLIPUT 7" 1000 Nits or similar
- **LC29H Dual-band GPS Module** for Raspberry Pi
  - Or compatible UART GPS module

#### Optional but Recommended
- **Active Cooler** for Raspberry Pi 5
- **Case** with ventilation
- **USB NVMe adapter** (for Method 1 OS install, ~$10-15)

### Cost Estimate

| Item | Approximate Cost |
|------|-----------------|
| Raspberry Pi 5 (8GB) | $80 |
| Pimoroni NVMe Base | $12-15 |
| NVMe SSD (512GB) | $40-60 |
| 2x Arducam HQ Camera | $100-140 |
| Wide angle lens | $30-40 |
| Waveshare CAN HAT | $25-30 |
| OBD-II cable | $10-20 |
| LILLIPUT Display | $200-300 |
| LC29H GPS | $50-80 |
| Power supply | $12 |
| Active Cooler | $5 |
| **Total** | **$565-785** |

---

## Chapter 2: OS Installation to NVMe

**⚠️ IMPORTANT: Complete this chapter BEFORE running dashcam_install.sh**

This guide covers headless setup (no monitor, keyboard, or mouse needed).

### Method 1: Direct Flash to NVMe (Recommended)

Easiest method using a USB NVMe adapter.

#### Requirements
- USB M.2 NVMe adapter/enclosure (~$10-15)
- Computer with SD card reader
- Ethernet cable (recommended) OR WiFi configured

#### Steps

**1. Remove NVMe from Pimoroni Base**
- Don't install hardware yet
- We'll flash the drive first, then install it

**2. Connect NVMe to Computer**
- Insert NVMe into USB adapter
- Connect to your computer
- Should appear as an external drive

**3. Flash OS with Raspberry Pi Imager**

Download: https://www.raspberrypi.com/software/

**Imager Settings:**
- **Device**: Raspberry Pi 5
- **OS**: Raspberry Pi OS Lite (64-bit)
  - Under "Raspberry Pi OS (other)"
  - Select "Raspberry Pi OS Lite (64-bit)"
- **Storage**: Your NVMe drive (⚠️ be careful to select correct drive!)

**Click the Gear Icon (⚙️) or "Edit Settings":**

**⚠️ CRITICAL for headless setup - Configure ALL of these:**

- ✅ Set hostname: `dashcam` (or your choice)
- ✅ Set username: `pi` (or your choice - remember this!)
- ✅ Set password: (choose a strong password - remember this!)
- ✅ **Enable SSH** ← REQUIRED for headless!
  - Select: "Use password authentication"
- ✅ Configure WiFi ← HIGHLY RECOMMENDED
  - SSID: Your network name
  - Password: Your WiFi password
  - Country: US (or your location)
  - **Note**: Ethernet is more reliable for first boot
- ✅ Set locale settings
  - Timezone: Your timezone
  - Keyboard layout: us (or your layout)

**Double-check SSH is enabled before proceeding!**

**Click "SAVE" then "YES" to apply customization**

**Click "WRITE"** and wait for completion (~5-10 minutes)

**4. Install NVMe in Pimoroni Base**
- Remove NVMe from USB adapter
- Insert in NVMe Base at an angle
- Press down flat
- Secure with provided screw

**5. Connect PCIe FFC Cable**

**⚠️ CRITICAL - Cable Connection Order and Orientation:**

**Connect Base side FIRST:**
- Locate brown connector on NVMe Base
- Lift the brown tab up gently
- Insert cable with **contacts facing UP** (blue side down)
- Press brown tab down firmly until it clicks
- Cable should be secure, not loose

**Then connect Pi side:**
- Locate black PCIe connector on Pi 5 (between USB ports and GPIO)
- Lift the black tab
- Insert cable with **contacts facing DOWN** (blue side up)
- Press black tab down firmly - you should hear/feel a click

**⚠️ Common mistakes that prevent NVMe detection:**
- Tabs not fully closed (cable feels loose)
- Cable inserted backwards (contacts wrong direction)
- Cable not fully inserted before closing tab
- Cable damaged or bent pins

**6. Mount Base to Pi**
- Attach standoffs to Base using short screws
- Position Pi on top, align mounting holes
- Secure Pi with remaining screws
- Cable should have slight slack (not stretched tight)

**7. First Boot - Headless**
- **Connect Ethernet cable** (strongly recommended) OR rely on WiFi
- Connect official 27W power supply
- **NO monitor or keyboard needed!**
- Wait ~60-90 seconds for first boot (longer than normal boots)
- Green LED should blink during boot, then settle to occasional activity

**8. Find Your Pi on the Network**

**Method A: Use hostname** (easiest if it works)
```bash
# From your computer, try to ping the hostname
ping dashcam.local

# If it responds, you can SSH:
ssh pi@dashcam.local
# Enter the password you configured
```

**Method B: Find IP address with network scan**

If hostname doesn't work:

```bash
# On Linux/Mac:
# Install nmap if needed
sudo apt install nmap  # Linux
brew install nmap      # Mac

# Scan your network (adjust IP range for your network)
sudo nmap -sn 192.168.1.0/24 | grep -B 2 "Raspberry Pi"

# Or use arp-scan:
sudo arp-scan --localnet | grep -i "raspberry\|b8:27:eb\|dc:a6:32\|e4:5f:01\|d8:3a:dd"
```

```powershell
# On Windows PowerShell:
# Use Advanced IP Scanner (GUI) or:
arp -a | findstr "b8-27-eb dc-a6-32 e4-5f-01 d8-3a-dd"
```

**Method C: Check your router's DHCP leases**
- Log into your router's web interface
- Look for connected devices
- Find device named "dashcam" or "raspberrypi"

**9. SSH into Your Pi**

Once you have the hostname or IP:

```bash
# Using hostname (if .local works on your network)
ssh pi@dashcam.local

# Or using IP address
ssh pi@192.168.1.XXX

# Enter your password when prompted
```

**First time connecting:**
- You'll see a warning about host authenticity
- Type `yes` and press Enter
- Enter your password

**10. Verify Boot from NVMe**

Once logged in:

```bash
# Check what we booted from
lsblk

# Should show:
# nvme0n1     259:0    0   477G  0 disk 
# ├─nvme0n1p1 259:1    0   512M  0 part /boot/firmware
# └─nvme0n1p2 259:2    0 476.4G  0 part /
```

If you see "/" mounted on nvme0n1p2, you're booting from NVMe! ✅

**Continue to Chapter 3.**

---

### Method 2: Boot from SD, Then Clone to NVMe

Use this if you don't have a USB NVMe adapter.

#### Steps

**1. Flash SD Card**

Use Raspberry Pi Imager:
- **Device**: Raspberry Pi 5
- **OS**: Raspberry Pi OS Lite (64-bit)
- **Storage**: Your SD card

**⚠️ CRITICAL - Configure for headless:**
- ✅ Set hostname: `dashcam`
- ✅ Set username: `pi`
- ✅ Set password
- ✅ **Enable SSH**
- ✅ Configure WiFi OR plan to use Ethernet
- ✅ Set locale settings

**2. First Boot from SD Card**

- Insert SD card in Pi
- Connect power (no NVMe yet)
- Wait ~60-90 seconds
- Find Pi on network (see Method 1 step 8)
- SSH in: `ssh pi@dashcam.local`

**3. Update System**

```bash
# Update everything
sudo apt update
sudo apt full-upgrade -y

# Update bootloader
sudo rpi-eeprom-update

# If update available:
sudo rpi-eeprom-update -a

# Reboot
sudo reboot
```

Wait ~30 seconds, then SSH back in.

**4. Shutdown and Install NVMe Hardware**

```bash
# Shutdown
sudo shutdown -h now
```

- Unplug power
- Install NVMe in Base
- Connect FFC cable (see Method 1 step 5 for critical tips!)
- Mount Base to Pi
- Plug power back in
- Wait for boot, SSH back in

**5. Verify NVMe Detected**

```bash
lsblk

# Should show both:
# mmcblk0     (SD card - currently booted)
# nvme0n1     (NVMe - ready to clone to)
```

**If NVMe NOT detected:**

```bash
# Enable PCIe
sudo nano /boot/firmware/config.txt

# Add at end:
dtparam=pciex1

# Save: Ctrl+X, Y, Enter
sudo reboot
```

SSH back in and check `lsblk` again.

**6. Clone SD to NVMe**

```bash
# Stop services to prevent file corruption
sudo systemctl stop unattended-upgrades
sudo sync

# Clone using dd (takes 5-10 minutes)
sudo dd if=/dev/mmcblk0 of=/dev/nvme0n1 bs=4M status=progress conv=fsync

# Verify
sudo lsblk
# nvme0n1 should now have partitions (nvme0n1p1, nvme0n1p2)
```

**7. Expand NVMe Partition**

```bash
# Resize partition to use full NVMe space
sudo parted /dev/nvme0n1 resizepart 2 100%
sudo resize2fs /dev/nvme0n1p2

# Verify
df -h /
# Should still show SD card size (we haven't booted NVMe yet)
```

**8. Set Boot Order to NVMe First**

```bash
# Edit bootloader config
sudo rpi-eeprom-config --edit

# Find line: BOOT_ORDER=0xf41
# Change to: BOOT_ORDER=0xf416
# (This tries NVMe before SD)

# Save: Ctrl+X, Y, Enter
```

**9. Reboot and Verify NVMe Boot**

```bash
sudo reboot
```

Wait 30 seconds, SSH back in:

```bash
lsblk

# Now should show:
# nvme0n1p2 mounted on /
```

**10. Optional: Remove SD Card**

Once confirmed booting from NVMe:
- Shutdown: `sudo shutdown -h now`
- Remove SD card
- Power back on
- Should still boot from NVMe

---

### After OS Installation (Both Methods)

Now that you're booted from NVMe via SSH:

**1. Update System**

```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

**2. Check Bootloader Version**

```bash
sudo rpi-eeprom-update

# Should show Dec 2023 or newer
# If older, update:
sudo rpi-eeprom-update -a
sudo reboot
```

**3. Enable PCIe Gen 3** (Optional but Recommended)

```bash
sudo nano /boot/firmware/config.txt

# Add at the end:
dtparam=pciex1_gen=3

# Save: Ctrl+X, Y, Enter
sudo reboot
```

After reboot, verify:
```bash
sudo dmesg | grep -i pcie | grep -i speed
# Look for "link speed 8.0 GT/s" (Gen 3)
```

**4. Test NVMe Performance**

```bash
sudo hdparm -Tt /dev/nvme0n1

# Should show:
# Timing cached reads:   ~5000 MB/sec
# Timing buffered disk reads: ~700-900 MB/sec (Gen 3)
```

**Your OS is now ready! Continue to Chapter 3.**

---

## Chapter 3: Hardware Assembly

Now we'll add cameras, CAN HAT, and GPS.

### 3.1: Camera Installation

#### Front Camera (CAM0)

**1. Attach Lens**
- Remove protective caps from camera and lens
- Screw M12 lens into camera sensor
- Adjust focus ring for desired focus distance

**2. Connect FFC Cable**
- Camera side: Lift black tab, insert cable (contacts down), close tab
- One end of cable has blue stripe - note orientation

**3. Connect to Pi CAM0 Port**
- CAM0 is closer to USB-C power port
- Lift black tab on CAM0 connector
- Insert cable with contacts facing inward (toward HDMI)
- Press tab down firmly

**4. Test**
```bash
rpicam-hello --camera 0 -t 5000
# Should show preview for 5 seconds
```

#### Rear Camera (CAM1)

**1. Attach Wide Angle Lens**
- Screw 158° wide angle lens into camera
- Focus should be set to infinity for rear view

**2. Connect FFC Cable**
- Same process as front camera

**3. Connect to Pi CAM1 Port**
- CAM1 is closer to HDMI port
- Insert cable with contacts facing inward (toward USB-C)

**4. Test**
```bash
rpicam-hello --camera 1 -t 5000
# Should show preview for 5 seconds
```

**5. Verify Both Cameras**
```bash
rpicam-hello --list-cameras

# Should show:
# 0 : imx477 [4056x3040] (/base/axi/.../i2c@80000/imx477@1a)
# 1 : imx477 [4056x3040] (/base/axi/.../i2c@88000/imx477@1a)
```

### 3.2: CAN HAT Installation

**1. Shutdown Pi**
```bash
sudo shutdown -h now
```

**2. Install CAN HAT**
- Align 40-pin header with GPIO on Pi
- Press down firmly and evenly
- HAT should sit flat on standoffs
- Secure with screws if provided

**3. Physical Check**
- Ensure all 40 pins are seated
- Check for bent pins
- HAT should not rock or move

**4. Power On and Test**
```bash
# After boot, check device tree
dtoverlay -l

# Should NOT show mcp2515 yet (we'll configure in software install)
```

### 3.3: GPS Module Installation

**1. Identify GPS Connection Method**

The LC29H can connect via:
- **UART** (recommended) - GPIO pins
- **USB** - USB port

**For UART connection:**

**2. Connect to GPIO**
- **GPS TX** → **Pi GPIO 15** (RX, pin 10)
- **GPS RX** → **Pi GPIO 14** (TX, pin 8)
- **GPS GND** → **Pi GND** (pin 6, 9, 14, 20, 25, 30, 34, or 39)
- **GPS VCC** → **Pi 5V** (pin 2 or 4)

**3. Enable UART**
```bash
sudo nano /boot/firmware/config.txt

# Add if not present:
enable_uart=1

# Save and reboot
sudo reboot
```

**4. Check Serial Port**
```bash
ls -l /dev/serial* /dev/ttyAMA*

# Should show:
# /dev/serial0 -> /dev/ttyAMA0
```

### 3.4: Display Connection

**1. Connect HDMI**
- Use HDMI0 port (closer to USB-C power)
- Connect to LILLIPUT display
- Power display

**2. Verify Display**
```bash
tvservice -s

# Should show current mode (e.g., 1920x1080 @ 60Hz)
```

**Your hardware assembly is complete! Continue to Chapter 4.**

---

## Chapter 4: Software Installation

### 4.1: Upload Installation Script

From your computer:

```bash
# Copy installation script to Pi
scp dashcam_install.sh pi@dashcam.local:~/

# Copy application files
scp config.py dashcam.py video_recorder.py video_display.py gps_handler.py \
    canbus.py camaro_canbus.py pi@dashcam.local:~/
```

### 4.2: Run Installation Script

SSH to Pi:

```bash
ssh pi@dashcam.local

# Make script executable
chmod +x dashcam_install.sh

# Run installation (takes 5-10 minutes)
sudo ./dashcam_install.sh
```

The script will:
- ✅ Detect NVMe drive
- ✅ Update bootloader if needed
- ✅ Configure both Arducam cameras (IMX477 overlays)
- ✅ Configure CAN HAT (MCP2515 overlays)
- ✅ Enable PCIe Gen 3
- ✅ Install system packages
- ✅ Create Python virtual environment
- ✅ Install Python packages (python-can, picamera2, etc.)
- ✅ Configure GPS (gpsd)
- ✅ Set up CAN interfaces (can0, can1)
- ✅ Create directory structure
- ✅ Create systemd service
- ✅ Disable screen blanking
- ✅ Set NVMe boot order

### 4.3: Reboot

```bash
# When prompted, reboot
sudo reboot
```

### 4.4: Upload Application Files

After reboot:

```bash
# From your computer
scp *.py pi@dashcam.local:/home/pi/dashcam/

# Or if already copied in 4.1, just move them:
ssh pi@dashcam.local
mv ~/*.py /home/pi/dashcam/
chmod +x /home/pi/dashcam/dashcam.py
```

**Software installation complete! Continue to Chapter 5.**

---

## Chapter 5: Camera Setup

### 5.1: Verify Camera Detection

```bash
ssh pi@dashcam.local

# List detected cameras
rpicam-hello --list-cameras

# Expected output:
# 0 : imx477 [4056x3040] (/base/.../i2c@80000/imx477@1a)
#     Modes: 'SRGGB10_CSI2P' : 1332x990 ...
# 1 : imx477 [4056x3040] (/base/.../i2c@88000/imx477@1a)
#     Modes: 'SRGGB10_CSI2P' : 1332x990 ...
```

If cameras not detected, see [Troubleshooting](#chapter-10-troubleshooting).

### 5.2: Test Individual Cameras

**Front Camera (CAM0):**
```bash
# 5 second preview
rpicam-hello --camera 0 -t 5000

# Test with recording mode settings
rpicam-hello --camera 0 --width 1920 --height 1080 -t 5000
```

**Rear Camera (CAM1):**
```bash
# 5 second preview
rpicam-hello --camera 1 -t 5000

# Test with recording mode settings
rpicam-hello --camera 1 --width 1920 --height 1080 -t 5000
```

### 5.3: Adjust Camera Settings

Edit `/home/pi/dashcam/config.py`:

**Camera Orientation:**
```python
# Front camera settings
self.front_camera_rotation = 0      # 0, 90, 180, or 270
self.front_camera_hflip = False     # Horizontal flip
self.front_camera_vflip = False     # Vertical flip

# Rear camera settings  
self.rear_camera_rotation = 0
self.rear_camera_hflip = False
self.rear_camera_vflip = False
```

**Recording Settings:**
```python
# Enable/disable recording per camera
self.front_camera_recording_enabled = True
self.rear_camera_recording_enabled = True

# Video quality
self.front_camera_bitrate = 8000000  # 8 Mbps
self.rear_camera_bitrate = 8000000   # 8 Mbps
```

**Display Settings:**
```python
# Which camera to display (0=front, 1=rear)
self.display_camera_index = 1  # Rear camera for mirror

# Mirror mode
self.display_mirror_mode = True  # Flip horizontal for mirror view
```

Apply changes:
```bash
sudo systemctl restart dashcam
```

**Camera setup complete! Continue to Chapter 6.**

---

## Chapter 6: CAN Bus Setup

### 6.1: Verify CAN HAT Detection

```bash
# Check device tree overlays
dtoverlay -l | grep mcp2515

# Should show:
# 2: mcp2515-can0
# 3: mcp2515-can1
```

### 6.2: Check CAN Interface Status

```bash
# Check interfaces exist
ip link show can0
ip link show can1

# Expected state: DOWN (until we bring them up)
```

### 6.3: Bring Up CAN Interfaces

The install script creates a service to do this automatically, but you can manually test:

```bash
# Configure and bring up CAN0 (500 kbps for GM)
sudo ip link set can0 type can bitrate 500000
sudo ip link set can0 up

# Check status
ip link show can0
# Should show: state UP

# Same for CAN1
sudo ip link set can1 type can bitrate 500000
sudo ip link set can1 up
```

### 6.4: Connect to Vehicle

**1. Locate OBD-II Port**
- Usually under dashboard, driver's side
- 2013 Camaro: Left of steering column, above hood release

**2. Identify CAN Pins**

Standard OBD-II pinout:
```
   1  2  3  4  5  6  7  8
  9 10 11 12 13 14 15 16

Pin 6:  CAN-H (High)
Pin 14: CAN-L (Low)
Pin 4:  Ground (chassis)
Pin 5:  Ground (signal)
Pin 16: +12V (battery, not needed for CAN)
```

**3. Wire CAN HAT to OBD-II**

Connect to **CAN0** (first channel):
- **CAN HAT CAN0_H** → **OBD-II Pin 6** (CAN-H)
- **CAN HAT CAN0_L** → **OBD-II Pin 14** (CAN-L)
- **CAN HAT GND** → **OBD-II Pin 4 or 5** (Ground)

**4. Safety Note**
⚠️ This system READS CAN data only. Do not send CAN messages without knowing what they do. Incorrect CAN messages can damage vehicle systems.

### 6.5: Test CAN Bus Communication

**1. Start Engine**
- Turn ignition to ON or start engine
- CAN bus is usually active when ignition is on

**2. Monitor CAN Traffic**
```bash
# Monitor all CAN messages
candump can0

# Should see messages like:
# can0  0C9   [8]  00 00 00 00 1A 2B 00 00
# can0  0F1   [8]  3C 00 00 00 00 00 00 00
# ...

# Press Ctrl+C to stop
```

If no messages:
- Check ignition is ON
- Verify wiring
- Try different bitrate (some vehicles use 250k)
- See [Troubleshooting](#chapter-10-troubleshooting)

**3. Log CAN Traffic**
```bash
# Log to file for analysis
candump -l can0

# Creates candump-YYYY-MM-DD_HHMMSS.log
# Press Ctrl+C after 30-60 seconds

# View log
less candump-*.log
```

### 6.6: Identify Vehicle CAN IDs

**1. Rev Engine and Watch for Changes**
```bash
candump can0

# Rev engine gently
# Look for IDs that change with RPM
# Typically 0x0C9 on GM vehicles
```

**2. Drive and Identify Speed**
```bash
# While driving (passenger monitors!)
candump can0 | grep "0C9\|110\|1E9"

# Look for IDs that change with speed
```

**3. Update Vehicle Module**

Edit `/home/pi/dashcam/camaro_canbus.py`:

```python
# Update message IDs based on your findings
MSG_ENGINE_RPM_SPEED = 0x0C9  # Change if different
MSG_ENGINE_COOLANT = 0x0F1    # Change if different
# etc.
```

### 6.7: Enable CAN in Configuration

Edit `/home/pi/dashcam/config.py`:

```python
# Enable CAN bus
self.canbus_enabled = True

# Select channel (can0 or can1)
self.canbus_channel = "can0"

# Bitrate (500000 for GM HS-CAN)
self.canbus_bitrate = 500000

# Vehicle type
self.canbus_vehicle_type = "camaro_2013_lfx"

# Display CAN data on screen
self.display_canbus_data = True

# Log CAN data to file
self.record_canbus_data = True
```

Restart:
```bash
sudo systemctl restart dashcam
```

### 6.8: Verify CAN Integration

```bash
# Check dashcam logs
journalctl -u dashcam -f

# Should see:
# CAN bus started on can0
# CAN: RPM=..., Speed=..., Temp=...
```

**CAN bus setup complete! Continue to Chapter 7.**

---

## Chapter 7: GPS Setup

### 7.1: Verify GPS Hardware

```bash
# Check serial device exists
ls -l /dev/serial0 /dev/ttyAMA0

# Should show:
# /dev/serial0 -> /dev/ttyAMA0
```

### 7.2: Test GPS Raw Output

```bash
# View raw NMEA sentences
sudo cat /dev/ttyAMA0

# Should see output like:
# $GNGGA,123456.00,4250.1234,N,08315.5678,W,1,08,1.2,280.5,M,-34.2,M,,*6B
# $GNRMC,123456.00,A,4250.1234,N,08315.5678,W,0.05,123.4,251124,,,A*7F
# ...

# Press Ctrl+C to stop
```

If no output:
- Check wiring
- Verify GPS has power (LED should blink)
- Go outside for clear sky view
- See [Troubleshooting](#chapter-10-troubleshooting)

### 7.3: Start GPSD

```bash
# Start GPS daemon
sudo systemctl start gpsd

# Check status
sudo systemctl status gpsd

# Should show: active (running)
```

### 7.4: Test GPS with cgps

```bash
# Interactive GPS monitor
cgps -s

# Wait 1-2 minutes for GPS fix
# Should show:
# - Status: 3D FIX
# - Latitude, Longitude
# - Speed, heading
# - Satellites in view

# Press Q to quit
```

**Or use gpsmon for detailed view:**
```bash
gpsmon

# Shows detailed NMEA sentences and satellite info
# Press Q to quit
```

### 7.5: Enable GPS in Configuration

Edit `/home/pi/dashcam/config.py`:

```python
# Enable GPS
self.gps_enabled = True

# Display settings
self.display_speed = True
self.speed_unit = "mph"  # or "kph"

# Speed-based recording (optional)
self.speed_recording_enabled = False  # Set True to only record when moving
self.start_recording_speed_mph = 5.0  # Minimum speed to start recording
```

Restart:
```bash
sudo systemctl restart dashcam
```

### 7.6: Verify GPS Integration

```bash
# Check logs
journalctl -u dashcam -f

# Should see:
# GPS: 45.2 mph, Position: 42.xxxxx, -83.xxxxx
```

**GPS setup complete! Continue to Chapter 8.**

---

## Chapter 8: Final Configuration

### 8.1: Review Configuration File

```bash
nano /home/pi/dashcam/config.py
```

**Key Settings to Review:**

**Video Quality:**
```python
self.front_camera_bitrate = 8000000  # Higher = better quality, more storage
self.rear_camera_bitrate = 8000000
```

**Segment Duration:**
```python
self.video_segment_duration = 60  # Seconds per file
```

**Storage Management:**
```python
self.disk_high_water_mark = 0.75   # Start cleanup at 75%
self.keep_minimum_gb = 10.0         # Keep 10GB free
```

**Display:**
```python
self.display_camera_index = 1       # 0=front, 1=rear
self.display_mirror_mode = True     # Flip for mirror view
self.overlay_enabled = True         # Show overlays
```

**Features:**
```python
self.gps_enabled = True
self.canbus_enabled = True
self.display_canbus_data = True
```

### 8.2: Set Up Auto-Start

```bash
# Enable service to start on boot
sudo systemctl enable dashcam

# Check it's enabled
sudo systemctl is-enabled dashcam
# Should show: enabled
```

### 8.3: Test Complete System

```bash
# Start service
sudo systemctl start dashcam

# Check status
sudo systemctl status dashcam
# Should show: active (running)

# Watch logs
journalctl -u dashcam -f

# Should see:
# - Display started
# - Cameras initialized
# - Recording started
# - GPS data (if available)
# - CAN data (if vehicle connected)
```

### 8.4: Verify Recording

```bash
# Check videos being created
ls -lht /dashcam/videos/current/

# Should see new files every 60 seconds:
# front_20241125_143052_0001.h264
# rear_20241125_143052_0001.h264
```

### 8.5: Test Video Playback

```bash
# Copy a file to your computer
scp pi@dashcam.local:/dashcam/videos/current/front_*.h264 .

# Play with VLC or ffplay
vlc front_*.h264
```

**Configuration complete! Continue to Chapter 9.**

---

## Chapter 9: Testing & Verification

### 9.1: System Health Checks

**Check Service:**
```bash
sudo systemctl status dashcam
# Should show: active (running), no errors
```

**Check Cameras:**
```bash
rpicam-hello --list-cameras
# Should show 2 cameras
```

**Check CAN Bus:**
```bash
ip link show can0
# Should show: state UP

candump can0 -n 10
# Should show messages if vehicle is on
```

**Check GPS:**
```bash
cgps -s
# Should show fix and position
```

**Check Disk Space:**
```bash
df -h /dashcam
# Should show plenty of free space
```

**Check Temperature:**
```bash
vcgencmd measure_temp
# Should be below 70°C under load
```

### 9.2: Display Verification

**Check Display Output:**
- Should show live rear camera feed
- Overlay should show time (and date if enabled)
- REC indicator should blink
- Speed should show (if GPS has fix)
- CAN data should show (if enabled and vehicle connected)

**Test Mirror Mode:**
```python
# In config.py, toggle:
self.display_mirror_mode = False  # Disable mirror flip

# Restart and check
sudo systemctl restart dashcam
```

### 9.3: Recording Verification

**Check File Creation:**
```bash
watch -n 5 'ls -lht /dashcam/videos/current/ | head -10'
# Should see new files every 60 seconds
```

**Check File Sizes:**
```bash
du -sh /dashcam/videos/current/*
# Should be ~60MB per minute per camera at 8 Mbps
```

**Verify Both Cameras Recording:**
```bash
ls /dashcam/videos/current/ | grep -c "front_"
ls /dashcam/videos/current/ | grep -c "rear_"
# Should be equal or close
```

### 9.4: Storage Management Test

**Check Cleanup Function:**
```bash
# Check current usage
df -h /dashcam

# Monitor cleanup logs
journalctl -u dashcam | grep -i cleanup

# Should see cleanup messages when approaching 75%
```

### 9.5: Error Recovery Test

**Test Camera Disconnect:**
```bash
# Stop service
sudo systemctl stop dashcam

# Disconnect one camera
# Reconnect camera

# Start service
sudo systemctl start dashcam

# Check logs for recovery
journalctl -u dashcam -f
# Should show camera reconnection
```

### 9.6: Performance Benchmark

**NVMe Speed:**
```bash
sudo hdparm -Tt /dev/nvme0n1
# Should show 700-900 MB/s (Gen 3)
```

**CPU Usage:**
```bash
htop
# During recording, should be 30-50% total
```

**Memory Usage:**
```bash
free -h
# Should have 2-3GB free on 8GB Pi
```

### 9.7: Full System Test

**1. Cold Boot Test:**
```bash
sudo reboot
```

Wait for boot, then verify:
- Service starts automatically
- Cameras initialize
- Recording starts
- Display shows video
- No errors in logs

**2. Drive Test:**
- GPS should track position and speed
- CAN data should update
- Video should record smoothly
- Files should rotate every 60 seconds

**3. Long Run Test:**
- Let run for several hours
- Check temperature stays reasonable
- Check disk cleanup works
- Check no errors accumulate

**All tests passed? Your system is ready for production use!**

---

## Chapter 10: Troubleshooting

### 10.1: NVMe Not Detected

**Symptom:** `lsblk` doesn't show nvme0n1

**Solutions:**

1. **Check Cable Connection** (most common)
   ```bash
   sudo shutdown -h now
   # Unplug power
   # Reseat cable at BOTH ends
   # Ensure clips are FULLY closed
   # Plug power, boot, check again
   ```

2. **Check Bootloader**
   ```bash
   sudo rpi-eeprom-update
   # Should be Dec 2023 or newer
   # If older:
   sudo rpi-eeprom-update -a
   sudo reboot
   ```

3. **Enable PCIe Explicitly**
   ```bash
   sudo nano /boot/firmware/config.txt
   # Add: dtparam=pciex1
   sudo reboot
   ```

### 10.2: Cameras Not Detected

**Symptom:** `rpicam-hello --list-cameras` shows no cameras or only one

**Solutions:**

1. **Check Config.txt**
   ```bash
   sudo nano /boot/firmware/config.txt
   
   # Should have:
   camera_auto_detect=0
   dtoverlay=imx477,cam0
   dtoverlay=imx477,cam1
   
   # Save and reboot
   sudo reboot
   ```

2. **Check Cable Connections**
   - Power off
   - Reseat both camera FFC cables
   - Ensure tabs are fully closed
   - Cable contacts facing correct direction

3. **Test Cameras Individually**
   ```bash
   # Shutdown
   sudo shutdown -h now
   
   # Test with only CAM0 connected
   # Boot and check: rpicam-hello --list-cameras
   
   # Then add CAM1 and test again
   ```

4. **Check for Hardware Damage**
   - Inspect FFC cables for tears
   - Check camera connectors for bent pins
   - Try different cable if available

### 10.3: CAN Bus Not Working

**Symptom:** `ip link show can0` shows "Device not found" or no CAN messages

**Solutions:**

1. **Check Device Tree Overlays**
   ```bash
   dtoverlay -l | grep mcp2515
   # Should show mcp2515-can0 and mcp2515-can1
   
   # If not, check /boot/firmware/config.txt:
   sudo nano /boot/firmware/config.txt
   
   # Should have:
   dtparam=spi=on
   dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=22
   dtoverlay=mcp2515-can1,oscillator=16000000,interrupt=13
   ```

2. **Check CAN HAT Physical Connection**
   - Power off
   - Remove and reseat CAN HAT
   - Ensure all 40 pins are properly connected

3. **Bring Up Interface Manually**
   ```bash
   sudo ip link set can0 type can bitrate 500000
   sudo ip link set can0 up
   ip link show can0
   ```

4. **Check Vehicle Connection**
   - Verify ignition is ON (CAN bus usually inactive when off)
   - Check OBD-II wiring (CAN-H pin 6, CAN-L pin 14, GND pin 4/5)
   - Try different bitrate (250000 for some vehicles)

5. **Test Loopback Mode**
   ```bash
   # Set loopback mode (no vehicle needed)
   sudo ip link set can0 type can bitrate 500000 loopback on
   sudo ip link set can0 up
   
   # Send test message
   cansend can0 123#DEADBEEF
   
   # Monitor
   candump can0
   # Should see your test message
   ```

### 10.4: GPS Not Getting Fix

**Symptom:** cgps shows "No Fix" or no satellites

**Solutions:**

1. **Go Outside**
   - GPS needs clear view of sky
   - Won't work indoors
   - Takes 1-2 minutes outdoors for first fix

2. **Check GPS Power and Connection**
   ```bash
   # Check for data
   sudo cat /dev/ttyAMA0
   # Should see NMEA sentences like $GNGGA, $GNRMC
   
   # If no output:
   # - Check wiring (TX, RX, GND, VCC)
   # - Verify GPS LED is blinking
   # - Check 5V power
   ```

3. **Check GPSD Status**
   ```bash
   sudo systemctl status gpsd
   
   # If not running:
   sudo systemctl start gpsd
   
   # Check gpsd is listening on correct port:
   sudo lsof -i :2947
   ```

4. **Restart GPSD**
   ```bash
   sudo systemctl stop gpsd
   sudo killall gpsd
   sudo systemctl start gpsd
   cgps -s
   ```

### 10.5: Service Won't Start

**Symptom:** `sudo systemctl status dashcam` shows failed

**Solutions:**

1. **Check Detailed Logs**
   ```bash
   journalctl -u dashcam -n 100 --no-pager
   # Look for specific error messages
   ```

2. **Run Manually to See Errors**
   ```bash
   sudo systemctl stop dashcam
   cd /home/pi/dashcam
   sudo /home/pi/dashcam/venv/bin/python dashcam.py
   
   # Watch for errors
   # Press Ctrl+C when done
   ```

3. **Common Issues:**
   - **Camera not found**: Check camera detection
   - **Framebuffer permission denied**: `sudo usermod -a -G video pi`, reboot
   - **Import error**: `cd /home/pi/dashcam/venv && bin/pip install <missing_package>`
   - **Config validation error**: Check config.py for typos

### 10.6: Display Issues

**Symptom:** Black screen, no video, or distorted image

**Solutions:**

1. **Check HDMI Connection**
   ```bash
   tvservice -s
   # Should show current mode
   
   # If no display:
   tvservice -o  # Power off HDMI
   tvservice -p  # Power on HDMI
   ```

2. **Check Framebuffer**
   ```bash
   ls -l /dev/fb0
   # Should exist and be accessible
   
   # Check permissions
   groups pi
   # Should include "video"
   
   # If not:
   sudo usermod -a -G video pi
   sudo reboot
   ```

3. **Force HDMI Mode**
   ```bash
   sudo nano /boot/firmware/config.txt
   
   # Add:
   hdmi_force_hotplug=1
   hdmi_group=2
   hdmi_mode=82  # 1920x1080 60Hz
   
   # Save and reboot
   sudo reboot
   ```

4. **Test Display with rpicam**
   ```bash
   # Stop dashcam service
   sudo systemctl stop dashcam
   
   # Test camera preview
   rpicam-hello --camera 1 -t 0
   # Should show preview
   # Press Ctrl+C to stop
   ```

### 10.7: Performance Issues

**Symptom:** Dropped frames, stuttering, high CPU

**Solutions:**

1. **Check Temperature**
   ```bash
   vcgencmd measure_temp
   # If above 80°C, throttling occurs
   
   # Add Active Cooler or improve ventilation
   ```

2. **Check CPU Frequency**
   ```bash
   vcgencmd get_config arm_freq
   # Should be 2400 (boosted)
   
   # If lower, check /boot/firmware/config.txt:
   arm_boost=1
   ```

3. **Lower Video Quality**
   ```python
   # In config.py:
   self.front_camera_bitrate = 6000000  # Reduce from 8M
   self.rear_camera_bitrate = 6000000
   ```

4. **Check NVMe Performance**
   ```bash
   sudo hdparm -Tt /dev/nvme0n1
   # Should be 700+ MB/s
   # If much lower, check PCIe Gen 3 is enabled
   ```

### 10.8: Disk Full

**Symptom:** Recording stops, "No space left on device" errors

**Solutions:**

1. **Check Disk Usage**
   ```bash
   df -h /dashcam
   ```

2. **Manual Cleanup**
   ```bash
   # Delete files older than 3 days
   find /dashcam/videos/archive/ -name "*.h264" -mtime +3 -delete
   ```

3. **Lower Cleanup Threshold**
   ```python
   # In config.py:
   self.disk_high_water_mark = 0.60  # Start cleanup earlier
   ```

4. **Check Automatic Cleanup is Working**
   ```bash
   journalctl -u dashcam | grep -i cleanup
   # Should see cleanup messages
   ```

### 10.9: SSH Connection Issues

**Symptom:** Can't connect via SSH

**Solutions:**

1. **Verify SSH is Enabled**
   ```bash
   # Need physical access to Pi
   sudo systemctl enable ssh
   sudo systemctl start ssh
   ```

2. **Check Network**
   ```bash
   # From your computer:
   ping dashcam.local
   # or
   ping <IP_ADDRESS>
   ```

3. **Find IP Address**
   - Check router DHCP leases
   - Use nmap: `sudo nmap -sn 192.168.1.0/24`
   - Connect monitor and keyboard temporarily

4. **Check Firewall**
   ```bash
   sudo ufw status
   # If active, ensure port 22 is allowed
   ```

---

## Summary

You now have a complete Active Dash Mirror system with:
- ✅ Dual Arducam HQ cameras (1080p@30fps each)
- ✅ CAN bus vehicle data integration
- ✅ GPS tracking and logging
- ✅ Live rearview mirror display
- ✅ Automatic storage management
- ✅ Remote monitoring via SSH

### Daily Operation

**Morning Check:**
```bash
ssh pi@dashcam.local
sudo systemctl status dashcam
df -h /dashcam
```

**After Trip:**
```bash
# Copy important footage
scp pi@dashcam.local:/dashcam/videos/archive/front_*.h264 ./backup/
```

**Maintenance:**
- Check temperature monthly
- Update software quarterly: `sudo apt update && sudo apt upgrade`
- Review and backup important footage regularly

---

**Enjoy your Active Dash Mirror system!** 🚗📹✨

For additional help, see:
- [README.md](README.md) - Overview and quick reference
- [CANBUS_GUIDE.md](CANBUS_GUIDE.md) - Detailed CAN bus information