"""Tests for ``scripts/sign-news.py``, and the Python half of the news seam.

The seam (root CLAUDE.md, "Seams"): ``tests/fixtures/news-envelope-contract.json``
is an envelope signed here with a fixed, deliberately public TEST key. The
Swift suite (``NewsCheckTests``, "Seam") verifies the same file with CryptoKit
and reads the same item out of it. Ed25519 is deterministic, so this side
proves the committed file is exactly what the script produces; the Swift side
proves the app accepts it. Change the signing format on one side and one of
the two suites fails.

Regenerate the fixture (only when the format changes on purpose)::

    .venv/bin/python tests/test_sign_news.py
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import importlib.util
import json
import re
import stat
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "tests" / "fixtures" / "news-envelope-contract.json"
SWIFT_KEYS = REPO / "desktop" / "Bristlenose" / "Bristlenose" / "NewsKeys.swift"


def _load_script():
    spec = importlib.util.spec_from_file_location("sign_news", REPO / "scripts" / "sign-news.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["sign_news"] = module
    spec.loader.exec_module(module)
    return module


# Before the load, which reads ZoneInfo("Europe/London") at import: Windows has
# the IANA zone database only with the tzdata package. The script is the
# maintainer's Mac release tool, and the seam's other half is proved by the Swift
# suite and the Linux and macOS jobs (windows-latest, 19 Nov 2026).
if sys.platform == "win32":
    pytest.skip(
        "scripts/sign-news.py is a Mac release tool; Windows has no Europe/London zone "
        "without the tzdata package",
        allow_module_level=True,
    )

sn = _load_script()

# A TEST key, public on purpose: it signs only the contract fixture. It is never
# in any keyring the app trusts (production keys live in NewsKeys.swift).
TEST_SEED = hashlib.sha256(b"bristlenose-news-contract-test-key-not-secret").digest()
NOW = dt.datetime(2026, 11, 20, 12, 0, tzinfo=dt.timezone.utc)


def _test_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(TEST_SEED)


def _payload(**overrides) -> dict:
    payload = {
        "schema": 1,
        "env": "prod",
        "issued": "2026-11-20T09:00:00Z",
        "expires": "2026-12-31T00:00:00Z",
        "items": [sn.office_hours_item(dt.date(2026, 12, 15))],
    }
    payload.update(overrides)
    return payload


def _bytes(payload: dict) -> bytes:
    return (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def build_fixture() -> dict:
    payload = _bytes(_payload())
    envelope = sn.sign_bytes(_test_key(), "k1", payload, now=NOW)
    item = _payload()["items"][0]
    return {
        "_comment": (
            "Signed by tests/test_sign_news.py with a PUBLIC test key; verified by "
            "NewsCheckTests (Swift). Regenerate: .venv/bin/python tests/test_sign_news.py"
        ),
        "public_key": sn.public_b64(_test_key()),
        "kid": "k1",
        "context": {
            "now": "2026-12-12T12:00:00Z",
            "interface_language": "en",
            "channel": "store",
            "app_version": "0.47.0",
        },
        "envelope": envelope,
        "expect": {
            "id": item["id"],
            "tone": item["tone"],
            "title": item["text"]["en"]["title"],
            "text": item["text"]["en"]["text"],
            "more": item["text"]["en"]["more"],
            "link": item["text"]["en"]["link"],
            "href": item["href"],
            "until": item["until"],
        },
    }


# --- the seam ----------------------------------------------------------------


def test_committed_fixture_is_what_the_script_signs():
    committed = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert committed == build_fixture()


def test_fixture_verifies_with_its_public_key():
    committed = json.loads(FIXTURE.read_text(encoding="utf-8"))
    public = sn.load_public(committed["public_key"])
    decoded = sn.verify_envelope(committed["envelope"], public, now=NOW)
    assert decoded["items"][0]["id"] == "office-hours-2026-12-15"


def test_public_keys_match_the_swift_constants():
    swift = SWIFT_KEYS.read_text(encoding="utf-8")
    found = dict(re.findall(r'static let production(K[01]) = "([^"]*)"', swift))
    assert found == {"K1": sn.PUBLIC_KEYS["k1"], "K0": sn.PUBLIC_KEYS["k0"]}


def test_context_matches_swift():
    swift = (SWIFT_KEYS.parent / "NewsCheck.swift").read_text(encoding="utf-8")
    assert 'Data("bristlenose-news-v1\\n".utf8)' in swift
    assert sn.CONTEXT == b"bristlenose-news-v1\n"


# --- keygen ------------------------------------------------------------------


def test_keygen_refuses_inside_the_repo():
    with pytest.raises(sn.NewsError, match="inside the repo"):
        sn.keygen(REPO / "scratch-news-keys", "k1")
    assert not (REPO / "scratch-news-keys").exists()


def test_keygen_writes_a_private_0600_key_and_prints_its_public_half(tmp_path):
    out = tmp_path / "keys"
    path, public = sn.keygen(out, "k1")
    assert len(path.read_bytes()) == 32
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert sn.public_b64(sn.load_private(path)) == public
    with pytest.raises(sn.NewsError, match="overwrite"):
        sn.keygen(out, "k1")


def test_cli_keygen_prints_only_the_public_key(tmp_path, capsys):
    assert sn.main(["keygen", "--out", str(tmp_path), "--kid", "k0"]) == 0
    out = capsys.readouterr().out.strip()
    assert len(base64.b64decode(out)) == 32
    assert (tmp_path / "bristlenose-news-k0.key").exists()


# --- sign and verify -----------------------------------------------------------


def test_sign_and_verify_round_trip_through_the_cli(tmp_path, capsys):
    key_path, public = sn.keygen(tmp_path / "keys", "k1")
    now = sn.now_utc()
    payload = _payload(issued=sn.format_time(now),
                       expires=sn.format_time(now + dt.timedelta(days=30)))
    (tmp_path / "payload.json").write_bytes(_bytes(payload))
    assert sn.main(["sign", "--key", str(key_path), "--kid", "k1",
                    "--in", str(tmp_path / "payload.json"),
                    "--out", str(tmp_path / "envelope.json")]) == 0
    assert sn.main(["verify", "--pub", public, "--in", str(tmp_path / "envelope.json")]) == 0
    assert capsys.readouterr().out.startswith("ok: kid k1")


def test_signature_covers_the_context_and_the_exact_bytes():
    envelope = sn.sign_bytes(_test_key(), "k1", _bytes(_payload()), now=NOW)
    raw = base64.b64decode(envelope["payload"])
    sig = base64.b64decode(envelope["sig"])
    _test_key().public_key().verify(sig, b"bristlenose-news-v1\n" + raw)


def test_a_tampered_payload_fails_verification():
    envelope = sn.sign_bytes(_test_key(), "k1", _bytes(_payload()), now=NOW)
    raw = bytearray(base64.b64decode(envelope["payload"]))
    raw[-2] ^= 1
    envelope["payload"] = base64.b64encode(bytes(raw)).decode()
    with pytest.raises(sn.NewsError, match="bad signature"):
        sn.verify_envelope(envelope, _test_key().public_key(), now=NOW)


def test_sign_refuses_issued_more_than_a_day_ahead():
    payload = _payload(issued="2026-11-21T12:00:01Z", expires="2026-12-20T00:00:00Z")
    with pytest.raises(sn.NewsError, match="too far ahead"):
        sn.sign_bytes(_test_key(), "k1", _bytes(payload), now=NOW)


def test_sign_refuses_a_lifetime_over_45_days():
    payload = _payload(issued="2026-11-20T09:00:00Z", expires="2027-01-04T09:00:01Z")
    with pytest.raises(sn.NewsError, match="45 days"):
        sn.sign_bytes(_test_key(), "k1", _bytes(payload), now=NOW)


def test_sign_accepts_exactly_45_days():
    payload = _payload(issued="2026-11-20T09:00:00Z", expires="2027-01-04T09:00:00Z")
    sn.sign_bytes(_test_key(), "k1", _bytes(payload), now=NOW)


def test_sign_refuses_a_payload_without_schema_1():
    with pytest.raises(sn.NewsError, match="schema 1"):
        sn.sign_bytes(_test_key(), "k1", _bytes(_payload(schema=2)), now=NOW)


def test_verify_refuses_an_expired_file():
    envelope = sn.sign_bytes(_test_key(), "k1", _bytes(_payload()), now=NOW)
    later = dt.datetime(2026, 12, 31, 0, 0, tzinfo=dt.timezone.utc)
    with pytest.raises(sn.NewsError, match="expired"):
        sn.verify_envelope(envelope, _test_key().public_key(), now=later)


def test_verify_with_an_unset_production_kid_fails_loudly(tmp_path, capsys, monkeypatch):
    envelope = sn.sign_bytes(_test_key(), "k1", _bytes(_payload()), now=NOW)
    (tmp_path / "e.json").write_text(json.dumps(envelope), encoding="utf-8")
    # Unset it here rather than skip once the real key is committed, which
    # would have retired this test on the day the key landed.
    monkeypatch.setitem(sn.PUBLIC_KEYS, "k1", "")
    assert sn.main(["verify", "--kid", "k1", "--in", str(tmp_path / "e.json")]) == 1
    assert "is it set" in capsys.readouterr().err


# --- office hours --------------------------------------------------------------


def test_office_hours_are_the_first_and_third_tuesdays():
    days = sn.office_hours_dates(dt.date(2026, 12, 15), 5)
    assert days == [dt.date(2026, 12, 15), dt.date(2027, 1, 5), dt.date(2027, 1, 19),
                    dt.date(2027, 2, 2), dt.date(2027, 2, 16)]
    assert all(day.weekday() == 1 for day in days)


def test_office_hours_item_for_15_december():
    item = sn.office_hours_item(dt.date(2026, 12, 15))
    assert item["id"] == "office-hours-2026-12-15"
    assert item["from"] == "2026-12-11T00:00:00Z"
    assert item["until"] == "2026-12-15T18:30:00Z"
    assert item["tone"] == "community"
    assert item["locales"] == ["en"]
    en = item["text"]["en"]
    assert "kind" not in en
    assert en["title"] == "Office hours"
    assert en["text"] == ("Drop in with Martin Storey, author of Bristlenose, on Tuesday "
                          "15 December, 5.30 to 6.30pm UK time.")
    assert en["more"] == "Bring a question, or something that needs fixing, improving or adding."
    assert en["link"] == "Office hours details"
    assert item["href"] == ("https://bristlenose.app/community/?ref=app-news"
                            "&id=office-hours-2026-12-15#office-hours")


def test_first_tuesdays_are_mornings():
    item = sn.office_hours_item(dt.date(2027, 1, 5))
    assert item["id"] == "office-hours-2027-01-05"
    assert item["from"] == "2027-01-01T00:00:00Z"
    assert item["until"] == "2027-01-05T09:00:00Z"
    assert item["text"]["en"]["text"] == ("Drop in with Martin Storey, author of Bristlenose, "
                                          "on Tuesday 5 January, 8 to 9am UK time.")
    assert item["href"] == ("https://bristlenose.app/community/?ref=app-news"
                            "&id=office-hours-2027-01-05#office-hours")


def test_sessions_alternate_morning_and_evening():
    items = [sn.office_hours_item(day) for day in sn.office_hours_dates(dt.date(2026, 12, 15), 4)]
    times = [item["until"][11:16] for item in items]
    assert times == ["18:30", "09:00", "18:30", "09:00"]


def test_office_hours_in_summer_time_convert_to_utc():
    morning = sn.office_hours_item(dt.date(2027, 4, 6))
    assert morning["until"] == "2027-04-06T08:00:00Z"
    assert morning["from"] == "2027-04-01T23:00:00Z"
    assert "Tuesday 6 April, 8 to 9am" in morning["text"]["en"]["text"]
    evening = sn.office_hours_item(dt.date(2027, 4, 20))
    assert evening["until"] == "2027-04-20T17:30:00Z"
    assert "Tuesday 20 April, 5.30 to 6.30pm" in evening["text"]["en"]["text"]


def test_a_day_that_is_not_a_session_is_refused():
    with pytest.raises(sn.NewsError):
        sn.office_hours_item(dt.date(2026, 12, 8))  # 2nd Tuesday
    with pytest.raises(sn.NewsError):
        sn.office_hours_item(dt.date(2026, 12, 16))  # a Wednesday


def test_office_hours_cli_prints_items(capsys):
    assert sn.main(["office-hours", "--from", "2026-12-15", "--count", "2"]) == 0
    items = json.loads(capsys.readouterr().out)
    assert [i["id"] for i in items] == ["office-hours-2026-12-15", "office-hours-2027-01-05"]


if __name__ == "__main__":
    FIXTURE.write_text(json.dumps(build_fixture(), indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"wrote {FIXTURE}")


# --- going live: set-keys and publish -----------------------------------------


def _two_keys(tmp_path):
    p1, k1 = sn.keygen(tmp_path / "k1", "k1")
    p0, k0 = sn.keygen(tmp_path / "k0", "k0")
    return p1, k1, k0


def _copies(tmp_path):
    """Copies of the two files with the production keys blanked, as before set-keys ran."""
    swift_text = re.sub(r'(static let productionK[01] = )"[^"]*"', r'\1""',
                        SWIFT_KEYS.read_text(encoding="utf-8"))
    script_text = re.sub(r'^PUBLIC_KEYS: dict\[str, str\] = .*$',
                         'PUBLIC_KEYS: dict[str, str] = {"k1": "", "k0": ""}',
                         (REPO / "scripts" / "sign-news.py").read_text(encoding="utf-8"),
                         count=1, flags=re.M)
    swift = tmp_path / "NewsKeys.swift"
    swift.write_text(swift_text, encoding="utf-8")
    script = tmp_path / "sign-news.py"
    script.write_text(script_text, encoding="utf-8")
    return swift, script


def test_set_keys_writes_both_places_once(tmp_path):
    _, k1, k0 = _two_keys(tmp_path)
    swift, script = _copies(tmp_path)
    sn.set_keys(k1, k0, swift_path=swift, script_path=script)
    found = dict(re.findall(r'static let production(K[01]) = "([^"]*)"',
                            swift.read_text(encoding="utf-8")))
    assert found == {"K1": k1, "K0": k0}
    assert f'{{"k1": "{k1}", "k0": "{k0}"}}' in script.read_text(encoding="utf-8")
    with pytest.raises(sn.NewsError, match="not both empty"):
        sn.set_keys(k1, k0, swift_path=swift, script_path=script)


def test_set_keys_refuses_bad_or_equal_keys(tmp_path):
    _, k1, _ = _two_keys(tmp_path)
    swift, script = _copies(tmp_path)
    before = swift.read_text(encoding="utf-8")
    with pytest.raises(sn.NewsError, match="k0"):
        sn.set_keys(k1, "not-a-key", swift_path=swift, script_path=script)
    with pytest.raises(sn.NewsError, match="different"):
        sn.set_keys(k1, k1, swift_path=swift, script_path=script)
    assert swift.read_text(encoding="utf-8") == before


def _site(tmp_path):
    app = tmp_path / "site" / "content" / "app"
    app.mkdir(parents=True)
    (app / ".htaccess").write_text("# test\n", encoding="utf-8")
    return tmp_path / "site"


def test_publish_writes_a_file_the_app_would_accept(tmp_path):
    key, k1, _ = _two_keys(tmp_path)
    site = _site(tmp_path)
    out = sn.publish(key, dt.date(2026, 12, 15), 2, site, now=NOW, public_b64=k1)
    assert out == site / "content" / "app" / "news"
    envelope = json.loads(out.read_text(encoding="utf-8"))
    assert envelope["kid"] == "k1"
    decoded = sn.verify_envelope(envelope, sn.load_public(k1), now=NOW)
    assert decoded["env"] == "prod"
    assert [i["id"] for i in decoded["items"]] == ["office-hours-2026-12-15",
                                                  "office-hours-2027-01-05"]
    assert sn.parse_time(decoded["expires"]) - sn.parse_time(decoded["issued"]) < sn.MAX_LIFETIME


def test_publish_refuses_a_key_the_app_does_not_trust(tmp_path):
    key, _, k0 = _two_keys(tmp_path)
    site = _site(tmp_path)
    with pytest.raises(sn.NewsError, match="bad signature"):
        sn.publish(key, dt.date(2026, 12, 15), 2, site, now=NOW, public_b64=k0)
    assert not (site / "content" / "app" / "news").exists()


def test_publish_refuses_a_folder_that_is_not_the_website(tmp_path):
    key, k1, _ = _two_keys(tmp_path)
    with pytest.raises(sn.NewsError, match="website repo"):
        sn.publish(key, dt.date(2026, 12, 15), 2, tmp_path, now=NOW, public_b64=k1)
