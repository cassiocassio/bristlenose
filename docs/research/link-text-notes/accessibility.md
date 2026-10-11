# Accessibility standards and guidance on link text purpose ("Learn more", "Read more", "Click here")

Researched 11 Oct 2026. Sources fetched directly unless marked **[search summary only — unverified]**.

**Correction to the brief:** WCAG 2.2 SC 2.4.4 Link Purpose (In Context) is **Level A**, not AA. It has been Level A since WCAG 2.0. 2.4.9 Link Purpose (Link Only) is **AAA**. That means 2.4.4 is part of every conformance claim at A or AA, and so of every procurement standard built on WCAG AA (EN 301 549, Section 508, the UK public-sector regulations).

## 1. What WCAG 2.2 actually requires (2.4.4, 2.4.9, techniques and failures)

### Takeaway
A bare "Learn more" link **passes 2.4.4 (Level A)** if its purpose can be worked out from *programmatically determined context*: the same sentence, paragraph, list item or table cell, the preceding heading, or an `aria-label` or `aria-labelledby` that names the destination. It **fails 2.4.9 (AAA)** unless the link text alone says where it goes, or the user has a way to switch to descriptive text. "Learn more" is therefore not a Level A/AA violation in itself. It becomes one when the context sits outside those programmatic containers, such as an adjacent paragraph or another table row (F63). Descriptive link text is the hard requirement only at AAA. At AA it is best practice that every authority below recommends.

