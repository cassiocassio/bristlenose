#!/usr/bin/env python3
"""Build a session digest page from a digest JSON file.

    build.py digest.json out.html [--root DIR] [--fragment]

Stdlib only. Does the mechanical work so the model does not: verifies every ref in one
pass, embeds screenshots (macOS `sips`), escapes the JSON for a <script> block, and
prepends the document header for a file on disk. `--fragment` skips the header, for
publishing as an Artifact (the host wraps the page itself).
"""

import base64
import html
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OPEN = '<script type="application/json" id="digest">'
HEADER = (
    '<!doctype html>\n<html lang="en">\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
)
MAX_SHOTS = 24
BUDGET = 3_000_000  # bytes of embedded base64
MAX_PAGE = 12_000_000


def run(*cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return r.returncode


def verify_ref(ref, root):
    """Set ref["v"] to ok or gone. Never leave a dead ref looking live."""
    f, sha = ref.get("file"), ref.get("sha")
    if sha and f:
        ok = run("git", "cat-file", "-e", f"{sha}:{f}", cwd=root) == 0
    elif sha:
        ok = run("git", "cat-file", "-e", sha, cwd=root) == 0
    elif f:
        ok = os.path.exists(os.path.join(root, f))
        if ok and ref.get("lines"):
            try:
                with open(os.path.join(root, f), encoding="utf-8", errors="replace") as fh:
                    n = len(fh.read().splitlines())
                ok = int(str(ref["lines"]).split("-")[-1]) <= n
            except (OSError, ValueError):
                pass
    else:
        return None
    ref["v"] = "ok" if ok else "gone"
    return ok


def walk(obj, root, stats):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "ref" and isinstance(v, dict):
                ok = verify_ref(v, root)
                if ok is not None:
                    stats["refs_ok" if ok else "refs_gone"] += 1
            else:
                walk(v, root, stats)
    elif isinstance(obj, list):
        for v in obj:
            walk(v, root, stats)


def embed_shots(data, root, stats):
    used = 0
    for i, s in enumerate(data.get("shots") or []):
        p = s.get("path") or ""
        full = p if os.path.isabs(p) else os.path.join(root, p)
        if s.get("src") or not os.path.isfile(full):
            s["gone"] = not s.get("src")
            if s["gone"]:
                s["src"] = None
                stats["shots_gone"] += 1
            continue
        if i >= MAX_SHOTS or used >= BUDGET:
            s["src"], s["gone"] = None, False
            stats["shots_skipped"] += 1
            continue
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "t.jpg")
            rc = run(
                "sips",
                "-Z",
                "960",
                "-s",
                "format",
                "jpeg",
                "-s",
                "formatOptions",
                "60",
                full,
                "--out",
                out,
            )
            if rc != 0 or not os.path.isfile(out):
                s["src"], s["gone"] = None, True
                stats["shots_gone"] += 1
                continue
            with open(out, "rb") as fh:
                b64 = base64.b64encode(fh.read()).decode()
        used += len(b64)
        s["src"], s["gone"] = "data:image/jpeg;base64," + b64, False
        stats["shots_embedded"] += 1


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    fragment = "--fragment" in argv
    root = os.getcwd()
    if "--root" in argv:
        root = argv[argv.index("--root") + 1]
        args = [a for a in args if a != root]
    if len(args) != 2:
        print(__doc__)
        return 2
    src, dst = args
    with open(src, encoding="utf-8") as fh:
        data = json.load(fh)
    stats = {"refs_ok": 0, "refs_gone": 0, "shots_embedded": 0, "shots_gone": 0, "shots_skipped": 0}
    walk(data, root, stats)
    for a in data.get("artefacts") or []:
        if not a.get("ref") and a.get("path"):
            full = a["path"] if os.path.isabs(a["path"]) else os.path.join(root, a["path"])
            a["gone"] = not os.path.exists(full)
    embed_shots(data, root, stats)

    # `<`, `>` and `&` escaped so no string can close the script block or open a comment.
    text = (
        json.dumps(data, ensure_ascii=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as fh:
        page = fh.read()
    a = page.index(OPEN) + len(OPEN)
    b = page.index("</script>", a)
    page = page[:a] + "\n" + text + "\n" + page[b:]
    name = data.get("name")
    if name:
        page = re.sub(
            r"<title>.*?</title>", "<title>" + html.escape(str(name)) + "</title>", page, count=1
        )
    if not fragment:
        page = HEADER + page
    if len(page.encode()) > MAX_PAGE:
        print("page over 12 MB; drop screenshots", file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(json.dumps(dict(stats, bytes=len(page.encode()), out=dst)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
