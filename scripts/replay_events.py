#!/usr/bin/env python3
"""Scripted event replay generator and player for VigilAI.

Enables full demonstration of the perceive-reason-act loop on a laptop
without requiring an optical camera or GPU.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("replay_events")


def generate_scenario_events() -> list[dict[str, Any]]:
    """Build canonical demo scenarios."""
    base_19_00 = datetime.datetime(2026, 10, 10, 19, 0, 0).timestamp()

    events = [
        # SCENARIO 1: Medicine box left on counter at 19:00 dosage time
        # Requires 3 consecutive frames to confirm
        {
            "scenario": "Medication Dosage Window",
            "frame_idx": 1,
            "timestamp": base_19_00 + 0.0,
            "detections": [
                {
                    "label": "medicine box",
                    "confidence": 0.88,
                    "bbox": [0.15, 0.20, 0.35, 0.45],
                    "center_x_norm": 0.25,
                    "center_y_norm": 0.32,
                    "grid_cell": [0, 1],
                }
            ],
        },
        {
            "scenario": "Medication Dosage Window",
            "frame_idx": 2,
            "timestamp": base_19_00 + 0.1,
            "detections": [
                {
                    "label": "medicine box",
                    "confidence": 0.92,
                    "bbox": [0.15, 0.20, 0.35, 0.45],
                    "center_x_norm": 0.25,
                    "center_y_norm": 0.32,
                    "grid_cell": [0, 1],
                }
            ],
        },
        {
            "scenario": "Medication Dosage Window",
            "frame_idx": 3,
            "timestamp": base_19_00 + 0.2,
            "detections": [
                {
                    "label": "medicine box",
                    "confidence": 0.94,
                    "bbox": [0.15, 0.20, 0.35, 0.45],
                    "center_x_norm": 0.25,
                    "center_y_norm": 0.32,
                    "grid_cell": [0, 1],
                }
            ],
        },
        # SCENARIO 2: New obstacle (backpack) dropped in walking path (cell [2, 1])
        {
            "scenario": "Walking Path Obstacle",
            "frame_idx": 4,
            "timestamp": base_19_00 + 5.0,
            "detections": [
                {
                    "label": "backpack",
                    "confidence": 0.84,
                    "bbox": [0.42, 0.60, 0.62, 0.88],
                    "center_x_norm": 0.52,
                    "center_y_norm": 0.74,
                    "grid_cell": [2, 1],
                }
            ],
        },
        {
            "scenario": "Walking Path Obstacle",
            "frame_idx": 5,
            "timestamp": base_19_00 + 5.1,
            "detections": [
                {
                    "label": "backpack",
                    "confidence": 0.89,
                    "bbox": [0.42, 0.60, 0.62, 0.88],
                    "center_x_norm": 0.52,
                    "center_y_norm": 0.74,
                    "grid_cell": [2, 1],
                }
            ],
        },
        {
            "scenario": "Walking Path Obstacle",
            "frame_idx": 6,
            "timestamp": base_19_00 + 5.2,
            "detections": [
                {
                    "label": "backpack",
                    "confidence": 0.91,
                    "bbox": [0.42, 0.60, 0.62, 0.88],
                    "center_x_norm": 0.52,
                    "center_y_norm": 0.74,
                    "grid_cell": [2, 1],
                }
            ],
        },
        # SCENARIO 3: Routine background cup (non-alert worthy)
        {
            "scenario": "Routine Non-Hazard Item",
            "frame_idx": 7,
            "timestamp": base_19_00 + 10.0,
            "detections": [
                {
                    "label": "cup",
                    "confidence": 0.72,
                    "bbox": [0.70, 0.15, 0.85, 0.35],
                    "center_x_norm": 0.78,
                    "center_y_norm": 0.25,
                    "grid_cell": [0, 2],
                }
            ],
        },
        {
            "scenario": "Routine Non-Hazard Item",
            "frame_idx": 8,
            "timestamp": base_19_00 + 10.1,
            "detections": [
                {
                    "label": "cup",
                    "confidence": 0.74,
                    "bbox": [0.70, 0.15, 0.85, 0.35],
                    "center_x_norm": 0.78,
                    "center_y_norm": 0.25,
                    "grid_cell": [0, 2],
                }
            ],
        },
        {
            "scenario": "Routine Non-Hazard Item",
            "frame_idx": 9,
            "timestamp": base_19_00 + 10.2,
            "detections": [
                {
                    "label": "cup",
                    "confidence": 0.73,
                    "bbox": [0.70, 0.15, 0.85, 0.35],
                    "center_x_norm": 0.78,
                    "center_y_norm": 0.25,
                    "grid_cell": [0, 2],
                }
            ],
        },
    ]
    return events


def save_scenario_file(filepath: str = "examples/sample_events.json") -> None:
    """Save scripted scenarios to JSON file."""
    p = Path(filepath)
    p.parent.mkdir(parents=True, exist_ok=True)
    events = generate_scenario_events()
    with open(p, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2)
    logger.info("Saved %d scripted replay frames to %s", len(events), filepath)


def load_scenario_file(filepath: str = "examples/sample_events.json") -> list[dict[str, Any]]:
    """Load scripted scenario sequence from file, creating if absent."""
    p = Path(filepath)
    if not p.exists():
        save_scenario_file(filepath)
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and inspect VigilAI replay events.")
    parser.add_argument("--save", default="examples/sample_events.json", help="Output path for sample events JSON")
    args = parser.parse_args()
    save_scenario_file(args.save)
    print(f"Sample scenario events written to {args.save}")


if __name__ == "__main__":
    main()
