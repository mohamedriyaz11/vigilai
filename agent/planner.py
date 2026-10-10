"""Spatial action planning: camera pixel-to-angle mapping and safety gating."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from actuation.calibration import ServoCalibration
from perception.events import SceneEvent

logger = logging.getLogger(__name__)


@dataclass
class ActionPlan:
    """Complete multimodal action plan ready for execution by actuators and speech."""

    target_angle_deg: float
    direction_cue: str
    speech_text: str
    can_act: bool
    refusal_reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "target_angle_deg": round(self.target_angle_deg, 1),
            "direction_cue": self.direction_cue,
            "speech_text": self.speech_text,
            "can_act": self.can_act,
            "refusal_reason": self.refusal_reason,
        }


class SpatialPlanner:
    """Calculates servo target angle and direction cues while enforcing safety gates."""

    def __init__(self, calibration: ServoCalibration | None = None) -> None:
        self.calib = calibration or ServoCalibration()

    def calculate_angle(self, center_x_norm: float) -> float:
        """Map normalized horizontal position [0.0, 1.0] to clamped servo angle."""
        # Baseline centered deviation: (x - 0.5)
        rel_x = center_x_norm - 0.5
        if self.calib.invert_direction:
            rel_x = -rel_x

        raw_angle = self.calib.center_deg + (rel_x * self.calib.hfov_deg) + self.calib.angle_offset
        clamped_angle = max(self.calib.min_deg, min(self.calib.max_deg, raw_angle))
        return clamped_angle

    def determine_direction(self, center_x_norm: float) -> str:
        """Derive spatial direction verbal cue for the user."""
        if center_x_norm < 0.38:
            return "on your left"
        if center_x_norm > 0.62:
            return "on your right"
        return "straight ahead"

    def plan_action(
        self,
        event: SceneEvent,
        message: str,
        is_muted: bool = False,
        in_cooldown: bool = False,
    ) -> ActionPlan:
        """Construct multimodal action plan and evaluate all safety gates."""
        target_angle = self.calculate_angle(event.center_x_norm)
        direction_cue = self.determine_direction(event.center_x_norm)

        # Prepend direction cue into speech if not already present
        if direction_cue not in message.lower():
            full_speech = f"{direction_cue.capitalize()}: {message}"
        else:
            full_speech = message

        # Safety Gate 1: Low Visibility (Dark or Blurry)
        if event.low_visibility:
            return ActionPlan(
                target_angle_deg=self.calib.center_deg,
                direction_cue=direction_cue,
                speech_text=full_speech,
                can_act=False,
                refusal_reason="Safety gate: Refused action due to low camera visibility.",
            )

        # Safety Gate 2: Hardware / Software Mute
        if is_muted:
            return ActionPlan(
                target_angle_deg=self.calib.center_deg,
                direction_cue=direction_cue,
                speech_text=full_speech,
                can_act=False,
                refusal_reason="Safety gate: Actuation muted by user.",
            )

        # Safety Gate 3: Temporal Cooldown Active
        if in_cooldown:
            return ActionPlan(
                target_angle_deg=self.calib.center_deg,
                direction_cue=direction_cue,
                speech_text=full_speech,
                can_act=False,
                refusal_reason="Safety gate: Object is inside alert cooldown window.",
            )

        return ActionPlan(
            target_angle_deg=target_angle,
            direction_cue=direction_cue,
            speech_text=full_speech,
            can_act=True,
            refusal_reason=None,
        )
