"""One malformed quote must not cost a session all its other quotes.

Measured on the any-llm Mistral walk, 23 Oct 2026: `mistral-small-latest`
returned quote-extraction replies in which ONE quote of thirty lacked a
required field (`start_timecode`, `topic_label`). Pydantic rejected the whole
`QuoteExtractionResult`, `_validate_repairing` had no candidate that kept the
valid items, and the session ended with zero quotes. Two of three sessions were
lost that way; the run exited 0 with "Done with warnings" and a cut-off pydantic
message, and never said which sessions came back empty.

Decided 23 Oct 2026: keep the quotes that validate, leave out the incomplete
one, and say so -- a WARNING in the log and a line in the CLI.

Any provider on the repair path (Claude, Gemini, any-llm) can hit it: the shape
is described to the model, never enforced at decode time. OpenAI and Azure use
strict Structured Outputs, where a required field cannot be omitted, so they
are out of scope by construction (`test_strict_structured_output_paths_do_not_repair`).

All tests use a mocked LLM: no network, no keys.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from bristlenose.events import StageFailure, StageOutcome
from bristlenose.llm.client import TruncatedResponseError, _validate_repairing
from bristlenose.llm.structured import (
    QuoteExtractionResult,
    ScreenClusteringResult,
    dropped_items,
)
from bristlenose.models import (
    PiiCleanTranscript,
    SessionTopicMap,
    SpeakerRole,
    TranscriptSegment,
)
from bristlenose.run_lifecycle import _build_cause
from bristlenose.stages.s09_quote_extraction import extract_quotes


def _quote(i: int) -> dict:
    return {
        "start_timecode": f"00:00:{10 + i:02d}",
        "end_timecode": f"00:00:{11 + i:02d}",
        "text": f"This is quote number {i} and it says something useful",
        "verbatim_excerpt": f"quote number {i}",
        "topic_label": "Onboarding",
        "quote_type": "general_context",
    }


def _reply(n: int = 5, bad: tuple[int, ...] = (3,), missing: str = "start_timecode") -> dict:
    """The observed shape: a list of quotes, some missing a required field."""
    quotes = [_quote(i) for i in range(n)]
    for i in bad:
        del quotes[i][missing]
    return {"quotes": quotes}


def _transcript(sid: str = "s1", n: int = 10) -> PiiCleanTranscript:
    segments = [
        TranscriptSegment(
            start_time=float(i),
            end_time=float(i + 1),
            text=f"This is quote number {i} and it says something useful",
            speaker_label="Speaker A",
            speaker_role=SpeakerRole.PARTICIPANT,
            speaker_code="p1",
            source="whisper",
            segment_index=i,
        )
        for i in range(10, 10 + n)
    ]
    return PiiCleanTranscript(
        participant_id="p1",
        session_id=sid,
        source_file=f"{sid}.mp4",
        session_date=datetime(2026, 10, 23, tzinfo=timezone.utc),
        duration_seconds=10.0 + n,
        segments=segments,
    )


def _client(reply) -> AsyncMock:
    """A client whose replies go through the real repair path, as Claude's do."""
    async def analyze(system_prompt, user_prompt, response_model, **kw):
        data = reply() if callable(reply) else reply
        if isinstance(data, BaseException):
            raise data
        return _validate_repairing(
            data, response_model, provider="anthropic", model="claude-sonnet-4-6",
        )

    client = AsyncMock()
    client.provider = "anthropic"
    client.analyze = analyze
    return client


def _no_topics(sid: str = "s1") -> SessionTopicMap:
    return SessionTopicMap(participant_id="p1", session_id=sid, boundaries=[])


# ---------------------------------------------------------------------------
# The repair step
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", ["anthropic", "google", "anyllm"])
def test_one_bad_quote_does_not_fail_the_whole_reply(provider):
    result = _validate_repairing(
        _reply(), QuoteExtractionResult, provider=provider, model="m",
    )
    assert [q.verbatim_excerpt for q in result.quotes] == [
        "quote number 0", "quote number 1", "quote number 2", "quote number 4",
    ]
    assert dropped_items(result) == 1


def test_a_reply_that_validates_whole_drops_nothing():
    assert dropped_items(_validate_repairing(
        _reply(bad=()), QuoteExtractionResult, provider="anthropic", model="m",
    )) == 0


