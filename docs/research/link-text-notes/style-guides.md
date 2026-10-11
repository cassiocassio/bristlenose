# What platform and design-system style guides say about link text ("Learn more", "Read more", "Click here", "More", links to documentation)

Researched 11 Oct 2026. Verification legend: **VERIFIED** = read in the primary source (page fetch, the published PDF, or the design system's own source repo). **UNVERIFIED** = seen only in a search-engine summary or paraphrased by a fetch tool without the exact wording; treat as indicative.

## Comparison table

| Guide | Generic text ("click here", "more", "read more") | "Learn more" | How to phrase link text | Docs / leaving the app |
|---|---|---|---|---|
| **Apple HIG** (Writing) | Avoid "Click here" (VERIFIED) | **Endorsed with a topic**: "Learn more about UX Writing" is the HIG's own *good* example (VERIFIED) | Lead with a verb for buttons and links (VERIFIED) | Help button: opens the help topic for the current context; one per window; no text introducing it (VERIFIED) |
| **Apple Style Guide** (June 2026 PDF) | No entry for "learn more", "click here" or "read more" (VERIFIED: searched the full text) | Not ruled on. Used in an example ("Learn more about the features of your MacBook Pro") (VERIFIED) | Say "click a link", not "follow a link". Cross-refs use "For more information, see …" or "See …" (VERIFIED) | Guide titles in onscreen text in roman, no quotes, often links (VERIFIED) |
| **Microsoft Writing Style Guide** | Use a page title or description "rather than a generic phrase like *click here*" (VERIFIED) | No A–Z entry found (the URL 404s). MS pages use "Learn more in [Title]" themselves (VERIFIED) | "Brief but specific and meaningful link text" (VERIFIED) | — |
| **Microsoft: Windows / Windows Admin Center UI text** | "More information about Windows Firewall" is marked "Not our style" (VERIFIED) | **Bare "Learn more" and "Learn more about color management" are "Not our style"**, BUT "it's OK to use a 'Learn more' link if the context is clear" (VERIFIED) | Full sentences or questions, specific to the topic; the whole sentence is the link; no end punctuation except "?" (VERIFIED) | Help links "Almost never"; place them next to the element; use a redirect service, not a raw URL (VERIFIED) |
| **Google developer docs** | Avoid "this document", "this article", "click here" (VERIFIED) | Not mentioned | Exact page title or a descriptive phrase; short; must make sense out of context (VERIFIED) | Use "For more information, see [Title]." (VERIFIED) |
| **Material Design (M2/M3)** | Could not read (JS-rendered) | Not found | — | — |
| **GOV.UK** | Avoid "click here" or "more" (VERIFIED) | Not named (it falls under "more") | Descriptive and front-loaded. A task link starts with a verb; an information link uses the topic. A one-word link should have ≥3 syllables (VERIFIED) | Say when a link leaves GOV.UK. Give a document's format and size: "(PDF, 19.5KB)" (VERIFIED) |
| **Mailchimp** | Avoid "click here" (VERIFIED) | **Avoid** "learn more" (VERIFIED) | Describe the action or destination (VERIFIED) | — |
| **Shopify Polaris** | "Never use 'click here' or 'here'" (VERIFIED) | **Endorsed as a pattern**: a "learn more" link for longer, multi-faceted info; at most one per screen; it follows a sentence that names the topic; no period (VERIFIED) | Embedded link inside the sentence's flow is preferred; punctuation outside the link (VERIFIED) | "Avoid links if possible". Error messages may "Link to help documentation" (VERIFIED) |
| **Atlassian** | — | **"DON'T use filler words and generic CTAs like 'Learn more.'"** (Forge automation guidelines, VERIFIED) | "Use clear labels" | — |
| **IBM Carbon** | "read more" type links: "consider making them unique" (VERIFIED) | **Tolerated if programmatically associated** with a heading through `aria-describedby` / `aria-labelledby` (VERIFIED) | "Distinctive and meaningful". No same text for different destinations (VERIFIED) | "Launch" icon for external links, "arrow right" for internal ones (VERIFIED) |
| **Intuit** | Avoid "Click here" (VERIFIED) | **Discouraged**: "isn't helpful link copy on its own" (VERIFIED) | Descriptive; 8 characters minimum; 6–8 words / ~55 characters maximum (VERIFIED) | — |
| **Adobe Spectrum** | "learn more" / "click here" "doesn't communicate any context" (UNVERIFIED) | Discouraged without context (UNVERIFIED) | Standalone link = short verb phrase, no end punctuation (UNVERIFIED) | — |
| **Salesforce Lightning** | Nothing found | Nothing found | — | — |

## Q1. What does each guide say about generic link text?

### Takeaway
Every guide we could read bans "click here". GOV.UK also bans "more" by name, and Carbon names "read more". None of them recommends a bare "More" or "Read more".

### Cited Findings
- Apple HIG, Writing: "For links, avoid using 'Click here' in favor of more descriptive words or phrases, such as 'Learn more about UX Writing.'" — [Apple HIG: Writing](https://developer.apple.com/design/human-interface-guidelines/writing) (VERIFIED from the HIG's JSON source, `developer.apple.com/tutorials/data/design/human-interface-guidelines/writing.json`)
- Apple Style Guide, *link (n.)*: "A user clicks a link to go to another page or to perform an action. Avoid using *follow a link*; use *click a link* instead." The guide has no entry for "click here", "learn more" or "read more". — [Apple Style Guide, June 2026 PDF](https://help.apple.com/pdf/applestyleguide/en_US/apple-style-guide.pdf) (VERIFIED; full text extracted and searched)
- Microsoft: "Write brief but specific and meaningful link text. Use the title or a description of a page rather than a generic phrase like *click here*." — [Microsoft Style Guide: URLs and web addresses](https://learn.microsoft.com/en-us/style-guide/urls-web-addresses) (VERIFIED)
- Google: "Write link text that makes sense without the surrounding text." The guide lists "this document", "this article" and "click here" as text to avoid. — [Google developer documentation style guide: Link text](https://developers.google.com/style/link-text) (VERIFIED through a fetch summary that quotes it)
- GOV.UK: "make it descriptive and avoid generic text like 'click here' or 'more'". Also: "if you have one-word link text, try to use a word with at least 3 syllables". — [GOV.UK: Add links](https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/writing-guidelines/add-links/) (VERIFIED; the old gov.uk/guidance/content-design/links redirects here)
- Mailchimp: "Links should provide information on the associated action or destination. Try to avoid 'click here' or 'learn more.'" — [Mailchimp: Writing for Accessibility](https://styleguide.mailchimp.com/writing-for-accessibility/) (VERIFIED)
- Polaris: "Never use 'click here' or 'here' for link text". Its Don't example: "Want to learn more about how to set up your online store? [Click here.]" — [Polaris source: grammar-and-mechanics.mdx § Links](https://github.com/Shopify/polaris/blob/main/polaris.shopify.com/content/content/grammar-and-mechanics.mdx) (VERIFIED in the repo. The public polaris.shopify.com content pages now redirect to shopify.dev.)
- Carbon: "Use distinctive and meaningful link text." "If your design uses generic link names such as 'read more,' consider making them unique." "Avoid using the same link text for different destinations on the same page." — [Carbon Link usage](https://carbondesignsystem.com/components/link/usage/) (VERIFIED; source `carbon-website/src/pages/components/link/usage.mdx`)
- Intuit, word list, *Click*: use "select", because not everyone clicks with a mouse; avoid "Click here" and say where the CTA goes. — [Intuit Content Design: Word list](https://contentdesign.intuit.com/word-list/) (VERIFIED through a fetch summary that quotes it)

### Inferences
- The ban on "click here" is universal. "More" and "Read more" are named by fewer guides (GOV.UK, Carbon), but they fail every guide's general test of making sense out of context.

### Gaps
- The Microsoft A–Z word-list page for "learn more" returns 404, so we could not confirm whether one exists now.

## Q2. Is "Learn more" allowed, and in which pattern?

### Takeaway
This is where the guides disagree. **Apple endorses "Learn more about <topic>".** **Polaris endorses a bare trailing "Learn more"** when the sentence before it names the topic, but rejects "Learn more about <topic>" when that only repeats the sentence. **Microsoft's Windows UI guidance rejects both forms** but allows "Learn more" when context is clear. **Carbon tolerates it only with an ARIA association.** **Mailchimp, Atlassian and Intuit discourage it.**

### Cited Findings
- **Apple HIG endorses the "Learn more about X" form.** Its own good example is "Learn more about UX Writing." — [Apple HIG: Writing](https://developer.apple.com/design/human-interface-guidelines/writing) (VERIFIED)
- **Polaris endorses "learn more" for a specific case.** "For added info that it's essential for most merchants to know, use the info icon (for short, stand-alone info), an embedded link (within the flow of an existing sentence), or a 'learn more' link (for longer, multi-faceted info)". "If you have to include 'learn more' links, avoid having more than one per screen". — [Polaris grammar-and-mechanics.mdx § Links](https://github.com/Shopify/polaris/blob/main/polaris.shopify.com/content/content/grammar-and-mechanics.mdx) (VERIFIED)
  - Do: "Track customer behavior on your online store to improve your marketing. [Learn more]" (no period, and the sentence before it names the topic).
  - Don't: "Show up where shoppers scroll, search, and shop with multichannel integration. [Learn more.]" (the period is inside the link, and an embedded link would have done the job).
  - Don't: "Facebook Pixel tracks customer behavior on your online store. This data improves your marketing abilities, including retargeting ads. [Learn more about Facebook Pixel]". Polaris marks the "about X" expansion a Don't when the context already names X. **This is the opposite of Apple's example.**
  - The Polaris Link component's own accessibility Do is the sentence "Learn more about [Fraud Protect]." with only the topic linked. — [Polaris link.mdx](https://github.com/Shopify/polaris/blob/main/polaris.shopify.com/content/components/navigation/link.mdx) (VERIFIED)
  - Error messages, Don't: "Sorry, something went wrong. Learn more." — [Polaris error-messages.mdx](https://github.com/Shopify/polaris/blob/main/polaris.shopify.com/content/content/error-messages.mdx) (VERIFIED)
- **Microsoft (Windows / Windows Admin Center UI text) gives a conditional yes.** Under "Be as specific as possible about the content of the help topic", "Not our style" lists "More information about Windows Firewall", "Learn more about color management" and "Learn more". "Our style" lists "How does Windows Firewall help protect my computer?" and "Why highlights can improve a picture". The same section then says: "In some cases, it's OK to use a 'Learn more' link if the context is clear what the user will be getting when they click the link." — [Windows Admin Center UI text and design style guide § Help links](https://learn.microsoft.com/en-us/windows-server/manage/windows-admin-center/extend/guides/ui-text-style-guide) (VERIFIED. The page says these are "tips from our Windows style guide", which is internal and not public.)
- The Microsoft Writing Style Guide uses the pattern itself: "Learn more in [Alternative text (alt text)]". — [MS Style Guide: URLs](https://learn.microsoft.com/en-us/style-guide/urls-web-addresses) (VERIFIED)
- **Carbon tolerates it if the link is associated with context.** "If your design uses generic link names such as 'read more,' consider making them unique. Otherwise, annotate a connection with other text in the design that provides context." Developers should "Associate generic links such as 'read more' with other contextual text, using either `aria-describedby` or `aria-labelledby`". The illustration links an IBM Cloud heading to a "Learn more" link, captioned "associate link with heading". — [Carbon Link accessibility § Ensure link context](https://carbondesignsystem.com/components/link/accessibility/) (VERIFIED; source `accessibility.mdx`)
- **Atlassian says no:** "DON'T use filler words and generic CTAs like 'Learn more.' Use clear labels as outlined in these standards." — [Atlassian Forge: Automation design guidelines](https://developer.atlassian.com/platform/forge/action-components-guidelines/) (VERIFIED. This is the Forge developer guidance, not the core atlassian.design content pages, which we could not reach.)
- **Mailchimp says avoid it.** — [Mailchimp](https://styleguide.mailchimp.com/writing-for-accessibility/) (VERIFIED)
- **Intuit discourages it:** "*Learn more* isn't helpful link copy on its own. It's ambiguous, making customers figure out where the link will go, and it implies work (learning is hard!). It's also inaccessible…" Suggested alternatives are "Find out more" or "Get more info", with context such as "Review your options" or "Get pricing details". — [Intuit word list](https://contentdesign.intuit.com/word-list/) (VERIFIED through a fetch summary that quotes it)
- **Adobe Spectrum discourages it.** It reportedly says generic wording like "learn more" or "click here" "doesn't communicate any context from elsewhere in the experience", which matters especially for screen-reader users. — [Spectrum: Link](https://spectrum.adobe.com/page/link/) (**UNVERIFIED**: the page returned 404 to the fetcher; this is from a search summary only)

### Inferences
- There are three distinct "Learn more" patterns, and the guides split on each:
  1. Bare trailing "Learn more" after a topic sentence: Polaris Do; Microsoft "OK if context is clear"; Carbon OK with an ARIA association; Mailchimp, Atlassian and Intuit no.
  2. "Learn more about <topic>" as the whole link: Apple HIG Do; Microsoft and Polaris Don't (when the about-clause only restates the context).
  3. "Learn more about [topic]" with only the topic linked: Polaris link component Do; matches Google's and Microsoft's "the title is the link".
- Google and GOV.UK never name "Learn more", but under their rules a bare "Learn more" fails ("makes sense without the surrounding text"; "avoid … 'more'").

### Gaps
- We found no Material Design writing guidance on "Learn more"; m2/m3 pages are JS-rendered and would not fetch.
- Salesforce Lightning: nothing found.

## Q3. How should link text be phrased (verb-first? names the destination? case? length?)

### Takeaway
There are two families. **Action links lead with a verb** (Apple, GOV.UK for task links, Spectrum standalone links). **Information or docs links use the destination's title or topic** (Google, Microsoft, GOV.UK, Carbon, Polaris). Length rules are short-and-specific everywhere; only Intuit gives numbers.

### Cited Findings
- Apple HIG: "When labeling buttons and links, it's almost always best to use a verb." On case: "Title case is generally considered formal, while sentence case is more casual. … Choose a style for each UI element type and use it consistently". — [HIG Writing](https://developer.apple.com/design/human-interface-guidelines/writing) (VERIFIED)
- GOV.UK: "If your link takes the user to a page where they can start a task, start your link with a verb. For example, 'Send a tax return'." and "If your link leads to information rather than starting a task, use the text about that information as the link." Also "frontload it with relevant terms". — [GOV.UK: Add links](https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/writing-guidelines/add-links/) (VERIFIED)
- Google: "use either the exact page title or a descriptive phrase", capitalized as part of the sentence. "Keep link text short where possible. Don't write lengthy link text such as a sentence or short paragraph." — [Google: Link text](https://developers.google.com/style/link-text) (VERIFIED through a fetch summary that quotes it)
- Microsoft (Windows UI help links): "Use full sentences." "Do not include ending punctuation except for question marks." "Use the entire sentence for the link text, not just the key words." The link text need not match the help topic title, but there must be "a logical connection". — [WAC UI text guide](https://learn.microsoft.com/en-us/windows-server/manage/windows-admin-center/extend/guides/ui-text-style-guide) (VERIFIED). **This conflicts with Google, which says not to make a whole sentence the link.**
- Polaris: keep punctuation "outside the link unless the link is a stand-alone sentence (exception: question marks)". Use the same text for links to the same content and different text for different content. — [Polaris grammar-and-mechanics](https://github.com/Shopify/polaris/blob/main/polaris.shopify.com/content/content/grammar-and-mechanics.mdx), [link.mdx](https://github.com/Shopify/polaris/blob/main/polaris.shopify.com/content/components/navigation/link.mdx) (VERIFIED)
- Intuit: "Write the link to be large enough for people to select—at least 8 characters. Don't write link text longer than 6 to 8 words (about 55 characters)." — [Intuit: Actions](https://contentdesign.intuit.com/product-and-ui/actions/) (VERIFIED through a fetch summary that quotes it)
- Spectrum: standalone links "are not full sentences and do not have punctuation at the end"; write them "as short verb phrases"; inline links should "include enough context in the link text to communicate the value and expectation of the landing experience". — [Spectrum Link](https://spectrum.adobe.com/page/link/) (**UNVERIFIED**, search summary)
- Carbon: standalone links follow content and are underlined only on hover/focus; inline links are always underlined and carry no icons. — [Carbon Link usage](https://carbondesignsystem.com/components/link/usage/) (VERIFIED)

### Inferences
- The guides agree that a link should say *where it goes* or *what it does*. They disagree on whether a full-sentence question link ("How does Windows Firewall help protect my computer?", Microsoft) is good or too long (Google).

### Gaps
- Material's casing and length rules for links are not captured.

## Q4. Guidance on links that leave the app or open documentation

### Takeaway
Apple and Microsoft both treat help links as rare and contextual: one help button per window, opening the relevant topic. GOV.UK and Carbon ask you to signal when a link leaves the site. Polaris and Microsoft prefer no help link if the UI can explain itself.

### Cited Findings
- Apple HIG, Help buttons: a help button "opens app-specific help documentation". "When possible, open the help topic that's related to the current context." "Include no more than one help button per window." "Avoid displaying text that introduces a help button. People know what a help button does, so they don't need additional descriptive text." — [HIG: Buttons](https://developer.apple.com/design/human-interface-guidelines/buttons) (VERIFIED from JSON source)
- Apple HIG, Writing: "If you need to direct someone to a setting, provide a direct link or button, rather than trying to describe its location." — [HIG Writing](https://developer.apple.com/design/human-interface-guidelines/writing) (VERIFIED)
- Apple Style Guide, cross-references: "For more information about adding contacts, see the Contacts User Guide." and "For more information, see the 'Edit with multicam clips' section of the Final Cut Pro User Guide." In onscreen text, guide titles are roman with no quotation marks because "Titles are often links". It's also "OK to use the common cross-reference *See* when linking to other material (for example, See the Apple Support article 'Set up Family Sharing')". — [Apple Style Guide PDF](https://help.apple.com/pdf/applestyleguide/en_US/apple-style-guide.pdf) (VERIFIED)
- Microsoft (Windows UI), "When should we provide a Help link? Almost never." Only provide one when "There's an obvious and important question that customers are likely to have" and "There's not enough room in the UI". Text links go "as close to the UI element … as possible", or at the bottom left for a whole screen. "Never link directly to a web address—instead use a redirection service." In error messages: "Only consider Help links for error messages that you can't make specific and actionable." — [WAC UI text guide](https://learn.microsoft.com/en-us/windows-server/manage/windows-admin-center/extend/guides/ui-text-style-guide) (VERIFIED)
- Polaris: "Avoid links if possible: Links add clutter and make things feel less like software, more like an old-fashioned webpage". It notes merchants already use the help center. Error-message bodies may "Link to help documentation". — [Polaris grammar-and-mechanics](https://github.com/Shopify/polaris/blob/main/polaris.shopify.com/content/content/grammar-and-mechanics.mdx), [error-messages.mdx](https://github.com/Shopify/polaris/blob/main/polaris.shopify.com/content/content/error-messages.mdx) (VERIFIED)
- GOV.UK: "tell users if the link will take users off GOV.UK – for example, 'Find a counsellor on Counselling Directory'", and "include the file format and size if you need to link directly to a document – for example 'Application form (PDF, 19.5KB)'". — [GOV.UK: Add links](https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/writing-guidelines/add-links/) (VERIFIED)
- Google: when a sentence exists only as a cross-reference, write "For more information, see [Title]". Include "about …" when the context doesn't say why. — [Google: Link text](https://developers.google.com/style/link-text) (VERIFIED through a fetch summary that quotes it)
- Carbon: "It's common to use the 'launch' icon for external links and the 'arrow right' icon for internal links", used consistently. — [Carbon Link usage](https://carbondesignsystem.com/components/link/usage/) (VERIFIED)

### Inferences
- "For more information, see <Title>" (Google, Apple Style Guide) and "Learn more in <Title>" (as Microsoft's own pages use it) are the documentation-native forms of a docs link. "Learn more" is the UI-native, space-constrained form. That split may explain why the UI-focused systems (Apple HIG, Polaris, Microsoft UI) allow some form of "Learn more" while the docs and government guides do not.

### Gaps
- No guide we read says whether docs links should open in a new tab or window, except Carbon's icon convention.
- Fluent 2 content guidance (Microsoft) was not checked.
