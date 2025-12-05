#!/usr/bin/env python3
"""
Standalone GPIO-based power loss monitor for Raspberry Pi.

- Uses a pull-up on the configured BCM pin and treats a transition from LOW->HIGH
  as a power-loss signal (active-low input from an external detection circuit).
- Confirms the signal stays HIGH after a short debounce window before issuing a
  shutdown command.
- Intended to run under systemd and remain independent of the dashcam process.
"""
import logging
import os
import shlex
import signal
import subprocess
import sys
import time

try:
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError) as exc:
    sys.stderr.write(f"Failed to import RPi.GPIO (run as root? missing package?): {exc}\n")
    sys.exit(1)


LOG_LEVEL = os.getenv("POWER_MONITOR_LOG_LEVEL", "INFO").upper()
POWER_GPIO_PIN = int(os.getenv("POWER_MONITOR_GPIO", "25"))  # Default BCM25 (pin 22)
DEBOUNCE_CONFIRM_SEC = float(os.getenv("POWER_MONITOR_CONFIRM_SEC", "1.0"))
BOUNCE_TIME_MS = int(os.getenv("POWER_MONITOR_BOUNCE_MS", "200"))
SHUTDOWN_CMD = shlex.split(os.getenv("POWER_MONITOR_SHUTDOWN_CMD", "shutdown -h now"))

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOGGER = logging.getLogger("power-monitor")

shutdown_requested = False


def _request_shutdown() -> None:
    """Invoke the shutdown command."""
    global shutdown_requested
    if shutdown_requested:
        LOGGER.debug("Shutdown already requested; ignoring duplicate trigger.")
        return

    shutdown_requested = True
    LOGGER.warning(
        "Power loss confirmed on BCM%s; executing shutdown command: %s",
        POWER_GPIO_PIN,
        " ".join(SHUTDOWN_CMD),
    )
    try:
        subprocess.run(SHUTDOWN_CMD, check=True)
    except subprocess.CalledProcessError as exc:
        LOGGER.error("Shutdown command failed: %s", exc)
    except Exception:  # noqa: BLE001
        LOGGER.exception("Unexpected error running shutdown command")


def handle_power_loss(channel: int) -> None:
    """Debounce the rising edge and request shutdown if power remains bad."""
    LOGGER.info("Power-loss edge detected on BCM%s; waiting %.2fs to confirm", POWER_GPIO_PIN, DEBOUNCE_CONFIRM_SEC)
    time.sleep(DEBOUNCE_CONFIRM_SEC)
    if GPIO.input(POWER_GPIO_PIN) == GPIO.HIGH:
        _request_shutdown()
    else:
        LOGGER.info("Power restored before debounce window elapsed; skipping shutdown.")


def _cleanup(signum=None, frame=None) -> None:  # noqa: ANN001
    """Cleanup GPIO state on exit."""
    LOGGER.info("Stopping power monitor (signal: %s). Cleaning up GPIO.", signum)
    GPIO.cleanup()
    sys.exit(0)


def main() -> None:
    LOGGER.info(
        "Starting power monitor on BCM%s (debounce %.2fs, bouncetime %sms)",
        POWER_GPIO_PIN,
        DEBOUNCE_CONFIRM_SEC,
        BOUNCE_TIME_MS,
    )
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(POWER_GPIO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(POWER_GPIO_PIN, GPIO.RISING, callback=handle_power_loss, bouncetime=BOUNCE_TIME_MS)

    signal.signal(signal.SIGTERM, _cleanup)
    signal.signal(signal.SIGINT, _cleanup)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        _cleanup()


if __name__ == "__main__":
    main()
