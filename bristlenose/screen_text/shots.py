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
_UNSAFE = re.compile(r"[^A-Za-z0-9_-]")


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
        # Codes and session ids come from a project folder, which may have come from anyone:
        # a file name is built only from characters that cannot leave the folder.
        stem = _UNSAFE.sub("_", stem)
        s["filename"] = f"{stem}-{s['seq']:0{width[s['session_id']]}d}.jpg"
    # Cleaning can make two names one (`s 1` and `s/1`): number the later ones apart.
    seen: set[str] = set()
    for s in shots:
        name, n = s["filename"], 2
        while name in seen:
            name = s["filename"].replace(".jpg", f"-{n}.jpg")
            n += 1
        seen.add(name)
        s["filename"] = name
    return shots


def _start(dom: str) -> int:
    """A quote's start second, from its DOM id (`q-{participant}-{int(start)}`)."""
    try:
        return int(dom.rsplit("-", 1)[1])
    except (IndexError, ValueError):
        return 0


def journey(
    screens: Iterable[Mapping[str, Any]],
    owner: Mapping[str, str],
    hidden: set[str] | frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    """One entry per screen, everyone's quotes on it, in the order screens usually came.

    The Miro board pools all the feedback on a screen, as the lens does: a screen is one place
    for everything said about it (owner, 17 Oct 2026; `docs/design-screens-export.md` §6). Its
    still is the version the lens shows first (`default_tab`). There is no shared clock across
    recordings, so screens go in journey order: by where each fell, on average, in its
    participants' own visit order, ties to the screen with more said about it. Each quote is
    grouped under the participant who said it, in time order, and appears once."""
    screens = list(screens)
    rank: dict[str, list[float]] = {}
    by_session: dict[str, list[tuple[float, str]]] = {}
    for sc in screens:
        for tab in sc["tabs"]:
            first = min((v[0] for v in tab["visits"]), default=tab["t"])
            by_session.setdefault(tab["session_id"], []).append((first, sc["key"]))
    for visits in by_session.values():
        # A place in that participant's own journey, 0 (first) to 1 (last), so a participant who
        # browsed widely does not outweigh three who went straight there.
        last = max(len(visits) - 1, 1)
        for i, (_, key) in enumerate(sorted(visits)):
            rank.setdefault(key, []).append(i / last)
    out: list[dict[str, Any]] = []
    for sc in screens:
        if not sc["tabs"]:
            continue
        shown = sc["tabs"][sc.get("default_tab", 0)]
        said: dict[str, set[str]] = {}
        for tab in sc["tabs"]:
            for dom in [p["dom_id"] for p in tab["pins"]] + list(tab["loose"]):
                if dom in owner and dom not in hidden:
                    # The participant is in the id itself: q-{participant}-{start}.
                    said.setdefault(dom.split("-")[1], set()).add(dom)
        groups = sorted(((code, sorted(doms, key=_start)) for code, doms in said.items()),
                        key=lambda g: code_order(g[0]))
        ranks = rank.get(sc["key"], [0.0])
        out.append({
            "screen_key": sc["key"],
            "title": title_of(sc, shown),
            "session_id": shown["session_id"],
            "t": shown["t"],
            "crop": list(shown["crop"]),
            "groups": groups,
            "_order": (sum(ranks) / len(ranks), -sum(len(d) for _, d in groups)),
        })
    out.sort(key=lambda e: e["_order"])
    for i, e in enumerate(out, 1):
        del e["_order"]
        e["filename"] = f"screen-{i:02d}.jpg"
    return out
