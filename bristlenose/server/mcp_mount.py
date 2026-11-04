"""The ``/mcp`` mount: the route, the browser explainer, the proxy-identity recorder, and the
holder that builds the endpoint on its first request.

Split from ``mcp_server`` (the tools) so that building the app does not import the ``mcp``
package. ``mcp_server`` imports the SDK at load, because ``ToolInputError`` has to subclass its
``ToolError`` for a refusal's message to reach the model, and that import is 275 to 280 ms
(measured 4 Nov 2026) that every serve start paid whether or not Agent Access was on. This
module imports nothing heavy; ``mcp_server`` is imported inside ``LazyMCP``'s build step.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import logging
import os
import re
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

#: Where the connect instructions live (permanent URL — see the website repo).
DOCS_URL = "https://bristlenose.app/docs/connect-an-agent.html"


# ---------------------------------------------------------------------------
# Project identity (light: /api/health needs it and must not load the SDK)
# ---------------------------------------------------------------------------

def _project_key(project: Any) -> str:
    """Stable, opaque identity for one project — the first field of a citation.

    ``project_id`` is a **slot**, not a name: the serve is single-project, so it
    is always 1, and *which* project that means changes with the window the
    researcher has open. Observed live 20 Aug 2026 — the same id returned "foo"
    and then "IKEA with uxfriends" inside one conversation.

    The name does not disambiguate either. A real sidebar holds "New Project",
    "New Project 2", "New Project 3" and "New Project3"; two of those echoing
    identical ``{id: 1, name: ...}`` payloads are indistinguishable.

    So: sha256 of the resolved input path. Stable across restarts, unique per
    project, and it leaks no filesystem path — §7 forbids paths reaching the
    agent, and a digest is not a path. Resolved first because ``/private/var``
    and ``/var`` spell the same folder two ways and would otherwise key one
    project twice (the same standardisation ``AgentActivity.samePath`` makes on
    the desktop side).

    Since 15 Oct 2026 a project that carries a study id (``projects.study_id``,
    from the output folder's marker) is keyed by that instead, so an agent
    keeps its project across a move or a rename, and a copy, which the app
    re-mints, is a different project (docs/design-project-identity.md §11).
    """
    study_id = getattr(project, "study_id", None)
    if study_id:
        return hashlib.sha256(f"study:{study_id}".encode()).hexdigest()[:8]
    raw = project.input_dir
    if not raw:
        # `os.path.realpath("")` returns the CWD, which mints a perfectly
        # well-formed key that is WRONG and that every project with an empty
        # input_dir collides on. An unidentifiable project must be visibly
        # unidentifiable — the caller omits `key` rather than shipping a lie.
        raise ValueError("project has no input_dir, so it has no stable key")
    real = os.path.realpath(raw)
    return hashlib.sha256(real.encode("utf-8")).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Browser-click explainer (naive GET from a terminal-linkified URL)
# ---------------------------------------------------------------------------

# Styled the status-page way (status_page.py precedent): the shipped theme
# CSS + bn-status classes, no bespoke styles. The stylesheet link 404s
# harmlessly on a project-less app; the page degrades to readable HTML.
_EXPLAINER_HTML = (
    "<!doctype html><html><head><meta charset=\"utf-8\">"
    "<meta name=\"color-scheme\" content=\"light dark\">"
    "<title>Bristlenose MCP endpoint</title>"
    "<link rel=\"stylesheet\" href=\"/report/assets/bristlenose-theme.css\">"
    "</head><body class=\"bn-status-page\"><main class=\"bn-status\">"
    "<h1 class=\"bn-status-short\">This is Bristlenose&rsquo;s MCP endpoint.</h1>"
    "<p class=\"bn-status-long\">It speaks to AI agents (Claude Code, Claude "
    "Desktop, ChatGPT, Codex), not to browsers.</p>"
    "<p class=\"bn-status-long\">Your report is at "
    "<a href=\"/report/\">/report/</a>. To connect an agent, copy the "
    "connection details from the terminal running "
    "<code>bristlenose serve</code> &mdash; the token is shown there, never "
    "here. How-to: <a href=\"" + DOCS_URL + "\">" + DOCS_URL + "</a></p>"
    "</main></body></html>"
)


class BrowserExplainerApp:
    """ASGI wrapper: browser-shaped GETs get a human page, agents pass through.

    MCP clients never GET with ``Accept: text/html`` (protocol GETs ask for
    ``text/event-stream``; everything substantive is POST), so content
    negotiation cleanly splits humans from agents. The page carries no
    project data and no token — same exemption class as ``/api/health``.
    """

    def __init__(self, inner: ASGIApp) -> None:
        self.inner = inner

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("method") == "GET":
            accept = ""
            for name, value in scope.get("headers", []):
                if name == b"accept":
                    accept = value.decode("latin-1", errors="replace")
                    break
            if "text/html" in accept and "text/event-stream" not in accept:
                body = _EXPLAINER_HTML.encode()
                await send({
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [
                        (b"content-type", b"text/html; charset=utf-8"),
                        (b"content-length", str(len(body)).encode()),
                        (b"cache-control", b"no-store"),
                    ],
                })
                await send({"type": "http.response.body", "body": body})
                return
        await self.inner(scope, receive, send)


class ProxyIdentityRecorder:
    """ASGI wrapper: record the extension proxy's self-reported build.

    The proxy has stamped ``X-Bristlenose-Proxy-Version`` on every call since
    it shipped, and nothing read it — so the host could report the version it
    *bundled* but never the one actually running. Those two diverge for the
    whole life of a ``.mcpb``: it has no auto-update, reinstall is the only
    delivery, and a reinstall that quietly re-lays a stale copy is
    indistinguishable from a working one at every surface the user can see.

    Recorded here rather than in ``_record_activity`` because that hook runs
    inside the tool implementation and never sees the request. A separate
    wrapper from ``BrowserExplainerApp`` for the ordinary reason: two
    concerns, two wrappers.

    Diagnostic only. Compatibility is decided by ``MCP_CONTRACT``, which is
    deliberately not a release version (see ``routes/health.py``) — this
    value must never become a gate, or it starts crying wolf on every patch.
    """

    #: A version grammar, not a character budget. "Printable ASCII, 64 chars"
    #: is comfortably a short imperative with a hostname — and this value is
    #: interpolated into a localised sentence in the pane that neighbours the
    #: Turn On/Off Agent Access controls. Real values are `0.26.0+854270a`
    #: and `2`, both of which this renders byte-identically, while a sentence
    #: becomes structurally unrepresentable. Excluding `<>&` falls out for
    #: free, which pays off the export-JSON scar here rather than at some
    #: future render site that inherits the string.
    _ALLOWED = re.compile(r"^[A-Za-z0-9.+_:-]+$")
    _MAX_LEN = 64

    def __init__(self, inner: ASGIApp, state: Any) -> None:
        self.inner = inner
        self.state = state

    @classmethod
    def _clean(cls, raw: bytes) -> str | None:
        text = raw.decode("latin-1", errors="replace").strip()
        # REJECT, never splice. Filtering characters out turns `9.9.9\tevil`
        # into `9.9.9evil` — neither what was sent nor an honest "unreadable",
        # just something that looks like a version. For a field whose whole
        # job is "is the proxy running the build I packed", a plausible wrong
        # answer is the worst outcome available; None says "can't tell", which
        # the host already renders correctly.
        if not text or len(text) > cls._MAX_LEN or not cls._ALLOWED.match(text):
            return None
        return text

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # POST ONLY, and that is load-bearing rather than tidy. `middleware.py`
        # deliberately exempts a browser-shaped GET (`Accept: text/html`) from
        # auth so a naive click gets the explainer page — and that request
        # reaches this wrapper. Without the method gate, any local process can
        # curl 64 chosen characters into a native label beside the Turn On/Off
        # Agent Access controls, with no bearer and no tool call, and can write
        # the `None` sentinel that means "no agent has called yet". Every real
        # proxy call is a POST (index.js), and POST has no auth exemption.
        if scope["type"] == "http" and scope.get("method") == "POST":
            headers = dict(scope.get("headers", []))
            if b"x-bristlenose-proxy-host" in headers:
                self._record_for_host(headers)
            else:
                if b"x-bristlenose-proxy-version" in headers:
                    self.state.mcp_proxy_version = self._clean(headers[b"x-bristlenose-proxy-version"])
                if b"x-bristlenose-proxy-contract" in headers:
                    self.state.mcp_proxy_contract = self._clean(headers[b"x-bristlenose-proxy-contract"])
        await self.inner(scope, receive, send)

    #: A host label is a word, not a sentence: "ChatGPT", "Claude".
    _HOST = re.compile(r"^[A-Za-z0-9._-]{1,32}$")
    #: A handful of hosts, never an unbounded map any local caller can grow.
    _MAX_HOSTS = 8

    def _record_for_host(self, headers: dict[bytes, bytes]) -> None:
        """The native helper names its host, so each host keeps its own build.

        One slot for every proxy meant the last caller won: a ChatGPT question
        would overwrite what the Claude tab compares against, and the Claude
        tab would offer an update it does not need (design-mcp-native-proxy
        §6.9 D8). The legacy slot stays the Node extension's, which sends no
        host. An unreadable host records nothing rather than landing in the
        legacy slot.
        """
        host = headers[b"x-bristlenose-proxy-host"].decode("latin-1", errors="replace").strip()
        if not self._HOST.match(host):
            return
        versions: dict[str, str | None] = self.state.mcp_proxy_versions
        if host not in versions and len(versions) >= self._MAX_HOSTS:
            return
        raw = headers.get(b"x-bristlenose-proxy-version")
        versions[host] = self._clean(raw) if raw is not None else None


class LazyMCP:
    """The ``/mcp`` endpoint, built on its first request rather than at startup.

    ``import mcp`` costs 275 to 280 ms (measured 4 Nov 2026) and every serve start paid it
    whether or not Agent Access was on. The mount, the route and ``health.mcp.mounted`` are
    unchanged; what moves is the import, the server's construction and the session manager's
    start, which now happen when an agent first calls. That first call pays them once.

    The session manager's ``run()`` is an anyio task group, so it is entered and left in ONE
    long-lived task (``_hold``); ``aclose`` stops that task, and the app's lifespan calls it on
    shutdown (``_compose_mcp_lifespan``).
    """

    def __init__(self, build: Callable[[], Any]) -> None:
        self._build = build
        self._lock = asyncio.Lock()
        self._http_app: Any = None
        self._task: asyncio.Task[None] | None = None
        self._stop: asyncio.Event | None = None
        self._closed = False

    async def _ensure(self) -> None:
        if self._http_app is not None:
            return
        async with self._lock:
            if self._http_app is not None:
                return
            if self._closed:
                raise RuntimeError("the MCP endpoint is shutting down")
            try:
                server, http_app = await asyncio.to_thread(self._build)
            except Exception:
                # Not cached: the next request tries again. A present-but-broken install
                # fails here, loudly, on every call, and not as "not installed".
                logger.exception("could not build the MCP endpoint")
                raise
            if self._closed:
                # shutdown began while the build ran in its thread: start nothing after it
                raise RuntimeError("the MCP endpoint is shutting down")
            stop = asyncio.Event()
            ready = asyncio.Event()

            async def _hold() -> None:
                async with server.session_manager.run():
                    ready.set()
                    await stop.wait()

            task = asyncio.create_task(_hold(), name="bristlenose-mcp-session-manager")
            waiter = asyncio.create_task(ready.wait())
            try:
                await asyncio.wait({task, waiter}, return_when=asyncio.FIRST_COMPLETED)
            except BaseException:
                # This call was cancelled while the manager started: nothing owns the task yet,
                # so stop it here or it would hold the session manager open until the loop dies.
                stop.set()
                waiter.cancel()
                task.cancel()
                raise
            if not ready.is_set():
                waiter.cancel()
                try:
                    task.result()
                finally:
                    logger.error("the MCP session manager stopped before it was ready")
                raise RuntimeError("the MCP session manager stopped before it was ready")
            self._stop, self._task, self._http_app = stop, task, http_app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        await self._ensure()
        await self._http_app(scope, receive, send)

    async def aclose(self) -> None:
        """Stop the session manager if it was ever started. Safe to call twice."""
        self._closed = True
        task, stop = self._task, self._stop
        self._task = self._stop = self._http_app = None
        if task is None or stop is None:
            return
        stop.set()
        try:
            await task
        except asyncio.CancelledError:
            pass


def mount_mcp_server(app: Any, session_factory: Callable[[], Any]) -> Any | None:
    """Mount ``/mcp`` on the FastAPI app; returns the endpoint handle, or None.

    "Installed" is decided by ``find_spec``, which does not import the package (the import is
    275 ms and is done on the first request, see ``LazyMCP``). Only a package that is ABSENT
    is "not installed"; a present-but-broken install fails loudly on the first request, in the
    log and as a 500, never as "not installed". The caller composes the shutdown (LAST, after
    the event watcher's assignment) and sets ``app.state.mcp_mounted``.
    """
    try:
        installed = importlib.util.find_spec("mcp") is not None
    except (ImportError, ValueError):
        installed = False
    if not installed:
        # info, not warning: the terminal handler shows WARNING+, and this is
        # the expected state for every install without the optional extra —
        # the CLI's "MCP: unavailable" line is the user-facing signal.
        logger.info(
            "mcp extra not installed — /mcp/ not mounted "
            '(pip install "bristlenose[mcp]")'
        )
        return None

    def _last_run() -> dict[str, Any] | None:
        # The newest run's outcome — what an agent needs to hear ("the latest
        # analysis failed"). Read from the condition: ``app.state.last_run`` is
        # the data version only and would hide a failed or running re-run.
        from bristlenose.output_paths import project_output_dir
        from bristlenose.server.app import current_condition

        project_dir = getattr(app.state, "project_dir", None)
        if project_dir is None:
            return (getattr(app.state, "last_run", None) or {}).get(1)
        latest = current_condition(app, project_output_dir(project_dir)).latest
        if latest is None:
            return None
        return {"run_id": latest.run_id, "outcome": latest.state.value,
                "completed_at": latest.ended_at}

    # Monotonic, not wall-clock: a wall clock could fake or erase activity
    # on an NTP step. Trade-off, documented in health.py: mach_absolute_time
    # pauses across sleep, so elapsed time under-counts by the sleep — fine
    # for health's 2-minute freshness bool, wrong for anything longer.
    # Scope gate. Open for a CLI serve — there are no windows, so there is no
    # roster to derive scope from and the researcher's own `serve` invocation
    # IS the grant. Closed for a desktop-hosted serve, which has an owner:
    # `ServeFleet.syncHandshake` derives the readable set from the window
    # roster and pushes it, so the host decides, not the default.
    #
    # This used to be an unconditional True with a CLI-shaped comment. The
    # desktop pane's claim is that a project absent from the register is not
    # shared — and with a fail-open default that was true by *convergence*
    # (the host's first PUT closes it) rather than by construction. A study
    # whose Agent Access was turned off would answer any caller holding its
    # durable Keychain bearer for one localhost round-trip after each spawn.
    # One round trip is small; "true by construction" is the sentence that
    # survives a hostile reading, and it costs one line.
    app.state.agent_readable = (
        os.environ.get("_BRISTLENOSE_HOSTED_BY_DESKTOP") != "1"
    )
    app.state.mcp_last_tool_call = None
    # The proxy's self-reported build, filled by ProxyIdentityRecorder on the
    # first call THROUGH THE EXTENSION. None is not "out of date" — but nor is
    # it simply "nobody has called": any MCP client that isn't our .mcpb sends
    # no header at all, and the Generic MCP tab is a supported path. So None
    # means "no EXTENSION build has identified itself", which `calls` in the
    # same payload disambiguates (calls > 0 and version None = a non-extension
    # agent). Don't let a future gate read more into it than that.
    app.state.mcp_proxy_version = None
    app.state.mcp_proxy_contract = None
    # Per host, for proxies that name theirs (the native helper). See
    # ProxyIdentityRecorder._record_for_host.
    app.state.mcp_proxy_versions = {}
    # Monotonic call count for the sidebar antenna's activity animation. A
    # COUNTER, not a timestamp: the host animates on any increment, and an
    # integer is immune to the sleep-pause skew described above (a lid close
    # cannot make the count go backwards or stall). Read via the authed
    # /api/agent-activity — never /api/health, which is auth-exempt and
    # deliberately publishes only the coarse `active` bool.
    app.state.mcp_tool_calls = 0

    def _record_activity() -> None:
        app.state.mcp_last_tool_call = time.monotonic()
        app.state.mcp_tool_calls = int(getattr(app.state, "mcp_tool_calls", 0) or 0) + 1

    def _readable() -> bool:
        # Defaults to False: a missing attribute means the mount did not
        # finish, which is not a reason to answer questions about a study.
        return bool(getattr(app.state, "agent_readable", False))

    from bristlenose.server.grounding import delivery_coverage

    def _build() -> tuple[Any, Any]:
        # Imported here, on the first request and off the event loop: this module imports the
        # SDK at load (ToolInputError subclasses its ToolError), which is the 275 ms.
        from bristlenose.server.mcp_server import create_mcp_server

        server = create_mcp_server(
            session_factory, _last_run, _record_activity, _readable,
            coverage=lambda: delivery_coverage(app.state),
        )
        http_app = server.streamable_http_app(
            streamable_http_path="/",
            json_response=True,
            stateless_http=True,
        )
        return server, http_app

    lazy = LazyMCP(_build)
    app.mount("/mcp", ProxyIdentityRecorder(BrowserExplainerApp(lazy), app.state))
    return lazy
