# Storybook 10 setup and the real cost of mocking app state (React 19 + Vite 8 + TS 6 SPA)

Researched 24 Nov 2026. Version and date facts for npm packages come from the npm registry JSON (`registry.npmjs.org/<pkg>`), read on 24 Nov 2026. GitHub issue facts come from `gh issue view` on `storybookjs/storybook`. Nothing was installed.

Project grounding (read from this repo, not a web source): `frontend/package.json` pins `react ^19.2.5`, `vite ^8.0.10`, `typescript ~6.0.3`, `vitest ^4.1.5`, `i18next ^26.0.8`, `react-i18next ^17.0.6`, `react-router-dom ^7.14.2`, `@vitejs/plugin-react ^6.0.0`; `.tool-versions` is `node 24`. 34 files in `frontend/src` use `useSyncExternalStore`; 41 non-test files import `utils/api`; `utils/api.ts` has 77 top-level `export function/const` lines; `frontend/src/contexts/` holds 24 non-test store modules; 25 files under `bristlenose/theme/` use `light-dark(`.

## 1. Storybook 10's state as of late 2026 (ESM-only, Node, Vite 8/Rolldown, React 19, footprint, cold start)

### Takeaway
Storybook 10 (released 28 Oct 2025) is mature at 10.6.8 (20 Nov 2026). It officially supports Vite 8 since 10.3 (18 Mar 2026) and React 19, and the project's Node 24, TS 6 and Vite 8 all fit. One Vite 8 dev-mode bloat bug is still open (an upstream Vite bug). The big timing fact: Storybook 11 is in beta (11.0.0-beta.5, 23 Nov 2026), and its migration notes run to about 2,200 lines, so a setup started on 10.x now will soon face a large major upgrade.

