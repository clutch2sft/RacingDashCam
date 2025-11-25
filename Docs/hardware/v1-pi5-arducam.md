# v1 Hardware Platform - Pi5 + Arducam HQ

## Overview

First-generation hardware platform using off-the-shelf components.

## Hardware Components

### Core
* **Raspberry Pi 5** (8GB recommended)
* **Pimoroni NVMe Base**
* **NVMe M.2 SSD** (512GB recommended)
* **Official 27W USB-C Power Supply**

### Cameras
* **2x Arducam 12.3MP HQ Camera** (IMX477 sensor)
  * Front: Standard lens
  * Rear: 158° wide angle M12 lens
* Connection: CSI (CAM0 and CAM1)

### Vehicle Interface
* **Waveshare 2-CH CAN HAT Plus**
  * Dual MCP2515 CAN controllers
  * SN65HVD230 transceivers
* Connection: GPIO 40-pin header

### GPS
* **LC29H Dual-band GPS Module**
* Connection: UART (GPIO 14/15)

### Display
* **LILLIPUT 7" 1000 Nits Display** (or similar)
* Connection: HDMI0

## Specifications

**Video Recording:**
* Resolution: 1920x1080 per camera
* Frame rate: 30 fps
* Codec: H.264 (hardware accelerated)
* Bitrate: 8 Mbps per camera (configurable)

**Storage:**
* Sequential write: 700-900 MB/s (PCIe Gen 3)
* Simultaneous dual camera: ~16 Mbps = ~2 MB/s (well within capacity)

**Performance:**
* Boot time: ~15-20 seconds
* Display latency: 10-15ms glass-to-glass
* CPU usage: 30-40% (distributed)
* Power consumption: 12-15W (with display)

## Bill of Materials

| Item | Quantity | Cost (USD) |
|------|----------|-----------|
| Raspberry Pi 5 (8GB) | 1 | $80 |
| Pimoroni NVMe Base | 1 | $15 |
| NVMe SSD (512GB) | 1 | $50 |
| Arducam HQ Camera | 2 | $70 x 2 = $140 |
| Wide angle lens | 1 | $35 |
| Waveshare 2-CH CAN HAT | 1 | $28 |
| LC29H GPS Module | 1 | $65 |
| LILLIPUT Display | 1 | $250 |
| 27W Power Supply | 1 | $12 |
| **Total** | | **~$675** |

## Pin Assignments

### GPIO Usage
* **GPIO 14 (TX)**: GPS RX
* **GPIO 15 (RX)**: GPS TX
* **GPIO 24**: CAN1 Interrupt
* **GPIO 25**: CAN0 Interrupt
* **SPI**: CAN HAT (MCP2515)
* **I2C**: Camera control

### Camera Ports
* **CAM0** (closer to USB-C): Front camera
* **CAM1** (closer to HDMI): Rear camera

### CAN Bus
* **CAN0**: Vehicle OBD-II connection
* **CAN1**: Available for expansion

## Known Limitations

1. **Temperature**: Can reach 65-70°C under load
   * Solution: Add Active Cooler
2. **Power**: Requires stable 27W supply
   * Insufficient power causes crashes
3. **Camera cables**: FFC cables can be fragile
   * Use care when connecting

## Tested Configurations

✅ **Working:**
* Samsung 980 NVMe
* WD Black SN750 NVMe
* Crucial P3 NVMe
* PCIe Gen 3 enabled
* Dual camera 1080p@30fps
* CAN at 500 kbps
* GPS at 1 Hz update

❌ **Not Working:**
* Cheap no-name NVMe drives (compatibility issues)
* Non-official power supplies (causes instability)

## Future Improvements

Potential v2 hardware changes:
* Custom camera board (reduce cables)
* Integrated CAN transceiver
* Better thermal management
* Smaller form factor

## Installation

See [SETUP_GUIDE.md](../SETUP_GUIDE.md) for complete installation instructions.

Installation script: `Scripts/install/v1-pi5-arducam/dashcam_install.sh`

---

**Version 1 Platform** - Proven, reliable, off-the-shelf components
