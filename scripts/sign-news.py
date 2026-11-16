#!/usr/bin/env python3
"""Sign, verify and generate the Mac app's news file.

The app fetches one signed envelope from ``https://bristlenose.app/app/news``::

    {"kid": "k1", "payload": "<base64 of the exact bytes>",
     "sig": "<base64 Ed25519 over b'bristlenose-news-v1\\n' + payload bytes>"}

and checks it in ``desktop/Bristlenose/Bristlenose/NewsCheck.swift``. Spec:
``docs/private/design-news-and-counts.md`` (v2) §4 and §9.

Commands::

    keygen --out <dir> [--kid k1]     raw 32-byte private key, 0600, OUTSIDE the
                                      repo; prints the base64 public key
    sign --key <file> --kid k1 --in payload.json --out envelope.json
    verify (--pub <b64> | --kid k1) --in envelope.json
    office-hours --from 2026-12-15 --count N
                                      items for the 1st Tuesdays (08:00-09:00)
                                      and 3rd Tuesdays (17:30-18:30),
                                      Europe/London

The private key never belongs in the repo, a syncing password manager or the
cloud (spec §9). ``keygen`` refuses to write inside this repository.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Domain separation. Mirrors ``NewsCheck.signingContext`` in Swift.
CONTEXT = b"bristlenose-news-v1\n"

#: Mirrors ``NewsKeys.productionK1`` / ``productionK0`` in ``NewsKeys.swift``,
#: pinned by ``tests/test_sign_news.py``. EMPTY until the owner generates keys:
#: until then the app accepts no file.
PUBLIC_KEYS: dict[str, str] = {"k1": "", "k0": ""}

MAX_LIFETIME = dt.timedelta(days=45)
#: The signer is stricter than the app (which allows 2 days ahead), so a file
#: signed in a hurry still has a day of slack against a slow clock.
MAX_ISSUE_AHEAD = dt.timedelta(days=1)
APP_ISSUE_AHEAD = dt.timedelta(days=2)

LONDON = ZoneInfo("Europe/London")
# English names written out: strftime's %A/%B follow the process locale.
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")
UTC = dt.timezone.utc


class NewsError(Exception):
    """A refusal, printed as one line."""


# --- dates -----------------------------------------------------------------


def parse_time(raw: str) -> dt.datetime:
    """RFC 3339 with ``Z`` or an offset, as the app reads it."""
    try:
        value = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise NewsError(f"not an RFC 3339 time: {raw!r}") from exc
    if value.tzinfo is None:
        raise NewsError(f"time has no zone: {raw!r}")
    return value.astimezone(UTC)


def format_time(value: dt.datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_utc() -> dt.datetime:
    return dt.datetime.now(UTC).replace(microsecond=0)


# --- keys ------------------------------------------------------------------


def public_b64(private: Ed25519PrivateKey) -> str:
    raw = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return base64.b64encode(raw).decode("ascii")


def _inside_repo(path: Path) -> bool:
    resolved = path.resolve()
    return resolved == REPO_ROOT or REPO_ROOT in resolved.parents


def keygen(out_dir: Path, kid: str) -> tuple[Path, str]:
    if _inside_repo(out_dir):
        raise NewsError(f"refusing to write a private key inside the repo: {out_dir}")
    out_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = out_dir / f"bristlenose-news-{kid}.key"
    private = Ed25519PrivateKey.generate()
    raw = private.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise NewsError(f"refusing to overwrite {path}") from exc
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
    return path, public_b64(private)


def load_private(path: Path) -> Ed25519PrivateKey:
    raw = path.read_bytes()
    if len(raw) != 32:
        raise NewsError(f"{path} is not a raw 32-byte Ed25519 private key")
    if os.name == "posix" and path.stat().st_mode & 0o077:
        raise NewsError(f"{path} is readable by others; chmod 600 it first")
    return Ed25519PrivateKey.from_private_bytes(raw)


def load_public(b64: str) -> Ed25519PublicKey:
    try:
        raw = base64.b64decode(b64, validate=True)
    except ValueError as exc:
        raise NewsError("public key is not base64") from exc
    if len(raw) != 32:
        raise NewsError("public key is not 32 bytes (is it set?)")
    return Ed25519PublicKey.from_public_bytes(raw)


# --- sign and verify -------------------------------------------------------


def check_payload_dates(payload: dict, *, now: dt.datetime, ahead: dt.timedelta) -> None:
    issued = parse_time(payload.get("issued", ""))
    expires = parse_time(payload.get("expires", ""))
    if issued > now + ahead:
        raise NewsError(f"issued {format_time(issued)} is too far ahead of now")
    if expires <= issued:
        raise NewsError("expires must be after issued")
    if expires > issued + MAX_LIFETIME:
        raise NewsError("expires is more than 45 days after issued")


def sign_bytes(private: Ed25519PrivateKey, kid: str, payload: bytes,
               *, now: dt.datetime | None = None) -> dict:
    try:
        decoded = json.loads(payload)
    except ValueError as exc:
        raise NewsError("payload is not JSON") from exc
    if not isinstance(decoded, dict) or decoded.get("schema") != 1:
        raise NewsError("payload must be an object with schema 1")
    if decoded.get("env") not in ("prod", "staging"):
        raise NewsError("payload env must be prod or staging")
    check_payload_dates(decoded, now=now or now_utc(), ahead=MAX_ISSUE_AHEAD)
    signature = private.sign(CONTEXT + payload)
    return {
        "kid": kid,
        "payload": base64.b64encode(payload).decode("ascii"),
        "sig": base64.b64encode(signature).decode("ascii"),
    }


def verify_envelope(envelope: dict, public: Ed25519PublicKey,
                    *, now: dt.datetime | None = None) -> dict:
    """The app's checks that need no stored state: signature, schema, dates."""
    try:
        payload = base64.b64decode(envelope["payload"], validate=True)
        signature = base64.b64decode(envelope["sig"], validate=True)
    except (KeyError, TypeError, ValueError) as exc:
        raise NewsError("not an envelope") from exc
    try:
        public.verify(signature, CONTEXT + payload)
    except InvalidSignature as exc:
        raise NewsError("bad signature") from exc
    decoded = json.loads(payload)
    if decoded.get("schema") != 1:
        raise NewsError("unsupported schema")
    current = now or now_utc()
    check_payload_dates(decoded, now=current, ahead=APP_ISSUE_AHEAD)
    if parse_time(decoded["expires"]) <= current:
        raise NewsError("expired")
    return decoded


