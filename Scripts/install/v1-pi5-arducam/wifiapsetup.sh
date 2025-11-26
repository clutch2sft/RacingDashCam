#!/bin/bash
# Standalone Wi-Fi AP setup for existing installations
# Configures wlan0 as an access point with DHCP for file transfer access.

set -e

# Defaults (override via env: WIFI_COUNTRY, AP_SSID, AP_PSK, AP_IP, AP_RANGE_START, AP_RANGE_END, AP_NETMASK)
WIFI_COUNTRY="${WIFI_COUNTRY:-US}"
AP_SSID="${AP_SSID:-dashcamxfer}"
AP_PSK="${AP_PSK:-changeme}"
AP_IP="${AP_IP:-10.42.0.1}"
AP_RANGE_START="${AP_RANGE_START:-10.42.0.50}"
AP_RANGE_END="${AP_RANGE_END:-10.42.0.150}"
AP_NETMASK="${AP_NETMASK:-255.255.255.0}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}ERROR: Please run as root (sudo).${NC}"
    exit 1
fi

echo -e "${BLUE}=== Wi-Fi Access Point Setup (wlan0) ===${NC}"
echo "Country: $WIFI_COUNTRY"
echo "SSID:    $AP_SSID"
echo "PSK:     $AP_PSK"
echo "IP:      $AP_IP ($AP_RANGE_START-$AP_RANGE_END)"
echo ""

echo -e "${GREEN}Step 1: Installing required packages...${NC}"
apt-get update
apt-get install -y hostapd dnsmasq iw rfkill

echo -e "${GREEN}Step 2: Setting regulatory domain...${NC}"
if command -v raspi-config >/dev/null 2>&1; then
    raspi-config nonint do_wifi_country "$WIFI_COUNTRY" || true
fi
iw reg set "$WIFI_COUNTRY" 2>/dev/null || true
rfkill unblock wifi 2>/dev/null || true

AP_CONFIGURED=0

if systemctl is-active --quiet NetworkManager && command -v nmcli >/dev/null 2>&1; then
    echo -e "${BLUE}NetworkManager detected; creating hotspot...${NC}"
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
        nmcli connection up "$AP_SSID" || echo -e "${YELLOW}⚠ NM hotspot created but failed to start; check wlan0 status${NC}"
        systemctl stop hostapd dnsmasq 2>/dev/null || true
        systemctl disable hostapd dnsmasq 2>/dev/null || true
        AP_CONFIGURED=1
        echo -e "${GREEN}✓ Access point configured via NetworkManager${NC}"
    else
        echo -e "${YELLOW}⚠ NetworkManager setup failed; falling back to hostapd/dnsmasq${NC}"
    fi
fi

if [ "$AP_CONFIGURED" -eq 0 ]; then
    echo -e "${BLUE}Configuring hostapd + dnsmasq...${NC}"

    if systemctl is-active --quiet NetworkManager && command -v nmcli >/dev/null 2>&1; then
        nmcli device set wlan0 managed no 2>/dev/null || true
    fi

    # Static IP for wlan0 (dhcpcd path preferred on Raspberry Pi OS)
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

    # hostapd config
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
    systemctl enable hostapd dnsmasq 2>/dev/null || RESTART_STATUS=1
    systemctl restart hostapd 2>/dev/null || RESTART_STATUS=1
    systemctl restart dnsmasq 2>/dev/null || RESTART_STATUS=1

    if [ "$RESTART_STATUS" -eq 0 ]; then
        AP_CONFIGURED=1
        echo -e "${GREEN}✓ Access point configured (SSID: $AP_SSID, PSK: $AP_PSK, IP: $AP_IP)${NC}"
    else
        echo -e "${YELLOW}⚠ AP services configured but failed to start; check hostapd/dnsmasq logs${NC}"
    fi
fi

echo ""
if [ "$AP_CONFIGURED" -eq 1 ]; then
    echo -e "${GREEN}Done. Connect to SSID '$AP_SSID' with PSK '$AP_PSK' and SSH/SFTP to $AP_IP.${NC}"
else
    echo -e "${YELLOW}AP setup did not complete successfully.${NC}"
fi
