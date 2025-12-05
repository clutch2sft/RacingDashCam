# Power Loss Monitor Service

Standalone GPIO watcher that requests a clean shutdown when the external 12 V detection circuit releases (goes HIGH) on a Raspberry Pi GPIO input. The service is independent of the dashcam process and runs from the dashcam venv.

## Hardware
- Default pin: **BCM25** (header pin 22) with an internal pull-up. The detection circuit should pull the line **LOW** while power is good and let it float HIGH on loss (active-low).
- Supercapacitor on the 12 V side should provide enough runtime for the shutdown to complete after the trigger.

## Service files
- Script: `python/scripts/power_monitor.py` (install to `/opt/dashcam/PowerMonitor/power_monitor.py`).
- Unit file: `systemd/power-monitor.service` (install to `/etc/systemd/system/power-monitor.service`).

## Install
```bash
sudo mkdir -p /opt/dashcam/PowerMonitor
sudo install -m 755 python/scripts/power_monitor.py /opt/dashcam/PowerMonitor/power_monitor.py
sudo install -m 644 systemd/power-monitor.service /etc/systemd/system/power-monitor.service
sudo systemctl daemon-reload
sudo systemctl enable --now power-monitor.service
```

## Configuration
Environment variables (set in the unit file if needed):
- `POWER_MONITOR_GPIO` (default `25`): BCM pin to monitor.
- `POWER_MONITOR_CONFIRM_SEC` (default `1.0`): Debounce confirmation delay before shutdown.
- `POWER_MONITOR_BOUNCE_MS` (default `200`): Edge detection debounce.
- `POWER_MONITOR_SHUTDOWN_CMD` (default `shutdown -h now`): Command to run on confirmed power loss (runs inside `/opt/dashcam/venv` Python).

After editing the unit file, run `sudo systemctl daemon-reload` and restart the service: `sudo systemctl restart power-monitor.service`.

## Status & logs
- Check status: `systemctl status power-monitor.service`
- View logs: `journalctl -u power-monitor.service -f`
