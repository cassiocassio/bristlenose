"""MCP lab runner: real tool output against realistic prompts, on SYNTHETIC data.

Builds a small fictional study ("Harbour Bank", invented participants and
quotes; nothing here is real research data) on top of the smoke fixture, then
runs a set of researcher prompts. For each prompt, `PROMPTS` below says which
tool calls a sensible agent would make (chosen by hand, NOT by a live model)
and which facts the output must show. The calls run against the server's own
tool functions at the current commit, and the results are written to
lab-results.json for docs/mockups/mcp-lab.html.

    .venv/bin/python experiments/mcp-lab/run_lab.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bristlenose.server.app import create_app  # noqa: E402
from bristlenose.server.mcp_server import (  # noqa: E402
    ToolInputError,
    _tool_get_framework,
    _tool_get_project_overview,
    _tool_get_signals,
    _tool_search_quotes,
    build_instructions,
)
from bristlenose.server.models import (  # noqa: E402
    ClusterQuote, CodebookGroup, DeletedBadge, Person, Project, ProjectCodebookGroup,
    Quote, QuoteEdit, QuoteState, QuoteTag, ScreenCluster, SessionSpeaker, TagDefinition,
    ThemeQuote,
)
from bristlenose.server.models import Session as SessionModel  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "smoke-test" / "input"
OUT = Path(__file__).with_name("lab-results.json")


def build_study(db) -> None:
    """Wipe the smoke fixture's quotes and seed a fictional study."""
    for model in (ClusterQuote, ThemeQuote, QuoteTag, QuoteState, QuoteEdit, DeletedBadge, Quote):
        db.query(model).delete()
    db.query(ScreenCluster).delete()
    db.commit()

    s1 = db.query(SessionModel).filter_by(session_id="s1").one()
    s1.duration_seconds = 2400.0  # the smoke fixture's 78 seconds would make timecodes absurd
    mod_slot = db.query(SessionSpeaker).filter_by(session_id=s1.id, speaker_code="m1").one()
    p1_slot = db.query(SessionSpeaker).filter_by(session_id=s1.id, speaker_code="p1").one()
    people = {n: Person(full_name=f"{n} (synthetic)", short_name=n) for n in ("Ada", "Ben", "Cleo")}
    db.add_all(people.values())
    db.flush()
    p1_slot.person_id, p1_slot.state = people["Ada"].id, "confirmed"
    mod_slot.state = None
    for sid, num, code, who in (("s2", 2, "p2", "Ben"), ("s3", 3, "p3", "Cleo")):
        s = SessionModel(project_id=1, session_id=sid, session_number=num, duration_seconds=2400.0)
        db.add(s)
        db.flush()
        db.add(SessionSpeaker(session_id=s.id, speaker_code="m1", speaker_role="researcher"))
        db.add(SessionSpeaker(session_id=s.id, speaker_code=code, speaker_role="participant",
                              person_id=people[who].id, state="confirmed"))
    db.flush()

    clusters = {n: ScreenCluster(project_id=1, screen_label=n, display_order=i)
                for i, n in enumerate(("Login", "Payments"))}
    db.add_all(clusters.values())
    db.flush()

    spec = [  # (key, session, tag, start, end, sentiment, intensity, cluster, text)
        ("pw", "s1", "p1", 120, 138, "frustration", 3, "Login",
         "I typed my password three times and it still said wrong."),
        ("again", "s2", "p2", 200, 215, "frustration", 2, "Login",
         "Why do I need to log in again every single time?"),
        ("code", "s1", "p1", 300, 345, "frustration", 3, "Login",
         "The code text never arrived so I just gave up."),
        ("faceid", "s2", "p2", 400, 408, "delight", 1, "Login",
         "Face ID worked, honestly that was fine."),
        ("locked", "s2", "p2", 620, 631, "frustration", 2, "Login",
         "Locked out again, second time today."),
        ("hidden", "s1", "p1", 700, 712, "frustration", 3, "Login",
         "My name is Alex Rivers and the login kicked me out at my desk."),
        ("pending", "s2", "p2", 500, 520, "confusion", 2, "Payments",
         "Where did the money go? It says pending and nothing else."),
        ("pay40", "s1", "p1", 600, 640, "frustration", 2, "Payments",
         "I paid my sister and honestly could not tell if it had gone."),
        # Session 3's participant slot is p3, but these quotes carry the tag p1:
        # what a renamed code leaves behind.
        ("orphan", "s3", "p1", 60, 80, "confusion", 2, "Login",
         "I thought logging in would work like my other bank app."),
        ("untimed", "s3", "p1", 0, 0, "frustration", 1, "Login", "Login again? Ok."),
    ]
    q: dict[str, Quote] = {}
    for key, sid, tag, a, b, sent, inten, cl, text in spec:
        q[key] = Quote(project_id=1, session_id=sid, participant_id=tag, start_timecode=float(a),
                       end_timecode=float(b), text=text, quote_type="screen_specific",
                       sentiment=sent, intensity=inten)
        db.add(q[key])
    db.flush()
    for key, *_rest in spec:
        cl = next(r for r in spec if r[0] == key)[7]
        db.add(ClusterQuote(cluster_id=clusters[cl].id, quote_id=q[key].id))
    db.add(QuoteState(quote_id=q["again"].id, is_starred=True))
    db.add(QuoteState(quote_id=q["hidden"].id, is_hidden=True))

    for name, colour, tags in (("Pain points", "emo", {"auth friction": ("pw", "again", "code")}),
                               ("Mental models", "task", {"borrowed model": ("orphan", "code")})):
        group = CodebookGroup(name=name, subtitle="", colour_set=colour, framework_id="uxr")
        db.add(group)
        db.flush()
        db.add(ProjectCodebookGroup(project_id=1, codebook_group_id=group.id))
        for tag_name, keys in tags.items():
            td = TagDefinition(codebook_group_id=group.id, name=tag_name)
            db.add(td)
            db.flush()
            for k in keys:
                db.add(QuoteTag(quote_id=q[k].id, tag_definition_id=td.id))
    # The importer tags every quote with its sentiment (the Sentiment framework),
    # so a real quote's tags always include it; seed the same.
    # The smoke fixture already carries the Sentiment group: reuse it (a second one,
    # which round-1 agents noticed, was this lab's own mistake, not the product's).
    sentiment_group = db.query(CodebookGroup).filter_by(name="Sentiment").one()
    sentiment_tags = {
        t.name: t for t in db.query(TagDefinition).filter_by(codebook_group_id=sentiment_group.id)
    }
    for key, *_rest in spec:
        db.add(QuoteTag(quote_id=q[key].id,
                        tag_definition_id=sentiment_tags[next(r for r in spec if r[0] == key)[5]].id))
    db.commit()


