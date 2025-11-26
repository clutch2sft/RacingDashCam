# GPS Time Synchronization Guide

> Chrony-based GPS/PPS time sync is configured system-wide by `dashcam_install.sh`. The dashcam application no longer sets system time itself or exposes `gps_time_sync_*` settings.

## Overview

- Chrony disciplines system time using GPS/PPS (via gpsd) plus NTP servers.
- The dashcam consumes GPS data for overlays/metadata; timestamps rely on chrony.
- PPS on GPIO 18 (Waveshare LC29H) is enabled in the installer for higher precision when hardware is present.

## Architecture

```
LC29H GPS Module
    ↓ (UART: /dev/ttyAMA0)
GPSD Daemon
    ↓ (Shared Memory/PPS)
Chrony (Reference Clock)
    ↓
System Time
    ↓
Dashcam Application & Video Timestamps
```

## Verification Checklist

```bash
sudo systemctl status gpsd
sudo systemctl status chrony
timedatectl status            # Expect "NTP service: chronyd"

chronyc sources               # Look for GPS/PPS rows
chronyc tracking              # Check stratum/offset

sudo ppstest /dev/pps0        # PPS pulses every second
gpspipe -w -n 5               # Confirm GPS sentences flowing
```

## Troubleshooting

| Issue | What to Check |
|-------|---------------|
| No GPS data | `gpspipe -w -n 5`; antenna placement; gpsd status |
| Chrony missing GPS/PPS | `chronyc sources`; ensure `/etc/chrony/conf.d/gps.conf` exists |
| PPS not detected | `sudo ppstest /dev/pps0`; confirm `pps-gpio` module loaded |
| Services failing | `journalctl -u gpsd -f`; `journalctl -u chrony -f` |

## Impact on Videos

- Video timestamps use chrony-disciplined system time.
- GPS coordinates and speed remain available for overlays and metadata.
- PPS improves accuracy when hardware is present and locked.
