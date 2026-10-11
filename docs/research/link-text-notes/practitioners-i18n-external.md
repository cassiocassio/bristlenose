# Link labels and CTA microcopy: practitioner guidance, external links from a desktop app, and localising short labels

Research notes, 11 Oct 2026. Context: replacing "Learn more" links on the desktop Welcome screen cards with labels that tell the reader where they lead ("information scent"), then translating them into about 20 languages.

**How sure each claim is.** Each claim is tagged with how it was seen:
- **VERIFIED**: I fetched the source page in this session and read the text.
- **SEARCH-SUMMARY**: I saw it only in a search engine's summary and did not open the page.
- **NOT FOUND**: I could not get to the claim from any source.

The books themselves (Yifrah, Podmajersky, Redish, Krug, Richards) were not readable. No book content below is verified against the book.

## 1. What practitioner books and experts say about link text and CTAs

### Takeaway
Every source I could actually read agrees on four rules:
- Name the destination, or what the reader will get there, in the link text.
- Put the key words first.
- Where possible, use the destination page's own title as the link text.
- Never use bare "Learn more", "Read more" or "Click here".

Guidance on grammatical form is split by what the link does:
- A link that **starts a task** opens with a verb (GOV.UK; Apple HIG for buttons).
- A link that **goes to something to read** is best named by its destination (NN/g; Microsoft).

The books named in the brief could not be checked directly, so their specific positions are unverified.

