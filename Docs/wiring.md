# Wiring Overview

Raspberry Pi 40-pin header usage for the dashcam stack (Pi 5 + dual MCP2515 CAN + LC29H GPS). Includes a suggested spare input for vehicle-running detection via dry relay contacts.

## Pin Use Summary

| Function              | GPIO  | Header Pin | Notes                             |
|-----------------------|-------|------------|-----------------------------------|
| 3V3 / 5V / GND        | —     | misc       | Power and ground rails            |
| GPS UART TX (Pi RX)   | GPIO15| 10         | From GPS TX                       |
| GPS UART RX (Pi TX)   | GPIO14| 8          | To GPS RX                         |
| GPS PPS               | GPIO18| 12         | 1 PPS input                       |
| CAN0 CS (SPI0 CE0)    | GPIO8 | 24         | MCP2515 CAN0 chip-select          |
| CAN1 CS (SPI0 CE1)    | GPIO7 | 26         | MCP2515 CAN1 chip-select          |
| SPI0 SCLK             | GPIO11| 23         | Shared by both MCP2515            |
| SPI0 MOSI             | GPIO10| 19         | Shared by both MCP2515            |
| SPI0 MISO             | GPIO9 | 21         | Shared by both MCP2515            |
| CAN0 Interrupt        | GPIO22| 15         | MCP2515 INT                       |
| CAN1 Interrupt        | GPIO13| 33         | MCP2515 INT                       |
| **Vehicle Run Input** | GPIO23| 16         | Dry-contact to GND (proposed)     |
| HAT EEPROM / ID bus   | GPIO0/1| 27/28     | Leave untouched (ID_SD / ID_SC)   |
| Others                | —     | various    | Currently free for expansion      |

## ASCII Pin Map (Pi 40-pin header)

Left column = odd pins (board edge), right column = even pins. Labels show current assignments.

```
3V3   (1)  (2) 5V
GPIO2 (3)  (4) 5V
GPIO3 (5)  (6) GND
GPIO4 (7)  (8) GPIO14 [GPS RX]
GND   (9)  (10) GPIO15 [GPS TX]
GPIO17(11) (12) GPIO18 [GPS PPS]
GPIO27(13) (14) GND
GPIO22[CAN0 INT] (15) (16) GPIO23 [Vehicle Run - proposed]
3V3   (17) (18) GPIO24
GPIO10[SPI0 MOSI] (19) (20) GND
GPIO9 [SPI0 MISO] (21) (22) GPIO25
GPIO11[SPI0 SCLK] (23) (24) GPIO8  [CAN0 CS]
GND   (25) (26) GPIO7  [CAN1 CS]
GPIO0 [ID_SD] (27) (28) GPIO1 [ID_SC]
GPIO5 (29) (30) GND
GPIO6 (31) (32) GPIO12
GPIO13[CAN1 INT] (33) (34) GND
GPIO19(35) (36) GPIO16
GPIO26(37) (38) GPIO20
GND   (39) (40) GPIO21
```

## Vehicle Running / Fuel Reset Input

- Proposed pin: **GPIO23 (header pin 16)** configured as input with an internal pull-up.
- Wiring: one side of the dry relay to **GND** (pin 14/20/25/30/34/39), the other side to **GPIO23**.
- Behavior: contacts closed → pin pulled to ground → vehicle running. Contacts open → pin floats high via pull-up.
- Software hook ideas: trigger start/stop logging, reset fuel counter to zero, or gate other automation on rising/falling edges.
