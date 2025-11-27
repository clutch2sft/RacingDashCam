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
WIFI_COUNTRY="${WIFI_COUNTRY:-US}"
AP_SSID="${AP_SSID:-dashcamxfer}"
AP_PSK="${AP_PSK:-changeme}"
AP_IP="10.42.0.1"
AP_RANGE_START="10.42.0.50"
AP_RANGE_END="10.42.0.150"
AP_NETMASK="255.255.255.0"

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
CMDLINE_FILE="/boot/firmware/cmdline.txt"
CMDLINE_DESIRED="quiet loglevel=0 splash vt.global_cursor_default=0 root=PARTUUID=5a50945f-02 rootfstype=ext4 fsck.repair=yes rootwait"

# Backup config file
cp "$CONFIG_FILE" "$CONFIG_FILE.backup.$(date +%Y%m%d_%H%M%S)"
cp "$CMDLINE_FILE" "$CMDLINE_FILE.backup.$(date +%Y%m%d_%H%M%S)"

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
# CAN0 on SPI0 CE0 (GPIO8) with INT on GPIO22 (INT_0 jumper → D22)
dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=22

# CAN1 on SPI0 CE1 (GPIO7) with INT on GPIO13 (INT_1 jumper → D13)
dtoverlay=mcp2515-can1,oscillator=16000000,interrupt=13

# End Active Dash Mirror Configuration
# ========================================
EOF

echo -e "${GREEN}✓ System configuration complete${NC}"

# Ensure cmdline.txt matches expected boot parameters for dashcam setup
CURRENT_CMDLINE=$(tr -d '\n' < "$CMDLINE_FILE")
if [ "$CURRENT_CMDLINE" != "$CMDLINE_DESIRED" ]; then
    echo -e "${BLUE}Updating $CMDLINE_FILE...${NC}"
    echo "$CMDLINE_DESIRED" > "$CMDLINE_FILE"
    echo -e "${GREEN}✓ cmdline.txt updated${NC}"
else
    echo -e "${GREEN}✓ cmdline.txt already configured${NC}"
fi

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
    i2c-tools \
    chrony \
    hostapd \
    dnsmasq

echo -e "${GREEN}✓ System packages installed${NC}"

echo ""
echo -e "${GREEN}Step 5: Configuring Wi-Fi access point...${NC}"

echo -e "${BLUE}Setting Wi-Fi country to ${WIFI_COUNTRY}...${NC}"
if command -v raspi-config >/dev/null 2>&1; then
    raspi-config nonint do_wifi_country "$WIFI_COUNTRY" || true
fi
iw reg set "$WIFI_COUNTRY" 2>/dev/null || true
rfkill unblock wifi 2>/dev/null || true

AP_CONFIGURED=0

if systemctl is-active --quiet NetworkManager && command -v nmcli >/dev/null 2>&1; then
    echo -e "${BLUE}NetworkManager detected, creating hotspot...${NC}"
    nmcli connection show "$AP_SSID" &>/dev/null && nmcli connection delete "$AP_SSID"
    if nmcli connection add type wifi ifname wlan0 con-name "$AP_SSID" autoconnect yes ssid "$AP_SSID"; then
        nmcli connection modify "$AP_SSID" \
            802-11-wireless.mode ap \
            802-11-wireless.band bg \
            ipv4.method shared \
            ipv4.addresses "$AP_IP/24" \
            ipv4.gateway "$AP_IP" \
            wifi-sec.key-mgmt wpa-psk \
            wifi-sec.psk "$AP_PSK"
        nmcli connection up "$AP_SSID" || echo -e "${YELLOW}⚠ NetworkManager hotspot created but failed to start; check wlan0 status${NC}"

        # Avoid conflicts with standalone hostapd/dnsmasq when NetworkManager is managing the hotspot
        systemctl stop hostapd dnsmasq 2>/dev/null || true
        systemctl disable hostapd dnsmasq 2>/dev/null || true

        echo -e "${GREEN}✓ Access point configured via NetworkManager (SSID: $AP_SSID)${NC}"
        AP_CONFIGURED=1
    else
        echo -e "${YELLOW}⚠ Failed to configure hotspot via NetworkManager, falling back to hostapd/dnsmasq${NC}"
    fi
fi