def test_a_drop_is_a_warning_naming_fields_never_values(caplog):
    with caplog.at_level(logging.WARNING, logger="bristlenose.llm.client"):
        _validate_repairing(
            _reply(n=30, bad=(4, 27)), QuoteExtractionResult, provider="anyllm", model="m",
        )
    (line,) = [r.getMessage() for r in caplog.records if "llm_shape_repair" in r.getMessage()]
    assert "dropped 2 of 30 items" in line
    assert "fields=start_timecode" in line
    # The values are participant speech: the log is not a place for them.
    assert "quote number" not in line


def test_nothing_valid_raises_the_original_error():
    """Every quote incomplete: no salvage, so the session fails as before, and
    is retried on the next run. An empty result would read as an interview
    with nothing worth quoting."""
    payload = _reply(n=3, bad=(0, 1, 2))
    with pytest.raises(ValidationError) as got:
        _validate_repairing(payload, QuoteExtractionResult, provider="anthropic", model="m")
    with pytest.raises(ValidationError) as want:
        QuoteExtractionResult.model_validate(payload)
    assert str(got.value) == str(want.value)


def test_salvage_is_opt_in_per_model():
    """A dropped screen cluster would orphan the quotes it held, silently."""
    payload = {"clusters": [
        {"screen_label": "a", "description": "d", "display_order": 1, "quote_indices": [0]},
        {"screen_label": "b"},
    ]}
    with pytest.raises(ValidationError):
        _validate_repairing(payload, ScreenClusteringResult, provider="anthropic", model="m")


# ---------------------------------------------------------------------------
# Stage 9
# ---------------------------------------------------------------------------


def test_one_bad_quote_does_not_empty_the_session():
    dropped: dict[str, int] = {}
    quotes, outcome = asyncio.run(extract_quotes(
        [_transcript()], [_no_topics()], _client(_reply()), dropped=dropped,
    ))
    assert outcome.failed == [] and outcome.succeeded == 1
    assert len(quotes) == 4
    assert dropped == {"s1": 1}


def test_a_failed_reply_says_so_in_plain_words():
    """The CLI prints errors[0]; pydantic's text is multi-line schema paths."""
    errors: list[str] = []
    dropped: dict[str, int] = {}
    quotes, outcome = asyncio.run(extract_quotes(
        [_transcript()], [_no_topics()], _client(_reply(n=2, bad=(0, 1))),
        errors=errors, dropped=dropped,
    ))
    assert quotes == [] and [f.session_id for f in outcome.failed] == ["s1"]
    assert errors == ["the model's reply didn't fit the expected format"]
    assert dropped == {}


def test_a_reply_any_llm_could_not_read_says_so_in_the_same_words():
    """Through any-llm the reply fails before we see it (free Nemotron on
    OpenRouter, 23 Oct 2026); the researcher's line is the same, not the
    library's text with its field paths."""
    from bristlenose.llm.client import UnreadableReplyError

    errors: list[str] = []
    quotes, outcome = asyncio.run(extract_quotes(
        [_transcript()], [_no_topics()],
        _client(UnreadableReplyError("OpenRouter returned a response any-llm couldn't read")),
        errors=errors,
    ))
    assert quotes == [] and [f.session_id for f in outcome.failed] == ["s1"]
    assert errors == ["the model's reply didn't fit the expected format"]


def test_a_session_that_fails_after_a_salvaged_chunk_reports_no_drop():
    """Smart-split: chunk one is salvaged, chunk two fails for good. The session
    has no quotes, so none were "left out" of it."""
    calls = {"n": 0}

    def reply():
        calls["n"] += 1
        if calls["n"] == 1:
            return TruncatedResponseError(
                "truncated", provider="anthropic", model="m",
                requested_max_tokens=1, model_cap=1,
            )
        if calls["n"] == 2:
            return _reply()
        return RuntimeError("provider fell over")

    dropped: dict[str, int] = {}
    quotes, outcome = asyncio.run(extract_quotes(
        [_transcript(n=20)], [_no_topics()], _client(reply), dropped=dropped,
    ))
    assert quotes == [] and [f.session_id for f in outcome.failed] == ["s1"]
    assert dropped == {}


