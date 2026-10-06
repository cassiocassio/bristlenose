"""Scene colour per speaker turn (bristlenose/utils/scene_colour.py).

The behaviours that matter are the ones the colour lab settled: black bars and call-grid gutters
must not drag the colour to near-black, only a colour that fills at least 15% of the frame may be
picked, and the result is lifted out of the dark range. Plus the cache, so a re-run is free.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bristlenose.models import FileType, FullTranscript, InputFile, InputSession, TranscriptSegment
from bristlenose.utils import scene_colour as sc

W, H = sc.FRAME_W, sc.FRAME_H


def _frame(fill) -> bytes:
    """32×18 RGB frame; fill(x, y) -> (r, g, b)."""
    return bytes(c for y in range(H) for x in range(W) for c in fill(x, y))


def _hex_lightness(hexcol: str) -> float:
    r, g, b = (int(hexcol[i:i + 2], 16) for i in (1, 3, 5))
    return sc.rgb_to_oklab(r, g, b)[0]


class TestFramePixels:
    def test_letterbox_bars_are_cropped(self):
        # Encoded bars are rarely pure black: dark grey (luma 25) sits above the near-black
        # ignore threshold, so only the crop removes it. 3 rows top and bottom, beige picture.
        raw = _frame(lambda x, y: (25, 25, 25) if y < 3 or y >= H - 3 else (200, 170, 140))
        px = sc.frame_pixels(raw)
        assert len(px) == W * (H - 6)
        assert min(p[0] for p in px) > 0.6  # nothing near-black survived

    def test_gutter_pixels_inside_the_picture_are_ignored(self):
        # A black column down the middle (a call-grid gutter) is not an edge bar.
        raw = _frame(lambda x, y: (5, 5, 5) if x in (15, 16) else (90, 140, 200))
        px = sc.frame_pixels(raw)
        assert len(px) == W * H - 2 * H

    def test_white_is_kept(self):
        raw = _frame(lambda x, y: (250, 250, 250))
        assert len(sc.frame_pixels(raw)) == W * H


class TestPickColour:
    def _labs(self, parts):
        out = []
        for rgb, n in parts:
            out += [sc.rgb_to_oklab(*rgb)] * n
        return out

    def test_most_colourful_eligible_cluster_wins(self):
        # 70% grey wall, 30% blue screen: blue fills more than 15%, so it is eligible and wins.
        hexcol, share = sc.pick_colour(self._labs([((120, 118, 115), 700), ((40, 90, 220), 300)]))
        r, g, b = (int(hexcol[i:i + 2], 16) for i in (1, 3, 5))
        assert b > r and b > g
        assert share == pytest.approx(0.3, abs=0.01)

    def test_a_colour_below_the_minimum_share_is_never_picked(self):
        # 10% vivid red is the most colourful thing in the frame, but too small to be honest.
        hexcol, share = sc.pick_colour(self._labs([((120, 118, 115), 900), ((230, 20, 20), 100)]))
        r, g, b = (int(hexcol[i:i + 2], 16) for i in (1, 3, 5))
        assert abs(r - g) < 40  # still the grey family, not red
        assert share >= sc.MIN_SHARE

    def test_dark_rooms_are_lifted(self):
        hexcol, _ = sc.pick_colour(self._labs([((40, 32, 28), 500)]))
        assert _hex_lightness(hexcol) >= sc.TONE_L_MIN - 0.01

    def test_no_pixels_no_colour(self):
        assert sc.pick_colour([]) is None


def _transcript(segs) -> FullTranscript:
    return FullTranscript(
        session_id="s1", participant_id="p1", source_file="v.mp4",
        session_date=datetime(2026, 1, 1, tzinfo=timezone.utc), duration_seconds=60.0,
        segments=[TranscriptSegment(start_time=a, end_time=b, text="x", speaker_code=c) for a, b, c in segs],
    )


class TestTurns:
    def test_consecutive_segments_merge_and_turns_reach_the_next_start(self):
        t = _transcript([(0, 4, "m1"), (5, 9, "m1"), (12, 20, "p1"), (21, 30, "m1")])
        assert sc.turns_of(t) == [(0, 12, "m1"), (12, 21, "p1"), (21, 30, "m1")]

    def test_a_short_turn_between_keyframes_takes_the_nearest(self):
        kf = [(0.0, [sc.rgb_to_oklab(200, 170, 140)] * 50), (10.0, [sc.rgb_to_oklab(40, 90, 220)] * 50)]
        out = sc.session_scene_colours(kf, [(8.5, 9.5, "p1")])
        r, g, b = (int(out[0]["colour"][i:i + 2], 16) for i in (1, 3, 5))
        assert b > r  # nearest keyframe (10 s, blue), not the earlier beige


def _session(video: Path) -> InputSession:
    return InputSession(
        session_id="s1", session_number=1, participant_id="p1", participant_number=1,
        session_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        files=[InputFile(path=video, file_type=FileType.VIDEO,
                         created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), size_bytes=video.stat().st_size)],
    )


class TestCache:
    def test_rerun_is_free_until_the_turns_change(self, tmp_path, monkeypatch):
        video = tmp_path / "v.mp4"
        video.write_bytes(b"not really a video")
        calls = []

        def fake_sample(path):
            calls.append(path)
            return [(1.0, [sc.rgb_to_oklab(200, 170, 140)] * 50)]

        monkeypatch.setattr(sc, "sample_keyframes", fake_sample)
        out = tmp_path / "scene-colours"
        t1 = _transcript([(0, 10, "m1"), (10, 20, "p1")])
        sc.extract_scene_colours([_session(video)], [t1], out)
        sc.extract_scene_colours([_session(video)], [t1], out)
        assert len(calls) == 1
        data = json.loads((out / "s1.json").read_text())
        assert [t["speaker"] for t in data["turns"]] == ["m1", "p1"]

        t2 = _transcript([(0, 10, "m1"), (10, 15, "p1"), (15, 20, "m1")])
        sc.extract_scene_colours([_session(video)], [t2], out)
        assert len(calls) == 2

    def test_a_failed_sample_leaves_no_file(self, tmp_path, monkeypatch):
        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")

        def broken(path):
            raise RuntimeError("ffmpeg said no")

        monkeypatch.setattr(sc, "sample_keyframes", broken)
        out = tmp_path / "scene-colours"
        assert sc.extract_scene_colours([_session(video)], [_transcript([(0, 5, "p1")])], out) == {}
        assert not (out / "s1.json").exists()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_real_video_round_trip(tmp_path):
    """A letterboxed clip: blue for 2 s then orange, with black bars. The bars must not darken it."""
    video = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x2850d0:s=320x180:d=2:r=10",
         "-f", "lavfi", "-i", "color=c=0xe08030:s=320x180:d=2:r=10",
         "-filter_complex", "[0][1]concat=n=2:v=1,pad=320:240:0:30:black[v]", "-map", "[v]",
         "-g", "5", "-pix_fmt", "yuv420p", str(video)],
        check=True,
    )
    kf = sc.sample_keyframes(video)
    assert kf, "no keyframes sampled"
    out = sc.session_scene_colours(kf, [(0.0, 2.0, "m1"), (2.0, 4.0, "p1")])
    first = [int(out[0]["colour"][i:i + 2], 16) for i in (1, 3, 5)]
    second = [int(out[1]["colour"][i:i + 2], 16) for i in (1, 3, 5)]
    assert first[2] > first[0]   # blue
    assert second[0] > second[2]  # orange
    assert _hex_lightness(out[0]["colour"]) > 0.45  # bars cropped, not averaged in
