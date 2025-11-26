# GPS Time Sync - Quick Reference

## What You Have

- **GPS Module**: LC29H on `/dev/ttyAMA0` @ 115200 baud
- **NTP Service**: Chrony (for continuous time correction)
- **Time Sync**: Automatic on startup + every 5 minutes

## Check Status

```bash
# GPS status
timedatectl status           # Shows "NTP service: chronyd"
chronyc tracking             # Time sync quality
chronyc sources              # See GPS as time source
gpspipe -w -n 5              # Raw GPS data

# Dashcam status
sudo systemctl status dashcam
journalctl -u dashcam -f | grep "GPS time sync"
```

## Manual Time Sync

```bash
# Get current GPS time
gpspipe -w -n 1 | grep GPRMC

# Set manually
sudo timedatectl set-time "2025-11-26 14:30:45"
```

## Enable/Disable

In `/home/greggc/RacingDashCam/python/dashcam/core/config.py`:

```python
self.gps_time_sync_enabled = True        # Disable if not needed
self.gps_time_sync_on_startup = True     # Don't sync on startup
self.gps_time_sync_update_interval = 300 # Sync interval (seconds)
```

## Troubleshooting

| Issue | Check |
|-------|-------|
| GPS not syncing | `gpspipe -w -n 5` - is GPS data flowing? |
| Chrony not using GPS | `chronyc sources` - does it list GPS? |
| Time keeps drifting | `chronyc tracking` - check sync quality |
| Sync errors in logs | `journalctl -u dashcam -f` |

## Logs

```bash
# Dashcam GPS sync events
tail -f /var/opt/dashcam/logs/dashcam_$(date +%Y%m%d).log | grep "GPS time"

# Full dashcam logs with timestamps
journalctl -u dashcam -f

# Chrony status
sudo systemctl status chrony
chronyc activity
```

## Advanced: PPS (Optional)

For microsecond-level accuracy, wire GPS PPS output to GPIO 27:

```python
# In config.py:
self.gps_pps_enabled = True
self.gps_pps_gpio = 27

# Then run:
sudo modprobe pps-gpio
sudo ppstest /dev/pps0
```

## Video Impact

✅ All video recordings automatically use synced system time
✅ Timestamps accurate to ~50ms (without PPS) or ~1μs (with PPS)
✅ GPS coordinates and speed in video overlays
✅ Metadata embedded in video files

## More Info

See: `Docs/GPS_TIME_SYNC_GUIDE.md` for complete documentation
