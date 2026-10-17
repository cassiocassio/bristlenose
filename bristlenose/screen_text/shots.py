"""The shot list: every still the screens show, one per participant per screen, in time order.

The Screens lens groups by screen across participants (`screens.derive_screens`); an export
wants the other cut. Each (screen, session) version becomes one still, carrying only that
participant's quotes, ordered participant by participant and, within a participant, by their
first visit to the screen. The folder, clipboard and Miro exports all start here, so they
cannot disagree about which stills exist or what order they are in
(`docs/design-screens-export.md` §2–§3).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

_CODE = re.compile(r"^([^\d]*)(\d*)(.*)$")


def code_order(code: str) -> tuple[str, int, str]:
    """`p2` before `p10`, as the Sessions lens lists them."""
    m = _CODE.match(code)
    assert m is not None  # the pattern matches any string
    head, num, tail = m.groups()
    return (head, int(num) if num else -1, tail)


def title_of(screen: Mapping[str, Any], tab: Mapping[str, Any]) -> str:
    """What the lens calls this version of the screen (`ScreensLens.tsx` `screenTitle`): a
    title-keyed screen by its title, an address-keyed one by the page heading on this still."""
    name = str(screen["name"])
    if not name.startswith("/"):
        return name[:1].upper() + name[1:]
    return str(tab.get("heading") or "") or name


def shot_list(
    screens: Iterable[Mapping[str, Any]],
    owner: Mapping[str, str],
    hidden: set[str] | frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    """One entry per still, in export order.

    ``screens`` is `derive_screens`' output. ``owner`` maps a quote's DOM id to the session it
    was said in: a version's pins include other participants' quotes whose words its still shows,
    and those are left to their own participant's still, so each quote appears once. ``hidden``
    quotes are on no still.
    """
    shots: list[dict[str, Any]] = []
    for sc in screens:
        for tab in sc["tabs"]:
            sid = tab["session_id"]

            def own(dom: str, sid: str = sid) -> bool:
                return owner.get(dom) == sid and dom not in hidden

            shots.append({
                "session_id": sid,
                "code": tab["code"],
                "screen_key": sc["key"],
                "screen_name": sc["name"],
                "title": title_of(sc, tab),
                "t": tab["t"],
                "crop": list(tab["crop"]),
                "first_visit": min(v[0] for v in tab["visits"]) if tab["visits"] else tab["t"],
                "pins": [p for p in tab["pins"] if own(p["dom_id"])],
                "loose": [d for d in tab["loose"] if own(d)],
            })
    shots.sort(key=lambda s: (code_order(s["code"]), s["session_id"], s["first_visit"], s["t"]))
    seq: dict[str, int] = {}
    for s in shots:
        seq[s["session_id"]] = seq.get(s["session_id"], 0) + 1
        s["seq"] = seq[s["session_id"]]
    width = {sid: max(2, len(str(n))) for sid, n in seq.items()}
    # A code names one session; should two sessions share one, the session id keeps their
    # files apart.
    sessions_of: dict[str, set[str]] = {}
    for s in shots:
        sessions_of.setdefault(s["code"], set()).add(s["session_id"])
    for s in shots:
        stem = s["code"] if len(sessions_of[s["code"]]) == 1 else f"{s['code']}-{s['session_id']}"
        s["filename"] = f"{stem}-{s['seq']:0{width[s['session_id']]}d}.jpg"
    return shots
