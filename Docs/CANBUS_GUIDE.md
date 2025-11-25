# CAN Bus Integration for Active Dash Mirror

## Hardware: Waveshare 2-CH CAN HAT Plus

The Waveshare 2-CH CAN HAT Plus provides dual MCP2515 CAN controllers connected via SPI.

### Hardware Specifications:
- **Controller**: MCP2515 CAN controller (x2)
- **Transceiver**: SN65HVD230 CAN transceiver (x2)
- **Oscillator**: 12MHz
- **Interface**: SPI
- **Channels**: can0 and can1
- **Interrupts**: GPIO25 (can0), GPIO24 (can1)

### Pin Connections:
- **CAN0**: GPIO25 (interrupt)
- **CAN1**: GPIO24 (interrupt)
- **SPI**: Standard Raspberry Pi SPI pins

## Software Components

### 1. `canbus.py` - Base CAN Interface
Core CAN bus functionality:
- Message sending/receiving
- Callback registration for specific CAN IDs
- Hardware filtering
- Statistics and monitoring
- Thread-safe operation

### 2. `camaro_canbus.py` - Vehicle-Specific Implementation
Camaro LFX (2013) specific implementation:
- GM HS-CAN protocol (500 kbps)
- Engine RPM and speed
- Coolant temperature
- Throttle position
- Fuel level
- Battery voltage
- Transmission gear
- Diagnostic codes

### 3. Integration with Dashcam System
See `canbus_integration_example.py` for examples of:
- Basic integration
- Conditional recording based on engine state
- CAN data logging to CSV
- Debug monitoring

## Installation

### Automatic (via install script):
```bash
sudo ./dashcam_install.sh
```

The install script will:
1. Configure device tree overlays for both CAN channels
2. Install `can-utils` package
3. Install `python-can` library
4. Create systemd service to bring up CAN interfaces at boot
5. Configure both CAN0 and CAN1 at 500 kbps

### Manual Installation:

1. **Update config.txt** (`/boot/firmware/config.txt`):
```
dtparam=spi=on
dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000
dtoverlay=mcp2515-can1,oscillator=12000000,interrupt=24,spimaxfrequency=2000000
```

2. **Install packages**:
```bash
sudo apt install can-utils
pip install python-can
```

3. **Bring up CAN interfaces**:
```bash
sudo ip link set can0 type can bitrate 500000
sudo ip link set can0 up

sudo ip link set can1 type can bitrate 500000
sudo ip link set can1 up
```

4. **Reboot**:
```bash
sudo reboot
```

## Testing CAN Bus

### Check Interface Status:
```bash
ip link show can0
ip link show can1
```

Expected output:
```
3: can0: <NOARP,UP,LOWER_UP,ECHO> mtu 16 qdisc pfifo_fast state UP mode DEFAULT group default qlen 10
    link/can
```

### Monitor CAN Traffic:
```bash
# Monitor all messages on can0
candump can0

# Monitor with timestamp
candump -t a can0

# Monitor specific ID
candump can0,0C9:7FF
```

### Send Test Message:
```bash
# Send message with ID 0x123 and data bytes
cansend can0 123#DEADBEEF
```

### CAN Statistics:
```bash
ip -details -statistics link show can0
```

## 2013 Camaro LFX CAN Message IDs

These are **starting point** IDs based on common GM HS-CAN protocol. Your vehicle may use different IDs. Use `candump can0` to identify actual IDs.

### Engine Data:
- **0x0C9**: Engine RPM and Vehicle Speed
- **0x0F1**: Coolant Temperature  
- **0x110**: Throttle Position, MAP, IAT

### Transmission:
- **0x1E9**: Current Gear

### Fuel:
- **0x3D1**: Fuel Level, Flow Rate

### Electrical:
- **0x4C1**: Battery Voltage, MIL Status

## Usage in Python

### Basic Example:
```python
from config import config
from camaro_canbus import CamaroCANBus, CANChannel

# Create instance
canbus = CamaroCANBus(config, channel=CANChannel.CAN0)

# Start
if canbus.start():
    print("CAN bus started")
    
    # Get vehicle data
    data = canbus.get_vehicle_data()
    print(f"RPM: {data.rpm}")
    print(f"Speed: {canbus.get_speed_mph()} mph")
    print(f"Coolant: {canbus.get_coolant_temp_f()}°F")
    
    # Check if engine running
    if canbus.is_engine_running():
        print("Engine is running")
    
    # Stop when done
    canbus.stop()
```

### Debug Mode:
```python
# Enable debug logging to see all CAN messages
monitor = canbus.enable_debug_logging()

# Let it run for a while...
time.sleep(60)

# Print summary
monitor.print_summary()
```

## Identifying Your Vehicle's CAN IDs

Every vehicle is different. To find your specific CAN message IDs:

1. **Monitor CAN traffic while driving**:
```bash
candump -l can0
```

2. **Look for patterns**:
   - RPM: Changes with engine speed
   - Speed: Changes with vehicle speed
   - Throttle: Changes when you press gas pedal
   - Coolant: Changes slowly as engine warms up

3. **Update `camaro_canbus.py`** with your IDs:
```python
MSG_ENGINE_RPM_SPEED = 0x0C9  # Change to your ID
MSG_ENGINE_COOLANT = 0x0F1    # Change to your ID
# ... etc
```

4. **Update message parsing** if data format is different.

## Configuration Options

In `config.py`:

```python
# Enable/disable CAN bus
self.canbus_enabled = True

# CAN channel (can0 or can1)
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

## Troubleshooting

### CAN interface not appearing:
```bash
# Check device tree overlays loaded
dtoverlay -l

# Should see mcp2515-can0 and mcp2515-can1
```

### No CAN messages received:
1. Check physical connections to vehicle OBD-II port:
   - CAN-H (Pin 6)
   - CAN-L (Pin 14)
   - Ground (Pin 4 or 5)
   
2. Verify bitrate matches vehicle (usually 500k for GM)

3. Check if vehicle CAN bus is active (engine running)

4. Try both CAN0 and CAN1 channels

### Permission denied:
```bash
# Add user to necessary groups (already done by install script)
sudo usermod -a -G dialout pi
```

## Creating Vehicle-Specific Implementations

To add support for another vehicle:

1. Copy `camaro_canbus.py` to `[your_vehicle]_canbus.py`

2. Update CAN message IDs for your vehicle

3. Update message parsing based on your vehicle's data format

4. Update `config.py`:
```python
self.canbus_vehicle_type = "your_vehicle_name"
```

5. Import in `dashcam.py`:
```python
from your_vehicle_canbus import YourVehicleCANBus
```

## References

- [Waveshare 2-CH CAN HAT Wiki](https://www.waveshare.com/wiki/2-CH_CAN_HAT)
- [MCP2515 Datasheet](http://ww1.microchip.com/downloads/en/DeviceDoc/MCP2515-Stand-Alone-CAN-Controller-with-SPI-20001801J.pdf)
- [python-can Documentation](https://python-can.readthedocs.io/)
- [GM CAN Bus Information](https://www.gm-efi.com/support/gm-canbus/)

## Safety Warning

⚠️ **IMPORTANT**: 
- Do NOT send CAN messages to your vehicle without knowing what they do
- Incorrect CAN messages can damage vehicle systems
- Use read-only mode for dashcam purposes
- Consult vehicle service manual before attempting to send CAN commands
- Test thoroughly before using in your primary vehicle