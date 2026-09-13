#!/usr/bin/env python
"""Re-measure docs/design-signal-strength.md against the real trial projects.

Runs the app's own path (``_resolve_active_groups`` -> ``_load_shared_data`` ->
``_compute_group_analysis``), then re-derives the shipped composite from raw
cells so both metrics come from one source, and asserts the reconstruction
against the app cell-by-cell.

    .venv/bin/python experiments/signal_strength/measure.py
    .venv/bin/python experiments/signal_strength/measure.py --project project-ikea

Two things the databases will do to you:
  * ``trial-runs/<p>/.bristlenose/`` holds empty stubs; the real database is
    under ``trial-runs/<p>/bristlenose-output/.bristlenose/``.
  * Several projects predate ``quotes.durable_id`` / ``projects.pii_redacted``.
    Each database is COPIED to a temp dir before anything touches it; the copy
    gains the missing project columns, and projects still missing quote columns
    are skipped with a line saying so.
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from metric import ceiling, strength  # noqa: E402
from summary import summarise  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from bristlenose.analysis.metrics import (  # noqa: E402
    composite_signal, concentration_ratio, mean_intensity, simpsons_neff,
)
from bristlenose.server.models import (  # noqa: E402
    Project, ProposedTag, QuoteTag, TagDefinition,
)
from bristlenose.server.routes.analysis import (  # noqa: E402
    _compute_group_analysis, _load_shared_data, _resolve_active_groups,
)

ROOT = Path(__file__).resolve().parents[2]
TRIALS = ROOT / "trial-runs"


def stage(src: Path, tmp: Path) -> Path | None:
    """Copy a database aside and add the project columns current models want.

    Returns None when the copy is on a schema too old to open at all.
    """
    dst = tmp / (src.parent.parent.parent.name.replace(" ", "_") + ".db")
    shutil.copy(src, dst)
    con = sqlite3.connect(dst)
    have = {r[1] for r in con.execute("PRAGMA table_info(projects)")}
    if "pii_redacted" not in have:
        con.execute("ALTER TABLE projects ADD COLUMN pii_redacted VARCHAR")
    if "mcp_anonymise" not in have:
        con.execute("ALTER TABLE projects ADD COLUMN mcp_anonymise BOOLEAN DEFAULT 0")
    con.commit()
    quote_cols = {r[1] for r in con.execute("PRAGMA table_info(quotes)")}
    con.close()
    return dst if {"durable_id", "frozen_form"} <= quote_cols else None


def open_db(path: Path):
    return sessionmaker(bind=create_engine(f"sqlite:///{path}"))()


def cells(db, pid: int, *, sentiment_values: bool = True,
          drop_sentiment_group: bool = True) -> list[dict]:
    """Every (location x label) pair, populated or not, with its quote ids.

    A *label* is either a codebook group or — when ``sentiment_values`` is on —
    a single sentiment value (``frustration``, ``delight``, …).  The whole
    point of the proposed metric is that these are the same kind of thing: the
    arithmetic is denominated in study quotes, so a label is just a subset of
    them and never a column of a particular matrix.
    """
    groups = _resolve_active_groups(db, pid, None)
    shared = _load_shared_data(db, pid)
    if shared is None or not groups:
        return []
    gid_name = {g.id: g.name for g in groups}
    gid_fw = {g.id: (g.framework_id or "custom") for g in groups}
    tds = db.query(TagDefinition).filter(
        TagDefinition.codebook_group_id.in_(gid_name)).all()
    td_g = {td.id: td.codebook_group_id for td in tds}
    qids = set(shared.quote_by_id)

    gq: dict[int, set[int]] = defaultdict(set)
    for qt in db.query(QuoteTag).filter(QuoteTag.tag_definition_id.in_(td_g)).all():
        if qt.quote_id in qids:
            gq[td_g[qt.tag_definition_id]].add(qt.quote_id)
    for pt in db.query(ProposedTag).filter(
            ProposedTag.tag_definition_id.in_(td_g),
            ProposedTag.status == "pending").all():
        if pt.quote_id in qids and pt.confidence > 0:
            gq[td_g[pt.tag_definition_id]].add(pt.quote_id)

    # The app keys quote->group by NAME, so same-named groups inside one
    # framework are ONE column.  Mirror that or the reconstruction disagrees.
    by_name: dict[tuple[str, str], set[int]] = defaultdict(set)
    for gid, gname in gid_name.items():
        by_name[(gid_fw[gid], gname)] |= gq[gid]

    # Sentiment VALUES as first-class labels, beside the groups.  Quote.sentiment
    # is a partition (one dominant value or None); a codebook group is a
    # relation.  Neither fact enters the arithmetic — both are just subsets.
    if sentiment_values:
        for qid, q in shared.quote_by_id.items():
            if q.sentiment:
                by_name[("sentiment-value", q.sentiment)].add(qid)
    # how many columns the framework DECLARES, whether or not they carry data
    declared: dict[str, int] = defaultdict(int)
    for fw, _ in by_name:
        declared[fw] += 1

    out: list[dict] = []
    for axis, qmap in (("section", shared.quote_section),
                       ("theme", shared.quote_theme)):
        axis_q = set(qmap)
        if not axis_q:
            continue
        row: dict[str, set[int]] = defaultdict(set)
        for qid, lab in qmap.items():
            row[lab].add(qid)
        for (fw, gname), gset in by_name.items():
            # The Sentiment GROUP is the union of the sentiment values, so
            # carrying both double-counts the same material at two
            # granularities.  The value is the comparable unit.
            if drop_sentiment_group and sentiment_values and fw == "sentiment":
                continue
            n_c = len(gset & axis_q)
            if n_c == 0:
                continue
            for lab, rq in row.items():
                cq = sorted(gset & rq)
                pc: dict[str, int] = defaultdict(int)
                ints = []
                for q in cq:
                    pc[shared.quote_by_id[q].participant_id] += 1
                    ints.append(shared.quote_by_id[q].intensity)
                out.append(dict(
                    axis=axis, location=lab, group=gname, framework=fw,
                    quote_ids=cq, k=len(cq),
                    part_counts=sorted(pc.values(), reverse=True),
                    n_part=len(pc), intensities=ints, K_r=len(rq),
                    n_c=n_c, K_all=len(axis_q), P=shared.total_participants,
                    n_cols_declared=declared[fw]))
    return out


def score(cs: list[dict]) -> None:
    """Attach both metrics.  Matrix totals are per (framework, axis)."""
    import statistics as _st

    # each label's own study-wide mean intensity — the heat baseline
    pool: dict = defaultdict(list)
    for c in cs:
        pool[(c["framework"], c["group"], c["axis"])].extend(c["intensities"])

    tot: dict = defaultdict(lambda: defaultdict(int))
    for c in cs:
        t = tot[(c["framework"], c["axis"])]
        t["grand"] += c["k"]
        t[("row", c["location"])] += c["k"]
        t[("col", c["group"])] += c["k"]
    for c in cs:
        t = tot[(c["framework"], c["axis"])]
        c["conc"] = concentration_ratio(c["k"], t[("row", c["location"])],
                                        t[("col", c["group"])], t["grand"])
        c["n_eff"] = simpsons_neff(c["part_counts"])
        c["mi"] = mean_intensity(c["intensities"])
        c["composite"] = composite_signal(c["conc"], c["n_eff"], c["P"], c["mi"])
        base = pool[(c["framework"], c["group"], c["axis"])]
        c["label_mi"] = _st.mean(base) if base else 1.0
        c["kind"] = ("sentiment" if c["framework"] == "sentiment-value"
                     else "codebook")
        c["strength"], c["V"], c["S"], c["H"] = strength(
            c["part_counts"], c["mi"], c["label_mi"], c["k"], c["K_r"],
            c["n_c"], c["K_all"], c["P"])
        c["ceiling"] = ceiling(c["K_r"], c["n_c"], c["K_all"], c["P"], c["label_mi"])


def verify(db, pid: int, cs: list[dict]) -> tuple[int, int]:
    """Assert the reconstruction reproduces the app's own numbers."""
    groups = _resolve_active_groups(db, pid, None)
    shared = _load_shared_data(db, pid)
    parts: dict[str, list] = defaultdict(list)
    for g in groups:
        parts[g.framework_id or "custom"].append(g)
    idx = {(c["axis"], c["location"], c["group"]): c for c in cs}
    checked = bad = 0
    for cb_groups in parts.values():
        res = _compute_group_analysis(cb_groups, shared, db, 500)
        if res is None:
            continue
        for s in res[0]:
            c = idx.get((s.source_type, s.location, s.sentiment))
            if c is None:
                continue
            checked += 1
            if (abs(c["composite"] - s.composite_signal) > 5e-3
                    or abs(c["conc"] - s.concentration) > 5e-3):
                bad += 1
                print(f"   MISMATCH {s.location[:24]} x {s.sentiment[:18]}: "
                      f"conc {c['conc']:.3f} vs {s.concentration:.3f}")
    return checked, bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", action="append",
                    help="trial-runs folder name; repeatable, default all")
    ap.add_argument("--floor", type=int, default=2,
                    help="MIN_QUOTES_PER_CELL to report at (default 2)")
    ap.add_argument("--as-shipped", action="store_true",
                    help="label set the product renders today: codebook groups "
                         "PLUS the one-column Sentiment group, and no sentiment "
                         "values.  Use this to measure the defect; the default "
                         "is the proposal's label set (sentiment VALUES beside "
                         "codebook groups, no Sentiment group).")
    ap.add_argument("--summary", action="store_true",
                    help="print the headline numbers quoted in the design note")
    ap.add_argument("--include-duplicate-projects", action="store_true",
                    help="fossda's database holds the same project twice "
                         "(project_id 1 and 2); the second is excluded by "
                         "default so the corpus is not double-counted")
    args = ap.parse_args()

    sources = sorted(TRIALS.glob("*/bristlenose-output/.bristlenose/bristlenose.db"))
    if args.project:
        wanted = set(args.project)
        sources = [p for p in sources if p.parent.parent.parent.name in wanted]

    total_checked = total_bad = 0
    corpus: list[dict] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for src in sources:
            name = src.parent.parent.parent.name
            staged = stage(src, tmp)
            if staged is None:
                print(f"{name:26s} SKIPPED — schema predates quotes.durable_id")
                continue
            db = open_db(staged)
            try:
                pids = [p.id for p in db.query(Project).all()]
            except Exception as exc:                    # noqa: BLE001
                print(f"{name:26s} SKIPPED — {type(exc).__name__}")
                db.close()
                continue
            for pid in pids[: None if args.include_duplicate_projects else 1]:
                cs = cells(db, pid,
                           sentiment_values=not args.as_shipped,
                           drop_sentiment_group=not args.as_shipped)
                if not cs:
                    continue
                score(cs)
                chk, bad = verify(db, pid, cs)
                total_checked += chk
                total_bad += bad
                for c in cs:
                    c["project"] = f"{name}#{pid}"
                corpus.extend(cs)
                shown = [c for c in cs if c["k"] >= args.floor]
                if not shown or args.summary:
                    continue
                over = sum(1 for c in shown if c["n_eff"] > c["n_part"] + 1e-9)
                flat = sum(1 for c in shown if abs(c["conc"] - 1.0) < 1e-9)
                print(f"\n{name}#{pid}  P={shown[0]['P']}  "
                      f"{len(shown)} cards at k>={args.floor} ({len(cs)} pairs)")
                print(f"   concentration == 1.00 exactly : {flat} of {len(shown)}")
                print(f"   n_eff > people who spoke      : {over} of {len(shown)}")
                print(f"   surprise < 0.05 (absence)     : "
                      f"{sum(1 for c in cs if c['S'] < 0.05)} of {len(cs)} pairs")
                print("   was  now  codebook    location x group"
                      "                     k ppl  conc  comp  strength")
                old = {id(c): i + 1 for i, c in
                       enumerate(sorted(shown, key=lambda c: -c["composite"]))}
                for i, c in enumerate(sorted(shown, key=lambda c: -c["strength"]), 1):
                    lab = f"{c['location'][:24]} x {c['group'][:18]}"
                    print(f"   {old[id(c)]:3d} {i:4d}  {c['framework'][:10]:10s} "
                          f"{lab:45s} {c['k']:2d} {c['n_part']:3d} "
                          f"{c['conc']:5.2f} {c['composite']:5.2f}   {c['strength']:5.1f}")
            db.close()

    print(f"\ncross-check vs the app path: {total_checked} cells compared, "
          f"{total_bad} mismatched")
    if args.summary:
        summarise(corpus, args.floor)
    return 1 if total_bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
