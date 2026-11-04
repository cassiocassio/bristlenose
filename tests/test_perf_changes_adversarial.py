"""The 4 Nov 2026 performance changes, attacked in awkward ways.

Each class names the change it hammers. These are regression tests for the behaviour the
speed-ups must not have disturbed, not benchmarks: nothing here asserts a time.
"""

from __future__ import annotations

import asyncio
import gzip
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import create_engine, text

from bristlenose import credentials_macos
from bristlenose.credentials_macos import MacOSCredentialStore
from bristlenose.server.perf_timing import ServerTimingMiddleware
from bristlenose.utils.text import count_noun

_REPO = Path(__file__).parents[1]


def _py(code: str, **env: str) -> subprocess.CompletedProcess[str]:
    import os

    full = dict(os.environ)
    full.update(env)
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=full)


# --------------------------------------------------------------------------- lazy inflect


class TestLazyInflect:
    """count_noun builds its engine on first plural."""

    @pytest.mark.parametrize("n", [-5, -1, 0, 1, 2, 3, 11, 100, 10**12])
    @pytest.mark.parametrize("word", ["session", "child", "person", "topic boundary", "quote", "é", "日本語"])
    def test_same_answer_as_the_eager_formula(self, n: int, word: str) -> None:
        import inflect

        eager = inflect.engine().plural_noun(word)
        expected = f"{n} {word if n == 1 else eager}"
        assert count_noun(n, word) == expected

    def test_a_count_of_one_never_loads_inflect(self) -> None:
        r = _py("import sys; from bristlenose.utils.text import count_noun as c; c(1, 'child'); "
                "sys.exit(1 if 'inflect' in sys.modules else 0)")
        assert r.returncode == 0, r.stderr

    def test_an_explicit_plural_never_loads_inflect(self) -> None:
        r = _py("import sys; from bristlenose.utils.text import count_noun as c; "
                "assert c(7, 'x', plural='xen') == '7 xen'; "
                "sys.exit(1 if 'inflect' in sys.modules else 0)")
        assert r.returncode == 0, r.stderr

    def test_a_pile_of_threads_hitting_the_first_plural_together(self) -> None:
        code = (
            "import threading, sys\n"
            "from bristlenose.utils.text import count_noun as c\n"
            "out=[]; err=[]\n"
            "def go():\n"
            "    try: out.append(c(3,'child'))\n"
            "    except BaseException as e: err.append(repr(e))\n"
            "ts=[threading.Thread(target=go) for _ in range(48)]\n"
            "[t.start() for t in ts]; [t.join() for t in ts]\n"
            "print(set(out), err)\n"
        )
        r = _py(code)
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == "{'3 children'} []"


# --------------------------------------------------------------------------- Keychain cache


