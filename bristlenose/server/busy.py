"""What this serve is doing that must not be cut off: paid calls, and passes that cannot start themselves again.

The Mac app reaps a study's server a little after its last window closes (``ServeReaping``, 90 s).
That is right for an idle one and wrong for one in the middle of a paid pass: the calls already made
are lost, and nothing here runs on a timer, so an interrupted AutoCode pass leaves its quotes owed
until something triggers it again. The host asks, on its 20-second poll, ``GET /api/background-work``
and holds the reap while the answer is busy (for at most a ceiling, so a wedged job cannot keep a
server alive for ever).

**Busy means paid or unrecoverable, on purpose.** AutoCode (an apply pass, and a catch-up that is
waiting or running) and Signals elaboration. Screens reading and the scene strips are not listed:
they spend nothing, they are cached by recording and pick up where they were at the next start, and
keeping a server alive for a study nobody is looking at would hold the Vision engine and the disk
for hours. Add a kind only if an interrupted pass costs money or loses work that nothing restarts.

Behind the bearer token, not on ``/api/health``: health is auth-exempt and refuses to publish when
the researcher is working (see ``routes/health.py``). The answer here is coarse kinds, no timestamps.
"""

from __future__ import annotations

import functools
import inspect
import threading
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, TypeVar

_lock = threading.Lock()
_active: Counter[str] = Counter()

F = TypeVar("F", bound=Callable[..., Any])


@contextmanager
def working(kind: str) -> Iterator[None]:
    """Mark ``kind`` busy for the length of the block, however it ends."""
    with _lock:
        _active[kind] += 1
    try:
        yield
    finally:
        with _lock:
            _active[kind] -= 1
            if _active[kind] <= 0:
                del _active[kind]


def tracked(kind: str) -> Callable[[F], F]:
    """Decorate a function (sync or async) so it counts as busy for as long as it runs."""

    def wrap(fn: F) -> F:
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_inner(*args: Any, **kwargs: Any) -> Any:
                with working(kind):
                    return await fn(*args, **kwargs)

            async_inner._busy_kind = kind  # type: ignore[attr-defined]
            return async_inner  # type: ignore[return-value]

        @functools.wraps(fn)
        def inner(*args: Any, **kwargs: Any) -> Any:
            with working(kind):
                return fn(*args, **kwargs)

        inner._busy_kind = kind  # type: ignore[attr-defined]
        return inner  # type: ignore[return-value]

    return wrap


def active_kinds() -> list[str]:
    """The kinds busy now, sorted, each once. Includes a catch-up that is waiting to fire."""
    with _lock:
        kinds = set(_active)
    from bristlenose.server import autocode_catch_up

    if autocode_catch_up.is_active():
        kinds.add("autocode")
    return sorted(kinds)