def test_the_readable_chain_keeps_its_drop_count_for_stage_9(tmp_path: Path):
    """On a first analysis the chain extracts quotes before stage 9, which then
    takes them as they are: the count has to come with them."""
    from bristlenose.config import BristlenoseSettings
    from bristlenose.llm.structured import TopicSegmentationResult
    from bristlenose.manifest import create_manifest
    from bristlenose.readable_chain import ChainAnalysis

    async def analyze(system_prompt, user_prompt, response_model, **kw):
        if response_model is TopicSegmentationResult:
            return TopicSegmentationResult(boundaries=[])
        return _validate_repairing(_reply(), response_model, provider="anthropic", model="m")

    client = AsyncMock()
    client.provider = "anthropic"
    client.analyze = analyze
    chain = ChainAnalysis(
        settings=BristlenoseSettings(output_dir=tmp_path, anthropic_api_key="sk-test"),
        llm_client=client, manifest=create_manifest("p", "0"), output_dir=tmp_path,
        clean=lambda t: t, topic_fingerprint=lambda _t: "t",
        quote_fingerprint=lambda _t, _m: "q", concurrency=1,
    )

    async def go():
        chain.start(_transcript())
        await chain.finish()

    asyncio.run(go())
    assert len(chain.quotes["s1"][0]) == 4
    assert chain.quote_drops == {"s1": 1}


# ---------------------------------------------------------------------------
# What the CLI says
# ---------------------------------------------------------------------------


def _failed(*sids: str) -> StageOutcome:
    return StageOutcome(attempted=len(sids) + 1, succeeded=1, failed=[
        StageFailure(session_id=sid, cause=_build_cause(
            RuntimeError("x"), stage="quote_extraction", provider="anyllm", session_id=sid,
        ))
        for sid in sids
    ])


def test_sessions_with_no_quotes_are_named_in_session_order():
    from bristlenose.pipeline import _quote_shortfall

    assert _quote_shortfall(_failed("s10", "s6", "s1"), {}) == ("no quotes from s1, s6, s10", "")
    assert _quote_shortfall(_failed(), {"s3": 1, "s10": 2}) == (
        "", "3 incomplete quotes left out (s3, s10)",
    )
    assert _quote_shortfall(_failed(), {"s3": 1})[1] == "1 incomplete quote left out (s3)"


def test_a_long_list_of_sessions_is_cut_with_a_count():
    from bristlenose.pipeline import _session_list

    assert _session_list(f"s{i}" for i in range(1, 10)) == "s1, s2, s3, s4, s5 and 4 more"


def test_the_step_names_the_empty_sessions_then_what_was_left_out(monkeypatch):
    """Walk 6a's run, as it would now print."""
    import bristlenose.pipeline as p

    printed: list[str] = []
    monkeypatch.setattr(p, "_print_warn", lambda msg, link="": printed.append(msg))
    p._print_quote_shortfall(
        _failed("s6", "s1"), {"s10": 1},
        ["the model's reply didn't fit the expected format"] * 2, "anyllm",
    )
    assert printed == [
        "No quotes from s1, s6 — the model's reply didn't fit the expected format",
        "1 incomplete quote left out (s10)",
    ]


def test_the_summary_line_puts_empty_sessions_first():
    from bristlenose.pipeline import _summary_warning

    assert _summary_warning(_failed("s1"), {"s10": 1}, ["e"], "anyllm") == "no quotes from s1"
    assert _summary_warning(_failed(), {"s10": 1}, [], "anyllm") == (
        "1 incomplete quote left out (s10)"
    )
    # Topic segmentation's error, when that is all there is.
    assert _summary_warning(_failed(), {}, ["topics failed"], "anyllm") == "topics failed"


def test_a_multi_line_error_is_cut_to_its_first_line():
    """Walk 6a printed "1 validation error for QuoteExtractionResult\\nquotes.4.
    start_timecode\\n  Fi…" after the em dash."""
    from bristlenose.pipeline import _short_reason

    msg, _ = _short_reason(["first line\nquotes.4.start_timecode\n  Field required"])
    assert msg == "first line"


# ---------------------------------------------------------------------------
# The two pipeline callers hand stage 9 a sink and print what comes back
# ---------------------------------------------------------------------------


def _fake_extract_quotes(stop: str):
    """Stage 9 as walk 6a ran it: s1 empty, one quote left out of s10."""
    from bristlenose.models import ExtractedQuote, QuoteType

    async def fake(ts, _maps, _client, **kw):
        kw["dropped"]["s10"] = 1
        if kw.get("errors") is not None:
            kw["errors"].append("the model's reply didn't fit the expected format")
        quote = ExtractedQuote(
            session_id="s10", participant_id="p10", start_timecode=1.0, end_timecode=2.0,
            text="a quote", topic_label="t", quote_type=QuoteType.GENERAL_CONTEXT,
        )
        return [quote], _failed("s1")

    async def stop_here(*_a, **_kw):
        raise RuntimeError(stop)

    return fake, stop_here


