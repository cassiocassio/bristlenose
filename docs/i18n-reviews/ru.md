# Bristlenose — Russian wording check

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

**Context you should have: nobody has ever reviewed the Russian.** It was
machine-seeded and is one of nine locales shipping that way, so this is the
first native read. There is also one open question older than this round that
matters more than anything in it — see the last section.

## The five new strings

```
Загрузка сигналов…
Сигналов пока нет. Запустите конвейер или примените теги кодировочной книги, чтобы создать сигналы.
Ошибка сигналов тегов: {{error}}
Сигналы — это статистически заметные концентрации настроения внутри разделов отчёта. Сильные и умеренные сигналы показывают, где кластеризуется опыт участников.
Сигналы — это статистически заметные концентрации настроения или тегов кодировочной книги внутри разделов отчёта. Два типа карточек сигналов.
```

## Where I'd value your steer

### Uninstall and Delete are the same word  ·  ru `Удалить` ×3

Three rows sit in one open menu: uninstalling a codebook, deleting a code, and
deleting a code group. English distinguishes them **in the verb** — Uninstall is
reversible, Delete is not, and the Library can reinstall what you uninstalled.
In your language all three currently read ru `Удалить` ×3, so nothing signals that one
of them is recoverable and two are permanent.

The objects differ, so the rows are tellable apart. The question is whether that
is enough, or whether the uninstall row should carry a longer, unambiguous form.

**Please don't feel you have to reach for a dictionary word.** We measured the
obvious candidates against Apple's own system strings and they appear **zero
times** — `Afinstaller`, `Deïnstalleer`, `Poista asennus`, `Деинсталлировать`, `설치 제거` — while the verb you
already have is exactly what Apple ships for Uninstall. So the seeded word is
right *and* the collision is real, at the same time. Danish and Korean happen to
avoid it because their delete verb differs.

One candidate, to accept or reject: no good alternative measured — this one may need inventing.

### «Сигналы — это …»  ·  I chose the definition idiom deliberately
- **What we use now:** «Сигналы — это статистически заметные концентрации…»
- **Also in play:** «Сигналы представляют собой…», or a plain dash without
  *это*
- **The nuance:** I used *— это* because this sentence is doing dictionary work
  under a heading that just says **Сигналы**, and *— это* is the ordinary
  Russian shape for defining a term. A plain dash is more formal; *представляют
  собой* is more technical-register.
- **My hunch:** *— это* is right for UI help text read by a practitioner.
- **You:** confirm, or would you pick one of the others?

### «Ошибка сигналов тегов»  ·  I think this is clumsy
- **What we use now:** «Ошибка сигналов тегов: {{error}}»
- **Also in play:** «Ошибка при обработке сигналов тегов», or «Ошибка расчёта
  сигналов тегов»
- **The nuance:** three nouns in a genitive chain, which Russian style guides
  discourage. The previous wording had the same shape with *анализа* in place of
  *сигналов*, so this is **not new drift** — but it was already awkward and I
  have made it no better.
- **My hunch:** naming the action («при обработке» / «расчёта») breaks the chain
  and reads properly.
- **You:** is the bare chain tolerable in an error label, and if not, which verb
  noun would you use?

### Number, where English is singular  ·  quick check
- **The nuance:** English says *Tag signal error*, singular. I went plural
  (*сигналов тегов*), which fourteen locales did independently by reusing their
  own section name *Сигналы тегов*. Coherent, but a deliberate departure from
  the source.
- **You:** plural as it stands?

## Quick confirms — all first-draft, none reviewed

- **«Загрузка сигналов…»** — nominal progress style, matching the file's other
  *Загрузка…* lines.
- **«Сигналов пока нет.»** — the empty state. The instruction now names the noun
  (*чтобы создать сигналы*) instead of the pronoun *их*, which is the fix
  described at the top: *их* sat two words after *теги* and read as *to create
  the tags*.
- **«конвейер»** for *pipeline* — already in the file, unchanged.
- **Intensity tooltip** — «Средняя эмоциональная интенсивность (1–3)». The range
  said 0–3 in every language including English; the scale has always been 1–3.
- **«Сигналы»** as the lens name — our own coinage, not a QDA term in any
  language. Note Apple's Russian ships *Signal* as **«Позывной»** (a call sign,
  in its radio sense), which is exactly why we do not borrow the platform word
  here.
- **A *Signals view* phrasing existed for a few hours and is gone.** I had
  written «В представлении «Сигналы» …», choosing *представление* over Apple's
  *Вид* because «в виде «Сигналы»» reads as *in the form of signals*. The
  definition-first rewrite removed the construction entirely, so no Russian
  string now names a lens. Recorded in case a future string needs one.

## The older question, and the bigger one

**What is a Codebook in Russian?** The files say **«кодировочная книга»** ×30.
The glossary said *«Книга кодов»* until 20 Sep 2026, when it was corrected to
match the files — but that resolved a contradiction, not the question, because
both had been written by the same machine pass with no human in the loop.

What the prior art says, measured 20 Sep 2026:

- MAXQDA's Russian interface calls the code system **«Система кодов»**; its
  Codebook label was not found in any localised material.
- **«кодировочная книга»** is the established **survey-methodology** term.
- The **qualitative** literature tends to **«кодировочная схема»**.
- **«книга кодов»** is what Simon Singh's cipher book is called in Russian.

So the shipped term may be from the wrong branch of the field. Two further
machine-seeding errors were fixed in the same pass and are worth knowing about
as a measure of how much trust to extend: two strings said **«кодировщиков»**
(*of coders*, people) where a codebook was meant, and two more said **«кодовый
справочник»**.

**You:** *кодировочная книга*, *кодировочная схема*, or something else — for a
qualitative-research audience?
