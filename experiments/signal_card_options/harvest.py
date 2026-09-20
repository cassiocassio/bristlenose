"""Harvest real signal cards from the trial databases.

A card is (axis, location, group). Quotes join it when any of their tags
belongs to that group — the same rule as generic_signals.py:104.
Writes cards.json for build.py.  Run from the repo root.
"""
import collections, glob, json, sqlite3

VALENCE = {"frustration": "neg", "confusion": "neg", "doubt": "neg",
           "surprise": "neu", "satisfaction": "pos", "delight": "pos",
           "confidence": "pos"}
SKIP = ("stress-test", "foo", "all the foo", "_")

AXES = [("section", "cluster_quotes", "screen_clusters", "cluster_id", "screen_label"),
        ("theme", "theme_quotes", "theme_groups", "theme_id", "theme_label")]


def harvest() -> list[dict]:
    cards: list[dict] = []
    for f in sorted(glob.glob("trial-runs/*/bristlenose-output/.bristlenose/bristlenose.db")):
        project = f.split("/")[1]
        if project.startswith(SKIP):
            continue
        db = sqlite3.connect(f)
        elab = {k: (n, p, e) for k, n, p, e in db.execute(
            "select signal_key, signal_name, pattern, elaboration from elaboration_caches")}
        people = {p for (p,) in db.execute(
            "select distinct participant_id from quotes where participant_id != ''")}
        for axis, tbl, jt, col, key in AXES:
            try:
                rows = db.execute(f"""
                    select sc.{key}, cg.name, cg.subtitle, cg.colour_set, td.name,
                           qu.id, qu.text, qu.participant_id, qu.start_timecode,
                           qu.intensity, qu.sentiment, qu.session_id
                    from {tbl} x
                    join {jt} sc on sc.id = x.{col}
                    join quotes qu on qu.id = x.quote_id
                    join quote_tags qt on qt.quote_id = qu.id
                    join tag_definitions td on td.id = qt.tag_definition_id
                    join codebook_groups cg on cg.id = td.codebook_group_id""").fetchall()
            except sqlite3.Error:
                continue
            acc: dict = collections.defaultdict(lambda: {"quotes": {}, "tags": set()})
            for (loc, grp, sub, cset, tag, qid, text, pid, t0, inten, sent, sess) in rows:
                c = acc[(loc, grp, sub, cset)]
                c["tags"].add(tag)
                q = c["quotes"].setdefault(qid, {
                    "id": qid, "text": " ".join((text or "").split()), "pid": pid,
                    "t": t0 or 0, "intensity": inten, "sentiment": sent,
                    "session": sess, "tags": []})
                if tag not in q["tags"]:
                    q["tags"].append(tag)
            for (loc, grp, sub, cset), c in acc.items():
                qs = sorted(c["quotes"].values(), key=lambda q: (q["pid"], q["t"]))
                sents = [q["sentiment"] for q in qs if q["sentiment"]]
                cards.append({
                    "project": project, "axis": axis, "location": loc,
                    "group": grp, "subtitle": sub or "", "colour_set": cset or "",
                    "tags": sorted(c["tags"]), "quotes": qs,
                    "participants": sorted({q["pid"] for q in qs}),
                    "all_participants": sorted(people),
                    "sentiments": sorted(set(sents)),
                    "valences": sorted({VALENCE.get(s, "?") for s in sents}),
                    "elab": elab.get(f"{axis}|{loc}|{grp}"),
                })
    return cards


if __name__ == "__main__":
    cards = harvest()
    json.dump(cards, open("experiments/signal_card_options/cards.json", "w"), indent=1)
    print(f"{len(cards)} cards  ·  {len({(c['project'], c['axis'], c['location']) for c in cards})} locations"
          f"  ·  {sum(1 for c in cards if c['elab'])} elaborated"
          f"  ·  {sum(1 for c in cards if len(c['tags']) > 1)} multi-tag")
