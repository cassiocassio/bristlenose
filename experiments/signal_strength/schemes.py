"""Five ways to present one ordering, side by side on the real projects.

Ordering and presentation are SEPARABLE.  Every scheme here is a monotone
per-study transform of the same score, so all five produce the identical
sequence.  What differs is what the number claims, and how it behaves when you
carry it from a three-person study to a twenty-person one.

    .venv/bin/python experiments/signal_strength/schemes.py            # text
    .venv/bin/python experiments/signal_strength/schemes.py --html OUT # page
"""
from __future__ import annotations

import html
import statistics as st
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import measure  # noqa: E402
from metric import ceiling, strength, surprise, voices  # noqa: E402

from bristlenose.server.models import Project  # noqa: E402

# Study model — every constant MEASURED from the corpus, not invented.
Q_PER_SESSION = 8         # 6.7-10.1, near-independent of session length
SENT_PER_QUOTE = 0.65     # 0.54-0.82; a partition over seven values
CODES_PER_QUOTE = 1.2     # at one installed codebook
LOCS_PER_SESSION = 2.2
N_SENT_VALUES = 7
N_GROUPS = 8


def band(attainment: float) -> str:
    if attainment >= 0.75:
        return "Strong"
    if attainment >= 0.50:
        return "Clear"
    if attainment >= 0.30:
        return "Emerging"
    return "Faint"


def load():
    out = {}
    with tempfile.TemporaryDirectory() as td:
        for src in sorted(Path("trial-runs").glob(
                "*/bristlenose-output/.bristlenose/bristlenose.db")):
            name = src.parent.parent.parent.name
            stg = measure.stage(src, Path(td))
            if stg is None:
                continue
            db = measure.open_db(stg)
            try:
                pids = [p.id for p in db.query(Project).all()]
            except Exception:                                  # noqa: BLE001
                db.close()
                continue
            for pid in pids[:1]:
                cs = measure.cells(db, pid)
                if cs:
                    measure.score(cs)
                    out[f"{name}#{pid}"] = cs
            db.close()
    return out


