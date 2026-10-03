"""The Discussion stage end to end with a fake LLM, its moderator selection, and
its guide reader. No paid calls: the client is a stand-in that answers each
response model the way a well-behaved model would — or raises, to prove a
failure is recorded and never read as "no questions asked"."""

from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path

import pytest

from bristlenose.discussion.guide import GUIDE_FOLDER, MAX_GUIDE_BYTES, NO_GUIDE_SHA, find_guide
from bristlenose.discussion.models import (
    ConsolidateOut,
    RouteBatchOut,
    RouteOut,
    SessionLabelsOut,
    SpineItemOut,
    SpineOut,
    SpineSectionOut,
    TurnLabelOut,
)
from bristlenose.discussion.moderator import moderator_turns
from bristlenose.discussion.stage import run_discussion
from bristlenose.models import (
    ExtractedQuote,
    FullTranscript,
    QuoteType,
    SpeakerRole,
    TranscriptSegment,
)

# ── fixtures ─────────────────────────────────────────────────────────────────


def seg(t: float, role: SpeakerRole, code: str, text: str, source: str = "vtt") -> TranscriptSegment:
    return TranscriptSegment(start_time=t, end_time=t + 5, text=text, speaker_role=role,
                             speaker_code=code, source=source)


M, P = SpeakerRole.RESEARCHER, SpeakerRole.PARTICIPANT


def transcript(sid: str, segs: list[TranscriptSegment], duration: float = 600) -> FullTranscript:
    return FullTranscript(session_id=sid, participant_id=f"p{sid[1:]}", source_file=f"{sid}.vtt",
                          session_date=datetime(2026, 10, 3), duration_seconds=duration, segments=segs)


def quote(sid: str, t: float, text: str) -> ExtractedQuote:
    return ExtractedQuote(session_id=sid, participant_id=f"p{sid[1:]}", start_timecode=t,
                          end_timecode=t + 4, text=text, topic_label="x",
                          quote_type=QuoteType.GENERAL_CONTEXT)


def two_sessions() -> tuple[list[FullTranscript], list[ExtractedQuote]]:
    s1 = transcript("s1", [
        seg(10, M, "m1", "Before we start, are you happy to be recorded today?"),
        seg(20, P, "p1", "Yes that is fine"),
        seg(30, M, "m1", "Tell me about who you live with at home"),
        seg(40, P, "p1", "I live with my partner and two children in Leeds"),
        seg(60, M, "m1", "Do you set yourselves a weekly budget?"),
        seg(70, P, "p1", "We try to keep it under a hundred pounds a week"),
        seg(90, M, "m1", "Great"),
    ])
    s2 = transcript("s2", [
        seg(15, M, "m1", "Could you tell me about your household?"),
        seg(25, P, "p2", "Just me and a flatmate in Bristol"),
        seg(45, M, "m2", "Have prices changed how you shop at all?"),
        seg(55, P, "p2", "I buy the reduced meat now and own-brand pasta"),
        seg(80, M, "m1", "Do you go looking for offers in the app?"),
        seg(90, P, "p2", "Every week, I sort everything by price per kilo"),
    ])
    qs = [quote("s1", 42, "I live with my partner and two children"),
          quote("s1", 72, "We try to keep it under a hundred pounds"),
          quote("s2", 27, "Just me and a flatmate in Bristol"),
          quote("s2", 57, "I buy the reduced meat now")]
    return [s1, s2], qs


