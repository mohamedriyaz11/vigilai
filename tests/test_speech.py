"""Unit tests for the speech text-to-speech dispatcher."""

from __future__ import annotations

from speech.tts import TTSDispatcher


def test_tts_dispatcher_queue_and_interruption():
    dispatcher = TTSDispatcher(enabled=True)
    # Ensure background worker is stopped so we can examine the queue deterministically
    dispatcher.stop()

    dispatcher.say("First announcement", priority=5)
    dispatcher.say("Critical warning", priority=1)
    dispatcher.say("Casual reminder", priority=8)

    # Pop from priority queue: priority 1 must come out first!
    p1, _, msg1 = dispatcher._queue.get_nowait()
    assert p1 == 1
    assert msg1 == "Critical warning"

    p2, _, msg2 = dispatcher._queue.get_nowait()
    assert p2 == 5
    assert msg2 == "First announcement"

    # Test interruption: clears queue
    assert not dispatcher._queue.empty()
    dispatcher.interrupt()
    assert dispatcher._queue.empty()


def test_tts_disabled_mode():
    dispatcher = TTSDispatcher(enabled=False)
    # Calling say should not crash or queue when disabled
    dispatcher.say("Muted message")
    assert dispatcher._queue.empty()
    dispatcher.stop()
