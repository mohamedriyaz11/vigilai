# VigilAI Safety Architecture & Failure Modes and Effects Analysis (FMEA)

**Vishwakarma Awards 2026–27 | Application ID: VK26-AU-HCI-0036**  
**Theme 9: HCI 2.0 (Agentic Hardware & Embodied Intelligent Systems)**

---

## 1. System Safety Philosophy

Because VigilAI is designed for ambient operation around vulnerable individuals (older adults, visually impaired persons, and distracted users), **hardware safety, user trust, and psychological calm** are core engineering requirements rather than afterthoughts. The system operates strictly as an **advisory attentional companion**, never exerting force on the user's environment.

---

## 2. Failure Mode and Effects Analysis (FMEA) Table

*Severity (S), Occurrence (O), and Detection (D) are rated on a standard 1–5 engineering scale. Risk Priority Number (RPN) = $S \times O \times D$.*

| Failure Mode | Root Cause | Effect on User | S | O | D | RPN | Mitigation & Fail-Safe Architecture |
|---|---|---|:---:|:---:|:---:|:---:|---|
| **Host Software Hang / Process Crash** | Python OOM, driver deadlock, or OS freeze | Servo arm stuck pointing or holding stale position | 3 | 2 | 1 | **6** | **Firmware Watchdog:** ESP32 firmware monitors heartbeat packets. If no heartbeat received within 500 ms, pointer automatically parks to 90° and detaches PWM drive. LED triggers fast warning blink. |
| **Mechanical Obstruction / Stalled Servo** | Physical object blocks pointer wand during sweep | Gear stripping, coil overheating, or power brownout | 2 | 2 | 1 | **4** | **2-Second Stall Timeout:** Firmware measures elapsed travel time; if current position fails to settle at target within 2.0 seconds, servo PWM is instantly detached. |
| **Startling Sudden Jerk Motion** | Sudden target angle jump from 10° to 170° | User startled or gear stripped by high acceleration | 3 | 2 | 1 | **6** | **Dual Slew Rate Cap:** Both host application and firmware enforce an invariant maximum slew rate of **120°/s** via smooth non-blocking interpolation ramps. |
| **Severe Lighting Degradation (Dark / Blurry)** | Room lights switched off, camera smudged, or occluded | False positive detections and erroneous voice alerts | 2 | 3 | 1 | **6** | **Perception Quality Gate:** CameraEvaluator computes Laplacian variance and mean luminance. If blurry (<100) or dark (<40), `low_visibility` flag blocks agent actuation. |
| **False Positive Alarm Fatigue** | Background item continuously misclassified as hazard | Annoyance, acoustic disruption, erosion of trust | 2 | 3 | 1 | **6** | **Episodic Dismissal Attenuation:** When user dismisses an alert via web UI or button, SQLite memory records the feedback, applying a -0.20 score penalty to future events for that label. |
| **Acoustic Disruption During Sleep Hours** | Non-critical object movement detected at night | Sleep disturbance for older adult or family | 3 | 2 | 1 | **6** | **Quiet Hours Gate:** Time-of-day filter suppresses all non-critical alerts between configured hours (default: 22:00 to 07:00). |
| **Accidental Video Leakage / Cloud Exposure** | Misconfiguration or cyber intruder accessing stream | Breach of home intimacy and private space | 5 | 1 | 1 | **5** | **Privacy by Construction:** Video frames reside strictly in volatile RAM and are never written to disk. Cloud LLM is disabled by default and restricted to structured text summaries only. |
| **Over-reliance as Life-Safety Device** | User assumes system will prevent every fall or hazard | Potential injury if an obstacle is missed | 4 | 2 | 1 | **8** | **Advisory Aid Disclaimers & Multi-Modal Cues:** Clear interface messaging and acoustic confirmations establish that the device is an assistive ambient guide, not certified PPE or a medical diagnostic tool. |

---

## 3. Dedicated Fail-Safe Mechanisms

### 3.1 Hardware Mute Switch (GPIO 15)
A physical toggle switch grounded to GPIO15 with an internal pull-up resistor. When pulled LOW:
- Immediate detach of the servo PWM output signal.
- Status indicator LED shuts off immediately.
- Speech synthesis audio output is suppressed.

### 3.2 Dual-Tier Slew Rate Limiter (120°/s)
Fast pointer jerks induce user alarm and mechanical wear. VigilAI enforces slew rate limiting across two layers:
1. **Tier 1 (Host Planner):** Commands issued at max 20 Hz, limiting delta angle $\le 120^\circ \times \Delta t$.
2. **Tier 2 (Firmware Timer Loop):** 10 ms interval step interpolator on the ESP32 ensures smooth sweep regardless of host packet burst timing.

### 3.3 Ephemeral Volatile Ingestion Guarantee
All OpenCV frames (`cv2.Mat`) are consumed directly from camera RAM and released immediately after tensor extraction. **No frame saving API, disk caching directory, or video transmission socket exists anywhere in the codebase.**
