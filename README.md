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

## **📣 Support the Project / GitHub Sponsors**

If this project helps your racing program — whether you're tracking CAN data, building your own dash mirror, or integrating Pi-based telemetry — you can support continued development through GitHub Sponsors:

[![Sponsor](https://img.shields.io/badge/Sponsor-@clutch2sft-ff69b4?logo=github\&logoColor=white)](https://github.com/sponsors/clutch2sft)

Sponsorship helps offset the real costs behind this work:

* Ongoing **Raspberry Pi 5** development, testing, and performance work
* Camera pipeline tuning (IMX477, IMX519, IMX415, Arducam HQ variations)
* Reliability improvements for long-duration recording and track-day abuse
* CAN bus decoding + messaging for multiple vehicle platforms
* GPS (LC29H) integration and higher-rate logging
* Storage management, corruption prevention, and safe-shutdown logic
* End-to-end documentation and examples
* Hardware experiments for the upcoming custom camera board

Your support directly accelerates features, fixes, and hardware testing.


## **🛠️ Project Roadmap**

A high-level view of where RacingDashCam is heading. Timeframes are flexible and based on testing, community input, and sponsorship capacity.


### **Phase 1 — Current Focus (Active)**

#### **Stability, Performance & Real-World Usability**

* Improve long-running recording robustness (thermal, I/O errors, camera restarts)
* Tune dual-camera H.264 pipelines for consistent latency and framerate
* Improve GPU/CPU balancing on Raspberry Pi 5
* Harden system boot, shutdown, overlay FS, and corruption protection
* Reduce rear-view display latency further (HDMI + DRM/KMS handling)

#### **CAN Bus & Vehicle Data Integration**

* Expand support for more common CAN layouts (GM, Toyota, Subaru, BMW, VW)
* Add configurable CAN message maps + CSV import/export
* Sync CAN + GPS + video timestamps with tighter accuracy
* Add detection helpers for common racing signals (RPM cutoff, throttle, braking)

#### **GPS & Timing**

* Improve LC29H integration (10 Hz logging, better discard logic for degraded fixes)
* Optional lap-timer pipeline (sector splits, best lap, delta overlay)

### **Phase 2 — Expanded Features (Near-Term)**

#### **UI, Overlays & Data Handling**

* On-screen overlays (speed, RPM, engine load, lap timing, GPS vectors)
* Video + telemetry export tools (CSV, Parquet, motorsport formats)
* A small “review mode” to quickly inspect last sessions at the track
* Configuration editor (YAML validation + sample presets)

#### **Automation & Events**

* Auto-start recording on engine start / vehicle motion
* Auto-stop with configurable cool-down period
* Error and health logs integrated into the Pi’s display or a mobile app


### **Phase 3 — Future Hardware Track**

While this repository is Pi-focused, development is happening in parallel on:

#### **Custom Camera Board (v2 Hardware)**

* RK3588S / Radxa CM5 test carrier
* High-bandwidth CSI design for multiple cameras
* Automotive-style power handling & packaging
* Expansion slot for future modules (analog input, IMU, CAN-FD, etc.)

RacingDashCam will remain Pi-first, but future releases will support both platforms with a unified software stack.

## **💬 Why This Roadmap Exists**

The goal is to keep the project transparent, community-guided, and aligned with real grassroots racing needs. Feedback, issues, test data, and PRs are all welcome — and sponsorship helps push features faster.


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