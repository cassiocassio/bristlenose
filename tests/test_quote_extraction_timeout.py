"""A long, dense interview whose quote-extraction call outlasts the provider's wall.

R33: one 94-minute interview ran for about 70 minutes and then failed; split in
two it worked (FOSSDA s3, 73,747 chars: a whole-session call needs ~671 s against
a 600 s read timeout; the halves took 522 s and 293 s and gave 91 quotes). The SDK
re-sent the same timed-out job six more times (7 x 600 s), and smart-split was
reachable only from truncation, never from a timeout.

These tests run the REAL ``LLMClient`` and the REAL Anthropic / OpenAI SDKs, so
the SDK's own retry policy is what is under test. Only the network is fake: a
mock transport that behaves like a non-streaming endpoint — it answers after a
time proportional to the chunk it was sent, and when that time exceeds the
request's read timeout it raises ``ReadTimeout`` at the timeout, exactly as an
idle socket would. A virtual clock makes 70 simulated minutes cost milliseconds.
No network, no keys, no spend.
"""

from __future__ import annotations

import asyncio
import functools
import heapq
import importlib
import json
import re
from datetime import datetime, timezone

import httpx2
import pytest

from bristlenose.config import BristlenoseSettings
from bristlenose.events import CauseCategoryEnum
from bristlenose.llm.client import LLMClient
from bristlenose.models import (
    PiiCleanTranscript,
    SessionTopicMap,
    SpeakerRole,
    TranscriptSegment,
)
from bristlenose.stages import s09_quote_extraction as s09
from bristlenose.stages.s09_quote_extraction import extract_quotes

# FOSSDA s3: 94 min, 376 fifteen-second turns, ~671 s for the whole session at
# the measured 9.10 s per 1k chars. Generation time scales with what is sent.
_SEGMENT_SECONDS = 15.0
_SECONDS_PER_SEGMENT = 671.0 / 376
_QUOTE_EVERY = 4  # ~60 quotes an hour, FOSSDA s3's density after the split
_MARKER = re.compile(rb"seg-(\d{4})")


class _VirtualClockLoop(asyncio.SelectorEventLoop):
    """An event loop whose clock jumps to the next timer whenever nothing can run.

    Every timeout in the stack under test (``asyncio.wait_for``, the SDK's
    ``anyio.sleep`` backoff, the fake endpoint's latency) is a loop timer, so
    simulated minutes pass instantly and ``time()`` reports them exactly. The
    clock holds still while thread work is in flight (the SDKs read the
    platform in a thread), or a pending deadline would fire on a real wait.
    """

    def __init__(self) -> None:
        super().__init__()
        self._now = 0.0
        self._in_threads = 0

    def time(self) -> float:
        return self._now

    def run_in_executor(self, executor, func, *args):  # type: ignore[override]
        future = super().run_in_executor(executor, func, *args)
        self._in_threads += 1

        def _done(_: object) -> None:
            self._in_threads -= 1

        future.add_done_callback(_done)
        return future

    def _run_once(self) -> None:
        if not self._ready and not self._in_threads:
            while self._scheduled and self._scheduled[0]._cancelled:
                handle = heapq.heappop(self._scheduled)
                handle._scheduled = False
                self._timer_cancelled_count -= 1
            if self._scheduled:
                self._now = max(self._now, self._scheduled[0]._when)
        super()._run_once()


def _transcript(minutes: float, *, timed: bool = True) -> PiiCleanTranscript:
    n = int(minutes * 60 / _SEGMENT_SECONDS)
    filler = "and I kept going back to it because the thing never quite did what I expected " * 2
    segments = [
        TranscriptSegment(
            start_time=i * _SEGMENT_SECONDS if timed else 0.0,
            end_time=(i + 1) * _SEGMENT_SECONDS if timed else 0.0,
            text=f"seg-{i:04d} {filler}",
            speaker_role=SpeakerRole.PARTICIPANT,
            speaker_code="p1",
            source="whisper",
            segment_index=i,
        )
        for i in range(n)
    ]
    return PiiCleanTranscript(
        participant_id="p1", session_id="s1", source_file="s1.mp4",
        session_date=datetime(2026, 1, 10, tzinfo=timezone.utc),
        duration_seconds=n * _SEGMENT_SECONDS, segments=segments,
    )


def _quotes_for(markers: list[int], timed: bool) -> list[dict]:
    quotes = []
    for i in markers:
        if i % _QUOTE_EVERY:
            continue
        t = int(i * _SEGMENT_SECONDS) if timed else 0
        tc = f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"
        quotes.append({
            "start_timecode": tc,
            "end_timecode": tc,
            "text": f"I think the seg-{i:04d} part of the flow worked for me",
            "verbatim_excerpt": f"seg-{i:04d} verbatim words from the participant",
            "topic_label": "Onboarding",
            "quote_type": "screen_specific",
        })
    return quotes