#: The live-agent runs: id -> (study, the researcher's words). The agents were given
#: ONLY tool_cli.py (see its docstring) and chose their own calls; their call logs and
#: answers live in experiments/mcp-lab/live/ and are shown unedited.
LIVE_PROMPTS = {
    "a1": ("main", "Find the best 3 clips under 30 seconds where users are most frustrated with login, "
                   "and tell me who each one is."),
    "a2": ("main", "Who did we interview and which sessions were they in? I want it for a "
                   "'who we interviewed' slide."),
    "a3": ("swap", "Session 1 looks empty to me. Ada talked for most of it. What's going on?"),
    "a4": ("main", "What are the pain points? Give me the top three with a quote each, in the shape "
                   "of the report."),
    "a5": ("main", "Pull the juiciest login rants for the readout."),
    "a6": ("main", "Anything about mental models? Who said it?"),
    # Round 2: the same prompts to fresh agents after the fixes the first round exposed.
    "b3": ("swap", "Session 1 looks empty to me. Ada talked for most of it. What's going on?"),
    "b4": ("main", "What are the pain points? Give me the top three with a quote each, in the shape "
                   "of the report."),
    "b6": ("main", "Anything about mental models? Who said it?"),
}

#: What six fresh agents (round 1) hit, and what became of it. Written by the author from their
#: reports; the reports themselves are shown unedited below.
LIVE_FINDINGS = [
    ("FIXED", "Four of six agents could not attribute two quotes in session 3 (credited to p1, "
              "while the session's only participant is p3): the overview showed a surplus but not "
              "whose tag carried it. The session row now lists quotes_with_no_speaker."),
    ("FIXED", "'login' as a text query found one quote (it matches the quote's words only). The "
              "description now says so and points to section, tag, group and theme."),
    ("FIXED", "get_signals showed one pattern and agents wondered where the rest were: the "
              "two-quotes-per-cell rule was undocumented. Now in the description."),
    ("FIXED", "A participant recoded from an unidentified moderator reads p?, which the instructions "
              "did not explain (they explained m?). They do now."),
    ("LAB DATA", "Session 1 was 78 seconds long and the quotes had no sentiment tags, which agents "
                 "noticed as odd. Artefacts of the synthetic study; fixed there, not in the product."),
    ("LAB DATA", "last_run is null in this command line (the real server fills it); agents asked "
                 "what null meant. Not a product bug, but worth saying what null means."),
    ("ROUND 2", "After the fixes, the mental-models agent used quotes_with_no_speaker and called "
                "session 3's attribution unresolved instead of guessing; the swap agent diagnosed "
                "session 1 from the set-aside count and the instructions alone, and said what it "
                "was inferring. Neither could say who or when the roles were changed."),
    ("LAB DATA", "Round 2 agents saw two Sentiment groups in the codebook: this lab seeded a second "
                 "one over the smoke fixture's. Fixed in the lab (round 2 transcripts still show it)."),
    ("OPEN", "A quote result carries no warning when its speaker tag is not in its session (agent "
             "b6); the overview flags it, the quote does not."),
    ("OPEN", "A swapped session reads code p? with slot_code m1 and code m? with slot_code p1, "
             "which agents decoded only by careful reading; an explicit 'roles look swapped' note "
             "was suggested."),
    ("OPEN", "Excluded-for-unknown-length quotes are counted but not named; an agent had to rerun "
             "the search to find which."),
    ("FIXED", "get_signals' sentiment cards showed supporting quotes with tags: [] where "
              "search_quotes showed them tagged (two agents), and 3 shown of 5 with no note. "
              "Tags are filled in and supporting_quotes_omitted says how many are not shown."),
    ("OPEN", "Names appear while the agent is told to attribute by code; agents asked what to "
             "disclose in a readout. A product decision, not a code one."),
    ("OPEN", "No way to read the text of set-aside quotes, so an agent cannot show the researcher "
             "what was set aside."),
]


