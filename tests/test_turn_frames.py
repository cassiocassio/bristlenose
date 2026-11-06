"""utils/turn_frames.py — which frames the hover thumbnail takes, and how they are cached."""

from __future__ import annotations

import json
from pathlib import Path

from bristlenose.utils import turn_frames as tf


def test_a_turn_with_no_change_is_one_frame_a_quarter_in() -> None:
    assert tf.select_frames([(10.0, 50.0)], []) == [{"t": 20.0, "a": 10.0, "b": 50.0, "change": False}]


def test_a_change_splits_the_turn_and_is_framed_two_seconds_after() -> None:
    frames = tf.select_frames([(10.0, 50.0)], [30.0])
    assert frames == [
        {"t": 15.0, "a": 10.0, "b": 30.0, "change": False},  # 25% into the first stretch
        {"t": 32.0, "a": 30.0, "b": 50.0, "change": True},
    ]


def test_a_short_stretch_is_framed_halfway() -> None:
    frames = tf.select_frames([(10.0, 50.0)], [30.0, 33.0])
    assert frames[1] == {"t": 31.5, "a": 30.0, "b": 33.0, "change": True}
    assert frames[2] == {"t": 35.0, "a": 33.0, "b": 50.0, "change": True}


def test_a_change_at_the_handover_or_outside_the_turn_is_ignored() -> None:
    # Within 2 s of the turn's start, at its very end, and in another turn.
    assert len(tf.select_frames([(10.0, 50.0)], [5.0, 11.5, 12.0, 50.0, 70.0])) == 1


def test_frames_follow_each_turn_in_order() -> None:
    frames = tf.select_frames([(0.0, 8.0), (20.0, 40.0)], [30.0])
    assert [f["t"] for f in frames] == [2.0, 22.5, 32.0]


def test_the_selection_key_moves_with_the_turns() -> None:
    a = tf.select_frames([(10.0, 50.0)], [])
    assert tf.selection_key(a) == tf.selection_key(tf.select_frames([(10.0, 50.0)], []))
    assert tf.selection_key(a) != tf.selection_key(tf.select_frames([(10.0, 52.0)], []))


class _Grab:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[float] = []
        self.fail = fail

    def __call__(self, video: Path, t: float) -> bytes | None:
        self.calls.append(t)
        return None if self.fail else b"\xff\xd8jpeg" + str(t).encode()


def test_extract_writes_one_jpeg_per_frame_and_caches(tmp_path: Path) -> None:
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    frames = tf.select_frames([(10.0, 50.0)], [30.0])
    grab = _Grab()
    path = tf.extract_turn_frames("s1", video, frames, tmp_path / "out", grabber=grab)
    assert path == tmp_path / "out" / "s1.json"
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert [f["t"] for f in rec["frames"]] == [15.0, 32.0]
    assert all(f["jpg"] for f in rec["frames"])
    assert rec["selection"] == tf.selection_key(frames)
    assert grab.calls == [15.0, 32.0]
    tf.extract_turn_frames("s1", video, frames, tmp_path / "out", grabber=grab)
    assert grab.calls == [15.0, 32.0]  # cached: nothing taken again


def test_new_turns_take_new_frames(tmp_path: Path) -> None:
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    grab = _Grab()
    tf.extract_turn_frames("s1", video, tf.select_frames([(10.0, 50.0)], []), tmp_path, grabber=grab)
    tf.extract_turn_frames("s1", video, tf.select_frames([(10.0, 90.0)], []), tmp_path, grabber=grab)
    assert grab.calls == [20.0, 30.0]


def test_no_ffmpeg_is_written_down_as_incomplete_and_tried_again(tmp_path: Path) -> None:
    # Not "no frames": the record says incomplete, so the next pass takes them once ffmpeg is there.
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    frames = tf.select_frames([(10.0, 50.0)], [30.0])

    def no_ffmpeg(v: Path, t: float) -> bytes | None:
        raise FileNotFoundError("ffmpeg")

    path = tf.extract_turn_frames("s1", video, frames, tmp_path, grabber=no_ffmpeg)
    assert path is not None
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert rec["complete"] is False and rec["frames"] == [] and rec["selection"] == tf.selection_key(frames)
    grab = _Grab()
    tf.extract_turn_frames("s1", video, frames, tmp_path, grabber=grab)
    assert grab.calls == [15.0, 32.0]
    assert json.loads(path.read_text(encoding="utf-8"))["complete"] is True


def test_a_missing_recording_is_written_down_too(tmp_path: Path) -> None:
    frames = tf.select_frames([(10.0, 50.0)], [])
    path = tf.extract_turn_frames("s1", tmp_path / "gone.mp4", frames, tmp_path, grabber=_Grab())
    assert path is not None
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert rec["complete"] is False and rec["key"] is None and rec["selection"] == tf.selection_key(frames)


def test_a_record_is_written_even_when_every_grab_fails(tmp_path: Path) -> None:
    # Otherwise the route, seeing no record for the current turns, would ask for a pass for ever.
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    frames = tf.select_frames([(10.0, 50.0)], [])
    path = tf.extract_turn_frames("s1", video, frames, tmp_path, grabber=_Grab(fail=True))
    assert path is not None
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert rec["frames"] == [] and rec["selection"] == tf.selection_key(frames)
    assert rec["complete"] is False