if [ "$AP_CONFIGURED" -eq 0 ]; then
    echo -e "${BLUE}Configuring hostapd + dnsmasq for Wi-Fi access point...${NC}"

    # Ensure NetworkManager does not interfere if present
    if systemctl is-active --quiet NetworkManager && command -v nmcli >/dev/null 2>&1; then
        nmcli device set wlan0 managed no 2>/dev/null || true
    fi

    # Static IP for AP interface
    if systemctl list-unit-files | grep -q '^dhcpcd.service'; then
        sed -i '/^# Dashcam AP configuration start$/,/^# Dashcam AP configuration end$/d' /etc/dhcpcd.conf
        cat >> /etc/dhcpcd.conf <<EOF
# Dashcam AP configuration start
interface wlan0
    static ip_address=$AP_IP/24
    nohook wpa_supplicant
# Dashcam AP configuration end
EOF
        systemctl restart dhcpcd 2>/dev/null || true
    else
        mkdir -p /etc/systemd/network
        cat > /etc/systemd/network/08-wlan0-ap.network <<EOF
[Match]
Name=wlan0

[Network]
Address=$AP_IP/24
DHCPServer=no
IPv6AcceptRA=no

[Link]
RequiredForOnline=no
EOF
        systemctl enable systemd-networkd 2>/dev/null || true
        systemctl restart systemd-networkd 2>/dev/null || true
    fi

    # DHCP for clients
    cat > /etc/dnsmasq.d/dashcam-ap.conf <<EOF
interface=wlan0
dhcp-range=$AP_RANGE_START,$AP_RANGE_END,$AP_NETMASK,12h
domain-needed
bogus-priv
EOF

    # hostapd configuration
    cat > /etc/hostapd/hostapd.conf <<EOF
country_code=$WIFI_COUNTRY
interface=wlan0
ssid=$AP_SSID
hw_mode=g
channel=6
ieee80211n=1
ieee80211d=1
wmm_enabled=1
auth_algs=1
wpa=2
wpa_passphrase=$AP_PSK
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
EOF

    if grep -q "^#DAEMON_CONF=" /etc/default/hostapd 2>/dev/null; then
        sed -i 's|^#DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd
    elif ! grep -q "^DAEMON_CONF=" /etc/default/hostapd 2>/dev/null; then
        echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' >> /etc/default/hostapd
    else
        sed -i 's|^DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd
    fi

    systemctl unmask hostapd 2>/dev/null || true
    systemctl stop wpa_supplicant@wlan0.service 2>/dev/null || true
    systemctl disable wpa_supplicant@wlan0.service 2>/dev/null || true

    RESTART_STATUS=0

    if ! systemctl enable hostapd dnsmasq; then
        RESTART_STATUS=1
    fi

    systemctl restart hostapd 2>/dev/null || RESTART_STATUS=1
    systemctl restart dnsmasq 2>/dev/null || RESTART_STATUS=1

    if [ "$RESTART_STATUS" -eq 0 ]; then
        echo -e "${GREEN}✓ Access point configured (SSID: $AP_SSID, PSK: $AP_PSK, IP: $AP_IP)${NC}"
        AP_CONFIGURED=1
    else
        echo -e "${YELLOW}⚠ AP services configured but failed to start; check hostapd/dnsmasq logs${NC}"
    fi
fi

if [ "$AP_CONFIGURED" -eq 0 ]; then
    echo -e "${YELLOW}⚠ Wi-Fi AP setup did not complete successfully${NC}"
fi

echo ""
echo -e "${GREEN}Step 6: Creating directory structure...${NC}"

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
echo -e "${GREEN}Step 7: Cloning repository from GitHub...${NC}"

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
echo -e "${GREEN}Step 8: Setting up Python virtual environment...${NC}"

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
    python-can \
    numba

# Note: Picamera2, numpy, opencv accessed from system packages

echo -e "${GREEN}✓ Virtual environment created and packages installed${NC}"
echo "  Location: $VENV_DIR"

echo ""
echo -e "${GREEN}Step 9: Creating default configuration...${NC}"

# Create a default config file if it doesn't exist
if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    if [ -f "$REPO_DIR/python/dashcam/config.template.yaml" ]; then
        cp "$REPO_DIR/python/dashcam/config.template.yaml" "$CONFIG_DIR/config.yaml"
    else
        echo -e "${YELLOW}⚠ config.template.yaml not found in repository; creating minimal config${NC}"
        cat > "$CONFIG_DIR/config.yaml" << 'EOF'
