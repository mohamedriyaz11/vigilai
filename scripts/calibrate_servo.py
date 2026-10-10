#!/usr/bin/env python3
"""Servo angular calibration utility for VigilAI.

Enables empirical two-point or center/HFOV alignment between camera coordinates
and servo pointing angles, saving the profile to calibration.json.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from actuation.calibration import ServoCalibration

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("calibrate_servo")


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate VigilAI servo angle parameters.")
    parser.add_argument("--output", default="calibration.json", help="Path to save calibration file")
    parser.add_argument("--center", type=float, default=90.0, help="Neutral center angle in degrees")
    parser.add_argument("--hfov", type=float, default=90.0, help="Horizontal field of view in degrees")
    parser.add_argument("--two-point", nargs=4, type=float, metavar=("X1", "A1", "X2", "A2"),
                        help="Fit two points: x1_norm angle1_deg x2_norm angle2_deg")
    parser.add_argument("--invert", action="store_true", help="Invert left/right pointing direction")
    args = parser.parse_args()

    if args.two_point:
        x1, a1, x2, a2 = args.two_point
        logger.info("Computing calibration from points: (%0.2f, %0.1f°) and (%0.2f, %0.1f°)", x1, a1, x2, a2)
        calib = ServoCalibration.fit_two_points(x1, a1, x2, a2)
    else:
        calib = ServoCalibration(
            center_deg=args.center,
            hfov_deg=args.hfov,
            invert_direction=args.invert,
        )

    calib.save(args.output)
    print("\n" + "=" * 45)
    print(" VIGILAI SERVO CALIBRATION RECORDED")
    print("=" * 45)
    print(f" Output Path       : {Path(args.output).resolve()}")
    print(f" Center Angle      : {calib.center_deg}°")
    print(f" Horizontal FOV    : {calib.hfov_deg}°")
    print(f" Invert Direction  : {calib.invert_direction}")
    print(f" Min Soft Limit    : {calib.min_deg}°")
    print(f" Max Soft Limit    : {calib.max_deg}°")
    print("=" * 45 + "\n")


if __name__ == "__main__":
    main()
