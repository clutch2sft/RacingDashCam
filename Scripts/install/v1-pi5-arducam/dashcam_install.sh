#!/bin/bash
#
# Active Dash Mirror Installation Script
# For Raspberry Pi 5 with Pimoroni NVMe Base
# 
# This script sets up a complete dash cam system with:
# - NVMe boot drive configuration
# - Dual Arducam HQ camera setup (both IMX477)
# - Low-latency camera display
# - GPS integration
# - CAN bus integration
# - Auto-start on boot
#
# Hardware:
# - Camera 0 (CAM0): Arducam 12.3MP HQ (front-facing)
# - Camera 1 (CAM1): Arducam 12.3MP HQ with 158° wide angle (rear mirror)
#
# Usage: 
#   chmod +x dashcam_install.sh
#   sudo ./dashcam_install.sh [github-repo-url]
#
# Example:
#   sudo ./dashcam_install.sh https://github.com/yourusername/RacingDashCam.git
#

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="${1:-}"
INSTALL_BASE="/opt/dashcam"
REPO_DIR="$INSTALL_BASE/RacingDashCam"
VIDEO_BASE="/var/opt/dashcam"
VIDEO_DIR="$VIDEO_BASE/videos"
LOG_DIR="$VIDEO_BASE/logs"
CONFIG_DIR="/etc/dashcam"
VENV_DIR="$INSTALL_BASE/venv"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Active Dash Mirror Installation${NC}"
echo -e "${BLUE}  Raspberry Pi 5 + NVMe Base${NC}"
echo -e "${BLUE}  Dual CSI Camera Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}ERROR: Please run as root (sudo)${NC}"
    exit 1
fi

# Check for repository URL
if [ -z "$REPO_URL" ]; then
    echo -e "${RED}ERROR: GitHub repository URL required${NC}"
    echo ""
    echo "Usage: sudo $0 <github-repo-url>"
    echo "Example: sudo $0 https://github.com/yourusername/RacingDashCam.git"
    exit 1
fi

# Validate we have a real user (not just root)
if [ -z "$SUDO_USER" ]; then
    echo -e "${RED}ERROR: Must be run with sudo, not as root directly${NC}"
    exit 1
fi

# Check if we're on a Pi 5
if ! grep -q "Raspberry Pi 5" /proc/cpuinfo; then
    echo -e "${YELLOW}WARNING: This doesn't appear to be a Raspberry Pi 5${NC}"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo -e "${GREEN}Step 1: Checking NVMe drive...${NC}"
if lsblk | grep -q nvme0n1; then
    echo -e "${GREEN}✓ NVMe drive detected${NC}"
    lsblk | grep nvme
else
    echo -e "${RED}✗ No NVMe drive detected!${NC}"
    echo -e "${YELLOW}Please check:${NC}"
    echo "  1. NVMe drive is properly installed in the NVMe Base"
    echo "  2. PCIe FFC cable is properly connected at both ends"
    echo "  3. Cable clips are fully closed on both Pi and Base"
    echo ""
    echo "Run 'lsblk' to see available drives"
    exit 1
fi

echo ""
echo -e "${GREEN}Step 2: Checking and updating bootloader...${NC}"

# Check if bootloader update is available
if rpi-eeprom-update | grep -q "UPDATE AVAILABLE"; then
    echo -e "${BLUE}Bootloader update available, updating...${NC}"
    rpi-eeprom-update -a
    echo -e "${GREEN}✓ Bootloader updated${NC}"
else
    echo -e "${GREEN}✓ Bootloader is up to date${NC}"
fi

# Show current version
BOOTLOADER_DATE=$(vcgencmd bootloader_version | grep "version" | cut -d' ' -f2)
echo -e "${GREEN}✓ Bootloader version: $BOOTLOADER_DATE${NC}"

echo ""
echo -e "${GREEN}Step 3: Configuring system settings...${NC}"

CONFIG_FILE="/boot/firmware/config.txt"

# Backup config file
cp "$CONFIG_FILE" "$CONFIG_FILE.backup.$(date +%Y%m%d_%H%M%S)"

