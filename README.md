# Active Dash Mirror - Racing Dashcam System

Raspberry Pi 5-based dashcam system with dual cameras, CAN bus vehicle data, and GPS integration.

## Current Version: v1 (Pi5 + Arducam HQ)

**Hardware:**
- Raspberry Pi 5 with Pimoroni NVMe Base
- Dual Arducam 12.3MP HQ cameras (IMX477)
- Waveshare 2-CH CAN HAT Plus
- LC29H GPS module

**Features:**
- Dual 1080p@30fps H.264 hardware encoding
- Live rearview mirror display
- CAN bus vehicle telemetry integration
- GPS tracking and logging
- Automatic storage management

## Quick Start

See [Docs/README.md](Docs/README.md) for complete documentation.

## Directory Structure
``````
RacingDashCam/
├── Docs/                    # All documentation
│   ├── README.md            # Documentation index
│   ├── SETUP_GUIDE.md       # Complete setup guide
│   └── CANBUS_GUIDE.md      # CAN bus reference
│
├── python/                  # Python application
│   ├── dashcam/             # Main package
│   │   ├── core/            # Platform-agnostic code
│   │   ├── canbus/          # CAN bus module
│   │   ├── platforms/       # Hardware-specific code
│   │   └── utils/           # Utilities
│   └── dashcam.py           # Main entry point
│
└── Scripts/                 # Installation scripts
    └── install/
        └── v1-pi5-arducam/  # v1 hardware install
``````

## Documentation

- [Complete Setup Guide](Docs/SETUP_GUIDE.md)
- [CAN Bus Integration](Docs/CANBUS_GUIDE.md)
- [v1 Hardware Details](Docs/hardware/v1-pi5-arducam.md)

## Installation

1. See [SETUP_GUIDE.md](Docs/SETUP_GUIDE.md) for complete instructions
2. Install script: ``Scripts/install/v1-pi5-arducam/dashcam_install.sh``

## Version History

- **v1** - Pi5 + Arducam HQ + Waveshare CAN HAT (current)
- **v2** - Planned: Custom camera board

## License

Personal use project.

---

**Ready to build your racing dashcam!** 🏁📹