"""Tests for FFmpeg clip extraction backend — mocked subprocess."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bristlenose.server.clip_backend import ClipBackend, FFmpegBackend


class TestFFmpegBackendProtocol:
    def test_implements_protocol(self) -> None:
        assert isinstance(FFmpegBackend(), ClipBackend)


class TestCheckAvailable:
    def test_available(self) -> None:
        with patch(
            "bristlenose.server.clip_backend.bundled_binary_path",
            return_value="/usr/bin/ffmpeg",
        ):
            ok, msg = FFmpegBackend().check_available()
            assert ok is True
            assert msg == ""

    def test_not_available(self) -> None:
        with patch(
            "bristlenose.server.clip_backend.bundled_binary_path",
            return_value=None,
        ):
            ok, msg = FFmpegBackend().check_available()
            assert ok is False
            assert "not found" in msg.lower()


class TestExtractClip:
    def test_success(self, tmp_path: Path) -> None:
        source = tmp_path / "source.mp4"
        source.write_bytes(b"fake video")
        output = tmp_path / "clips" / "clip.mp4"

        mock_result = MagicMock(returncode=0, stderr="")
        with patch("bristlenose.server.clip_backend.subprocess.run", return_value=mock_result):
            # Create the output file to simulate FFmpeg writing it
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"fake clip data")

            result = FFmpegBackend().extract_clip(source, output, 10.0, 20.0)
            assert result == output

    def test_ffmpeg_command_args(self, tmp_path: Path) -> None:
        source = tmp_path / "source.mp4"
        source.write_bytes(b"fake")
        output = tmp_path / "clip.mp4"

        mock_result = MagicMock(returncode=0, stderr="")
        with patch("bristlenose.server.clip_backend.subprocess.run", return_value=mock_result) as mock_run:
            output.write_bytes(b"clip")
            FFmpegBackend().extract_clip(source, output, 10.5, 25.3)

            args = mock_run.call_args[0][0]
            assert args[0].endswith("ffmpeg")
            assert "-ss" in args
            assert "-to" in args
            assert "-c" in args
            assert "copy" in args
            assert "-y" in args
            assert str(source) in args
            assert str(output) in args

    def test_nonzero_exit_returns_none(self, tmp_path: Path) -> None:
        source = tmp_path / "source.mp4"
        source.write_bytes(b"fake")
        output = tmp_path / "clip.mp4"

        mock_result = MagicMock(returncode=1, stderr="Error: corrupt file")
        with patch("bristlenose.server.clip_backend.subprocess.run", return_value=mock_result):
            result = FFmpegBackend().extract_clip(source, output, 10.0, 20.0)
            assert result is None

    def test_timeout_returns_none(self, tmp_path: Path) -> None:
        source = tmp_path / "source.mp4"
        source.write_bytes(b"fake")
        output = tmp_path / "clip.mp4"

        import subprocess
        with patch(
            "bristlenose.server.clip_backend.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=120),
        ):
            result = FFmpegBackend().extract_clip(source, output, 10.0, 20.0)
            assert result is None

    def test_ffmpeg_not_found_returns_none(self, tmp_path: Path) -> None:
        source = tmp_path / "source.mp4"
        source.write_bytes(b"fake")
        output = tmp_path / "clip.mp4"

        with patch(
            "bristlenose.server.clip_backend.subprocess.run",
            side_effect=FileNotFoundError("ffmpeg not found"),
        ):
            result = FFmpegBackend().extract_clip(source, output, 10.0, 20.0)
            assert result is None

    def test_empty_output_returns_none(self, tmp_path: Path) -> None:
        source = tmp_path / "source.mp4"
        source.write_bytes(b"fake")
        output = tmp_path / "clip.mp4"

        mock_result = MagicMock(returncode=0, stderr="")
        with patch("bristlenose.server.clip_backend.subprocess.run", return_value=mock_result):
            # Don't create the output file — simulates FFmpeg silently failing
            result = FFmpegBackend().extract_clip(source, output, 10.0, 20.0)
            assert result is None

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        source = tmp_path / "source.mp4"
        source.write_bytes(b"fake")
        output = tmp_path / "deep" / "nested" / "clip.mp4"

        mock_result = MagicMock(returncode=0, stderr="")
        with patch("bristlenose.server.clip_backend.subprocess.run", return_value=mock_result):
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"clip")
            result = FFmpegBackend().extract_clip(source, output, 10.0, 20.0)
            assert result == output

    @pytest.mark.parametrize("timeout", [120])
    def test_timeout_value(self, tmp_path: Path, timeout: int) -> None:
        source = tmp_path / "source.mp4"
        source.write_bytes(b"fake")
        output = tmp_path / "clip.mp4"

        mock_result = MagicMock(returncode=0, stderr="")
        with patch("bristlenose.server.clip_backend.subprocess.run", return_value=mock_result) as mock_run:
            output.write_bytes(b"clip")
            FFmpegBackend().extract_clip(source, output, 10.0, 20.0)
            assert mock_run.call_args[1]["timeout"] == timeout


class TestSubtitleMux:
    def _run(self, tmp_path: Path, subtitles: Path | None) -> list[str]:
        source = tmp_path / "source.mp4"
        source.write_bytes(b"fake")
        output = tmp_path / "clip.mp4"
        output.write_bytes(b"clip")
        mock_result = MagicMock(returncode=0, stderr="")
        with patch(
            "bristlenose.server.clip_backend.subprocess.run", return_value=mock_result,
        ) as mock_run:
            FFmpegBackend().extract_clip(source, output, 10.0, 20.0, subtitles)
        return list(mock_run.call_args[0][0])

    def test_without_subtitles_first_video_and_audio_only(self, tmp_path: Path) -> None:
        args = self._run(tmp_path, None)
        assert args[1:] == [
            "-ss", "10.000", "-to", "20.000", "-i", str(tmp_path / "source.mp4"),
            "-map", "0:v:0?", "-map", "0:a:0?",
            "-c", "copy", "-y", str(tmp_path / "clip.mp4"),
        ]

    def test_subtitles_are_a_second_input_muxed_as_mov_text(self, tmp_path: Path) -> None:
        srt = tmp_path / "clip.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n")
        args = self._run(tmp_path, srt)
        joined = " ".join(args)
        assert f"-i {srt}" in joined
        # The same first video and audio as a plain cut, plus the subtitles:
        # every-stream mapping let a second audio track fail the mux.
        assert "-map 0:v:0? -map 0:a:0? -map 1:0" in joined
        assert "-c copy -c:s mov_text" in joined
        # Untagged (und), QuickTime's "subtitles in my language" can't find it.
        assert "-metadata:s:s:0 language=und" in joined
        # The seek stays an input option on the source, before its -i.
        assert args.index("-ss") < args.index(str(tmp_path / "source.mp4"))

    def test_subtitle_track_carries_the_language(self, tmp_path: Path) -> None:
        source = tmp_path / "source.mp4"
        source.write_bytes(b"fake")
        output = tmp_path / "clip.mp4"
        output.write_bytes(b"clip")
        srt = tmp_path / "clip.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n")
        mock_result = MagicMock(returncode=0, stderr="")
        with patch(
            "bristlenose.server.clip_backend.subprocess.run", return_value=mock_result,
        ) as mock_run:
            FFmpegBackend().extract_clip(source, output, 1.0, 2.0, srt, "jpn")
        assert "-metadata:s:s:0 language=jpn" in " ".join(mock_run.call_args[0][0])

    def test_audio_clip_takes_no_video(self, tmp_path: Path) -> None:
        source = tmp_path / "source.m4a"
        source.write_bytes(b"fake")
        output = tmp_path / "clip.m4a"
        output.write_bytes(b"clip")
        mock_result = MagicMock(returncode=0, stderr="")
        with patch(
            "bristlenose.server.clip_backend.subprocess.run", return_value=mock_result,
        ) as mock_run:
            FFmpegBackend().extract_clip(source, output, 1.0, 2.0)
        args = list(mock_run.call_args[0][0])
        assert "0:v:0?" not in args and "0:a:0?" in args


_PROBE_1280 = '{"streams": [{"width": 1280, "height": 720, "sample_aspect_ratio": "1:1"}]}'


class TestDisplaySize:
    """The size the burn draws for is the size the viewer sees."""

    def _size(self, **stream: object) -> tuple[int, int]:
        from bristlenose.server.clip_backend import display_size

        return display_size({"streams": [stream]})

    def test_plain_landscape(self) -> None:
        assert self._size(width=1280, height=720, sample_aspect_ratio="1:1") == (1280, 720)

    def test_portrait_phone_video_is_stored_rotated(self) -> None:
        side = [{"side_data_type": "Display Matrix", "rotation": -90}]
        assert self._size(width=1920, height=1080, side_data_list=side) == (1080, 1920)

    def test_older_files_carry_a_rotate_tag(self) -> None:
        assert self._size(width=1920, height=1080, tags={"rotate": "90"}) == (1080, 1920)

    def test_anamorphic_pixels_are_squared(self) -> None:
        assert self._size(width=1440, height=1080, sample_aspect_ratio="4:3") == (1920, 1080)

    def test_odd_sides_become_even(self) -> None:
        assert self._size(width=1277, height=719, sample_aspect_ratio="0:1") == (1276, 720)


class TestBurnSubtitles:
    def _cues(self):  # type: ignore[no-untyped-def]
        from bristlenose.server.clip_subtitles import Cue

        return [Cue(0.0, 2.0, "p1", "white", ("Hello.",))]

    def test_can_burn_needs_libass_and_x264(self) -> None:
        from bristlenose.server import clip_backend

        def fake(filters: str, encoders: str):  # type: ignore[no-untyped-def]
            outs = iter([MagicMock(stdout=filters, returncode=0),
                         MagicMock(stdout=encoders, returncode=0)])
            return lambda *a, **k: next(outs)

        yes = (" .. subtitles  V->V  Render text subtitles\n", " V....D libx264  H.264\n")
        no = (" .. scale  V->V  Scale\n", " V....D libx264  H.264\n")
        for (filters, encoders), expected in ((yes, True), (no, False)):
            clip_backend._can_burn.cache_clear()
            with patch("bristlenose.server.clip_backend.subprocess.run", fake(filters, encoders)):
                assert clip_backend._can_burn("/x/ffmpeg") is expected
        clip_backend._can_burn.cache_clear()

    def test_a_probe_that_did_not_run_is_not_remembered(self) -> None:
        """A timeout, or an ffmpeg that exits 133, is not the answer "no"."""
        from bristlenose.server import clip_backend

        clip_backend._can_burn.cache_clear()
        good = (" .. subtitles  V->V  Render text subtitles\n", " V....D libx264  H.264\n")
        calls = iter([
            subprocess.TimeoutExpired("ffmpeg", 30),
            MagicMock(stdout=good[0], returncode=0),
            MagicMock(stdout=good[1], returncode=0),
        ])

        def run(*a, **k):  # type: ignore[no-untyped-def]
            nxt = next(calls)
            if isinstance(nxt, Exception):
                raise nxt
            return nxt

        with patch("bristlenose.server.clip_backend.bundled_binary_path", return_value="/x/ffmpeg"), \
                patch("bristlenose.server.clip_backend.subprocess.run", side_effect=run):
            assert FFmpegBackend().can_burn_subtitles() is False
            assert FFmpegBackend().can_burn_subtitles() is True
        clip_backend._can_burn.cache_clear()

    def test_burn_command_and_cleanup(self, tmp_path: Path) -> None:
        clip = tmp_path / "clip.mp4"
        clip.write_bytes(b"clip")
        out = tmp_path / "clip (subtitled).mp4"
        seen: dict[str, object] = {}

        def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
            if "ffprobe" in cmd[0] or "-show_entries" in cmd:
                return MagicMock(returncode=0, stdout=_PROBE_1280, stderr="")
            vf = cmd[cmd.index("-vf") + 1]
            cwd = Path(kwargs["cwd"])
            ass_path = cwd / vf.split("subtitles=")[1].split(":fontsdir=")[0]
            fonts = cwd / vf.split(":fontsdir=")[1]
            seen.update(vf=vf, ass=ass_path.read_text(), font=(fonts / "Inter-Medium.otf").exists(),
                        tmp=fonts, cmd=cmd)
            Path(cmd[-1]).write_bytes(b"burned")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("bristlenose.server.clip_backend.subprocess.run", side_effect=fake_run):
            result = FFmpegBackend().burn_subtitles(clip, self._cues(), out)
        assert result == out
        assert "Style: Default,Inter Medium,48," in str(seen["ass"])
        assert "scale=1280:720,setsar=1,subtitles=" in str(seen["vf"])
        assert seen["font"] is True  # the bundled face is what libass reads
        joined = " ".join(seen["cmd"])  # type: ignore[arg-type]
        assert "-c:v libx264" in joined and "-c:a copy" in joined
        assert not Path(str(seen["tmp"])).exists()  # temp folder removed

    def test_burns_from_a_temp_folder_whose_path_needs_escaping(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Windows temp is ``C:\\Users\\…``: a colon and backslashes, which an
        ffmpeg filter graph would read as syntax. The burn refused any such
        path, so on Windows it never ran. ffmpeg now runs inside the temp
        folder and the graph names its files relatively, so the folder's
        path never reaches it. A space stands in for the drive colon here."""
        clip = tmp_path / "clip.mp4"
        clip.write_bytes(b"clip")
        out = tmp_path / "clip (subtitled).mp4"
        awkward = tmp_path / "Temp dir"
        awkward.mkdir()
        monkeypatch.setattr(
            "bristlenose.server.clip_backend.tempfile.mkdtemp",
            lambda prefix="": str(awkward / f"{prefix}x"),
        )
        (awkward / "bn-burn-x").mkdir()
        seen: dict[str, object] = {}

        def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
            if "-show_entries" in cmd:
                return MagicMock(returncode=0, stdout=_PROBE_1280, stderr="")
            seen.update(vf=cmd[cmd.index("-vf") + 1], cwd=kwargs.get("cwd"))
            Path(cmd[-1]).write_bytes(b"burned")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("bristlenose.server.clip_backend.subprocess.run", side_effect=fake_run):
            assert FFmpegBackend().burn_subtitles(clip, self._cues(), out) == out
        assert seen["vf"].endswith("subtitles=subtitles.ass:fontsdir=.")  # type: ignore[union-attr]
        assert Path(str(seen["cwd"])) == awkward / "bn-burn-x"

    def test_failed_burn_returns_none(self, tmp_path: Path) -> None:
        clip = tmp_path / "clip.mp4"
        clip.write_bytes(b"clip")

        def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
            if "-show_entries" in cmd:
                return MagicMock(returncode=0, stdout=_PROBE_1280, stderr="")
            return MagicMock(returncode=1, stdout="", stderr="No such filter: 'subtitles'")

        with patch("bristlenose.server.clip_backend.subprocess.run", side_effect=fake_run):
            assert FFmpegBackend().burn_subtitles(clip, self._cues(), tmp_path / "o.mp4") is None

    def test_bundled_font_ships_with_its_licence(self) -> None:
        from bristlenose.server.clip_backend import BURN_FONT

        assert BURN_FONT.is_file() and BURN_FONT.stat().st_size > 100_000
        assert "SIL Open Font License" in (BURN_FONT.parent / "Inter-OFL.txt").read_text()