class FakeClient:
    """Answers each response model plausibly; `fail_on` names a session whose
    classify call raises, `fail_kinds` response models that always raise."""

    provider = "anthropic"

    def __init__(self, fail_on: str | None = None, fail_kinds: tuple[type, ...] = ()):
        self.fail_on, self.fail_kinds, self.calls = fail_on, fail_kinds, []

    async def analyze(self, system_prompt, user_prompt, response_model, max_tokens=None, prompt_template=None):
        self.calls.append(response_model.__name__)
        if response_model in self.fail_kinds:
            raise RuntimeError("provider said no")
        if response_model is SpineOut:
            return SpineOut(sections=[
                SpineSectionOut(title="Consent", kind="instruction",
                                items=[SpineItemOut(text="Confirm consent to record", terse="Consent")]),
                SpineSectionOut(title="About you", items=[SpineItemOut(text="Who do you live with?", terse="Household")]),
            ])
        if response_model is SessionLabelsOut:
            ids = re.findall(r"^(s\d@[\d:]+'*) \|", user_prompt, re.M)
            if self.fail_on and any(i.startswith(self.fail_on + "@") for i in ids):
                raise RuntimeError("classify failed")
            out = []
            for i in ids:
                line = re.search(rf"^{re.escape(i)} \| (.*)$", user_prompt, re.M).group(1).lower()
                if "record" in line:
                    out.append(TurnLabelOut(turn_id=i, kind="instruction"))
                elif "live with" in line or "household" in line:
                    out.append(TurnLabelOut(turn_id=i, kind="planned", item_id="s2.1"))
                else:
                    out.append(TurnLabelOut(turn_id=i, kind="new", cluster="money", terse="Money"))
            return SessionLabelsOut(labels=out)
        if response_model is ConsolidateOut:
            ids = re.findall(r"^(s\d@[\d:]+'*) \|", user_prompt, re.M)
            return ConsolidateOut.model_validate({
                "topics": [{"name": "Money", "nav": "Money", "heading": "Budget and prices"}],
                "items": [{"turn_ids": [i], "terse": "Money q", "where": "Money"} for i in ids]})
        if response_model is RouteBatchOut:
            ids = re.findall(r"^(q\d+) \|", user_prompt, re.M)
            return RouteBatchOut(routes=[RouteOut(quote_id=i, section_id="UNROUTED") for i in ids])
        raise AssertionError(response_model)


def write_guide(tmp: Path, text: str = "# Guide\n## About you\n- Who do you live with?\n") -> Path:
    folder = tmp / GUIDE_FOLDER
    folder.mkdir()
    (folder / "guide.md").write_text(text)
    return folder


def run(transcripts, quotes, tmp, client):
    return asyncio.run(run_discussion(transcripts, quotes, tmp, client))


# ── the stage ────────────────────────────────────────────────────────────────


def test_with_a_guide_builds_the_record_and_keeps_it_to_codes(tmp_path):
    write_guide(tmp_path)
    ts, qs = two_sessions()
    record, outcome = run(ts, qs, tmp_path, FakeClient())
    assert record.status == "complete" and record.guide and record.guide_sha != NO_GUIDE_SHA
    assert outcome.attempted == 2 and outcome.succeeded == 2 and not outcome.failed
    household = next(i for s in record.sections for i in s.items if i.id == "s2.1")
    assert household.source == "both" and {a.session for a in household.asks} == {"s1", "s2"}
    # two sessions, three asks of "money" ("Great" is too short to count) → promoted
    assert any(s.origin == "emergent" for s in record.sections)
    # quotes keyed by identity and placed by the anchor
    q = next(q for q in record.quotes if q.session == "s1" and q.sec == 42)
    assert q.after_item == "s2.1" and q.how == "anchor"
    # codes only: no participant names anywhere in the record
    assert record.sessions[0].participants == ["p1"]
    # a session with two moderators keeps each turn's own code
    assert {t.speaker for t in record.turns if t.session == "s2"} == {"m1", "m2"}


def test_instruction_sections_keep_their_title_only(tmp_path):
    write_guide(tmp_path)
    ts, qs = two_sessions()
    record, _ = run(ts, qs, tmp_path, FakeClient())
    consent = next(s for s in record.spine if s.kind == "instruction")
    assert consent.title == "Consent" and consent.items == []


