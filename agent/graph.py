"""LangGraph state machine implementing the Perceive-Reason-Act loop for VigilAI."""

from __future__ import annotations

import logging
import time
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from actuation.servo_interface import ServoInterface
from agent.explainer import EventExplainer
from agent.memory import AgentMemory
from agent.planner import SpatialPlanner
from agent.relevance import RelevanceScorer
from perception.events import SceneEvent

logger = logging.getLogger(__name__)


class VigilAIState(TypedDict):
    """LangGraph state schema representing world context and agent deliberative flow."""

    incoming_events: list[SceneEvent]
    current_event: SceneEvent | None
    time_of_day: float
    is_muted: bool
    low_visibility: bool
    relevance_assessment: dict[str, Any] | None
    decision: str  # 'alert' or 'suppress'
    explanation_text: str | None
    action_plan: dict[str, Any] | None
    execution_result: dict[str, Any] | None


class VigilAIGraph:
    """Encapsulates compiled LangGraph state graph for VigilAI."""

    def __init__(
        self,
        memory: AgentMemory,
        relevance_scorer: RelevanceScorer,
        explainer: EventExplainer,
        planner: SpatialPlanner,
        servo: ServoInterface | None = None,
        tts_dispatcher: Any | None = None,
    ) -> None:
        self.memory = memory
        self.scorer = relevance_scorer
        self.explainer = explainer
        self.planner = planner
        self.servo = servo
        self.tts = tts_dispatcher

        self.app = self._build_graph()

    def _node_perceive(self, state: VigilAIState) -> dict[str, Any]:
        """Node 1: Select the primary active event from perception."""
        events = state.get("incoming_events", [])
        if not events:
            return {"current_event": None, "decision": "suppress"}

        # Select highest confidence event
        primary = max(events, key=lambda e: e.confidence)
        return {"current_event": primary}

    def _node_update_world_state(self, state: VigilAIState) -> dict[str, Any]:
        """Node 2: Enrich state with time of day and memory context."""
        ts = state.get("time_of_day") or time.time()
        return {"time_of_day": ts}

    def _node_score_relevance(self, state: VigilAIState) -> dict[str, Any]:
        """Node 3: Heuristic scoring fast-path."""
        event = state.get("current_event")
        if event is None:
            return {"relevance_assessment": None, "decision": "suppress"}

        assessment = self.scorer.score_event(event, now=state.get("time_of_day"))
        return {"relevance_assessment": assessment.to_dict()}

    def _node_decide(self, state: VigilAIState) -> dict[str, Any]:
        """Node 4: Priority and safety gating decision."""
        assessment = state.get("relevance_assessment")
        if not assessment or not assessment.get("is_alert_worthy", False):
            return {"decision": "suppress"}
        return {"decision": "alert"}

    def _node_explain(self, state: VigilAIState) -> dict[str, Any]:
        """Node 5: Verbal explanation synthesis."""
        event = state.get("current_event")
        assessment = state.get("relevance_assessment") or {}
        if event is None:
            return {"explanation_text": ""}

        direction = self.planner.determine_direction(event.center_x_norm)
        reason = assessment.get("reason", "")
        urgency = assessment.get("priority", "low")
        rule_matched = assessment.get("rule_matched", "default")

        text = self.explainer.explain(
            label=event.label,
            direction=direction,
            reason=reason,
            urgency=urgency,
            rule_matched=rule_matched,
        )
        return {"explanation_text": text}

    def _node_act(self, state: VigilAIState) -> dict[str, Any]:
        """Node 6: Multimodal pointing and acoustic dispatch."""
        event = state.get("current_event")
        text = state.get("explanation_text", "")
        if event is None or not text:
            return {"action_plan": None, "execution_result": None}

        plan = self.planner.plan_action(
            event=event,
            message=text,
            is_muted=state.get("is_muted", False),
        )

        exec_res = {"pointed": False, "spoken": False, "angle": plan.target_angle_deg}

        if plan.can_act:
            if self.servo:
                self.servo.point(plan.target_angle_deg)
                exec_res["pointed"] = True
            if self.tts:
                self.tts.say(plan.speech_text)
                exec_res["spoken"] = True

        return {"action_plan": plan.to_dict(), "execution_result": exec_res}

    def _node_log(self, state: VigilAIState) -> dict[str, Any]:
        """Node 7: Record episodic memory and routine histograms."""
        event = state.get("current_event")
        if event:
            self.memory.log_event(
                event_id=event.event_id,
                label=event.label,
                confidence=event.confidence,
                center_x_norm=event.center_x_norm,
                grid_cell=event.grid_cell,
                event_type=event.event_type,
                timestamp=state.get("time_of_day"),
                metadata={
                    "decision": state.get("decision"),
                    "relevance": state.get("relevance_assessment"),
                    "explanation": state.get("explanation_text"),
                },
            )
        return {}

    def _route_decision(self, state: VigilAIState) -> str:
        """Conditional routing branch after decision node."""
        if state.get("decision") == "alert":
            return "explain"
        return "log"

    def _build_graph(self):
        """Construct and compile LangGraph state workflow."""
        builder = StateGraph(VigilAIState)

        # Register nodes
        builder.add_node("perceive", self._node_perceive)
        builder.add_node("update_world_state", self._node_update_world_state)
        builder.add_node("score_relevance", self._node_score_relevance)
        builder.add_node("decide", self._node_decide)
        builder.add_node("explain", self._node_explain)
        builder.add_node("act", self._node_act)
        builder.add_node("log", self._node_log)

        # Connect edges
        builder.set_entry_point("perceive")
        builder.add_edge("perceive", "update_world_state")
        builder.add_edge("update_world_state", "score_relevance")
        builder.add_edge("score_relevance", "decide")

        # Conditional branching based on decision
        builder.add_conditional_edges(
            "decide",
            self._route_decision,
            {
                "explain": "explain",
                "log": "log",
            },
        )

        builder.add_edge("explain", "act")
        builder.add_edge("act", "log")
        builder.add_edge("log", END)

        return builder.compile()

    def step(
        self,
        events: list[SceneEvent],
        now: float | None = None,
        is_muted: bool = False,
        low_visibility: bool = False,
    ) -> VigilAIState:
        """Execute one complete cycle of the state machine."""
        initial_state: VigilAIState = {
            "incoming_events": events,
            "current_event": None,
            "time_of_day": now or time.time(),
            "is_muted": is_muted,
            "low_visibility": low_visibility,
            "relevance_assessment": None,
            "decision": "suppress",
            "explanation_text": None,
            "action_plan": None,
            "execution_result": None,
        }
        return self.app.invoke(initial_state)
