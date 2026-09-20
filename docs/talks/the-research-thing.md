# The Research Thing

_Talk material for demoing Bristlenose to researchers. Started 20 Sep 2026._

Slides are `##` headings, separated by `---`. Everything under **Speaker notes**
stays off the slide. Keep slide bodies short enough to read from the back of a
room — if it needs a second breath, it belongs in the notes.

> **⚠️ Status check before you present this.** The two slides below describe
> decision logic that is **designed and measured, not shipped**. As of
> 20 Sep 2026 the card still shows one quote, orders them by participant and
> clock, and labels the sentiment card `Sentiment`. Either present this as
> *how we're building it* or check `docs/design-signal-card.md` §9 for what has
> landed since. Do not demo it as live behaviour.

---

## How a card gets its name

Every card gathers the quotes from one place in your study — a section, or a
theme. The label says how that place felt.

**Name the feeling where you can. Refuse where you can't.**

| What's there | What it's called |
|---|---|
| One feeling, or several pulling the same way | **Delight** |
| Feelings pulling both ways, and plenty of them | **Frustration** |
| Feelings pulling both ways, and not much of it | **Mixed sentiments** |

> **It's the amount of feeling that decides, not the balance.**
>
> Three negative to one positive, on a handful of quotes → *Mixed sentiments*
> Eighteen to twelve, across a lot of them → *Frustration*

**Speaker notes**

The counterintuitive line is the one to land: *amount, not balance*. Most people
assume a 3-to-1 split is a clearer result than a 60/40 one. It isn't, if the
3-to-1 is three quotes. A strong ratio on thin evidence is a coincidence; a weak
ratio on thick evidence is a finding.

Why refuse at all. `Mixed sentiments` on its own tells you nothing — so it has
to earn its place. It means *inconsistent responses, worth investigating*, not
*the numbers were close*. If the card can honestly name a feeling, it should,
because a named feeling is something you can act on.

Why not the majority alone. Because in ten interviews two or three people will be
confused about something, whatever you build. A little friction inside a good
result is the normal condition, not a finding — so a small opposing minority
doesn't flip the label. It stays visible in the quotes, which is the next slide.

**Honest caveat if asked how we know.** The rule is fitted to 27 judgements a
researcher made on real cards, with the label hidden. It is small, and most of
those cards came from short test sessions rather than full studies. We know the
*shape* is right — volume decides, not ratio — and we expect the exact cut-off
to move as we see more real data.

**Likely question — "what about surprise?"** Surprise is neither good nor bad, so
it never makes a card mixed. A place with nothing but praise and one surprised
remark is still a positive place.

---

## Which quotes you see

A card shows four quotes. Most cards have more — some have fifty.

**Three that carry the finding. One held back for someone who disagreed.**

That fourth slot only goes to a dissenting voice that said it with force. A
passing remark doesn't take it. A clear, strong one does.

> One voice in five, said clearly and with feeling, has earned the right to be
> seen.

**Speaker notes**

This is the slide researchers tend to react to, because the obvious design is
the wrong one. The obvious design shows the quotes that prove the label — and a
card that only ever agrees with itself is a card you stop reading.

What it replaces. Quotes used to appear in the order they were said, by
participant. That sounds neutral and isn't: on a fifty-quote card the four you
saw were whatever the first participant happened to say early on, which told you
very little about the card. Two cards about the same place would often open with
the same sentence.

The measured result, if you want a number: cards where none of the visible
quotes supported the label went from three to zero, and cards showing a
dissenting voice went *up*, from thirteen to sixteen. Better grounded and more
argumentative at the same time — which is not the trade you'd expect.

**What we can't do yet.** We pick the dissenting voice on how forcefully it was
said, because force is the only thing we measure per quote. The thing we'd
rather use is clarity — someone quiet and sharp beats someone loud and muddy —
and we don't have it. That's an open piece of work, not a solved one.

**Likely question — "can I see the rest?"** Yes. The four are what the card
shows at rest; the whole set is one click away, and nothing is ever discarded.

---

## Slides to write

- **What a signal is** — the concentration idea, in one picture. This is the
  concept everything else rests on and there's no slide for it yet.
- **Why the report is a file you own** — the outcome and the artefact, not the
  machinery.
- **What we don't do** — the negative roadmap. Researchers trust a tool more
  when it says what it won't try to decide for them.
