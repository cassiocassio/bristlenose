"""Every welcome illustration must enrol with the curtain, and none may loop.

The welcome baton used to declare how long a turn lasts and sleep for it, which
meant two clocks — the declared turn and the illustration's own beat list — that
had to agree with nothing making them agree. They never did: measured across the
six looping illustrations on 22 Sep 2026, every turn ran between 1.26 and 1.83
passes, so every turn ended mid-play and a truncated pass was the last thing on
screen before the cell went still.

The fix moves the clock into the illustration: it plays once, holds its finished
frame, drops its curtain and posts `done`, and the baton passes then. That only
works if the illustration actually *enrols* — an illustration that never calls
`BN.register` paints nothing at rest, never plays, and never hands the baton
back, so its cell sits out the whole watchdog ceiling in silence. Nothing else in
the tree can see that: Swift cannot type a string of JavaScript, and the Swift
suite never parses these templates.

So this gate reads the templates themselves, enrolling a new illustration by its
existence rather than by a list somebody has to remember to extend.

**Why the loop check is `setInterval` and not `setTimeout`.** Several
illustrations legitimately build a `sleep()` out of `setTimeout` to pace their
own beats — that is one beat, awaited, not a loop. `setInterval` is unbounded by
construction and was how `signal` ran forever. The recursive-`setTimeout` form
(`(function loop(){ setTimeout(…loop()…) })()`) that `quote` used is caught by
the registration check instead: a looping illustration has nowhere to put a
`play` that returns.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SWIFT = REPO / "desktop/Bristlenose/Bristlenose/WelcomeIllustrations.swift"

# The curtain's own script is exempt from the beat rules below — it is the thing
# that owns timing, so of course it holds timers.
CURTAIN_RE = re.compile(
    r"static func curtain\(_ kind: WelcomeIllustration\) -> String \{\n        \"\"\"\n"
    r"(?P<body>.*?)\n        \"\"\"\n    \}",
    re.S,
)
# Every illustration template. `dark:` is the shared first parameter and is what
# separates them from `stringsBlock` / `curtain`, which take neither.
TEMPLATE_RE = re.compile(
    r"static func (?P<name>\w+)\(dark: Bool.*?\n        return \"\"\"\n"
    r"(?P<body>.*?)\n        \"\"\"",
    re.S,
)


def templates() -> dict[str, str]:
    src = SWIFT.read_text()
    assert CURTAIN_RE.search(src), "the curtain helper is gone — the contract has no owner"
    found = {m.group("name"): m.group("body") for m in TEMPLATE_RE.finditer(src)}
    assert found, "no illustration templates matched — the extraction regex has drifted"
    return found


NAMES = sorted(templates())


def test_the_set_of_templates_is_what_we_think_it_is() -> None:
    """A new illustration lands here first, which is the point.

    The assertion is not the list — it is that the list is *found*, and that the
    count moves when the set does. A template that stops matching the regex would
    otherwise drop out of every check below in silence.
    """
    assert len(NAMES) == 9, f"expected 9 illustration templates, found {len(NAMES)}: {NAMES}"


@pytest.mark.parametrize("name", NAMES)
def test_illustration_embeds_the_curtain(name: str) -> None:
    assert r"\(curtain(kind))" in templates()[name], (
        f"{name} does not embed the curtain, so `BN` is undefined in its document "
        "and its own `BN.register` call throws at load"
    )


@pytest.mark.parametrize("name", NAMES)
def test_illustration_registers_a_still_and_a_pass(name: str) -> None:
    """`still` is what a resting cell shows; `play` is the one pass the baton awaits.

    Asserted as the call expression rather than by searching for the words, so a
    comment mentioning either cannot satisfy the test.
    """
    body = templates()[name]
    assert "BN.register({" in body, f"{name} never enrols with the curtain"
    call = body[body.index("BN.register({"):]
    assert re.search(r"\bstill\s*:", call), f"{name} registers no still frame"
    assert re.search(r"\bplay\s*:", call), f"{name} registers no pass"


@pytest.mark.parametrize("name", NAMES)
def test_illustration_does_not_run_its_own_perpetual_loop(name: str) -> None:
    body = templates()[name]
    assert "setInterval(" not in body, (
        f"{name} starts an interval — it will still be running when the baton "
        "moves on, which is the class of bug the curtain replaced"
    )


def test_the_retired_lead_in_is_gone_from_every_template() -> None:
    """The flat three-second lead-in is now `fade + establish`, in the curtain.

    Left in one template it would stack on top of the curtain's own beat, and the
    cell would sit inert for four and a half seconds after taking the baton.
    """
    src = SWIFT.read_text()
    assert "jsLeadMs" not in src, "a template still interpolates the retired lead-in"
    assert "leadInSeconds" not in src, "a native illustration still sleeps the retired lead-in"
