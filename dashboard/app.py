"""Flask telemetry dashboard for VigilAI.

Displays real-time symbolic detections, agent decision logs, and interaction controls.
Protected by token authentication. Does NOT transmit or display any video frames.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from functools import wraps
from typing import Any

from flask import Flask, jsonify, render_template, request
from flask_sock import Sock

from agent.memory import AgentMemory

logger = logging.getLogger(__name__)


def create_app(
    memory: AgentMemory | None = None,
    auth_token: str | None = None,
    state_provider: Any | None = None,
) -> Flask:
    """Factory function for Flask dashboard application."""
    app = Flask(__name__, template_folder="templates", static_folder="static")
    sock = Sock(app)

    token = auth_token or os.getenv("VIGILAI_DASHBOARD_TOKEN", "vigil-dev-token-change-in-production")
    db_mem = memory or AgentMemory()

    # Active connected websocket clients
    ws_clients: set[Any] = set()
    ws_lock = threading.Lock()

    def token_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            req_token = request.args.get("token") or request.headers.get("X-VigilAI-Token")
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                req_token = auth_header.split(" ", 1)[1]

            if not req_token or req_token != token:
                return jsonify({"error": "Unauthorized: Invalid or missing VigilAI token"}), 401
            return f(*args, **kwargs)

        return decorated

    @app.route("/")
    def index():
        req_token = request.args.get("token", "")
        return render_template("index.html", token=req_token)

    @app.route("/api/status")
    @token_required
    def api_status():
        """Provide telemetry and recent event summaries."""
        recent_events = db_mem.get_recent_events(limit=25)
        status_info = {
            "status": "online",
            "privacy_mode": "Strict Ephemeral RAM (Zero Video Stored/Transmitted)",
            "recent_events": recent_events,
        }
        if state_provider is not None and hasattr(state_provider, "get_dashboard_telemetry"):
            status_info.update(state_provider.get_dashboard_telemetry())
        return jsonify(status_info)

    @app.route("/api/feedback", methods=["POST"])
    @token_required
    def api_feedback():
        """Record user feedback (dismiss, snooze, confirm)."""
        data = request.get_json() or {}
        label = data.get("label", "unknown")
        fb_type = data.get("feedback_type", "dismiss")
        reason = data.get("reason", "manual web UI action")

        db_mem.record_feedback(label=label, feedback_type=fb_type, reason=reason)
        logger.info("Recorded %s feedback for label '%s'", fb_type, label)

        # Notify websockets of updated feedback
        broadcast_ws({"type": "feedback_logged", "label": label, "feedback_type": fb_type})
        return jsonify({"success": True, "label": label, "feedback_type": fb_type})

    @app.route("/api/control/mute", methods=["POST"])
    @token_required
    def api_control_mute():
        """Toggle system software mute."""
        data = request.get_json() or {}
        is_muted = data.get("muted", True)
        if state_provider is not None and hasattr(state_provider, "set_muted"):
            state_provider.set_muted(is_muted)
        broadcast_ws({"type": "mute_changed", "muted": is_muted})
        return jsonify({"success": True, "muted": is_muted})

    @sock.route("/ws")
    def ws_endpoint(ws):
        """WebSocket connection for live streaming agent decisions."""
        req_token = request.args.get("token")
        if req_token != token:
            ws.send(json.dumps({"error": "Unauthorized WebSocket connection"}))
            ws.close()
            return

        with ws_lock:
            ws_clients.add(ws)

        try:
            while True:
                msg = ws.receive()
                if msg is None:
                    break
        except Exception:
            pass
        finally:
            with ws_lock:
                ws_clients.discard(ws)

    def broadcast_ws(payload: dict[str, Any]) -> None:
        """Push real-time state update to all active web clients."""
        with ws_lock:
            to_remove = set()
            for ws in ws_clients:
                try:
                    ws.send(json.dumps(payload))
                except Exception:
                    to_remove.add(ws)
            ws_clients.difference_update(to_remove)

    app.broadcast_ws = broadcast_ws
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=False)