### Cited Findings
- **10.0 release:** published 28 Oct 2025. ESM-only (CommonJS removed) is its single breaking change. Install size is 29% smaller than 9 (which was itself about 50% smaller than 8), and the dist code is no longer minified. It needs a Node that can `require()` ESM: 20.16+, 22.19+ or 24+ — [Storybook 10 blog](https://storybook.js.org/blog/storybook-10/)
- **Config files:** the ESM-only pre-announcement says the Storybook config and story files must be valid ESM — [Storybook is going ESM-only](https://storybook.js.org/blog/storybook-is-going-esm-only/) (summarised via search result)
- **10.0 also shipped** module automocking (`sb.mock`, built with the Vitest team, works on the Vite and Webpack builders and in static builds) and moved CSF Factories from Experimental to Preview. It added Vitest 4 support — [Storybook 10 blog](https://storybook.js.org/blog/storybook-10/)
- **10.3:** `storybook@10.3.0` was published 18 Mar 2026 (npm registry); the blog post is dated 6 Apr 2026. It lists Vite 8, Next.js 16.2 and ESLint 10 support, plus Storybook MCP for React, but gives no Vite 8 caveats — [Storybook 10.3 blog](https://storybook.js.org/blog/storybook-10-3/)
- **Vite 8 itself:** stable 12 Mar 2026, with Rolldown as its single bundler. Storybook was among the teams that tested rolldown-vite early. Vite recommends a two-step move (rolldown-vite on Vite 7 first, then Vite 8) for large projects — [Vite 8 announcement](https://vite.dev/blog/announcing-vite8) (via search summary)
- **Later 10.x minors:**
  - 10.4 (blog 18 May 2026): AI-agent setup, sidebar filters for New/Modified/Related stories, quick share to Chromatic, TanStack React support — [Storybook 10.4 blog](https://storybook.js.org/blog/storybook-10-4/)
  - 10.5 (Jul 2026): "Foundational changes for new AI workflows", Angular-Vite in preview — [Storybook 10.5 release](https://storybook.js.org/releases/10.5)
  - 10.6 (Sep 2026): skills architecture for agents; the release page says no breaking changes — [Storybook 10.6 release](https://storybook.js.org/releases/10.6)
- **Current versions (npm registry, 24 Nov 2026):**
  - `storybook` latest is 10.6.8, published 20 Nov 2026, and the `next` tag is 11.0.0-beta.5, published 23 Nov 2026
  - `@storybook/react-vite@10.6.8` peers: `vite ^5 || ^6 || ^7 || ^8`, `react`/`react-dom ^16.8–^19`, `typescript >= 4.9.x`
  - `@storybook/addon-vitest@10.6.8` peers: `vitest ^4 || ^5` and `@vitest/browser-playwright ^4 || ^5` — [npm registry](https://registry.npmjs.org/@storybook%2Freact-vite)
- **Install footprint, core `storybook` package only (registry `dist.unpackedSize`):** 9.1.21 is 36.7 MB, 10.0.0 is 22.9 MB, 10.3.0 is 20.5 MB, 10.6.8 is 22.3 MB (17 direct dependencies), and 11.0.0-beta.5 is 16.0 MB (5 direct dependencies). This is not the full `node_modules` delta, which also includes the framework, addons, docgen and Playwright for Vitest — [npm registry](https://registry.npmjs.org/storybook)
- **Open Vite 8 bug #36228 (opened 8 Sep 2026):** in `storybook dev` with Vite 8, `storybook_internal_preview_runtime.js` is served at 1.3 MB with an inline sourcemap (3.4M characters). The same file is 383 kB on Vite 7. A maintainer comment (6 Oct 2026) puts the root cause in Vite 8: Rolldown's dep optimizer stops writing the `sourceMappingURL` comment, so the dev server inlines every optimized dep's map. The upstream fix is `vitejs/vite#23561`, and the issue stays open until that is released — [storybookjs/storybook#36228](https://github.com/storybookjs/storybook/issues/36228)
- **Open feature request #37495 (17 Nov 2026):** with SB 10.6.2, Vite 8.3.3 and React 19.3.0, a static build warns about a 1,119 KiB (315 KiB gzip) `iframe-*.js` preview-runtime chunk. Rolldown `codeSplitting.groups` did not remove the warning. The reporter says it is not a functional bug — [storybookjs/storybook#37495](https://github.com/storybookjs/storybook/issues/37495)
- **Dev/build asymmetry under Vite 8 (#36005, 21 Aug 2026):** dev does not resolve tsconfig `compilerOptions.paths` (Vite's `resolve.tsconfigPaths` defaults to false), while build does, because Rolldown's native resolver auto-detects tsconfig. A build can be green while dev fails on aliases. The issue was auto-closed for lacking a repro link, not fixed — [storybookjs/storybook#36005](https://github.com/storybookjs/storybook/issues/36005)
- **Earlier regression, now resolved (#34320):** 10.3.0's `vite-inject-mocker-runtime` plugin deadlocked dev on Vite 7 for one reporter. The plugin is added whenever `.storybook/preview.ts` exists, even without `sb.mock`. Maintainers could not reproduce it, and the issue was closed 9 Apr 2026 — [storybookjs/storybook#34320](https://github.com/storybookjs/storybook/issues/34320)
- **Storybook 11 (from MIGRATION.md on `next`, read 24 Nov 2026):**
  - Requirements: Node 22.12+, TypeScript 5.9+, Vite 6.3+, Vitest addon on Vitest 4+
  - `typescript` becomes a required peer, and the notes warn that TypeScript 7.0 cannot be used by docgen
  - `@storybook/test-runner` is removed (use the Vitest addon), and `storybook/test` moves to `@vitest/spy`/`@vitest/expect` 5
  - Yarn PnP support is removed
  - `storybook dev` sends `frame-ancestors` CSP, so only localhost can embed the dev server
  - `storybook dev` no longer opens a browser
  - Toolbar `globalTypes` entries lose `defaultValue` and the index signature
  - CSF Next changes `fn()` arg typing (wrap in `mocked()`)
  - The 10→11 section is about 2,188 lines with 87 `###` headings, against about 150 lines and 1 heading for 9→10 and about 739 lines for 8→9 — [MIGRATION.md (next)](https://github.com/storybookjs/storybook/blob/next/MIGRATION.md)
- **React 19 in the wild:** the #37495 reporter runs SB 10.6.2 with React 19.3.0 and has no React-specific complaint — [storybookjs/storybook#37495](https://github.com/storybookjs/storybook/issues/37495)
- **Cold start, older data:** a team with 1,900+ stories reported the Vite dev server up in 10–20 s (against about 1 min on Webpack), with time-to-interaction "still not great" — [Migrating 1900+ Stories Storybook to Vite (Medium, fundamental-library)](https://medium.com/fundamental-library/migrating-1900-stories-storybook-to-vite-d0daf9a19281) (older, likely 2022–23, possibly stale). Storybook's own post noted that Vite serves modules unbundled, so browser-side load can lag server start — [Storybook performance: Webpack to Vite](https://storybook.js.org/blog/storybook-performance-from-webpack-to-vite/) (older, possibly stale)

### Inferences
- The stack fits SB 10.6.8 on every declared peer: React 19, Vite 8, Node 24 (above both the 10.x floor and the 11 floor of 22.12), and TS 6 (above 11's 5.9 floor). TS 6 is also the version the 11 notes recommend adding.
- Expect a slower first dev page load on Vite 8 until `vitejs/vite#23561` ships, because every optimized dep gets an inline base64 sourcemap. This is a dev-only speed and memory issue, not a correctness one.
- Timing choice. Starting on 10.6 now means facing an 87-item 11.0 migration within months. Most of it targets addon authors, Angular/Svelte, the test-runner and Webpack, but CSF Next typing and toolbar globalTypes changes touch ordinary projects. Starting on 11.0 stable, once released, may be cheaper than 10 followed by an upgrade. Starting on a beta is risky for a solo developer.
- If the project ever imports via tsconfig `paths` aliases, #36005 is a trap. Check `vite.config.ts` aliases first.

### Gaps
- I found no measured `storybook dev` cold-start time or full `node_modules` footprint for SB 10 on Vite 8 from 2025–26. Measuring both on this repo is the only reliable figure (out of scope: no installs).
- No release date for Storybook 11.0 stable was found. The 10.0 blog said "next Spring" (spring 2026), and that date has slipped.
- The upstream release status of `vitejs/vite#23561` was not checked.

## 2. Global CSS and tokens, light/dark via `light-dark()`, `data-color-theme` themes, i18next locale switching, and "modes"

### Takeaway
Import the global CSS in `.storybook/preview.ts` and hand-roll small decorators: one global for colour scheme (set `color-scheme` on `<html>`, which is what `light-dark()` follows), one for `data-color-theme`, and one for locale (`i18n.changeLanguage` plus `lang` and `dir`). The official `@storybook/addon-themes` manages a single theme axis, and the i18next addon gains little over 15 lines of decorator. "Modes" is a Chromatic concept layered on Storybook globals, not a Storybook-native runner feature.

### Cited Findings
- **`@storybook/addon-themes` (docs for 10.6)** offers `withThemeByClassName`, `withThemeByDataAttribute` (options `themes`, `defaultTheme`, `attributeName`) and `withThemeFromJSXProvider`. The docs say nothing about combining several of them or about `color-scheme`/`prefers-color-scheme` — [Storybook docs: Themes](https://storybook.js.org/docs/essentials/themes). Latest version is 10.6.8 (20 Nov 2026), peer `storybook ^10.6.8` — [npm registry](https://registry.npmjs.org/@storybook%2Faddon-themes)
- **The theme addon owns `globals.theme`.** A community theme addon warns against enabling another addon that also owns `globals.theme`, naming `@storybook/addon-themes`. Decorators run global, then component, then story, so two global theme decorators both run and the later one can override the earlier — [storybook-addon-themes README](https://unpkg.com/storybook-addon-themes@6.1.0/README.md) (older package)
- **Globals and toolbars:** `globalTypes` (with `toolbar: {title, icon, items, dynamicTitle}`) and `initialGlobals` live in `preview.*`. Decorators read `context.globals`. A per-story or per-component `globals` annotation overrides the toolbar and disables that toolbar menu for those stories. The docs include a `locale` global example — [Storybook docs: Toolbars & globals](https://storybook.js.org/docs/essentials/toolbars-and-globals)
- **`light-dark()` switching:** Mozilla's own Storybook work proposed a `color-scheme` switcher precisely because "Now that we use light-dark() in our CSS we can change the theme using the color-scheme" — [Mozilla bug 1858998](https://bugzilla.mozilla.org/show_bug.cgi?id=1858998). A community addon, "Preview Scheme Toggler" (SB 9/10), toggles light/dark/auto with an `enableAutoMode` parameter — [Storybook addon catalogue](https://storybook.js.org/addons/storybook-preview-scheme-toggler)
- **i18next addon:** `storybook-react-i18next` latest is 10.1.5 (published 20 Nov 2026). Peers: `storybook ^9 || ^10`, `i18next ^22–^27`, `react-i18next ^12–^18`, and also `i18next-http-backend` and `i18next-browser-languagedetector`. A `next` tag 11.0.0-next.1 exists for SB 11 — [npm registry](https://registry.npmjs.org/storybook-react-i18next); addon page: [storybook-react-i18next](https://storybook.js.org/addons/storybook-react-i18next)
- **Chromatic modes:** named combinations of globals (theme, viewport, locale…) defined in `.storybook/modes.ts` and applied with `parameters.chromatic.modes` at project, component or story level. Modes stack across levels and can be switched off with `disable: true`. Each mode is a separate snapshot with its own baseline (2 stories × 2 modes = 4 tests). Any global-driven addon or custom decorator works with them — [Chromatic docs: Modes](https://www.chromatic.com/docs/modes/)
- **Storybook 11 typing change:** toolbar `globalTypes` entries no longer accept extra keys or `defaultValue`, so an unknown key becomes a type error (the migration example is a `locale` global) — [MIGRATION.md (next)](https://github.com/storybookjs/storybook/blob/next/MIGRATION.md)
- **Agent setup's choices:** the 10.4 agent built a shared `preview.tsx` with a provider tree, an MSW loader, MockDate and a portal-root decorator, then wrote one story that checks the theme's styles loaded. This suggests style loading in preview is a known failure point — [Storybook 10.4 blog](https://storybook.js.org/blog/storybook-10-4/)

### Inferences
- **Recommended shape for this app** (not from a single source):
  - `preview.ts` imports the same CSS entry the SPA uses, so the tokens, `light-dark()` rules and `[data-color-theme]` blocks all come along
  - `globalTypes` declares `scheme` (light/dark/system) and `colorTheme` (the app's theme list)
  - One decorator sets `document.documentElement.style.colorScheme` and `dataset.colorTheme` from `context.globals`. Use whatever the SPA's `bootPalette.ts`/`platform.ts` actually sets, ideally by calling the same function, so the story and app paths cannot drift
- **Why hand-roll the theme axes:** `addon-themes` holds one `theme` global, and this app has two independent axes. Two `withThemeByDataAttribute` decorators would compete over the same global. Two hand-rolled globals avoid that.
- **Locale with a hand-rolled decorator:** add a `locale` global listing the 21 locales, and a decorator that calls `i18n.changeLanguage(locale)` and sets `<html lang>` and `dir`. That is a few lines and adds no addon to track across a Storybook major. The addon also pulls peers for http-backend and the language detector, which the app may not use.
- **Per-story locale:** story-level `globals: { locale: 'de' }` gives "long locale" and RTL stories without the toolbar.
- **The browser is not WKWebView.** The Storybook preview runs in whatever browser opens it (Chrome by default). For WebKit fidelity, the Vitest addon's Playwright provider can run WebKit, but that is Playwright WebKit, not WKWebView. This is an inference; confirm with the visual-regression research.
- **"Modes" without Chromatic** means per-story `globals`, or a loop that generates stories per locale/theme. Nothing in Storybook core multiplies stories across globals automatically.

### Gaps
- No source covers how `storybook-react-i18next` handles async resource loading for 21 locales, or whether it works with bundled (non-http) resources.
- No source confirms whether a `color-scheme` set on `<html>` in the preview iframe interacts with the Storybook `backgrounds` addon (which paints its own background). This is worth one manual check.

## 3. Mocking module-level stores and a directly imported fetch module

### Takeaway
For components that import a store or `utils/api.ts` directly, the least invasive option is `sb.mock()` in `preview.ts`: zero changes to app code. Storybook resolves it at build time and replaces exports with Vitest mocks that stories configure in `beforeEach`. It has real sharp edges: global registration only, no factory, no unmock, relative paths that must include the extension, enum exports, and an open spy-mode bug. MSW (the addon is v3, MSW 2) is the zero-code-change alternative at the network layer. Subpath `#` imports are the most explicit route, but would mean rewriting about 41 import sites here. Stores that already expose setters can usually be seeded directly in `beforeEach` with no mocking at all.

### Cited Findings
- **`sb.mock` modes:**
  - Registered only in `.storybook/preview.*`, never in story files
  - `sb.mock(import('../lib/session.ts'), { spy: true })` keeps the real code and records calls
  - Without `spy`, exports become Vitest mock functions; the docs warn that "the module is still evaluated"
  - A `__mocks__` file beside the module overrides automocking, and must be JS ESM, not TypeScript
  - Stories control behaviour with `mocked(fn).mockReturnValue(...)` in `beforeEach` or `play`
  - [Storybook docs: Mocking modules](https://storybook.js.org/docs/writing-stories/mocking-data-and-modules/mocking-modules)
- **`sb.mock` limits:** no `sb.unmock()`, and no factory function, because "all mocking decisions are resolved at build time". Local paths must be relative to the preview file, cannot use aliases or subpath imports, and must include the file extension. Subpath imports need TS `moduleResolution` of `Bundler`, `NodeNext` or `Node16` — [Storybook docs: Mocking modules](https://storybook.js.org/docs/writing-stories/mocking-data-and-modules/mocking-modules)
- **Subpath imports alternative:** a `package.json` `imports` map sends `#api` to a `storybook` condition (mock file) or a `default` condition (real file). Mock files wrap the originals in `fn(...).mockName(...)`. Builder aliases via `viteFinal` are a third option — [Storybook docs: Mocking modules](https://storybook.js.org/docs/writing-stories/mocking-data-and-modules/mocking-modules)
- **Open bug #37040 (27 Oct 2026):** `sb.mock(..., { spy: true })` empties array properties and breaks `new` on exported classes in `storybook dev`/`build`, but passes under `@storybook/addon-vitest`, "so CI is green while dev and the deployed Storybook are broken". The cause: dev and build bundle `@vitest/mocker`/`@vitest/spy` 3.2.4 while the Vitest addon uses Vitest 4 — [storybookjs/storybook#37040](https://github.com/storybookjs/storybook/issues/37040). SB 11 moves `storybook/test` to `@vitest/spy` 5, which should remove the version split — [MIGRATION.md (next)](https://github.com/storybookjs/storybook/blob/next/MIGRATION.md)
- **Open bug #32336 (27 Aug 2025):** `sb.mock` on a file that exports a TypeScript `enum` fails with "does not provide an export named 'TestEnum'" — [storybookjs/storybook#32336](https://github.com/storybookjs/storybook/issues/32336)
- **Other `sb.mock` history:**
  - Mocking broke for a Storybook deployed under a subpath route (#32631, closed)
  - "Cannot convert undefined or null to object" (#32599, closed)
  - `clearAllMocks` did not work in `beforeEach` (#34075, closed Mar 2026)
  - Mocking TanStack Router `Link` is still open (#32370)
  - [GitHub issue search, storybookjs/storybook](https://github.com/storybookjs/storybook/issues?q=sb.mock)
- **msw-storybook-addon status:**
  - v3.0.0 published 24 Jul 2026, latest 3.0.3 published 15 Sep 2026
  - Peers: `msw >=2`, `storybook ^9 || ^10 || ^11.0.0-0`
  - [npm registry](https://registry.npmjs.org/msw-storybook-addon)
  - The CSF 3 `mswLoader` and `parameters.msw` path is deprecated. Under CSF Next you use `addonMsw()` and set per-story handlers with `beforeEach({ msw }) => msw.use(...)`
  - Handlers passed to `setupWorker()` are initial handlers and are not reset between stories
  - Setup needs `npx msw init ./public`
  - [msw-storybook-addon README](https://github.com/mswjs/msw-storybook-addon); [unpkg README 3.0.0](https://app.unpkg.com/msw-storybook-addon@3.0.0/files/README.md)
- **Official connected-components guidance:** Storybook lists three mocking layers (imports, network, providers). Its preferred alternative to mocking is container components injected through React context, so stories swap in presentational versions. It admits that pure-presentational restructuring "may be difficult" for an existing app, and that props must be drilled down — [Storybook docs: Build pages with Storybook](https://storybook.js.org/docs/writing-stories/build-pages-with-storybook)
- **React Router:**
  - `storybook-addon-remix-react-router@7.0.0` (28 Jul 2026), peers `react-router ^7.0.2 || ^8`, `storybook ^10`, `react >=18`
  - The older `storybook-addon-react-router-v6@3.0.0` (12 Mar 2026) peers `storybook ^9` only
  - [npm registry](https://registry.npmjs.org/storybook-addon-remix-react-router)
- **The 10.4 AI setup** generates MSW mocks, a provider tree (router, store, theme) and stories for up to 10 components. Storybook gives no success rate for it — [Storybook 10.4 blog](https://storybook.js.org/blog/storybook-10-4/)
- **Experience reports on mocked inputs:** "Any input data the component takes has to be mocked in its story file," and a component API change forces story edits. The upkeep is not worth it if no designer or client views the stories (Atomic Object, Apr 2024) — [Reconsider Using Storybook](https://spin.atomicobject.com/using-storybook-reconsider/) (2024, older than preferred)

### Inferences
- **Least invasive for this codebase:**
  1. `sb.mock(import('../src/utils/api.ts'))`, fully automocked, in `preview.ts`
     - All 77 exports become `undefined`-returning mocks
     - Each story then sets only what it needs: `mocked(getThing).mockResolvedValue(fixture)`
     - No app code changes, and loading and error states are trivial: `mockReturnValue(new Promise(() => {}))` and `mockRejectedValue(...)`
     - Cost: fixtures must match real response shapes by hand. A typed `mocked()` helps, because TS flags fixture drift against the real return types.
  2. Avoid `{ spy: true }` on `api.ts` if it exports classes (such as an error class) or arrays, until #37040 is fixed. Also check that `api.ts` exports no TS `enum` (#32336).
  3. Don't automock the stores themselves. Stores built on `useSyncExternalStore` are plain modules with module-level state, so a fully automocked store's `subscribe`/`getSnapshot` would return `undefined` and the component would crash or render nothing. If the stores expose actions or setters (or a `reset`), seed state in `beforeEach` by calling them directly and reset afterwards.
- **Store state leaks between stories.** Module-level stores are singletons in the preview iframe, so state from one story carries into the next unless `beforeEach` resets it. This is the main source of order-dependent story flakiness for this architecture. A per-store `__resetForTests()` (if not already present) is a small, worthwhile app-side change.
- **A fully automocked module is still evaluated**, so any import-time side effect in `api.ts` (reading a bearer token from the DOM, building a base URL) still runs.
- **MSW against the directly imported API module.** It keeps the real `api.ts` code path, including URL building, auth headers and JSON parsing, so it catches more drift. Handlers need the real path templates and the bearer-token behaviour, and the service worker file has to be served from `staticDirs`. It costs more per story than `mocked()` but gives higher fidelity. It is a good fit if fixtures can be reused from existing API tests or the export JSON.
- **Subpath `#api` imports would touch about 41 import sites**, and would also change the vitest/tsconfig resolution for the app itself. That is not worth it when `sb.mock` exists.
- **The cost gradient is real:** leaf presentational components cost about args only, while connected components cost fixtures, store seeding, a router decorator and an i18n decorator per state. Storybook's own docs concede that restructuring an existing app into presentational/container form is the clean fix and is hard.
- **React Router 7 data router:** either the community addon (v7.0.0, supports RR 7/8 and SB 10) or a hand-rolled decorator with `createMemoryRouter`/`RouterProvider` per story. The hand-rolled version has no addon to track across Storybook majors.

### Gaps
- I found no dated 2025–26 engineering write-up that quantifies hours per connected story, or that compares `sb.mock` with MSW at scale. Evidence for "connected components are hard" is the official docs plus older experience posts.
- I couldn't confirm whether `sb.mock` handles a module that is imported both by stores and by components (shared singleton mocking across importers). The build-time design implies yes, but no doc states it explicitly.
- No source tested `sb.mock` against a `useSyncExternalStore` store specifically. The issue search for `useSyncExternalStore` returned nothing relevant.

## 4. Story-writing patterns that keep stories from rotting

### Takeaway
Use CSF Next (factories) only if you start on SB 11 or accept the typing churn in the 11 migration. Otherwise use CSF3 with `satisfies Meta<typeof X>`. Co-locate stories, keep one story per state, and run stories as tests (Vitest addon), so a story that stops rendering fails CI instead of rotting quietly.

### Cited Findings
- **CSF Factories status:** Preview since 10.0, extended from React-only to Vue, Angular and Web Components in 10.x. They are planned to be the default in 11, and upgrading is optional (codemod `npx storybook automigrate csf-factories`) — [Storybook 10 blog](https://storybook.js.org/blog/storybook-10/); [Storybook 10.3 blog](https://storybook.js.org/blog/storybook-10-3/); [CSF Next docs](https://storybook.js.org/docs/api/csf/csf-next)
- **SB 11 CSF Next changes:** meta args no longer need `as const`; `fn()` args are typed as the component declares them, so `mocked()` is needed for the mock API; every key in meta args must be an arg — [MIGRATION.md (next)](https://github.com/storybookjs/storybook/blob/next/MIGRATION.md)
- **MSW addon under CSF Next:** `parameters.msw` is unsupported there; use `beforeEach` — [msw-storybook-addon README](https://github.com/mswjs/msw-storybook-addon)
- **Stories as tests:** SB 11 removes `@storybook/test-runner` and points to `@storybook/addon-vitest`, which requires a Vite framework — [MIGRATION.md (next)](https://github.com/storybookjs/storybook/blob/next/MIGRATION.md). The 10.4 agent setup verified its 37 generated stories by running them as passing tests — [Storybook 10.4 blog](https://storybook.js.org/blog/storybook-10-4/)
- **Tag filtering:** sidebar exclusion filters and `defaultFilterSelection` arrived in 10.0, useful for hiding `experimental` stories — [Storybook 10 blog](https://storybook.js.org/blog/storybook-10/). The 10.4 change-detection filters show New/Modified/Related stories for review — [Storybook 10.4 blog](https://storybook.js.org/blog/storybook-10-4/)
- **Per-story globals** pin locale or theme for "long locale", RTL and dark-mode stories — [Storybook docs: Toolbars & globals](https://storybook.js.org/docs/essentials/toolbars-and-globals)
- **Args composition:** screen stories reuse child stories' args — [Storybook docs: Build pages](https://storybook.js.org/docs/writing-stories/build-pages-with-storybook)

### Inferences
- **Anti-rot checklist (synthesis):**
  - Co-locate `X.stories.tsx` beside `X.tsx`
  - Type fixtures from the real API return types, so `tsc` (strict, already a gate) catches drift
  - Add one named story per state: `Empty`, `Loading` (never-resolving promise), `Error` (rejected mock), `LongText`, `LongLocale` (`globals: { locale: 'de' }` or `fi`), `RTL` (if any RTL locale ships), `Dark` (`globals: { scheme: 'dark' }`), plus one per colour theme only where the component uses theme tokens
  - Run all stories as smoke tests through the Vitest addon in CI
  - Reset module stores in a global `beforeEach`
- **Keep the number of addons small:** core, docs only if wanted, and the Vitest addon. Hand-rolled decorators replace the theme, i18n and router addons. Every community addon is a peer-range compatibility check at each Storybook major, and the i18next and router addons already need different releases for SB 9, 10 and 11.

### Gaps
- No 2025–26 data was found on how often teams adopt CSF Next in practice, or on how reliable the factories codemod is.

## 5. Known failure modes: maintenance burden, drift, slow builds, addon churn, upgrade pain 8→9→10(→11)

### Takeaway
The recurring complaints are the same each year: story upkeep on every API change, mocked inputs, stories going unviewed and unrun, slow builds, and addon/major-version churn. Storybook has cut weight hard (−50% in 9, −29% in 10). The size of each major's migration notes, however, shows the churn continues, and 11 is the largest yet.

### Cited Findings
- **Maintenance complaints:**
  - Atomic Object (Apr 2024): every component needs a story file, inputs must be mocked, API changes force story edits, and it is not worth it unless people actually view the stories
  - The alternatives proposed: a temporary route in the app, or a homemade Vite showcase that has "far fewer features but requires no maintenance" (reader comment)
  - [Reconsider Using Storybook](https://spin.atomicobject.com/using-storybook-reconsider/)
- **Hacker News thread (2021, stale):**
  - "a nightmare to maintain and train devs on"
  - rollout owners lost interest after a couple of months
  - one team kept Storybook only for sunk cost
  - 20–30 s webpack compiles
  - [HN](https://news.ycombinator.com/item?id=28494559)
- **GitLab UI discussion:** a contributor argued that if stories carry a maintenance cost they quickly become a net negative — [gitlab-ui MR](https://gitlab.com/gitlab-org/gitlab-ui/-/merge_requests/2345) (older, via search summary)
- **8→9 (Storybook 9, Jun 2025):** essentials addons (viewport, controls, interactions, actions) moved into core; `@storybook/blocks` consolidated into addon-docs; storysource and mdx-gfm addons removed; Svelte 5+, Angular 18+ and Next 14+ required. The section is about 739 lines — [MIGRATION.md (next)](https://github.com/storybookjs/storybook/blob/next/MIGRATION.md). The release claimed a 48% lighter bundle and a dependency graph about 10% the size — [Storybook 9.0 release](https://storybook.js.org/releases/9.0); [Storybook bloat fixed](https://storybook.js.org/blog/storybook-bloat-fixed/)
- **9→10:** one breaking change (ESM-only); the section is about 150 lines — [Storybook 10 blog](https://storybook.js.org/blog/storybook-10/); [MIGRATION.md (next)](https://github.com/storybookjs/storybook/blob/next/MIGRATION.md)
- **Within 10.x, minors still carry migration notes.** 10.5→10.6 lists 7 items (for example `@storybook/csf-plugin` removed, Playwright CT integration removed, MCP tool renames) even though the 10.6 release page says "no breaking changes" — [MIGRATION.md (next)](https://github.com/storybookjs/storybook/blob/next/MIGRATION.md); [Storybook 10.6 release](https://storybook.js.org/releases/10.6)
- **Build regressions inside a minor:** `build-storybook` was about 15–20× slower after 10.4.6 → 10.5.x with `vue-component-meta` docgen (#35556, Vue-specific, closed) — [storybookjs/storybook#35556](https://github.com/storybookjs/storybook/issues/35556)
- **Addon churn across majors** shows in peer ranges (npm registry, 24 Nov 2026):
  - `storybook-react-i18next` 10.1.5 supports SB 9/10, and SB 11 needs its `next` 11.0.0-next.1
  - `storybook-addon-react-router-v6` supports only SB 9, and its successor `storybook-addon-remix-react-router` 7.x needs SB 10
  - In SB 11 QA, `@storybook/addon-designs` 12.0.0, installed by the upgrade, crashed the dev server (#37311, closed)
  - [npm registry](https://registry.npmjs.org/storybook-react-i18next); [storybookjs/storybook#37311](https://github.com/storybookjs/storybook/issues/37311)
- **Silent dev/build/test divergence:** spy mocks behave differently in dev/build than under Vitest (#37040), and tsconfig paths resolve in build but not in dev on Vite 8 (#36005) — [#37040](https://github.com/storybookjs/storybook/issues/37040); [#36005](https://github.com/storybookjs/storybook/issues/36005)
- **Maintainer capacity:** historically volunteers, and Storybook has since announced full-time maintenance — [Storybook maintainers AMA (DEV)](https://dev.to/norbertdelangen/were-the-core-maintainers-of-storybook-ask-us-anything-41ee) (date not confirmed, likely older)

### Inferences
- For a solo developer the dominant cost is not writing stories. It is the upkeep tax: keeping connected-story fixtures in step with `api.ts`, and one major upgrade a year (8→9 Jun 2025, 9→10 Oct 2025, 11 now in beta), each with community-addon catch-up. Hand-rolled decorators and a minimal addon set reduce the second cost the most.
- **Stories rot quietly unless they are executed.** Running them through the Vitest addon in CI turns "story drifted from the app" into a red build. That is the same principle as this repo's own gate policy ("a gate that can't fail isn't a gate").
- **A cheap middle path** for a solo product whose main surface is a WKWebView: Storybook only for leaf and presentational components plus a handful of key connected screens (via `sb.mock` on `api.ts` and store seeding), rather than blanket coverage.

### Gaps
- I found no 2025–2026 first-hand account of a team abandoning Storybook. The search results were dominated by 2021–2024 material, so the complaint set may be partly stale against SB 9/10's lighter footprint.
- No public data was found on how long the 8→9 or 9→10 upgrades took in real projects.
