"""Temporal tracker with multi-frame confirmation, cooldowns, and spatial placement tracking."""

from __future__ import annotations

import logging
import time

from perception.events import Detection, SceneEvent

logger = logging.getLogger(__name__)


class ObjectTrack:
    """Internal state for tracking a specific object label across consecutive frames."""

    def __init__(self, label: str, grid_cell: tuple[int, int], center_x_norm: float) -> None:
        self.label = label
        self.consecutive_frames = 1
        self.last_seen_timestamp = time.time()
        self.last_alert_timestamp = 0.0
        self.last_grid_cell = grid_cell
        self.last_center_x_norm = center_x_norm
        self.confirmed = False

    def update(self, detection: Detection, now: float) -> None:
        self.consecutive_frames += 1
        self.last_seen_timestamp = now
        self.last_grid_cell = detection.grid_cell
        self.last_center_x_norm = detection.center_x_norm


class TemporalTracker:
    """Tracks objects across frames, enforcing 3-frame confirmation and cooldowns."""

    def __init__(
        self,
        confirm_frames: int = 3,
        cooldown_s: float = 120.0,
        usual_places: dict[str, tuple[int, int]] | None = None,
    ) -> None:
        """Args:

        confirm_frames: Number of consecutive frames needed before confirmation (default: 3).
        cooldown_s: Minimum seconds between successive alert emissions for the same object.
        usual_places: Dictionary of {label: (row, col)} representing baseline locations.
        """
        self.confirm_frames = confirm_frames
        self.cooldown_s = cooldown_s
        self.usual_places: dict[str, tuple[int, int]] = usual_places or {}

        # Active tracks keyed by object label
        self.tracks: dict[str, ObjectTrack] = {}

    def set_usual_place(self, label: str, grid_cell: tuple[int, int]) -> None:
        """Register the baseline usual grid cell for an object label."""
        self.usual_places[label] = grid_cell

    def process_frame(
        self,
        detections: list[Detection],
        now: float | None = None,
        low_visibility: bool = False,
    ) -> list[SceneEvent]:
        """Ingest detections for the current frame and return any confirmed or state-change events.

        Args:
            detections: List of Detection instances from detector.
            now: Current timestamp (defaults to time.time()).
            low_visibility: Whether frame was flagged as low visibility.

        Returns:
            List of SceneEvent ready for the reasoning agent.
        """
        current_time = now if now is not None else time.time()
        events: list[SceneEvent] = []

        seen_labels: set[str] = set()

        for det in detections:
            label = det.label
            seen_labels.add(label)

            if label not in self.tracks:
                # New track
                self.tracks[label] = ObjectTrack(
                    label=label,
                    grid_cell=det.grid_cell,
                    center_x_norm=det.center_x_norm,
                )
            else:
                self.tracks[label].update(det, current_time)

            track = self.tracks[label]

            # Check if confirmation threshold reached
            if track.consecutive_frames >= self.confirm_frames:
                is_first_confirmation = not track.confirmed
                track.confirmed = True

                # Check cooldown
                time_since_last_alert = current_time - track.last_alert_timestamp
                is_cooldown_expired = time_since_last_alert >= self.cooldown_s

                if is_first_confirmation or is_cooldown_expired:
                    # Check if displaced from usual place
                    event_type = "confirmed_detection"
                    usual_cell = self.usual_places.get(label)
                    if usual_cell is not None and usual_cell != det.grid_cell:
                        event_type = "object_moved"

                    events.append(
                        SceneEvent(
                            label=label,
                            confidence=det.confidence,
                            center_x_norm=det.center_x_norm,
                            grid_cell=det.grid_cell,
                            event_type=event_type,
                            timestamp=current_time,
                            low_visibility=low_visibility,
                            metadata={
                                "consecutive_frames": track.consecutive_frames,
                                "usual_cell": list(usual_cell) if usual_cell else None,
                            },
                        )
                    )
                    track.last_alert_timestamp = current_time

        # Reset consecutive frames for tracks not seen in current frame
        for label, track in list(self.tracks.items()):
            if label not in seen_labels:
                track.consecutive_frames = 0
                track.confirmed = False

        return events
