# VigilAI Bill of Materials (BOM)

**Vishwakarma Awards 2026–27 | Application ID: VK26-AU-HCI-0036**  
**Theme 9: HCI 2.0 (Agentic Hardware & Embodied Intelligent Systems)**

> [!NOTE]
> All prices listed below represent **market estimates (Q4 2026 INR)** for commercial-off-the-shelf (COTS) prototyping components in India. VigilAI is intentionally engineered to run on existing laptops and standard webcams first, requiring zero proprietary or specialized hardware.

---

## 1. System Bill of Materials (8 Line Items)

| Item # | Component & Description | Key Specifications | Qty | Unit Price (INR, Est.) | Extended Price (INR, Est.) |
|:---:|---|---|:---:|:---:|:---:|
| **1** | **ESP32-WROOM-32D Development Board** | Dual-core 240 MHz Xtensa LX6, USB-C/Micro-USB UART, 38-pin DIP | 1 | ₹450 | ₹450 |
| **2** | **MG90S Metal Gear Micro Servo** | High-torque metal gear 180° sweep, 0.10s/60°, 5V operation | 1 | ₹250 | ₹250 |
| **3** | **Wide-Angle USB Webcam Module** | 90° Horizontal FOV, 1080p@30fps, UVC driverless, Volatile USB stream | 1 | ₹1,850 | ₹1,850 |
| **4** | **Dedicated Edge Compute Host (SBC)** | Raspberry Pi 5 (4GB RAM) / Refurbished Mini-PC host for local inference | 1 | ₹7,500 | ₹7,500 |
| **5** | **Regulated 5V 3A DC Adapter** | Universal 100-240V AC to 5V 3A DC with multi-tap power distribution | 1 | ₹650 | ₹650 |
| **6** | **3D Printed Ambient Enclosure & Pointer Arm** | PLA/PETG desktop shell, low-inertia pointer wand, weighted base | 1 | ₹850 | ₹850 |
| **7** | **Passive Electronics & Safety Harness** | SPST toggle switch, 5mm diffused LED, 220Ω resistor, 470µF cap, JST wiring | 1 set | ₹300 | ₹300 |
| **8** | **Mechanical Fasteners & Anti-Slip Base** | M2/M3 stainless standoffs, brass heat-set inserts, silicone damping pads | 1 set | ₹500 | ₹500 |
| **TOTAL** | **Estimated Prototype Bill of Materials** | *(Excluding optional cloud token credits)* | | | **₹12,350 INR** |

---

## 2. Component Selection Justification

1. **COTS Ubiquity:** Every component is available from standard Indian electronics distributors (Robu, Evelta, Tanotis) with zero custom silicon or single-source dependencies.
2. **Modular Edge Decoupling:** For users already owning a personal laptop or desktop PC, **Item #4 (₹7,500)** is omitted entirely, bringing the incremental companion accessory hardware cost to approximately **₹4,850 INR**.
3. **Repairability & Open Physical Design:** The 3D CAD files for Item #6 use standard metric screws and snap-fit joints to allow full repairability and disassembly in assisted living communities.
