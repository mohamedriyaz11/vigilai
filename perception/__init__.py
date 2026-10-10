"""VigilAI Perception Package."""

from perception.camera import CameraCapture
from perception.detector import ObjectDetector
from perception.events import Detection, SceneEvent
from perception.tracker import ObjectTrack, TemporalTracker

__all__ = [
    "CameraCapture",
    "ObjectDetector",
    "Detection",
    "SceneEvent",
    "TemporalTracker",
    "ObjectTrack",
]