class _Spawner:
    def __init__(self) -> None:
        self.reads = 0
        self.value: str | BaseException = "sk-a"
        self.lock = threading.Lock()

    def __call__(self, argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        if argv[1] == "find-generic-password":
            with self.lock:
                self.reads += 1
            if isinstance(self.value, BaseException):
                raise self.value
            return subprocess.CompletedProcess(argv, 0, stdout=self.value + "\n", stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")


@pytest.fixture
def sp(monkeypatch: pytest.MonkeyPatch) -> _Spawner:
    s = _Spawner()
    monkeypatch.setattr(subprocess, "run", s)
    return s


class TestKeychainCache:
    def test_thirty_two_threads_agree_and_then_nobody_spawns(self, sp: _Spawner) -> None:
        results: list[str | None] = []
        barrier = threading.Barrier(32)

        def go() -> None:
            barrier.wait()
            results.append(MacOSCredentialStore().get("anthropic"))

        ts = [threading.Thread(target=go) for _ in range(32)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        assert set(results) == {"sk-a"}
        before = sp.reads
        for _ in range(50):
            assert MacOSCredentialStore().get("anthropic") == "sk-a"
        assert sp.reads == before  # a duplicate race read is allowed once; none after

    def test_exactly_at_the_ttl_the_read_has_expired(
        self, sp: _Spawner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        now = [1000.0]
        monkeypatch.setattr(credentials_macos, "_clock", lambda: now[0])
        store = MacOSCredentialStore()
        store.get("openai")
        now[0] += credentials_macos._CACHE_TTL_S  # not "< TTL" any more
        store.get("openai")
        assert sp.reads == 2

    def test_a_clock_that_leaps_forward_a_year_just_expires_it(
        self, sp: _Spawner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        now = [0.0]
        monkeypatch.setattr(credentials_macos, "_clock", lambda: now[0])
        store = MacOSCredentialStore()
        store.get("azure")
        now[0] += 3600 * 24 * 365
        store.get("azure")
        assert sp.reads == 2

    def test_a_failing_security_gives_none_and_a_later_set_is_seen_at_once(
        self, sp: _Spawner
    ) -> None:
        sp.value = PermissionError("sandbox said no")
        store = MacOSCredentialStore()
        assert store.get("google") is None
        assert store.get("google") is None  # kept for the window, not re-spawned
        assert sp.reads == 1
        sp.value = "sk-new"
        store.set("google", "sk-new")  # clears the entry
        assert store.get("google") == "sk-new"

    def test_an_unregistered_key_gets_a_derived_name_and_poisons_nothing(self, sp: _Spawner) -> None:
        # providers.credential_service_name derives a name for a key it does not know
        # (miro_refresh, a test's throwaway); that must behave like any other key.
        store = MacOSCredentialStore()
        sp.value = "throwaway"
        assert store.get("no-such-provider") == "throwaway"
        sp.value = "real"
        assert store.get("anthropic") == "real"
        assert store.get("no-such-provider") == "throwaway"

    def test_values_with_odd_whitespace_and_unicode_round_trip_and_stay_equal_when_cached(
        self, sp: _Spawner
    ) -> None:
        sp.value = "  sk-ünï-☃  "
        store = MacOSCredentialStore()
        first = store.get("miro")
        assert first == "sk-ünï-☃"
        assert store.get("miro") == first

    def test_each_key_has_its_own_entry(self, sp: _Spawner) -> None:
        store = MacOSCredentialStore()
        sp.value = "A"
        assert store.get("anthropic") == "A"
        sp.value = "B"
        assert store.get("openai") == "B"
        assert store.get("anthropic") == "A"
        assert store.get("openai") == "B"

    def test_clear_cache_is_idempotent_and_safe_when_empty(self) -> None:
        credentials_macos.clear_cache()
        credentials_macos.clear_cache()


# --------------------------------------------------------------------------- Server-Timing


def _timed_app() -> FastAPI:
    engine = create_engine("sqlite://")
    app = FastAPI()
    app.add_middleware(ServerTimingMiddleware)

    def run(n: int) -> None:
        with engine.connect() as c:
            for _ in range(n):
                c.execute(text("select 1"))

    @app.get("/one")
    def one() -> dict[str, int]:
        run(1)
        return {"n": 1}

    @app.get("/five")
    def five() -> dict[str, int]:
        run(5)
        return {"n": 5}

    @app.get("/boom")
    def boom() -> None:
        run(2)
        raise RuntimeError("route exploded")

    @app.get("/gone")
    def gone() -> None:
        raise HTTPException(status_code=404)

    @app.get("/stream")
    def stream() -> StreamingResponse:
        run(3)
        return StreamingResponse(iter([b"a" * 10, b"b" * 10]), media_type="text/plain")

    @app.get("/prior")
    def prior() -> Any:
        from fastapi.responses import JSONResponse

        return JSONResponse({"ok": 1}, headers={"Server-Timing": "cache;desc=hit"})

    return app


def _count(resp: httpx.Response) -> int:
    import re

    m = re.search(r'desc="(\d+) queries"', resp.headers["server-timing"])
    assert m, resp.headers.get("server-timing")
    return int(m.group(1))


class TestServerTiming:
    def test_two_hundred_interleaved_requests_each_get_their_own_count(self) -> None:
        async def go() -> list[tuple[str, int]]:
            transport = httpx.ASGITransport(app=_timed_app())
            async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
                paths = ["/one", "/five"] * 100
                resps = await asyncio.gather(*(c.get(p) for p in paths))
                return [(p, _count(r)) for p, r in zip(paths, resps, strict=True)]

        got = asyncio.run(go())
        assert {(p, n) for p, n in got} == {("/one", 1), ("/five", 5)}

    def test_a_request_after_a_crash_starts_from_zero(self) -> None:
        # Not mutation-sensitive to the context-var reset: each ASGI request runs in its own
        # task context, so the reset is hygiene. The counts are what must not bleed.
        async def go() -> int:
            transport = httpx.ASGITransport(app=_timed_app(), raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
                boom = await c.get("/boom")
                assert boom.status_code == 500
                return _count(await c.get("/one"))

        assert asyncio.run(go()) == 1  # the two queries of /boom did not leak into it

    @pytest.mark.parametrize("path,status", [("/gone", 404), ("/nowhere", 404)])
    def test_error_responses_carry_the_header_too(self, path: str, status: int) -> None:
        async def go() -> httpx.Response:
            transport = httpx.ASGITransport(app=_timed_app())
            async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
                return await c.get(path)

        r = asyncio.run(go())
        assert r.status_code == status
        assert "server-timing" in r.headers

    def test_a_streaming_response_gets_the_header_and_its_whole_body(self) -> None:
        async def go() -> httpx.Response:
            transport = httpx.ASGITransport(app=_timed_app())
            async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
                return await c.get("/stream")

        r = asyncio.run(go())
        assert r.content == b"a" * 10 + b"b" * 10
        assert _count(r) == 3

    def test_an_existing_server_timing_header_is_added_to_not_replaced(self) -> None:
        async def go() -> list[str]:
            transport = httpx.ASGITransport(app=_timed_app())
            async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
                return c.get_list if False else (await c.get("/prior")).headers.get_list("server-timing")

        values = asyncio.run(go())
        assert any(v.startswith("cache;") for v in values)
        assert any(v.startswith("bn;") for v in values)

    def test_a_websocket_scope_passes_through_untouched(self) -> None:
        seen: list[str] = []

        async def inner(scope: Any, receive: Any, send: Any) -> None:
            seen.append(scope["type"])

        mw = ServerTimingMiddleware(inner)

        async def go() -> None:
            await mw({"type": "websocket"}, None, None)  # type: ignore[arg-type]
            await mw({"type": "lifespan"}, None, None)  # type: ignore[arg-type]

        asyncio.run(go())
        assert seen == ["websocket", "lifespan"]


# --------------------------------------------------------------------------- gzip level 1


class TestGzipLevelOne:
    @pytest.fixture
    def client(self) -> Any:
        from bristlenose.server.app import create_app
        from tests.conftest import AuthTestClient

        app = create_app(db_url="sqlite://")

        @app.get("/__big")
        def big() -> dict[str, str]:
            return {"x": "lorem ipsum dolor sit amet " * 4000}

        @app.get("/__small")
        def small() -> dict[str, str]:
            return {"x": "tiny"}

        return AuthTestClient(app)

    def test_a_big_body_is_gzipped_and_decompresses_to_the_identical_bytes(self, client: Any) -> None:
        gz = client.get("/__big", headers={"Accept-Encoding": "gzip"})
        raw = client.get("/__big", headers={"Accept-Encoding": "identity"})
        assert gz.headers["content-encoding"] == "gzip"
        assert "content-encoding" not in raw.headers
        assert gz.content == raw.content

    def test_the_wire_bytes_are_a_valid_gzip_stream(self, client: Any) -> None:
        with client.stream("GET", "/__big", headers={"Accept-Encoding": "gzip"}) as r:
            wire = b"".join(r.iter_raw())
        assert gzip.decompress(wire).startswith(b'{"x":"lorem')

    def test_a_small_body_survives_whether_or_not_it_is_compressed(self, client: Any) -> None:
        # Starlette skips a body under minimum_size, but the app's BaseHTTPMiddleware layers
        # stream the body in chunks, so the gzip layer cannot see its size and compresses
        # even a 12-byte JSON (seen at level 9 too: /signals/snapshot 65 B -> 78 B on 4 Nov
        # 2026). About 0.1 ms and 13 bytes; not worth a fix. What must hold is the round trip.
        gz = client.get("/__small", headers={"Accept-Encoding": "gzip"})
        raw = client.get("/__small", headers={"Accept-Encoding": "identity"})
        assert gz.content == raw.content == b'{"x":"tiny"}'

    def test_no_accept_encoding_means_no_compression(self, client: Any) -> None:
        r = client.get("/__big", headers={"Accept-Encoding": ""})
        assert "content-encoding" not in r.headers

    def test_head_request_does_not_crash(self, client: Any) -> None:
        # HEAD of a GET-only route is a 405, never a 500
        assert client.head("/__big", headers={"Accept-Encoding": "gzip"}).status_code in (200, 405)


# --------------------------------------------------------------------------- libyaml templates


class TestCodebookLoader:
    def test_the_c_loader_refuses_python_object_tags_like_safe_load(self) -> None:
        hostile = "x: !!python/object/apply:os.system ['echo pwned']\n"
        loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
        with pytest.raises(yaml.YAMLError):
            yaml.load(hostile, Loader=loader)
        with pytest.raises(yaml.YAMLError):
            yaml.safe_load(hostile)

    @pytest.mark.parametrize(
        "doc",
        [
            "a: 1\nb: [1, 2, {c: d}]\n",
            "base: &b {k: v}\nuse:\n  <<: *b\n  extra: 1\n",
            "text: |\n  line one\n  line two\n",
            "emoji: \"☃ 日本語 é\"\n",
            "n: 0x1F\nf: 1e3\nnull_: ~\nyes_: yes\n",
            "",
        ],
    )
    def test_both_loaders_agree_on_awkward_documents(self, doc: str) -> None:
        c = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
        assert yaml.load(doc, Loader=c) == yaml.safe_load(doc)

    def test_without_libyaml_the_template_still_loads_the_same(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from bristlenose.server import codebook

        path = next(iter(codebook._bundled_template_paths().values()))
        with_c = codebook._load_template.__wrapped__(path)
        monkeypatch.delattr(yaml, "CSafeLoader", raising=False)
        without_c = codebook._load_template.__wrapped__(path)
        assert with_c == without_c

    def test_a_malformed_template_raises_a_yaml_error_not_something_stranger(
        self, tmp_path: Path
    ) -> None:
        from bristlenose.server import codebook

        bad = tmp_path / "bad.yaml"
        bad.write_text("a: [unclosed\n", encoding="utf-8")
        with pytest.raises(yaml.YAMLError):
            codebook._load_template.__wrapped__(bad)


# --------------------------------------------------------------------------- export, parked pill


class TestExportWithParkedPill:
    @pytest.fixture
    def client(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
        from bristlenose.server.app import create_app
        from bristlenose.server.routes import export
        from tests.conftest import AuthTestClient

        (tmp_path / "app.js").write_text("// stub", encoding="utf-8")
        (tmp_path / "app.css").write_text("/* stub */", encoding="utf-8")
        monkeypatch.setattr(export, "_EXPORT_STATIC_DIR", tmp_path)
        fixture = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
        return AuthTestClient(create_app(project_dir=fixture, dev=True, db_url="sqlite://"))

    def _keys(self, resp: httpx.Response) -> set[str]:
        import re

        return set(re.findall(r'"(/[a-z][^"]*)":', resp.text))

    def test_the_only_difference_between_parked_and_enabled_is_the_moderator_keys(
        self, client: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from bristlenose.server.routes import export, quotes

        monkeypatch.setattr(quotes, "get_moderator_question",
                            lambda project_id, dom_id, request: {"question": "q?"})
        monkeypatch.setattr(export, "MODERATOR_QUESTION_PILL_ENABLED", False)
        parked = self._keys(client.get("/api/projects/1/export"))
        monkeypatch.setattr(export, "MODERATOR_QUESTION_PILL_ENABLED", True)
        enabled = self._keys(client.get("/api/projects/1/export"))
        extra = enabled - parked
        assert extra and all("moderator-question" in k for k in extra)
        assert parked <= enabled

    def test_repeated_exports_are_stable_and_leave_no_state_behind(self, client: Any) -> None:
        sizes = {len(client.get("/api/projects/1/export").content) for _ in range(4)}
        assert len(sizes) == 1
