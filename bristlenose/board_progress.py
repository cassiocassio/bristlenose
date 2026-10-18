"""How far a board being built on Miro has got, and how long the rest should take.

A board is a known number of Miro calls: the layout is finished before the first one is made, so
the total is counted, never guessed, and counted by kind (the board, frames, sticky batches, groups,
screengrabs, the title). What is not known is how long a call takes, and the kinds differ: measured
18 Oct 2026 on a 242-quote board, a batch of twenty stickies and a group of two took about the same
round trip each, but there were 13 batches and 212 groups, so grouping was 83 of the 94 seconds.
An estimate from one rate for all calls said "<1 min left" from the fifth second.

So each kind keeps its own rate. A rate is earned by this build measuring four calls of that kind
(the pipeline's threshold, `timing.py`), or by earlier builds having measured them: the rates are
kept per machine in ``board-timing.json``, beside the pipeline's ``timing.json`` but apart from it,
so the Run Inspector, which reads the profile with the most observations from ``timing.json``, never
mistakes a board for a run. Nothing is said until every kind still to come has a rate, and nothing
under ten seconds left (the pipeline's floor). A kind with only a few calls left (the title, the
quotes board's two frames) borrows the build's average rather than holding the estimate back.

Two kinds of time are kept apart. Miro refusing a new board's frames for its first half-minute, and
backing off on a rate limit, are waits: they are counted as waiting, said as waiting, and kept out
of every rate, or one refusal would swing every estimate after it.

The phases are what a researcher is told:

- ``starting``: before the layout (the quotes board reading its quotes).
- ``preparing``: local work before any call (the screens board's screengrabs), counted.
- ``opening``: the board and its first frame. Miro's start-up refusal lands here, so no bar
  fraction and no estimate are claimed, and these calls are not timed.
- ``quotes``, ``groups``, ``screens``: the build, each with its own count; the bar is the share of
  all the board's calls made.

The tracker is written by the worker thread and read by the status route; every field is a plain
value, read whole, and the fraction is clamped, so a read between two writes is never wrong by more
than one call.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from bristlenose.timing import TimingEstimator, WelfordStat, load_timing_data, save_timing_data

logger = logging.getLogger(__name__)

#: The pipeline's thresholds, read from it rather than copied: no rate from fewer measured calls
#: than its fewest runs, and no estimate under its ten-second floor.
MIN_MEASURED_CALLS = TimingEstimator._MIN_N_ESTIMATE
ETA_FLOOR_SECONDS = 10.0

#: Phases in which no fraction and no estimate are claimed, and no call is timed: nothing to divide
#: yet (starting, preparing), or the time is Miro's start-up, not ours (opening).
UNMEASURED_PHASES = frozenset({"starting", "preparing", "opening"})

#: The kinds of Miro call a board makes.
CALL_KINDS = ("board", "frame", "bulk", "group", "image", "text")

#: Where the rates live, and the profile they live under (one service today).
HISTORY_FILENAME = "board-timing.json"
HISTORY_PROFILE = "miro"
#: A kept rate follows Miro as it changes: past this many calls, older ones weigh less.
HISTORY_WEIGHT_CAP = 200


def default_history_dir() -> Path:
    """The per-machine config folder the pipeline's timings use (`$SNAP_USER_COMMON` on Snap)."""
    snap = os.environ.get("SNAP_USER_COMMON")
    return Path(snap) if snap else Path("~/.config/bristlenose").expanduser()


def load_history(config_dir: Path) -> dict[str, WelfordStat]:
    """The per-kind rates earlier builds measured. Empty, never an error, when there are none."""
    data = load_timing_data(config_dir, HISTORY_FILENAME)
    profile = data.get("profiles", {}).get(HISTORY_PROFILE, {})
    out: dict[str, WelfordStat] = {}
    for kind, stat in profile.items():
        try:
            out[kind] = WelfordStat.from_dict(stat)
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _merge(a: WelfordStat, b: WelfordStat) -> WelfordStat:
    """Two running means as one (Chan et al.'s parallel form of Welford)."""
    n = a.n + b.n
    if n == 0:
        return WelfordStat()
    delta = b.mean - a.mean
    merged = WelfordStat(mean=a.mean + delta * b.n / n,
                         m2=a.m2 + b.m2 + delta * delta * a.n * b.n / n, n=n)
    if merged.n > HISTORY_WEIGHT_CAP:  # keep the mean, let the next builds count for more
        merged.m2 *= HISTORY_WEIGHT_CAP / merged.n
        merged.n = HISTORY_WEIGHT_CAP
    return merged


class BoardCancelledError(Exception):
    """The researcher stopped the build; the board keeps what it has."""


