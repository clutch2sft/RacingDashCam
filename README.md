Grassroots Racing Data Platform

An open source project built by racers, for racers.

Welcome to the Grassroots Racing Data Platform – a community-driven initiative dedicated to democratizing motorsport data collection and analysis. We believe that cutting-edge telemetry and performance insights shouldn't be exclusive to big-budget racing teams.

Our Mission
Whether you're campaigning a weekend warrior track car, building a competitive rally machine, or developing the next generation of grassroots racing technology, this project empowers you to:

Collect professional-grade data without professional-grade budgets
Analyze your performance with powerful, accessible tools
Collaborate with a community of like-minded racers and developers
Innovate through open source contributions that benefit everyone

This is more than just a software project – it's a movement to level the playing field and give every racer access to the tools they need to improve, compete, and win.
Built on Community Power

By leveraging the collective knowledge, creativity, and passion of the grassroots racing community, we're building DIY data collection and analysis systems that rival commercial solutions. Every contribution, from code to documentation to testing on track, helps make racing data accessible to all.

Ready to join the pit crew? Dive into the docs below and let's build something amazing together.

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