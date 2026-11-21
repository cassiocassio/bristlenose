#!/usr/bin/env python3
"""check-provider-links.py: the provider-links register, swept and (with --live) fetched.

The links we send people to (a provider's key page, billing page, pricing page) and the
claims that rest on a provider's page (a US$5 minimum, a free-tier data policy) are
declared once in ``bristlenose/data/provider-links.json``. Every file that carries a
copy is listed there as a mirror, so changing one link points you to every other place
that needs the same change. ``tests/test_provider_links.py`` is the offline gate;
this script is the live half:

    scripts/check-provider-links.py                 # offline: sweep + mirrors (what the test runs)
    scripts/check-provider-links.py --live          # also fetch every URL
    scripts/check-provider-links.py --live --provider claude
    scripts/check-provider-links.py --list          # every URL with its mirror files

``--live`` fetches each URL with a browser User-Agent, follows redirects by hand and
prints the chain. A permanent move, a changed final path, a 4xx or a 5xx is a finding,
and the files to update are printed under it. A sign-in redirect is expected for pages
behind a login (marked ``login`` in the register) and is not a finding. A 403 from a
bot block is reported as "check in a browser", never as broken: some portals refuse
scripts. No network happens outside ``--live``, and the test never asks for it.

Exit 0 = clean, 1 = a finding, 2 = a broken register. Stdlib only.
"""

from __future__ import annotations

import argparse
import functools
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent.parent
REGISTER = ROOT / "bristlenose" / "data" / "provider-links.json"

# What the sweep reads: tracked source the user can see, not history. Markdown under
# these directories is developer notes and is skipped; the files named in SWEEP_FILES
# are user-facing docs and are read.
SWEEP_DIRS = ("bristlenose", "desktop/Bristlenose/Bristlenose", "frontend/src")
SWEEP_FILES = ("README.md", "INSTALL.md", "DEVELOPMENT.md", ".env.example")
SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".icns", ".pdf", ".ttf", ".woff", ".woff2", ".svg", ".mp4",
    ".xcprivacy", ".car", ".bin", ".gz", ".zip", ".md", ".pyc", ".txt",
}
WEBSITE_PREFIX = "website:"
WEBSITE_DOCS = "docs-src"

_PROVIDER_HOSTS = (
    r"anthropic\.com|claude\.com|claude\.ai|openai\.com|chatgpt\.com|google\.dev|ai\.google|"
    r"aistudio\.google\.com|cloud\.google\.com|googleapis\.com|azure\.com|azure\.net|"
    r"microsoft\.com|ollama\.com|mistral\.ai|deepseek\.com|openrouter\.ai|zoom\.us|zoom\.com|"
    r"miro\.com"
)
URL_RE = re.compile(
    r"(?:https?://)?(?:[A-Za-z0-9-]+\.)*(?:" + _PROVIDER_HOSTS + r")(?:/[^\s\"'`)<>\\,;\[\]}]*)?",
    re.IGNORECASE,
)


def normalise(url: str) -> str:
    """Scheme off, host lowercased, no www, no trailing slash or sentence punctuation."""
    u = re.sub(r"^https?://", "", url.strip()).rstrip(".:;,)")
    host, sep, path = u.partition("/")
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return (host + sep + path).rstrip("/")


def load_register(path: Path = REGISTER) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def all_links(reg: dict) -> list[dict]:
    """Every link, with its provider key attached."""
    out = []
    for key, prov in reg["providers"].items():
        for link in prov["links"]:
            out.append({**link, "provider": key})
    return out


def website_root(env: dict[str, str] | None = None) -> Path | None:
    import os

    e = os.environ if env is None else env
    p = Path(e.get("BN_WEBSITE_REPO", str(Path.home() / "Code" / "bristlenose-website")))
    return p if (p / WEBSITE_DOCS).is_dir() else None


def resolve(spec: str, website: Path | None) -> list[Path]:
    """A mirror's file spec: a path or glob from the repo root, or ``website:docs-src/x.md``."""
    if spec.startswith(WEBSITE_PREFIX):
        if website is None:
            return []
        return sorted(website.glob(spec[len(WEBSITE_PREFIX):]))
    return sorted(ROOT.glob(spec))


def label(path: Path, website: Path | None) -> str:
    if website is not None and website in path.parents:
        return WEBSITE_PREFIX + str(path.relative_to(website))
    return str(path.relative_to(ROOT))


