"""Abstract base interface for VigilAI servo actuation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ServoInterface(ABC):
    """Abstract interface defining required servo control primitives."""

    @abstractmethod
    def point(self, angle_deg: float) -> bool:
        """Drive physical or simulated pointer to the specified target angle (degrees)."""
        pass

    @abstractmethod
    def park(self) -> bool:
        """Move pointer to default neutral park position (typically 90 deg)."""
        pass

    @abstractmethod
    def detach(self) -> bool:
        """Disable PWM drive signal to allow free pointer movement and conserve power."""
        pass

    @abstractmethod
    def heartbeat(self) -> bool:
        """Send a periodic keepalive signal to prevent watchdog failsafe trigger."""
        pass

    @abstractmethod
    def status(self) -> dict[str, Any]:
        """Query actuator status (current angle, state, muted status)."""
        pass
