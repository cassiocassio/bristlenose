# -*- coding: utf-8 -*-
"""§9 data: wide vocabulary + glyph exploration. Imported by build_valence.py."""

# risk: how well the word survives 21 locales.  low = ordinary word or productive
# negation in every language.  high = metaphor or loanword (the ja test: our own
# four were ALL katakana-transliterated — サクセス/ギャップ/テンション/リカバリー).
FRAMES = [
 ("A", "The evidence", "What the quote set looks like. Says nothing about the experience — "
  "this is the frame <code>tension</code> actually belongs to, and the reason it never matched its siblings.",
  [("aligned","divided","adverse","turning","med","‘adverse’ is latinate — clean in Romance, loanword-ish in ja/ko"),
   ("consistent","split","contrary","reversing","med","‘split’ is short and concrete; ‘contrary’ is bookish"),
   ("unanimous","contested","uniform","shifting","high","‘unanimous’ is long in every language and legalistic in most"),
   ("agreed","mixed","opposed","turning","low","all four are everyday words with everyday equivalents")]),

 ("B", "Against the ideal", "The relation between the evidence and the standard the tag names. "
  "The construct the prompt actually describes — but only 40% of cards have an ideal to meet.",
  [("met","partly met","unmet","met late","low","<b>negation-pair</b>: every language has productive negation, so this is one lexical hit, not two"),
   ("satisfied","partly satisfied","unsatisfied","satisfied late","low","same negation trick; longer, and collides with the <code>satisfaction</code> sentiment tag"),
   ("upheld","uneven","breached","restored","high","‘upheld/breached’ is legal register; ‘restored’ is clinical"),
   ("cleared","partial","missed","cleared late","med","‘cleared’ reads as a test result — precise, but implies a threshold nobody set")]),

 ("C", "The lived experience", "How it went for the person. Survives a study with no product in it — "
  "which 9 of the 24 <code>success</code> cards need, being oral history and life interviews.",
  [("worked","mixed","didn’t work","worked out","low","plain speech; ‘work’ is idiomatic in English but the sense exists everywhere"),
   ("smooth","bumpy","blocked","unblocked","med","tactile metaphor; ‘bumpy’ travels worse than it reads"),
   ("held up","gave way","fell down","picked up","high","phrasal verbs are the single worst category for translation"),
   ("went well","went both ways","went badly","came good","med","honest and dull; length varies a lot across locales")]),

 ("D", "Needs and wants", "Your framing — goals, desires, needs, wants. Already the register the model "
  "writes in when the group is Motivation: <i>“the deeper job driving this IKEA visit”</i>.",
  [("served","partly served","underserved","served late","low","‘underserved’ is one negation away; the set is parallel and short"),
   ("need met","need part met","need unmet","need met late","low","most explicit, least elegant; two words is a real cost in a chip"),
   ("wanted &amp; got","got some","wanted, didn’t get","got there","high","a clause, not a label — unusable in 21 locales"),
   ("fulfilled","partial","frustrated","fulfilled late","med","‘frustrated’ collides head-on with the <code>frustration</code> sentiment tag")]),

 ("E", "The plain account", "Maximally dull, maximally translatable. The floor case — what you get if "
  "you decide the label should carry no interpretation at all and let the name do the work.",
  [("positive","mixed","negative","—","low","every locale has all three as ordinary words; no metaphor, no collision"),
   ("good","mixed","bad","—","low","shortest possible; reads as a grade, which may be more than you want to claim"),
   ("praise","mixed","complaint","—","med","about what people <i>said</i>, not what happened — a cleaner subject than it looks"),
   ("+ / ± / −","±","−","—","low","not words at all; maths is the one notation that needs no translation")]),

 ("F", "Strength language", "The prompt’s own instinct. Step 4’s worked example is "
  "<i>“Feedback + all positive → <b>Feedback strength</b>”</i> — it reaches for <i>strength</i>, "
  "not the <code>success</code> it just defined.",
  [("strength","split","shortfall","recovery","high","two independent lexical hits per locale, both metaphors"),
   ("strong","mixed","weak","improving","low","adjective ladder; obviously ordinal, obviously translatable"),
   ("works well","works partly","doesn’t work","works late","med","the honest phrase; too long for a chip, fine for a filter menu")]),
]

GLYPHS = [
 ("Status marks", "✓ ✕ ⚠ !", "highest recognition of any family, and the wrong speaker: these are the "
  "vocabulary of <i>system</i> status — job succeeded, job failed. Here the claim is about the experience "
  "under study, not about Bristlenose.",
  [("✓","success"),("✕","gap"),("⚠","tension"),("↻","recovery"),("!","gap"),("✗","gap"),("☑","success")]),

 ("Harvey balls", "○ ◔ ◑ ◕ ●", "the consumer-reporting ordinal set. No colour, no language, no nominal "
  "problem — the glyph <b>is</b> the proportion. Renders at text size beside the name. The one family that "
  "encodes §2’s ordinal reading directly.",
  [("○","gap"),("◔","tension"),("◑","tension"),("◕","tension"),("●","success")]),

 ("Fill / quantity", "▰▱ █▓▒░", "the same idea as blocks rather than circles. More legible small, uglier "
  "large, and the block characters have the worst cross-platform metrics of anything here.",
  [("▱▱▱","gap"),("▰▱▱","tension"),("▰▰▱","tension"),("▰▰▰","success"),("░","gap"),("▒","tension"),("▓","tension"),("█","success")]),

 ("Direction / trend", "↑ ↓ ↗ ↔", "arrows assert change over time. Honest only for <code>recovery</code> — "
  "which §2 shows is a sort-key artefact — so this family is mostly claiming something the data cannot support.",
  [("↑","success"),("↓","gap"),("↔","tension"),("↗","recovery"),("⇄","tension"),("⤴","recovery"),("→","tension")]),

 ("Geometric valence", "▲ ▼ ◆", "borrowed from finance, and inverted in exactly the markets red/green is — "
  "▲ is red-for-up in Shanghai, Tokyo and Taipei. Same contested space, one channel further in.",
  [("▲","success"),("▼","gap"),("◆","tension"),("◇","tension"),("◢","recovery")]),

 ("Typographic", "+ − ±", "maths needs no translation and no colour, and <code>±</code> is genuinely the "
  "right sign for mixed evidence. Sets small and cleanly. Reads as arithmetic, which may be too cold for a "
  "human finding.",
  [("+","success"),("−","gap"),("±","tension"),("∓","recovery"),("+−","tension")]),

 ("Containment", "⊕ ⊖ ⊘", "circled operators — more presence than bare signs, less shouty than filled marks. "
  "Poor font coverage below 12px in Segoe.",
  [("⊕","success"),("⊖","gap"),("⊙","tension"),("⊘","gap"),("◉","success")]),

 ("Faces", "☺ ☹", "instant comprehension, and the wrong register for a deliverable a researcher hands to a "
  "client. Reads as an emoji rating widget. Listed to be ruled out.",
  [("☺","success"),("☹","gap"),("☻","tension")]),
]