class BoardProgress:
    """Counts and timings for one board build. Never holds a quote, a name or a title."""

    def __init__(self, kind: str, *, clock: Callable[[], float] = time.monotonic,
                 history_dir: Path | None = None) -> None:
        """``history_dir`` is where rates are kept between builds (`default_history_dir()` for a
        real build); without one the build starts from nothing and remembers nothing."""
        self.kind = kind  # "quotes" | "screens" — for the log line
        self._clock = clock
        self.started = clock()
        self.phase = "starting"
        self.done = 0  # Miro calls made
        self.total = 0  # Miro calls planned; 0 until the layout is known
        self.count_done = 0  # what the current phase's line counts
        self.count_total = 0
        self.waiting = False
        self.waited = 0.0  # seconds spent waiting for Miro
        self.opening_seconds: float | None = None  # board created to first build call
        self._opening_started: float | None = None
        self._planned: dict[str, int] = {}
        self._made: dict[str, int] = {}
        self._rates: dict[str, WelfordStat] = {}  # this build's, timed calls only
        self._history_dir = history_dir
        self._history = load_history(history_dir) if history_dir is not None else {}
        self._all = WelfordStat()  # every timed call, whatever its kind
        self._slowest = 0.0
        self._mark = self.started  # end of the last call or wait

    # -- writes (the worker thread) -------------------------------------------------------------

    def plan(self, calls: Mapping[str, int]) -> None:
        """Every call the board will make, by kind, counted from the layout before the first."""
        self._planned = {k: max(0, n) for k, n in calls.items() if n}
        self.total = sum(self._planned.values())

    def enter(self, phase: str, count_total: int = 0) -> None:
        now = self._clock()
        if phase == "opening" and self._opening_started is None:
            self._opening_started = now
        if self.phase == "opening" and phase != "opening" and self._opening_started is not None:
            self.opening_seconds = now - self._opening_started
        self.phase = phase
        self.count_done = 0
        self.count_total = max(0, count_total)
        self._mark = now

    def counted(self, n: int = 1) -> None:
        """The phase's line moved on: a screengrab prepared, quotes placed, a screen finished."""
        self.count_done = min(self.count_total, self.count_done + n) if self.count_total else (
            self.count_done + n)

    def call_done(self, kind: str, counted: int = 0) -> None:
        """One Miro call of ``kind`` answered. ``counted`` is how far it moved the phase's line."""
        now = self._clock()
        elapsed = now - self._mark
        self._mark = now
        self.done += 1
        self._made[kind] = self._made.get(kind, 0) + 1
        if counted:
            self.counted(counted)
        if self.phase not in UNMEASURED_PHASES:
            self._rates.setdefault(kind, WelfordStat()).update(elapsed)
            self._all.update(elapsed)
            self._slowest = max(self._slowest, elapsed)

    @contextmanager
    def waiting_for(self, _seconds: float, _reason: str) -> Iterator[None]:
        """Wrap a backoff sleep: said as waiting, and kept out of every rate."""
        began = self._clock()
        self.waiting = True
        try:
            yield
        finally:
            spent = self._clock() - began
            self.waited += spent
            self._mark += spent
            self.waiting = False

    # -- reads (the status route) ---------------------------------------------------------------

    def fraction(self) -> float | None:
        if self.phase in UNMEASURED_PHASES or self.total <= 0:
            return None
        return min(1.0, max(0.0, self.done / self.total))

    def _rate(self, kind: str, left: int) -> float | None:
        own = self._rates.get(kind)
        if own is not None and own.n >= MIN_MEASURED_CALLS:
            return own.mean
        kept = self._history.get(kind)
        if kept is not None and kept.n >= MIN_MEASURED_CALLS:
            return kept.mean
        if left <= MIN_MEASURED_CALLS and self._all.n >= MIN_MEASURED_CALLS:
            return self._all.mean  # a handful of calls: the build's average is close enough
        return None

    def eta_seconds(self) -> float | None:
        """Seconds left — or None until every kind of call still to come has an earned rate."""
        if self.phase in UNMEASURED_PHASES or self.total <= 0:
            return None
        seconds = 0.0
        for kind, planned in self._planned.items():
            left = planned - self._made.get(kind, 0)
            if left <= 0:
                continue
            rate = self._rate(kind, left)
            if rate is None:
                return None
            seconds += left * rate
        return seconds if seconds >= ETA_FLOOR_SECONDS else None

    def snapshot(self) -> dict[str, Any]:
        eta = self.eta_seconds()
        return {
            "phase": self.phase,
            "done": self.done,
            "total": self.total,
            "count_done": self.count_done,
            "count_total": self.count_total,
            "waiting": self.waiting,
            "fraction": self.fraction(),
            "eta_seconds": round(eta, 1) if eta is not None else None,
        }

    # -- after the build ------------------------------------------------------------------------

    def remember(self) -> None:
        """Fold this build's rates into the ones kept for the next build to start from."""
        folder = self._history_dir
        if folder is None or not any(s.n for s in self._rates.values()):
            return
        data = load_timing_data(folder, HISTORY_FILENAME)
        profile = data.setdefault("profiles", {}).setdefault(HISTORY_PROFILE, {})
        for kind, stat in self._rates.items():
            try:
                kept = WelfordStat.from_dict(profile[kind]) if kind in profile else WelfordStat()
            except (KeyError, TypeError, ValueError):
                kept = WelfordStat()
            profile[kind] = _merge(kept, stat).to_dict()
        save_timing_data(data, folder, HISTORY_FILENAME)

    def log_summary(self, outcome: str) -> None:
        """One line per build: counts and timings only, so later builds can be predicted."""
        rates = " ".join(f"{k}={s.mean:.2f}s/{s.n}" for k, s in sorted(self._rates.items()))
        logger.info(
            "miro_board_built kind=%s outcome=%s calls=%d/%d elapsed=%.1fs waited=%.1fs "
            "opening=%s slowest=%.2fs rates=[%s]",
            self.kind, outcome, self.done, self.total, self._clock() - self.started, self.waited,
            f"{self.opening_seconds:.1f}s" if self.opening_seconds is not None else "-",
            self._slowest, rates,
        )
