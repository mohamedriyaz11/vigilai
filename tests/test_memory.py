"""Unit tests for SQLite episodic memory and routine histograms."""

from __future__ import annotations

import datetime

from agent.memory import AgentMemory


def test_sqlite_event_logging_and_histograms(tmp_path):
    db_file = str(tmp_path / "test_memory.db")
    memory = AgentMemory(db_path=db_file)

    # Log 3 events at 19:30 (hour 19)
    fixed_dt_19 = datetime.datetime(2026, 10, 10, 19, 30, 0)
    ts_19 = fixed_dt_19.timestamp()

    memory.log_event(
        event_id="evt-1",
        label="medicine box",
        confidence=0.91,
        center_x_norm=0.35,
        grid_cell=(1, 1),
        event_type="confirmed_detection",
        timestamp=ts_19,
    )
    memory.log_event(
        event_id="evt-2",
        label="medicine box",
        confidence=0.93,
        center_x_norm=0.35,
        grid_cell=(1, 1),
        event_type="confirmed_detection",
        timestamp=ts_19 + 60,
    )

    # Log 1 event at 08:15 (hour 8)
    fixed_dt_8 = datetime.datetime(2026, 10, 10, 8, 15, 0)
    ts_8 = fixed_dt_8.timestamp()

    memory.log_event(
        event_id="evt-3",
        label="medicine box",
        confidence=0.88,
        center_x_norm=0.35,
        grid_cell=(1, 1),
        event_type="confirmed_detection",
        timestamp=ts_8,
    )

    hist = memory.get_hour_histogram("medicine box")
    assert hist[19] == 2
    assert hist[8] == 1
    assert hist[12] == 0

    recent = memory.get_recent_events(limit=10)
    assert len(recent) == 3
    assert recent[0]["event_id"] in {"evt-1", "evt-2", "evt-3"}


def test_feedback_recording_and_dismissal_counts(tmp_path):
    db_file = str(tmp_path / "test_feedback.db")
    memory = AgentMemory(db_path=db_file)

    now = 10000.0
    memory.record_feedback("keys", "dismiss", timestamp=now - 500, reason="user clicked dismiss")
    memory.record_feedback("keys", "dismiss", timestamp=now - 100, reason="user clicked dismiss")
    memory.record_feedback("keys", "confirm", timestamp=now - 50, reason="helpful")

    # Within past 3600 seconds, 2 dismissals recorded
    dismissals = memory.get_recent_dismissals("keys", lookback_s=3600, now=now)
    assert dismissals == 2

    # In a narrow window (last 60s), only 0 dismissals
    assert memory.get_recent_dismissals("keys", lookback_s=60, now=now) == 0