# Check and update camera auto-detect
if grep -q "^camera_auto_detect=1" "$CONFIG_FILE"; then
    echo -e "${BLUE}Disabling camera auto-detect...${NC}"
    sed -i 's/^camera_auto_detect=1/camera_auto_detect=0/' "$CONFIG_FILE"
    echo -e "${GREEN}✓ Camera auto-detect disabled${NC}"
elif ! grep -q "^camera_auto_detect=0" "$CONFIG_FILE"; then
    echo -e "${BLUE}Adding camera_auto_detect=0...${NC}"
    echo "camera_auto_detect=0" >> "$CONFIG_FILE"
    echo -e "${GREEN}✓ Camera auto-detect disabled${NC}"
else
    echo -e "${GREEN}✓ Camera auto-detect already disabled${NC}"
fi

# Remove existing Active Dash Mirror configuration if present
sed -i '/# Active Dash Mirror Configuration/,/# End Active Dash Mirror Configuration/d' "$CONFIG_FILE"

# Add comprehensive configuration
echo -e "${BLUE}Adding camera and system configuration...${NC}"
cat >> "$CONFIG_FILE" << 'EOF'

# ========================================
# Active Dash Mirror Configuration
# ========================================

# Dual CSI Camera Setup
# CAM0 (front): Arducam 12.3MP HQ Camera (IMX477)
dtoverlay=imx477,cam0

# CAM1 (rear): Arducam 12.3MP HQ Camera (IMX477)
dtoverlay=imx477,cam1

# Enable PCIe Gen 3 (experimental - better NVMe performance)
dtparam=pciex1_gen=3

# Increase CMA memory for dual cameras
# 512MB provides good headroom for 4K + HQ camera
dtparam=cma=512M

# Disable screen blanking
consoleblank=0

# Performance settings
arm_boost=1
over_voltage=2
arm_freq=2400

# GPU memory allocation (256MB minimum for dual cameras)
gpu_mem=256

# Enable UART for GPS
enable_uart=1

# CAN Bus Configuration (Waveshare 2-CH CAN HAT Plus)
# Enable SPI for MCP2515 CAN controllers
dtparam=spi=on
dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000
dtoverlay=mcp2515-can1,oscillator=12000000,interrupt=24,spimaxfrequency=2000000

# End Active Dash Mirror Configuration
# ========================================
EOF

echo -e "${GREEN}✓ System configuration complete${NC}"

echo ""
echo -e "${GREEN}Step 4: Installing system packages...${NC}"
apt update
apt install -y \
    python3-venv \
    python3-dev \
    python3-pip \
    python3-picamera2 \
    python3-libcamera \
    python3-kms++ \
    python3-opencv \
    python3-numpy \
    v4l-utils \
    ffmpeg \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-bad \
    rpicam-apps \
    gpsd \
    gpsd-clients \
    can-utils \
    git \
    vim \
    htop \
    screen \
    rsync \
    libcap-dev \
    i2c-tools

echo -e "${GREEN}✓ System packages installed${NC}"

echo ""
echo -e "${GREEN}Step 5: Creating directory structure...${NC}"

# Create application directories
mkdir -p "$INSTALL_BASE"
mkdir -p "$CONFIG_DIR"

# Create data directories
mkdir -p "$VIDEO_DIR/current"
mkdir -p "$VIDEO_DIR/archive"
mkdir -p "$LOG_DIR"

# Set ownership for data directories
chown -R $SUDO_USER:$SUDO_USER "$VIDEO_BASE"

# Also create legacy/compat paths under the install base so services
# that expect /opt/dashcam/videos and /opt/dashcam/logs will work.
mkdir -p "$INSTALL_BASE/videos/current"
mkdir -p "$INSTALL_BASE/videos/archive"
mkdir -p "$INSTALL_BASE/logs"
chown -R $SUDO_USER:$SUDO_USER "$INSTALL_BASE"

echo -e "${GREEN}✓ Directories created${NC}"
echo "  Install: $INSTALL_BASE"
echo "  Config:  $CONFIG_DIR"
echo "  Videos:  $VIDEO_DIR"
echo "  Logs:    $LOG_DIR"

echo ""
echo -e "${GREEN}Step 6: Cloning repository from GitHub...${NC}"

