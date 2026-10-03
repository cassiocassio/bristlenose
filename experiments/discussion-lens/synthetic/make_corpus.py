#!/usr/bin/env python3
"""Build the synthetic Discussion-lens corpus with planted ground truth.

Everything here is invented: a weekly-food-shop study, three sessions, no real
participant. The session scripts below carry their labels inline, so the
transcripts and the gold file come from ONE source and cannot drift apart.

Writes, next to this file:
  guide.md              the discussion guide as a researcher would write it
  transcripts/sN.txt    Bristlenose transcript format ([mm:ss] [code] text)
  gold.json             per-turn and per-quote labels (the answer key)

What the corpus plants, on purpose:
  - planned items asked reworded and out of order; one never asked (g2.3)
  - session 2 runs Delivery before Ordering (flow ≠ guide order)
  - ad-libs on topic (unplanned follow-ups inside a planned section)
  - "budget": a new line of enquiry in all three sessions, 4 distinct
    questions → must be PROMOTED to its own section (≥2 sessions, ≥3 items)
  - "recipes": a tangent in session 2 only, 3 questions → must NOT be
    promoted (one session); placed by flow or standalone
  - chit-chat, logistics and consent turns that are not questions
  - s3@ an answer that drifts to budget while the last question was about the
    app: the conversational anchor and the topic disagree on purpose

Script line grammar (one per turn):
  M <label> | text        moderator turn
  P <section> | text      participant turn (a quote when it is substantive)
  M labels:  instr | chat | plan:<item> | adlib:<section>:<key> | new:<cluster>:<key>
  P section: g1..g5 | new:<cluster> | chat
Each moderator question's <key> names the item it belongs to, so the same
question asked in two sessions shares a key (planned items use their guide id).

Run:  python3 experiments/discussion-lens/synthetic/make_corpus.py
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

GUIDE = """# Weekly food shop — discussion guide

## Consent and recording
- Confirm consent to record, and that they can stop at any time

## 1. About you
- Tell me a little about yourself and who you live with
- How often do you do a "big shop"?

## 2. Planning the week
- How do you decide what to buy each week?
- Do you write a list? Where does it live?
- Who else has a say in what gets bought?
- What happens when plans change mid-week?

## 3. Ordering in the app
- Walk me through the last time you ordered
- What's hard to find?
- How do you feel about substitutions?

## 4. Delivery and collection
- How do you choose a delivery slot?
- Have you ever collected instead of having it delivered?
- Tell me about a time a delivery went wrong

