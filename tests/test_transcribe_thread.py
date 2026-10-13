"""Whisper on its own thread during a chained run (progressive lenses, Phase 3).

``aiter_transcribe_sessions`` runs ``iter_transcribe_sessions`` on one daemon
thread so the event loop keeps working while a file decodes.
"""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import patch

import pytest

from bristlenose.stages import s05_transcribe
from bristlenose.stages.s05_transcribe import SessionTranscription, aiter_transcribe_sessions


def _collect(gen_fn, **kw):
    """Run the iterator over a stub backend; what came out, and on which threads."""
    seen: dict[str, object] = {"items": [], "progress_threads": set()}

    async def main():
        loop_thread = threading.current_thread()
        seen["loop_thread"] = loop_thread

        def on_progress(i, total):
            seen["progress_threads"].add(threading.current_thread())  # type: ignore[union-attr]

        async for done in aiter_transcribe_sessions([], None, on_progress=on_progress, **kw):  # type: ignore[arg-type]
            seen["items"].append(done.session_id)  # type: ignore[union-attr]

    with patch.object(s05_transcribe, "iter_transcribe_sessions", gen_fn):
        asyncio.run(main())
    return seen


def test_sessions_arrive_in_order_and_callbacks_run_on_the_loop() -> None:
    threads: list[threading.Thread] = []

    def _gen(_sessions, _settings, *, on_progress=None, on_segment=None):
        threads.append(threading.current_thread())
        for i, sid in enumerate(("s1", "s2", "s3"), start=1):
            on_progress(i, 3)
            yield SessionTranscription(sid, [])

    finished: list[float] = []
    seen = _collect(_gen, on_finished=finished.append)
    assert seen["items"] == ["s1", "s2", "s3"]
    assert threads[0] is not threading.main_thread() and threads[0].daemon
    assert seen["progress_threads"] == {seen["loop_thread"]}, "no callback from the worker"
    assert len(finished) == 1


def test_the_loop_works_while_a_file_decodes() -> None:
    """The point of the thread: a coroutine makes progress during a decode."""
    release = threading.Event()
    ticks: list[int] = []
    released: list[bool] = []

    def _gen(_sessions, _settings, *, on_progress=None, on_segment=None):
        # "Decoding" until the loop has ticked: on the loop's own thread the
        # ticker could never run, and this would time out.
        released.append(release.wait(5))
        yield SessionTranscription("s1", [])

    async def main():
        async def ticker():
            for n in range(3):
                ticks.append(n)
                await asyncio.sleep(0)
            release.set()

        task = asyncio.create_task(ticker())
        got = [d.session_id async for d in aiter_transcribe_sessions([], None)]  # type: ignore[arg-type]
        await task
        return got

    with patch.object(s05_transcribe, "iter_transcribe_sessions", _gen):
        assert asyncio.run(main()) == ["s1"]
    assert released == [True], "the loop ran while the file decoded"
    assert ticks == [0, 1, 2]


def test_a_backend_error_is_raised_on_the_loop() -> None:
    def _gen(_sessions, _settings, *, on_progress=None, on_segment=None):
        yield SessionTranscription("s1", [])
        raise RuntimeError("the backend could not start")

    with pytest.raises(RuntimeError, match="could not start"):
        _collect(_gen)


def test_a_consumer_that_leaves_stops_the_thread_at_the_next_file() -> None:
    """Ctrl-C cancels the consumer: the worker must not go on decoding the rest.
    The file in hand finishes (a decode cannot be interrupted); nothing after it."""
    import time

    decoded: list[str] = []

    def _gen(_sessions, _settings, *, on_progress=None, on_segment=None):
        for sid in ("s1", "s2", "s3", "s4", "s5", "s6"):
            time.sleep(0.05)  # a decode
            decoded.append(sid)
            yield SessionTranscription(sid, [])

    async def main():
        async def consume():
            async for _done in aiter_transcribe_sessions([], None):  # type: ignore[arg-type]
                await asyncio.sleep(10)  # working on s1 when Ctrl-C arrives

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0.3)  # time enough to decode the rest, were it going on

    with patch.object(s05_transcribe, "iter_transcribe_sessions", _gen):
        asyncio.run(main())
    assert len(decoded) <= 3, f"went on decoding after the consumer left: {decoded}"


def test_the_chains_topic_time_is_wall_time_not_the_sum_of_its_calls() -> None:
    """Up to ``llm_concurrency`` sessions' calls run at once: two that overlap from
    t=0 to t=3 took three seconds, not four."""
    from bristlenose.readable_chain import ChainAnalysis

    analysis = ChainAnalysis.__new__(ChainAnalysis)
    analysis.topic_seconds = analysis.quote_seconds = 0.0
    analysis._busy = {"topics": (0, 0.0), "quotes": (0, 0.0)}
    with patch("bristlenose.readable_chain.time.perf_counter", side_effect=[0.0, 3.0]):
        analysis._enter("topics")   # t=0, first call starts
        analysis._enter("topics")   # t=1, second starts (no clock read)
        analysis._leave("topics")   # t=2, one still in flight (no clock read)
        analysis._leave("topics")   # t=3
    assert analysis.topic_seconds == 3.0