if [ -d "$REPO_DIR" ]; then
    echo -e "${YELLOW}Repository already exists, pulling latest changes...${NC}"
    cd "$REPO_DIR"
    git pull
else
    echo -e "${BLUE}Cloning $REPO_URL...${NC}"
    git clone "$REPO_URL" "$REPO_DIR"
fi

# Set ownership
chown -R $SUDO_USER:$SUDO_USER "$REPO_DIR"

# Ensure dashcam.py uses package-qualified imports (fix older clones)
# This patches legacy top-level imports like `from config import config`
if [ -f "$REPO_DIR/python/dashcam.py" ]; then
    if grep -q "from config import config" "$REPO_DIR/python/dashcam.py" 2>/dev/null; then
        echo -e "${BLUE}Patching legacy imports in dashcam.py...${NC}"
        sed -i "s|from config import config|from dashcam.core.config import config|g" "$REPO_DIR/python/dashcam.py"
        sed -i "s|from video_display import VideoDisplay|from dashcam.platforms.pi5_arducam.video_display import VideoDisplay|g" "$REPO_DIR/python/dashcam.py"
        sed -i "s|from video_recorder import VideoRecorder|from dashcam.platforms.pi5_arducam.video_recorder import VideoRecorder|g" "$REPO_DIR/python/dashcam.py"
        sed -i "s|from gps_handler import GPSHandler|from dashcam.core.gps_handler import GPSHandler|g" "$REPO_DIR/python/dashcam.py"
        chown $SUDO_USER:$SUDO_USER "$REPO_DIR/python/dashcam.py"
        echo -e "${GREEN}✓ dashcam.py imports patched${NC}"
    fi
fi

echo -e "${GREEN}✓ Repository cloned/updated${NC}"
echo "  Location: $REPO_DIR"

echo ""
echo -e "${GREEN}Step 7: Setting up Python virtual environment...${NC}"

# Create venv with system-site-packages for Picamera2 access
python3 -m venv --system-site-packages "$VENV_DIR"

# Install Python packages in venv
echo -e "${BLUE}Installing Python packages in virtual environment...${NC}"
"$VENV_DIR/bin/pip" install --upgrade pip

# Install the dashcam package in development mode
cd "$REPO_DIR/python"
"$VENV_DIR/bin/pip" install -e .

# Install additional dependencies
"$VENV_DIR/bin/pip" install \
    pillow \
    gps \
    pyserial \
    pyyaml \
    python-can

# Note: Picamera2, numpy, opencv accessed from system packages

echo -e "${GREEN}✓ Virtual environment created and packages installed${NC}"
echo "  Location: $VENV_DIR"

echo ""
echo -e "${GREEN}Step 8: Creating default configuration...${NC}"

# Create a default config file if it doesn't exist
if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    cat > "$CONFIG_DIR/config.yaml" << 'EOF'
# Active Dash Mirror Configuration
# Edit this file to customize your setup

# Video settings
video:
  # Directory for video recordings
  output_dir: /var/opt/dashcam/videos/current
  
  # Archive directory for processed videos
  archive_dir: /var/opt/dashcam/videos/archive
  
  # Resolution for front camera (CAM0)
  front_resolution: [1920, 1080]
  
  # Resolution for rear camera (CAM1) 
  rear_resolution: [1920, 1080]
  
  # Frame rate
  framerate: 30
  
  # Video segment duration in seconds
  segment_duration: 60
  
  # Keep last N segments (rolling buffer)
  keep_segments: 10

# Display settings
display:
  # Main display resolution
  resolution: [1920, 1080]
  
  # Show rear camera as picture-in-picture
  pip_enabled: true
  
  # PIP size and position (x, y, width, height)
  pip_rect: [1520, 20, 380, 214]
  
  # Show overlay info (speed, GPS, etc)
  overlay_enabled: true

# GPS settings
gps:
  enabled: true
  device: /dev/serial0

# CAN bus settings
canbus:
  enabled: true
  # Vehicle profile to use (see dashcam/canbus/vehicles/)
  vehicle: camaro_2013_lfx
  # CAN interfaces
  interfaces:
    - can0
    - can1

# Logging
logging:
  level: INFO
  dir: /var/opt/dashcam/logs