def test_without_a_guide_runs_merged_only(tmp_path):
    ts, qs = two_sessions()
    client = FakeClient()
    record, _ = run(ts, qs, tmp_path, client)
    assert not record.guide and record.guide_sha == NO_GUIDE_SHA and record.spine == []
    assert "SpineOut" not in client.calls


def test_a_failed_session_is_recorded_and_its_questions_stay_visible(tmp_path):
    ts, qs = two_sessions()
    record, outcome = run(ts, qs, tmp_path, FakeClient(fail_on="s2"))
    assert record.status == "partial"
    assert next(s for s in record.sessions if s.id == "s2").state == "failed"
    assert [f.session_id for f in outcome.failed] == ["s2"]
    s2 = [t for t in record.turns if t.session == "s2"]
    assert s2 and all(t.kind == "unclassified" for t in s2)  # never hidden as chat


def test_a_guide_that_will_not_parse_is_a_failure_not_no_guide(tmp_path):
    write_guide(tmp_path)
    ts, qs = two_sessions()
    record, outcome = run(ts, qs, tmp_path, FakeClient(fail_kinds=(SpineOut,)))
    assert record.status == "partial" and record.stats.get("guide_parse_failed") == 1
    assert record.guide_sha != NO_GUIDE_SHA  # the guide is known, even though it did not parse
    assert outcome.failed and outcome.failed[0].session_id is None


def test_an_unreadable_guide_is_said_so_on_the_record(tmp_path):
    folder = tmp_path / GUIDE_FOLDER
    folder.mkdir()
    (folder / "guide.docx").write_bytes(b"not a zip")
    ts, qs = two_sessions()
    record, _ = run(ts, qs, tmp_path, FakeClient())
    assert record.guide_problem == "unreadable" and not record.guide
    assert record.status == "partial"  # never "complete, no guide"


class EmptyClient(FakeClient):
    """Valid but empty replies: the shape a model gives when it finds nothing."""

    def __init__(self, empty: tuple[type, ...]):
        super().__init__()
        self.empty = empty

    async def analyze(self, system_prompt, user_prompt, response_model, max_tokens=None, prompt_template=None):
        if response_model in self.empty:
            self.calls.append(response_model.__name__)
            return response_model.model_validate({"sections": []} if response_model is SpineOut
                                                 else {"labels": []})
        return await super().analyze(system_prompt, user_prompt, response_model, max_tokens, prompt_template)


def test_an_empty_classify_reply_is_a_failed_session_not_no_questions(tmp_path):
    ts, qs = two_sessions()
    record, outcome = run(ts, qs, tmp_path, EmptyClient((SessionLabelsOut,)))
    assert {s.state for s in record.sessions} == {"failed"} and record.status == "failed"
    assert {f.session_id for f in outcome.failed} == {"s1", "s2"}
    assert all(t.kind == "unclassified" for t in record.turns if len(t.text.split()) >= 3)


def test_a_guide_that_parses_to_nothing_is_said_so(tmp_path):
    write_guide(tmp_path)
    ts, qs = two_sessions()
    record, _ = run(ts, qs, tmp_path, EmptyClient((SpineOut,)))
    assert record.guide_problem == "empty_parse" and record.status == "partial"


def test_an_unreliable_sessions_questions_stay_visible(tmp_path):
    ts, qs = two_sessions()
    # whisper over-attribution: the moderator speaks most of the words
    ts.append(transcript("s3", [seg(10, P, "p3", "hi", "mlx-whisper")] +
                         [seg(30 + i * 60, M, "m1", "and how do you feel about the budget", "mlx-whisper")
                          for i in range(10)], duration=700))
    record, _ = run(ts, qs, tmp_path, FakeClient())
    assert next(s for s in record.sessions if s.id == "s3").state == "moderator_unreliable"
    s3 = [t for t in record.turns if t.session == "s3"]
    assert s3 and all(t.kind == "unclassified" for t in s3)  # not "chat"


