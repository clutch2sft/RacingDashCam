# v1 Hardware Platform - Pi5 + Arducam HQ

## Overview

First-generation hardware platform using off-the-shelf components for a dual-camera dash mirror with CAN and GPS integration on a Raspberry Pi 5.

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
* Electrical interface:
  * **SPI0** (MCP2515):
    * MISO0: GPIO9
    * MOSI0: GPIO10
    * SCLK0: GPIO11
    * CE0 (CAN0 CS): GPIO8
    * CE1 (CAN1 CS): GPIO7
  * **Interrupts:**
    * CAN0 INT: GPIO22
    * CAN1 INT: GPIO13

### GPS
* **LC29H Dual-band GPS Module**
* Connection:
  * UART (GPIO 14/15 for TX/RX)
  * PPS on GPIO18

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
* Sequential write: 700–900 MB/s (PCIe Gen 3)
* Simultaneous dual camera: ~16 Mbps = ~2 MB/s (well within capacity)

**Performance:**
* Boot time: ~15–20 seconds
* Display latency: 10–15 ms glass-to-glass
* CPU usage: 30–40% (distributed)
* Power consumption: 12–15 W (with display)

## Bill of Materials

| Item | Quantity | Cost (USD) |
|------|----------|-----------|
| Raspberry Pi 5 (8GB) | 1 | $80 |
| Pimoroni NVMe Base | 1 | $15 |
| NVMe SSD (512GB) | 1 | $50 |
| Arducam HQ Camera | 2 | $70 × 2 = $140 |
| Wide angle lens | 1 | $35 |
| Waveshare 2-CH CAN HAT Plus | 1 | $28 |
| LC29H GPS Module | 1 | $65 |
| LILLIPUT Display | 1 | $250 |
| 27W Power Supply | 1 | $12 |
| **Total** | | **~$675** |

## Pin Assignments

### GPIO Usage

**Serial / GPS**
* **GPIO14 (TXD0)**: GPS RX
* **GPIO15 (RXD0)**: GPS TX
* **GPIO18**: GPS PPS input

**CAN HAT (Waveshare 2-CH CAN HAT Plus)**
* **SPI0 (MCP2515)**  
  * MISO0: GPIO9  
  * MOSI0: GPIO10  
  * SCLK0: GPIO11  
* **Chip Selects**  
  * CAN0 CS: GPIO8 (SPI0 CE0)  
  * CAN1 CS: GPIO7 (SPI0 CE1)  
* **Interrupts**  
  * CAN0 INT: GPIO22  
  * CAN1 INT: GPIO13  

**Other**
* **I2C**: Reserved for camera control / ancillary sensors
* Remaining GPIOs are left available for future expansion (buttons, LEDs, etc.)

### Camera Ports
* **CAM0** (closer to USB-C): Front camera
* **CAM1** (closer to HDMI): Rear camera

### CAN Bus
* **CAN0**: Primary vehicle HS-CAN (e.g., connection into OBD-II / backbone)
* **CAN1**: Available for expansion (additional modules, secondary vehicle network, or development use)

## Known Limitations

1. **Temperature**: Can reach 65–70°C under load  
   * Recommended: active cooling on the Raspberry Pi 5 (fan or active heatsink).
2. **Power**: Requires a stable 27 W supply  
   * Insufficient power (especially in-vehicle) can cause SD/NVMe errors and crashes.
3. **Camera cables**: FFC cables are fragile  
   * Use care when connecting/disconnecting and provide strain relief in the enclosure.
4. **GPIO resource sharing**:  
   * PPS uses **GPIO18**.  
   * CAN is deliberately placed on **SPI0** to avoid conflicts with SPI1 chip-select pins on the Pi 5 RP1 (SPI1 CS0 is also GPIO18). Any future use of SPI1 must take that into account.

## Tested Configurations

✅ **Working:**
* Samsung 980 NVMe  
* WD Black SN750 NVMe  
* Crucial P3 NVMe  
* PCIe Gen 3 enabled  
* Dual camera 1080p@30fps  
* CAN at 500 kbps (both channels available)  
* GPS at 1 Hz update with PPS on GPIO18  

❌ **Not Working / Not Recommended:**
* Cheap no-name NVMe drives (compatibility and stability issues)
* Non-official or undersized power supplies (causes instability, throttling, or crashes)

## Future Improvements

Potential v2 hardware changes:
* Custom camera board (reduced cable clutter)
* Integrated CAN transceivers and cleaner vehicle connector
* Improved thermal management and ducted cooling
* Smaller enclosure and better automotive mounting options

## Installation

See [SETUP_GUIDE.md](../SETUP_GUIDE.md) for complete installation instructions.

Installation script: `Scripts/install/v1-pi5-arducam/dashcam_install.sh`  
(Installs the CAN configuration using `mcp2515-can0` and `mcp2515-can1` on **SPI0** with interrupts on GPIO22 and GPIO13.)
