"""Camera capture loop running in a dedicated thread.

Evaluates frame quality (Laplacian blur and mean brightness) to signal
low-visibility conditions. All frames reside strictly in memory.
"""

from __future__ import annotations

import logging
import threading
import time

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class CameraCapture:
    """Threaded OpenCV camera capture with real-time blur and illumination analysis."""

    def __init__(
        self,
        camera_index: int = 0,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
        blur_threshold: float = 100.0,
        brightness_threshold: float = 40.0,
    ) -> None:
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.fps = fps
        self.blur_threshold = blur_threshold
        self.brightness_threshold = brightness_threshold

        self._cap: cv2.VideoCapture | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.Lock()

        self._latest_frame: np.ndarray | None = None
        self._latest_timestamp: float = 0.0
        self._low_visibility: bool = False
        self._blur_score: float = 0.0
        self._brightness_score: float = 0.0

    def start(self) -> None:
        """Start camera capture in background thread."""
        if self._running:
            return

        logger.info("Initializing camera capture on index %d...", self.camera_index)
        self._cap = cv2.VideoCapture(self.camera_index)
        if not self._cap.isOpened():
            logger.warning("Camera index %d could not be opened. Using fallback mode.", self.camera_index)

        self._running = True
        self._thread = threading.Thread(target=self._capture_worker, daemon=True, name="VigilAICameraWorker")
        self._thread.start()

    def stop(self) -> None:
        """Stop background capture and release video resource."""
        self._running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        logger.info("Camera capture stopped.")

    def __enter__(self) -> CameraCapture:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    def _assess_quality(self, frame: np.ndarray) -> tuple[float, float, bool]:
        """Compute variance of Laplacian (blur) and mean luminance (brightness)."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        mean_brightness = float(np.mean(gray))

        is_blurry = blur_var < self.blur_threshold
        is_dark = mean_brightness < self.brightness_threshold
        low_visibility = is_blurry or is_dark

        return blur_var, mean_brightness, low_visibility

    def _capture_worker(self) -> None:
        """Continuously grab frames and update quality metrics."""
        while self._running:
            if self._cap is None or not self._cap.isOpened():
                time.sleep(0.1)
                continue

            ret, frame = self._cap.read()
            if not ret or frame is None:
                time.sleep(0.05)
                continue

            blur, brightness, low_vis = self._assess_quality(frame)

            with self._lock:
                # Frames are kept purely in volatile memory
                self._latest_frame = frame
                self._latest_timestamp = time.time()
                self._blur_score = blur
                self._brightness_score = brightness
                self._low_visibility = low_vis

            # Throttle slightly according to requested target FPS
            time.sleep(max(0.001, 1.0 / self.fps - 0.005))

    def get_latest_frame(self) -> tuple[np.ndarray | None, bool, float, float]:
        """Return the most recent volatile frame and quality attributes.

        Returns:
            Tuple of (frame, low_visibility_flag, blur_score, brightness_score).
        """
        with self._lock:
            if self._latest_frame is None:
                return None, True, 0.0, 0.0
            return (
                self._latest_frame.copy(),
                self._low_visibility,
                self._blur_score,
                self._brightness_score,
            )

    def assess_frame_directly(self, frame: np.ndarray) -> tuple[bool, float, float]:
        """Convenience function to inspect any frame buffer without active camera thread."""
        blur, brightness, low_vis = self._assess_quality(frame)
        return low_vis, blur, brightness
