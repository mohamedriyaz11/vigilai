# VigilAI — An Agentic Embodied Companion for Proactive Situational Awareness

[![CI](https://github.com/vigilai-project/vigilai/actions/workflows/ci.yml/badge.svg)](https://github.com/vigilai-project/vigilai/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Theme: HCI 2.0](https://img.shields.io/badge/Vishwakarma%20Awards%202026--27-Theme%209%20HCI%202.0-indigo.svg)](https://vishwakarma-awards.in)

**Vishwakarma Awards 2026–27**  
**Application ID:** `VK26-AU-HCI-0036`  
**Theme 9:** Human-Computer Interaction (HCI 2.0)  
**Sub-Theme:** Agentic Hardware & Embodied Intelligent Systems  

---

## 1. Executive Summary & Pitch

**VigilAI** is an embodied, screenless, zero-wake-word ambient desktop companion designed to restore situational awareness and safety for older adults, visually impaired users, and distracted individuals. Operating autonomously through a single camera and a low-inertia physical pointer servo, VigilAI runs a continuous **Perceive $\rightarrow$ Reason $\rightarrow$ Act** loop entirely on local compute. Without requiring verbal prompts or intrusive screens, it perceives environmental changes, reasons through time-of-day routine statistics and contextual relevance rules (such as forgotten medication on counters during dosage windows or tripping hazards obstructing walking paths), and physically directs human attention via directional physical pointing coupled with natural spatial speech cues (*"On your left: your evening medication has not been taken yet"*). By strictly decoupling intelligence from surveillance, VigilAI processes all visual frames in volatile memory without ever saving or transmitting video, establishing a privacy-preserving benchmark for assistive embodied systems.

---

## 2. Architecture Pipeline

```mermaid
flowchart TD
    subgraph PERCEPTION ["Perception Pipeline (Host / Edge Compute)"]
        A[USB Camera / Video Stream] -->|Volatile BGR Frames| B[Frame Quality Evaluator<br/>Laplacian Blur & Mean Brightness]
        B -->|Quality Pass / Low Visibility Flag| C[YOLOv8n Lightweight Detector<br/>320x320 Input]
        C -->|Detections Confidence >= 0.6| D[Temporal Tracker<br/>3-Frame Confirmation & Cooldowns]
        D -->|Confirmed Scene Events| E[Grid-Cell Spatial Register<br/>Usual Place Tracking]
    end

    subgraph AGENT ["Agentic Reasoning Core (LangGraph)"]
        E --> F[Perceive & Update World State]
        F --> G[Relevance Scoring Engine<br/>Heuristics & Routine Memory]
        H[(SQLite Long-Term Memory<br/>Time-of-Day Histograms & Feedback)] <--> G
        G --> I{Priority Gate}
        I -->|High / Alert Worthy| J[Explanation Synthesizer<br/>Template Fallback & Guardrailed LLM]
        I -->|Suppressed / Routine| K[Log & Sleep]
        J --> L[Spatial Action Planner<br/>HFOV Angle Mapping & Safety Gates]
    end

    subgraph ACTUATION ["Actuation & Multimodal Feedback"]
        L -->|Normalized Angle 10°-170°| M{Target Actuator}
        M -->|Simulated Flag| N[Simulated Pointer Terminal/Plot]
        M -->|Physical ESP32 Link| O[Binary Serial Protocol<br/>CRC-8, 120°/s Slew, 20Hz]
        L -->|Spatial Voice Message| P[Text-to-Speech Engine<br/>Non-blocking pyttsx3 / Piper]
        O --> Q[ESP32 Microcontroller<br/>PWM Servo Pointer & Mute Switch]
    end

    subgraph TELEMETRY ["Telemetry & Control"]
        F -.->|JSON State Only (No Video)| R[Flask Dashboard & WebSocket<br/>Token-Authenticated Local UI]
        R -.->|Mute / Snooze / Feedback| G
    end
```

---

## 3. Quick Start in 5 Commands (Laptop & Simulated Servo)

Experience the complete end-to-end loop directly on a laptop using simulated actuation and replay events:

```bash
# 1. Clone repository & navigate to directory
git clone https://github.com/vigilai-project/vigilai.git && cd vigilai

# 2. Create and activate a Python 3.11+ virtual environment
python -m venv .venv && source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy configuration environment template
cp .env.example .env

# 5. Launch VigilAI in simulated servo mode with offline replay scenario
python scripts/run_vigilai.py --sim-servo --replay examples/sample_events.json
```

To run with your laptop webcam instead of replayed events:
```bash
python scripts/run_vigilai.py --sim-servo --camera 0
```

---

## 4. Hardware Specification & Wiring

When transitioning from laptop simulation to the physical desktop companion:

| Subsystem | Component | Specifications |
|---|---|---|
| **Microcontroller** | ESP32-WROOM-32D | Dual Xtensa 32-bit LX6, 240 MHz, USB-UART CH340/CP2102 |
| **Actuator** | MG90S Micro Servo | Metal gear, 180° sweep, Operating speed 0.1 s/60° |
| **Optics** | Wide-Angle USB Camera | 90° HFOV, 720p/1080p UVC Compliant |
| **Safety Switch** | Physical Toggle Switch | SPST switch for hardware mute / detachment |
| **Indicator** | Status LED | 5mm diffused Green LED (Current limiting 220Ω resistor) |
| **Power Supply** | 5V 2A DC Adapter | External rail powering servo to prevent MCU brownouts |

### Wiring Pinout Table

| ESP32 Pin | Connected Component | Function / Notes |
|---|---|---|
| **GPIO 18** | MG90S Servo PWM (Orange/Yellow) | LEDC Timer Channel PWM Output (50 Hz, 500-2500 µs pulse) |
| **GPIO 4** | Active Status LED Anode | Output: Solid = Active Tracking, Fast Blink = Watchdog/Offline |
| **GPIO 15** | Hardware Mute Switch | Input with Internal Pull-up (`INPUT_PULLUP`). LOW = Muted / Detached |
| **VIN / 5V** | External 5V Power Supply Rail | Common 5V DC Rail (powers ESP32 & Servo VCC) |
| **GND** | External Common Ground | Tied ground plane across Host, ESP32, and Servo supply |

### Documentation & Hardware Guides
* [System Architecture & State Machine Pipeline](docs/architecture.md)
* [Safety Architecture & FMEA Matrix](docs/safety.md)
* [Serial Protocol Specification (CRC-8)](docs/serial_protocol.md)
* [Hardware Wiring & Electrical Schematics](docs/wiring.md)
* [Bill of Materials (8 Line Items, ~₹12,350 INR)](docs/BOM.md)
* [Empirical Hardware Benchmarking Guide](docs/benchmarks.md)

---

## 5. Firmware Installation (ESP32)

The firmware is located in `firmware/vigilai_esp32/vigilai_esp32.ino`.

### Via Arduino IDE:
1. Open Arduino IDE and install the **esp32 by Espressif Systems** board package.
2. Select **ESP32 Dev Module** from the Tools menu.
3. Open [`firmware/vigilai_esp32/vigilai_esp32.ino`](firmware/vigilai_esp32/vigilai_esp32.ino).
4. Connect the ESP32 via USB and select the COM port.
5. Click **Upload**.

### Via PlatformIO:
```bash
cd firmware/vigilai_esp32
pio run --target upload
```

---

## 6. Safety and Privacy Safeguards

VigilAI is designed with **Privacy by Construction** and strict hardware safety invariants:

* **Ephemeral Video Ingestion:** Visual frames reside strictly in volatile RAM. They are never written to disk, cached, or transmitted over any local or wide-area network.
* **Text-Only Agent Summaries:** The agent reasoning engine operates solely on structured JSON symbolic events (e.g., `{"label": "bottle", "x": 0.42, "time": "19:05"}`). Cloud LLMs are disabled by default (`cloud_llm_enabled: false`).
* **Mechanical Slew Limiting:** Both host and firmware enforce a strict slew rate cap of **120°/s**, preventing sudden physical pointer jerks or gear stripping.
* **Firmware Safety Watchdog:** If the host application halts or fails to send a serial heartbeat within **500 ms**, the ESP32 automatically parks the pointer to 90° and detaches PWM drive.
* **Instant Physical Mute:** A physical switch connected to GPIO15 forces immediate servo detachment and silences all acoustic cues.
* **Quiet Hours Gate:** Auditory alerts are suppressed between configurable quiet hours (default: `22:00` to `07:00`) unless marked critical.

---

## 7. Project Status

| Module / Feature | Current Implementation Status | Hardware Validation |
|---|:---:|:---:|
| **YOLOv8n Lightweight Detection (320px)** | ✅ Fully Implemented | Laptop / Host Tested |
| **Temporal 3-Frame Confirmation & Cooldowns** | ✅ Fully Implemented | Automated Unit Tested |
| **Laplacian Blur & Brightness Visibility Filter** | ✅ Fully Implemented | Synthetic & Live Tested |
| **Time-of-Day Routine Memory (SQLite)** | ✅ Fully Implemented | Verified with Mock Clocks |
| **Fast-Path Relevance Heuristics** | ✅ Fully Implemented | Verified with Test Suite |
| **LangGraph Agent Workflow** | ✅ Fully Implemented | Validated via Mock Graph |
| **Non-blocking TTS Voice Dispatcher** | ✅ Fully Implemented | Tested (pyttsx3) |
| **Simulated Servo Actuator (`--sim-servo`)** | ✅ Fully Implemented | Verified in Terminal/Plot |
| **CRC-8 Serial Binary Protocol** | ✅ Fully Implemented | 100% Vector Tested |
| **ESP32 Firmware (Slew cap, Watchdog, Mute)** | ✅ Source Complete | [ ] Untested on Physical Rig |
| **Web Dashboard (WebSocket State, Token Auth)** | ✅ Fully Implemented | Verified via Localhost |
| **Sub-2.0s Latency Benchmarking Script** | ✅ Fully Implemented | Live Profiling Tool |

---

## 8. Development Roadmap (Oct 2026 – Jan 2027)

```
[Oct 2026] ───────► Core Architecture, Laptop MVP, Simulated Actuation, CI Suite
[Nov 2026] ───────► ESP32 Hardware Integration, 3D Printed Desk Enclosure, Slew Testing
[Dec 2026] ───────► On-Device Quantization (NCNN/TensorRT on Jetson/OrangePi), Edge Calibration
[Jan 2027] ───────► HCI Pilot Study with 15 Older Adults & Visually Impaired Participants
```

---

## 9. Limitations & Disclaimer

> [!IMPORTANT]
> **Advisory Companion Disclaimer:**  
> VigilAI is an experimental academic prototype developed under the Vishwakarma Awards 2026–27 (Theme 9: HCI 2.0). It is an ambient assistive aid designed for contextual awareness and proactive attention guiding. **VigilAI is NOT a certified medical device, certified assistive medical aid, or mission-critical safety system.** It must not be relied upon as a sole preventative measure for falls, medical emergencies, or hazardous object interactions.

---

## 10. License & Credits

- **License:** Released under the permissive [MIT License](LICENSE).
- **Inspiration & Awards:** Developed for **Vishwakarma Awards 2026–27**, Application ID `VK26-AU-HCI-0036`.
- **Core Open Source Technologies:** Ultralytics YOLOv8, LangGraph, OpenCV, PySerial, Flask.