def _anthropic_body(quotes: list[dict]) -> dict:
    return {
        "id": "msg_fake", "type": "message", "role": "assistant",
        "model": "claude-sonnet-4-6", "stop_reason": "tool_use", "stop_sequence": None,
        "content": [{
            "type": "tool_use", "id": "toolu_fake", "name": "structured_output",
            "input": {"quotes": quotes},
        }],
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


def _openai_body(quotes: list[dict]) -> dict:
    return {
        "id": "chatcmpl-fake", "object": "chat.completion", "created": 0, "model": "fake",
        "choices": [{
            "index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": json.dumps({"quotes": quotes})},
        }],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


class _Endpoint:
    """A non-streaming LLM endpoint: silent until the whole answer is ready."""

    def __init__(self, provider: str, *, timed: bool = True, black_hole: bool = False):
        self.provider = provider
        self.timed = timed
        self.black_hole = black_hole
        self.jobs: list[tuple[int, ...]] = []  # the segments each request carried

    async def __call__(self, request: httpx2.Request) -> httpx2.Response:
        markers = sorted({int(m) for m in _MARKER.findall(request.content)})
        self.jobs.append(tuple(markers))
        read_timeout = request.extensions["timeout"]["read"]
        needed = len(markers) * _SECONDS_PER_SEGMENT
        if self.black_hole or (read_timeout is not None and needed > read_timeout):
            await asyncio.sleep(read_timeout if read_timeout is not None else 10**9)
            raise httpx2.ReadTimeout("no bytes before the read timeout", request=request)
        await asyncio.sleep(needed)
        quotes = _quotes_for(markers, self.timed)
        body = _anthropic_body(quotes) if self.provider == "anthropic" else _openai_body(quotes)
        return httpx2.Response(200, json=body)


def _settings(provider: str) -> BristlenoseSettings:
    if provider == "anthropic":
        return BristlenoseSettings(
            llm_provider="anthropic", anthropic_api_key="sk-ant-test-not-a-key",
            llm_model="claude-sonnet-4-6",
        )
    if provider == "openai":
        return BristlenoseSettings(
            llm_provider="openai", openai_api_key="sk-test-not-a-key", llm_model="gpt-5",
        )
    return BristlenoseSettings(
        llm_provider="local", local_model="llama3.2", local_url="http://localhost:11434/v1",
    )


def _run(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    transcript: PiiCleanTranscript,
    endpoint: _Endpoint,
):
    """Run s09 over one session through the production client; return (quotes, outcome, secs)."""
    # The production constructors run unchanged — retry budget and all — with
    # only the HTTP transport swapped for the fake endpoint.
    http_client = httpx2.AsyncClient(transport=httpx2.MockTransport(endpoint))
    # Patch the SDK module the client will import NOW, not the one this file
    # imported at collection: other tests swap SDK modules in sys.modules, and a
    # patch on a stale module object sends the request to the real API.
    sdk = importlib.import_module("anthropic" if provider == "anthropic" else "openai")
    name = "AsyncAnthropic" if provider == "anthropic" else "AsyncOpenAI"
    real = getattr(sdk, name)
    monkeypatch.setattr(sdk, name, functools.partial(real, http_client=http_client))
    llm = LLMClient(_settings(provider))
    topic_map = SessionTopicMap(participant_id="p1", session_id="s1", boundaries=[])

    loop = _VirtualClockLoop()
    try:
        quotes, outcome = loop.run_until_complete(
            extract_quotes([transcript], [topic_map], llm, concurrency=1)
        )
        secs = loop.time()
        loop.run_until_complete(http_client.aclose())
        # Every request must have gone to the fake endpoint, never the network.
        assert endpoint.jobs, "no request reached the fake endpoint"
        return quotes, outcome, secs
    finally:
        loop.close()


def _covered(quotes) -> set[int]:
    return {int(m) for q in quotes for m in re.findall(r"seg-(\d{4})", q.verbatim_excerpt)}


def _expected(transcript: PiiCleanTranscript) -> set[int]:
    return {i for i in range(len(transcript.segments)) if i % _QUOTE_EVERY == 0}


@pytest.mark.parametrize("provider", ["anthropic", "openai", "local"])
def test_a_long_dense_session_is_split_not_failed(monkeypatch, provider) -> None:
    """94 min, dense: the whole-session call outlasts the read timeout.

    Before: the SDK re-sent the same job until its retries ran out (70 min on
    Claude / ChatGPT, 30 min on a local model), then the session failed with no
    quotes. After: the job is cut short once, the session splits, and every
    part of the interview is quoted.
    """
    transcript = _transcript(94)
    endpoint = _Endpoint(provider)

    quotes, outcome, secs = _run(monkeypatch, provider, transcript, endpoint)

    assert outcome.failed == []
    assert outcome.succeeded == 1
    # Start, middle and end all quoted: no silent loss of the second half.
    assert _covered(quotes) == _expected(transcript)
    assert len(quotes) == len(_expected(transcript))
    # The same job is never sent twice — a timeout is the size of the job, not
    # a transient, so re-sending it whole only repeats the wait.
    assert len(endpoint.jobs) == len(set(endpoint.jobs)), endpoint.jobs
    # One cut-short attempt plus two halves: well inside the old 70 minutes.
    assert secs < 30 * 60, secs


def test_a_two_hour_dense_session_is_split_not_failed(monkeypatch) -> None:
    transcript = _transcript(120)
    endpoint = _Endpoint("anthropic")

    quotes, outcome, secs = _run(monkeypatch, "anthropic", transcript, endpoint)

    assert outcome.succeeded == 1
    assert _covered(quotes) == _expected(transcript)
    assert secs < 30 * 60, secs


@pytest.mark.parametrize("minutes", [180, 240])
def test_a_very_long_session_splits_again_where_halves_still_overrun(
    monkeypatch, minutes
) -> None:
    """3 hours: halves still outlast the wall, quarters fit. 4 hours: eighths."""
    transcript = _transcript(minutes)
    endpoint = _Endpoint("anthropic")

    quotes, outcome, secs = _run(monkeypatch, "anthropic", transcript, endpoint)

    assert outcome.succeeded == 1
    assert _covered(quotes) == _expected(transcript)
    assert len(endpoint.jobs) == len(set(endpoint.jobs))


def test_a_normal_hour_is_one_call_and_never_split(monkeypatch) -> None:
    """The fix must not touch the common case: a 60-minute session fits the wall."""
    transcript = _transcript(60)
    endpoint = _Endpoint("anthropic")

    quotes, outcome, secs = _run(monkeypatch, "anthropic", transcript, endpoint)

    assert outcome.succeeded == 1
    assert len(endpoint.jobs) == 1
    assert _covered(quotes) == _expected(transcript)


def test_a_long_untimed_transcript_splits_by_turns(monkeypatch) -> None:
    """A long transcript with no timecodes (a plain Word document) still splits.

    Halving by turn count needs no clock, so a missing timecode is no reason
    to refuse the split and fail the session.
    """
    transcript = _transcript(94, timed=False)
    endpoint = _Endpoint("anthropic", timed=False)

    quotes, outcome, secs = _run(monkeypatch, "anthropic", transcript, endpoint)

    assert outcome.failed == []
    assert outcome.succeeded == 1
    assert _covered(quotes) == _expected(transcript)


def test_a_provider_that_never_answers_fails_the_session_in_bounded_time(
    monkeypatch,
) -> None:
    """Splitting must not turn a hung provider into hours of waiting.

    Before: 7 x 600 s per session. After: one deadline per level down the
    first chunk at each depth — chunks run in order and the first failure ends
    the session — categorised as a network failure, as an SDK timeout was.
    """
    transcript = _transcript(94)
    endpoint = _Endpoint("anthropic", black_hole=True)

    quotes, outcome, secs = _run(monkeypatch, "anthropic", transcript, endpoint)

    assert quotes == []
    assert outcome.succeeded == 0
    assert len(outcome.failed) == 1
    assert outcome.failed[0].cause.category == CauseCategoryEnum.NETWORK
    levels = s09._SPLIT_MAX_DEPTH + 1
    assert len(endpoint.jobs) == levels
    assert secs <= levels * s09._PASS_DEADLINE_S + 60, secs


def test_an_overrun_that_cannot_be_split_is_still_a_timeout(monkeypatch) -> None:
    """One enormous turn can't be halved; the failure must still say it overran."""
    transcript = _transcript(94)
    transcript = transcript.model_copy(update={"segments": transcript.segments[:1]})
    endpoint = _Endpoint("anthropic", black_hole=True)

    quotes, outcome, secs = _run(monkeypatch, "anthropic", transcript, endpoint)

    assert outcome.succeeded == 0
    assert outcome.failed[0].cause.category == CauseCategoryEnum.NETWORK
    assert len(endpoint.jobs) == 1
