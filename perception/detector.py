"""YOLOv8n object detection wrapper running at 320x320 resolution.

Complies with the VigilAI privacy specification: video frames remain strictly
in volatile memory and are discarded immediately after feature extraction.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from perception.events import Detection

logger = logging.getLogger(__name__)


class ObjectDetector:
    """YOLOv8n object detector wrapper with NCNN / ONNX support and 320px input."""

    def __init__(
        self,
        model_name_or_path: str = "yolov8n.pt",
        input_size: int = 320,
        min_confidence: float = 0.6,
        grid_rows: int = 3,
        grid_cols: int = 3,
        use_ncnn: bool = False,
    ) -> None:
        self.model_name_or_path = model_name_or_path
        self.input_size = input_size
        self.min_confidence = min_confidence
        self.grid_rows = grid_rows
        self.grid_cols = grid_cols
        self.use_ncnn = use_ncnn

        self._model: Any = None
        self._load_model()

    def _load_model(self) -> None:
        """Load YOLO model from ultralytics."""
        try:
            from ultralytics import YOLO

            target_path = self.model_name_or_path
            if self.use_ncnn:
                ncnn_path = Path(self.model_name_or_path).with_suffix("_ncnn_model")
                if ncnn_path.exists():
                    target_path = str(ncnn_path)
                    logger.info("Using exported NCNN model: %s", target_path)
                else:
                    logger.warning("NCNN model %s not found. Falling back to base weights.", ncnn_path)

            logger.info("Loading YOLO detector: %s (input size: %d)", target_path, self.input_size)
            self._model = YOLO(target_path)
        except Exception as exc:
            logger.warning("Could not load ultralytics YOLO model (%s). Fallback to mock mode.", exc)
            self._model = None

    def export_ncnn(self) -> str:
        """Export current model to NCNN format for accelerated edge inference."""
        if self._model is None:
            raise RuntimeError("Base YOLO model is not loaded; cannot export to NCNN.")
        logger.info("Exporting model to NCNN format at %dpx...", self.input_size)
        exported_path = self._model.export(format="ncnn", imgsz=self.input_size)
        return str(exported_path)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Run object detection on a volatile BGR frame.

        Args:
            frame: Raw BGR image as numpy array.

        Returns:
            List of confirmed Detection objects passing the confidence threshold.
        """
        if frame is None or frame.size == 0:
            return []

        if self._model is None:
            # Fallback for environments without weights downloaded or mock passes
            return []

        h, w = frame.shape[:2]
        if h == 0 or w == 0:
            return []

        try:
            # Run inference without saving artifacts or printing verbose output
            results = self._model.predict(
                source=frame,
                imgsz=self.input_size,
                conf=self.min_confidence,
                verbose=False,
                save=False,
            )
        except Exception as exc:
            logger.error("Inference failed: %s", exc)
            return []

        detections: list[Detection] = []
        if not results:
            return detections

        result = results[0]
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return detections

        for box in boxes:
            conf = float(box.conf[0].item())
            if conf < self.min_confidence:
                continue

            cls_id = int(box.cls[0].item())
            label = self._model.names.get(cls_id, f"class_{cls_id}")

            # Normalized bounding box coordinates [x1, y1, x2, y2]
            xyxy = box.xyxy[0].tolist()
            x1_norm = max(0.0, min(1.0, xyxy[0] / w))
            y1_norm = max(0.0, min(1.0, xyxy[1] / h))
            x2_norm = max(0.0, min(1.0, xyxy[2] / w))
            y2_norm = max(0.0, min(1.0, xyxy[3] / h))

            cx_norm = (x1_norm + x2_norm) / 2.0
            cy_norm = (y1_norm + y2_norm) / 2.0

            # Calculate coarse grid cell (row, col)
            row = min(self.grid_rows - 1, int(cy_norm * self.grid_rows))
            col = min(self.grid_cols - 1, int(cx_norm * self.grid_cols))

            detections.append(
                Detection(
                    label=label,
                    confidence=conf,
                    bbox=(x1_norm, y1_norm, x2_norm, y2_norm),
                    center_x_norm=cx_norm,
                    center_y_norm=cy_norm,
                    grid_cell=(row, col),
                )
            )

        return detections