EOF

    chown $SUDO_USER:$SUDO_USER "$CONFIG_DIR/config.yaml"
    echo -e "${GREEN}✓ Default configuration created${NC}"
else
    echo -e "${GREEN}✓ Configuration file already exists${NC}"
fi

echo "  Config file: $CONFIG_DIR/config.yaml"

echo ""
echo -e "${BLUE}Camera Configuration:${NC}"
echo "  CAM0 (CSI port 0): Arducam HQ 12.3MP - Front camera"
echo "  CAM1 (CSI port 1): Arducam HQ 12.3MP - Rear mirror"
echo ""
echo -e "${YELLOW}Note: After reboot, verify cameras with:${NC}"
echo "  rpicam-hello --list-cameras"
echo ""

echo ""
echo -e "${GREEN}Step 9: Configuring GPS (GPSD)...${NC}"

# Configure GPSD for LC29H module
cat > /etc/default/gpsd << 'EOF'
# Default settings for the gpsd init script and the hotplug wrapper.

# Start the gpsd daemon automatically at boot time
START_DAEMON="true"

# Use USB hotplugging to add new USB devices automatically to the daemon
USBAUTO="true"

# Devices gpsd should collect to at boot time.
# LC29H module typically appears as /dev/ttyAMA0 or /dev/serial0
DEVICES="/dev/serial0 /dev/ttyAMA0"

# Other options you want to pass to gpsd
GPSD_OPTIONS="-n -G"
EOF

# Disable serial console to free up serial port for GPS
systemctl disable serial-getty@ttyAMA0.service 2>/dev/null || true
systemctl disable serial-getty@serial0.service 2>/dev/null || true

# Enable GPSD
systemctl enable gpsd.service
systemctl enable gpsd.socket

echo -e "${GREEN}✓ GPSD configured${NC}"

echo ""
echo -e "${GREEN}Step 10: Configuring CAN bus...${NC}"

# Create systemd service to bring up CAN interfaces on boot
cat > /etc/systemd/system/can-setup.service << 'EOF'
[Unit]
Description=Setup CAN interfaces
After=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/setup-can.sh

[Install]
WantedBy=multi-user.target
EOF

# Create CAN setup script
cat > /usr/local/bin/setup-can.sh << 'EOF'
#!/bin/bash
# Setup CAN interfaces for Waveshare 2-CH CAN HAT

# Bring up CAN0 (500 kbps for GM HS-CAN)
ip link set can0 type can bitrate 500000
ip link set can0 up

# Bring up CAN1 (500 kbps)
ip link set can1 type can bitrate 500000
ip link set can1 up

echo "CAN interfaces configured"
EOF

chmod +x /usr/local/bin/setup-can.sh

# Enable CAN setup service
systemctl daemon-reload
systemctl enable can-setup.service

echo -e "${GREEN}✓ CAN bus configured${NC}"
echo "  CAN0 and CAN1 will be configured at boot (500 kbps)"

echo ""
echo -e "${GREEN}Step 11: Creating systemd service...${NC}"

cat > /etc/systemd/system/dashcam.service << EOF
[Unit]
Description=Active Dash Mirror - Dual CSI Camera System
After=network.target graphical.target gpsd.service can-setup.service
Wants=gpsd.service can-setup.service

[Service]
Type=simple
User=$SUDO_USER
WorkingDirectory=$REPO_DIR/python
Environment="PYTHONUNBUFFERED=1"
Environment="LIBCAMERA_LOG_LEVELS=*:ERROR"
Environment="DASHCAM_CONFIG=$CONFIG_DIR/config.yaml"
ExecStart=$VENV_DIR/bin/python -m dashcam
Restart=always
RestartSec=5

# Logging
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable dashcam.service

echo -e "${GREEN}✓ Systemd service created and enabled${NC}"

echo ""
echo -e "${GREEN}Step 12: Disabling screen blanking...${NC}"

# Add to rc.local
if [ ! -f /etc/rc.local ]; then
    cat > /etc/rc.local << 'EOF'
#!/bin/bash
# Disable screen blanking
setterm -blank 0 -powerdown 0 -powersave off > /dev/tty1 2>&1 || true
echo -e "\033[9;0]" > /dev/tty0 2>&1 || true