def test_a_numeric_string_confidence_is_a_number():
    assert RouteOut(quote_id="q0", section_id="s1", confidence="0.9").confidence == 0.9
    assert RouteOut(quote_id="q0", section_id="s1", confidence="high").confidence == 0.0


def test_one_failed_route_batch_keeps_the_others(tmp_path):
    ts, qs = two_sessions()
    many = [quote("s1", 42 + i, f"quote number {i}") for i in range(30)]  # two batches of 25 + 5

    class OneBadBatch(FakeClient):
        async def analyze(self, system_prompt, user_prompt, response_model, max_tokens=None, prompt_template=None):
            if response_model is RouteBatchOut:
                ids = re.findall(r"^(q\d+) \|", user_prompt, re.M)
                if "q0" in ids:
                    raise RuntimeError("batch failed")
                return RouteBatchOut(routes=[RouteOut(quote_id=i, section_id="s2", confidence=0.9) for i in ids])
            return await super().analyze(system_prompt, user_prompt, response_model, max_tokens, prompt_template)

    write_guide(tmp_path)
    record, outcome = run(ts, many, tmp_path, OneBadBatch())
    assert record.stats.get("route_failed") == 1 and outcome.failed
    second = [q for q in record.quotes if q.sec >= 42 + 25]  # the batch that succeeded
    assert second and all(q.how != "anchor" or q.section for q in second)
    assert any(q.how in ("topic", "agree") for q in second)


def test_routing_failure_falls_back_to_the_anchor(tmp_path):
    ts, qs = two_sessions()
    record, _ = run(ts, qs, tmp_path, FakeClient(fail_kinds=(RouteBatchOut,)))
    assert record.stats.get("route_failed") == 1
    assert all(q.how in ("anchor", "unrouted") for q in record.quotes)
    assert record.stats["quotes_routed"] + record.stats["quotes_unrouted"] == len(qs)


def test_the_record_is_stamped_with_what_it_was_built_from(tmp_path):
    ts, qs = two_sessions()
    a, _ = run(ts, qs, tmp_path, FakeClient())
    b, _ = run(ts, qs[:-1], tmp_path, FakeClient())
    assert a.quotes_sha and a.quotes_sha != b.quotes_sha


# ── moderator selection ──────────────────────────────────────────────────────


def test_platform_transcripts_are_trusted():
    t = transcript("s1", [seg(i * 60, M if i % 2 else P, "m1" if i % 2 else "p1", "a question about something here")
                          for i in range(20)], duration=1200)
    assert moderator_turns(t).reliable


def test_whisper_over_attribution_is_unreliable():
    t = transcript("s1", [seg(10, P, "p1", "hi there everyone", "mlx-whisper")] +
                   [seg(30 + i * 60, M, "m1", "and then a long stretch of talk", "mlx-whisper") for i in range(20)],
                   duration=1300)
    assert moderator_turns(t).reason == "moderator_over_attributed"


def test_whisper_under_attribution_is_unreliable():
    # 18 minutes; the last moderator turn is at 4:25, inside the splitter's window
    segs = [seg(60, M, "m1", "tell me about your home", "whisper"), seg(265, M, "m1", "and what about the kitchen", "whisper")]
    segs += [seg(300 + i * 40, P, "p1", "long participant answer goes on and on", "whisper") for i in range(20)]
    t = transcript("s1", segs, duration=1090)
    assert moderator_turns(t).reason == "moderator_under_attributed"


def test_no_moderator_is_its_own_state():
    t = transcript("s1", [seg(10, P, "p1", "only the participant speaks here")])
    assert moderator_turns(t).reason == "no_moderator"


def test_unreliable_sessions_are_left_out_and_say_why(tmp_path):
    ts, qs = two_sessions()
    ts.append(transcript("s3", [seg(10, P, "p3", "only the participant speaks here")]))
    record, _ = run(ts, qs, tmp_path, FakeClient())
    assert next(s for s in record.sessions if s.id == "s3").state == "no_moderator"
    assert record.status == "partial"


