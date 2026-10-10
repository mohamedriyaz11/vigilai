"""Unit tests for Flask dashboard endpoints and token authentication."""

from __future__ import annotations

from agent.memory import AgentMemory
from dashboard.app import create_app


def test_dashboard_token_authentication(tmp_path):
    db_file = str(tmp_path / "test_dash.db")
    memory = AgentMemory(db_path=db_file)
    test_token = "secure-test-token-123"

    app = create_app(memory=memory, auth_token=test_token)
    client = app.test_client()

    # 1. Unauthenticated request to API -> 401
    resp_unauth = client.get("/api/status")
    assert resp_unauth.status_code == 401
    assert "Unauthorized" in resp_unauth.get_json()["error"]

    # 2. Authenticated with query param -> 200
    resp_query = client.get(f"/api/status?token={test_token}")
    assert resp_query.status_code == 200
    data = resp_query.get_json()
    assert data["status"] == "online"
    assert "privacy_mode" in data

    # 3. Authenticated with Authorization Bearer header -> 200
    resp_header = client.get("/api/status", headers={"Authorization": f"Bearer {test_token}"})
    assert resp_header.status_code == 200

    # 4. Authenticated with X-VigilAI-Token header -> 200
    resp_custom = client.get("/api/status", headers={"X-VigilAI-Token": test_token})
    assert resp_custom.status_code == 200


def test_dashboard_feedback_and_mute_endpoints(tmp_path):
    db_file = str(tmp_path / "test_dash_actions.db")
    memory = AgentMemory(db_path=db_file)
    test_token = "action-token-456"

    app = create_app(memory=memory, auth_token=test_token)
    client = app.test_client()

    # Log feedback
    resp_fb = client.post(
        f"/api/feedback?token={test_token}",
        json={"label": "backpack", "feedback_type": "dismiss", "reason": "not an obstacle"},
    )
    assert resp_fb.status_code == 200
    assert memory.get_recent_dismissals("backpack") == 1

    # Toggle mute
    resp_mute = client.post(
        f"/api/control/mute?token={test_token}",
        json={"muted": True},
    )
    assert resp_mute.status_code == 200
    assert resp_mute.get_json()["muted"] is True
