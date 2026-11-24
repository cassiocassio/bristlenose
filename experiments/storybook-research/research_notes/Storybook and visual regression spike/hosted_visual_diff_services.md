# Hosted visual-regression services for a solo developer (as of 24 Nov 2026)

All vendor pages accessed 24 Nov 2026 unless marked otherwise. "Vendor page" means the vendor's own site; Argos-authored comparison blogs are marked as **vendor-biased (Argos)**. Fetches were done with a summarising fetch tool, so figures are as the page rendered on that date; FAQ accordions on Chromatic's pricing page did not render and are covered from its docs instead.

Worked-estimate basis used throughout: 150 stories × 2 colour schemes × 2 locales = **600 snapshots per browser per build**. At 20–40 builds/month that is **12,000–24,000/month with one browser** and **24,000–48,000/month with two** (before any change-only optimisation). Adding the "several colour themes" the brief mentions multiplies this further (e.g. 3 themes × 2 schemes × 2 locales = 1,800 per browser per build).

## Summary comparison table

| | Chromatic | Argos | Lost Pixel Platform | Percy (BrowserStack) | Happo (credible alternative) |
|---|---|---|---|---|---|
| Status | Active | Active | **Sunsetting; team joined Figma (22 Apr 2026); OSS repo archived same day** | Active | Active |
| Free tier | 5,000 billed snapshots/mo, **Chrome only**; "25k" equivalent TurboSnaps | Hobby: 5,000 screenshots/mo, one person, 30-day retention, commercial use allowed | Free 7,000/mo (page still up, product sunsetting) | 5,000 screenshots/mo, unlimited users, 1 month history | No free tier; 14-day unlimited trial; free for open source on request |
| Cheapest paid | Starter $179/mo, 35,000, $0.008 extra | Pro $100/mo, 35,000, $0.004 extra ($0.0015 Storybook) | Startup $100/mo, 40,000 | Desktop $199/mo (annual), 10k or 25k, $0.036 extra | Pay-as-you-go $4 per 1,000, no monthly fee; Team $199/mo for 66,000 |
| Next tier | Pro $399/mo, 85,000 | Enterprise (custom) | Business $250, Scale $670 | Desktop & Mobile $599/mo, $0.048 extra | Pro $599/mo, 300,000 |
| At the cap | Free: testing and review **paused** until reset or upgrade; paid: billed at period end | Hobby: uploads **paused** until renewal; email at 90%; Pro: billed | n/a | Not stated | Budget you set; runs pause at budget; extra at plan rate |
| Who renders | Chromatic's Capture Cloud | **You** (your CI; Argos only diffs) | You (OSS engine in your CI) | Percy's cloud re-renders | Happo's cloud |
| Safari/WebKit | Paid only (Starter+); "Safari 26.0" in Capture 8; OS not stated | Whatever you run (Playwright WebKit on Linux or macOS runner) | Engine claimed Chrome/Firefox/Safari | Listed (Safari, Safari on iPhone); Percy-managed fixed OS; Safari on macOS updated annually | Chrome, Firefox, Safari, Edge on every plan; OS not stated |
| What is uploaded | Built Storybook (see note) | Screenshots only | Screenshots | DOM snapshot + assets (per third-party description) | Not researched |
| Retention | Minimum 12 months, all plans | Hobby 30 days, Pro 1 year | n/a | Free 1 month, Desktop 1 year | Not researched |
| Open source | Storybook is OSS; Chromatic service is not | Platform MIT-licensed; self-hosting "not officially supported" | MIT, archived/read-only | No | No |

## Chromatic: limits, snapshot counting, TurboSnap, Safari, upload, retention

### Takeaway
Free is 5,000 billed snapshots/month and Chrome only; Safari needs Starter ($179/mo, 35,000 snapshots). A snapshot is Tests × Builds × Browsers × Modes, TurboSnap copies cost 0.2, and the free plan hard-stops at the cap. Without TurboSnap the project overruns the free tier in its first 8 builds (one browser).

