"""Perception event and detection dataclasses for VigilAI.

Frames are kept volatile in memory only; only structured events are emitted.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Detection:
    """Represents a single bounding box prediction from an object detector."""

    label: str
    confidence: float
    bbox: tuple[float, float, float, float]  # (x1, y1, x2, y2) normalized in [0, 1]
    center_x_norm: float  # Normalized horizontal center in [0.0, 1.0]
    center_y_norm: float = 0.5  # Normalized vertical center in [0.0, 1.0]
    grid_cell: tuple[int, int] = (1, 1)  # Coarse grid (row, col), default (1, 1)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "confidence": round(self.confidence, 4),
            "bbox": [round(c, 4) for c in self.bbox],
            "center_x_norm": round(self.center_x_norm, 4),
            "center_y_norm": round(self.center_y_norm, 4),
            "grid_cell": list(self.grid_cell),
            "timestamp": self.timestamp,
        }


@dataclass
class SceneEvent:
    """Represents a temporally confirmed or state-changed event emitted to the agent."""

    label: str
    confidence: float
    center_x_norm: float
    grid_cell: tuple[int, int]
    event_type: str  # e.g., 'confirmed_detection', 'object_moved', 'stale_object', 'hazard_path'
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    low_visibility: bool = False
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "label": self.label,
            "confidence": round(self.confidence, 4),
            "center_x_norm": round(self.center_x_norm, 4),
            "grid_cell": list(self.grid_cell),
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "low_visibility": self.low_visibility,
            "metadata": self.metadata,
        }
