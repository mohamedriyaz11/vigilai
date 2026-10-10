"""VigilAI Actuation Package."""

from actuation.calibration import ServoCalibration
from actuation.serial_servo import (
    CMD_DETACH,
    CMD_HEARTBEAT,
    CMD_PARK,
    CMD_POINT,
    CMD_STATUS_REPLY,
    CMD_STATUS_REQUEST,
    SerialServo,
    compute_crc8,
    decode_frame,
    encode_frame,
)
from actuation.servo_interface import ServoInterface
from actuation.sim_servo import SimulatedServo

__all__ = [
    "ServoInterface",
    "SimulatedServo",
    "SerialServo",
    "ServoCalibration",
    "encode_frame",
    "decode_frame",
    "compute_crc8",
    "CMD_POINT",
    "CMD_PARK",
    "CMD_DETACH",
    "CMD_HEARTBEAT",
    "CMD_STATUS_REQUEST",
    "CMD_STATUS_REPLY",
]
