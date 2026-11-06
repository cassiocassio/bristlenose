"""Property-based tests for the session registry: which recording is which session (R49).

What a researcher would notice if it broke: the same interview under two names is analysed
twice and its quotes read as two participants agreeing; or a study re-read in a different
order (a cloud sync rewrites dates, a folder is re-sorted) renumbers its sessions, and every
star, tag and typed name hangs on the wrong interview. The defect-mining pass of 5 Nov 2026
found this the largest group of serious fixes (identity by a loose key at a persisted
boundary), so the invariants are stated once, for every study the generator can build, not for
the cases that happened to break. The registry is driven for real, over real files in a
temporary folder; only the bytes are small. Placement rule: docs/design-test-philosophy.md.

CI runs these derandomised (tests/conftest.py). A kill that matters is found by the generator's
steering (small alphabets, duplicate contents), not pinned: the mutation record is in the commits.
"""

from __future__ import annotations

import random
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from bristlenose.models import FileType, InputFile, InputSession
from bristlenose.session_registry import SessionRegistry

_T0 = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)

# Names are distinct stems (ingest keeps different stems apart); contents repeat on purpose:
# two names with one content is the same recording twice, the case that matters.
NAMES = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot"]
STUDIES = st.lists(
    st.tuples(st.sampled_from(NAMES), st.integers(min_value=0, max_value=2)),
    min_size=1, max_size=6, unique_by=lambda t: t[0],
)


def _write(folder: Path, study: list[tuple[str, int]]) -> dict[str, int]:
    contents = {}
    for name, content in study:
        (folder / f"{name}.wav").write_bytes(f"recording {content}".encode() * 20)
        contents[name] = content
    return contents


def _sessions(folder: Path, names: list[str]) -> list[InputSession]:
    out = []
    for n, name in enumerate(names, 1):
        path = folder / f"{name}.wav"
        media = InputFile(path=path, file_type=FileType.AUDIO, created_at=_T0,
                          size_bytes=path.stat().st_size)
        out.append(InputSession(
            session_id=f"s{n}", session_number=n, participant_id=f"p{n}", participant_number=n,
            files=[media], audio_path=path, has_existing_transcript=False, session_date=_T0))
    return out


def _by_name(kept: list[InputSession]) -> dict[str, str]:
    return {s.files[0].path.stem: s.session_id for s in kept}


def _run(folder: Path, registry_dir: Path, names: list[str]) -> dict[str, str]:
    registry = SessionRegistry.load(registry_dir)
    kept = registry.apply(_sessions(folder, names), folder)
    registry.save()
    return _by_name(kept)


@settings(max_examples=60)
@given(STUDIES)
def test_one_recording_under_two_names_is_one_session(study: list) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        folder, reg = Path(tmp) / "in", Path(tmp) / "out"
        folder.mkdir()
        contents = _write(folder, study)
        kept = _run(folder, reg, [n for n, _ in study])
        assert len({contents[name] for name in kept}) == len(kept), "a content kept twice"
        assert {contents[name] for name in kept} == set(contents.values()), "a content lost"


@settings(max_examples=60)
@given(STUDIES)
def test_every_kept_session_has_its_own_number(study: list) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        folder, reg = Path(tmp) / "in", Path(tmp) / "out"
        folder.mkdir()
        _write(folder, study)
        sids = list(_run(folder, reg, [n for n, _ in study]).values())
        assert len(set(sids)) == len(sids)


@settings(max_examples=60)
@given(STUDIES, st.randoms(use_true_random=False))
def test_re_reading_a_numbered_study_in_any_order_keeps_every_number(
    study: list, rnd: random.Random,
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        folder, reg = Path(tmp) / "in", Path(tmp) / "out"
        folder.mkdir()
        _write(folder, study)
        names = [n for n, _ in study]
        first = _run(folder, reg, names)
        shuffled = list(names)
        rnd.shuffle(shuffled)
        assert _run(folder, reg, shuffled) == first


@settings(max_examples=60)
@given(STUDIES, st.randoms(use_true_random=False))
def test_which_copy_is_kept_does_not_depend_on_the_order_read(
    study: list, rnd: random.Random,
) -> None:
    # A fresh registry numbers new sessions in ingest order, by design; but which of two
    # identical copies is the session and which is set aside must not be that order's gift.
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / "in"
        folder.mkdir()
        _write(folder, study)
        names = [n for n, _ in study]
        shuffled = list(names)
        rnd.shuffle(shuffled)
        a = set(_run(folder, Path(tmp) / "out-a", names))
        b = set(_run(folder, Path(tmp) / "out-b", shuffled))
        assert a == b


@settings(max_examples=60)
@given(st.lists(st.sampled_from(NAMES), min_size=2, max_size=5, unique=True),
       st.integers(min_value=1, max_value=4))
def test_a_recording_keeps_its_number_when_the_names_swap_under_it(
    names: list, shift: int,
) -> None:
    # Two interviews renamed over each other, a re-sorted export: the bytes are the
    # interview, so the number follows the bytes, and no number is handed out twice.
    with tempfile.TemporaryDirectory() as tmp:
        folder, reg = Path(tmp) / "in", Path(tmp) / "out"
        folder.mkdir()
        content_of = {name: i for i, name in enumerate(names)}
        _write(folder, [(name, content_of[name]) for name in names])
        before = _run(folder, reg, names)
        sid_of_content = {content_of[name]: sid for name, sid in before.items()}
        k = shift % len(names) or 1
        rotated = {name: content_of[names[(i + k) % len(names)]] for i, name in enumerate(names)}
        _write(folder, list(rotated.items()))
        after = _run(folder, reg, names)
        assert {rotated[name]: sid for name, sid in after.items()} == sid_of_content
        assert len(set(after.values())) == len(after)


@settings(max_examples=60)
@given(st.lists(st.sampled_from(NAMES), min_size=2, max_size=6, unique=True),
       st.integers(min_value=1, max_value=5), st.randoms(use_true_random=False))
def test_a_recording_added_later_never_renumbers_the_ones_already_numbered(
    names: list, cut: int, rnd: random.Random,
) -> None:
    # Analyse a study, then drop more recordings into the folder (some of them older, some
    # copies of ones already there): the numbers the researcher has already seen must not move,
    # and what arrives takes numbers nobody holds.
    with tempfile.TemporaryDirectory() as tmp:
        folder, reg = Path(tmp) / "in", Path(tmp) / "out"
        folder.mkdir()
        _write(folder, [(name, i % 3) for i, name in enumerate(names)])
        first_names = names[: max(1, min(cut, len(names) - 1))]
        before = _run(folder, reg, first_names)
        everything = list(names)
        rnd.shuffle(everything)
        after = _run(folder, reg, everything)
        content = {name: i % 3 for i, name in enumerate(names)}  # as written above
        sid_of_content_before = {content[n]: sid for n, sid in before.items()}
        sid_of_content_after = {content[n]: sid for n, sid in after.items()}
        # By content, so a recording that went missing, or took a new number, is seen: the
        # kept name may legitimately change among identical copies, the number may not.
        for c, sid in sid_of_content_before.items():
            assert sid_of_content_after.get(c) == sid, f"content {c} was {sid}"
        assert len(set(after.values())) == len(after)
