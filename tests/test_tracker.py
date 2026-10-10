"""Unit tests for TemporalTracker (confirmation, cooldown, usual place)."""

from __future__ import annotations

from perception.events import Detection
from perception.tracker import TemporalTracker


def test_confirmation_requires_three_consecutive_frames():
    tracker = TemporalTracker(confirm_frames=3, cooldown_s=120.0)
    det = Detection(
        label="medicine box",
        confidence=0.88,
        bbox=(0.2, 0.3, 0.4, 0.5),
        center_x_norm=0.3,
        grid_cell=(1, 1),
    )

    t0 = 1000.0

    # Frame 1: consecutive = 1 -> no event
    events = tracker.process_frame([det], now=t0)
    assert len(events) == 0

    # Frame 2: consecutive = 2 -> no event
    events = tracker.process_frame([det], now=t0 + 0.1)
    assert len(events) == 0

    # Frame 3: consecutive = 3 -> confirmed event emitted!
    events = tracker.process_frame([det], now=t0 + 0.2)
    assert len(events) == 1
    assert events[0].label == "medicine box"
    assert events[0].event_type == "confirmed_detection"


def test_interruption_resets_confirmation_counter():
    tracker = TemporalTracker(confirm_frames=3, cooldown_s=120.0)
    det = Detection(
        label="cup",
        confidence=0.75,
        bbox=(0.1, 0.1, 0.2, 0.2),
        center_x_norm=0.15,
        grid_cell=(0, 0),
    )

    # Frame 1 & 2 seen
    tracker.process_frame([det], now=100.0)
    tracker.process_frame([det], now=100.1)

    # Frame 3: missed/empty -> resets
    events = tracker.process_frame([], now=100.2)
    assert len(events) == 0

    # Frame 4: seen again -> consecutive starts back at 1
    events = tracker.process_frame([det], now=100.3)
    assert len(events) == 0

    # Frame 5: seen again -> consecutive = 2
    events = tracker.process_frame([det], now=100.4)
    assert len(events) == 0

    # Frame 6: seen again -> consecutive = 3 -> emits
    events = tracker.process_frame([det], now=100.5)
    assert len(events) == 1


def test_cooldown_suppresses_repeats():
    tracker = TemporalTracker(confirm_frames=3, cooldown_s=120.0)
    det = Detection(
        label="keys",
        confidence=0.9,
        bbox=(0.4, 0.4, 0.6, 0.6),
        center_x_norm=0.5,
        grid_cell=(1, 1),
    )

    t0 = 500.0
    # Frames 1, 2, 3 -> confirmed at t0 + 2
    tracker.process_frame([det], now=t0)
    tracker.process_frame([det], now=t0 + 1)
    events = tracker.process_frame([det], now=t0 + 2)
    assert len(events) == 1

    # Frame 4 at t0 + 10s (inside 120s cooldown) -> suppressed
    events = tracker.process_frame([det], now=t0 + 10.0)
    assert len(events) == 0

    # Frame at t0 + 120s -> still suppressed (since alert was at t0 + 2, 118s elapsed)
    events = tracker.process_frame([det], now=t0 + 120.0)
    assert len(events) == 0

    # Frame at t0 + 123s -> 121s elapsed (> 120s cooldown) -> emits alert again
    events = tracker.process_frame([det], now=t0 + 123.0)
    assert len(events) == 1
    assert events[0].label == "keys"


def test_usual_place_tracking():
    tracker = TemporalTracker(confirm_frames=3, cooldown_s=120.0)
    tracker.set_usual_place("glasses", (0, 0))

    # Detect glasses in usual cell (0, 0)
    det_usual = Detection(
        label="glasses",
        confidence=0.9,
        bbox=(0.0, 0.0, 0.2, 0.2),
        center_x_norm=0.1,
        grid_cell=(0, 0),
    )
    tracker.process_frame([det_usual], now=1.0)
    tracker.process_frame([det_usual], now=2.0)
    events = tracker.process_frame([det_usual], now=3.0)
    assert len(events) == 1
    assert events[0].event_type == "confirmed_detection"

    # Reset tracker with new object moved to cell (2, 2)
    tracker_moved = TemporalTracker(confirm_frames=3, cooldown_s=120.0)
    tracker_moved.set_usual_place("glasses", (0, 0))

    det_moved = Detection(
        label="glasses",
        confidence=0.9,
        bbox=(0.7, 0.7, 0.9, 0.9),
        center_x_norm=0.8,
        grid_cell=(2, 2),
    )
    tracker_moved.process_frame([det_moved], now=1.0)
    tracker_moved.process_frame([det_moved], now=2.0)
    events_moved = tracker_moved.process_frame([det_moved], now=3.0)
    assert len(events_moved) == 1
    assert events_moved[0].event_type == "object_moved"
