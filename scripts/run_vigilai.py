#!/usr/bin/env python3
"""Main entry point for VigilAI — An Agentic Embodied Companion.

Executes the continuous Perceive -> Reason -> Act loop.
Supports laptop camera mode or scripted event replay with simulated or physical actuation.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any

# Ensure repository root is on PYTHONPATH
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import yaml

from actuation.calibration import ServoCalibration
from actuation.sim_servo import SimulatedServo
from agent.explainer import EventExplainer
from agent.graph import VigilAIGraph
from agent.llm import CloudLLMProvider, LocalLLMProvider, NoneLLMProvider
from agent.memory import AgentMemory
from agent.planner import SpatialPlanner
from agent.relevance import RelevanceScorer
from perception.camera import CameraCapture
from perception.detector import ObjectDetector
from perception.events import Detection
from perception.tracker import TemporalTracker
from scripts.replay_events import load_scenario_file
from speech.tts import TTSDispatcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("VigilAI")


def load_config(config_path: str = "config/default.yaml") -> dict[str, Any]:
    """Load configuration YAML file."""
    p = Path(config_path)
    if not p.exists():
        logger.warning("Config file '%s' not found. Using defaults.", config_path)
        return {}
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_agent_pipeline(args: argparse.Namespace, config: dict[str, Any]) -> tuple[VigilAIGraph, Any, Any]:
    """Initialize memory, reasoning graph, actuator, and TTS engine."""
    cfg_agent = config.get("agent", {})
    cfg_servo = config.get("servo", {})
    cfg_priv = config.get("privacy", {})

    # 1. Long-term episodic memory
    db_path = cfg_agent.get("sqlite_db_path", "vigilai_memory.db")
    memory = AgentMemory(db_path=db_path)

    # 2. Fast-path relevance scorer
    quiet_hours = tuple(cfg_agent.get("quiet_hours", ["22:00", "07:00"]))
    scorer = RelevanceScorer(memory=memory, quiet_hours=quiet_hours)

    # 3. Pluggable LLM provider
    provider_name = args.llm or cfg_agent.get("llm_provider", "none")
    if provider_name == "local":
        model_path = cfg_agent.get("local_model_path", "")
        llm = LocalLLMProvider(model_path=model_path)
    elif provider_name == "cloud":
        cloud_enabled = cfg_priv.get("cloud_llm_enabled", False)
        cloud_model = cfg_agent.get("cloud_model_name", "gpt-4o-mini")
        llm = CloudLLMProvider(model=cloud_model, enabled=cloud_enabled)
    else:
        llm = NoneLLMProvider()

    explainer = EventExplainer(llm_provider=llm)

    # 4. Calibration & Spatial Planner
    calib = ServoCalibration.load("calibration.json")
    planner = SpatialPlanner(calibration=calib)

    # 5. Actuation: Simulated or Serial Hardware
    if args.sim_servo or not args.port:
        logger.info("Initializing Simulated Servo (Terminal / ASCII pointer)...")
        actuator = SimulatedServo(
            min_deg=cfg_servo.get("min_deg", 10.0),
            max_deg=cfg_servo.get("max_deg", 170.0),
            center_deg=cfg_servo.get("center_deg", 90.0),
            slew_dps=cfg_servo.get("slew_dps", 120.0),
        )
    else:
        logger.info("Connecting to physical ESP32 servo on port %s...", args.port)
        from actuation.serial_servo import SerialServo

        actuator = SerialServo(port=args.port, baudrate=cfg_servo.get("baudrate", 115200))

    # 6. Audio Text-to-Speech Dispatcher
    tts_enabled = not args.no_tts
    tts = TTSDispatcher(enabled=tts_enabled)

    # 7. LangGraph Execution Engine
    graph = VigilAIGraph(
        memory=memory,
        relevance_scorer=scorer,
        explainer=explainer,
        planner=planner,
        servo=actuator,
        tts_dispatcher=tts,
    )

    return graph, actuator, tts


def run_replay_mode(args: argparse.Namespace, config: dict[str, Any]) -> None:
    """Execute scripted event replay scenario."""
    logger.info("Starting VigilAI in REPLAY MODE with scenario '%s'...", args.replay)
    graph, actuator, tts = build_agent_pipeline(args, config)

    tracker = TemporalTracker(
        confirm_frames=config.get("detection", {}).get("confirm_frames", 3),
        cooldown_s=config.get("detection", {}).get("cooldown_s", 120.0),
    )

    events_data = load_scenario_file(args.replay)
    logger.info("Loaded %d replay frames.", len(events_data))

    for item in events_data:
        frame_idx = item.get("frame_idx", 0)
        scenario_title = item.get("scenario", "Scenario")
        ts = item.get("timestamp", time.time())
        raw_detections = item.get("detections", [])

        # Parse detections
        detections: list[Detection] = []
        for d in raw_detections:
            detections.append(
                Detection(
                    label=d["label"],
                    confidence=d["confidence"],
                    bbox=tuple(d["bbox"]),
                    center_x_norm=d["center_x_norm"],
                    center_y_norm=d.get("center_y_norm", 0.5),
                    grid_cell=tuple(d.get("grid_cell", [1, 1])),
                    timestamp=ts,
                )
            )

        print(f"\n--- [Frame #{frame_idx} | {scenario_title}] ---")
        confirmed_events = tracker.process_frame(detections, now=ts)

        if not confirmed_events:
            print(f"Perception: Tracking {len(detections)} candidate object(s)... (Waiting for 3-frame confirmation)")
        else:
            for ce in confirmed_events:
                print(f"Perception: CONFIRMED EVENT -> {ce.label} (type={ce.event_type}, x={ce.center_x_norm})")

        # Step graph state machine
        state = graph.step(confirmed_events, now=ts)
        decision = state.get("decision")
        print(f"Agent Decision: {decision.upper()}")

        if decision == "alert":
            plan = state.get("action_plan", {})
            print(f"Action Taken  : Angle={plan.get('target_angle_deg')} deg, Cue='{plan.get('direction_cue')}'")
            print(f"Vocalized     : \"{plan.get('speech_text')}\"")

        time.sleep(0.4)

    logger.info("Replay completed successfully.")
    tts.stop()


def run_live_camera_mode(args: argparse.Namespace, config: dict[str, Any]) -> None:
    """Execute live continuous loop with OpenCV webcam and YOLOv8n detector."""
    logger.info("Starting VigilAI in LIVE CAMERA MODE (Camera index: %d)...", args.camera)
    graph, actuator, tts = build_agent_pipeline(args, config)

    cfg_det = config.get("detection", {})
    detector = ObjectDetector(
        input_size=cfg_det.get("input_size", 320),
        min_confidence=cfg_det.get("min_confidence", 0.6),
    )
    tracker = TemporalTracker(
        confirm_frames=cfg_det.get("confirm_frames", 3),
        cooldown_s=cfg_det.get("cooldown_s", 120.0),
    )

    with CameraCapture(
        camera_index=args.camera,
        blur_threshold=cfg_det.get("blur_threshold", 100.0),
        brightness_threshold=cfg_det.get("brightness_threshold", 40.0),
    ) as cam:
        logger.info("VigilAI Active. Press Ctrl+C to terminate.")
        try:
            while True:
                frame, low_vis, blur_score, bright_score = cam.get_latest_frame()
                if frame is None:
                    time.sleep(0.05)
                    continue

                # Run inference strictly in memory
                detections = detector.detect(frame)
                now = time.time()
                confirmed_events = tracker.process_frame(detections, now=now, low_visibility=low_vis)

                if confirmed_events:
                    state = graph.step(confirmed_events, now=now, low_visibility=low_vis)
                    if state.get("decision") == "alert":
                        plan = state.get("action_plan", {})
                        logger.info("ALERT TRIGGERED: %s", plan.get("speech_text"))

                # Keepalive heartbeat to actuator
                actuator.heartbeat()
                time.sleep(0.05)  # 20 Hz loop limit

        except KeyboardInterrupt:
            logger.info("Shutting down VigilAI gracefully...")
        finally:
            actuator.park()
            tts.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="VigilAI Ambient Companion Runtime")
    parser.add_argument("--sim-servo", action="store_true", default=True, help="Use simulated servo (default)")
    parser.add_argument("--port", type=str, default=None, help="ESP32 serial port (e.g. COM5 or /dev/ttyUSB0)")
    parser.add_argument("--camera", type=int, default=0, help="Camera device index (default: 0)")
    parser.add_argument("--no-tts", action="store_true", help="Disable voice audio synthesis")
    parser.add_argument("--llm", choices=["none", "local", "cloud"], default="none", help="Reasoning verbalizer")
    parser.add_argument("--config", default="config/default.yaml", help="Path to config YAML")
    parser.add_argument("--replay", type=str, default=None, help="Path to replay scenario JSON file")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.replay:
        run_replay_mode(args, config)
    else:
        run_live_camera_mode(args, config)


if __name__ == "__main__":
    main()