exit 0
EOF
    chmod +x /etc/rc.local
else
    if ! grep -q "screen blanking" /etc/rc.local; then
        sed -i '/exit 0/i # Disable screen blanking\nsetterm -blank 0 -powerdown 0 -powersave off > /dev/tty1 2>&1 || true\necho -e "\\033[9;0]" > /dev/tty0 2>&1 || true\n' /etc/rc.local
    fi
fi

echo -e "${GREEN}✓ Screen blanking disabled${NC}"

echo ""
echo -e "${GREEN}Step 13: Configuring framebuffer permissions...${NC}"

# Add user to video group for framebuffer access
usermod -a -G video $SUDO_USER
echo -e "${GREEN}✓ User added to video group${NC}"

# Set framebuffer permissions
if [ -e /dev/fb0 ]; then
    chmod 666 /dev/fb0
    echo -e "${GREEN}✓ Framebuffer permissions set${NC}"
else
    echo -e "${YELLOW}⚠  Framebuffer not found (will be available after reboot)${NC}"
fi

# Create udev rule for persistent framebuffer permissions
cat > /etc/udev/rules.d/99-framebuffer.rules << 'EOF'
# Allow video group access to framebuffer
KERNEL=="fb0", MODE="0666", GROUP="video"
EOF

echo -e "${GREEN}✓ Framebuffer udev rule created${NC}"

echo ""
echo -e "${GREEN}Step 14: Setting boot order for NVMe...${NC}"

# Set boot order to try NVMe first
BOOT_CONFIG="/tmp/bootloader_config.txt"
rpi-eeprom-config > "$BOOT_CONFIG"

if ! grep -q "BOOT_ORDER=0xf416" "$BOOT_CONFIG"; then
    sed -i 's/BOOT_ORDER=.*/BOOT_ORDER=0xf416/' "$BOOT_CONFIG"
    rpi-eeprom-config --apply "$BOOT_CONFIG"
    echo -e "${GREEN}✓ Boot order set to: NVMe -> USB -> SD${NC}"
else
    echo -e "${GREEN}✓ Boot order already configured${NC}"
fi

rm -f "$BOOT_CONFIG"

echo ""
echo -e "${GREEN}Step 15: Creating convenience scripts...${NC}"

# Camera test script
cat > /usr/local/bin/dashcam-test-cameras << 'TESTEOF'
#!/bin/bash
# Camera test script for dual CSI setup

echo "========================================"
echo "  Camera Detection Test"
echo "========================================"
echo ""

echo "Detected cameras:"
rpicam-hello --list-cameras

echo ""
echo "========================================"
echo "Testing CAM0 (Arducam HQ - Front)..."
echo "========================================"
rpicam-hello -t 5000 --camera 0 --width 1920 --height 1080

echo ""
echo "========================================"
echo "Testing CAM1 (Arducam HQ - Rear)..."
echo "========================================"
rpicam-hello -t 5000 --camera 1 --width 1920 --height 1080

echo ""
echo "Test complete!"
TESTEOF

chmod +x /usr/local/bin/dashcam-test-cameras

# Repository update script
cat > /usr/local/bin/dashcam-update << UPDATEEOF
#!/bin/bash
# Update dashcam software from GitHub

set -e

echo "Updating dashcam software..."

# Stop service if running
echo "Stopping dashcam service..."
sudo systemctl stop dashcam || true

# Pull latest changes
echo "Pulling latest changes from GitHub..."
cd $REPO_DIR
sudo -u $SUDO_USER git pull

# Update Python dependencies
echo "Updating Python dependencies..."
cd $REPO_DIR/python
$VENV_DIR/bin/pip install -e . --upgrade

# Reload systemd
echo "Reloading systemd..."
sudo systemctl daemon-reload

# Start service
echo "Starting dashcam service..."
sudo systemctl start dashcam

echo "Update complete!"
echo ""
echo "Check status with: sudo systemctl status dashcam"
echo "View logs with: journalctl -u dashcam -f"
UPDATEEOF

chmod +x /usr/local/bin/dashcam-update

