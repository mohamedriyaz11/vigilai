# VigilAI Hardware Wiring & Power Architecture

**Vishwakarma Awards 2026–27 | Application ID: VK26-AU-HCI-0036**  
**Theme 9: HCI 2.0 (Agentic Hardware & Embodied Intelligent Systems)**

---

## 1. Pin Interconnect Map

| ESP32 GPIO | Subsystem / Component | Direction | Electrical Characteristics |
|---|---|---|---|
| **GPIO 18** | MG90S Micro Servo PWM Signal (Orange/Yellow wire) | Output | LEDC PWM Channel 0 (50 Hz, 3.3V logic level compatible) |
| **GPIO 4** | Status Indicator LED Anode (Green 5mm) | Output | Active HIGH, 3.3V via 220Ω series resistor (approx. 9 mA drive) |
| **GPIO 15** | Hardware Mute Toggle Switch | Input | Active LOW via internal pull-up resistor (`INPUT_PULLUP`), debounced |
| **VIN / 5V** | External 5V Regulated Power Rail | Power Input | Powers onboard AMS1117 3.3V LDO regulator |
| **GND** | System Ground Plane | Ground | Common reference tied across Host, ESP32, and Servo Supply |

---

## 2. Power Rail Distribution & Decoupling

A critical embedded failure mode in servo actuation is **MCU brownout reset** caused by inductive current surges during rapid acceleration. To eliminate this:

1. **Split Power Rail:** The MG90S servo is powered directly from an external regulated **5V 2A DC adapter**, completely bypassing the ESP32 onboard 3.3V regulator.
2. **Bulk Decoupling:** A **470 µF 16V low-ESR electrolytic capacitor** is placed in parallel across the servo 5V and GND rail right next to the servo connector.
3. **Common Ground:** The USB ground from the host PC/laptop is tied directly to the external 5V supply ground to maintain a common logic reference.

```
+-------------------------------------------------------+
|                 EXTERNAL 5V 2A DC ADAPTER            |
+-------------------+-----------------------------------+
                    | 5V DC
                    +------------------------+-------------------+
                    |                        |                   |
            +-------v-------+        +-------v-------+   +-------v-------+
            |  ESP32 VIN    |        |  Servo VCC    |   | 470uF Cap     |
            |  (Regulated)  |        |  (MG90S 5V)   |   | (Decoupling)  |
            +-------+-------+        +-------+-------+   +-------+-------+
                    |                        |                   |
                    +------------------------+-------------------+
                    | GND (Common Tied Ground Plane)
+-------------------+-----------------------------------+
|               HOST LAPTOP / EMBEDDED CONTROLLER        |
+-------------------------------------------------------+
```

---

## 3. Electrical Power Budget

| Component | Operating Voltage | Idle Current | Peak / Operating Current |
|---|---|---|---|
| ESP32-WROOM-32 (WiFi/BT Idle) | 3.3V (via LDO) | 45 mA | 95 mA |
| MG90S Metal Gear Micro Servo | 5.0V | 10 mA | 650 mA (Stall / Acceleration) |
| Green Status LED (GPIO4) | 3.3V | 0 mA | 9 mA |
| Mute Switch Circuit (GPIO15) | 3.3V | 0 mA | 0.07 mA (Pull-up when active) |
| **Total System Draw** | **5.0V Input** | **~55 mA** | **~755 mA** |

*A 5V 2.0A (10W) adapter provides a **2.6× safety margin**, ensuring zero voltage dips during maximum slew rate maneuvers.*