### Cited Findings
- **NN/g (Katie Sherwin, 13 Dec 2015), "Learn More Links: You Can Do Better"**: generic "Learn more" has weak information scent. The "lack of descriptive keywords is a serious problem for accessibility", and readers can't tell whether several "Learn more" links go to the same page or to different ones. It gives three fixes, in order of preference:
  1. Use keywords that describe the destination, front-loaded. Its example is "Cook Squash Like The Pros" rather than "Learn How Professional Chefs Cook Squash".
  2. Add a qualifier ("Learn more about our services").
  3. Make the preceding heading itself the link.

  VERIFIED. [NN/g](https://www.nngroup.com/articles/learn-more-links/)
- **GOV.UK content guidance**, the house style of the content-design discipline Sarah Richards founded at GDS. That attribution is from background knowledge and was not checked this session. The guidance says:
  - "make it descriptive and avoid generic text like 'click here' or 'more'"
  - "frontload it with relevant terms"
  - "Consider using the title of the page the link goes to as your link text."
  - "If your link takes the user to a page where they can start a task, start your link with a verb. For example, 'Send a tax return'."
  - "tell users if the link will take users off GOV.UK – for example, 'Find a counsellor on Counselling Directory'"

  VERIFIED. [GOV.UK guidance](https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/writing-guidelines/add-links/)
- **Microsoft Writing Style Guide, "Search and writing"**:
  - "Write short link text (four or fewer words) that's descriptive and includes keywords."
  - "If it works, use the title or description of the target page as link text."

  VERIFIED. [Microsoft Style Guide](https://learn.microsoft.com/en-us/style-guide/search-writing)
- **Microsoft Fluent 2, Link component**:
  - "Avoid using 'Learn more' links without specifying what someone will learn more about."
  - "People should be able to accurately predict the purpose of a link based on its link text. Don't use URLs or generic text like 'Click here'…"

  VERIFIED. [Fluent 2 Link usage](https://fluent2.microsoft.design/components/web/react/core/link/usage)
  - A search summary also said Microsoft allows "Learn more" when context makes the destination clear, and suggests an `aria-label` when vague text can't be avoided. I did not see this sentence on the Fluent page I fetched. SEARCH-SUMMARY. [search result list incl. Fluent/Windows Admin Center guide](https://learn.microsoft.com/en-us/windows-server/manage/windows-admin-center/extend/guides/ui-text-style-guide)
- **Apple HIG, Buttons** (applies to buttons, not links): "consider starting the label with a verb to help convey the button's action — for example… 'Add to Cart.'" VERIFIED. [Apple HIG Buttons (JSON data of the page)](https://developer.apple.com/tutorials/data/design/human-interface-guidelines/buttons.json)
- **Steve Krug, *Don't Make Me Think***: the name of each page should match the words the reader clicked to get there. The summaries quote his "Hot mashed potatoes" example, where a link saying that leads to a page named that, and call it a crucial agreement between site and user. This is the source of "match link text to the destination title". SEARCH-SUMMARY only, from secondary summaries, not the book. [Goodreads Krug quotes](https://www.goodreads.com/work/quotes/561281-don-t-make-me-think-a-common-sense-approach-to-web-usability); [Medium summary](https://medium.com/design-bootcamp/dont-make-me-think-by-steve-krug-key-takeaways-and-real-life-examples-97f19e8d1ee8)
- **Ginny Redish, *Letting Go of the Words***: the book has a chapter titled "Writing Meaningful Links" (Ch. 12, 2nd ed.). I could not see its contents. Only the chapter's existence is confirmed. [Perlego listing](https://www.perlego.com/book/1810094/letting-go-of-the-words-writing-web-content-that-works-pdf); [Elsevier](https://shop.elsevier.com/books/letting-go-of-the-words/redish/978-0-12-385930-3)
- **Torrey Podmajersky, *Strategic Writing for UX*** (2nd ed. 2025 adds LLM content design): I found no publicly visible passage on link text or "Learn more". Goodreads quotes cover her framing that UX text serves both the reader's goals and the organisation's: "the person investigates, verifies, commits to, sets up, uses, fixes…". Her voice chart and "purpose-driven" link wording could not be verified. [Goodreads quotes](https://www.goodreads.com/work/quotes/68652898-strategic-writing-for-ux-drive-engagement-conversion-and-retention-wi); [author book page](https://www.torreypodmajersky.com/content-design-book)
- **UX Content Collective (Alice Chen, undated), "'Learn more' is not enough"**: makes the same case on information scent, screen readers and repetitive clutter, and recommends "always opt for clarity over cleverness". VERIFIED. [UX Content Collective](https://uxcontent.com/learn-more-is-not-enough-a-case-for-descriptive-cta/)
- **Lettercrafted** (a minor source) offers replacements that name the object: "See pricing", "Read the guide", "Compare plans". SEARCH-SUMMARY. [Lettercrafted](https://lettercrafted.com/ux-writing-guide-for-better-labels/)

### Inferences
- The welcome-card links lead to documentation, which means reading, not starting a task. That favours a noun-phrase label naming the destination: ideally the docs page's own title, cut to about 4 words or fewer.
  - Basis: Krug/GOV.UK matching titles, plus Microsoft's four-word limit.
  - A verb-first label ("Read the codebook guide") fits if the house style prefers verbs. GOV.UK reserves verb-first for task-starting links.
- "Promise only what the page delivers" follows from the title-matching rule. If the label is the page title, the label cannot over-promise.
- NN/g's third option, making the card's heading the link, removes the separate link label altogether. That is worth weighing, because it removes a short string to translate (see §3).

### Gaps
- **Kinneret Yifrah, *Microcopy: The Complete Guide***: no accessible text on link labels. Searches returned only book listings. NOT FOUND.
- **Sarah Richards, *Content Design* (book)**: not checked directly. GOV.UK guidance is used as a stand-in, and that is an inference.
- **John Saito, Biz Sanford / Content Design London, UX Writing Hub**: no primary statement on link text found in this session.
- Podmajersky's voice chart and her specific link/button patterns: not verified.

## 2. Links that leave a desktop app for a website or docs

### Takeaway
Apple's macOS rule is for buttons, not links: a trailing ellipsis means "opens another window, view or app where you give more input". It is not a signal for "opens in the browser", and I found no Apple guidance at all on in-app links to web content.

The web sources (GOV.UK, Microsoft Fluent, NN/g) agree on one point: tell people in advance when a link takes them somewhere else, and do it mainly through the link text. An icon (such as ↗ or the "open" icon) is a secondary cue that research suggests many users don't understand.

### Cited Findings
- **Apple HIG on the ellipsis**:
  - "Append a trailing ellipsis to the title when a push button opens another window, view, or app."
  - "…an ellipsis in a control title signals that people can provide additional input."

  VERIFIED. [Apple HIG Buttons JSON](https://developer.apple.com/tutorials/data/design/human-interface-guidelines/buttons.json)
  - **Caution:** the "or app" wording could be read as covering a button that opens the browser. But the stated meaning, that the person can provide more input, does not fit a docs page.
- **Apple HIG on help buttons**:
  - "Use the system-provided help button to display your help documentation."
  - "When possible, open the help topic that's related to the current context."
  - "Avoid displaying text that introduces a help button."
  - Use no more than one per window, and place it within a view, not the window frame.

  The page has no guidance on buttons that link to web content. VERIFIED. [Apple HIG Buttons JSON](https://developer.apple.com/tutorials/data/design/human-interface-guidelines/buttons.json)
- **Older Apple HIG (Leopard era)**: the ellipsis means extra information is needed before the command can run. Its examples are Preferences, Customize Toolbar and Send Feedback. SEARCH-SUMMARY. [Leopard HIG Controls](https://leopard-adc.pepas.com/documentation/UserExperience/Conceptual/AppleHIGuidelines/XHIGControls/XHIGControls.html)
- **Microsoft Fluent 2**: "If a link opens in a new tab or window, be sure to inform people beforehand. Add a visual cue, like the open icon, and an `aria-label` indicating the link goes to a new tab or window." VERIFIED. [Fluent 2 Link](https://fluent2.microsoft.design/components/web/react/core/link/usage)
- **GOV.UK**: say in the link text itself when a link leaves the site ("Find a counsellor on Counselling Directory"). VERIFIED. [GOV.UK](https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/writing-guidelines/add-links/)
- **NN/g (Nielsen & Kaley, 27 Sep 2020), "Opening Links in New Browser Windows and Tabs"**:
  - The default is the same tab.
  - When a link does open a new window or tab, it should be labelled consistently, "with an icon and descriptive text", so people know before they click.

  VERIFIED. [NN/g](https://www.nngroup.com/articles/new-browser-windows-and-tabs/)
- **Users don't reliably understand external-link icons**: a search summary said most users don't understand the external-link icon on first sight, and that users were inconsistent about both the icon and an "Exit" badge. It advised using the link text to show the destination and applying any indicator consistently.
  - The summary seemed to blend an independent blog with NN/g findings, and I did not open the original NN/g study.
  - SEARCH-SUMMARY / unverified. [hey.georgie.nu](https://hey.georgie.nu/hyperlinks/); [USWDS Link](https://designsystem.digital.gov/components/link/)

### Inferences
- On macOS, do **not** put an ellipsis on a label that opens docs in the browser. Apple defines the ellipsis as "more input to come", and a docs page asks for none.
- The desktop-app case is a stronger version of the new-window problem: the user is moved to a different application, the browser. On the Fluent/NN/g reasoning, that warrants warning people beforehand, ideally in the words (for example naming the site, GOV.UK-style). An icon would be a consistent secondary cue.
- A ↗ glyph carries the "leaves the app" meaning better than →, which reads as "next/continue" within the app. **This is my inference only**: no source I read set the two arrows against each other.
- An arrow or icon should be decorative, outside the translatable string, and mirrored or chosen per writing direction (see §3).

### Gaps
- No Apple guidance found on signalling "opens in your browser" from inside a Mac app, and none on the ↗ glyph.
- No primary NN/g article found specifically on external-link icon comprehension. The claim is unverified.
- I did not read the Microsoft Windows/WinUI guidance on hyperlinks that launch the browser.

## 3. Localising short link labels

### Takeaway
Short strings expand the most when translated. IBM's figures, as quoted by the W3C, give 200–300% for English strings of up to 10 characters and 180–200% for 11–20 characters. So a 2–4-word label on a fixed-width card is the riskiest kind of text in the UI.

Ways to keep translations from breaking the layout:
- Let the text wrap or reflow rather than truncate.
- Don't abbreviate to make text fit.
- Keep each label as one complete, standalone string, never built from pieces.
- Keep icons and arrows out of the translatable text.
- Expect languages to use different grammatical forms. German UI convention prefers the infinitive ("Kanäle verwalten") to the imperative.

### Cited Findings
- **W3C Internationalization, "Text size in translation"**, quoting IBM's design guidelines:

  | English length | Expansion |
  |---|---|
  | up to 10 characters | 200–300% |
  | 11–20 | 180–200% |
  | 21–30 | 160–180% |
  | 31–50 | 140–160% |
  | 51–70 | 151–170% |
  | over 70 | 130% |

  The article makes three further points:
  - "the smaller the source message, the higher the likely translation length".
  - Short strings are "more likely to be squeezed into a small space".
  - Don't abbreviate "to make it fit in a restricted space", because many languages have no equivalent abbreviation. Prefer flexible layouts and avoid "small fixed-width containers".

  VERIFIED. [W3C i18n](https://www.w3.org/International/articles/article-text-size)
- **Microsoft Globalization, "String concatenation"** (2024):
  - "Concatenated strings are one of the most challenging issues for translators to resolve."
  - Fragments can be reordered in resource files and lose their context.
  - Word order (Japanese is subject–object–verb), punctuation (Japanese 。, French spacing), word separators (Chinese uses none), adjective agreement (French) and declension (Polish) all break templates built from pieces.
  - Recommended practice: one complete string with placeholders, so "translators have full control over the words, the word order, punctuation, and spacing".
  - Test for concatenation with pseudolocalisation.

  VERIFIED. [Microsoft Learn](https://learn.microsoft.com/en-us/globalization/internationalization/concatenation)
- **Arrows in right-to-left languages**: directional icons such as arrows must be redesigned or mirrored for RTL layouts. A label-plus-icon combination should be one localisable unit, or the icon should stay outside the string, not be joined to it.
  - SEARCH-SUMMARY, from aggregated localisation-blog results; the specific pages were not opened.
  - [Phrase](https://phrase.com/blog/posts/10-common-mistakes-in-software-localization/); [Mozilla l10n dev best practices](https://mozilla-l10n.github.io/documentation/localization/dev_best_practices.html)
- **German form for labels**: Zulip's German translation guide says "Use continuous labels with verbs in infinitive form… e.g., *Manage streams* – *Kanäle verwalten* instead of *Verwalte Kanäle*". VERIFIED. [Zulip German guide](https://zulip.readthedocs.io/en/stable/translating/german.html)
  - Second Life's German guide reportedly says the same (short labels, infinitive). SEARCH-SUMMARY. [Second Life wiki](https://wiki.secondlife.com/wiki/German_Style_Guide)
- **Microsoft language-specific style guides** exist for each language and are downloadable. Microsoft German reportedly writes out "Informationen" rather than "Info". SEARCH-SUMMARY; the guide itself was not read. [Microsoft Localization Style Guides](https://learn.microsoft.com/en-us/globalization/reference/microsoft-style-guides)

### Inferences
- A two-word English label such as "Codebook guide" (14 characters) could plausibly come back at 25–28 characters. The card needs either line wrapping or room for about twice the English width. Truncating with "…" would destroy exactly the destination words the redesign adds.
- Make each label a single string per locale. Don't build "Read the" + {page name} + " →" from parts. Render the arrow or icon in the view, outside the string, so each locale controls word order and the glyph can be mirrored or swapped for RTL. The project currently ships no RTL locale, but the separation costs nothing.
- Noun-phrase labels (the destination's name) are probably safer across languages than English imperatives. Some languages' UI conventions turn imperatives into infinitives or nouns (German infinitive; Japanese UI typically uses nominal forms, which is unverified here). A destination name moves between languages with less change of register.
  - This is an inference from the German evidence.
  - Check it against the project's own per-locale Apple loctable corpus rather than assuming it.
- Using the docs page's real title as the label has a localisation benefit too, as long as the docs page title is itself localised. If the docs exist only in English, a localised label naming an English page is a promise the page can't keep. Consider adding "(English)" or the equivalent.

### Gaps
- I found no verified source on how Japanese, Korean or Chinese conventionally word link text (verb vs noun), and no Apple localisation guidance specific to link labels. Not fetched this session.
- The Microsoft per-language style guides (German, Japanese) were not opened.
- No empirical data found on truncation rates in fixed-width cards.