### Cited Findings
- **2.4.4 normative text (Level A):** "The purpose of each link can be determined from the link text alone or from the link text together with its programmatically determined link context, except where the purpose of the link would be ambiguous to users in general." — [WCAG 2.2](https://www.w3.org/TR/WCAG22/); [Understanding 2.4.4](https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context.html)
- **2.4.9 normative text (Level AAA):** "A mechanism is available to allow the purpose of each link to be identified from link text alone, except where the purpose of the link would be ambiguous to users in general." — [WCAG 2.2](https://www.w3.org/TR/WCAG22/); [Understanding 2.4.9](https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-link-only.html)
- **Definition, "programmatically determined link context":** "Additional information that can be programmatically determined from relationships with a link, combined with the link text, and presented to users in different modalities." — [WCAG 2.2 glossary](https://www.w3.org/TR/WCAG22/)
- **Definition, "ambiguous to users in general":** "The purpose cannot be determined from the link and all information of the web page presented to the user simultaneously with the link (i.e., readers without disabilities would not know what a link would do until they activated it)." — [WCAG 2.2 glossary](https://www.w3.org/TR/WCAG22/)
- **Understanding 2.4.4 on "Read more":** vague text can be acceptable when "the user should be able to identify the purpose of the link without moving focus from the link". Context that **precedes** the link serves sequential screen-reader users better than context that follows it. — [Understanding 2.4.4](https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context.html)
- **Understanding 2.4.9 intent:** links should make sense out of context, for example in a list of all links on the page. Links to the same destination should have consistent text, and links with different purposes should have different text. — [Understanding 2.4.9](https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-link-only.html)
- **Sufficient techniques for 2.4.4** (as listed in the Understanding document):
  - G91: link text that describes the purpose
  - H30: link text for `<a>` elements
  - H24: text alternatives for image-map areas
  - G189 and SCR30: let the user choose short or long link text
  - G53: link text combined with the enclosing sentence
  - H33 and C7: supplement the link text with `title`, or with CSS-hidden text
  - ARIA7 (`aria-labelledby`) and ARIA8 (`aria-label`)
  - H77, H78, H79 and H81: context from the enclosing list item, paragraph, table cell, or the heading of a nested list
  - PDF11 and PDF13
  — [Understanding 2.4.4](https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context.html)
- **Advisory techniques for 2.4.4:**
  - H2: combine adjacent image and text links
  - H80: link text combined with the preceding heading
  - G201: warn before opening a new window
  - SCR24: progressive enhancement for new windows
  — [Understanding 2.4.4](https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context.html)
- **Failures for 2.4.4:**
  - F63: the context is not related to the link
  - F89: an image-only link with no accessible name
  — [Understanding 2.4.4](https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context.html)
- **F63 examples:** a "Read More..." link in a paragraph *after* the paragraph that introduces the article fails. So does a download link in a different table row from its description. Valid context locations are the same sentence, paragraph, list item or table cell, or `aria-label`/`aria-labelledby`. — [F63](https://www.w3.org/WAI/WCAG22/Techniques/failures/F63)
- **Sufficient techniques for 2.4.9:** ARIA8, G91, H30, H24, G189, SCR30, C7, PDF11, PDF13. H33 (`title`) is only advisory here. **Failures:** F84 and F89. — [Understanding 2.4.9](https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-link-only.html)
- **F84** ("non-specific links such as 'click here' or 'more' without a mechanism to change the link text"): its two examples are `<a>Click here</a> for more information on the Rocky Mountains` and a "read more" link under a news headline. The rationale it gives: "Many blind people who use screen readers call up a dialog box that has a list of links from the page." It fails only when the nondescript link exists **and** there is no mechanism to change it. — [F84](https://www.w3.org/WAI/WCAG22/Techniques/failures/F84)
- **ARIA8 worked example:** `<a href="taxhike.html" aria-label="Read more about Seminole tax hike">Read more</a>`. The technique warns that "The `aria-label` text will override the text supplied within the link," so authors should "start the text used in `aria-label` with the text used within the link" to satisfy 2.5.3. — [ARIA8](https://www.w3.org/WAI/WCAG22/Techniques/aria/ARIA8)

### Inferences
- For the purposes of 2.4.4, a "Learn more" link inside the same paragraph or list item as the thing it explains is conformant at A/AA. A "Learn more" link sitting alone below a heading relies on H80, which is only *advisory* for 2.4.4. That is a weaker position, so treat it as risky.
- An aria-label that expands the text ("Learn more about AutoCode") makes the link pass 2.4.9 as well, through ARIA8. The visible label still says "Learn more", so sighted users scanning the page, and cognitive-accessibility readers, get no benefit from it.

### Gaps
- I did not fetch the full text of G53, H77–H81, ARIA7 or H33. Their titles above come from the 2.4.4 Understanding page's technique list, not from the technique pages themselves.
- WCAG 3: I checked no WCAG 3 draft for this topic. Nothing here is drawn from it.

## 2. How screen-reader users meet generic links (links lists, rotor, survey data)

### Takeaway
Every major screen reader can list a page's links out of context: the VoiceOver rotor on the Mac, and the elements lists in NVDA and JAWS. W3C cites this behaviour as the main reason generic links fail 2.4.9. In such a list, a page with five "Learn more" links shows five identical entries. Survey data shows navigating by links is a **minority** strategy for finding content (4.8% primary), well behind headings (71.6%). Users also meet these links one by one when tabbing between focusable elements.

### Cited Findings
- **macOS VoiceOver rotor:** lets users "navigate directly to an item in an app window or a webpage," with lists including Links and Headings. It opens with VO-Command-Left/Right Arrow, and VO-U opens the rotor menus. — [Apple Support: Use the VoiceOver rotor on Mac](https://support.apple.com/guide/voiceover/use-the-voiceover-rotor-mchlp2719/mac)
- **WebAIM Screen Reader User Survey #10** (Dec 2023 – Jan 2024, 1,539 valid responses). How respondents first look for information on a lengthy page:
  - headings 71.6%
  - Find 13.6%
  - reading through 6.4%
  - links 4.8%
  - landmarks 3.7%

  Primary screen reader: JAWS 40.5%, NVDA 37.7%, VoiceOver 9.7%. — [WebAIM SRUS #10](https://webaim.org/projects/screenreadersurvey10/)
- W3C F84: users "call up a dialog box that has a list of links from the page", and "hearing repeated 'click here' phrases creates confusion" for people tabbing through links. — [F84](https://www.w3.org/WAI/WCAG22/Techniques/failures/F84)
- MDN: "Assistive software has shortcuts to list all links on a page. However, strong link text benefits all users — the 'list all links' shortcut emulates how sighted users quickly scan pages." — [MDN `<a>`](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/a)
- GOV.UK: "Screen reader users often read out lists of links in isolation, so make the purpose of the link clear from the link text alone." — [search summary only — unverified; attributed to GOV.UK guidance, likely the Service Manual / DWP Accessibility Manual](https://accessibility-manual.dwp.gov.uk/guidance-for-your-job-role/interaction-designer)

### Inferences
- The 4.8% figure measures the *first* strategy for finding content on a long page. It does not measure how often links lists are used at all. People who start with headings still tab through links and open the rotor. Do not read 4.8% as "few people meet a links list".
- In a native SwiftUI or AppKit window, links and buttons come up in sequence under VoiceOver navigation and Full Keyboard Access. The rotor's lists depend on the content. Several identical "Learn more" controls in one window are as indistinguishable there as they are in a web page.

### Gaps
- The survey summary page has no question on *how often* users use a links list. I found no current statistic for that.
- I did not verify NVDA's Elements List (NVDA+F7) or the JAWS Links List (Insert+F7) against vendor documentation. They are well known but uncited here.

## 3. What WebAIM, Deque, GOV.UK, MDN and A11y authorities recommend; aria-label vs visible text; 2.5.3 Label in Name

### Takeaway
All of them say the same thing: make the visible link text describe the destination, and drop "click here". If the visible text has to stay short, use visually hidden text or `aria-label` **that begins with and contains the visible words**. That is a Level A requirement under 2.5.3 Label in Name, because speech-input users say what they see. An aria-label that replaces "Learn more" with something that doesn't contain "Learn more" fails 2.5.3 (F96).

### Cited Findings
- **2.5.3 Label in Name (Level A):** "For user interface components with labels that include text or images of text, the name contains the text that is presented visually." — [Understanding 2.5.3](https://www.w3.org/WAI/WCAG22/Understanding/label-in-name.html)
- 2.5.3 best practice: "A best practice is to have the text of the label at the start of the name." Capitalisation and "most punctuation" differences are not failures, because they are ignored when the label is spoken. — [Understanding 2.5.3](https://www.w3.org/WAI/WCAG22/Understanding/label-in-name.html)
- **F96:** "Failure due to the accessible name not containing the visible label text." — [Understanding 2.5.3](https://www.w3.org/WAI/WCAG22/Understanding/label-in-name.html)
- **WebAIM:** avoid "click here", "here", "more" and "link to …". "Click here" is unnecessary even when meaningful text follows it ("today's weather" rather than "click here to access today's weather"). "Read more" and "learn more" may be acceptable with context, but WebAIM suggests removing them where possible and keeping links "as concise as possible without sacrificing meaning". — [WebAIM: Links and Hypertext — Link Text](https://webaim.org/techniques/hypertext/link_text)
- **Deque** (Sailesh Panchang, Jan 2020): avoid "click here" and "read more". Use `aria-label` when different text is needed: "The aria-label gains preference even over the anchor text in determining the accessible name". Reserve `title` for supplementary advice. Screen readers "consistently and correctly expose aria-label overriding the anchor text" across the platforms tested. — [Deque blog](https://www.deque.com/blog/text-links-practices-screen-readers/)
- **GOV.UK Design System, Links:** use visually hidden text (`govuk-visually-hidden`) to add context such as "(opens in new tab)". Don't include the full stop in the link. Make external links clear in the link text. — [GOV.UK Design System: Links](https://design-system.service.gov.uk/styles/links/)
- **GOV.UK on "click here":** "Never use a link which tells the user to 'Click here'. The word 'click' makes an assumption that a mouse is being used…" — [search summary only — unverified; sources returned: DWP Accessibility Manual](https://accessibility-manual.dwp.gov.uk/guidance-for-your-job-role/interaction-designer), [GOV.UK Service Manual: Writing for user interfaces](https://www.gov.uk/service-manual/design/writing-for-user-interfaces)
- **MDN:** marks `Learn more about our products <a>here</a>` as weak and `Learn more <a>about our products</a>` as strong. Icons that signal a new window or file type need a text alternative such as "(opens in new tab)" or "(PowerPoint file)". — [MDN `<a>`](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/a)
- **Speech input with aria-label:** the visible link text should be included in the aria-label, "otherwise we risk making the link inaccessible for people using speech navigation". — [search summary only — unverified; Vision Australia](https://www.visionaustralia.org/business-consulting/digital-access/blog/how-to-make-read-more-links-accessible)

### Inferences
- In practice the options rank like this:
  1. Descriptive visible text, such as "About AutoCode". This passes 2.4.4, 2.4.9 and 2.5.3, and serves sighted scanners and readers with cognitive disabilities too.
  2. "Learn more" plus visually hidden text that completes the phrase ("Learn more<span hidden> about AutoCode</span>"). The accessible name then starts with the visible words, which satisfies 2.5.3 and its best practice.
  3. `aria-label="Learn more about AutoCode"`, as in ARIA8.
  4. Bare "Learn more" inside a programmatic context container. This passes 2.4.4 only.
- An aria-label like "AutoCode documentation" on a link whose visible text is "Learn more" is a **2.5.3 failure (Level A)**. Of the patterns here, it is the one most likely to be a hard violation.
- I could not open the A11y Project's own page. Its position, as commonly cited, matches the others, but I have not verified it.

### Gaps
- The A11y Project: not fetched. No verified citation.
- GOV.UK's exact "click here" wording: seen only through a search summary.

## 4. Native macOS: SwiftUI Link / NSButton under VoiceOver and Voice Control; Apple guidance

### Takeaway
SwiftUI `Link` takes its accessible label from its label view: the string or `Text` you pass, or a custom label view. Apple's guidance on labelling is general: "label interface elements appropriately" for Voice Control and VoiceOver. I found no Apple text that addresses generic "Learn more" link labels specifically. Voice Control targets controls by their spoken names, and "Show names" displays them. A label that differs from the visible text breaks speech targeting in the same way 2.5.3 describes for the web. Apple provides `accessibilityInputLabels` (`accessibilityUserInputLabels` in UIKit/AppKit) to add alternative spoken names.

### Cited Findings
- SwiftUI `Link` is "a control for navigating to a URL". Its label comes from a string (`Link("View Our Terms of Service", destination:)`) or from a custom label view. The default action opens a Universal Link in its app if possible, otherwise in the default browser, and `OpenURLAction` can override this. — [Apple: SwiftUI Link](https://developer.apple.com/documentation/swiftui/link)
- Apple HIG, Accessibility: "Let people use Voice Control to give guidance and enter information verbally… To ensure a smooth experience, label interface elements appropriately." Also: verify "that your interface elements are appropriately labeled" for VoiceOver, Switch Control, Full Keyboard Access and similar. — [Apple HIG: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)
- An accessibility label is "a short, localized word or phrase that succinctly describes the control or view, but does not identify the element's type" (e.g. "Add", "Play"). — [search summary only — unverified; Apple archive: Understanding Accessibility on iOS](https://developer.apple.com/library/archive/documentation/UserExperience/Conceptual/iPhoneAccessibility/Accessibility_on_iPhone/Accessibility_on_iPhone.html). This is an archived iOS guide, not current macOS documentation.
- Voice Control uses the accessibility label as the control's name. Saying "show names" shows whether labels are descriptive and accurate. `accessibilityUserInputLabels` adds alternative spoken names, with the label first. — [search summary only — unverified; e.g. Apple WWDC25 "Evaluate your app for Accessibility Nutrition Labels"](https://developer.apple.com/videos/play/wwdc2025/224/), [Mobile A11y: Writing great iOS accessibility labels](https://mobilea11y.com/blog/writing-great-labels/)
- The NSObject `accessibilityLabel` API reference page has no writing guidance. It declares the property and nothing more. — [Apple: accessibilityLabel](https://developer.apple.com/documentation/objectivec/nsobject-swift.class/accessibilitylabel)

### Inferences
- WCAG is a web standard and does not formally govern a native Mac app. The same failure modes apply all the same, and accessibility audits of native software usually apply WCAG by analogy (EN 301 549 has a non-web software chapter derived from it). A SwiftUI `Link("Learn more", …)` that relies on nearby text has no equivalent of HTML's "programmatically determined context". VoiceOver announces the label and its role, roughly "Learn more, link", unless you add `.accessibilityLabel` or `.accessibilityHint`. In a native window, then, the 2.4.9 bar (meaningful from the label alone) is effectively the practical bar.
- If you add `.accessibilityLabel("Learn more about AutoCode")`, keep the visible words at the start, or add `.accessibilityInputLabels(["Learn more", …])`, so that Voice Control's "Click Learn more" still works.

### Gaps
- I found no current Apple macOS documentation that addresses generic link text such as "Learn more" specifically.
- I did not verify VoiceOver's exact announcement for SwiftUI `Link` (link role vs button) on macOS 15/26/27. Test it on hardware.

## 5. Are arrow glyphs (→, ↗) in link text read aloud?

### Takeaway
I found no authoritative source on how each screen reader pronounces Unicode arrows in link text. Practitioner guidance says decorative arrows and icons beside link text get announced ("right arrow") unless they are hidden with `aria-hidden="true"`, or on the web placed outside the accessible name via CSS. A meaningful glyph, such as ↗ meaning "opens externally", should be replaced by text in the accessible name ("opens in new window"), as MDN and GOV.UK recommend for new-tab and file-type icons. Separately, Understanding 2.5.3 says "most punctuation" is ignored when a user speaks a label, so a trailing arrow should not break speech targeting under 2.5.3.

### Cited Findings
- Decorative arrows next to link text are announced repeatedly ("arrow, arrow, arrow…") unless marked `aria-hidden="true"`. — [search summary only — unverified; Yale Usability: Accessible Links](https://usability.yale.edu/web-accessibility/articles/links)
- `aria-hidden="true"` removes decorative or duplicated content from the accessibility tree while it stays visible. — [search summary only — unverified; Orange accessibility guidelines](https://a11y-guidelines.orange.com/en/articles/accessible-hiding/), [ADG](https://www.accessibility-developer-guide.com/examples/sensible-aria-usage/hidden/)
- MDN: an icon that signals behaviour (new tab, file type) needs equivalent text in the name, e.g. `alt="(PowerPoint file)"` or "(opens in new tab)". — [MDN `<a>`](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/a)
- GOV.UK: put "(opens in new tab)" in visually hidden text inside the link. — [GOV.UK Design System: Links](https://design-system.service.gov.uk/styles/links/)
- 2.5.3: "Capitalization… and most punctuation are generally ignored when a user speaks a label." — [Understanding 2.5.3](https://www.w3.org/WAI/WCAG22/Understanding/label-in-name.html)

### Inferences
- From practitioner experience, not a cited source: VoiceOver on macOS usually speaks "→" as "right arrow". NVDA and JAWS vary with the user's punctuation/symbol verbosity setting. So "Setup →" can be announced as "Setup right arrow, link". In SwiftUI, the way to keep the visible glyph out of speech is an explicit `.accessibilityLabel("Setup")` (2.5.3 is still satisfied, since the visible word is contained), or drawing the arrow as a separate `Image(systemName:)` with `.accessibilityHidden(true)`.
- Whether Voice Control accepts "Click Setup" for a control labelled "Setup →" is untested. Under the 2.5.3 punctuation note it probably does, but verify on a device.

### Gaps
- No vendor or W3C source found on per-screen-reader pronunciation of U+2192 (→) or U+2197 (↗). Needs hands-on testing (VoiceOver macOS, NVDA, JAWS).
- WCAG 3 drafts: not examined.