def test_analyze_prints_the_shortfall_under_stage_9(tmp_path: Path, monkeypatch):
    from unittest.mock import MagicMock, patch

    import bristlenose.pipeline as p

    tx = tmp_path / "transcripts"
    tx.mkdir()
    for sid in ("s1", "s10"):
        (tx / f"{sid}.txt").write_text(
            f"# Transcript: {sid}\n# Source: {sid}.wav\n# Date: 2026-10-23\n"
            f"# Duration: 00:00:10\n\n[00:00] [m1] Hello.\n[00:05] [p{sid[1:]}] Hi there.\n",
            encoding="utf-8",
        )
    settings = MagicMock(
        project_name="t", llm_provider="anthropic", llm_model="claude-sonnet-4-6",
        write_intermediate=True, llm_concurrency=1, min_quote_words=3, pii_enabled=False,
    )

    async def topics(ts, _client, **_kw):
        return ([SessionTopicMap(session_id=t.session_id, participant_id=t.participant_id,
                                 boundaries=[]) for t in ts],
                StageOutcome(attempted=len(ts), succeeded=len(ts)))

    def llm(_settings):
        client = AsyncMock()
        client.provider = "anthropic"
        return client

    printed: list[str] = []
    monkeypatch.setattr(p, "_print_warn", lambda msg, link="": printed.append(msg))
    quotes, stop = _fake_extract_quotes("stop after stage 9")
    with (
        patch("bristlenose.llm.client.LLMClient", side_effect=llm),
        patch("bristlenose.stages.s08_topic_segmentation.segment_topics", new=topics),
        patch("bristlenose.stages.s09_quote_extraction.extract_quotes", new=quotes),
        # s10 and s11 run together: both stop, or s11 reaches the real client.
        patch("bristlenose.stages.s10_quote_clustering.cluster_by_screen", new=stop),
        patch("bristlenose.stages.s11_thematic_grouping.group_by_theme", new=stop),
        pytest.raises(RuntimeError, match="stop after stage 9"),
    ):
        asyncio.run(p.Pipeline(settings).run_analysis_only(tx, tmp_path / "out"))
    assert printed == [
        "No quotes from s1 — the model's reply didn't fit the expected format",
        "1 incomplete quote left out (s10)",
    ]


def test_run_prints_the_shortfall_under_stage_9(tmp_path: Path, monkeypatch):
    from unittest.mock import patch

    import bristlenose.pipeline as p
    from tests.conftest import iter_transcribe_from
    from tests.test_pipeline_abandon import _async_passthrough, _pii_run_fixture

    (settings, input_dir, output_dir, sessions,
     transcripts, fake_transcribe) = _pii_run_fixture(tmp_path)
    settings.pii_enabled = False
    settings.min_quote_words = 5

    async def speakers(_segments, _client, **_kw):
        return []

    async def topics(ts, _client, **_kw):
        return ([SessionTopicMap(session_id=t.session_id, participant_id=t.participant_id,
                                 boundaries=[]) for t in ts],
                StageOutcome(attempted=len(ts), succeeded=len(ts)))

    printed: list[str] = []
    monkeypatch.setattr(p, "_print_warn", lambda msg, link="": printed.append(msg))
    quotes, stop = _fake_extract_quotes("stop after stage 9")
    with (
        patch("bristlenose.stages.s01_ingest.ingest", return_value=sessions),
        patch("bristlenose.stages.s02_extract_audio.extract_audio_for_sessions",
              new=_async_passthrough),
        patch("bristlenose.stages.s05_transcribe.iter_transcribe_sessions",
              new=iter_transcribe_from(fake_transcribe)),
        patch("bristlenose.stages.s05b_identify_speakers.identify_speaker_roles_llm",
              new=speakers),
        patch("bristlenose.stages.s06_merge_transcript.merge_transcripts",
              return_value=transcripts),
        patch("bristlenose.stages.s08_topic_segmentation.segment_topics", new=topics),
        patch("bristlenose.stages.s09_quote_extraction.extract_quotes", new=quotes),
        # s10 and s11 run together: both stop, or s11 reaches the real client.
        patch("bristlenose.stages.s10_quote_clustering.cluster_by_screen", new=stop),
        patch("bristlenose.stages.s11_thematic_grouping.group_by_theme", new=stop),
        patch.object(p.Pipeline, "_readable_chain", return_value=None),
        pytest.raises(RuntimeError, match="stop after stage 9"),
    ):
        asyncio.run(p.Pipeline(settings).run(input_dir, output_dir))
    assert printed[-2:] == [
        "No quotes from s1 — the model's reply didn't fit the expected format",
        "1 incomplete quote left out (s10)",
    ]
