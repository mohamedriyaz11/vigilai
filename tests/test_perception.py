"""Unit tests for the perception module (Camera, Detector, Events)."""

from __future__ import annotations

import numpy as np

from perception.camera import CameraCapture
from perception.detector import ObjectDetector
from perception.events import Detection, SceneEvent


def test_detection_dataclass():
    det = Detection(
        label="bottle",
        confidence=0.85,
        bbox=(0.1, 0.2, 0.3, 0.4),
        center_x_norm=0.2,
        center_y_norm=0.3,
        grid_cell=(0, 0),
    )
    d = det.to_dict()
    assert d["label"] == "bottle"
    assert d["confidence"] == 0.85
    assert d["grid_cell"] == [0, 0]
    assert d["center_x_norm"] == 0.2


def test_scene_event_dataclass():
    evt = SceneEvent(
        label="medicine box",
        confidence=0.92,
        center_x_norm=0.25,
        grid_cell=(1, 0),
        event_type="confirmed_detection",
        low_visibility=False,
    )
    d = evt.to_dict()
    assert d["label"] == "medicine box"
    assert d["event_type"] == "confirmed_detection"
    assert d["low_visibility"] is False
    assert "event_id" in d


def test_camera_quality_blur_and_brightness():
    cam = CameraCapture(blur_threshold=100.0, brightness_threshold=40.0)

    # 1. Pitch black image -> must be flagged dark / low visibility
    dark_frame = np.zeros((240, 320, 3), dtype=np.uint8)
    low_vis_dark, blur_dark, bright_dark = cam.assess_frame_directly(dark_frame)
    assert bright_dark < 1.0
    assert low_vis_dark is True

    # 2. Uniform gray image -> blur is 0 (variance of laplacian of constant is 0) -> blurry
    flat_frame = np.full((240, 320, 3), 128, dtype=np.uint8)
    low_vis_flat, blur_flat, bright_flat = cam.assess_frame_directly(flat_frame)
    assert blur_flat < 1.0
    assert bright_flat > 100.0
    assert low_vis_flat is True

    # 3. High frequency sharp checkerboard -> sharp and adequately bright
    checkers = np.indices((240, 320)).sum(axis=0) % 2 * 255
    sharp_frame = np.stack([checkers.astype(np.uint8)] * 3, axis=-1)
    low_vis_sharp, blur_sharp, bright_sharp = cam.assess_frame_directly(sharp_frame)
    assert blur_sharp > 500.0
    assert bright_sharp > 50.0
    assert low_vis_sharp is False


def test_detector_empty_frame():
    detector = ObjectDetector(model_name_or_path="yolov8n.pt")
    # Should safely return empty list on None or empty frame
    assert detector.detect(None) == []
    empty_frame = np.empty((0, 0, 3), dtype=np.uint8)
    assert detector.detect(empty_frame) == []
