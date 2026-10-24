"""What screen text keeps on disk (``docs/design-screens.md`` §4): an explicit off deletes it, and
the index stores no query strings, no fragments but an app's routes, and no chrome.

Synthetic frames and a fake engine, so nothing here needs ffmpeg or Vision.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from bristlenose import screen_text
from bristlenose.screen_text import index as sti
from bristlenose.screen_text.address import minimise, url_norm
from bristlenose.screen_text.engine import FakeEngine, Frame
from bristlenose.screen_text.screens import SessionInput, derive_screens, id_key
from bristlenose.server.app import create_app
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    p = tmp_path / "input"
    shutil.copytree(_FIXTURE_DIR, p)
    return p


def _read(project: Path) -> Path:
    """Something the job and the still route would have left: an index and a cached still."""
    d = sti.index_dir(project / "bristlenose-output")
    (d / "stills").mkdir(parents=True)
    (d / "s1.json").write_text(json.dumps({"version": screen_text.INDEX_VERSION}), encoding="utf-8")
    (d / "stills" / "s1_0123456789abcdef.jpg").write_bytes(b"\xff\xd8")
    return d


# ── Explicit off ──────────────────────────────────────────────────────────


def test_explicitly_off_is_exactly_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRISTLENOSE_SCREEN_TEXT", raising=False)
    assert not screen_text.explicitly_off()
    for value, off in (("0", True), ("1", False), ("", False), ("false", False), (" 0", False)):
        monkeypatch.setenv("BRISTLENOSE_SCREEN_TEXT", value)
        assert screen_text.explicitly_off() is off, value


def test_serve_started_explicitly_off_deletes_what_was_read(project: Path,
                                                            monkeypatch: pytest.MonkeyPatch) -> None:
    d = _read(project)
    monkeypatch.setenv("BRISTLENOSE_SCREEN_TEXT", "0")
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    assert not d.exists()
    # Off, and saying so: the lens and the progress row must be able to see it.
    client = AuthTestClient(app)
    assert client.get("/api/projects/1/screens/status").json()["enabled"] is False


def test_serve_started_with_the_switch_unset_deletes_nothing(project: Path,
                                                             monkeypatch: pytest.MonkeyPatch) -> None:
    """Unset is the CLI's default, not a decision: a CLI serve of a project the Mac app read must
    leave what it read alone."""
    d = _read(project)
    monkeypatch.delenv("BRISTLENOSE_SCREEN_TEXT", raising=False)
    create_app(project_dir=project, dev=False, db_url="sqlite://")
    assert (d / "s1.json").exists() and (d / "stills" / "s1_0123456789abcdef.jpg").exists()


def test_serve_started_on_deletes_nothing(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    d = _read(project)
    monkeypatch.setenv("BRISTLENOSE_SCREEN_TEXT", "1")
    create_app(project_dir=project, dev=False, db_url="sqlite://")
    assert (d / "s1.json").exists()


def test_explicitly_off_outranks_dev(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The researcher's off is not undone by a developer flag: the job would read it all again."""
    monkeypatch.setenv("BRISTLENOSE_SCREEN_TEXT", "0")
    app = create_app(project_dir=project, dev=True, db_url="sqlite://")
    app.state.dev = True
    assert AuthTestClient(app).get("/api/projects/1/screens/status").json()["enabled"] is False
    assert not app.state.screen_text._enabled()
    monkeypatch.delenv("BRISTLENOSE_SCREEN_TEXT")
    assert app.state.screen_text._enabled()  # unset, --dev still turns it on


def test_a_symlink_in_its_place_is_not_followed(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "keep.txt").write_text("not ours", encoding="utf-8")
    out = tmp_path / "out"
    link = sti.index_dir(out)
    link.parent.mkdir(parents=True)
    link.symlink_to(elsewhere, target_is_directory=True)
    assert sti.delete_at_rest(out) == 0
    assert (elsewhere / "keep.txt").exists()


# ── Addresses at rest ─────────────────────────────────────────────────────