### Cited Findings
- Plans: Free $0, 5,000 billed snapshots/mo ("25k" equivalent TurboSnaps), "Test on Chrome"; Starter $179/mo, 35,000 (175k TurboSnaps), "Extra billed snapshots $0.008", "Test on Safari, Firefox, Edge"; Pro $399/mo, 85,000 (425k TurboSnaps); Enterprise custom with "Data retention" listed — [Chromatic pricing](https://www.chromatic.com/pricing) (accessed 24 Nov 2026)
- Price conflict: a search-engine summary of third-party pages cited Chromatic's entry tier as "$149/mo with 35,000 snapshots"; Chromatic's own page on 24 Nov 2026 says $179. Treat $179 as current; the $149 figure is likely an older price — [Chromatic pricing](https://www.chromatic.com/pricing); [search summary of Argos comparison pages](https://argos-ci.com/blog/percy-vs-chromatic-vs-argos) (third-party, vendor-biased, page returned 404 on direct fetch)
- Counting: "visual snapshots = Tests x Builds x Browsers x Modes"; "accessibility snapshots = Tests x Builds x Modes"; interaction tests are not billed — [Chromatic billing docs](https://www.chromatic.com/docs/billing/)
- TurboSnap billing: copied snapshots "cost 0.2 billed snapshots each"; bypassed snapshots (nothing in any test's dependencies changed) cost 0 — [Chromatic billing docs](https://www.chromatic.com/docs/billing/)
- At the cap (free): "Review and testing will be paused once you use all 5,000 included billed snapshots per month"; resume by upgrading or waiting for the reset; paid plans are not interrupted and overage is charged at period end — [Chromatic billing docs](https://www.chromatic.com/docs/billing/)
- Retention: "Chromatic guarantees a minimum of 12 months of data retention for builds and snapshots on all plans" — [Chromatic billing docs](https://www.chromatic.com/docs/billing/)
- TurboSnap requirements: uses Git history and "the dependency graph generated by Webpack or Vite"; bypassed builds need CLI 17.7.0+. Full retest triggers include changes to Storybook `main`/`preview` files, **any file imported by `preview.js|ts`**, the static folder, a missing/out-of-sync lockfile, or `--force-rebuild` — [Chromatic TurboSnap docs](https://www.chromatic.com/docs/turbosnap/)
- Browsers: Chrome, Firefox, Safari, Edge; "Chrome is enabled by default"; "Chromatic does not support running tests on specific browser versions"; latest stable, which "can be behind the latest version"; "Upgrades can cause subtle changes in story appearance" — [Chromatic browsers docs](https://www.chromatic.com/docs/browsers/)
- Capture 8 (4 Nov 2025): Chrome 140, Firefox 141.0, **Safari 26.0**, Edge 140; "Certain combinations of colors, layered images, and CSS filters can cause a color shift in Safari" due to "WebKit's image rendering" — [Chromatic blog, Capture 8](https://www.chromatic.com/blog/capture-8-is-now-available/)
- Chromatic's troubleshooting docs say Chrome and Firefox snapshots are captured in a Linux environment; Safari is not named in that sentence — [Chromatic troubleshooting snapshots](https://chromatic.com/docs/troubleshooting-snapshots) (via search summary)

### Inferences
- TurboSnap appears to be on the free plan: the pricing page quotes "25k" equivalent TurboSnaps for Free, which is exactly 5,000 ÷ 0.2. Not stated in words.
- The "Safari 26.0" version label suggests a real Safari build (Playwright's WebKit is not versioned as Safari), but where it runs (macOS vs Linux) is unconfirmed.
- TurboSnap's value is weaker for this project than usual: theme tokens, global CSS and locale loading are typically imported by `preview.ts`, and every change there retests everything. A design-system-heavy SPA will hit full rebuilds often.
- Worked estimate (600 snapshots per browser per build):
  - Free, Chrome only, no TurboSnap: 12,000–24,000/mo against 5,000. The cap is reached after about 8 builds and testing pauses. Not viable.
  - Free, Chrome only, TurboSnap, about 10% of stories changed per build: 600 × (0.1 + 0.9 × 0.2) ≈ 168 per build, so 3,360–6,720/mo. It fits at 20 builds and overruns at 40. Any full-retest build costs 600.
  - Starter, Chrome + Safari (1,200 per build), no TurboSnap: 24,000–48,000/mo. At 40 builds the 13,000 overage × $0.008 ≈ $104, about **$283/mo** in total. With TurboSnap it stays within 35,000 for **$179/mo**.
- Upload: Chromatic's Storybook workflow publishes the built static Storybook (JS/CSS/assets) to Chromatic, which then renders it. This comes from general knowledge of the product and was not re-verified on a docs page in this session (see Gaps).

### Gaps
- No Chromatic page found stating the OS that Safari captures run on, or whether it is Apple Safari or a WebKit build.
- TurboSnap availability on Free is inferred from the "25k" figure, not stated.
- The pricing FAQ answers ("What's a snapshot?", exceeding limits) did not render; the billing docs were used instead.
- The upload contents and its storage region and deletion were not verified on a Chromatic page in this session. SOC 2 / GDPR posture was not researched.

## Argos: tiers, integrations, browsers, open source, data handling

### Takeaway
Argos only diffs screenshots that your own CI captures, so the browser is whatever you run, and Playwright WebKit counts. Hobby is free for 5,000/month for one person; Pro is $100/mo for 35,000 with very cheap Storybook overage. It is MIT-licensed, but self-hosting is unsupported. It is the cheapest hosted route to a WebKit diff, and with the caveat that Linux WebKit is not macOS Safari.

### Cited Findings
- Hobby $0: "Up to 5,000" screenshots/mo, one person, 30-day media retention, commercial use and private repos allowed, 50 MB per media file; at the cap "you will not be able to upload any additional screenshots until your billing period renews"; email at 90% — [Argos pricing](https://argos-ci.com/pricing)
- Pro $100/mo: 35,000 screenshots, overage **$0.004 per screenshot ($0.0015 for Storybook)**, unlimited members, 1-year retention, 14-day trial; Enterprise custom (99.99% SLA, SAML/SCIM) — [Argos pricing](https://argos-ci.com/pricing)
- Open-source projects' screenshots "are public" — [Argos pricing](https://argos-ci.com/pricing)
- Capture model: "Your tests capture screenshots in CI", and Argos compares them — [Argos docs (llms-full)](https://argos-ci.com/docs/llms-full.txt)
- Storybook paths: Storybook 9+ Vitest addon via `@argos-ci/storybook` and `argosVitestPlugin()` ("captured automatically in Chromium"); the Test Runner (v8+) with `argosScreenshot(page, context)` in `postVisit` then `argos upload`; Storycap for older versions. "Argos reads `parameters.chromatic.modes`", so Chromatic-style modes for themes and viewports carry over — [Argos docs (llms-full)](https://argos-ci.com/docs/llms-full.txt)
- Open source: the platform is "MIT-licensed" (`argos-ci/argos`). Self-hosting is not officially supported (AWS + PostgreSQL, RabbitMQ, Redis, S3, DynamoDB; you are "on your own to deploy and operate them") — [Argos docs (llms-full)](https://argos-ci.com/docs/llms-full.txt)
- Security: "SOC 2 Type II" (Prescient Security auditor, Vanta monitoring); "GDPR compliant", SCCs, DPA at argos-ci.com/dpa; screenshots on **AWS S3 in the United States, replicated to the EU**; encrypted at rest and in transit. Individual builds/screenshots **cannot be deleted on their own** (project/team/account deletion only; other requests go to support) — [Argos security](https://argos-ci.com/security)

### Inferences
- WebKit: because Argos ingests your screenshots, the Playwright SDK should accept screenshots from a Playwright `webkit` project. The docs excerpt only shows Chromium in quickstarts, and the Storybook Vitest addon says Chromium. Treat WebKit capture via the Vitest addon as **unverified**. The Test Runner path (Playwright page) is the more likely WebKit route.
- Linux Playwright WebKit is a WebKit build, not Safari on macOS, so text rendering and antialiasing will differ from WKWebView. Running the capture job on a GitHub `macos-*` runner would come closer. If the repo is public, those minutes are free on GitHub Actions; this is a GitHub fact not re-verified here.
- Public-repo caveat: if Argos treats the project as open source, its screenshots are public. That is harmless with synthetic fixtures, but it is worth knowing.
- Worked estimate (600 per browser per build; Storybook overage rate):
  - Hobby: 12,000–24,000/mo against 5,000. Uploads pause after about 8 builds. Not viable unless change-only capture or far fewer modes.
  - Pro, 1 browser: 12,000–24,000 is within 35,000, so **$100/mo**.
  - Pro, Chromium + WebKit: 24,000–48,000. At 40 builds the 13,000 × $0.0015 = $19.50 overage, about **$120/mo** (about $152 at the non-Storybook $0.004 rate).

### Gaps
- No Argos page fetched that explicitly lists WebKit as supported. The `/docs/browsers` URL returned "Page Not Found".
- Retention beyond the 30-day and 1-year media figures, and whether Argos has a TurboSnap-like "only changed stories" feature, were not found.
- No price history for Argos was found.

## Lost Pixel: OSS mode versus Platform

### Takeaway
Lost Pixel is no longer a viable choice. The team announced it was "sunsetting" the product and joining Figma on 22 Apr 2026, and the MIT-licensed OSS repo was archived (read-only) the same day. No shutdown date or data-deletion guidance was published.

### Cited Findings
- "We're sunsetting Lost Pixel." The post is dated 22 Apr 2026 (Dima Ivashchuk). It gives no shutdown date, data-deletion or migration guidance — [Lost Pixel blog](https://www.lost-pixel.com/blog/lost-pixel-team-is-joining-figma)
- The pricing page still lists Free 7,000/mo, Startup $100 (40,000, $0.006), Business $250 (100,000, $0.005) and Scale $670 (300,000, $0.004) under a banner "We are sunsetting the product" — [Lost Pixel pricing](https://www.lost-pixel.com/pricing)
- The GitHub repo shows "archived by the owner on Apr 22, 2026. It is now read-only"; it is MIT-licensed. It supported Storybook, Ladle, Histoire, Pages and Custom shots; "OSS mode" used `generateOnly: true` and `failOnDifference: true`; the README claims "Multiple browser execution (Chrome, Mozilla, Safari)" — [lost-pixel GitHub](https://github.com/lost-pixel/lost-pixel)
- Argos has published a "Lost Pixel Alternatives in 2026" migration piece (vendor-biased; 404 on direct fetch) — [Argos blog (search result)](https://argos-ci.com/blog/lost-pixel-alternatives)

### Inferences
- The OSS engine still runs as an archived MIT tool, but it will receive no fixes for future Storybook or Playwright versions. With Storybook 10 / Vite 8 churn, adopting it in late 2026 means inheriting a fork.

### Gaps
- Platform shutdown date and data deletion: not published.

## Percy (BrowserStack): free tier, browsers, pricing

### Takeaway
Percy has a 5,000/month free tier and lists Safari (desktop and iPhone) on Percy-managed infrastructure. Paid plans start at $199/mo (annual) with very expensive overage at $0.036. It is the most expensive option for this workload.

### Cited Findings
- Free: $0, 5,000 screenshots/mo, unlimited users, "Cross-browser support", 1 month build history. Desktop: $199/mo billed annually, 10,000 or 25,000 or custom, **$0.036 per additional screenshot**, 1-year history. Desktop & Mobile: $599/mo (annual), $0.048 extra. Enterprise on enquiry — [BrowserStack Percy pricing](https://www.browserstack.com/pricing?product=percy)
- Supported browsers: "Safari, Chrome, Edge, Safari on iPhone, Chrome on Android", Firefox; up to 10 widths per snapshot (120–2000 px) — [Percy browser compatibility](https://browserstack.com/docs/percy/common-issue/browser-compatibility)
- Percy renders on its own infrastructure; "Each browser runs on a fixed operating system that Percy manages"; Safari on macOS and mobile browsers are updated annually, other desktop browsers every two quarters; Percy "does not support localhost proxying on Safari" — [Percy cross-browser settings](https://www.browserstack.com/docs/percy/project-settings/cross-browser) (via search summary)
- Cross-browser insights is on paid plans only and "only in the old version of the Percy dashboard" — [Percy cross-browser insights](https://www.browserstack.com/docs/percy/ai-agents/visual-review-agent/cross-browser-insights) (via search summary)
- Architecture (as described by a competitor): Percy uploads a DOM snapshot and re-renders it in the cloud, and every browser × width counts as a screenshot — [Argos comparison (search summary; vendor-biased)](https://argos-ci.com/blog/percy-vs-chromatic-vs-argos)

### Inferences
- "Safari on macOS ... updated annually" implies real macOS Safari. That is the closest thing on this list to WKWebView rendering, but it lags up to a year.
- Worked estimate: 1 browser, 12,000–24,000 needs the 25k Desktop tier. The price for the 25k tier versus 10k is unclear ($199 may be the 10k price). 2 browsers at 48,000 is 23,000 × $0.036 ≈ $828 overage on top. Not viable for a cost-sensitive solo developer.

### Gaps
- Whether Safari is enabled on the free plan; the per-tier price for 25k; and how browser × width is billed were not stated on the pages fetched. Percy's data storage and region were not researched.

## Newer or credible alternatives

### Takeaway
Happo is the credible non-Storybook-vendor entrant. It renders in its own cloud with Chrome, Firefox, Safari and Edge on every plan, and its pay-as-you-go pricing has no monthly fee.

### Cited Findings
- Happo: pay as you go "$4 per 1,000 snapshots, no monthly fee"; Team $199/mo for 66,000; Pro $599/mo for 300,000; Enterprise from $1,499. A snapshot is "One screenshot of one component variant, story, or page, in one target". Chrome, Firefox, Safari and Edge are on every plan. There is a 14-day unlimited trial and it is free for open source on request. You set a budget and runs pause there, and "Extra snapshots cost your plan's own rate, never a higher one" — [Happo pricing](https://happo.io/pricing)
- Argos's own "9 best visual regression testing tools in 2026" and Applitools/Percy-alternatives posts exist, but they are vendor-biased (Argos) — [Argos blog](https://argos-ci.com/blog/best-visual-regression-testing-tools)

### Inferences
- Happo worked estimate (PAYG): 12,000 = $48, 24,000 = $96, 48,000 (2 browsers × 40 builds) = $192/mo. Each Safari capture is a separate "target", so the 2-browser number is the relevant one. Where Happo's Safari runs (macOS or not) is unverified.
- A "none" option, with Playwright `toHaveScreenshot` on WebKit and baselines committed to git, costs no service fee and uploads nothing. It loses the hosted review UI and needs baselines regenerated on the same OS/runner image. This is an inference, not researched here.

### Gaps
- Happo's rendering OS, retention, data region and SOC 2 were not researched. Applitools and Meticulous were not researched.

## Real-user reports: flakiness, review UX, lock-in, price rises, limits

### Takeaway
No independent, hands-on 2026 user reports were found. Nearly every 2026 comparison surfaced by search is written by Argos (a competitor), and their price figures for rivals disagree with the rivals' own pages.

### Cited Findings
- Search for 2026 comparisons returned mainly Argos-authored posts. The search summary flagged that their Chromatic/Percy figures were "not independently confirmed" — [Argos: Percy vs Chromatic vs Argos (search result)](https://argos-ci.com/blog/percy-vs-chromatic-vs-argos)
- Evidence of a price rise: Chromatic's entry tier is cited at $149 by third-party summaries and $179 on Chromatic's own page today — [Chromatic pricing](https://www.chromatic.com/pricing)
- Lock-in evidence, from Lost Pixel's shutdown: a hosted visual-diff vendor closed with no published shutdown date or data guidance — [Lost Pixel blog](https://www.lost-pixel.com/blog/lost-pixel-team-is-joining-figma)
- Chromatic warns that browser upgrades "can cause subtle changes in story appearance" (a source of whole-suite re-baselines it controls, not you), and lists a known Safari colour shift — [Chromatic browsers docs](https://www.chromatic.com/docs/browsers/); [Capture 8](https://www.chromatic.com/blog/capture-8-is-now-available/)

### Inferences
- Lock-in is lowest with Argos, which takes standard screenshots and is MIT, and with a git-baseline "none" option. It is highest with Chromatic and Percy, where the vendor's renderer *is* the baseline, so leaving means re-baselining on a new renderer.
- Cap behaviour differs in a way that matters for a solo developer: the Chromatic Free and Argos Hobby tiers hard-pause, which turns a busy week into a blind spot rather than a bill. Happo pauses at a self-set budget. Paid Chromatic, Argos and Percy plans bill overage.

### Gaps
- No GitHub issues, Reddit or HN threads with first-hand flakiness or review-UX reports were retrieved within the tool budget.

## Data handling: storage, retention, deletion, SOC 2 / GDPR

### Takeaway
Only Argos's posture was verified in detail: SOC 2 Type II, GDPR with a DPA, US S3 replicated to the EU, and no per-build deletion. Chromatic guarantees at least 12 months of retention. Percy's free tier keeps 1 month of history. With synthetic fixtures only, the main question is how much of the app gets uploaded: Chromatic and Percy receive the built front-end, while Argos receives only PNGs.

### Cited Findings
- Argos: SOC 2 Type II, GDPR, SCCs, DPA; AWS S3 in the US replicated to the EU; individual builds can't be deleted on their own — [Argos security](https://argos-ci.com/security)
- Argos retention: Hobby 30 days, Pro 1 year — [Argos pricing](https://argos-ci.com/pricing)
- Chromatic: minimum 12 months retention on all plans; Enterprise lists "Data retention" as a configurable feature — [Chromatic billing docs](https://www.chromatic.com/docs/billing/); [Chromatic pricing](https://www.chromatic.com/pricing)
- Percy: 1 month build history on Free, 1 year on Desktop — [Percy pricing](https://www.browserstack.com/pricing?product=percy)

### Inferences
- Uploading a built Storybook (Chromatic) or a DOM plus assets (Percy) sends the vendor the compiled front-end code, CSS, fonts and locale strings, not just pixels. For an AGPL public repo that is already public. It matters only if unreleased features sit in stories.

### Gaps
- Chromatic's and Percy's SOC 2 / GDPR status, data region and deletion process were not verified in this session.
