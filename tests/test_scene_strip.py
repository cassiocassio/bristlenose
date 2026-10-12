"""Scene strip: dense per-moment colour for the session tapestry (utils/scene_strip.py)."""

from __future__ import annotations

import base64
import json
import os
import shutil
import struct
import subprocess
import zlib
from pathlib import Path

import pytest

from bristlenose.utils import scene_strip as ss
from bristlenose.utils.scene_colour import rgb_to_oklab

BLUE = (0.45, -0.03, -0.25)
ORANGE = (0.7, 0.12, 0.14)
GREY = (0.6, 0.0, 0.0)


class TestColour:
    def test_mean_of_nothing_is_black(self):
        assert ss.mean_lab([]) == (0.0, 0.0, 0.0)

    def test_mean_is_per_channel(self):
        assert ss.mean_lab([(0.2, 0.1, -0.1), (0.4, 0.3, 0.1)]) == pytest.approx((0.3, 0.2, 0.0))

    def test_tone_lifts_lightness_into_the_strip_band_and_keeps_hue(self):
        lo = ss.tone_strip((0.0, 0.1, -0.1))
        hi = ss.tone_strip((1.0, 0.1, -0.1))
        assert lo[0] == pytest.approx(ss.STRIP_L_MIN) and hi[0] == pytest.approx(ss.STRIP_L_MAX)
        assert lo[1] > 0 and lo[2] < 0  # chroma scaled, sign kept

    def test_rgb_is_in_gamut_even_for_wild_chroma(self):
        for lab in [(0.99, 0.4, 0.4), (0.3, -0.4, 0.4), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]:
            r, g, b = ss.lab_to_rgb(lab)
            assert all(0 <= c <= 255 for c in (r, g, b))
        assert ss.lab_to_rgb((1.0, 0.0, 0.0)) == (255, 255, 255)
        assert ss.lab_to_rgb(ORANGE)[0] > ss.lab_to_rgb(ORANGE)[2]
        assert ss.lab_to_rgb(BLUE)[2] > ss.lab_to_rgb(BLUE)[0]


class TestEdges:
    def test_a_cut_gives_one_notch_at_the_cut(self):
        means = [BLUE] * 40 + [ORANGE] * 40
        assert ss.scene_edges(means, fps=4) == [10.0]

    def test_a_steady_scene_has_no_notch(self):
        assert ss.scene_edges([GREY] * 80, fps=4) == []

    def test_a_slow_fade_still_counts_once(self):
        """Neighbouring samples barely differ across a 3 s fade; the windows see the change."""
        fade = [tuple(a + (b - a) * k / 12 for a, b in zip(BLUE, ORANGE, strict=True)) for k in range(12)]
        means = [BLUE] * 40 + fade + [ORANGE] * 40
        edges = ss.scene_edges(means, fps=4)
        assert len(edges) == 1 and 10.0 <= edges[0] <= 13.0

    def test_small_drift_is_below_the_threshold(self):
        means = [GREY] * 40 + [(0.62, 0.01, 0.0)] * 40
        assert ss.scene_edges(means, fps=4) == []

    def test_too_short_for_a_window_is_empty(self):
        assert ss.scene_edges([BLUE, ORANGE] * 3, fps=4) == []


class TestPng:
    def test_row_png_is_well_formed_and_carries_the_pixels(self):
        pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        png = ss.encode_png_row(pixels)
        assert png.startswith(b"\x89PNG\r\n\x1a\n")
        # IHDR: width 3, height 1, 8-bit RGB
        assert struct.unpack(">IIBBBBB", png[16:29]) == (3, 1, 8, 2, 0, 0, 0)
        # Walk the chunks, checking each CRC, and decompress the one row.
        pos, chunks = 8, {}
        while pos < len(png):
            (length,) = struct.unpack(">I", png[pos:pos + 4])
            tag, body, crc = png[pos + 4:pos + 8], png[pos + 8:pos + 8 + length], png[pos + 8 + length:pos + 12 + length]
            assert struct.unpack(">I", crc)[0] == zlib.crc32(tag + body) & 0xFFFFFFFF
            chunks[tag] = body
            pos += 12 + length
        assert zlib.decompress(chunks[b"IDAT"]) == b"\x00" + bytes(c for p in pixels for c in p)
        assert chunks[b"IEND"] == b""


class TestRecord:
    def test_record_has_png_fps_count_and_edges(self):
        rec = ss.strip_record([BLUE] * 40 + [ORANGE] * 40, fps=4)
        assert rec["version"] == ss.VERSION and rec["fps"] == 4 and rec["n"] == 80 and rec["t0"] == 0.0
        assert base64.b64decode(rec["png"]).startswith(b"\x89PNG")
        assert rec["edges"] == [10.0]

    def test_a_late_stream_start_shifts_the_notches(self):
        rec = ss.strip_record([BLUE] * 40 + [ORANGE] * 40, fps=4, t0=3.5)
        assert rec["t0"] == 3.5 and rec["edges"] == [13.5]


