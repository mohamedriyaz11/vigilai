"""Fast-path heuristic relevance scoring for VigilAI.

Scores detected events using contextual rules, time-of-day routine statistics,
and user dismissal history without requiring LLM inference.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass

from agent.memory import AgentMemory
from perception.events import SceneEvent

logger = logging.getLogger(__name__)

# Canonical object classifications
MEDICATION_LABELS = {"medicine box", "pill bottle", "medication", "pill", "medicine", "bottle"}
HAZARD_OBSTACLE_LABELS = {"backpack", "suitcase", "box", "shoes", "chair", "wire", "obstacle", "slippers"}


@dataclass
class RelevanceAssessment:
    """Outcome of rule-based contextual relevance scoring."""

    score: float  # Normalized score [0.0, 1.0]
    priority: str  # 'low', 'medium', 'high', 'critical'
    rule_matched: str
    reason: str
    is_alert_worthy: bool
    quiet_hours_suppressed: bool = False

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 3),
            "priority": self.priority,
            "rule_matched": self.rule_matched,
            "reason": self.reason,
            "is_alert_worthy": self.is_alert_worthy,
            "quiet_hours_suppressed": self.quiet_hours_suppressed,
        }


class RelevanceScorer:
    """Evaluates whether an observed scene event warrants proactively alerting the user."""

    def __init__(
        self,
        memory: AgentMemory,
        quiet_hours: tuple[str, str] = ("22:00", "07:00"),
        walking_path_cells: tuple[tuple[int, int], ...] = ((2, 1), (1, 1)),
        stale_threshold_s: float = 1800.0,  # 30 minutes
        dose_hours: tuple[int, ...] = (8, 9, 19, 20),
    ) -> None:
        self.memory = memory
        self.quiet_hours = quiet_hours
        self.walking_path_cells = set(walking_path_cells)
        self.stale_threshold_s = stale_threshold_s
        self.dose_hours = set(dose_hours)

    def _is_in_quiet_hours(self, dt: datetime.datetime) -> bool:
        """Check if given datetime falls into quiet hours window."""
        start_h, start_m = map(int, self.quiet_hours[0].split(":"))
        end_h, end_m = map(int, self.quiet_hours[1].split(":"))

        current_minutes = dt.hour * 60 + dt.minute
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m

        if start_minutes <= end_minutes:
            return start_minutes <= current_minutes <= end_minutes
        # Window spans across midnight (e.g. 22:00 to 07:00)
        return current_minutes >= start_minutes or current_minutes <= end_minutes

    def score_event(
        self,
        event: SceneEvent,
        now: float | None = None,
    ) -> RelevanceAssessment:
        """Calculate relevance score for a given scene event."""
        current_time = now if now is not None else event.timestamp
        dt = datetime.datetime.fromtimestamp(current_time)
        hour = dt.hour

        label_lower = event.label.lower()
        score = 0.3
        priority = "low"
        rule_matched = "default_background"
        reason = f"Detected {event.label} in background monitoring."

        # 1. Rule: Medication during dose window
        if label_lower in MEDICATION_LABELS:
            # Check configured dose hours or learned routine histogram
            histogram = self.memory.get_hour_histogram(event.label)
            learned_routine_active = histogram.get(hour, 0) > 0
            if hour in self.dose_hours or learned_routine_active:
                score = 0.90
                priority = "high"
                rule_matched = "medication_dose_window"
                reason = f"Medication ({event.label}) visible during scheduled dosage hour ({hour}:00)."

        # 2. Rule: Obstacle / tripping hazard in walking path
        elif event.grid_cell in self.walking_path_cells or label_lower in HAZARD_OBSTACLE_LABELS:
            score = 0.85
            priority = "high"
            rule_matched = "walking_path_hazard"
            reason = f"Potential hazard ({event.label}) detected in standard walking corridor."

        # 3. Rule: Object displaced from usual place
        elif event.event_type == "object_moved":
            score = 0.65
            priority = "medium"
            rule_matched = "object_displaced"
            reason = f"{event.label.capitalize()} has moved from its usual location."

        # Feedback attenuation: if user dismissed recent alerts for this label, penalize score
        dismissals = self.memory.get_recent_dismissals(event.label, now=current_time)
        if dismissals > 0:
            penalty = min(0.6, dismissals * 0.20)
            score = max(0.0, score - penalty)
            logger.info("Applied feedback penalty of -%.2f to %s due to %d recent dismissals", penalty, event.label, dismissals)

        # Re-derive priority category after penalty
        if score >= 0.8:
            priority = "high"
        elif score >= 0.5:
            priority = "medium"
        else:
            priority = "low"

        # Check quiet hours suppression (unless priority is critical >= 0.95)
        in_quiet = self._is_in_quiet_hours(dt)
        quiet_hours_suppressed = False
        is_alert_worthy = score >= 0.5

        if in_quiet and is_alert_worthy and score < 0.95:
            quiet_hours_suppressed = True
            is_alert_worthy = False
            reason += " [Suppressed due to active quiet hours]"

        return RelevanceAssessment(
            score=score,
            priority=priority,
            rule_matched=rule_matched,
            reason=reason,
            is_alert_worthy=is_alert_worthy,
            quiet_hours_suppressed=quiet_hours_suppressed,
        )