@functools.lru_cache(maxsize=4)
def swept_files(website: Path | None) -> list[Path]:
    import subprocess

    names = subprocess.run(
        ["git", "ls-files", *SWEEP_DIRS, *SWEEP_FILES],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    files = [ROOT / n for n in names if Path(n).suffix.lower() not in SKIP_SUFFIXES
             or n in SWEEP_FILES]
    files = [f for f in files if f != REGISTER]
    if website is not None:
        files += sorted((website / WEBSITE_DOCS).glob("*.md"))
    return [f for f in files if f.is_file()]


@functools.lru_cache(maxsize=4)
def sweep(website: Path | None) -> list[tuple[str, int, str]]:
    """Every provider-domain occurrence as (file label, line, normalised URL)."""
    found = []
    for f in swept_files(website):
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for m in URL_RE.finditer(line):
                found.append((label(f, website), n, normalise(m.group(0))))
    return found


def is_ignored(url: str, reg: dict) -> bool:
    return any(re.search(p, url) for p in reg["ignore_patterns"])


def known_hosts(reg: dict) -> set[str]:
    return {normalise(link["url"]).partition("/")[0] for link in all_links(reg)}


def retired_hit(url: str, reg: dict) -> dict | None:
    for r in reg["retired"]:
        if re.search(r["pattern"], url):
            return r
    return None


@functools.lru_cache(maxsize=512)
def _text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


@functools.lru_cache(maxsize=512)
def _urls(p: Path) -> frozenset[str]:
    return frozenset(normalise(x.group(0)) for x in URL_RE.finditer(_text(p)))


def check(website: Path | None) -> list[str]:
    """The offline gate. Returns findings; empty means clean."""
    reg = load_register()
    problems: list[str] = []
    links = all_links(reg)
    by_norm = {normalise(link["url"]): link for link in links}
    mirrors: dict[str, set[str]] = {}

    # 1. every mirror file exists (skipped when it lives in an absent website repo) and
    #    contains its URL, or its `contains` text for bare-host copies.
    for link in links:
        norm = normalise(link["url"])
        mirrors[norm] = set()
        for m in link["mirrors"]:
            spec, needle = (m, None) if isinstance(m, str) else (m["file"], m.get("contains"))
            skip = () if isinstance(m, str) else tuple(m.get("except", ()))
            paths = [p for p in resolve(spec, website) if not any(x in str(p) for x in skip)]
            if not paths:
                if spec.startswith(WEBSITE_PREFIX) and website is None:
                    continue
                problems.append(f"{link['id']}: mirror {spec} matches no file")
                continue
            for p in paths:
                mirrors[norm].add(label(p, website))
                text = _text(p)
                if needle is not None:
                    ok = needle in text
                else:
                    seen = _urls(p)
                    # A link that is only a host ("platform.claude.com") is carried by any
                    # mention of that host, with or without a path.
                    ok = norm in seen or ("/" not in norm and
                                          any(u.partition("/")[0] == norm for u in seen))
                if not ok:
                    problems.append(
                        f"{link['id']}: {label(p, website)} no longer carries "
                        f"{needle or link['url']}; update the register or the file")

    # 2. every provider URL in the tree is registered, ignored, a bare known host, or
    #    retired (retired is always a failure). A full URL must also sit in a listed mirror.
    hosts = known_hosts(reg)
    for where, n, url in sweep(website):
        r = retired_hit(url, reg)
        if r:
            problems.append(f"{where}:{n}: {url} is retired; {r['use']}")
            continue
        if is_ignored(url, reg):
            continue
        if "/" not in url:
            if url not in hosts:
                problems.append(f"{where}:{n}: host {url} is not in the provider-links register")
            continue
        if url not in by_norm:
            problems.append(f"{where}:{n}: {url} is not in the provider-links register")
        elif where not in mirrors[url] and not _bare_mirror(by_norm[url], where):
            problems.append(
                f"{where}:{n}: carries {url}, but {where} is not one of its mirrors "
                f"({by_norm[url]['id']})")

    # 3. claims: every listed file still says the claim.
    for claim in reg["claims"]:
        for m in claim["mirrors"]:
            paths = resolve(m["file"], website)
            if not paths:
                if not (m["file"].startswith(WEBSITE_PREFIX) and website is None):
                    problems.append(f"claim {claim['id']}: {m['file']} matches no file")
                continue
            for p in paths:
                if m["contains"] not in _text(p):
                    problems.append(
                        f"claim {claim['id']}: {label(p, website)} no longer says "
                        f"{m['contains']!r}; update the register or the file")
    return problems


def _bare_mirror(link: dict, where: str) -> bool:
    """A mirror entry with a ``contains`` needle covers its whole file set for sweep purposes."""
    return any(isinstance(m, dict) and m["file"] == where for m in link["mirrors"])


# ---- live ------------------------------------------------------------------------


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # type: ignore[no-untyped-def]
        return None


UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")


def fetch_chain(url: str, hops: int = 6, timeout: int = 20) -> list[tuple[str, int | str]]:
    """Follow redirects by hand. Returns [(url, status), ...]."""
    opener = urllib.request.build_opener(_NoRedirect)
    chain: list[tuple[str, int | str]] = []
    cur = url
    for _ in range(hops):
        status: int | str = "error"
        location = None
        for method in ("HEAD", "GET"):
            req = urllib.request.Request(cur, method=method, headers={"User-Agent": UA})
            try:
                with opener.open(req, timeout=timeout) as r:
                    status = r.status
            except urllib.error.HTTPError as e:
                status = e.code
                location = e.headers.get("Location")
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                status = f"error: {getattr(e, 'reason', e)}"
            if status != 405:
                break
        chain.append((cur, status))
        if isinstance(status, int) and 300 <= status < 400 and location:
            cur = urljoin(cur, location)
            continue
        break
    return chain


def judge(link: dict, chain: list[tuple[str, int | str]]) -> tuple[str, str]:
    """(verdict, detail). Verdicts: ok, moved, login, blocked, broken."""
    first, last = chain[0], chain[-1]
    final_url, final_status = last
    if any(s in (301, 308) for _, s in chain[:-1]):
        permanent = True
    else:
        permanent = False
    if "accounts.google.com" in final_url or "/login" in final_url or "/signin" in final_url:
        if link.get("login"):
            return "login", f"sign-in redirect, as expected ({final_status})"
    if final_status == 403:
        return "blocked", "403: some portals refuse scripts; check in a browser"
    if not isinstance(final_status, int) or final_status >= 400:
        return "broken", f"{final_status} at {final_url}"
    if normalise(final_url) != normalise(first[0]):
        kind = "permanent" if permanent else "temporary"
        return "moved", f"{kind} redirect to {final_url}"
    return "ok", str(final_status)


def live(only: str | None, website: Path | None) -> int:
    reg = load_register()
    bad = 0
    for link in all_links(reg):
        if only and link["provider"] != only:
            continue
        chain = fetch_chain(link["url"])
        verdict, detail = judge(link, chain)
        print(f"{verdict.upper():8} {link['id']:28} {link['url']}\n         {detail}")
        if verdict in ("moved", "broken"):
            bad += 1
            for m in link["mirrors"]:
                print(f"           update: {m if isinstance(m, str) else m['file']}")
    for claim in reg["claims"]:
        if only and claim.get("provider") != only:
            continue
        print(f"CLAIM    {claim['id']:28} verified {claim['verified']}: {claim['source']}")
    print(f"\n{bad} to look at" if bad else "\nnothing moved or broken")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--live", action="store_true", help="fetch every URL (needs the network)")
    ap.add_argument("--provider", help="with --live: only this provider key")
    ap.add_argument("--list", action="store_true", help="print every URL with its mirrors")
    args = ap.parse_args(argv)
    try:
        reg = load_register()
    except (OSError, ValueError) as exc:
        print(f"check-provider-links: cannot read {REGISTER}: {exc}", file=sys.stderr)
        return 2
    web = website_root()
    if args.list:
        for link in all_links(reg):
            print(f"{link['id']}  {link['url']}  (verified {link['verified']})")
            for m in link["mirrors"]:
                print(f"    {m if isinstance(m, str) else m['file']}")
        return 0
    problems = check(web)
    for p in problems:
        print(p)
    if web is None:
        print("(website repo not found: its mirrors were skipped; set BN_WEBSITE_REPO)")
    code = 1 if problems else 0
    if args.live:
        code = max(code, live(args.provider, web))
    return code


if __name__ == "__main__":
    sys.exit(main())