# Status script
cat > /usr/local/bin/dashcam-status << 'STATUSEOF'
#!/bin/bash
# Show dashcam system status

echo "=========================================="
echo "  Dashcam System Status"
echo "=========================================="
echo ""

echo "Service Status:"
systemctl status dashcam --no-pager || true
echo ""

echo "Cameras:"
rpicam-hello --list-cameras 2>&1 | head -20
echo ""

echo "GPS Status:"
timeout 2 gpspipe -w -n 5 2>/dev/null || echo "GPS not responding"
echo ""

echo "CAN Bus:"
ip link show can0 2>/dev/null || echo "CAN0 not configured"
ip link show can1 2>/dev/null || echo "CAN1 not configured"
echo ""

echo "Disk Usage:"
df -h /var/opt/dashcam
echo ""

echo "Recent Log Entries:"
journalctl -u dashcam -n 20 --no-pager
STATUSEOF

chmod +x /usr/local/bin/dashcam-status

echo -e "${GREEN}✓ Convenience scripts created${NC}"
echo "  dashcam-test-cameras - Test camera functionality"
echo "  dashcam-update       - Update software from GitHub"
echo "  dashcam-status       - Show system status"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Installation Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}IMPORTANT: Reboot required for all changes to take effect${NC}"
echo ""
echo "Installation Summary:"
echo "  ✓ NVMe drive detected and configured"
echo "  ✓ PCIe Gen 3 enabled for better performance"
echo "  ✓ Dual CSI cameras configured:"
echo "    - CAM0: Arducam HQ 12.3MP (front)"
echo "    - CAM1: Arducam HQ 12.3MP (rear mirror)"
echo "  ✓ GPU memory set to 256MB for dual cameras"
echo "  ✓ CMA memory set to 512MB for video buffers"
echo "  ✓ GPS configured (LC29H on serial port)"
echo "  ✓ CAN bus configured (Waveshare 2-CH CAN HAT)"
echo "  ✓ Repository cloned: $REPO_DIR"
echo "  ✓ Python virtual environment: $VENV_DIR"
echo "  ✓ Configuration: $CONFIG_DIR/config.yaml"
echo "  ✓ Video directory: $VIDEO_DIR"
echo "  ✓ Auto-start service configured"
echo ""
echo "Directory Structure:"
echo "  /opt/dashcam/           - Application installation"
echo "    ├── RacingDashCam/    - Git repository"
echo "    └── venv/             - Python virtual environment"
echo "  /etc/dashcam/           - Configuration files"
echo "    └── config.yaml       - Main config (edit this!)"
echo "  /var/opt/dashcam/       - Runtime data"
echo "    ├── videos/           - Video recordings"
echo "    └── logs/             - Application logs"
echo ""
echo "Next steps:"
echo "  1. REBOOT: sudo reboot"
echo ""
echo "  2. After reboot, test cameras:"
echo "     dashcam-test-cameras"
echo ""
echo "  3. Check system status:"
echo "     dashcam-status"
echo ""
echo "  4. Edit configuration:"
echo "     sudo nano $CONFIG_DIR/config.yaml"
echo ""
echo "  5. Service management:"
echo "     sudo systemctl start dashcam   # Start"
echo "     sudo systemctl stop dashcam    # Stop"
echo "     sudo systemctl status dashcam  # Check status"
echo "     sudo systemctl restart dashcam # Restart"
echo "     journalctl -u dashcam -f       # View logs"
echo ""
echo "  6. Update software:"
echo "     dashcam-update"
echo ""
echo -e "${YELLOW}Hardware reminder:${NC}"
echo "  - Connect front Arducam HQ to CAM0 (port closer to USB-C)"
echo "  - Connect rear Arducam HQ to CAM1 (port closer to HDMI)"
echo "  - Both cameras should have proper FFC cable connections"
echo ""
echo -e "${YELLOW}Configuration:${NC}"
echo "  - Edit $CONFIG_DIR/config.yaml to customize settings"
echo "  - Default vehicle profile: Camaro 2013 LFX"
echo "  - See Docs/CANBUS_GUIDE.md for vehicle-specific setup"
echo ""
read -p "Reboot now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Rebooting..."
    reboot
fi