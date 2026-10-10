"""Servo-to-camera angular calibration management."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ServoCalibration:
    """Calibration parameters linking camera normalized coordinates to physical servo angles."""

    center_deg: float = 90.0
    angle_offset: float = 0.0
    hfov_deg: float = 90.0
    min_deg: float = 10.0
    max_deg: float = 170.0
    invert_direction: bool = False

    def save(self, filepath: str = "calibration.json") -> None:
        """Persist calibration parameters to JSON."""
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)
        logger.info("Saved servo calibration to %s", filepath)

    @classmethod
    def load(cls, filepath: str = "calibration.json") -> ServoCalibration:
        """Load calibration from file or instantiate default if absent."""
        p = Path(filepath)
        if not p.exists():
            logger.info("Calibration file %s not found. Using default parameters.", filepath)
            return cls()

        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            return cls(
                center_deg=float(data.get("center_deg", 90.0)),
                angle_offset=float(data.get("angle_offset", 0.0)),
                hfov_deg=float(data.get("hfov_deg", 90.0)),
                min_deg=float(data.get("min_deg", 10.0)),
                max_deg=float(data.get("max_deg", 170.0)),
                invert_direction=bool(data.get("invert_direction", False)),
            )
        except Exception as exc:
            logger.warning("Failed parsing %s (%s). Using defaults.", filepath, exc)
            return cls()

    @classmethod
    def fit_two_points(
        cls,
        x1_norm: float,
        angle1_deg: float,
        x2_norm: float,
        angle2_deg: float,
        min_deg: float = 10.0,
        max_deg: float = 170.0,
    ) -> ServoCalibration:
        """Derive calibration slope (HFOV) and center angle from two empirical anchor points."""
        dx = x2_norm - x1_norm
        if abs(dx) < 1e-4:
            raise ValueError("Calibration x coordinates must not be identical.")

        # angle = slope * (x - 0.5) + center
        slope = (angle2_deg - angle1_deg) / dx
        hfov = abs(slope)
        invert = slope < 0.0

        # Find center angle at x = 0.5
        center = angle1_deg + slope * (0.5 - x1_norm)

        return cls(
            center_deg=round(center, 1),
            angle_offset=0.0,
            hfov_deg=round(hfov, 1),
            min_deg=min_deg,
            max_deg=max_deg,
            invert_direction=invert,
        )
