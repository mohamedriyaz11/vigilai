"""VigilAI Perception Package."""

from perception.camera import CameraCapture
from perception.detector import ObjectDetector
from perception.events import Detection, SceneEvent

__all__ = [
    "CameraCapture",
    "ObjectDetector",
    "Detection",
    "SceneEvent",
]
