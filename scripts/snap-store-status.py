#!/usr/bin/env python3
"""Is the Snap Store down? Read status.snapcraft.io's RSS feed and say why.

Why this exists (11 Nov 2026): the 0.46.0 Snap edge build failed twice with
"unable to contact snap store" and "cannot download snapd". A red run with a
network error looks like our bug, and the reflex is to retry. status.snapcraft.io
had an open incident from 11:55 GMT (api.snapcraft.io refresh/search, login.ubuntu.com,
Serial Vault, store downloads). The page itself is JavaScript, but StatusIQ
publishes an RSS feed of per-component status changes, and that one is plain XML.

Exit codes (for callers):
  0  every component's latest status is Operational: a failure is probably ours
  3  at least one component is not Operational: do NOT retry, wait for the store
  4  the feed could not be read or parsed: unknown, say so, do not guess

    scripts/snap-store-status.py            human summary
    scripts/snap-store-status.py --json     machine-readable
    scripts/snap-store-status.py --markdown GitHub step-summary text
"""
from __future__ import annotations

import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

FEED = "https://snapcraft.site24x7statusiq.com/rss"
PAGE = "https://status.snapcraft.io"
OK, INCIDENT, UNREADABLE = 0, 3, 4


def parse(xml_text: str) -> dict[str, dict[str, str]]:
    """Latest status per component: {name: {"status": ..., "since": ISO-8601}}."""
    latest: dict[str, tuple[object, str, str]] = {}
    for item in ET.fromstring(xml_text).iter("item"):
        title = (item.findtext("title") or "").strip()
        if " - " not in title:
            continue
        name, status = title.rsplit(" - ", 1)
        when = parsedate_to_datetime(item.findtext("pubDate") or "")
        if name not in latest or when > latest[name][0]:  # type: ignore[operator]
            latest[name] = (when, status.strip(), when.isoformat())
    return {n: {"status": s, "since": iso} for n, (_, s, iso) in latest.items()}


def verdict(components: dict[str, dict[str, str]]) -> dict[str, object]:
    down = {n: c for n, c in components.items() if c["status"].lower() != "operational"}
    return {"ok": not down, "page": PAGE, "down": down, "components": len(components)}


def fetch(timeout: int = 20) -> str:
    with urllib.request.urlopen(FEED, timeout=timeout) as r:  # noqa: S310 - fixed https URL
        return r.read().decode("utf-8")


def render(v: dict[str, object], markdown: bool) -> str:
    down: dict[str, dict[str, str]] = v["down"]  # type: ignore[assignment]
    if not down:
        return "Snap Store status: every listed component is Operational. A failure here is probably ours."
    bullet = "- " if markdown else "  "
    lines = ["Snap Store incident: do NOT retry blindly. Wait for the store, then re-run once."]
    lines += [f"{bullet}{n}: {c['status']} since {c['since']}" for n, c in sorted(down.items())]
    lines.append(f"Details: {PAGE}")
    return ("\n".join(lines)) if not markdown else "### " + lines[0] + "\n\n" + "\n".join(lines[1:])


def main(argv: list[str]) -> int:
    try:
        v = verdict(parse(fetch()))
    except Exception as exc:  # network, XML or date: unknown is its own answer
        msg = f"Snap Store status unreadable ({type(exc).__name__}): check {PAGE} by hand."
        print(json.dumps({"ok": None, "error": msg}) if "--json" in argv else msg)
        return UNREADABLE
    if "--json" in argv:
        print(json.dumps(v, indent=2))
    else:
        print(render(v, "--markdown" in argv))
    return OK if v["ok"] else INCIDENT


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
