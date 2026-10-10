"""Simulated servo actuator for laptop execution and testing."""

from __future__ import annotations

import logging
import time
from typing import Any

from actuation.servo_interface import ServoInterface

logger = logging.getLogger(__name__)


class SimulatedServo(ServoInterface):
    """Simulated servo providing virtual pointer positioning and ASCII visualization."""

    def __init__(
        self,
        min_deg: float = 10.0,
        max_deg: float = 170.0,
        center_deg: float = 90.0,
        slew_dps: float = 120.0,
        enforce_slew: bool = True,
        enable_visualizer: bool = False,
    ) -> None:
        self.min_deg = min_deg
        self.max_deg = max_deg
        self.center_deg = center_deg
        self.slew_dps = slew_dps
        self.enforce_slew = enforce_slew
        self.enable_visualizer = enable_visualizer

        self.current_angle = center_deg
        self.target_angle = center_deg
        self.state = "parked"  # 'parked', 'active', 'detached'
        self.muted = False
        self.last_update_time = time.time()
        self.last_heartbeat_time = time.time()

    def set_muted(self, muted: bool) -> None:
        """Toggle hardware mute emulation."""
        self.muted = muted
        if muted:
            self.state = "detached"
            logger.info("[SIM-SERVO] Hardware Mute ENGAGED. Actuator detached.")
        else:
            logger.info("[SIM-SERVO] Hardware Mute DISENGAGED.")

    def point(self, angle_deg: float) -> bool:
        """Command the pointer to target angle, enforcing soft limits and slew cap."""
        if self.muted:
            logger.warning("[SIM-SERVO] Command ignored: Actuator is muted.")
            return False

        # Enforce soft limits
        clamped_target = max(self.min_deg, min(self.max_deg, float(angle_deg)))

        now = time.time()
        if self.enforce_slew:
            dt = max(0.001, now - self.last_update_time)
            max_delta = self.slew_dps * dt

            delta = clamped_target - self.current_angle
            if abs(delta) > max_delta:
                direction = 1.0 if delta > 0 else -1.0
                self.current_angle += direction * max_delta
            else:
                self.current_angle = clamped_target
        else:
            self.current_angle = clamped_target

        self.target_angle = clamped_target
        self.last_update_time = now
        self.state = "active"

        # Display terminal indicator
        gauge = self._render_ascii_gauge(self.current_angle)
        logger.info("[SIM-SERVO] Target: %5.1f° | Current: %5.1f° %s", clamped_target, self.current_angle, gauge)

        return True

    def park(self) -> bool:
        """Drive pointer back to neutral center position."""
        if self.muted:
            return False
        self.target_angle = self.center_deg
        self.current_angle = self.center_deg
        self.state = "parked"
        logger.info("[SIM-SERVO] Parked at %5.1f°", self.center_deg)
        return True

    def detach(self) -> bool:
        """Detach virtual PWM signal."""
        self.state = "detached"
        logger.info("[SIM-SERVO] Detached (PWM signal idle).")
        return True

    def heartbeat(self) -> bool:
        """Acknowledge periodic heartbeat from host controller."""
        self.last_heartbeat_time = time.time()
        return True

    def status(self) -> dict[str, Any]:
        """Return virtual servo telemetry."""
        return {
            "current_angle": round(self.current_angle, 1),
            "target_angle": round(self.target_angle, 1),
            "state": self.state,
            "muted": self.muted,
            "last_heartbeat": self.last_heartbeat_time,
        }

    def _render_ascii_gauge(self, angle: float, width: int = 21) -> str:
        """Render a compact horizontal text gauge representing the 180-deg arc."""
        # Normalize angle (10 to 170 deg) to gauge index [0, width-1]
        norm = (angle - 10.0) / (170.0 - 10.0)
        idx = max(0, min(width - 1, int(norm * (width - 1))))
        bar = ["-"] * width
        bar[idx] = "▲"
        return "[" + "".join(bar) + "]"
