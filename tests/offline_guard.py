"""A machine with the Wi-Fi off, for tests: every non-loopback connection is refused.

``install(log)`` replaces the ``socket`` module's resolvers (``getaddrinfo``,
``gethostbyname``, ``gethostbyname_ex``, ``gethostbyaddr``) and the socket methods that
reach an address (``connect``, ``connect_ex``, ``sendto``, and ``sendmsg`` with an address
where the platform has it: Windows does not).
A name that is not loopback fails the way macOS fails it with no network (``gaierror``
"nodename nor servname provided"), and a non-loopback address fails with ``ENETUNREACH``.
Loopback (``127.0.0.0/8``, ``::1``, ``localhost``) and Unix sockets pass, so the serve can
bind and be asked. Every refusal is appended to ``log``, one line each, so a test can say
"nothing even tried" rather than only "it survived".

What it covers is what goes through the ``socket`` module in THIS process: urllib, httpx
(sync and asyncio), the provider SDKs, and the standard asyncio loop's ``getaddrinfo`` and
``sock_connect``. It does not see:

- a C library that opens its own sockets (uvloop's resolver, libcurl, Windows' proactor
  loop, which connects through ``ConnectEx``); ``serve`` runs uvicorn inside
  ``asyncio.run``, the standard selector loop on macOS and Linux;
- a child process (the serve shells out to ``security``, which stays on the machine);
- a request sent to a loopback proxy or gateway that forwards it on, so a test strips
  the proxy and ``*_BASE_URL`` variables (``OFFLINE_STRIP``) before it installs this.

It models Wi-Fi off, where a lookup fails at once. A network that accepts a connection
and then says nothing (a captive portal, a dead route) is a different test.

Run as a module (``python -c "from tests.offline_guard import main; main()" serve ...``),
it installs the guard before anything else is imported and then runs the CLI, the same
launch the Mac app makes.
"""

from __future__ import annotations

import errno
import ipaddress
import os
import socket
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

_LOOPBACK_NAMES = frozenset({"localhost", "localhost.", "ip6-localhost"})

#: Variables that send a request through a loopback proxy or gateway the guard would
#: allow: a test strips every one before it installs the guard.
OFFLINE_STRIP = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
    "http_proxy", "https_proxy", "all_proxy", "no_proxy",
)


def strip_proxies(environ: dict[str, str] | os._Environ[str]) -> list[str]:
    """The names in ``environ`` that would route around the guard: proxies and base URLs."""
    return [k for k in environ if k in OFFLINE_STRIP or k.upper().endswith("_BASE_URL")]


def _is_loopback(host: object) -> bool:
    if host is None:
        return True  # getaddrinfo(None, port): the wildcard / loopback for a bind
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    text = str(host).strip().lower().strip("[]")
    if text in _LOOPBACK_NAMES or text == "":
        return True
    try:
        addr = ipaddress.ip_address(text.split("%", 1)[0])
    except ValueError:
        return False  # a name, and not one of the loopback names
    mapped = getattr(addr, "ipv4_mapped", None)
    return bool(addr.is_loopback or (mapped is not None and mapped.is_loopback))


def install(
    log: Path, set_attr: Callable[[Any, str, Any], None] = setattr
) -> None:
    """Refuse every non-loopback resolution and send from here on, logging each one.

    ``set_attr`` is ``monkeypatch.setattr`` in-process, so pytest restores every name.
    """
    real = {
        name: getattr(socket, name)
        for name in ("getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr")
    }
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_sendto = socket.socket.sendto
    # POSIX only: Windows' socket has no sendmsg, so there is nothing to guard there.
    real_sendmsg = getattr(socket.socket, "sendmsg", None)

    def note(what: str) -> None:
        with log.open("a", encoding="utf-8") as fh:
            fh.write(what + "\n")

    def resolver(name: str) -> Callable[..., Any]:
        def resolve(host: Any, *args: Any, **kwargs: Any) -> Any:
            if not _is_loopback(host):
                note(f"{name} {host!r}")
                raise socket.gaierror(
                    socket.EAI_NONAME, "nodename nor servname provided, or not known"
                )
            return real[name](host, *args, **kwargs)

        return resolve

    def _outbound(sock: socket.socket, address: Any) -> bool:
        if sock.family not in (socket.AF_INET, socket.AF_INET6):
            return False  # AF_UNIX and friends never leave the machine
        return not _is_loopback(address[0] if isinstance(address, tuple) else address)

    def refuse(what: str, address: Any) -> OSError:
        note(f"{what} {address!r}")
        return OSError(errno.ENETUNREACH, "Network is unreachable")

    def connect(self: socket.socket, address: Any) -> None:
        if _outbound(self, address):
            raise refuse("connect", address)
        real_connect(self, address)

    def connect_ex(self: socket.socket, address: Any) -> int:
        if _outbound(self, address):
            refuse("connect_ex", address)
            return errno.ENETUNREACH
        return real_connect_ex(self, address)

    def sendto(self: socket.socket, data: Any, *rest: Any) -> int:
        if rest and _outbound(self, rest[-1]):
            raise refuse("sendto", rest[-1])
        return real_sendto(self, data, *rest)

    def sendmsg(self: socket.socket, buffers: Any, *rest: Any) -> int:
        if len(rest) >= 3 and rest[2] is not None and _outbound(self, rest[2]):
            raise refuse("sendmsg", rest[2])
        assert real_sendmsg is not None
        return int(real_sendmsg(self, buffers, *rest))

    for name in real:
        set_attr(socket, name, resolver(name))
    set_attr(socket.socket, "connect", connect)
    set_attr(socket.socket, "connect_ex", connect_ex)
    set_attr(socket.socket, "sendto", sendto)
    if real_sendmsg is not None:
        set_attr(socket.socket, "sendmsg", sendmsg)


def main() -> None:
    """``argv``: ``<log> <static-dir> <mode> args...``.

    ``mode`` is ``serve``, ``cli <command> ...`` or ``probe <url>``.
    """
    log, static_dir, mode, *rest = sys.argv[1:]
    for name in strip_proxies(os.environ):
        del os.environ[name]
    install(Path(log))
    if mode == "probe":
        # The guard's own canary: an outbound fetch must fail, fast, and be logged.
        import urllib.request

        try:
            urllib.request.urlopen(rest[0], timeout=5)
        except OSError as exc:
            print(f"refused: {type(exc).__name__}", flush=True)
            return
        print("REACHED", flush=True)
        return
    if mode == "serve":
        # The bundle's SPA is not built in CI (and needn't be here): serve the source
        # index.html, which carries the same <head> the build does.
        import bristlenose.server.app as server_app

        server_app._STATIC_DIR = Path(static_dir)
    # "serve": the Mac app's launch; "cli": any other command (the first Analyse is "run").
    sys.argv = ["bristlenose", *(["serve"] if mode == "serve" else []), *rest]
    from bristlenose.cli import app

    app()


if __name__ == "__main__":
    main()