# ── the guide reader ─────────────────────────────────────────────────────────


def test_no_folder_no_guide(tmp_path):
    assert find_guide(tmp_path) is None


def test_reads_the_newest_and_reports_the_rest(tmp_path):
    folder = write_guide(tmp_path, "old guide")
    newer = folder / "v2.txt"
    newer.write_text("new guide")
    os.utime(folder / "guide.md", (1, 1))
    g = find_guide(tmp_path)
    assert g and g.text == "new guide" and g.ignored == ["guide.md"]


def test_ignores_lock_files_and_dotfiles(tmp_path):
    folder = tmp_path / GUIDE_FOLDER
    folder.mkdir()
    for name in ("~$guide.docx", ".DS_Store"):
        (folder / name).write_text("x")
    assert find_guide(tmp_path) is None  # tool state only: there is no guide


def test_a_guide_in_another_format_is_there_but_unread(tmp_path):
    folder = tmp_path / GUIDE_FOLDER
    folder.mkdir()
    (folder / "notes.pdf").write_text("x")
    g = find_guide(tmp_path)
    assert g is not None and g.problem == "unsupported_format" and g.text == ""


def test_refuses_a_symlinked_folder_and_an_oversize_file(tmp_path):
    real = tmp_path / "elsewhere"
    real.mkdir()
    (real / "guide.md").write_text("x")
    (tmp_path / GUIDE_FOLDER).symlink_to(real, target_is_directory=True)
    g = find_guide(tmp_path)
    assert g is not None and g.problem == "symlink" and g.text == ""  # refused, not "no guide"
    other = tmp_path / "p2"
    folder = other / GUIDE_FOLDER
    folder.mkdir(parents=True)
    (folder / "guide.md").write_bytes(b"x" * (MAX_GUIDE_BYTES + 1))
    g = find_guide(other)
    assert g is not None and g.problem == "too_large" and g.text == ""


def test_an_empty_guide_is_present_but_unreadable(tmp_path):
    write_guide(tmp_path, "   ")
    g = find_guide(tmp_path)
    assert g is not None and g.text == "" and g.sha and g.problem == "unreadable"


@pytest.mark.parametrize("payload", [b"", b"not a zip", b"PK\x03\x04truncated",
                                     b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"])  # last: Word's encrypted container
def test_a_corrupt_or_locked_docx_never_raises(tmp_path, payload):
    folder = tmp_path / GUIDE_FOLDER
    folder.mkdir()
    (folder / "guide.docx").write_bytes(payload)
    g = find_guide(tmp_path)
    assert g is not None and g.problem == "unreadable"


def test_a_zip_that_is_not_a_docx_never_raises(tmp_path):
    import zipfile
    folder = tmp_path / GUIDE_FOLDER
    folder.mkdir()
    with zipfile.ZipFile(folder / "guide.docx", "w") as z:
        z.writestr("hello.txt", "hi")
    assert find_guide(tmp_path).problem == "unreadable"


def test_the_folder_is_found_whatever_its_case_and_ingest_skips_it(tmp_path):
    from bristlenose.discussion.guide import is_guide_folder
    folder = tmp_path / GUIDE_FOLDER.upper()
    folder.mkdir()
    (folder / "guide.md").write_text("# Guide\n- Who do you live with?\n")
    assert is_guide_folder(folder)
    g = find_guide(tmp_path)
    assert g is not None and g.text.startswith("# Guide")


@pytest.mark.parametrize("name", ["discussion-parse-guide", "discussion-classify-turns",
                                  "discussion-consolidate", "discussion-route-quotes"])
def test_prompts_format_without_stray_braces(name):
    from bristlenose.llm.prompts import get_prompt_template
    t = get_prompt_template(name)
    vars_ = set(re.findall(r"\{(\w+)\}", t.user))
    t.user.format(**{v: "x" for v in vars_})  # raises on an unescaped literal brace