paths:
  base_dir: /opt/dashcam
  video_dir: /var/opt/dashcam/videos
  current_dir: /var/opt/dashcam/videos/current
  archive_dir: /var/opt/dashcam/videos/archive
  log_dir: /var/opt/dashcam/logs
EOF
    fi

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
echo -e "${GREEN}Step 10: Configuring GPS (GPSD)...${NC}"

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

# Allow the invoking user to access the serial port for GPS
if [ -n "$SUDO_USER" ]; then
    usermod -a -G dialout $SUDO_USER
    echo -e "${GREEN}✓ User added to dialout group${NC}"
fi

echo ""
echo -e "${GREEN}Step 11: Enabling GPS PPS time sync...${NC}"

# Ensure PPS overlay on GPIO 18 is configured
if grep -q "dtoverlay=pps-gpio,gpiopin=18" "$CONFIG_FILE"; then
    echo -e "${GREEN}✓ PPS overlay already configured on GPIO 18${NC}"
elif grep -q "dtoverlay=pps-gpio" "$CONFIG_FILE"; then
    echo -e "${YELLOW}⚠ PPS overlay found with different GPIO, updating to GPIO 18...${NC}"
    sed -i 's/dtoverlay=pps-gpio.*/dtoverlay=pps-gpio,gpiopin=18/' "$CONFIG_FILE"
    echo -e "${GREEN}✓ Updated PPS to GPIO 18${NC}"
else
    echo -e "${BLUE}Adding PPS overlay to config.txt...${NC}"
    if grep -q "enable_uart=1" "$CONFIG_FILE"; then
        sed -i '/enable_uart=1/a\\n# PPS (Pulse Per Second) from GPS via GPIO 18\n# Waveshare LC29H ES HAT - PPS signal on GPIO 18\ndtoverlay=pps-gpio,gpiopin=18' "$CONFIG_FILE"
    else
        sed -i '/# End Active Dash Mirror Configuration/i \\n# PPS (Pulse Per Second) from GPS via GPIO 18\n# Waveshare LC29H ES HAT - PPS signal on GPIO 18\ndtoverlay=pps-gpio,gpiopin=18\n' "$CONFIG_FILE"
    fi
    echo -e "${GREEN}✓ PPS overlay added to config.txt${NC}"
fi

# Ensure pps-gpio loads at boot
if ! grep -q "^pps-gpio$" /etc/modules; then
    echo "pps-gpio" >> /etc/modules
    echo -e "${GREEN}✓ pps-gpio added to /etc/modules${NC}"
else
    echo -e "${GREEN}✓ pps-gpio already in /etc/modules${NC}"
fi

# Install tools needed for PPS verification (if not already installed)
apt-get install -y pps-tools lsof >/dev/null

# Configure chrony for GPS + PPS
mkdir -p /etc/chrony/conf.d
cat > /etc/chrony/conf.d/gps.conf << 'CHRONYEOF'
# GPS Time Reference via GPSD shared memory
refclock SHM 0 refid GPS precision 1e-1 poll 4 minsamples 3

# PPS (Pulse Per Second) for high-precision time
refclock PPS /dev/pps0 refid PPS precision 1e-7 lock GPS
CHRONYEOF

if ! grep -q "confdir /etc/chrony/conf.d" /etc/chrony/chrony.conf; then
    echo -e "${BLUE}Adding conf.d include to chrony.conf...${NC}"
    {
        echo ""
        echo "# Include configuration files from conf.d"
        echo "confdir /etc/chrony/conf.d"
    } >> /etc/chrony/chrony.conf
    echo -e "${GREEN}✓ Chrony conf.d include added${NC}"
else
    echo -e "${GREEN}✓ Chrony conf.d already configured${NC}"
fi

systemctl enable chrony

# GPS/PPS status helper
cat > /usr/local/bin/dashcam-gps-status << 'GPSSTATUSEOF'
#!/bin/bash
# Check GPS and time sync status

echo "=========================================="
echo "  GPS and Time Sync Status"
echo "=========================================="
echo ""

echo "1. GPS Fix Status:"
echo "----------------------------"
if command -v cgps &> /dev/null; then
    timeout 3 cgps -s 2>&1 | grep -E "Status|Sats|Time|Latitude|Longitude" || echo "GPS not responding"
else
    echo "cgps not installed"
fi
echo ""