def attainable_range(P: int, sessions: int | None = None):
    """Strongest and weakest measurable card a study of P users can produce,
    for a sentiment value and for a codebook group."""
    sessions = sessions or P
    Q = int(sessions * Q_PER_SESSION)
    L = max(1, int(sessions * LOCS_PER_SESSION))
    K_r = max(2, Q // L)
    out = {}
    for kind, n_c in (("sentiment", max(1, int(Q * SENT_PER_QUOTE / N_SENT_VALUES))),
                      ("codebook", max(1, int(Q * CODES_PER_QUOTE / N_GROUPS)))):
        hi = ceiling(K_r, n_c, Q, P, 1.9)
        lo, *_ = strength([1], 1.0, 1.9, 1, K_r, n_c, Q, P)
        out[kind] = (lo, hi, n_c)
    return Q, K_r, out


def rows(cs: list[dict]):
    cards = sorted((c for c in cs if c["k"] >= 2), key=lambda c: -c["strength"])
    if not cards:
        return [], 0.0
    cap = max(c["ceiling"] for c in cs if c["ceiling"] > 0)
    n, top = len(cards), cards[0]["strength"]
    out = []
    for i, c in enumerate(cards, 1):
        att = c["strength"] / cap if cap else 0
        out.append(dict(rank=i, card=c, attain=att, of_best=c["strength"] / top,
                        pctile=1 - (i - 1) / n, band=band(att)))
    return out, cap


def text_report(projects):
    print("ATTAINABLE RANGE — the strongest and weakest measurable card a study")
    print("of N users can produce, for each kind of label.\n")
    print(f"{'N':>3} {'Q':>4} {'K_r':>4} | {'sentiment value':^22s} | "
          f"{'codebook group':^22s} | overlap")
    for P in (3, 5, 6, 8, 12, 20):
        Q, K_r, b = attainable_range(P)
        (sl, sh, sn), (cl, ch, cn) = b["sentiment"], b["codebook"]
        lo, hi = max(sl, cl), min(sh, ch)
        ov = (hi - lo) / (max(sh, ch) - min(sl, cl)) if hi > lo else 0
        print(f"{P:3d} {Q:4d} {K_r:4d} | n_c={sn:3d} {sl:6.1f} … {sh:6.1f} | "
              f"n_c={cn:3d} {cl:6.1f} … {ch:6.1f} | {ov:6.0%}")

    print("\n\nPER PROJECT — one ordering, five presentations")
    for proj, cs in sorted(projects.items()):
        rs, cap = rows(cs)
        if not rs:
            continue
        c0 = rs[0]["card"]
        kinds = {r["card"]["kind"] for r in rs}
        print(f"\n=== {proj}  P={c0['P']}  {len(rs)} cards  "
              f"ceiling {cap:.1f}  kinds: {'+'.join(sorted(kinds))} ===")
        print(f"{'#':>2}  {'label':38s} {'Signal':>7s} {'Strength':>8s} "
              f"{'Attain':>7s} {'ofBest':>7s} {'Pctile':>7s} {'Band':>9s}")
        for r in rs[:14]:
            c = r["card"]
            lab = f"{c['group'][:18]} @ {c['location'][:17]}"
            mark = "S" if c["kind"] == "sentiment" else "C"
            print(f"{r['rank']:2d}{mark} {lab:38s} {c['composite']:7.2f} "
                  f"{c['strength']:8.1f} {r['attain']:6.0%} {r['of_best']:6.0%} "
                  f"{r['pctile']:6.0%} {r['band']:>9s}")


def html_report(projects, path: Path):
    e = html.escape
    P_ = []
    P_.append("<title>Signal strength — normalisation spike</title>")
    P_.append("""<style>
:root{--bg:#fbfbfa;--fg:#1a1a18;--mut:#6b6b66;--line:#e2e2dd;--s:#b45309;--c:#1d4ed8;
      --card:#fff;--hi:#fef3c7}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
  --bg:#16161a;--fg:#e8e8e4;--mut:#9a9a94;--line:#2e2e34;--s:#fbbf24;--c:#93c5fd;
  --card:#1d1d22;--hi:#3a3020}}
:root[data-theme=dark]{--bg:#16161a;--fg:#e8e8e4;--mut:#9a9a94;--line:#2e2e34;
  --s:#fbbf24;--c:#93c5fd;--card:#1d1d22;--hi:#3a3020}
body{background:var(--bg);color:var(--fg);font:14px/1.5 ui-sans-serif,-apple-system,
  "Segoe UI",sans-serif;margin:0;padding:32px 24px;max-width:1080px;margin-inline:auto}
h1{font-size:22px;margin:0 0 4px} h2{font-size:16px;margin:34px 0 6px;
  padding-bottom:5px;border-bottom:1px solid var(--line)}
p{color:var(--mut);max-width:66ch} code{font:12px ui-monospace,monospace}
.wrap{overflow-x:auto;border:1px solid var(--line);border-radius:8px;
  background:var(--card);margin:12px 0}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{padding:5px 9px;text-align:right;white-space:nowrap}
th{font-weight:600;color:var(--mut);font-size:11px;text-transform:uppercase;
  letter-spacing:.04em;border-bottom:1px solid var(--line)}
td.l,th.l{text-align:left}
tr+tr td{border-top:1px solid var(--line)}
.k{display:inline-block;width:15px;height:15px;line-height:15px;text-align:center;
  border-radius:3px;font-size:10px;font-weight:700;margin-right:6px;color:#fff}
.ks{background:var(--s)} .kc{background:var(--c)}
.mut{color:var(--mut)} .num{font-variant-numeric:tabular-nums}
.b{font-weight:600} mark{background:var(--hi);color:inherit;padding:0 3px;border-radius:3px}
</style>""")
    P_.append("<h1>Signal strength — normalisation spike</h1>")
    P_.append("<p>One ordering, five presentations. Every scheme is a monotone "
              "per-study transform of the same score, so the <em>sequence is "
              "identical in all of them</em> — only what the number claims "
              "changes. <span class='k ks'>S</span> a sentiment value, "
              "<span class='k kc'>C</span> a codebook group. Nothing here is "
              "wired into the product.</p>")

    P_.append("<h2>Attainable range by study size</h2>")
    P_.append("<p>The strongest and the weakest measurable card a study of N users "
              "can produce, for each kind of label. Two things to read: the two "
              "kinds' bands <strong>converge from N=5</strong>, and the ceiling "
              "<strong>falls as the study grows</strong> — because a location holds "
              "a near-constant number of quotes however many sessions you run, so "
              "it can never involve every participant.</p>")
    P_.append("<div class=wrap><table><tr><th>N users</th><th>quotes</th>"
              "<th>per location</th><th class=l>sentiment value</th>"
              "<th class=l>codebook group</th><th>band overlap</th></tr>")
    for P in (3, 5, 6, 8, 12, 20):
        Q, K_r, b = attainable_range(P)
        (sl, sh, sn), (cl, ch, cn) = b["sentiment"], b["codebook"]
        lo, hi = max(sl, cl), min(sh, ch)
        ov = (hi - lo) / (max(sh, ch) - min(sl, cl)) if hi > lo else 0
        P_.append(f"<tr><td class=num>{P}</td><td class=num>{Q}</td>"
                  f"<td class=num>{K_r}</td>"
                  f"<td class='l num'>{sl:.1f} … {sh:.1f}</td>"
                  f"<td class='l num'>{cl:.1f} … {ch:.1f}</td>"
                  f"<td class=num><mark>{ov:.0%}</mark></td></tr>")
    P_.append("</table></div>")

    for proj, cs in sorted(projects.items()):
        rs, cap = rows(cs)
        if not rs:
            continue
        c0 = rs[0]["card"]
        ns = sum(1 for r in rs if r["card"]["kind"] == "sentiment")
        P_.append(f"<h2>{e(proj)}</h2>")
        P_.append(f"<p>{c0['P']} participants · {len(rs)} cards "
                  f"({ns} sentiment, {len(rs)-ns} codebook) · this study's "
                  f"ceiling {cap:.0f}</p>")
        P_.append("<div class=wrap><table><tr><th>#</th><th class=l>label</th>"
                  "<th class=l>location</th><th>Signal<br><span class=mut>today"
                  "</span></th><th>Strength</th><th>Attain</th><th>of best</th>"
                  "<th>pctile</th><th class=l>band</th></tr>")
        for r in rs[:16]:
            c = r["card"]
            kc = "ks" if c["kind"] == "sentiment" else "kc"
            kl = "S" if c["kind"] == "sentiment" else "C"
            P_.append(
                f"<tr><td class=num>{r['rank']}</td>"
                f"<td class=l><span class='k {kc}'>{kl}</span>{e(c['group'])}</td>"
                f"<td class='l mut'>{e(c['location'][:34])}</td>"
                f"<td class=num>{c['composite']:.2f}</td>"
                f"<td class='num b'>{c['strength']:.0f}</td>"
                f"<td class=num>{r['attain']:.0%}</td>"
                f"<td class=num>{r['of_best']:.0%}</td>"
                f"<td class=num>{r['pctile']:.0%}</td>"
                f"<td class=l>{r['band']}</td></tr>")
        P_.append("</table></div>")

    path.write_text("\n".join(P_))
    return path


if __name__ == "__main__":
    projects = load()
    if "--html" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--html") + 1])
        print("wrote", html_report(projects, out))
    else:
        text_report(projects)
