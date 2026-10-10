"""SQLite episodic memory and time-of-day routine modeling for VigilAI."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AgentMemory:
    """Persistent SQLite store for detected events, routine hour histograms, and feedback."""

    def __init__(self, db_path: str = "vigilai_memory.db") -> None:
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create tables if they do not exist."""
        parent = Path(self.db_path).parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Events log table (symbolic events only, NO raw frames)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE,
                    label TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    center_x_norm REAL NOT NULL,
                    grid_row INTEGER NOT NULL,
                    grid_col INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    hour_of_day INTEGER NOT NULL,
                    metadata_json TEXT
                )
            """)

            # 2. Routine time-of-day histograms (24 hours per label)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS routines (
                    label TEXT NOT NULL,
                    hour INTEGER NOT NULL,
                    frequency INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (label, hour)
                )
            """)

            # 3. User feedback table (dismissals, snoozes, confirmations)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT NOT NULL,
                    feedback_type TEXT NOT NULL,  -- 'dismiss', 'snooze', 'confirm'
                    timestamp REAL NOT NULL,
                    reason TEXT
                )
            """)
            conn.commit()

    def log_event(
        self,
        event_id: str,
        label: str,
        confidence: float,
        center_x_norm: float,
        grid_cell: tuple[int, int],
        event_type: str,
        timestamp: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a confirmed symbolic event and increment its routine histogram."""
        ts = timestamp if timestamp is not None else time.time()
        hour = time.localtime(ts).tm_hour

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO events (
                    event_id, label, confidence, center_x_norm, grid_row, grid_col,
                    event_type, timestamp, hour_of_day, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    label,
                    confidence,
                    center_x_norm,
                    grid_cell[0],
                    grid_cell[1],
                    event_type,
                    ts,
                    hour,
                    json.dumps(metadata or {}),
                ),
            )

            # Update routine histogram for (label, hour)
            cursor.execute(
                """
                INSERT INTO routines (label, hour, frequency)
                VALUES (?, ?, 1)
                ON CONFLICT(label, hour) DO UPDATE SET frequency = frequency + 1
                """,
                (label, hour),
            )
            conn.commit()

    def get_hour_histogram(self, label: str) -> dict[int, int]:
        """Return the 24-hour frequency histogram for a given object label."""
        histogram = dict.fromkeys(range(24), 0)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT hour, frequency FROM routines WHERE label = ?", (label,))
            for row in cursor.fetchall():
                histogram[row["hour"]] = row["frequency"]
        return histogram

    def record_feedback(
        self,
        label: str,
        feedback_type: str,
        timestamp: float | None = None,
        reason: str = "",
    ) -> None:
        """Store user interaction (e.g. dismissing an alert)."""
        ts = timestamp if timestamp is not None else time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO feedback (label, feedback_type, timestamp, reason) VALUES (?, ?, ?, ?)",
                (label, feedback_type, ts, reason),
            )
            conn.commit()

    def get_recent_dismissals(self, label: str, lookback_s: float = 3600.0, now: float | None = None) -> int:
        """Count how many times alerts for this label were dismissed in the lookback window."""
        current_time = now if now is not None else time.time()
        cutoff = current_time - lookback_s
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) as count FROM feedback WHERE label = ? AND feedback_type = 'dismiss' AND timestamp >= ?",
                (label, cutoff),
            )
            row = cursor.fetchone()
            return int(row["count"]) if row else 0

    def get_recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve recent symbolic events for dashboard display."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT event_id, label, confidence, center_x_norm, grid_row, grid_col,
                       event_type, timestamp, hour_of_day, metadata_json
                FROM events
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )
            events = []
            for row in cursor.fetchall():
                events.append({
                    "event_id": row["event_id"],
                    "label": row["label"],
                    "confidence": row["confidence"],
                    "center_x_norm": row["center_x_norm"],
                    "grid_cell": [row["grid_row"], row["grid_col"]],
                    "event_type": row["event_type"],
                    "timestamp": row["timestamp"],
                    "hour": row["hour_of_day"],
                    "metadata": json.loads(row["metadata_json"] or "{}"),
                })
            return events