## 5. Wrap-up
- If you could change one thing about the app, what would it be?
- Anything else you'd like to add?
"""

# Gold spine: ids in guide order. g0 is the instruction section.
SPINE = {
    "g0": ("Consent and recording", "instruction", ["g0.1"]),
    "g1": ("About you", "questions", ["g1.1", "g1.2"]),
    "g2": ("Planning the week", "questions", ["g2.1", "g2.2", "g2.3", "g2.4"]),
    "g3": ("Ordering in the app", "questions", ["g3.1", "g3.2", "g3.3"]),
    "g4": ("Delivery and collection", "questions", ["g4.1", "g4.2", "g4.3"]),
    "g5": ("Wrap-up", "questions", ["g5.1", "g5.2"]),
}
ITEM_TEXT = {
    "g0.1": "Confirm consent to record, and that they can stop at any time",
    "g1.1": "Tell me a little about yourself and who you live with",
    "g1.2": 'How often do you do a "big shop"?',
    "g2.1": "How do you decide what to buy each week?",
    "g2.2": "Do you write a list? Where does it live?",
    "g2.3": "Who else has a say in what gets bought?",
    "g2.4": "What happens when plans change mid-week?",
    "g3.1": "Walk me through the last time you ordered",
    "g3.2": "What's hard to find?",
    "g3.3": "How do you feel about substitutions?",
    "g4.1": "How do you choose a delivery slot?",
    "g4.2": "Have you ever collected instead of having it delivered?",
    "g4.3": "Tell me about a time a delivery went wrong",
    "g5.1": "If you could change one thing about the app, what would it be?",
    "g5.2": "Anything else you'd like to add?",
}

S1 = """
M chat | Hi Asha, can you hear me okay? The connection seems a bit choppy.
P chat | Yes, I can hear you fine now, it was frozen for a second.
M instr | Before we start, are you happy for me to record this? You can stop at any point.
P chat | Yes, that's absolutely fine with me, go ahead and record.
M plan:g1.1 | So to begin, tell me a little bit about yourself and who's at home with you.
P g1 | I live in a terraced house in Leeds with my partner and our two kids, who are seven and ten, so the fridge empties quickly.
M plan:g1.2 | And how often would you say you do a proper big shop?
P g1 | Once a week, usually Sunday evening, and then there's always a top-up shop on Wednesday for milk and bread.
M plan:g2.1 | How do you decide what actually goes in the basket each week?
P g2 | I look at what we've got in the cupboards first, then I plan maybe four dinners and fill in the gaps around those.
M plan:g2.2 | Do you write it down as a list at all?
P g2 | Always, there's a shared note on my phone that my partner adds to whenever we run out of something.
M adlib:g2:list-medium | Is that note something you'd ever print out, or is it always the phone?
P g2 | Always the phone, paper lists just get lost in my coat pocket and then I'm stood in the kitchen guessing.
M new:budget:set-budget | Do you set yourselves a budget for the week?
P new:budget | We try to keep it under a hundred and twenty pounds, but it creeps up every month without us really noticing.
M new:budget:track-spend | How do you keep track of what you're actually spending?
P new:budget | Honestly I just watch the running total in the basket and start taking things out when it goes over a hundred.
M plan:g2.4 | What happens when the week's plans change halfway through?
P g2 | Then the vegetables go off, that's the honest answer, and I feel guilty throwing half a bag of spinach away.
M chat | Right, that makes sense, thank you.
M plan:g3.1 | Can you walk me through the last time you ordered in the app?
P g3 | I opened the favourites tab, ticked most of last week's things, then searched for the odd extra like birthday candles.
M plan:g3.2 | Was anything hard to find?
P g3 | The candles, actually, I searched three different ways and it kept showing me candle-shaped cake toppers instead.
M plan:g3.3 | How do you feel about substitutions?
P g3 | They make me nervous, last time they swapped oat milk for a chocolate oat drink and my son was delighted but I wasn't.
M plan:g4.1 | How do you choose which delivery slot to book?
P g4 | I book the cheapest one on Sunday night, even if it means unpacking shopping at nine o'clock when I'm exhausted.
M plan:g4.2 | Have you ever collected it yourself instead?
P g4 | Once, when the slots were all gone before Christmas, and the car park pickup was quicker than I expected it to be.
M plan:g5.1 | If you could change one thing about the app, what would it be?
P g5 | Let me lock substitutions per item, so the milk is never swapped but the bread can be anything at all.
M plan:g5.2 | Is there anything else you'd like to add before we finish?
P chat | No, I think that's everything, thanks.
M chat | Brilliant, thank you so much for your time today Asha.
"""

S2 = """
M chat | Hello Ben, thanks for joining, let me just share my screen.
M instr | I'm going to record the session if that's okay with you, and you can stop it whenever you like.
P chat | Sure, that's no problem at all for me.
M plan:g1.1 | Could you start by telling me about yourself and your household?
P g1 | It's just me and my flatmate in Bristol, we split some things but mostly shop separately for our own meals.
M plan:g4.1 | Since you mentioned your evenings are busy, how do you pick a delivery slot?
P g4 | I pick whatever's free after eight, because I'm never home before then and I hate the idea of a missed delivery.
M plan:g4.3 | Has a delivery ever gone wrong for you?
P g4 | The driver once left everything with a neighbour I'd never met, and the frozen stuff had defrosted by the time I found it.
M adlib:g4:missed-fix | What did the shop do to put that right?
P g4 | They refunded the frozen items after I sent photos, but it took two separate chats with the support bot to get there.
M plan:g2.1 | Going back a step, how do you decide what to buy each week?
P g2 | Mostly I follow recipes I've saved, I'll pick three for the week and buy exactly what those need and nothing else.
M new:recipes:which-app | Which app do you keep your recipes in?
P new:recipes | A free recipe app with a meal planner in it, I've been using it for about two years now and it's full.
M new:recipes:to-basket | Does anything go from the recipe app straight into your basket?
P new:recipes | No, I type every ingredient in by hand, which is the most tedious part of the whole weekly routine for me.
M new:recipes:shared | Do you ever share recipes with your flatmate through it?
P new:recipes | Sometimes I send her a link when I've cooked something good, but she never actually makes any of them.
M plan:g3.1 | So once you've got the list, walk me through placing the order.
P g3 | I search item by item from the recipe list, which takes ages because the search doesn't understand quantities at all.
M plan:g3.3 | What do you think about substitutions?
P g3 | I turn them off completely, I'd rather have nothing than the wrong thing turn up when I'm cooking to a recipe.
M new:budget:prices-changed | Have rising prices changed the way you shop at all?
P new:budget | Yes, I've stopped buying branded pasta and sauces, and I buy meat on the reduced shelf whenever I can find it.
M chat | Mm-hm, that's really interesting.
M plan:g5.1 | If you could change one thing about the app, what would that be?
P g5 | Let me paste a whole recipe in and have the app build the basket for me, with the right quantities already worked out.
M chat | Great, thanks Ben, that's all my questions for today.
"""

S3 = """
M chat | Hi Carla, sorry, give me one moment while I get the recording going.
M instr | Just to confirm, you're happy for this to be recorded, and you can ask me to stop at any time?
P chat | Yes, totally fine, no problem at all.
M plan:g1.1 | Tell me a bit about yourself and who you live with.
P g1 | I live with my mum, who doesn't use the internet at all, so I do all of the shopping for both of us now.
M plan:g2.1 | How do you work out what to buy each week?
P g2 | Mum tells me what she fancies on Saturday, and I add the basics we always need on top of whatever she's asked for.
M new:budget:set-budget | And is there a set amount you try to stay within?
P new:budget | Eighty pounds is the limit, because it comes out of mum's pension and she checks the receipt very carefully every week.
M new:budget:offers | Do you go looking for offers at all?
P new:budget | Every single week, I sort by price per kilo and I'll switch brands without a second thought if it saves us money.
M plan:g2.2 | Where do you keep the shopping list?
P g2 | On the fridge, on paper, because mum needs to be able to add things to it herself while I'm out at work.
M plan:g3.1 | Talk me through the last time you placed an order.
P new:budget | I'll be honest, I spent most of that order hunting through the offers page, the actual ordering bit was the quick part.
M plan:g3.2 | Is there anything you find hard to find in there?
P g3 | Mum's particular brand of decaf tea, it's listed under a different name in the app and it took me ages to find it.
M adlib:g3:wrong-sub | What did you do when a substitute came that was wrong?
P g3 | I rejected it at the door, the driver was lovely about it and the refund was on my card the very next morning.
M new:budget:prices-changed | Have you noticed prices going up much lately?
P new:budget | Massively, the same basket is about fifteen pounds more than it was last spring, and mum notices every penny of it.
M plan:g4.1 | And how do you choose your delivery slot?
P g4 | Saturday morning, so mum can be up and dressed when the driver comes and help put things away in the right places.
M plan:g4.3 | Has a delivery ever gone wrong?
P g4 | Once it arrived two hours late, which meant mum had to sit waiting by the window all morning, and she was quite upset.
M chat | Okay, thank you, that's really helpful.
M plan:g5.2 | Is there anything else at all you'd like to tell me?
P g5 | Only that the app should have a simple mode for older people, mum would love to order her own things one day.
M chat | Lovely, thank you Carla, that's us done for today.
"""

SESSIONS = {"s1": ("Asha", "p1", S1), "s2": ("Ben", "p2", S2), "s3": ("Carla", "p3", S3)}


def tc(sec: float) -> str:
    s = int(sec)
    return f"{s // 60:02d}:{s % 60:02d}"


def build() -> None:
    (HERE / "transcripts").mkdir(exist_ok=True)
    (HERE / "guide.md").write_text(GUIDE, encoding="utf-8")
    gold = {"spine": {k: {"title": t, "kind": kind, "items": {i: ITEM_TEXT[i] for i in items}}
                      for k, (t, kind, items) in SPINE.items()},
            "turns": {}, "quotes": [], "sessions": {}}
    for sid, (name, pid, script) in SESSIONS.items():
        clock = 30.0
        lines = []
        for raw in script.strip().splitlines():
            head, _, text = raw.partition(" | ")
            who, label = head.split(" ", 1)
            code = "m1" if who == "M" else pid
            at = clock
            # speaking time from word count, plus a pause; answers run longer
            clock += len(text.split()) / 2.6 + (4 if who == "M" else 9)
            lines.append(f"[{tc(at)}] [{code}] {text}")
            if who == "M":
                kind, _, rest = label.partition(":")
                g = {"kind": {"plan": "planned"}.get(kind, kind), "text": text}
                if kind == "plan":
                    g["item"] = rest
                    g["section"] = rest.split(".")[0]
                elif kind == "adlib":
                    sec, key = rest.split(":")
                    g["section"], g["item"] = sec, f"adlib:{key}"
                elif kind == "new":
                    cl, key = rest.split(":")
                    g["section"], g["item"] = f"new:{cl}", f"new:{key}"
                gold["turns"][f"{sid}@{tc(at)}"] = g
            elif label != "chat":
                gold["quotes"].append({"session_id": sid, "participant_id": pid,
                                       "start": round(at, 2), "time": tc(at),
                                       "text": text, "section": label})
        header = (f"# Transcript: {sid}\n# Source: synthetic\n# Duration: {tc(clock)}\n"
                  "# Language: en\n\n")
        (HERE / "transcripts" / f"{sid}.txt").write_text(header + "\n\n".join(lines) + "\n",
                                                         encoding="utf-8")
        gold["sessions"][sid] = {"name": name, "participant_id": pid, "duration": tc(clock),
                                 "seconds": round(clock, 1)}
    (HERE / "gold.json").write_text(json.dumps(gold, indent=1, ensure_ascii=False) + "\n",
                                    encoding="utf-8")
    kinds = [t["kind"] for t in gold["turns"].values()]
    print(f"{len(gold['turns'])} moderator turns "
          f"({', '.join(f'{k} {kinds.count(k)}' for k in sorted(set(kinds)))}), "
          f"{len(gold['quotes'])} quotes, sessions "
          + ", ".join(f"{s} {v['duration']}" for s, v in gold["sessions"].items()))


if __name__ == "__main__":
    build()
