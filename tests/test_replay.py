"""Unit tests for the scripted replay pipeline."""

from __future__ import annotations

from perception.events import Detection
from perception.tracker import TemporalTracker
from scripts.replay_events import generate_scenario_events


def test_replay_scenario_events_structure():
    events = generate_scenario_events()
    assert len(events) >= 6

    # Verify scenario 1 has 3 consecutive medicine box frames
    med_frames = [e for e in events if e.get("scenario") == "Medication Dosage Window"]
    assert len(med_frames) == 3

    tracker = TemporalTracker(confirm_frames=3, cooldown_s=120.0)

    confirmed_list = []
    for f in med_frames:
        raw_det = f["detections"][0]
        det = Detection(
            label=raw_det["label"],
            confidence=raw_det["confidence"],
            bbox=tuple(raw_det["bbox"]),
            center_x_norm=raw_det["center_x_norm"],
            grid_cell=tuple(raw_det["grid_cell"]),
            timestamp=f["timestamp"],
        )
        conf = tracker.process_frame([det], now=f["timestamp"])
        confirmed_list.extend(conf)

    # Only the 3rd frame produces a confirmed event
    assert len(confirmed_list) == 1
    assert confirmed_list[0].label == "medicine box"
