"""Unit tests for rule-based relevance scoring with mock clocks."""

from __future__ import annotations

import datetime

from agent.memory import AgentMemory
from agent.relevance import RelevanceScorer
from perception.events import SceneEvent


def test_medication_dose_window_high_relevance(tmp_path):
    db_file = str(tmp_path / "test_rel.db")
    memory = AgentMemory(db_path=db_file)
    scorer = RelevanceScorer(memory=memory, dose_hours=(8, 19))

    # Mock time: 19:15 (within evening dose window)
    dt_19 = datetime.datetime(2026, 10, 10, 19, 15, 0)
    ts_19 = dt_19.timestamp()

    event = SceneEvent(
        label="medicine box",
        confidence=0.92,
        center_x_norm=0.3,
        grid_cell=(0, 1),
        event_type="confirmed_detection",
        timestamp=ts_19,
    )

    assessment = scorer.score_event(event, now=ts_19)
    assert assessment.score >= 0.85
    assert assessment.priority == "high"
    assert assessment.rule_matched == "medication_dose_window"
    assert assessment.is_alert_worthy is True


def test_walking_path_obstacle_high_relevance(tmp_path):
    db_file = str(tmp_path / "test_rel_obstacle.db")
    memory = AgentMemory(db_path=db_file)
    scorer = RelevanceScorer(memory=memory, walking_path_cells=((2, 1), (1, 1)))

    dt_afternoon = datetime.datetime(2026, 10, 10, 14, 0, 0)
    ts = dt_afternoon.timestamp()

    # Backpack placed in walking corridor (cell 2, 1)
    event = SceneEvent(
        label="backpack",
        confidence=0.88,
        center_x_norm=0.5,
        grid_cell=(2, 1),
        event_type="confirmed_detection",
        timestamp=ts,
    )

    assessment = scorer.score_event(event, now=ts)
    assert assessment.score >= 0.8
    assert assessment.priority == "high"
    assert assessment.rule_matched == "walking_path_hazard"
    assert assessment.is_alert_worthy is True


def test_dismissed_feedback_lowers_score(tmp_path):
    db_file = str(tmp_path / "test_rel_feedback.db")
    memory = AgentMemory(db_path=db_file)
    scorer = RelevanceScorer(memory=memory, walking_path_cells=((2, 1),))

    dt = datetime.datetime(2026, 10, 10, 15, 0, 0)
    ts = dt.timestamp()

    event = SceneEvent(
        label="shoes",
        confidence=0.85,
        center_x_norm=0.5,
        grid_cell=(2, 1),
        event_type="confirmed_detection",
        timestamp=ts,
    )

    # Initial score without dismissals
    initial_assessment = scorer.score_event(event, now=ts)
    assert initial_assessment.score >= 0.8

    # User dismisses shoes twice
    memory.record_feedback("shoes", "dismiss", timestamp=ts - 300)
    memory.record_feedback("shoes", "dismiss", timestamp=ts - 100)

    # Second assessment: penalized by 2 * 0.20 = -0.40
    penalized_assessment = scorer.score_event(event, now=ts)
    assert penalized_assessment.score <= initial_assessment.score - 0.35


def test_quiet_hours_suppression(tmp_path):
    db_file = str(tmp_path / "test_rel_quiet.db")
    memory = AgentMemory(db_path=db_file)
    # Quiet hours between 22:00 and 07:00
    scorer = RelevanceScorer(memory=memory, quiet_hours=("22:00", "07:00"))

    # Time: 23:30 (inside quiet hours)
    dt_night = datetime.datetime(2026, 10, 10, 23, 30, 0)
    ts_night = dt_night.timestamp()

    event = SceneEvent(
        label="cup",
        confidence=0.80,
        center_x_norm=0.8,
        grid_cell=(1, 2),
        event_type="object_moved",
        timestamp=ts_night,
    )

    assessment = scorer.score_event(event, now=ts_night)
    assert assessment.quiet_hours_suppressed is True
    assert assessment.is_alert_worthy is False
