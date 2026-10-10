"""Non-blocking text-to-speech engine with priority queuing and interruptibility."""

from __future__ import annotations

import logging
import queue
import threading
import time

logger = logging.getLogger(__name__)


class TTSDispatcher:
    """Non-blocking audio speech synthesizer using pyttsx3 with graceful mock fallback."""

    def __init__(self, enabled: bool = True, rate: int = 165) -> None:
        self.enabled = enabled
        self.rate = rate

        self._queue: queue.PriorityQueue[tuple[int, float, str]] = queue.PriorityQueue()
        self._running = False
        self._thread: threading.Thread | None = None
        self._engine = None

        if self.enabled:
            self._init_engine()
            self.start()

    def _init_engine(self) -> None:
        """Initialize pyttsx3 synthesizer."""
        try:
            import pyttsx3

            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self.rate)
            logger.info("Initialized pyttsx3 offline TTS engine.")
        except Exception as exc:
            logger.warning("Could not initialize system audio TTS (%s). Audio will be simulated via console logs.", exc)
            self._engine = None

    def start(self) -> None:
        """Start background audio worker thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True, name="VigilAITTSWorker")
        self._thread.start()

    def stop(self) -> None:
        """Halt worker thread and drain queue."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._engine = None

    def say(self, text: str, priority: int = 5) -> None:
        """Queue an utterance.

        Lower priority number indicates higher urgency (1 = Critical, 10 = Low).
        """
        if not self.enabled:
            logger.info("[SPEECH-MUTED] %s", text)
            return

        # Push to priority queue (priority, timestamp, text)
        self._queue.put((priority, time.time(), text))

    def interrupt(self) -> None:
        """Clear pending utterances to prioritize an urgent alert."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break
        if self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass
        logger.info("Speech queue interrupted and cleared.")

    def _worker(self) -> None:
        """Consume messages and vocalize one utterance at a time."""
        while self._running:
            try:
                priority, ts, utterance = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            logger.info("[VOICE OUT] (Priority %d): \"%s\"", priority, utterance)

            if self._engine is not None:
                try:
                    self._engine.say(utterance)
                    self._engine.runAndWait()
                except Exception as exc:
                    logger.warning("TTS speech synthesis error (%s). Falling back.", exc)
            else:
                # Simulation mode: brief sleep proportional to utterance length
                simulated_duration = max(0.2, len(utterance) * 0.03)
                time.sleep(simulated_duration)

            self._queue.task_done()