@pytest.fixture
def video(tmp_path: Path) -> Path:
    v = tmp_path / "s1.mp4"
    v.write_bytes(b"not really a video")
    return v


class TestExtract:
    def test_writes_a_record_then_serves_it_from_cache(self, tmp_path, video, monkeypatch):
        calls = []
        monkeypatch.setattr(ss, "sample_dense", lambda v, fps=4: calls.append(v) or (2.0, [BLUE] * 40 + [ORANGE] * 40))
        out = tmp_path / "strips"
        first = ss.extract_scene_strips({"s1": video}, out)
        assert first == {"s1": out / "s1.json"}
        rec = json.loads((out / "s1.json").read_text())
        assert rec["n"] == 80 and rec["t0"] == 2.0 and rec["edges"] == [12.0] and rec["key"]
        assert not (out / "s1.json.tmp").exists()
        ss.extract_scene_strips({"s1": video}, out)
        assert len(calls) == 1  # cached

    def test_a_recording_of_a_new_size_is_resampled(self, tmp_path, video, monkeypatch):
        calls = []
        monkeypatch.setattr(ss, "sample_dense", lambda v, fps=4: calls.append(v) or (0.0, [GREY] * 40))
        out = tmp_path / "strips"
        ss.extract_scene_strips({"s1": video}, out)
        st = video.stat()
        video.write_bytes(b"a different recording, longer")
        os.utime(video, (st.st_atime, st.st_mtime))  # same mtime: only the size says it changed
        ss.extract_scene_strips({"s1": video}, out)
        assert len(calls) == 2

    def test_a_recording_with_a_new_mtime_is_resampled(self, tmp_path, video, monkeypatch):
        calls = []
        monkeypatch.setattr(ss, "sample_dense", lambda v, fps=4: calls.append(v) or (0.0, [GREY] * 40))
        out = tmp_path / "strips"
        ss.extract_scene_strips({"s1": video}, out)
        os.utime(video, (0, 0))  # same bytes: only the mtime says it changed
        ss.extract_scene_strips({"s1": video}, out)
        assert len(calls) == 2

    def test_an_unreadable_cache_is_recomputed(self, tmp_path, video, monkeypatch):
        monkeypatch.setattr(ss, "sample_dense", lambda v, fps=4: (0.0, [GREY] * 40))
        out = tmp_path / "strips"
        out.mkdir()
        (out / "s1.json").write_text("{not json")
        ss.extract_scene_strips({"s1": video}, out)
        assert json.loads((out / "s1.json").read_text())["n"] == 40

    def test_a_failed_sample_leaves_no_file_and_does_not_stop_the_rest(self, tmp_path, monkeypatch):
        v1, v2 = tmp_path / "s1.mp4", tmp_path / "s2.mp4"
        v1.write_bytes(b"x")
        v2.write_bytes(b"y")

        def sample(v, fps=4):
            if v == v1:
                raise RuntimeError("ffmpeg said no")
            return 0.0, [GREY] * 40

        monkeypatch.setattr(ss, "sample_dense", sample)
        out = tmp_path / "strips"
        assert ss.extract_scene_strips({"s1": v1, "s2": v2}, out) == {"s2": out / "s2.json"}
        assert not (out / "s1.json").exists()

    def test_a_missing_recording_is_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ss, "sample_dense", lambda v, fps=4: pytest.fail("should not sample"))
        assert ss.extract_scene_strips({"s1": tmp_path / "gone.mp4"}, tmp_path / "strips") == {}


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_real_video_round_trip(tmp_path):
    """Blue for 2 s then orange, letterboxed: 16 samples at 4 fps, blue then orange, one notch at 2 s."""
    video = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x2850d0:s=320x180:d=2:r=10",
         "-f", "lavfi", "-i", "color=c=0xe08030:s=320x180:d=2:r=10",
         "-filter_complex", "[0][1]concat=n=2:v=1,pad=320:240:0:30:black[v]", "-map", "[v]",
         "-g", "5", "-pix_fmt", "yuv420p", str(video)],
        check=True,
    )
    t0, means = ss.sample_dense(video)
    assert t0 == 0.0
    assert 15 <= len(means) <= 17, len(means)
    first, last = ss.lab_to_rgb(ss.tone_strip(means[0])), ss.lab_to_rgb(ss.tone_strip(means[-1]))
    assert first[2] > first[0]  # blue
    assert last[0] > last[2]    # orange
    # Untoned: the bars (a quarter of the frame, black) were cropped, not averaged in — the mean
    # lightness is the fill colour's own, not three quarters of it.
    assert abs(means[0][0] - rgb_to_oklab(0x28, 0x50, 0xD0)[0]) < 0.05
    assert ss.scene_edges(means) == [2.0]
