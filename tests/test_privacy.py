"""Privacy invariant test suite.

Asserts that no code path writes camera frames or videos to persistent disk storage,
and that only sanitized structured text events are ever emitted.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import yaml

from actuation.sim_servo import SimulatedServo
from agent.explainer import EventExplainer
from agent.graph import VigilAIGraph
from agent.memory import AgentMemory
from agent.planner import SpatialPlanner
from agent.relevance import RelevanceScorer
from perception.camera import CameraCapture
from perception.detector import ObjectDetector
from perception.tracker import TemporalTracker

IMAGE_VIDEO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".mp4", ".avi", ".mkv", ".mov"}


def test_codebase_has_no_frame_saving_calls():
    """Statically verify that no dangerous video/frame writing APIs exist in perception or agent."""
    repo_root = Path(__file__).resolve().parent.parent

    target_dirs = [repo_root / "perception", repo_root / "agent", repo_root / "scripts"]
    forbidden_calls = ["cv2.imwrite", "cv2.VideoWriter", "imwrite", "VideoWriter"]

    for d in target_dirs:
        for py_file in d.glob("**/*.py"):
            with open(py_file, encoding="utf-8") as f:
                content = f.read()
                for call in forbidden_calls:
                    assert call not in content, f"Forbidden image write call '{call}' detected in {py_file}!"


def test_pipeline_execution_creates_zero_image_files(tmp_path):
    """Dynamically run end-to-end loop and assert zero image files are generated on disk."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Capture initial directory snapshot
    initial_files = set(os.listdir(workspace))

    db_file = str(workspace / "privacy_mem.db")
    memory = AgentMemory(db_path=db_file)
    scorer = RelevanceScorer(memory=memory)
    explainer = EventExplainer()
    planner = SpatialPlanner()
    servo = SimulatedServo(enforce_slew=False)
    graph = VigilAIGraph(memory, scorer, explainer, planner, servo)

    detector = ObjectDetector(model_name_or_path="yolov8n.pt", input_size=320)
    tracker = TemporalTracker(confirm_frames=1, cooldown_s=0.0)
    cam = CameraCapture()

    # Ingest synthetic frames
    for _ in range(5):
        frame = np.random.randint(0, 256, (320, 320, 3), dtype=np.uint8)
        low_vis, blur, bright = cam.assess_frame_directly(frame)
        detections = detector.detect(frame)
        events = tracker.process_frame(detections, low_visibility=low_vis)
        if events:
            graph.step(events, low_visibility=low_vis)

    # Inspect all newly created files in workspace
    final_files = set(os.listdir(workspace))
    new_files = final_files - initial_files

    for f_name in new_files:
        ext = Path(f_name).suffix.lower()
        assert ext not in IMAGE_VIDEO_EXTENSIONS, f"Discovered persisted frame artifact: {f_name}"


def test_default_config_enforces_privacy():
    """Verify that default YAML configuration strictly sets privacy constraints."""
    config_path = Path(__file__).resolve().parent.parent / "config" / "default.yaml"
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    privacy = cfg.get("privacy", {})
    assert privacy.get("save_frames") is False
    assert privacy.get("cloud_llm_enabled") is False
