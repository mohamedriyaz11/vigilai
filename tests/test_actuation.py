"""Unit tests for simulated servo actuation and calibration."""

from __future__ import annotations

import pytest

from actuation.calibration import ServoCalibration
from actuation.sim_servo import SimulatedServo


def test_simulated_servo_point_and_limits():
    servo = SimulatedServo(min_deg=10.0, max_deg=170.0, center_deg=90.0, enforce_slew=False)

    # Point to valid angle
    assert servo.point(120.0) is True
    assert 119.0 <= servo.current_angle <= 121.0

    # Point below soft limit (e.g. 5 deg -> clamped to 10 deg)
    assert servo.point(5.0) is True
    assert servo.target_angle == 10.0
    assert servo.current_angle == 10.0

    # Point above soft limit (e.g. 180 deg -> clamped to 170 deg)
    assert servo.point(180.0) is True
    assert servo.target_angle == 170.0
    assert servo.current_angle == 170.0


def test_simulated_servo_mute_and_park():
    servo = SimulatedServo()
    servo.set_muted(True)
    assert servo.status()["muted"] is True
    # Commands must be rejected while muted
    assert servo.point(45.0) is False

    servo.set_muted(False)
    servo.point(130.0)
    assert servo.park() is True
    assert servo.current_angle == 90.0
    assert servo.status()["state"] == "parked"


def test_servo_calibration_save_load_and_fitting(tmp_path):
    calib_file = str(tmp_path / "test_calib.json")
    original = ServoCalibration(center_deg=88.5, hfov_deg=85.0, angle_offset=1.5, invert_direction=True)
    original.save(calib_file)

    loaded = ServoCalibration.load(calib_file)
    assert loaded.center_deg == 88.5
    assert loaded.hfov_deg == 85.0
    assert loaded.angle_offset == 1.5
    assert loaded.invert_direction is True

    # Test two-point fitting
    # x1=0.2 -> 63 deg, x2=0.8 -> 117 deg
    # dx=0.6, da=54 -> slope = 90 deg HFOV, center at 0.5 is 90 deg
    fitted = ServoCalibration.fit_two_points(x1_norm=0.2, angle1_deg=63.0, x2_norm=0.8, angle2_deg=117.0)
    assert 89.0 <= fitted.hfov_deg <= 91.0
    assert 89.0 <= fitted.center_deg <= 91.0

    with pytest.raises(ValueError):
        ServoCalibration.fit_two_points(0.5, 90.0, 0.5, 90.0)
