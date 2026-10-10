"""Unit tests for spatial action planning and safety gates."""

from __future__ import annotations

from actuation.calibration import ServoCalibration
from agent.planner import SpatialPlanner
from perception.events import SceneEvent


def test_angle_mapping_and_clamping():
    # Center=90, HFOV=90
    calib = ServoCalibration(center_deg=90.0, hfov_deg=90.0, min_deg=10.0, max_deg=170.0)
    planner = SpatialPlanner(calibration=calib)

    # Center object: x=0.5 -> 90.0 deg
    assert planner.calculate_angle(0.5) == 90.0

    # Left object: x=0.0 -> 90 + (0.0 - 0.5) * 90 = 45.0 deg
    assert planner.calculate_angle(0.0) == 45.0

    # Right object: x=1.0 -> 90 + (1.0 - 0.5) * 90 = 135.0 deg
    assert planner.calculate_angle(1.0) == 135.0

    # Out of range test: wide HFOV=200 -> clamps to 10 and 170
    wide_calib = ServoCalibration(center_deg=90.0, hfov_deg=250.0, min_deg=10.0, max_deg=170.0)
    wide_planner = SpatialPlanner(calibration=wide_calib)
    assert wide_planner.calculate_angle(0.0) == 10.0
    assert wide_planner.calculate_angle(1.0) == 170.0


def test_direction_verbal_cues():
    planner = SpatialPlanner()
    assert planner.determine_direction(0.1) == "on your left"
    assert planner.determine_direction(0.5) == "straight ahead"
    assert planner.determine_direction(0.9) == "on your right"


def test_safety_gates_refusals():
    planner = SpatialPlanner()
    normal_event = SceneEvent(
        label="bottle",
        confidence=0.9,
        center_x_norm=0.2,
        grid_cell=(1, 0),
        event_type="confirmed_detection",
        low_visibility=False,
    )

    # 1. Normal execution -> permitted
    plan = planner.plan_action(normal_event, "Your medication is ready.")
    assert plan.can_act is True
    assert plan.refusal_reason is None
    assert "on your left" in plan.speech_text.lower()

    # 2. Low visibility gate -> refused
    dark_event = SceneEvent(
        label="bottle",
        confidence=0.9,
        center_x_norm=0.2,
        grid_cell=(1, 0),
        event_type="confirmed_detection",
        low_visibility=True,
    )
    plan_dark = planner.plan_action(dark_event, "Your medication is ready.")
    assert plan_dark.can_act is False
    assert "visibility" in plan_dark.refusal_reason.lower()

    # 3. Muted gate -> refused
    plan_muted = planner.plan_action(normal_event, "Your medication is ready.", is_muted=True)
    assert plan_muted.can_act is False
    assert "muted" in plan_muted.refusal_reason.lower()

    # 4. Cooldown gate -> refused
    plan_cd = planner.plan_action(normal_event, "Your medication is ready.", in_cooldown=True)
    assert plan_cd.can_act is False
    assert "cooldown" in plan_cd.refusal_reason.lower()
