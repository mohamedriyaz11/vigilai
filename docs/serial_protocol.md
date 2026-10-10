# VigilAI Host <-> ESP32 Serial Binary Protocol Specification

This document specifies the binary communication protocol operating over UART (USB-CDC) between the VigilAI Host Application (Laptop/SBC) and the ESP32 actuator firmware.

---

## 1. Physical & Link Layer Parameters

| Parameter | Value |
|---|---|
| **Baud Rate** | 115,200 baud |
| **Data Bits** | 8 |
| **Parity** | None |
| **Stop Bits** | 1 |
| **Flow Control** | None |
| **Maximum Transmission Rate** | 20 Hz (Host command rate limiter) |
| **Heartbeat Frequency** | 200 ms (5 Hz) |
| **Firmware Watchdog Timeout** | 500 ms |

---

## 2. Frame Structure

Every transmission is enclosed in a structured binary frame with a Start-of-Frame delimiter and cyclic redundancy check:

```
+------------+------------+------------+--------------------+------------+
|  SOF (1B)  |  LEN (1B)  |  CMD (1B)  |   PAYLOAD (N B)    |  CRC8 (1B) |
+------------+------------+------------+--------------------+------------+
```

| Field | Size | Type | Description |
|---|---|---|---|
| **SOF** | 1 byte | uint8 | Constant sync byte: `0xAA` (170 decimal) |
| **LEN** | 1 byte | uint8 | Byte length of `PAYLOAD` ($0 \le N \le 32$) |
| **CMD** | 1 byte | uint8 | Opcode defining command or reply type |
| **PAYLOAD** | $N$ bytes | bytes | Command arguments or telemetry data |
| **CRC8** | 1 byte | uint8 | CRC-8 checksum computed over `LEN + CMD + PAYLOAD` |

---

## 3. Command Opcodes (Host &rarr; ESP32)

### `0x01` — POINT
Commands the pointer servo to orient towards target angle.
- **LEN:** `0x01`
- **Payload:** `[target_angle_deg]` (uint8, clamped between 10 and 170).
- **Frame Example:** `AA 01 01 5A 37` (Target 90° = `0x5A`)

### `0x02` — PARK
Instructs firmware to return servo pointer to neutral center position (90°).
- **LEN:** `0x00`
- **Payload:** None
- **Frame Example:** `AA 00 02 B1`

### `0x03` — DETACH
Instructs firmware to disable PWM timer output, freeing the servo arm.
- **LEN:** `0x00`
- **Payload:** None
- **Frame Example:** `AA 00 03 B6`

### `0x04` — HEARTBEAT
Periodic keepalive packet from the host. Prevents firmware failsafe trigger.
- **LEN:** `0x00`
- **Payload:** None
- **Frame Example:** `AA 00 04 BF`

### `0x05` — STATUS_REQUEST
Requests current status from firmware. Firmware responds with `STATUS_REPLY` (`0x81`).
- **LEN:** `0x00`
- **Payload:** None
- **Frame Example:** `AA 00 05 B8`

---

## 4. Reply Opcodes (ESP32 &rarr; Host)

### `0x81` — STATUS_REPLY
Telemetry response providing internal firmware state.
- **LEN:** `0x03`
- **Payload (3 bytes):**
  1. `angle_deg` (uint8): Current servo position (10–170).
  2. `is_muted` (uint8): Hardware mute switch state (`0x00` = active, `0x01` = muted).
  3. `system_state` (uint8): `0x00` = Disconnected/Idle, `0x01` = Parked, `0x02` = Active Tracking, `0x03` = Failsafe Watchdog Timeout.
- **Frame Example:** `AA 03 81 5A 00 02 C4`

---

## 5. CRC-8 Algorithm & Polynomial

CRC-8 is calculated using the polynomial **`0x07`** ($x^8 + x^2 + x + 1$), with initial value `0x00`:

```python
def compute_crc8(data: bytes) -> int:
    crc = 0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc
```

---

## 6. Host & Firmware Timing Invariants

1. **Host Slew Limiting:** The host enforces a slew cap of **120°/s** before issuing `POINT` commands.
2. **Firmware Slew Limiting:** The ESP32 implements hardware-level slew ramping at **120°/s** via a 10 ms non-blocking timer interval.
3. **Firmware Watchdog:** If no valid `HEARTBEAT` (`0x04`) or `POINT` (`0x01`) is decoded for **500 ms**, firmware initiates failsafe:
   - Sets target to 90° (Park).
   - Detaches PWM drive after reaching target or 2 seconds.
   - Sets LED pattern to rapid warning blink (10 Hz).
4. **Hardware Mute Switch:**
   - Monitored on GPIO15.
   - When pulled LOW (active), any `POINT` command is silently dropped, servo is detached, and LED is turned OFF.
