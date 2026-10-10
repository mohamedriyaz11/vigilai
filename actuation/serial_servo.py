"""ESP32 Serial binary communication protocol and hardware servo actuator."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from actuation.servo_interface import ServoInterface

logger = logging.getLogger(__name__)

# Protocol Constants
SOF = 0xAA
CRC8_POLY = 0x07

CMD_POINT = 0x01
CMD_PARK = 0x02
CMD_DETACH = 0x03
CMD_HEARTBEAT = 0x04
CMD_STATUS_REQUEST = 0x05
CMD_STATUS_REPLY = 0x81


def compute_crc8(data: bytes | bytearray) -> int:
    """Calculate CRC-8 checksum over bytes using polynomial 0x07 (init 0x00)."""
    crc = 0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ CRC8_POLY) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


def encode_frame(cmd: int, payload: bytes = b"") -> bytes:
    """Construct a binary transmission frame: 0xAA | LEN | CMD | PAYLOAD | CRC8."""
    length = len(payload)
    if length > 32:
        raise ValueError(f"Payload length exceeds maximum allowable (32 bytes): {length}")

    header_and_payload = bytes([length, cmd]) + payload
    crc = compute_crc8(header_and_payload)
    return bytes([SOF]) + header_and_payload + bytes([crc])


def decode_frame(raw: bytes) -> tuple[int, bytes]:
    """Validate and parse a raw binary frame.

    Returns:
        Tuple of (cmd_opcode, payload_bytes).

    Raises:
        ValueError: If frame is truncated, missing SOF, or fails CRC-8 check.
    """
    if len(raw) < 4:
        raise ValueError(f"Frame is too short ({len(raw)} bytes; minimum is 4 bytes).")

    if raw[0] != SOF:
        raise ValueError(f"Invalid Start of Frame delimiter: 0x{raw[0]:02X} (expected 0x{SOF:02X}).")

    length = raw[1]
    expected_total_len = 1 + 1 + 1 + length + 1  # SOF + LEN + CMD + PAYLOAD + CRC8

    if len(raw) < expected_total_len:
        raise ValueError(f"Frame truncated: received {len(raw)} bytes, expected {expected_total_len} bytes.")

    cmd = raw[2]
    payload = raw[3 : 3 + length]
    received_crc = raw[3 + length]

    calculated_crc = compute_crc8(raw[1 : 3 + length])
    if received_crc != calculated_crc:
        raise ValueError(
            f"CRC-8 verification failed: computed 0x{calculated_crc:02X}, received 0x{received_crc:02X}."
        )

    return cmd, payload


class SerialServo(ServoInterface):
    """Controls physical ESP32-driven pointer servo over serial UART link."""

    def __init__(
        self,
        port: str = "COM5",
        baudrate: int = 115200,
        min_deg: float = 10.0,
        max_deg: float = 170.0,
        slew_dps: float = 120.0,
        command_rate_hz: float = 20.0,
        heartbeat_ms: int = 200,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.min_deg = min_deg
        self.max_deg = max_deg
        self.slew_dps = slew_dps
        self.min_interval_s = 1.0 / max(1.0, command_rate_hz)
        self.heartbeat_interval_s = heartbeat_ms / 1000.0

        self.current_angle = 90.0
        self.target_angle = 90.0
        self.muted = False
        self.state = "disconnected"

        self._last_command_time = 0.0
        self._last_update_time = time.time()
        self._serial = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        self._init_serial()
        self._start_heartbeat_worker()

    def _init_serial(self) -> None:
        """Attempt serial connection; fall back to dry-run mode if port unavailable."""
        try:
            import serial

            self._serial = serial.Serial(self.port, self.baudrate, timeout=0.1)
            self.state = "parked"
            logger.info("Connected to ESP32 on port %s (%d baud).", self.port, self.baudrate)
        except Exception as exc:
            logger.warning("Serial connection to %s failed (%s). Running in dry-run mode.", self.port, exc)
            self._serial = None
            self.state = "dry_run"

    def _start_heartbeat_worker(self) -> None:
        """Start background heartbeat thread sending keepalive every 200ms."""
        self._running = True
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True, name="SerialHeartbeatWorker")
        self._thread.start()

    def _heartbeat_loop(self) -> None:
        while self._running:
            self.heartbeat()
            time.sleep(self.heartbeat_interval_s)

    def close(self) -> None:
        """Shutdown background worker and close serial interface."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        with self._lock:
            if self._serial and self._serial.is_open:
                self._serial.close()
            self._serial = None

    def _send_raw_frame(self, frame: bytes) -> None:
        """Transmit frame over serial port."""
        with self._lock:
            if self._serial and self._serial.is_open:
                try:
                    self._serial.write(frame)
                    self._serial.flush()
                except Exception as exc:
                    logger.error("Serial write failed: %s", exc)

    def point(self, angle_deg: float) -> bool:
        """Send rate-limited, slew-capped POINT command to ESP32."""
        if self.muted:
            return False

        now = time.time()
        # Enforce host command rate limiter (max 20 Hz)
        if now - self._last_command_time < self.min_interval_s:
            return False

        # Host slew cap enforcement
        dt = max(0.001, now - self._last_update_time)
        max_delta = self.slew_dps * dt

        clamped = max(self.min_deg, min(self.max_deg, float(angle_deg)))
        delta = clamped - self.current_angle
        if abs(delta) > max_delta:
            direction = 1.0 if delta > 0 else -1.0
            next_angle = self.current_angle + direction * max_delta
        else:
            next_angle = clamped

        self.current_angle = next_angle
        self.target_angle = clamped
        self._last_update_time = now
        self._last_command_time = now
        self.state = "active"

        uint8_angle = int(round(self.current_angle))
        frame = encode_frame(CMD_POINT, bytes([uint8_angle]))
        self._send_raw_frame(frame)
        return True

    def park(self) -> bool:
        """Command ESP32 to return pointer to center park position (90 deg)."""
        frame = encode_frame(CMD_PARK)
        self._send_raw_frame(frame)
        self.current_angle = 90.0
        self.target_angle = 90.0
        self.state = "parked"
        return True

    def detach(self) -> bool:
        """Command ESP32 to disable PWM output."""
        frame = encode_frame(CMD_DETACH)
        self._send_raw_frame(frame)
        self.state = "detached"
        return True

    def heartbeat(self) -> bool:
        """Send periodic keepalive packet to satisfy firmware 500ms watchdog."""
        frame = encode_frame(CMD_HEARTBEAT)
        self._send_raw_frame(frame)
        return True

    def status(self) -> dict[str, Any]:
        """Request and return status from ESP32."""
        frame = encode_frame(CMD_STATUS_REQUEST)
        self._send_raw_frame(frame)

        # Parse response if serial data is available
        with self._lock:
            if self._serial and self._serial.is_open and self._serial.in_waiting >= 7:
                try:
                    resp = self._serial.read(7)
                    cmd, payload = decode_frame(resp)
                    if cmd == CMD_STATUS_REPLY and len(payload) == 3:
                        self.current_angle = float(payload[0])
                        self.muted = bool(payload[1])
                except Exception as exc:
                    logger.debug("Failed parsing serial status response: %s", exc)

        return {
            "current_angle": round(self.current_angle, 1),
            "target_angle": round(self.target_angle, 1),
            "state": self.state,
            "muted": self.muted,
        }
