# Self-hosted visual regression with Playwright (option A: extend the E2E suite; vs B/C: Storybook-based)

Research date: 24 Nov 2026. Current versions seen in the sources: Playwright docs show v1.64.1 (Docker tags `v1.64.1-noble`, `-jammy`, `-resolute`); Vitest docs site shows v5.1.1. 16 tool calls; several practitioner sources are vendor blogs (Argos, Diffy, TestQuality, BrowserStack) and are flagged as such.

## Cross-OS rendering: why macOS and Linux screenshots differ, and Playwright's guidance

### Takeaway
Playwright's own position is that a baseline is only valid on the OS, browser build and settings that made it. The filename carries the platform (`-darwin.png` vs `-linux.png`), so a Mac-made baseline is never even compared on Linux CI. The standard fix is to make and compare baselines inside the official, version-pinned Playwright Docker image, locally and in CI alike, and to self-host the web fonts.

### Cited Findings
- Playwright warns: "Browser rendering can vary based on the host OS, version, settings, hardware, power source". Headless vs headed is also a factor. It also says "Screenshots differ between browsers and platforms due to different rendering, fonts and more". The guidance is to run tests in the same environment that made the baselines. [Playwright: Visual comparisons](https://playwright.dev/docs/test-snapshots)
- Baselines go into `<spec>-snapshots/`, named `<name>-<project>-<platform>.png` (e.g. `example-test-1-chromium-darwin.png`). The path can be changed with `testConfig.snapshotPathTemplate`. WebP is supported via a `.webp` name or the `type` option. Playwright says: "You should commit this directory to your version control (e.g. `git`), and review any changes to it." [Playwright: Visual comparisons](https://playwright.dev/docs/test-snapshots)
- `--update-snapshots [mode]` (`-u`) accepts `all`, `changed`, `missing`, `none` and `default`. The bare flag means `changed`, and no flag means `default`. Related flags: `--ignore-snapshots`, `--repeat-each <N>`, `--fail-on-flaky-tests`, `--only-changed [ref]`. [Playwright CLI](https://playwright.dev/docs/test-cli)
- Docker image: `mcr.microsoft.com/playwright:v1.64.1-noble` (Ubuntu 24.04), plus `-jammy` (22.04) and `-resolute` (26.04). Playwright says "It is recommended to always pin your Docker image to a specific version if possible". If the image and the npm package disagree, Playwright "will be unable to locate browser executables". It recommends `--init` and `--ipc=host` (the latter for Chromium). [Playwright: Docker](https://playwright.dev/docs/docker)
- **Remote-server mode lets a macOS developer render in Linux without running the tests in Docker.** Run `run-server --port 3000 --host 0.0.0.0` in the container, then set `PW_TEST_CONNECT_WS_ENDPOINT=ws://127.0.0.1:3000/` on the host. To reach the host's dev server from the container, add `--add-host=hostmachine:host-gateway` and use the `hostmachine` hostname. The Playwright version in the tests must match the container's. [Playwright: Docker](https://playwright.dev/docs/docker)
- Causes listed by a vendor post (Diffy, 6 Nov 2026):
  - Different system fonts per OS, where fallback fonts change line wrapping and shift the layout below.
  - Headed Chromium and the headless shell are separate builds.
  - GPU, display scaling and power source shift anti-aliasing by about a pixel.
  - The default `scale: "css"` keeps a Retina laptop from producing 2x images.
  - Its fixes: baselines in the pinned image via `docker run --rm --ipc=host --init … npx playwright test --update-snapshots`; in GitHub Actions, run the job in the same image (`options: --user 1001`); self-host and preload fonts; use thresholds sparingly.
  - It gives no measured pixel deltas.

  [Diffy blog](https://diffy.website/blog/playwright-screenshots-ci-docker/)
- Practitioner guides agree that baselines captured on macOS and compared on Linux CI is the main flake source. The ongoing cost is that every baseline update must go through Docker or a CI round-trip. "Forget once, and the PR turns red with diffs that have nothing to do with the change." Several of these guides are vendor or SEO-style. [TestQuality guide](https://testquality.com/?p=7894); [adequatica, Apr 2025: OS-independent screenshot testing with Playwright and Docker](https://adequatica.github.io/2025/04/10/operating-system-independent-screenshot-testing-with-playwright-and-docker.html)
- **CI-commit pattern for baselines:** a GitHub Action runs `--update-snapshots` and commits with `stefanzweifel/git-auto-commit-action@v5` (vendor source, which calls it "workable"). [Argos: Playwright VRT in CI](https://argos-ci.com/blog/playwright-visual-regression-testing-ci)
- Vitest's visual-regression docs give an equivalent manually triggered `workflow_dispatch` workflow:
  - runs only on non-default branches, with a concurrency group;
  - runs `npm run test:visual --update` on Ubuntu 24.04 / Node 24;
  - commits only if screenshots changed, credits the triggering user as co-author, and writes a job summary of changed files;
  - warns that "running updates locally produces screenshots that may not match the CI environment" (paraphrase).

  [Vitest: Visual Regression Testing](https://main.vitest.dev/guide/browser/visual-regression-testing)

### Inferences
- **The project's fit with Docker:** the developer works on Apple silicon and CI runs Linux x86_64, so the cleanest loop is:
  1. Pin `@playwright/test` and the Docker tag to the same version.
  2. Generate and update baselines only through (a) the container, using the remote-server mode above, or (b) a `workflow_dispatch` "update screenshots" job.
  3. Commit only `-linux.png` baselines.
  4. Add a guard so local macOS runs skip screenshot assertions or use `--ignore-snapshots`. Otherwise they fail for lack of `-darwin` files.
- The image is amd64 and arm64-capable (Playwright publishes multi-arch images; not confirmed on the page fetched). An arm64 container on the Mac may still differ from x86_64 CI in rare float/raster paths. Treat cross-arch equality as a spike measurement, not an assumption.
- With web fonts self-hosted (the app already uses web fonts), the biggest single cross-OS variable (system font fallback) mostly goes away. Hinting and anti-aliasing differences remain, which is why the platform suffix exists.

### Gaps
- No source fetched explained font hinting, subpixel AA, or FreeType vs Core Text rasterisation in detail, and none had measured pixel deltas. The Diffy article explicitly does not cover hinting or colour profiles.
- Not verified: whether the Playwright Docker image is multi-arch (arm64) and whether arm64-Linux and amd64-Linux WebKit screenshots are pixel-identical.

## How faithful is Playwright's WebKit on Linux to Safari / WKWebView on macOS? Can it run on GitHub macOS runners?

### Takeaway
Playwright's WebKit is a patched build of WebKit trunk, not Safari. Playwright says WebKit on Linux is the cheapest option, and points to macOS for the closest-to-Safari behaviour. Linux WebKit screenshots therefore catch CSS and layout regressions, but not WKWebView-specific rendering. Running on a GitHub macOS runner costs about 10x per minute ($0.062 vs $0.006), and its baselines would be `-darwin` and separate from Linux ones.

### Cited Findings
- Playwright's WebKit is "derived from the latest WebKit main branch sources". Playwright "doesn't work with the branded version of Safari since it relies on patches". Feature availability "may vary between operating systems", with media codecs differing notably across Linux, macOS and Windows. The page says Linux CI is the most affordable option and recommends macOS for the closest Safari experience (e.g. video playback). It makes no claim of exact Safari parity. [Playwright: Browsers](https://playwright.dev/docs/browsers)
- A GitHub PR adding Safari snapshots via Playwright WebKit says WebKit on Linux uses a different network stack and compositor than on macOS, "so screenshots do not match" (search snippet, not fetched in full). [adriangohjw/storybranch PR #40](https://github.com/adriangohjw/storybranch/pull/40)
- Concrete font bug, now fixed: WebKit on Ubuntu (Docker `v1.32.3-jammy`) failed to render the weights of Montserrat that macOS rendered correctly. A maintainer reproduced it and found it fixed in 1.33, and the issue was closed 19 Apr 2023. Later comments (Dec 2023, v1.40.1 on Windows; Nov 2024, v1.47.0 on Windows/Azure) report the same symptom with no maintainer reply. [microsoft/playwright #22429](https://github.com/microsoft/playwright/issues/22429)
- GitHub-hosted runner prices: Linux 2-core x64 $0.006/min, Linux 2-core arm64 $0.005/min, macOS 3/4-core (M1 or Intel) $0.062/min. "Larger runners are not free for public repositories." [GitHub Docs: Actions runner pricing](https://docs.github.com/en/billing/reference/actions-runner-pricing)

### Inferences
- **Divergence expected between Linux WebKit and WKWebView on macOS:**
  - Font rasterisation: FreeType/Linux vs Core Text.
  - Native form controls and scrollbars: the macOS port draws AppKit-style controls and overlay scrollbars, while the Linux (WPE/GTK) port draws its own.
  - Colour management: macOS colour-manages to the display profile, while headless Linux is effectively sRGB.
  - Media codecs.

  This list comes from general WebKit port knowledge; only codecs and "closest to Safari on macOS" are confirmed by the sources above. Screenshots should therefore assert *layout and token* regressions, not "this is what the Mac app looks like".
- For a WKWebView-first product, Linux WebKit baselines are a regression tripwire, not a fidelity check. A small `-darwin` set on a macOS runner (or locally on the dev Mac) would be the only way to watch Mac-native details (scrollbars, form controls, font weight rendering). It doubles baseline maintenance, so scope it to a handful of shots if at all.
- Bristlenose's repo is public. Standard GitHub-hosted runners (including the standard macOS runner) have historically been free for public repos, so the $0.062/min figure may not bill. This is not confirmed on the fetched page, which only says *larger* runners are not free for public repos; check the billing page. macOS runners are also typically slower to queue and boot than Linux ones (no measured figure found).
- WKWebView itself cannot be driven by Playwright. A true WKWebView screenshot would need the macOS app's own XCUITest/snapshot tooling, which is out of scope for this note.

### Gaps
- Not found: a 2025–2026 source measuring the pixel diff between Linux Playwright WebKit and macOS Playwright WebKit or Safari for the same page.
- No measured macOS-runner speed or queue time for Playwright screenshot jobs.
- Not confirmed: whether standard macOS runners are free for public repos in Nov 2026, and any 2026 GitHub price change.

## Flakiness controls

### Takeaway
Playwright's defaults already remove the two biggest sources: `animations: "disabled"` and `caret: "hide"`. The assertion also retries until two consecutive captures match. The remaining work is app-side determinism: frozen clock, stopped polling, fonts loaded, mouse moved away, volatile regions masked or hidden via `stylePath`. Loosen thresholds last.

### Cited Findings
- `toHaveScreenshot` options and defaults (added v1.23):

  | Option | Default | Behaviour |
  |---|---|---|
  | `animations` | `"disabled"` | Finite CSS animations, transitions and Web Animations jump to the end; infinite ones reset to the start and replay after capture |
  | `caret` | `"hide"` | |
  | `scale` | `"css"` | |
  | `mask` | none | Array of Locators overlaid with a box, including invisible elements |
  | `maskColor` | `#FF00FF` | Added v1.35 |
  | `stylePath` | none | String or array of CSS files applied during capture; pierces Shadow DOM and inner frames; added v1.41 |
  | `threshold` | `0.2` | YIQ per-pixel tolerance, range 0–1 |
  | `maxDiffPixels`, `maxDiffPixelRatio` | none | Set via the config |
  | Other options | | `fullPage` (default false), `clip`, `omitBackground`, `timeout` |

  [Playwright API: PageAssertions.toHaveScreenshot](https://playwright.dev/docs/api/class-pageassertions#page-assertions-to-have-screenshot-1)
- Stability retry: "The assertion keeps taking screenshots until two consecutive captures match", then compares against the stored expectation within `timeout` (paraphrase). [Playwright API](https://playwright.dev/docs/api/class-pageassertions#page-assertions-to-have-screenshot-1)
- "Screenshots capture any hover effects present in the page at the moment", so move the mouse away (e.g. to `-1,-1`) before capture. `stylePath` "allows filtering out dynamic or volatile elements, hence improving the screenshot determinism." [Playwright: Visual comparisons](https://playwright.dev/docs/test-snapshots)
- Freeze time with `page.clock.setFixedTime()`, mask dynamic regions, and hide elements via `stylePath`. An example `maxDiffPixelRatio` is 0.01. [Diffy blog](https://diffy.website/blog/playwright-screenshots-ci-docker/)
- Common flake sources are animations, network requests and dynamic content. Avoid fixed sleeps ("Tests that wait for time are inherently flaky", quoting Playwright guidance), and adjust tolerances only after fixing instability. [TestQuality guide](https://testquality.com/?p=7894); [Argos: fix flaky visual tests](https://argos-ci.com/blog/fix-flaky-visual-tests) (vendor)
- Vitest recommends `allowedMismatchedPixelRatio` over a fixed pixel count. If both are set, the stricter one applies, and there is no default tolerance. [Vitest: Visual Regression Testing](https://main.vitest.dev/guide/browser/visual-regression-testing)

### Inferences
- **Checklist for this app** (assembled from the above; the `document.fonts.ready` and polling items are standard practice, not sourced here):
  1. Self-hosted fonts, then `await page.evaluate(() => document.fonts.ready)` before capture.
  2. `page.clock.install()` / `setFixedTime()` before navigation, so relative timestamps ("2 minutes ago") and polling intervals are frozen.
  3. Stub the live-polling endpoints with `page.route()` to return a fixed payload, or mask the polling region.
  4. One shared `stylePath` CSS file that kills `transition`, spinner keyframes and skeleton shimmer, and hides video and thumbnail elements.
  5. Hover reset via `page.mouse.move(-1, -1)`.
  6. A fixed viewport and `deviceScaleFactor`.
  7. Explicit `colorScheme` (`page.emulateMedia({ colorScheme })`) and a set locale per project.
  8. Start with `threshold` 0.2 and `maxDiffPixels: 0`, and loosen only with evidence.
- The two-consecutive-match retry means a constantly animating or polling region produces a *timeout*, not a silent pass. That is a useful signal in a spike, because it shows the determinism setup is incomplete.

### Gaps
- No source fetched gave flake-rate numbers for a tuned self-hosted suite.

## Baseline management: repo size, LFS, diff review, how many screenshots one person can review

### Takeaway
Committing PNGs is the official model. Its costs are permanent git-history growth (every UI change rewrites PNGs), merge conflicts, and a review UI limited to the Playwright HTML report and trace viewer. For a solo developer, conflicts largely disappear; size and review fatigue remain. LFS helps clone size but is not free on GitHub, and adds friction for CI auto-commits.

### Cited Findings
- The official workflow is to commit the `-snapshots` directory and review changes to it. Snapshots can be stored as WebP, which is smaller than PNG. [Playwright: Visual comparisons](https://playwright.dev/docs/test-snapshots)
- Hundreds of PNGs rewritten on every UI change "bloat git history permanently", and even with Git LFS clones and checkouts slow over time. This is a vendor source selling hosted baselines. [Argos: Playwright VRT in CI](https://argos-ci.com/blog/playwright-visual-regression-testing-ci)
- Large snapshot folders are often kept in Git LFS. [BugBug blog](https://bugbug.io/blog/software-testing/playwright-visual-regression-testing/)
- Full-page screenshots of long pages can be several MB and slow git over time; prefer element-level shots. [DEV: Playwright VRT](https://dev.to/grabbit/playwright-visual-regression-testing-catch-ui-bugs-in-ci-31eh)
- Team-scale critique (Apr 2025, by the Argos author on HN; the thread had only that one comment):
  - snapshots in Git conflict;
  - comparisons run against your last push, not production;
  - updates need manual runs;
  - results are hard to review without a proper UI;
  - flaky diffs come from platform inconsistencies.

  [HN: Why Playwright's visual testing breaks down in teams](https://news.ycombinator.com/item?id=43653464)
- Vitest warns: "screenshots for deleted or renamed tests aren't removed automatically". Stale references must be cleaned by hand. [Vitest: Visual Regression Testing](https://main.vitest.dev/guide/browser/visual-regression-testing)

### Inferences
- **Size estimate** (arithmetic, not sourced):
  - One axis set (light/dark × 2 browsers) multiplies every shot by 4. Adding even 3 colour themes × 3 sample locales multiplies by 36.
  - 20 shots × 4 = 80 baselines at roughly 50–300 KB each is about 4–24 MB per full regeneration in history.
  - The full matrix (20 × 2 × 2 × themes × 21 locales) runs into the thousands. That is untenable for one reviewer and for git.
  - Scope the matrix: all pages in one locale and theme; one or two "stress" locales (a long-string one such as German, and a CJK or RTL-like one if supported) on a few key components; themes on a token-swatch page or one representative screen.
- Playwright's HTML report shows expected, actual and diff with a slider, and the trace viewer shows the DOM at failure (well known; not re-fetched here). This is adequate for one person. It is weak for reviewing 50+ intentional changes after a token edit, which is where hosted tools earn their fee.
- Prefer `.webp` baselines and element- or viewport-level shots over `fullPage` to keep size down. Stay off LFS unless history size proves a problem in the spike: LFS bandwidth and storage are metered on GitHub, and auto-commit jobs must have LFS configured.

### Gaps
- No primary source gave an empirical "N screenshots is too many for one reviewer" figure. No measured repo-growth numbers from a real project were found.

## Element-level vs full-page, and on-page component screenshots as a substitute for stories

### Takeaway
Element-level screenshots (`expect(locator).toHaveScreenshot()`) are smaller, less brittle to unrelated layout changes, and need no extra harness. In an existing E2E suite they are the "stories-free" way to get component coverage. The trade-off is that you only get the states the fixture project and the real routes produce. Stories can reach edge states (empty, error, 200-character name) on demand.

### Cited Findings
- Full-page screenshots of long pages can be several MB. Element-level screenshots are the suggested remedy. [DEV: Playwright VRT](https://dev.to/grabbit/playwright-visual-regression-testing-catch-ui-bugs-in-ci-31eh)
- Vitest likewise advises scoping screenshots to a component rather than a whole page. [Vitest: Visual Regression Testing](https://main.vitest.dev/guide/browser/visual-regression-testing); [Argos: Vitest visual testing](https://argos-ci.com/blog/vitest-visual-testing)
- The same option set (`mask`, `stylePath`, `animations`) applies to both the page and locator forms. [Playwright API](https://playwright.dev/docs/api/class-pageassertions#page-assertions-to-have-screenshot-1)
- Argos's own 2026 roundup concedes its fit "is weaker" if visual tests live in Playwright E2E suites rather than stories (vendor framing). [Argos: best VRT tools 2026](https://argos-ci.com/blog/best-visual-regression-testing-tools)

### Inferences
- **Option A** (E2E plus locator screenshots):
  - Zero new tooling. It reuses the server, fixture and route walk the suite already has.
  - It tests the real composition: tokens, cascade, the SPA's actual data.
  - Costs: each shot runs the whole app, so it is slower per shot than a story. A fixture-data change cascades into many baseline updates. Hard-to-reach states need `page.route()` stubs or extra fixture data.
- **Option B** (Playwright over Storybook `index.json` stories):
  - Gains isolated, enumerable states and a natural one-story-one-shot inventory.
  - Costs: writing and maintaining stories (mocks for API and stores), a second server in CI, and the same Docker/baseline discipline as A.
  - It does not remove any of A's cross-OS or flake work.
- **Option C** (Storybook addon-vitest): see the next section. Native screenshot assertions were not supported as of Dec 2025.
- For a solo developer with an existing route-walking suite, A is the cheaper first spike. B only pays off if stories are wanted anyway (docs, isolated development).

### Gaps
- No 2025–2026 primary source directly compared on-page locator screenshots with story screenshots in maintenance hours.

## Option B/C status: Storybook test-runner and addon-vitest screenshots

### Takeaway
Vitest browser mode has a native `toMatchScreenshot` (added in Vitest 4, current docs at v5.1.1), with platform-suffixed references and the same stabilisation model as Playwright. Storybook's addon-vitest did not expose it in story tests as of Nov/Dec 2025: it threw `Invalid Chai property: toMatchScreenshot`, and Storybook's line was "use Chromatic". Workarounds are third-party (`repobuddy/visual-testing` / storybook-addon-vis) or a standalone Vitest browser test that imports stories via `composeStories`.

### Cited Findings
- Vitest 4 added visual regression testing in Browser Mode via `toMatchScreenshot`. [Vitest 4.0 announcement](https://vitest.dev/blog/vitest-4)
- How Vitest's `toMatchScreenshot` works:
  - Reference names include browser and platform.
  - It takes repeated screenshots until two are stable, then makes a final diff.
  - Comparator: `pixelmatch`, with `threshold` and `allowedMismatchedPixelRatio`/`allowedMismatchedPixels`; third-party comparators such as `@blazediff/ssim` can be plugged in.
  - With the Playwright provider, animations are disabled by default and `mask` is available.
  - It recommends Docker, CI-only references, or a cloud service.
  - It warns "`toMatchScreenshot` is not a substitute for proper assertions".

  [Vitest: Visual Regression Testing](https://main.vitest.dev/guide/browser/visual-regression-testing)
- **Storybook discussion #32930** (3 Nov 2025):
  - Using `toMatchScreenshot` in a Storybook Vitest addon test threw `Invalid Chai property: toMatchScreenshot`.
  - The only reply (a bot, not a maintainer) said there was no integration or roadmap: "Storybook continues to recommend Chromatic for visual regression testing."
  - The asker's accepted answer (8 Dec 2025) points to Storybook's migration guide, which names `repobuddy/visual-testing` as the replacement for `jest-image-snapshot` (the old test-runner pattern).
  - No later reply reports native support.

  [storybookjs/storybook discussion #32930](https://github.com/storybookjs/storybook/discussions/32930)
- Workarounds reported: a standalone browser-mode test pulling stories via `composeStories` and calling `toMatchScreenshot`; Argos's Storybook integration, which captures every story the Vitest addon runs (vendor); `storybook-addon-vis` as a per-story harness. [Argos: Vitest visual testing](https://argos-ci.com/blog/vitest-visual-testing); [pagopa/ui issue #71](https://github.com/pagopa/ui/issues/71)

### Inferences
- Option C, "addon-vitest screenshots", is not first-party. It depends on a third-party addon or a hand-written `composeStories` test file. Both reintroduce the same platform-suffix and Docker baseline discipline as option A, plus a Storybook to maintain.
- The older `@storybook/test-runner` (Jest + Playwright) supported `jest-image-snapshot` in `postVisit` hooks. Storybook's migration guidance treats that as superseded by addon-vitest (inferred from discussion #32930; test-runner docs not fetched).

### Gaps
- Not verified: whether Storybook 10.x (2026) added native `toMatchScreenshot` support after Dec 2025. I did not fetch current Storybook docs.
- `@storybook/test-runner` docs were not fetched, so its current maintenance status is unconfirmed.

## Real reports (2024–2026): kept, moved to hosted, or dropped

### Takeaway
I found no first-person, non-vendor case study from 2024–2026 of a team keeping, dropping or migrating away from self-hosted Playwright screenshots. The material is dominated by vendor blogs (Argos, Chromatic, Percy, Diffy). They converge on the same pain points: cross-OS baselines, git bloat and conflicts, a manual update loop, and review UI. These are mostly team-scale problems, and a solo developer avoids the conflict one.

### Cited Findings
- The Argos author's argument (Apr 2025) is that built-in `toHaveScreenshot` is "fast, simple, and local" and fine for small projects, but fragile with multiple contributors. The pain points are Git conflicts, comparison against the last push rather than production, manual updates, a weak review UI, and platform flake. [HN item 43653464](https://news.ycombinator.com/item?id=43653464)
- Chromatic says it reduces flake by rendering captured page archives on standardised cloud browsers, piggybacking on existing Playwright tests (vendor marketing). [Chromatic: Playwright comparison](https://www.chromatic.com/compare/playwright)
- Argos positions itself as an open-source alternative to Chromatic and Percy, capturing locally in the browser the tests already run and adding flake detection and traces (vendor). [Argos](https://argos-ci.com/); [Argos: best VRT tools 2026](https://argos-ci.com/blog/best-visual-regression-testing-tools)
- Practitioner guides (2025–2026) name platform lock-in, i.e. every update through Docker or CI, as the ongoing tax. [TestQuality](https://testquality.com/?p=7894); [OneUptime, Jan 2026](https://oneuptime.com/blog/post/2026-01-27-playwright-visual-testing/view)

### Inferences
- For a solo developer, the team-scale objections (conflicts, review across people) mostly fall away. What remains is the update loop through Docker or CI and the review burden after intentional global changes (token or theme edits). Those two are what a spike should measure.
- Hosted services (Argos has an open-source core and a free tier; Chromatic and Percy are paid) solve baseline storage and review UI. They do not solve app-side determinism, which is the same work in every option.

### Gaps
- No credible 2024–2026 non-vendor post found describing a team abandoning or keeping self-hosted Playwright VRT, with reasons and numbers. Recommend the report writer say so explicitly rather than generalise from vendor content.

## Spike scoping: time-box and measurable success / kill criteria

### Takeaway
I found no sourced practitioner framework specifically for time-boxing a VRT tooling spike. The criteria below are derived from the mechanics documented above (`--repeat-each`, `--fail-on-flaky-tests`, the platform-suffixed baselines, CI minute pricing), so the spike measures exactly the costs the sources identify.

### Cited Findings
- Measurement hooks Playwright already provides: `--repeat-each <N>` ("Run each test `N` times"), `--fail-on-flaky-tests`, `--only-changed [ref]`, and `--update-snapshots=changed|missing|all`. [Playwright CLI](https://playwright.dev/docs/test-cli)
- CI cost basis: Linux 2-core $0.006/min, macOS $0.062/min. [GitHub runner pricing](https://docs.github.com/en/billing/reference/actions-runner-pricing)
- Tune thresholds only after removing instability, so the false-positive rate should be measured before any threshold changes. [TestQuality](https://testquality.com/?p=7894)

### Inferences
Proposed spike shape (derived, not sourced): two to three days, option A only, WebKit and Chromium on Linux in the pinned Docker image.

**Scope**
- About 10 page-level and 10 locator-level shots across existing routes.
- Light and dark.
- One theme beyond the default.
- One long-string locale.

**Success criteria**
1. **Determinism:** 0 screenshot failures across `--repeat-each=20` locally in Docker and 5 consecutive CI runs, with `threshold` at the default 0.2 and `maxDiffPixels` ≤ a small fixed number (decide before the run).
2. **Cross-arch:** baselines made on the Mac via the Docker remote-server pass unchanged on GitHub's x86_64 runner. If they do not, the update loop must be CI-only, and that is the cost to record.
3. **Seeded-regression catch rate:** introduce about 5 deliberate regressions (a 1px padding token, a colour token in dark mode only, a font-weight change, a hidden icon, a long-locale overflow). The suite must catch at least 4 of 5, and you record which would have shipped.
4. **Cost to add:** a new locator screenshot takes 10 minutes or less from idea to committed baseline. A full intentional baseline refresh after a token change takes 15 minutes or less to review.
5. **CI time:** added wall-clock time per PR stays within a fixed number of minutes (e.g. ≤ 3). Record the CI minutes.
6. **Size:** bytes added to git per full regeneration, measured with `.webp` vs `.png`.

**Kill criteria**
- Any irreducible flake after the determinism checklist (more than 1 flaky shot in 100 runs).
- Mac-to-CI baselines never match and the CI-only update loop is judged too slow.
- The seeded-regression catch rate is below 3 of 5.
- Review of a token-change refresh exceeds about 30 minutes.

**Comparison step**
- Port 3–5 of the same component shots to option B (stories plus a Playwright loop over `index.json`) and record story-authoring time per component. That gives a like-for-like add-cost number.

### Gaps
- No sourced examples were found of published VRT spike or kill criteria from real teams. The criteria above are the researcher's synthesis and should be presented as such.
