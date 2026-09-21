# Bristlenose — Ukrainian wording check

Bristlenose turns a folder of user-interview recordings into a browsable report
— quotes, themes, sentiment. One of its five lenses was called **Analysis** and
is now called **Signals**, and that rename left five sentences describing the
old name in every language but English. They are fixed, and **everything below
is a first draft I wrote, not a translation anyone has checked.**

Two of the five are worth knowing the history of, because the English moved
twice in one day:

- **The definition came back.** Before the rename the sentence read *"the
  analysis page surfaces signals — statistically notable concentrations of
  sentiment within report sections"*, and that dash was the only place the
  product said **what a signal is**. The rename dropped it, so the next
  sentence talked about *strong and moderate signals* without the term ever
  being introduced. The English is now definition-first: *"Signals are
  statistically notable concentrations of sentiment within report sections."*
- **A pronoun was pointing at the wrong noun.** The empty state said *"apply
  codebook tags to generate **them**"* — and in thirteen languages the nearest
  candidate for *them* was **the tags**, which invites *apply tags to generate
  tags*. Your language was one of the five where the pronoun form matched the
  tags noun *exactly*, so the wrong reading was the easier one. It now names
  the noun.

Where your language's own earlier wording already carried the definition, I
reused it verbatim rather than re-translating — so the clause in the middle of
those sentences is the one a predecessor already wrote. The copula and the
subject at the front are mine, and they are what I would most like checked.

**Context you should have: nobody has ever reviewed the Ukrainian**, and no
qualitative-analysis tool ships a Ukrainian interface at all — MAXQDA, NVivo and
Taguette all lack one. So there is no prior art to defer to for the domain
terms, and your reading is the only authority available. There is one open
question older than this round that matters more than anything in it — see the
last section.

## The five new strings

```
Завантаження сигналів…
Сигналів поки немає. Запустіть конвеєр або застосуйте теги кодової книги, щоб згенерувати сигнали.
Помилка сигналів тегів: {{error}}
Сигнали — це статистично помітні концентрації настрою в розділах звіту. Сильні й помірні сигнали підкреслюють, де досвід учасників групується.
Сигнали — це статистично помітні концентрації настрою або тегів кодової книги в розділах звіту. Два типи карток сигналів.
```

## Where I'd value your steer

### «Сигнали — це …»  ·  I chose the definition idiom deliberately
- **What we use now:** «Сигнали — це статистично помітні концентрації…»
- **Also in play:** «Сигнали становлять…», or a plain dash without *це*
- **The nuance:** the sentence is doing dictionary work under a heading that
  just says **Сигнали**, and *— це* is the ordinary shape for defining a term.
- **You:** confirm, or pick another?

### «Помилка сигналів тегів»  ·  I think this is clumsy
- **What we use now:** «Помилка сигналів тегів: {{error}}»
- **Also in play:** «Помилка під час обробки сигналів тегів», «Помилка
  обчислення сигналів тегів»
- **The nuance:** three nouns in a genitive chain. The previous wording had the
  same shape with *аналізу* in its place, so this is **not new** — but it was
  already awkward.
- **You:** tolerable in an error label, or name the action?

### Number, where English is singular  ·  quick check
- English says *Tag signal error*, singular; I went plural, as fourteen locales
  did by reusing their own *Сигнали тегів*. Confirm?

## Quick confirms — all first-draft, none reviewed

- **«Сигналів поки немає.»** — the empty state. The instruction now names the
  noun (*щоб згенерувати сигнали*) instead of the pronoun *їх*, which is the fix
  described at the top: *їх* sat two words after *теги*.
- **«конвеєр»** for *pipeline* — already in the file, unchanged.
- **Intensity tooltip** — «Середня емоційна інтенсивність (1–3)». The range said
  0–3 in every language including English; the scale has always been 1–3.
- **«Сигнали»** as the lens name — our own coinage, not a QDA term anywhere.
- **A *Signals view* phrasing existed for a few hours and is gone.** I had
  written «У поданні «Сигнали» …» and was already uneasy: *подання* carries a
  strong everyday sense of *submission / filing* (*подання документів*), so it
  risked reading as *in the Signals submission*. The definition-first rewrite
  removed the construction, so nothing depends on it now. If a future string
  needs the word, this is the trap.

## The older question, and the bigger one

**What is a Codebook in Ukrainian?** The files say **«кодова книга»** ×30. The
glossary said *«Книга кодів»* until 20 Sep 2026, when it was corrected to match
the files — but that resolved a contradiction, not the question: both had been
written by the same machine pass, so no human ever chose.

Wikipedia attests **both** forms — *кодова книга* in the lede, *книга кодів* as
the title — and, as noted above, no tool ships Ukrainian to copy from. One
machine-seeding error was fixed in the same pass and is a useful measure of how
much trust to extend: two strings said **«кодувальник»**, which means *a coder*
— a person, not a codebook.

One grammatical note from that fix, in case it reads oddly: *уже* became **вже**
in one string, because the у/в alternation follows the preceding sound and the
noun change put a vowel there.

**You:** *кодова книга* or *книга кодів*, for a qualitative-research audience?