def load_live() -> list[dict]:
    """Merge each live agent's call log and its written answer into lab cards."""
    live_dir = Path(__file__).with_name("live")
    out = []
    for aid, (study, prompt) in LIVE_PROMPTS.items():
        log = live_dir / f"{aid}.jsonl"
        answer = live_dir / f"{aid}.answer.md"
        if not log.exists():
            continue
        steps = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line]
        out.append({"id": aid, "study": study, "prompt": prompt,
                    "round": 2 if aid.startswith("b") else 1,
                    "steps": [s for s in steps if s["tool"] in
                              ("get_project_overview", "search_quotes", "get_signals", "get_framework")],
                    "answer": answer.read_text(encoding="utf-8") if answer.exists() else ""})
    return out


def apply_swap(db) -> None:
    """Session 1's participant tag recoded as researcher, its moderator tag as participant."""
    s1 = db.query(SessionModel).filter_by(session_id="s1").one()
    for slot in db.query(SessionSpeaker).filter_by(session_id=s1.id):
        slot.person_id, slot.state = None, None
        slot.speaker_role = "researcher" if slot.speaker_code == "p1" else "participant"
    db.commit()


def call(tool: str, db, **args):
    fns = {
        "get_project_overview": lambda: _tool_get_project_overview(db, 1, None),
        "search_quotes": lambda: _tool_search_quotes(db, 1, **{
            "query": None, "tag": None, "sentiment": None, "participant": None, "section": None,
            "theme": None, "starred_only": False, "limit": 20, "offset": 0, **args}),
        "get_signals": lambda: _tool_get_signals(db, 1, args.get("lens", "sentiment"),
                                                 args.get("limit", 10)),
        "get_framework": lambda: _tool_get_framework(db, 1, args["framework_id"]),
    }
    try:
        return {"tool": tool, "args": args, "result": fns[tool]()}
    except ToolInputError as exc:
        return {"tool": tool, "args": args, "error": str(exc)}