@pytest.mark.parametrize(("read", "stored"), [
    # A query string is dropped: it carries searches, emails, session ids.
    ("example.com/account/orders?email=jane%40example.com&ref=abc", "example.com/account/orders"),
    ("https://www.example.co.uk/basket?x=1#top", "https://www.example.co.uk/basket"),
    # An OAuth fragment is never kept, nor an in-page anchor.
    ("app.example.io/callback#access_token=eyJhbGciOiJIUzI1NiJ9.abc&state=xyz", "app.example.io/callback"),
    ("docs.example.org/guide#section-2", "docs.example.org/guide"),
    # A route is how an app's screens are told apart: kept, with its identifiers masked.
    ("ikea.com/de/de/planner/#/planner", "ikea.com/de/de/planner/#/planner"),
    ("app.example.com/#/orders/12345678/edit?tab=notes", "app.example.com/#/orders/#/edit"),
    ("app.example.com/#!/users/3f2a9c1e5b7d4a608c1e/profile", "app.example.com/#!/users/#/profile"),
    ("app.example.com/#/account-settings-overview", "app.example.com/#/account-settings-overview"),
    # A route carrying something that is not a path (an email, a parameter) is not kept at all.
    ("app.example.com/#/invite/jane@example.com", "app.example.com/"),
    ("app.example.com/#/reset/token=abc", "app.example.com/"),
    # An address shown on the page, in a sentence, is minimised too.
    ("Open example.net/s?q=my+bank+balance to see it", "Open example.net/s to see it"),
    # Found by the security review, 14 Oct 2026: a percent-encoded email in a route, and the
    # hosts of internal tools and staging (no dotted name), kept their data.
    ("app.example.com/#/invite/jane%40example.com", "app.example.com/"),
    ("http://localhost:3000/reset?token=xyz", "http://localhost:3000/reset"),
    ("10.0.0.5/login?user=jane.smith", "10.0.0.5/login"),
    ("http://intranet/hr/case?employee=jane", "http://intranet/hr/case"),
    ("staging:8080/account?email=jane", "staging:8080/account"),
    ("intranet/hr/case?employee=jane", "intranet/hr/case"),
    ("http://localhost:3000/callback#access_token=xyz", "http://localhost:3000/callback"),
    # No address with a query or fragment: as read.
    ("Continue to checkout", "Continue to checkout"),
    ("ikea.com/gb/en/p/korken-jar-50213546", "ikea.com/gb/en/p/korken-jar-50213546"),
    ("Is this right?", "Is this right?"),
])
def test_an_address_is_stored_without_its_query_or_a_non_route_fragment(read: str, stored: str) -> None:
    assert minimise(read) == stored


def test_a_minimised_route_keys_the_screen_it_did_before() -> None:
    """Masking with url_norm's own mark keeps the key: a re-read study keeps its screens."""
    for read in ("app.example.com/#/orders/12345678", "ikea.com/de/de/planner/#/planner",
                 "ikea.com/gb/en/p/korken-jar-50213546?utm_source=x"):
        before, after = url_norm(read), url_norm(minimise(read))
        assert before is not None and after is not None
        assert id_key(before["path"], before["frag"]) == id_key(after["path"], after["frag"])


def _frames(n: int) -> list[Frame]:
    return [Frame(width=4, height=2, bgra=b"\0" * 32, t=4.0 * i) for i in range(n)]


def _ln(text: str, x: float, y: float, w: float = 0.3, h: float = 0.02) -> dict:
    return {"text": text, "conf": 0.9, "box": [x, y, w, h]}


def test_the_written_index_holds_no_query_and_no_chrome(tmp_path: Path) -> None:
    def lines(t: float) -> list[dict]:
        page = [_ln(f"order line {int(t)} {i}", 0.1, 0.2 + i * 0.02) for i in range(30)]
        return page + [
            _ln("Martin Storey", 0.9, 0.5),  # a call tile's name: on every dense frame, chrome
            _ln("example.com/account/orders?email=jane%40example.com", 0.2, 0.03),
            _ln("example.com/#access_token=s3cr3tT0k3nValue", 0.2, 0.06),
        ]
    rec = sti.index_frames(iter(_frames(3)), FakeEngine(lines))
    path = tmp_path / "s1.json"
    sti.write_index(path, {**rec, "key": "k"})
    written = path.read_text(encoding="utf-8")
    for secret in ("Martin Storey", "jane", "email=", "access_token", "s3cr3t"):
        assert secret not in written, secret
    texts = {e["text"] for e in json.loads(written)["episodes"]}
    # The address bar is sticky here too (one page, every frame), and kept: it is the screen key.
    assert "example.com/account/orders" in texts
    assert any(e["sticky"] for e in rec["episodes"] if e["text"] == "example.com/account/orders")
    assert sti.read_index(path) is not None


