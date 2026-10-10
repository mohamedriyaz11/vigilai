"""Unit tests for LangGraph state machine, explainer fallback, and privacy invariants."""

from __future__ import annotations

import datetime
from typing import Any

from actuation.sim_servo import SimulatedServo
from agent.explainer import EventExplainer
from agent.graph import VigilAIGraph
from agent.llm import LLMProvider
from agent.memory import AgentMemory
from agent.planner import SpatialPlanner
from agent.relevance import RelevanceScorer
from perception.events import SceneEvent


class MockFaultyLLM(LLMProvider):
    """Simulates an LLM throwing errors or returning hallucinated invalid markdown."""

    def __init__(self, mode: str = "error") -> None:
        self.mode = mode
        self.last_received_payload: dict[str, Any] | None = None

    def generate_explanation(self, event_summary: dict[str, Any]) -> str | None:
        self.last_received_payload = event_summary
        if self.mode == "error":
            raise TimeoutError("Simulated LLM call timed out")
        elif self.mode == "code_leakage":
            return "```json\n{'hallucinated': True}\n```"
        elif self.mode == "empty":
            return ""
        return "Valid concise explanation."


class MockTTS:
    """Mock text-to-speech recorder."""

    def __init__(self) -> None:
        self.spoken_messages: list[str] = []

    def say(self, message: str) -> None:
        self.spoken_messages.append(message)


def test_explainer_fallback_on_llm_error():
    mock_llm = MockFaultyLLM(mode="error")
    explainer = EventExplainer(llm_provider=mock_llm)

    text = explainer.explain(
        label="medicine box",
        direction="on your left",
        reason="Scheduled dose window",
        urgency="high",
        rule_matched="medication_dose_window",
    )
    # Must gracefully fall back to deterministic template
    assert "medicine box is on the counter" in text


def test_explainer_fallback_on_malformed_llm_output():
    mock_llm = MockFaultyLLM(mode="code_leakage")
    explainer = EventExplainer(llm_provider=mock_llm)

    text = explainer.explain(
        label="backpack",
        direction="straight ahead",
        reason="Hazard in path",
        urgency="high",
        rule_matched="walking_path_hazard",
    )
    # Code leakage rejected -> template fallback
    assert "watch your step" in text


def test_explainer_critical_urgency_bypasses_llm():
    mock_llm = MockFaultyLLM(mode="valid")
    explainer = EventExplainer(llm_provider=mock_llm)

    text = explainer.explain(
        label="medicine box",
        direction="on your left",
        reason="Critical medication reminder",
        urgency="critical",
        rule_matched="medication_dose_window",
    )
    # Critical alerts must never invoke external LLM
    assert mock_llm.last_received_payload is None
    assert "medicine box is on the counter" in text


def test_privacy_payload_strictly_text(tmp_path):
    mock_llm = MockFaultyLLM(mode="valid")
    explainer = EventExplainer(llm_provider=mock_llm)

    explainer.explain(
        label="keys",
        direction="on your right",
        reason="Displaced item",
        urgency="medium",
        rule_matched="object_displaced",
    )

    payload = mock_llm.last_received_payload
    assert payload is not None
    # Hard privacy verification: payload contains only text summaries, zero binary frames
    assert "frame" not in payload
    assert "image" not in payload
    assert "raw_bytes" not in payload
    assert isinstance(payload["label"], str)


def test_langgraph_end_to_end_alert_flow(tmp_path):
    db_file = str(tmp_path / "graph_test.db")
    memory = AgentMemory(db_path=db_file)
    scorer = RelevanceScorer(memory=memory, dose_hours=(19,))
    explainer = EventExplainer()
    planner = SpatialPlanner()
    servo = SimulatedServo(enforce_slew=False)
    tts = MockTTS()

    graph = VigilAIGraph(
        memory=memory,
        relevance_scorer=scorer,
        explainer=explainer,
        planner=planner,
        servo=servo,
        tts_dispatcher=tts,
    )

    # 1. Trigger alert-worthy event (Medication box at 19:15)
    dt_19 = datetime.datetime(2026, 10, 10, 19, 15, 0)
    ts_19 = dt_19.timestamp()

    event_med = SceneEvent(
        label="medicine box",
        confidence=0.92,
        center_x_norm=0.25,  # left
        grid_cell=(0, 1),
        event_type="confirmed_detection",
        timestamp=ts_19,
    )

    result_state = graph.step([event_med], now=ts_19)

    assert result_state["decision"] == "alert"
    assert result_state["action_plan"] is not None
    assert result_state["action_plan"]["can_act"] is True
    assert result_state["execution_result"]["pointed"] is True
    assert result_state["execution_result"]["spoken"] is True
    assert len(tts.spoken_messages) == 1
    assert "on your left" in tts.spoken_messages[0].lower()

    # 2. Trigger low-relevance event -> should suppress
    event_cup = SceneEvent(
        label="cup",
        confidence=0.70,
        center_x_norm=0.5,
        grid_cell=(0, 0),
        event_type="confirmed_detection",
        timestamp=ts_19,
    )

    result_state_cup = graph.step([event_cup], now=ts_19)
    assert result_state_cup["decision"] == "suppress"
    assert result_state_cup["action_plan"] is None