# --- office hours ----------------------------------------------------------


#: Sessions alternate (owner, 16 Nov 2026): the 1st Tuesday of each month is a
#: morning, the 3rd an evening, both Europe/London. (start, end, house-style copy)
SESSIONS = {
    1: (dt.time(8, 0), dt.time(9, 0), "8 to 9am"),
    3: (dt.time(17, 30), dt.time(18, 30), "5.30 to 6.30pm"),
}


def office_hours_dates(start: dt.date, count: int) -> list[dt.date]:
    """The 1st and 3rd Tuesdays of each month, on or after ``start``."""
    found: list[dt.date] = []
    year, month = start.year, start.month
    while len(found) < count:
        first = dt.date(year, month, 1)
        first_tuesday = first + dt.timedelta(days=(1 - first.weekday()) % 7)
        for day in (first_tuesday, first_tuesday + dt.timedelta(days=14)):
            if day >= start and len(found) < count:
                found.append(day)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return found


def office_hours_item(day: dt.date) -> dict:
    """One session's item. ``day`` must be a 1st or 3rd Tuesday."""
    nth = (day.day - 1) // 7 + 1
    if day.weekday() != 1 or nth not in SESSIONS:
        raise NewsError(f"{day} is not a 1st or 3rd Tuesday")
    _, ends, times = SESSIONS[nth]
    # Shown from midnight London time four days before; gone when it ends.
    end = dt.datetime.combine(day, ends, LONDON)
    shown = dt.datetime.combine(day - dt.timedelta(days=4), dt.time(0, 0), LONDON)
    item_id = f"office-hours-{day.isoformat()}"
    when = f"{WEEKDAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]}"
    return {
        "id": item_id,
        "channels": ["store", "dmg"],
        "from": format_time(shown),
        "until": format_time(end),
        "locales": ["en"],
        "tone": "community",
        "text": {
            "en": {
                "title": "Office hours",
                "text": (
                    "Drop in with Martin Storey, author of Bristlenose, on "
                    f"{when}, {times} UK time."
                ),
                "more": "Bring a question, or something that needs fixing, improving or adding.",
                "link": "Office hours details",
            }
        },
        "href": (
            f"https://bristlenose.app/community/?ref=app-news&id={item_id}#office-hours"
        ),
    }


# --- CLI -------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_keygen = sub.add_parser("keygen", help="make a key pair outside the repo")
    p_keygen.add_argument("--out", type=Path, required=True)
    p_keygen.add_argument("--kid", default="k1")

    p_sign = sub.add_parser("sign", help="sign a payload into an envelope")
    p_sign.add_argument("--key", type=Path, required=True)
    p_sign.add_argument("--kid", required=True)
    p_sign.add_argument("--in", dest="inp", type=Path, required=True)
    p_sign.add_argument("--out", type=Path, required=True)

    p_verify = sub.add_parser("verify", help="verify an envelope as the app would")
    who = p_verify.add_mutually_exclusive_group(required=True)
    who.add_argument("--pub")
    who.add_argument("--kid", help="use PUBLIC_KEYS[kid]")
    p_verify.add_argument("--in", dest="inp", type=Path, required=True)

    p_hours = sub.add_parser("office-hours", help="print office-hours items as JSON")
    p_hours.add_argument("--from", dest="start", required=True, help="YYYY-MM-DD")
    p_hours.add_argument("--count", type=int, default=4)

    args = parser.parse_args(argv)
    try:
        if args.command == "keygen":
            path, public = keygen(args.out, args.kid)
            print(f"private key: {path}", file=sys.stderr)
            print(public)
        elif args.command == "sign":
            envelope = sign_bytes(load_private(args.key), args.kid, args.inp.read_bytes())
            args.out.write_text(json.dumps(envelope) + "\n", encoding="utf-8")
        elif args.command == "verify":
            b64 = args.pub if args.pub is not None else PUBLIC_KEYS.get(args.kid, "")
            envelope = json.loads(args.inp.read_text(encoding="utf-8"))
            if args.kid is not None and envelope.get("kid") != args.kid:
                raise NewsError(f"envelope kid is {envelope.get('kid')!r}, not {args.kid!r}")
            decoded = verify_envelope(envelope, load_public(b64))
            print(f"ok: kid {envelope.get('kid')}, env {decoded.get('env')}, "
                  f"issued {decoded['issued']}, expires {decoded['expires']}, "
                  f"{len(decoded.get('items') or [])} items")
        elif args.command == "office-hours":
            if args.count < 1:
                raise NewsError("--count must be at least 1")
            start = dt.date.fromisoformat(args.start)
            items = [office_hours_item(day) for day in office_hours_dates(start, args.count)]
            print(json.dumps(items, indent=2, ensure_ascii=False))
    except (NewsError, OSError, ValueError) as exc:
        print(f"sign-news: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
