"""How far a board being built on Miro has got, and how long the rest should take.

A board is a known number of Miro calls: the layout is finished before the first one is made, so
the total is counted, never guessed. What is not known is how long a call takes, so the estimate is
measured inside the job, the way the screen-text pass measures its own rate, and nothing is said
until there is enough of it. The thresholds are the pipeline's (`timing.py`): no estimate from fewer
than four measured calls, and none under ten seconds left.

Two kinds of time are kept apart. Miro refusing a new board's frames for its first half-minute, and
backing off on a rate limit, are waits: they are counted as waiting, said as waiting, and kept out
of the per-call rate, or one refusal would swing every estimate after it.

The phases are what a researcher is told:

- ``preparing``: local work before any call (the screens board's screengrabs), counted.
- ``opening``: the board and its first frames. Miro's start-up refusal lands here, so no bar
  fraction and no estimate are claimed.
- ``quotes``, ``groups``, ``screens``: the build, each with its own count; the bar is the share of
  all the board's calls made.

The tracker is written by the worker thread and read by the status route; every field is a plain
value, read whole, and the fraction is clamped, so a read between two writes is never wrong by more
than one call.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from bristlenose.timing import TimingEstimator, WelfordStat

logger = logging.getLogger(__name__)

#: The pipeline's thresholds, read from it rather than copied: no estimate from fewer measured
#: calls than its fewest runs, and none under its ten-second floor.
MIN_MEASURED_CALLS = TimingEstimator._MIN_N_ESTIMATE
ETA_FLOOR_SECONDS = 10.0

#: Phases in which no fraction and no estimate are claimed: there is no Miro call count to divide
#: (preparing), or the time is Miro's start-up, not ours (opening).
UNMEASURED_PHASES = frozenset({"preparing", "opening"})


class BoardCancelledError(Exception):
    """The researcher stopped the build; the board keeps what it has."""


class BoardProgress:
    """Counts and timings for one board build. Never holds a quote, a name or a title."""

    def __init__(self, kind: str, *, clock: Callable[[], float] = time.monotonic) -> None:
        self.kind = kind  # "quotes" | "screens" — for the log line
        self._clock = clock
        self.started = clock()
        self.phase = "preparing"
        self.done = 0  # Miro calls made
        self.total = 0  # Miro calls planned; 0 until the layout is known
        self.count_done = 0  # what the current phase's line counts
        self.count_total = 0
        self.waiting = False
        self.waited = 0.0  # seconds spent waiting for Miro
        self.opening_seconds: float | None = None  # board created to first build call
        self._opening_started: float | None = None
        self._rate = WelfordStat()  # seconds of work per call, build phases only
        self._slowest = 0.0
        self._mark = self.started  # end of the last call or wait

    # -- writes (the worker thread) -------------------------------------------------------------

    def plan(self, total_calls: int) -> None:
        self.total = max(0, total_calls)

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
        """Local work done (no Miro call): a screengrab prepared."""
        self.count_done = min(self.count_total, self.count_done + n) if self.count_total else (
            self.count_done + n)

    def call_done(self, counted: int = 0) -> None:
        """One Miro call answered. ``counted`` is how far it moved the phase's line."""
        now = self._clock()
        elapsed = now - self._mark
        self._mark = now
        self.done += 1
        if counted:
            self.counted(counted)
        if self.phase not in UNMEASURED_PHASES:
            self._rate.update(elapsed)
            self._slowest = max(self._slowest, elapsed)

    @contextmanager
    def waiting_for(self, _seconds: float, _reason: str) -> Iterator[None]:
        """Wrap a backoff sleep: said as waiting, and kept out of the per-call rate."""
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

    def eta_seconds(self) -> float | None:
        """Seconds left, from this build's own rate — or None until that rate is earned."""
        if self.phase in UNMEASURED_PHASES or self.total <= 0 or self._rate.n < MIN_MEASURED_CALLS:
            return None
        left = max(0, self.total - self.done) * self._rate.mean
        return left if left >= ETA_FLOOR_SECONDS else None

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

    def log_summary(self, outcome: str) -> None:
        """One line per build: counts and timings only, so later builds can be predicted."""
        logger.info(
            "miro_board_built kind=%s outcome=%s calls=%d/%d elapsed=%.1fs waited=%.1fs "
            "opening=%s per_call=%s slowest=%.2fs measured=%d",
            self.kind, outcome, self.done, self.total, self._clock() - self.started, self.waited,
            f"{self.opening_seconds:.1f}s" if self.opening_seconds is not None else "-",
            f"{self._rate.mean:.2f}s" if self._rate.n else "-", self._slowest, self._rate.n,
        )
