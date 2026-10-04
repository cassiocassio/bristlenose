"""The stage 5b voice pass (stages/s05b_voice.py).

The decisions — cluster, match clusters to the text splitter's names, decline
and say why — are tested with synthetic embeddings, so no model, audio or
network is involved. ffmpeg is faked too (a skipif on its absence would count
against the skip ratchet); real decoding and the real model are exercised by
experiments/speaker_split_full/eval_voice.py --audio. The pipeline tests drive
the real ``Pipeline.run`` with the pass faked, to pin what it writes to the
speaker cache.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from bristlenose.models import TranscriptSegment, Word
from bristlenose.stages import s05b_voice as voice


def _seg(i: int, label: str | None, dur: float = 3.0, words: bool = False) -> TranscriptSegment:
    start = i * 10.0
    seg = TranscriptSegment(start_time=start, end_time=start + dur, text=f"line {i}",
                            speaker_label=label, source="mlx-whisper")
    if words:
        seg.words = [Word(text="a", start_time=start + 0.5, end_time=start + dur - 0.5)]
    return seg


def _embedder(truth: dict[float, int], noise: float = 0.05, seed: int = 1):
    """An embed(start, end) that returns one of two voice directions plus noise."""
    rng = np.random.default_rng(seed)
    dirs = np.eye(16)[:2]

    def embed(a: float, _b: float):
        return dirs[truth[a]] + rng.normal(0, noise, 16)

    return embed


# ── cluster_voices ─────────────────────────────────────────────────────────


class TestClusterVoices:
    def test_two_voices_come_back_as_two_clusters(self) -> None:
        who = [0, 1] * 6
        spans = [(i * 10.0, i * 10.0 + 3.0) for i in range(12)]
        vc = voice.cluster_voices(spans, _embedder({a: w for (a, _), w in zip(spans, who)}))
        assert vc is not None
        # Same partition as the truth, whichever way round the ids fall.
        assert len({(c, w) for c, w in zip(vc.clusters, who)}) == 2
        assert vc.centroid_cos < 0.3
        assert vc.fit_segments == 12

    def test_a_span_too_short_to_embed_gets_no_verdict(self) -> None:
        spans = [(i * 10.0, i * 10.0 + 3.0) for i in range(10)] + [(200.0, 200.4)]
        truth = {a: i % 2 for i, (a, _) in enumerate(spans)}
        vc = voice.cluster_voices(spans, _embedder(truth))
        assert vc is not None
        assert vc.clusters[-1] is None and vc.margins[-1] == 0.0

    def test_an_empty_or_nan_embedding_is_no_verdict_not_a_voice(self) -> None:
        """sherpa-onnx returns an EMPTY vector for an empty slice rather than
        raising; before the guard, empty vectors clustered as one voice and the
        whole session was relabelled to one speaker, recorded as success."""
        spans = [(i * 10.0, i * 10.0 + 3.0) for i in range(12)]
        truth = {a: i % 2 for i, (a, _) in enumerate(spans)}
        real = _embedder(truth)

        def embed(a, b):
            if a == 0.0:
                return np.array([])
            if a == 10.0:
                return np.full(16, np.nan)
            return real(a, b)

        vc = voice.cluster_voices(spans, embed)
        assert vc is not None and vc.clusters[:2] == [None, None]
        assert vc.fit_segments == 10

    def test_all_empty_embeddings_decline_rather_than_relabel(self) -> None:
        spans = [(i * 10.0, i * 10.0 + 3.0) for i in range(12)]
        assert voice.cluster_voices(spans, lambda a, b: np.array([])) is None

    def test_spans_are_clamped_to_the_audio(self) -> None:
        segs = [_seg(0, None, dur=4.0), _seg(1, None, dur=4.0), _seg(2, None, dur=4.0)]
        # 12 s of audio: the third segment (20–24 s) lies wholly past the end.
        spans = voice.segment_spans(segs, audio_seconds=12.0)
        assert spans[1] == (10.0, 12.0)
        assert spans[2][1] - spans[2][0] <= 0  # no audio left, so no verdict later

    def test_too_few_long_segments_is_no_answer(self) -> None:
        spans = [(i * 10.0, i * 10.0 + 1.0) for i in range(20)]  # all under MIN_FIT_S
        assert voice.cluster_voices(spans, _embedder({a: 0 for a, _ in spans})) is None

    def test_spans_come_from_word_timings_when_there_are_words(self) -> None:
        segs = [_seg(0, None, dur=4.0, words=True), _seg(1, None, dur=4.0)]
        assert voice.segment_spans(segs) == [(0.5, 3.5), (10.0, 14.0)]


# ── merge_voice_and_text ───────────────────────────────────────────────────


def _clusters(clusters: list[int | None], cos: float = 0.3) -> voice.VoiceClusters:
    return voice.VoiceClusters(clusters, [0.5] * len(clusters), cos, len(clusters))


class TestMerge:
    def test_voice_relabels_and_keeps_the_text_splitters_names(self) -> None:
        # Text got segment 3 wrong; voice cluster 1 is "Speaker B" throughout.
        segs = [_seg(i, lab) for i, lab in enumerate(
            ["Speaker A", "Speaker B", "Speaker A", "Speaker A", "Speaker A", "Speaker B"])]
        relabelled, reason = voice.merge_voice_and_text(segs, _clusters([0, 1, 0, 1, 0, 1]))
        assert reason == ""
        assert relabelled == 1
        assert [s.speaker_label for s in segs] == [
            "Speaker A", "Speaker B", "Speaker A", "Speaker B", "Speaker A", "Speaker B"]

    def test_cluster_ids_are_matched_whichever_way_round_they_fall(self) -> None:
        segs = [_seg(i, lab) for i, lab in enumerate(["Speaker A", "Speaker B"] * 3)]
        voice.merge_voice_and_text(segs, _clusters([1, 0] * 3))
        assert [s.speaker_label for s in segs] == ["Speaker A", "Speaker B"] * 3

    def test_a_segment_with_no_verdict_keeps_its_text_label(self) -> None:
        segs = [_seg(i, lab) for i, lab in enumerate(["Speaker A", "Speaker B", "Speaker B"])]
        voice.merge_voice_and_text(segs, _clusters([0, 1, None]))
        assert segs[2].speaker_label == "Speaker B"

    def test_three_text_speakers_are_left_alone(self) -> None:
        segs = [_seg(i, lab) for i, lab in enumerate(["A", "B", "C", "A"])]
        relabelled, reason = voice.merge_voice_and_text(segs, _clusters([0, 1, 1, 1]))
        assert relabelled == 0 and "3 speakers" in reason
        assert [s.speaker_label for s in segs] == ["A", "B", "C", "A"]

    def test_one_text_speaker_is_left_alone(self) -> None:
        segs = [_seg(i, None) for i in range(4)]
        relabelled, reason = voice.merge_voice_and_text(segs, _clusters([0, 1, 0, 1]))
        assert relabelled == 0 and "0 speakers" in reason

    def test_one_text_speaker_reads_in_the_singular(self) -> None:
        segs = [_seg(i, "A") for i in range(3)]
        assert "found 1 speaker;" in voice.text_split_reason(segs)

    def test_a_nan_centroid_cosine_declines(self) -> None:
        segs = [_seg(i, lab) for i, lab in enumerate(["A", "B", "A", "B"])]
        relabelled, reason = voice.merge_voice_and_text(segs, _clusters([0, 0, 0, 0], cos=float("nan")))
        assert relabelled == 0 and "not distinct" in reason

    def test_voice_overruling_text_on_most_lines_changes_nothing(self) -> None:
        """One person's voice split in two would disagree with the text split
        wholesale; that is declined, counted before any label moves."""
        labels = ["A"] * 6 + ["B"] * 6
        segs = [_seg(i, lab) for i, lab in enumerate(labels)]
        relabelled, reason = voice.merge_voice_and_text(segs, _clusters([0, 1] * 6))
        assert relabelled == 0 and "disagree on 6 of 12" in reason
        assert [s.speaker_label for s in segs] == labels

    def test_voices_that_are_not_distinct_change_nothing(self) -> None:
        segs = [_seg(i, lab) for i, lab in enumerate(["A", "B", "A", "B"])]
        relabelled, reason = voice.merge_voice_and_text(segs, _clusters([0, 0, 0, 1], cos=0.9))
        assert relabelled == 0 and "not distinct" in reason
        assert [s.speaker_label for s in segs] == ["A", "B", "A", "B"]


# ── refine_speakers_by_voice: declines are recorded, never raised ──────────


class TestRefine:
    def _segs(self) -> list[TranscriptSegment]:
        return [_seg(i, "Speaker A" if i % 2 == 0 else "Speaker B") for i in range(12)]

    def test_unavailable_is_recorded_with_its_reason(self) -> None:
        rec = voice.refine_speakers_by_voice(self._segs(), Path("x.wav"), None,
                                             unavailable_reason="voice extra not installed")
        assert rec.method == "text" and rec.reason == "voice extra not installed"

    def test_no_audio_and_no_model_are_recorded(self) -> None:
        assert voice.refine_speakers_by_voice(self._segs(), None, Path("m")).reason == (
            "no audio extracted for this session (it came with a transcript)")
        assert voice.refine_speakers_by_voice(self._segs(), Path("a"), None).reason == (
            "voice model unavailable")

    def test_a_text_split_it_cannot_refine_is_declined_before_decoding(self) -> None:
        segs = [_seg(i, lab) for i, lab in enumerate(["A", "B", "C"] * 4)]
        with patch.object(voice, "load_audio_16k") as load:
            rec = voice.refine_speakers_by_voice(segs, Path("a.wav"), Path("m.onnx"))
        load.assert_not_called()
        assert rec.method == "text" and "3 speakers" in rec.reason

    def test_audio_that_decodes_to_nothing_is_a_recorded_failure(self) -> None:
        segs = self._segs()
        before = [s.speaker_label for s in segs]
        with (
            patch("bristlenose.utils.fs.ensure_materialised"),
            patch.object(voice.subprocess, "run", return_value=_Done(0, b"")),
        ):
            rec = voice.refine_speakers_by_voice(segs, Path("empty.wav"), Path("m.onnx"))
        assert rec.method == "text" and "decoded no audio" in rec.reason
        assert [s.speaker_label for s in segs] == before

    def test_a_failure_leaves_the_text_labels_and_says_so(self) -> None:
        segs = self._segs()
        before = [s.speaker_label for s in segs]
        with patch.object(voice, "load_audio_16k", side_effect=RuntimeError("bad file")):
            rec = voice.refine_speakers_by_voice(segs, Path("a.wav"), Path("m.onnx"))
        assert rec.method == "text" and rec.reason == "voice pass failed: bad file"
        assert [s.speaker_label for s in segs] == before

    def test_success_records_method_counts_and_time(self) -> None:
        segs = self._segs()
        segs[3].speaker_label = "Speaker A"  # the text splitter's mistake
        truth = {s.start_time: i % 2 for i, s in enumerate(segs)}
        with (
            patch.object(voice, "load_audio_16k",
                         return_value=np.full(130 * voice.SAMPLE_RATE, 0.1, dtype=np.float32)),
            patch.object(voice, "_sherpa_embedder", return_value=_embedder(truth)),
        ):
            rec = voice.refine_speakers_by_voice(segs, Path("a.wav"), Path("m.onnx"))
        assert rec.method == "voice+text" and rec.reason == ""
        assert rec.voice_verdicts == 12 and rec.relabelled == 1
        assert segs[3].speaker_label == "Speaker B"
        assert rec.elapsed_ms >= 0 and rec.centroid_cos is not None
        d = rec.to_dict()
        assert d["voice_version"] == voice.VOICE_VERSION
        assert d["voice_model"] == voice.VOICE_MODEL_NAME


# ── the model file ─────────────────────────────────────────────────────────


class _Resp(io.BytesIO):
    def geturl(self) -> str:
        return voice.VOICE_MODEL_URL

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestModel:
    @pytest.fixture(autouse=True)
    def _cache(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SNAP_USER_COMMON", raising=False)
        monkeypatch.delenv(voice.VOICE_MODEL_ENV, raising=False)
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    def test_in_the_mac_app_the_model_lives_in_library_caches(self, tmp_path, monkeypatch) -> None:
        import sys

        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", "1")
        monkeypatch.setenv("HOME", str(tmp_path))
        assert voice.voice_model_cache_path() == (
            tmp_path / "Library" / "Caches" / "bristlenose" / "models" / voice.VOICE_MODEL_NAME)

    def test_cache_path_honours_snap_and_xdg(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
        assert voice.voice_model_cache_path() == tmp_path / "bristlenose" / "models" / voice.VOICE_MODEL_NAME
        monkeypatch.setenv("SNAP_USER_COMMON", str(tmp_path / "snap"))
        assert voice.voice_model_cache_path() == tmp_path / "snap" / "models" / voice.VOICE_MODEL_NAME

    def test_no_fetch_declines_without_touching_the_network(self) -> None:
        with patch("urllib.request.urlopen") as urlopen:
            path, reason = voice.resolve_voice_model(allow_fetch=False)
        assert path is None and "no-fetch" in reason
        urlopen.assert_not_called()

    def test_override_names_a_file_or_says_it_is_missing(self, tmp_path, monkeypatch) -> None:
        model = tmp_path / "bundled.onnx"
        model.write_bytes(b"x")
        monkeypatch.setenv(voice.VOICE_MODEL_ENV, str(model))
        assert voice.resolve_voice_model(allow_fetch=False) == (model, "")
        monkeypatch.setenv(voice.VOICE_MODEL_ENV, str(tmp_path / "missing.onnx"))
        path, reason = voice.resolve_voice_model(allow_fetch=True)
        assert path is None and voice.VOICE_MODEL_ENV in reason

    def test_a_download_with_the_wrong_hash_is_refused_and_not_kept(self) -> None:
        with patch("urllib.request.urlopen", return_value=_Resp(b"not the model")):
            path, reason = voice.resolve_voice_model(allow_fetch=True)
        assert path is None and "hash mismatch" in reason
        assert not voice.voice_model_cache_path().exists()
        assert list(voice.voice_model_cache_path().parent.glob("*.part")) == []

    def test_a_download_larger_than_the_model_is_refused(self, monkeypatch) -> None:
        monkeypatch.setattr(voice, "VOICE_MODEL_BYTES", 4)
        with patch("urllib.request.urlopen", return_value=_Resp(b"far too many bytes")):
            path, reason = voice.resolve_voice_model(allow_fetch=True)
        assert path is None and "larger than expected" in reason

    def test_a_cached_file_that_fails_its_hash_is_not_used(self, monkeypatch) -> None:
        monkeypatch.setattr(voice, "VOICE_MODEL_BYTES", 5)
        cache = voice.voice_model_cache_path()
        cache.parent.mkdir(parents=True)
        cache.write_bytes(b"wrong")  # the right size, the wrong bytes
        assert voice.cached_voice_model() == cache  # doctor's cheap look accepts it
        path, reason = voice.resolve_voice_model(allow_fetch=False)
        assert path is None and "no-fetch" in reason

    def test_a_verified_download_lands_in_the_cache(self, monkeypatch) -> None:
        payload = b"pretend model bytes"
        monkeypatch.setattr(voice, "VOICE_MODEL_SHA256", hashlib.sha256(payload).hexdigest())
        monkeypatch.setattr(voice, "VOICE_MODEL_BYTES", len(payload))
        with patch("urllib.request.urlopen", return_value=_Resp(payload)):
            path, reason = voice.resolve_voice_model(allow_fetch=True)
        assert reason == "" and path == voice.voice_model_cache_path()
        assert path.read_bytes() == payload
        assert voice.cached_voice_model() == path  # the next run needs no fetch


# ── audio ──────────────────────────────────────────────────────────────────


class _Done:
    def __init__(self, returncode: int, stdout: bytes = b"", stderr: bytes = b"") -> None:
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


class TestAudio:
    """Our half of decoding: the ffmpeg command and the sample conversion.

    ffmpeg itself is not run here (a skipif on its absence would count against
    the skip ratchet); real decoding is exercised end to end by
    experiments/speaker_split_full/eval_voice.py --audio.
    """

    def test_asks_ffmpeg_for_16k_mono_pcm_and_scales_to_float(self, tmp_path) -> None:
        pcm = np.array([0, 16384, -32768, 32767], dtype=np.int16).tobytes()
        with (
            patch("bristlenose.utils.fs.ensure_materialised"),
            patch.object(voice.subprocess, "run", return_value=_Done(0, pcm)) as run,
        ):
            audio = voice.load_audio_16k(tmp_path / "talk.m4a")
        cmd = run.call_args.args[0]
        assert cmd[cmd.index("-ar") + 1] == "16000" and cmd[cmd.index("-ac") + 1] == "1"
        assert cmd[cmd.index("-f") + 1] == "s16le" and cmd[-1] == "-"
        assert cmd[cmd.index("-i") + 1] == str(tmp_path / "talk.m4a")
        assert audio.dtype == np.float32
        assert audio.tolist() == pytest.approx([0.0, 0.5, -1.0, 32767 / 32768])

    def test_a_decode_failure_raises_with_ffmpegs_reason(self, tmp_path) -> None:
        with (
            patch("bristlenose.utils.fs.ensure_materialised"),
            patch.object(voice.subprocess, "run", return_value=_Done(1, b"", b"Invalid data")),
            pytest.raises(RuntimeError, match="Invalid data"),
        ):
            voice.load_audio_16k(tmp_path / "broken.mp4")


# ── the pipeline record ────────────────────────────────────────────────────


class TestPipelineRecord:
    """What the real Pipeline.run writes to the speaker cache."""

    def _run(self, tmp_path, monkeypatch, sessions, *, available=True):
        from tests.test_pipeline_platform_transcripts import run_pipeline

        monkeypatch.setenv("BRISTLENOSE_VOICE_PASS", "true")
        calls = []

        def _fake_refine(segments, audio_path, model_path, *, unavailable_reason=""):
            calls.append((audio_path, model_path, unavailable_reason))
            rec = voice.VoiceRecord(segments=len(segments), reason=unavailable_reason)
            if not unavailable_reason:
                segments[-1].speaker_label = "Speaker A"  # voice moved the last line
                rec.method, rec.relabelled, rec.voice_verdicts = "voice+text", 1, len(segments)
            return rec

        with (
            patch.object(voice, "voice_runtime_available", return_value=available),
            patch.object(voice, "cached_voice_model", return_value=None),
            patch.object(voice, "resolve_voice_model", return_value=(Path("/m.onnx"), "")),
            patch.object(voice, "refine_speakers_by_voice", new=_fake_refine),
        ):
            h = run_pipeline(tmp_path, sessions)
        return h, calls

    def _record(self, h, sid: str) -> dict:
        return json.loads((h.intermediate / "speaker-info" / f"{sid}.json").read_text())[
            "speaker_split"]

    def test_a_voice_checked_session_is_recorded_and_relabelled(self, tmp_path, monkeypatch) -> None:
        from tests.test_pipeline_platform_transcripts import audio_session

        h, calls = self._run(tmp_path, monkeypatch, lambda d, _i: [audio_session(d, 1, "bare")])
        assert len(calls) == 1 and calls[0][1] == Path("/m.onnx")
        assert calls[0][0] is not None  # the session's audio reached the pass
        rec = self._record(h, "s1")
        assert rec["method"] == "voice+text" and rec["relabelled"] == 1
        assert rec["voice_version"] == voice.VOICE_VERSION
        assert h.speaker_segments("s1")[-1].speaker_label == "Speaker A"
        assert "voice_pass | session=s1 | method=voice+text" in h.log()

    def test_without_the_extra_the_text_labels_stand_and_the_reason_is_kept(
        self, tmp_path, monkeypatch,
    ) -> None:
        from tests.test_pipeline_platform_transcripts import audio_session

        h, calls = self._run(tmp_path, monkeypatch, lambda d, _i: [audio_session(d, 1, "bare")],
                             available=False)
        rec = self._record(h, "s1")
        assert rec["method"] == "text" and "voice extra not installed" in rec["reason"]

    def test_a_named_platform_transcript_never_reaches_the_pass(self, tmp_path, monkeypatch) -> None:
        from tests.test_pipeline_platform_transcripts import TEAMS_PAIR, pair_session

        h, calls = self._run(tmp_path, monkeypatch,
                             lambda d, _i: [pair_session(d, 1, "P07", TEAMS_PAIR)])
        assert calls == []
        assert self._record(h, "s1") == {"method": "transcript-labels"}

    def test_one_named_account_is_recorded_as_not_separated(self, tmp_path, monkeypatch) -> None:
        from tests.test_pipeline_platform_transcripts import IN_ROOM_ONE_ACCOUNT, pair_session

        h, calls = self._run(tmp_path, monkeypatch,
                             lambda d, _i: [pair_session(d, 1, "In-room", IN_ROOM_ONE_ACCOUNT)])
        assert calls == []
        assert self._record(h, "s1") == {"method": "not-separated"}

    def test_switched_off_is_recorded(self, tmp_path, monkeypatch) -> None:
        from tests.test_pipeline_platform_transcripts import audio_session, run_pipeline

        monkeypatch.setenv("BRISTLENOSE_VOICE_PASS", "false")
        with patch.object(voice, "voice_runtime_available", return_value=True):
            h = run_pipeline(tmp_path, lambda d, _i: [audio_session(d, 1, "bare")])
        rec = self._record(h, "s1")
        assert rec["method"] == "text" and "switched off" in rec["reason"]


# ── doctor ─────────────────────────────────────────────────────────────────


class TestDoctor:
    def _check(self, monkeypatch, *, on=True, installed=True, cached=None):
        from bristlenose.config import BristlenoseSettings
        from bristlenose.doctor import check_voice

        monkeypatch.setenv("BRISTLENOSE_VOICE_PASS", "true" if on else "false")
        with (
            patch.object(voice, "voice_runtime_available", return_value=installed),
            patch.object(voice, "cached_voice_model", return_value=cached),
        ):
            return check_voice(BristlenoseSettings())

    def test_never_a_failure_whatever_the_state(self, monkeypatch) -> None:
        from bristlenose.doctor import CheckStatus

        states = [
            self._check(monkeypatch, on=False),
            self._check(monkeypatch, installed=False),
            self._check(monkeypatch),
            self._check(monkeypatch, cached=Path("/m.onnx")),
        ]
        assert [r.status for r in states] == [
            CheckStatus.SKIP, CheckStatus.SKIP, CheckStatus.SKIP, CheckStatus.OK]
        assert "switched off" in states[0].detail
        assert "bristlenose[voice]" in states[1].detail
        assert "doctor --fetch" in states[2].detail

    def test_in_the_mac_app_no_cli_command_is_suggested(self, monkeypatch) -> None:
        monkeypatch.setenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", "1")
        result = self._check(monkeypatch)
        assert "first analysis" in result.detail
        assert "bristlenose" not in result.detail and "pip" not in result.detail

    def test_an_override_says_what_runs_will_do(self, monkeypatch, tmp_path) -> None:
        from bristlenose.config import BristlenoseSettings
        from bristlenose.doctor import CheckStatus, check_voice

        monkeypatch.setenv("BRISTLENOSE_VOICE_PASS", "true")
        monkeypatch.setenv(voice.VOICE_MODEL_ENV, str(tmp_path / "missing.onnx"))
        with patch.object(voice, "voice_runtime_available", return_value=True):
            missing = check_voice(BristlenoseSettings())
            (tmp_path / "missing.onnx").write_bytes(b"x")
            present = check_voice(BristlenoseSettings())
        assert missing.status == CheckStatus.WARN and "does not exist" in missing.detail
        assert present.status == CheckStatus.OK and "not hash-checked" in present.detail


class TestBundleSelfTest:
    """doctor --self-test runs pre-sign inside the frozen sidecar."""

    def test_present_and_loadable(self) -> None:
        from bristlenose.doctor import CheckStatus, check_bundle_voice

        result = check_bundle_voice()
        if voice.voice_runtime_available():
            assert result.status == CheckStatus.OK and "load" in result.detail
        else:
            assert result.status == CheckStatus.OK and "not installed" in result.detail

    def test_missing_in_a_frozen_bundle_fails_the_build(self, monkeypatch) -> None:
        import sys

        from bristlenose.doctor import CheckStatus, check_bundle_voice

        monkeypatch.setattr(voice, "voice_runtime_available", lambda: False)
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        frozen = check_bundle_voice()
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        loose = check_bundle_voice()
        assert frozen.status == CheckStatus.FAIL and "missing from the bundle" in frozen.detail
        assert loose.status == CheckStatus.OK

    def test_installed_but_unloadable_fails_everywhere(self, monkeypatch) -> None:
        import builtins
        import sys

        from bristlenose.doctor import CheckStatus, check_bundle_voice

        real_import = builtins.__import__

        def broken(name, *a, **kw):
            if name == "sherpa_onnx":
                raise OSError("dlopen: libonnxruntime.dylib not found")
            return real_import(name, *a, **kw)

        monkeypatch.setattr(voice, "voice_runtime_available", lambda: True)
        monkeypatch.setattr(builtins, "__import__", broken)
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        result = check_bundle_voice()
        assert result.status == CheckStatus.FAIL and "libonnxruntime" in result.detail