echo "2. GPSD Service:"
echo "----------------------------"
systemctl is-active gpsd && echo "✓ GPSD running" || echo "✗ GPSD not running"
echo ""

echo "3. PPS Hardware:"
echo "----------------------------"
if [ -e /dev/pps0 ]; then
    echo "✓ /dev/pps0 exists"
    ls -l /dev/pps0
    
    if lsmod | grep -q pps_gpio; then
        echo "✓ pps-gpio module loaded"
    else
        echo "✗ pps-gpio module NOT loaded (reboot required)"
    fi
    
    echo ""
    echo "Testing PPS signal (3 seconds)..."
    if timeout 3 sudo ppstest /dev/pps0 2>&1 | grep -q "assert.*sequence"; then
        echo "✓ PPS pulses detected!"
        timeout 3 sudo ppstest /dev/pps0 2>&1 | head -5
    else
        echo "✗ No PPS signals (GPS may need fix or reboot required)"
    fi
else
    echo "✗ /dev/pps0 does not exist (reboot required)"
fi
echo ""

echo "4. Chrony Time Sources:"
echo "----------------------------"
chronyc sources
echo ""

echo "5. Chrony Tracking:"
echo "----------------------------"
chronyc tracking | grep -E "Reference|Stratum|System time|Last offset"
echo ""

echo "6. Shared Memory (GPSD -> Chrony):"
echo "----------------------------"
if ipcs -m | grep -q 0x4e54; then
    echo "✓ GPSD shared memory segments found"
    ipcs -m | grep 0x4e54 | head -3
else
    echo "✗ No GPSD shared memory (GPSD may not be running)"
fi
echo ""

echo "=========================================="
echo "Legend:"
echo "  Chrony sources status:"
echo "    #* GPS/PPS = Currently selected"
echo "    #+ GPS/PPS = Combined with selected"
echo "    #? GPS/PPS = Unreachable or validating"
echo "    #x GPS/PPS = False ticker (rejected)"
echo ""
echo "  For best results:"
echo "    - GPS should have 3D fix"
echo "    - PPS should show pulses"
echo "    - Chrony should show GPS/PPS as sources"
echo "    - System time offset should be < 1ms"
echo "=========================================="
GPSSTATUSEOF

chmod +x /usr/local/bin/dashcam-gps-status

echo -e "${GREEN}✓ GPS PPS time sync configured${NC}"
echo "  - PPS overlay on GPIO 18"
echo "  - Chrony configured with GPS + PPS"
echo "  - Status script: dashcam-gps-status"

echo ""
echo -e "${GREEN}Step 12: Configuring CAN bus...${NC}"

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
echo -e "${GREEN}Step 13: Creating systemd service...${NC}"

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
echo -e "${GREEN}Step 14: Disabling screen blanking...${NC}"

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
echo -e "${GREEN}Step 15: Configuring framebuffer permissions...${NC}"

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
echo -e "${GREEN}Step 16: Setting boot order for NVMe...${NC}"

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
echo -e "${GREEN}Step 17: Creating convenience scripts...${NC}"

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
echo "  dashcam-gps-status   - Check GPS/PPS time sync"

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
echo "  ✓ Wi-Fi access point ready for transfers (SSID: $AP_SSID, PSK: $AP_PSK, IP: $AP_IP)"
echo "  ✓ GPS configured (LC29H on serial port) with PPS + chrony time sync"
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
echo "  2. Connect to the dashcam Wi-Fi for transfers (SSID: $AP_SSID, PSK: $AP_PSK, IP: $AP_IP)"
echo "     ssh $SUDO_USER@$AP_IP"
echo "     sftp $SUDO_USER@$AP_IP"
echo ""
echo "  3. After reboot, test cameras:"
echo "     dashcam-test-cameras"
echo ""
echo "  4. Check system status:"
echo "     dashcam-status"
echo ""
echo "  5. Edit configuration:"
echo "     sudo nano $CONFIG_DIR/config.yaml"
echo ""
echo "  6. Verify GPS/PPS time sync:"
echo "     dashcam-gps-status"
echo ""
echo "  7. Service management:"
echo "     sudo systemctl start dashcam   # Start"
echo "     sudo systemctl stop dashcam    # Stop"
echo "     sudo systemctl status dashcam  # Check status"
echo "     sudo systemctl restart dashcam # Restart"
echo "     journalctl -u dashcam -f       # View logs"
echo ""
echo "  8. Update software:"
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
