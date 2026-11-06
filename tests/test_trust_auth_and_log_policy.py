"""Trust gates: every API route refuses a missing bearer, and no log call carries
quote text or speaker labels.

Two sweeps, both derived from the running thing rather than a hand list:

1. **401 sweep.** Every (method, path) in ``create_app().openapi()`` that is not
   in a pinned literal set of deliberately ungated paths is requested with no
   ``Authorization`` header and no cookie, and must get the middleware's fixed
   401 body. The exempt prefixes and the ungated path set are pinned as literals
   here, so widening either (a new ``_AUTH_EXEMPT_PREFIXES`` entry, a new
   non-``/api`` route) fails this file until somebody edits the pin on purpose.
   Model: ``tests/test_serve_export_coverage.py``.

2. **Logger scan.** ``bristlenose/logging.py`` states the PII policy: never log
   transcript content (quote text, segment text) and log identifiers, not names.
   An AST scan finds every ``log*.<level>(...)`` call whose arguments reference a
   quote-text or speaker-label attribute/name. Violations that already exist are
   listed in ``_KNOWN_VIOLATIONS`` (empty now).
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import bristlenose
import bristlenose.logging as bn_logging
from bristlenose.server.app import create_app
from bristlenose.server.middleware import _AUTH_EXEMPT_PREFIXES, _AUTH_REQUIRED_PREFIXES

_REPO = Path(__file__).parents[1]
_FIXTURE_DIR = _REPO / "tests" / "fixtures" / "smoke-test" / "input"
_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
_UNAUTHORIZED = {"detail": "Unauthorized"}

# --- pinned literals: change these deliberately, in a commit that says why ---

_PINNED_EXEMPT_PREFIXES: tuple[str, ...] = ("/api/health", "/api/docs", "/openapi.json")
_PINNED_REQUIRED_PREFIXES: tuple[str, ...] = ("/api/", "/mcp")
# OpenAPI paths the bearer gate does not cover (exempt prefix, or outside /api).
# Always mounted:
_PINNED_UNGATED_ALWAYS: frozenset[str] = frozenset({
    "/api/health",
    "/media/{path}",
    "/report",
    "/report/assets/bristlenose-theme.css",
    "/report/{path}",
})
# Mounted only when the frontend is built (absent in CI's pytest job and in a
# `git archive` tree, since bristlenose/server/static is gitignored):
_PINNED_UNGATED_WITH_FRONTEND: frozenset[str] = frozenset({
    "/static/{path}",
    "/assets/{path}",
    "/report/assets/bristlenose-player.html",
    "/report/assets/bristlenose-logo.png",
    "/report/assets/bristlenose-logo-dark.png",
})
_PINNED_UNGATED_PATHS = _PINNED_UNGATED_ALWAYS | _PINNED_UNGATED_WITH_FRONTEND

_ENV_TO_ISOLATE = (
    "_BRISTLENOSE_AUTH_TOKEN",
    "_BRISTLENOSE_MCP_TOKEN",
    "_BRISTLENOSE_HOSTED_BY_DESKTOP",
)


def test_imports_this_tree() -> None:
    assert Path(bristlenose.__file__).is_relative_to(Path(__file__).parents[1])


def _build_app():
    """create_app with env isolated and no log file written into the fixture tree."""
    real_setup = bn_logging.setup_logging

    def _setup_logging(*, output_dir=None, verbose=False):
        real_setup(output_dir=None, verbose=verbose)

    with pytest.MonkeyPatch.context() as mp:
        for name in _ENV_TO_ISOLATE:
            mp.delenv(name, raising=False)
        mp.setattr(bn_logging, "setup_logging", _setup_logging)
        app = create_app(project_dir=_FIXTURE_DIR, dev=False, db_url="sqlite://")
        # create_app exports the token to os.environ; the context restores it.
        assert os.environ.get("_BRISTLENOSE_AUTH_TOKEN") == app.state.auth_token
    return app


def _surface(app) -> list[tuple[str, str]]:
    spec = app.openapi()
    return sorted(
        (method.upper(), path)
        for path, item in spec["paths"].items()
        for method in item
        if method in _HTTP_METHODS
    )


def _is_ungated(path: str) -> bool:
    return (not any(path.startswith(p) for p in _AUTH_REQUIRED_PREFIXES)) or any(
        path.startswith(p) for p in _AUTH_EXEMPT_PREFIXES
    )


def _concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "x1", path)


# Collected once at import: parametrisation needs the live surface by name.
def _isolated_app():
    """Build the app under the conftest isolation, which a module-level build runs BEFORE."""
    import tempfile
    from types import SimpleNamespace

    from tests.conftest import _isolate_machine_config

    base = Path(tempfile.mkdtemp(prefix="bn-trust-")).resolve()
    factory = SimpleNamespace(
        getbasetemp=lambda: base,
        mktemp=lambda name, numbered=True: Path(tempfile.mkdtemp(prefix=name, dir=base)),
    )
    with pytest.MonkeyPatch.context() as mp:
        _isolate_machine_config(mp, factory)
        return _build_app()


_SURFACE = _surface(_isolated_app())
_GATED = [(m, p) for m, p in _SURFACE if p not in _PINNED_UNGATED_PATHS]


@pytest.fixture(scope="module")
def bare_client():
    app = _isolated_app()
    assert app.state.auth_token
    return app, TestClient(app, base_url="http://127.0.0.1")


def test_exempt_prefixes_equal_pinned_literal() -> None:
    assert tuple(_AUTH_EXEMPT_PREFIXES) == _PINNED_EXEMPT_PREFIXES
    assert tuple(_AUTH_REQUIRED_PREFIXES) == _PINNED_REQUIRED_PREFIXES


def test_ungated_paths_equal_pinned_literal() -> None:
    ungated = {p for _, p in _SURFACE if _is_ungated(p)}
    assert ungated <= _PINNED_UNGATED_PATHS, (
        f"new ungated path(s): {sorted(ungated - _PINNED_UNGATED_PATHS)}"
    )
    assert _PINNED_UNGATED_ALWAYS <= ungated, (
        f"pinned ungated path(s) gone: {sorted(_PINNED_UNGATED_ALWAYS - ungated)}"
    )


def test_sweep_is_not_empty() -> None:
    assert len(_GATED) > 50
    assert ("GET", "/api/projects/{project_id}/quotes") in _GATED


@pytest.mark.parametrize(("method", "path"), _GATED, ids=[f"{m} {p}" for m, p in _GATED])
def test_route_refuses_missing_bearer(bare_client, method: str, path: str) -> None:
    app, client = bare_client
    assert any(r == (method, path) for r in _surface(app))
    client.cookies.clear()
    res = client.request(method, _concrete(path))
    assert res.status_code == 401, f"{method} {path} -> {res.status_code}"
    assert res.json() == _UNAUTHORIZED


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_mcp_mount_refuses_missing_bearer(bare_client, method: str) -> None:
    _, client = bare_client
    res = client.request(method, "/mcp/", headers={"accept": "application/json"})
    assert res.status_code == 401
    assert res.json() == _UNAUTHORIZED


def test_wrong_bearer_refused_and_right_one_passes(bare_client) -> None:
    app, client = bare_client
    url = "/api/projects/1/quotes"
    wrong = client.get(url, headers={"authorization": "Bearer not-a-real-token-1"})
    assert wrong.status_code == 401
    right = client.get(url, headers={"authorization": f"Bearer {app.state.auth_token}"})
    assert right.status_code != 401


# --------------------------------------------------------------------------
# Logger scan
# --------------------------------------------------------------------------

_LEVELS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}
# Quote / segment text and speaker labels (models.py: ExtractedQuote.text,
# TranscriptSegment.text / speaker_label, PersonComputed.full_name / short_name).
_FORBIDDEN = frozenset({
    "text",
    "quote_text",
    "segment_text",
    "verbatim",
    "researcher_context",
    "speaker_label",
    "speaker_name",
    "full_name",
    "short_name",
})

# Existing violations, keyed by file and the offending expression, not by line number. Empty
# since 6 Nov 2026 (the two found when this gate was written were fixed); a new entry needs a
# reason and an owner.
_KNOWN_VIOLATIONS: frozenset[tuple[str, str]] = frozenset()


def _is_logger_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _LEVELS
        and isinstance(node.func.value, ast.Name)
        and re.search(r"log", node.func.value.id, re.I) is not None
    )


def _violations_in(source: str) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not _is_logger_call(node):
            continue
        assert isinstance(node, ast.Call)
        args = [*node.args, *(k.value for k in node.keywords if k.arg != "exc_info")]
        for arg in args:
            for sub in ast.walk(arg):
                if isinstance(sub, ast.Attribute) and sub.attr in _FORBIDDEN:
                    found.add(ast.unparse(sub))
                elif isinstance(sub, ast.Name) and sub.id in _FORBIDDEN:
                    found.add(sub.id)
    return found


def _scan_package() -> set[tuple[str, str]]:
    pkg = Path(bristlenose.__file__).parent
    out: set[tuple[str, str]] = set()
    for f in sorted(pkg.rglob("*.py")):
        rel = f.relative_to(pkg.parent).as_posix()
        for expr in _violations_in(f.read_text(encoding="utf-8")):
            out.add((rel, expr))
    return out


@pytest.mark.parametrize(
    "snippet",
    [
        "logger.info('q %s', quote.text)",
        "log.debug(f'speaker {seg.speaker_label}')",
        "logger.warning('%s', p.full_name[:5])",
        "_log.error('x %s' % speaker_label)",
    ],
)
def test_scanner_catches_synthetic_violation(snippet: str) -> None:
    assert _violations_in(snippet)


@pytest.mark.parametrize(
    "snippet",
    [
        "logger.info('q %s', quote.quote_id)",
        "logger.debug('seg %s', seg.speaker_code)",
        "logger.exception('boom', exc_info=err.text)",
    ],
)
def test_scanner_allows_identifiers(snippet: str) -> None:
    assert not _violations_in(snippet)


def test_no_new_log_calls_carry_quote_text_or_speaker_labels() -> None:
    new = _scan_package() - _KNOWN_VIOLATIONS
    assert not new, (
        "log call(s) interpolate quote text or speaker labels, which the policy in "
        f"bristlenose/logging.py forbids: {sorted(new)}"
    )
