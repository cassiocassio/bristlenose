# Usability evidence on link text and CTA microcopy: generic vs descriptive labels

Researched 11 Oct 2026. Fidelity note: pages were read through a fetch tool that summarises. Text in quotation marks is what the tool returned as verbatim, and it is usually accurate. Before publishing any quote, check it against the live page. Anything I saw only in a search-engine summary, and not on the source page, is marked **UNVERIFIED**.

## 1. What Nielsen Norman Group says about "Learn More", "Click here" and scanning links

### Takeaway
NN/g's position is consistent across 2009–2020: a link's words should say what the user will get, and the information-carrying word should come first. This is because scanning users mostly see only the first two words of a link. A bare "Learn More" is a clarity and accessibility weakness, but NN/g does not treat it as catastrophic when the surrounding text makes the destination obvious.

### Cited Findings
- **"'Learn More' Links: You Can Do Better"** by Katie Sherwin, 13 Dec 2015. It names three problems with a bare "Learn More". (a) Weak information scent: it "creates uncertainty, because users don't know what to expect if they click". (b) Accessibility: screen-reader users who pull up a list of links hear a run of identical "Learn More" items. (c) When several "Learn More" links share a page, users cannot tell whether they go to the same place or different places. It offers three fixes: use descriptive keywords that match the destination; keep "Learn more" but add a qualifier ("Learn more about our services"); or make the preceding heading the link. It also concedes that a bare "Learn More" is not "devastating" when the preceding text makes the destination obvious. — [NN/g, Sherwin 2015](https://www.nngroup.com/articles/learn-more-links/)
- **"Writing Hyperlinks: Salient, Descriptive, Start with Keyword"** by Marieke McCloskey, 9 Mar 2014. Its guidance:
  - "People mostly look at the first 2 words of a link."
  - "Don't force users to read the text surrounding a link to determine where it leads."
  - Links "must clearly explain where they will take users".
  - Avoid "Click here" and "Read more". The "Click here" guidance goes back to 1996 and is reinforced by touchscreens, where nobody "clicks".
  - Eye-tracking shows users first scan in an F-pattern and then fixate disproportionately on hyperlinks, which act as signposts.

  — [NN/g, McCloskey 2014](https://www.nngroup.com/articles/writing-links/)
- **"First 2 Words: A Signal for the Scanning Eye"** by Jakob Nielsen, 6 Apr 2009. This is the main measured NN/g data point.
  - Design: 80 participants were each shown only the first 11 characters of 20 links and headlines taken from major sites on three continents.
  - Best result: Ann Taylor's "Gift Cards & E-Gift Certificates" was understood by 85% of participants, and 100% chose correctly.
  - Worst result: Chase Bank's "Introducing…" scored 15%.
  - Nielsen's three "nasties" are bland generic words, made-up terms, and "starting with blah-blah and deferring the information-carrying text to the end".
  - Users scanning lists typically see "about 2 words" of each item.

  — [NN/g, Nielsen 2009](https://www.nngroup.com/articles/first-2-words-a-signal-for-scanning/)
- **F-shaped pattern** (original eye-tracking study 2006, article updated 12 Nov 2017). It says links should "include information-bearing words (instead of generic 'go', 'click here' or 'more')", and that "First few words on the left of each line of text receive more fixations than subsequent words on the same line." Its advice for headings is to front-load so that "if users see only the first 2 words, they should still get the gist". — [NN/g, F-shaped pattern](https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/)
- **Information scent**, Raluca Budiu, 2 Feb 2020. Scent comes from "the link label, the content that accompanies the link, the context in which the link appears, and any background knowledge". Link names "should be clear and self-explanatory". — [NN/g, Budiu 2020](https://www.nngroup.com/articles/information-foraging/)

### Inferences
- The strongest NN/g claim is about where the words sit, not about banning one phrase. "Learn more about X" still front-loads boilerplate, so by the first-two-words finding it is weaker than "X: …" or "See X".
- NN/g's evidence is about scanning and comprehension. None of these articles reports a click-through difference between "Learn More" and a descriptive label.

### Gaps
- The Sherwin 2015 article gives no quantitative study of "Learn More"; it is argued from principles plus observation.
- I could not confirm sample sizes for the 2006 F-pattern study from the 2017 article. The original study is widely cited as 232 users, but I did not verify that here.

## 2. Information foraging theory and information scent: what they predict for labels

### Takeaway
Information foraging theory (Pirolli & Card 1999) models users as maximising the rate at which they gain valuable information. Link labels are the "proximal cues" users judge that value from. Its prediction for labels is direct: cues that are vague or mismatched lower the perceived value, so users either choose wrongly or give up on the path. Spool/UIE turned this into the practitioner idea of "trigger words".

### Cited Findings
- Pirolli, P. & Card, S. (1999). "Information foraging". *Psychological Review* 106, 643–675. People adapt their information-seeking to maximise the rate of gain of valuable information per unit cost. Information scent is the imperfect perception of a source's value, cost or access path, obtained from proximal cues such as link labels, citations or icons. — [PhilPapers record](https://philpapers.org/rec/PIRIF); the definition is paraphrased in [NN/g](https://www.nngroup.com/articles/information-foraging/) (I did not read the paper itself; the definition is from secondary sources)
- NN/g's reading of the theory: when cues are insufficient, "users don't bother scrolling anymore… they quickly decide that the page is not worth exploring any longer and simply leave". — [NN/g, Budiu 2020](https://www.nngroup.com/articles/information-foraging/)
- **Jared Spool, "The Secret Lives of Links"** (talk, 2011; liveblogged by Jeremy Keith, 2 May 2011):
  - "Users scan a page looking for trigger words. If they find a trigger word, they click on it but if they don't find it, they go to search."
  - Search logs are "completely filled with trigger words".
  - Clickstream numbers Spool reported, as relayed in the liveblog:
    - 58% failure overall;
    - more than 80% failure once a user hits the back button;
    - 98% failure after two back clicks;
    - 89% failure after pogo-sticking.

  These are Spool's figures relayed second-hand. No method is published in the liveblog. — [Adactio liveblog](https://adactio.com/journal/4539); [UIE archive](https://archive.uie.com/brainsparks/2012/12/12/jared-spool-the-secret-lives-of-links/)
- **Cognitive Walkthrough for the Web (CWW).** Blackmon, Polson, Kitajima & Lewis, CHI 2002. It uses Latent Semantic Analysis to estimate the scent between a user's goal and each heading or link label. It found that unfamiliar labels and confusable labels were major classes of navigation failure. This is the academic operationalisation of "the label must match the goal vocabulary". — [ACM DL](https://dl.acm.org/doi/10.1145/503376.503459); [ResearchGate](https://www.researchgate.net/publication/221514534_Cognitive_walkthrough_for_the_Web) (seen through a search summary; I did not read the paper's results tables)

### Inferences
- Under foraging theory, "Learn more" carries close to zero scent of its own. All its scent is borrowed from nearby text. Where that text is strong (a card heading right above it), the theory predicts only a small penalty. Where several identical labels compete, or the link is met out of context (link lists, screen readers, a scanning eye), the theory predicts a real penalty.
- "Trigger words" means a label should use the user's vocabulary for their goal, not the producer's ("Introducing", product brand names).

### Gaps
- **UNVERIFIED:** the widely repeated Spool/UIE finding that links of 7–12 words succeeded far more often, against an average link success of about 43%. I found it only in search summaries of secondary pages: a course page on uvu.edu that I could not reach (DNS failure), and [UX Tigers](https://www.uxtigers.com/post/information-scent). The primary source is reportedly UIE's "Designing for the Scent of Information" report (Spool, Perfetti & Brittan, c. 2004). A mirror PDF exists but I could not extract its text ([Oregon State mirror](https://web.engr.oregonstate.edu/~mjb/cs553/Projects/Papers/infoScentArticle-spool.pdf)). Treat it as a practitioner claim from about 2004, with an unpublished method.
- I did not read Pirolli's 2007 book *Information Foraging Theory* (OUP).

## 3. Measured evidence that descriptive link text improves outcomes

### Takeaway
The measured evidence is thinner than the strength of the consensus suggests. The best direct measurement is Nielsen's 2009 first-11-characters test: specific, front-loaded labels were understood 85% of the time and generic ones 15%. The academic evidence (CWW, foraging models) supports the mechanism, that semantic match predicts navigation success. I found no peer-reviewed controlled experiment comparing "Learn more" with a descriptive label on click-through or task success. Practitioner A/B results exist but are weak evidence.

### Cited Findings
- Nielsen 2009: 80 users, 20 links, first 11 characters only. Specific and front-loaded labels were understood 85% of the time (100% chose correctly); a generic "Introducing…" was understood 15% of the time. This measures comprehension from a fragment, not click-through. It is web content from 2009. — [NN/g](https://www.nngroup.com/articles/first-2-words-a-signal-for-scanning/)
- CWW (CHI 2002) found unfamiliar and confusable link labels to be predictable causes of navigation failure, and a follow-up paper reported that repairing those labels improved success. — [ACM DL](https://dl.acm.org/doi/10.1145/503376.503459); [Repairing usability problems… (ResearchGate)](https://www.researchgate.net/publication/221514993_Repairing_usability_problems_identified_by_the_Cognitive_Walkthrough_for_the_Web) (search summary only; I did not read the effect sizes)
- **Links shape reading more broadly.** Jayes, Fitzsimmons, Weal, Kaakinen & Drieghe (2022), *PLOS ONE*.
  - Experiment 1: 50 participants rated sentences that contained links as more important regardless of their content, and more links meant higher ratings.
  - Experiment 2: an eye-tracking study with 32 participants. Under skim-reading, importance had less effect on reading, and comprehension accuracy fell from 91% to 86%.

  The implication is that link styling pulls attention and signals importance whatever the link's words say. — [PLOS ONE 2022](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0263669)
- **Practitioner A/B tests (LOW strength, UNVERIFIED).** Search summaries repeat results such as "Start your free 30 day trial" → "Start my free 30 day trial" giving +90% click-through, and an unattributed +33.1% from a button-copy change. These come from CRO marketing blogs, without sample sizes or significance tests visible in the summaries. The first is pronoun framing, not generic-versus-descriptive. — [OptinMonster roundup](https://optinmonster.com/8-ab-tests-to-run-on-your-popups-to-get-more-email-subscribers/); [CXL](https://cxl.com/blog/ab-testing-forms/)
- **UNVERIFIED:** a claim that "users ignore or misinterpret vague links at rates up to 50% higher than those with clear labels". It appeared only in a search summary of university accessibility pages, with no traceable study. Do not cite it.

### Inferences
- An honest framing: the case for descriptive labels rests on (a) a well-established theory with strong models of the mechanism, (b) eye-tracking showing where attention goes, and (c) one direct comprehension test from 2009. It does not rest on a body of click-through experiments.
- CTA button A/B tests usually vary specificity, value, pronoun and urgency together. They cannot isolate "Learn more versus a descriptive label", and results do not transfer between sites.

### Gaps
- I found no Baymard Institute finding specific to "Learn more" or "Read more" link labels. Baymard's work on truncated product descriptions behind "Read more" may exist but I did not locate it.
- I found no app-context (native or mobile) study of generic link labels. Nearly all the evidence is from web pages, and much of it predates 2015.

## 4. Counter-evidence and nuance: when generic labels are acceptable

### Takeaway
Generic labels are defensible when strong context sits directly before them and is programmatically tied to the link: a card whose heading names the topic, or the same sentence or list item. WCAG's Level A criterion explicitly allows this. The bigger rule is to front-load the information-carrying word, so "Learn more about X" is acceptable but weaker than a link that starts with X.

### Cited Findings
- **WCAG 2.2 SC 2.4.4 Link Purpose (In Context), Level A.** A link passes if its purpose "can be determined from the link text alone or from the link text together with its programmatically determined link context". That context means the same sentence, paragraph, list item or table cell, the associated table headers, or ARIA (aria-labelledby, aria-label). The context "will be most usable if it precedes the link". **SC 2.4.9 (Level AAA)** is stricter and requires link text alone to be enough. — [W3C Understanding 2.4.4](https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context.html)
- NN/g concedes that a bare "Learn More" is not "devastating" when the preceding text makes the destination obvious. Its recommended middle path is to keep the phrase and add a qualifier, or to make the heading itself the link. — [NN/g, Sherwin 2015](https://www.nngroup.com/articles/learn-more-links/)
- Information scent is multi-source: label, accompanying content, context, and background knowledge. So a weak label can be carried by strong surroundings. — [NN/g, Budiu 2020](https://www.nngroup.com/articles/information-foraging/)

### Inferences
- The context has to come before the link. A card with heading, then summary, then "Learn more" works for sighted scanning, where the heading is the trigger word. It fails if the card's link has no association with its heading (a list of links, a screen reader moving by links), unless aria-labelledby or visually hidden text supplies the topic.
- Several identical "Learn more" links on one page are the case that both NN/g and WCAG's AAA level object to. A single "Learn more" under a strong heading is the case both tolerate.
- Space-constrained UI (buttons, cards) is a legitimate reason for short labels. The evidence argues for a short, specific verb plus object ("See pricing", "Read the guide") over a generic phrase, rather than for long links. Spool's "longer links" claim is unverified and dates from web navigation menus around 2004.

### Gaps
- I found no study that measures the penalty of "Learn more" under a strong card heading compared with a descriptive alternative.

## 5. How people scan links

### Takeaway
People do not read links in full. They scan in an F-shaped or left-anchored pattern, fixate disproportionately on links, and take in roughly the first two words of each. Links also draw attention, and signal importance, by their styling alone.

### Cited Findings
- "People mostly look at the first 2 words of a link." Eye-tracking shows an initial F-pattern scan and then concentrated attention on hyperlinks. — [NN/g 2014](https://www.nngroup.com/articles/writing-links/)
- Users scanning lists see "about 2 words" per item. They read the first items "somewhat thoroughly" and less and less further down. — [NN/g 2009](https://www.nngroup.com/articles/first-2-words-a-signal-for-scanning/)
- "First few words on the left of each line of text receive more fixations than subsequent words on the same line." — [NN/g F-pattern 2017](https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/)
- Users look for trigger words and switch to search when they cannot find them. — [Adactio liveblog of Spool, 2011](https://adactio.com/journal/4539)
- Screen-reader users often navigate a list of links pulled out of context, which is where identical generic labels fail outright. — [NN/g 2015](https://www.nngroup.com/articles/learn-more-links/); [W3C 2.4.4](https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context.html)
- Linked sentences are rated more important regardless of content. — [Jayes et al. 2022, PLOS ONE](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0263669)

### Inferences
- In practice, users read link text in isolation, as a fragment: the first two words, possibly out of order on the page. Boilerplate openers ("Learn more about", "Click here to", "Introducing") spend the user's two-word budget on nothing.

### Gaps
- I found no recent (post-2020) eye-tracking study of link scanning specifically, and none for native apps.