def test_the_same_screens_derive_from_the_minimised_index() -> None:
    """Chrome dropped and addresses minimised, the screens are the ones the full reading gave."""
    def lines(t: float) -> list[dict]:
        # Three pages, a third of the frames each: no page's own lines are on half of them (sticky).
        page = "checkout" if t < 12 else "basket" if t < 24 else "delivery"
        body = [_ln(f"{page} line {i}", 0.1, 0.25 + i * 0.02) for i in range(30)]
        return body + [_ln("Martin Storey", 0.9, 0.5),
                       _ln(f"ikea.com/gb/en/{page}?session=abc123", 0.2, 0.05)]
    minimised = sti.index_frames(iter(_frames(9)), FakeEngine(lines))
    # The same frames as an index that stored everything as read (as version 2 did).
    seen: dict[str, tuple[list[float], list[float]]] = {}
    for i in range(9):
        for ln in lines(4.0 * i):
            seen.setdefault(ln["text"], (ln["box"], []))[1].append(4.0 * i)
    raw = {"every": 4.0, "moments": [], "episodes": [
        {"text": text, "box": box, "sticky": text == "Martin Storey", "runs": [[min(ts), max(ts)]]}
        for text, (box, ts) in seen.items()]}
    keys = lambda idx: sorted(s["key"] for s in derive_screens([SessionInput("s1", "p1", idx, [])]))  # noqa: E731
    assert keys(minimised) == keys(raw) == ["url:/basket", "url:/checkout", "url:/delivery"]
    assert not any(e["text"] == "Martin Storey" for e in minimised["episodes"])


def test_an_index_from_an_older_version_is_deleted_with_its_stills(tmp_path: Path) -> None:
    d = sti.index_dir(tmp_path)
    (d / "stills").mkdir(parents=True)
    (d / "s1.json").write_text(json.dumps({"version": screen_text.INDEX_VERSION - 1}), encoding="utf-8")
    (d / "s2.json").write_text(json.dumps({"version": screen_text.INDEX_VERSION}), encoding="utf-8")
    (d / "stills" / "s1_12.jpg").write_bytes(b"x")
    (d / "stills" / "s2_12.jpg").write_bytes(b"x")
    assert sti.purge_stale(tmp_path) == 1
    assert sorted(p.name for p in d.rglob("*") if p.is_file()) == ["s2.json", "s2_12.jpg"]


def test_a_still_from_before_stills_were_named_by_session_is_deleted(tmp_path: Path) -> None:
    d = sti.index_dir(tmp_path)
    (d / "stills").mkdir(parents=True)
    (d / "stills" / "053a1df9ebb6a69a.jpg").write_bytes(b"x")
    (d / "stills" / "s1_053a1df9ebb6a69a.jpg").write_bytes(b"x")
    sti.purge_stale(tmp_path)
    assert [p.name for p in (d / "stills").iterdir()] == ["s1_053a1df9ebb6a69a.jpg"]


def test_an_index_from_a_newer_version_is_kept(tmp_path: Path) -> None:
    d = sti.index_dir(tmp_path)
    d.mkdir(parents=True)
    (d / "s1.json").write_text(json.dumps({"version": screen_text.INDEX_VERSION + 1}), encoding="utf-8")
    assert sti.purge_stale(tmp_path) == 0
    assert (d / "s1.json").exists()


def test_serve_start_purges_an_older_index(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRISTLENOSE_SCREEN_TEXT", raising=False)
    d = sti.index_dir(project / "bristlenose-output")
    d.mkdir(parents=True, exist_ok=True)
    (d / "old.json").write_text(json.dumps({"version": screen_text.INDEX_VERSION - 1}), encoding="utf-8")
    create_app(project_dir=project, dev=False, db_url="sqlite://")
    assert not (d / "old.json").exists()