def rows(step):  # the quotes of a search step
    return step["result"]["quotes"]


def main() -> None:
    app = create_app(project_dir=FIXTURE, dev=True, db_url="sqlite://")
    db = app.state.db_factory()
    build_study(db)

    def overview():
        return call("get_project_overview", db)

    def check(ok: bool, text: str) -> dict:
        return {"ok": bool(ok), "text": text}

    results = []

    def run(pid, prompt, intent, calls, checks):
        steps = [call(t, db, **a) for t, a in calls]
        try:
            verdicts = checks(steps)
        except Exception as exc:  # a broken output is a failed check, not a dead lab
            verdicts = [{"ok": False, "text": f"the checks could not run: {type(exc).__name__}: {exc}"}]
        results.append({"id": pid, "prompt": prompt, "intent": intent, "steps": steps,
                        "checks": verdicts})

    run("who", "Who did we interview, and which sessions were they in?",
        "A session-by-session roster an agent can turn into a 'who we interviewed' slide.",
        [("get_project_overview", {})],
        lambda s: [
            check(all(r["speakers"] for r in s[0]["result"]["sessions"]["items"]),
                  "every session row lists its speakers, participants included"),
            check(any(sp["role"] == "participant" for r in s[0]["result"]["sessions"]["items"]
                      for sp in r["speakers"]), "a session names its participant"),
            check(all("name" in sp for r in s[0]["result"]["sessions"]["items"]
                      for sp in r["speakers"] if sp["role"] == "participant"),
                  "names ride along (Anonymise is off)")])

    run("gap", "Cleo's session doesn't seem to have any quotes from her. What happened?",
        "The 14 Nov incident: quotes credited to a tag nobody in the session holds.",
        [("get_project_overview", {}), ("search_quotes", {"participant": "p3"}),
         ("search_quotes", {"participant": "p1", "session": "s3"})],
        lambda s: (lambda r3: [
            check(next(sp for sp in r3["speakers"] if sp["code"] == "p3")["visible_quotes"] == 0,
                  "p3 is listed with visible_quotes: 0 (not omitted)"),
            check(r3["visible_quotes"] > sum(sp["visible_quotes"] for sp in r3["speakers"]),
                  "the session total exceeds its speakers' sum: the gap IS the orphaned quotes"),
            check(s[1]["result"]["total_matched"] == 0, "searching p3 finds nothing"),
            check(any(x["session_id"] == "s3" for x in rows(s[2])),
                  "the missing quotes are still there, under the tag p1")])(
            next(r for r in s[0]["result"]["sessions"]["items"] if r["session_id"] == "s3")))

    run("best3", "Find the best 3 clips under 30 seconds where users are most frustrated "
        "with login.", "The owner's scenario: filter by feeling, topic and length, then rank.",
        [("search_quotes", {"sentiment": "frustration", "section": "Login", "max_duration_seconds": 30,
                            "sort": "strength", "limit": 3})],
        lambda s: [
            check(all((x["duration_seconds"] or 999) <= 30 for x in rows(s[0])),
                  "every quote is 30 seconds or less"),
            check([x["quote_id"] for x in rows(s[0])] == ["q-p2-200", "q-p1-120", "q-p2-620"],
                  "exactly the three expected clips, in order: the starred one, then the two in the "
                  "same signal by intensity (3 then 2)"),
            check(rows(s[0])[0]["starred"], "the researcher's starred quote comes first"),
            check(not any("Alex Rivers" in x["text"] for x in rows(s[0])), "the hidden quote is absent"),
            check(s[0]["result"]["sorted_by"].startswith("strength"), "the basis is stated: sorted_by"),
            check(s[0]["result"]["duration_unknown_excluded"] >= 1,
                  "untimed quotes are left out and counted, not silently dropped")])

    run("long", "Which frustrated quotes are over 40 seconds? (what's the longest?)",
        "min_duration_seconds, and the timing fields on each row.",
        [("search_quotes", {"sentiment": "frustration", "min_duration_seconds": 40})],
        lambda s: [check({x["quote_id"] for x in rows(s[0])} == {"q-p1-300", "q-p1-600"},
                         "exactly the two frustrated quotes of 40 seconds or more (45s and 40s)"),
                   check(all(x["end_timecode"] and x["duration_seconds"] for x in rows(s[0])),
                         "each carries its start, end and length")])

    run("untimed", "Show me quotes under 10 seconds from session 3.",
        "An untimed transcript: the answer must say why it is empty, not look like an empty study.",
        [("search_quotes", {"max_duration_seconds": 10, "session": "s3"})],
        lambda s: [check(s[0]["result"]["total_matched"] == 0 and
                         s[0]["result"]["duration_unknown_excluded"] == 1,
                         "nothing under 10 seconds, and exactly one s3 quote left out for unknown length"),
                   check(all(x["session_id"] == "s3" for x in rows(s[0])), "only session 3")])

    run("pain", "What are the pain points?",
        "Research vocabulary mapped to the codebook: the Pain points group and its tags.",
        [("get_project_overview", {}), ("get_framework", {"framework_id": "codebook"}),
         ("search_quotes", {"group": "Pain points", "sort": "strength"})],
        lambda s: [
            check(any(g["name"] == "Pain points" for g in s[0]["result"]["codebook"]["groups"]),
                  "the overview lists a 'Pain points' group the agent can match to"),
            check({x["quote_id"] for x in rows(s[2])} == {"q-p1-120", "q-p2-200", "q-p1-300"}
                  and s[2]["result"]["total_matched"] == 3,
                  "the group returns exactly the three quotes tagged inside it"),
            check(s[2]["result"]["groups_matched"] == [{"name": "Pain points", "framework_id": "uxr"}],
                  "the result says which group matched")])

    run("mental", "What came up about mental models?",
        "The researcher's words ('mental models') are a real codebook group, not a text search.",
        [("get_framework", {"framework_id": "codebook"}),
         ("search_quotes", {"group": "Mental models"})],
        lambda s: [check({x["quote_id"] for x in rows(s[1])} == {"q-p1-60", "q-p1-300"}
                         and s[1]["result"]["total_matched"] == 2,
                         "exactly the two quotes carrying a Mental models tag"),
                   check(any(x["session_id"] == "s3" and x["participant"] == "p1" for x in rows(s[1])),
                         "WATCH THIS: one of them is session 3's words, credited to the tag p1, which "
                         "the roster says is Ada in session 1. An agent that attributes by tag alone "
                         "would misattribute it.")])

    run("signals", "What did we learn? Give me the strongest patterns.",
        "Signal cards for the 'what we learned' slide.",
        [("get_signals", {"lens": "sentiment", "limit": 3})],
        lambda s: [check(s[0]["result"]["signals"] and all(c["participants"] and c["confidence"]
                                                          for c in s[0]["result"]["signals"]),
                         "every card names its participants and its confidence"),
                   check(len(s[0]["result"]["signals"]) <= 3, "limited to the three asked for"),
                   check(all(q["tags"] for c in s[0]["result"]["signals"] for q in c["supporting_quotes"]),
                         "every supporting quote carries its tags (they read [] before the live "
                         "agents noticed)")])

    run("best", "What are the best quotes overall?",
        "A bare 'best': the stated ranking, and the basis named.",
        [("search_quotes", {"sort": "strength", "limit": 3})],
        lambda s: [check([x["quote_id"] for x in rows(s[0])] == ["q-p2-200", "q-p1-600", "q-p2-500"],
                         "the starred quote first, then the two Payments quotes: that cell has two "
                         "participants agreeing, a stronger signal than Login's (OBSERVED, and worth "
                         "arguing with: a researcher may not call that 'best')"),
                   check(not any("Alex Rivers" in x["text"] for x in rows(s[0])), "the hidden quote is absent")])

    run("typo", "Show me what p9 said.",
        "A code that does not exist.",
        [("search_quotes", {"participant": "p9"})],
        lambda s: [check("error" in s[0] and "p1" in s[0]["error"],
                         "an unknown code gets an error that lists the valid ones, "
                         "not a silent empty result")])

    run("ben", "What did Ben say in session 2?",
        "Roster first (who is Ben's code), then his quotes: the two have to agree.",
        [("get_project_overview", {}), ("search_quotes", {"participant": "p2", "session": "s2"})],
        lambda s: [check(s[1]["result"]["total_matched"] == next(
                             sp["visible_quotes"] for r in s[0]["result"]["sessions"]["items"]
                             if r["session_id"] == "s2" for sp in r["speakers"] if sp["code"] == "p2"),
                         "the roster's count for p2 in s2 equals the total the search matched"),
                   check(all(x["participant"] == "p2" and x["session_id"] == "s2" for x in rows(s[1])),
                         "only p2's words, only session 2")])

    run("stars", "What has the researcher starred?",
        "The researcher's own judgement, surfaced as a filter.",
        [("search_quotes", {"starred_only": True})],
        lambda s: [check([x["quote_id"] for x in rows(s[0])] == ["q-p2-200"], "exactly the one starred quote")])

    run("s2", "Summarise what happened in session 2.",
        "A session-scoped question: the roster for who, then every quote of that session in time order.",
        [("get_project_overview", {}), ("search_quotes", {"session": "s2"})],
        lambda s: [check(all(x["session_id"] == "s2" for x in rows(s[1])) and rows(s[1]),
                         "only session 2's quotes"),
                   check(s[1]["result"]["total_matched"] == next(
                       r["visible_quotes"] for r in s[0]["result"]["sessions"]["items"]
                       if r["session_id"] == "s2"),
                       "as many quotes as the roster says session 2 has")])

    run("2fa", "Anything about 2FA or text codes?",
        "A synonym miss: the quote says 'the code text never arrived'. Substring search cannot know "
        "2FA means that. An honest lab shows the miss.",
        [("search_quotes", {"query": "2FA"}), ("search_quotes", {"query": "code"})],
        lambda s: [check(s[0]["result"]["total_matched"] == 0,
                         "KNOWN LIMIT: searching '2FA' finds nothing, though a quote is about exactly that"),
                   check(any("code" in x["text"].lower() for x in rows(s[1])),
                         "a second try with the quote's own word does find it: the agent has to retry")])

    run("rants", "Pull the juiciest login rants for the readout.",
        "A messier, human phrasing of 'best': no length limit, no tool vocabulary.",
        [("search_quotes", {"sentiment": "frustration", "section": "Login", "sort": "strength",
                            "limit": 5})],
        lambda s: [check(rows(s[0])[0]["quote_id"] == "q-p2-200", "the starred quote leads"),
                   check(all(x["sentiment"] == "frustration" for x in rows(s[0])),
                         "only frustration"),
                   check(not any("Alex Rivers" in x["text"] for x in rows(s[0])),
                         "the hidden quote is not offered")])

    run("hiddenprobe", "Include the quotes I hid too.",
        "The researcher asks for hidden quotes. There is no way to: hidden means hidden.",
        [("search_quotes", {"query": "Alex Rivers"})],
        lambda s: [check(s[0]["result"]["total_matched"] == 0,
                         "a hidden quote cannot be found, even by its exact words")])

    p = db.query(Project).one()
    p.mcp_anonymise = True
    db.commit()
    run("anon", "Who did we interview? (Anonymise switched on)",
        "The same roster with names withheld; codes and counts remain.",
        [("get_project_overview", {})],
        lambda s: [check(not any(n in json.dumps(s[0]["result"]) for n in ("Ada", "Ben", "Cleo", "synthetic")),
                         "no participant name anywhere in the payload"),
                   check(all("name" not in sp for r in s[0]["result"]["sessions"]["items"]
                             for sp in r["speakers"]), "no speaker row carries a name key"),
                   check({(r["session_id"], sp["code"], sp["visible_quotes"])
                          for r in s[0]["result"]["sessions"]["items"] for sp in r["speakers"]} ==
                         {(r["session_id"], sp["code"], sp["visible_quotes"])
                          for r in results[0]["steps"][0]["result"]["sessions"]["items"]
                          for sp in r["speakers"]},
                         "codes and counts are exactly what they were with names on")])

    run("anonada", "What did Ada say in session 1? (Anonymise on)",
        "A researcher asks by name. The tools only know codes, and no name leaks back.",
        [("search_quotes", {"participant": "p1", "session": "s1"})],
        lambda s: [check(s[0]["result"]["total_matched"] == 3 and
                         not any(n in json.dumps(s[0]["result"]) for n in ("Ada", "synthetic")),
                         "three quotes (the fourth is hidden) come back under the code p1, with no "
                         "name in the payload")])

    # A second, separate study: the participant and the moderator of session 1
    # have their roles swapped (the real incident that started this work).
    db = create_app(project_dir=FIXTURE, dev=True, db_url="sqlite://").state.db_factory()
    build_study(db)
    apply_swap(db)
    run("swap", "Why does session 1 show no quotes at all? Ada talked for most of it.",
        "Roles swapped by mistake: the participant's tag recoded as researcher, the moderator's as "
        "participant. The quotes are set aside, not lost; the roster has to say so.",
        [("get_project_overview", {}), ("search_quotes", {"participant": "p1"})],
        lambda s: (lambda r1: [
            check(r1["visible_quotes"] == 0, "the session shows no visible quotes"),
            check(any(sp.get("quotes_set_aside") == 3 and sp["role"] == "researcher"
                      and sp.get("slot_code") == "p1" for sp in r1["speakers"]),
                  "the row for the tag p1 now says researcher, with exactly 3 quotes set aside "
                  "(four were extracted; the researcher hid one, and a hidden quote is not counted)"),
            check(any(sp["role"] == "participant" and sp["visible_quotes"] == 0
                      for sp in r1["speakers"]),
                  "the moderator's tag now reads as a participant with nothing to show")])(
            next(r for r in s[0]["result"]["sessions"]["items"] if r["session_id"] == "s1")))

    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--",
                            "bristlenose/server", "desktop/mcpb"],
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        commit += "+uncommitted"  # the run imports the working tree, not the commit
    payload = {
        "commit": commit, "instructions": build_instructions(), "prompts": results,
        "live": load_live(), "live_findings": LIVE_FINDINGS,
        "note": "Synthetic study. Tool calls chosen by hand, not by a live model; outputs are real "
                "results of the server's tool functions at this commit. The checks were written by "
                "the same author that chose the calls: a tick means that one-line claim holds, not "
                "that the answer is good. Judge the output, not the ticks.",
    }
    OUT.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    template = Path(__file__).with_name("lab-template.html").read_text(encoding="utf-8")
    blob = json.dumps(payload, default=str).replace("</", "<\\/")  # never close the script early
    (ROOT / "docs" / "mockups" / "mcp-lab.html").write_text(
        template.replace("__DATA__", blob), encoding="utf-8")
    bad = [(r["id"], c["text"]) for r in results for c in r["checks"] if not c["ok"]]
    print(f"{len(results)} prompts, {sum(len(r['checks']) for r in results)} checks, "
          f"{len(bad)} not met")
    for b in bad:
        print("  NOT MET:", b)


if __name__ == "__main__":
    main()
