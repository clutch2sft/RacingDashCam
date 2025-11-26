# GPS Time Sync - Quick Reference

> Note: Chrony-based GPS/PPS time sync is now configured system-wide by `dashcam_install.sh`. The dashcam application no longer adjusts system time directly or uses `gps_time_sync_*` settings.

## What You Have

- **GPS Module**: LC29H on `/dev/ttyAMA0` @ 115200 baud
- **NTP Service**: Chrony (for continuous GPS/PPS + NTP correction)
- **Time Sync**: Continuous via chrony (no in-app time setting)

## Check Status

```bash
# GPS status
timedatectl status           # Shows "NTP service: chronyd"
chronyc tracking             # Time sync quality
chronyc sources              # See GPS as time source
gpspipe -w -n 5              # Raw GPS data

# Dashcam status
sudo systemctl status dashcam
journalctl -u dashcam -f | grep GPS
```

## Manual Checks

```bash
# Chrony service + sources
sudo systemctl status chrony
chronyc sources
chronyc tracking

# PPS signal sanity check
sudo ppstest /dev/pps0
```

## Troubleshooting

| Issue | Check |
|-------|-------|
| GPS data missing | `gpspipe -w -n 5` - is GPS data flowing? |
| Chrony missing GPS/PPS | `chronyc sources` - do you see GPS/PPS entries? |
| PPS not detected | `sudo ppstest /dev/pps0` - pulses every second? |
| Service issues | `journalctl -u chrony -f`, `journalctl -u gpsd -f` |

## Logs

```bash
# Dashcam logs
journalctl -u dashcam -f

# Chrony activity
chronyc activity
```

## Video Impact

✅ System time is disciplined by chrony (GPS/PPS + NTP)  
✅ Video timestamps use that disciplined system clock  
✅ GPS coordinates and speed in video overlays  
✅ PPS provides sub-millisecond accuracy when available

## More Info

See: `Docs/GPS_TIME_SYNC_GUIDE.md` for complete documentation
