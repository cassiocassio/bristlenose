# Miro integration: what we learned, 8 November 2026

One evening's work settled how Bristlenose gets a research board into Miro for
researchers who are not developers. This is the record, so nobody does the
research again. Design of the result: `docs/design-miro-in-board-app.md`. The
REST route it replaces as the end-user path: `docs/design-miro-bridge.md`.
The abandoned one-click sign-in plan: `docs/archive/design-miro-oauth-one-click.md`.

## The outcome

| Route | What the researcher does | Server | Status |
|---|---|---|---|
| **In-Miro app** (Web SDK, static files) | Add the app to their team once by link; per board: copy or download the board file in Bristlenose, open the Bristlenose panel in Miro, paste | None | **Chosen.** Built and run on a real board 8 Nov 2026 |
| Developer token (REST, today's Send to Miro) | Create a Miro developer team and app, tick scopes, install, copy the token, paste into Bristlenose; then one click per board | None | **Kept for keen beta testers only, labelled interim** |
| One-click sign-in via a relay (REST) | Click Connect, Allow; then one click per board | A sign-in relay holding the client secret | **Parked** (100days). Costed, then ruled out |
| One-click sign-in with PKCE, no secret | Click Connect, Allow | None | **Impossible**: Miro refuses it (measured) |
| Client secret inside the app | Click Connect, Allow | None | **Rejected**: anyone could extract the secret and pose as Bristlenose |

Owner rulings, 8 Nov 2026:

- **No servers.** "Bristlenose has no servers. I am 1000% happier not having to
  provide this." A relay is a last resort, not a default.
- **The token route is credible only in beta.** It "feels really odd": a
  researcher will think it wrong to "become a developer", and boards made
  through a developer team carry Miro's "Developer team" watermark, so they
  "can't really be shared to a stakeholder, or made into a presentation".
  Keen testers may still use it (it gets feedback on the sticky layout), and
  are told plainly that it is interim.
- **The in-Miro app, because company admins decide.** A researcher may
  install anything on a work Mac, but on a company Miro the question "does a
  third party hold access to our boards?" is very likely to be vetoed. A board
  plugin that acts only while the board is open, holding no token outside
  Miro, is something a client's IT can say yes to.
- **No Miro submission.** Nobody will find Bristlenose by browsing Miro's
  Marketplace, and nobody needs to: researchers already use Bristlenose, which
  hands them the install link.

## Measured (our own probes)

`experiments/miro-pkce-probe/probe.py`, app client ID `3458764676772092122`:

1. **PKCE with no client secret is refused.** The token exchange returned
   `HTTP 401`, `code: tokenNotProvided`, "No authorization data was found on the
   request", both with the fields in the query string (Miro's documented shape)
   and in a form-urlencoded body (the shape Miro staff gave as the working one).
   The authorize step itself worked: consent screen "Add & allow Bristlenose",
   one permission line "Read and modify boards users have access to", redirect
   back with a code.
2. **Redirects: plain HTTP only with the name `localhost`.** Miro refused
   `http://127.0.0.1:8765/callback` ("These urls are not valid") and accepted
   `http://localhost:8765/callback`. A probe on `localhost` must listen on both
   loopback addresses (the browser may resolve it to `::1`).
3. **Expiring tokens must stay off.** With them on, a token lasts about an hour
   and the refresh call needs the client secret, so without a server the user
   would sign in again hourly. The setting cannot be changed after the app is
   created; in April 2024 Miro staff called a bug where the checkbox reverts "a
   known bug".
4. **The Web SDK's loader hangs instead of failing.** `miro.js` is a 3 KB
   bootstrap that asks the Miro page for the real SDK's address and injects it.
   Outside Miro (or if it cannot connect) every `miro.board.*` call returns a
   promise that never settles. The app gives Miro's first answer 15 seconds and
   then says so.
5. **The in-Miro app works.** First run on a real board, 8 Nov 2026: "Board
   built: 10 quotes", frames, headers, attributed quotes, a split quote as a
   grouped pair. No sign-in, no token.

## Researched (two deep-research runs, 8 Nov 2026; 24 of 25 and all checked claims verified)

### Sign-in

- Miro's REST OAuth is documented only as a confidential-client flow with the
  secret at the token exchange; no doc, staff post or official sample shows a
  secretless public client. Miro's separate MCP authorization server accepts
  PKCE (S256) but still lists only client-secret auth at its token endpoint.
  [Authorization](https://developers.miro.com/reference/authorization-and-authentication) ·
  [Getting started with OAuth](https://developers.miro.com/docs/getting-started-with-oauth) ·
  [Official samples](https://github.com/miroapp/app-examples)
- The same misleading `401 tokenNotProvided` is what Miro returns for a
  wrongly encoded exchange; staff (Jan 2025) gave a form-urlencoded body as the
  fix. [Forum thread](https://community.miro.com/developer-platform-and-apis-57/exchange-authorization-code-with-access-token-19915)
- Developer tokens: non-expiring when created that way, bound to one user and
  one team, endorsed by staff for the developer's own use (Apr 2025, answered in
  7 minutes). [Thread](https://community.miro.com/developer-platform-and-apis-57/is-it-not-possible-to-generate-a-permanent-api-token-for-use-in-scripts-20981) ·
  [Cross-team tokens](https://community.miro.com/developer-platform-and-apis-57/provide-cross-team-tokens-276)
- Not found anywhere: anyone shipping the secret in a desktop app and how Miro
  reacted; any staff statement on plans for PKCE.

### The Web SDK route

- Documented with no backend token exchange: an in-board app reading a local
  file. [Mind map from CSV](https://developers.miro.com/docs/create-mind-map-from-csv)
- Rate limits are credits: 100,000 a minute and 1,000,000 an hour per user
  session, **shared across all of that user's apps**; a sticky, frame or text
  costs 50, an image 500. About 2,000 board items a minute. Plenty for a
  research board; two developers ran out re-laying out 1,000+ items, and Miro's
  answer to a batch-API request was "please vote".
  [Rate limiting](https://developers.miro.com/docs/websdk-reference-rate-limiting) ·
  [Batch idea](https://community.miro.com/ideas/web-sdk-batch-item-update-api-15216)
- SDK facts used in the build: `createStickyNote` takes the **centre**, and one
  of width or height (the height includes the sticky's shadow); content allows
  `p a strong b em i u s br`, under 6,000 characters; `fillColor` is one of
  Miro's named colours; `findEmptySpace` returns a centre rectangle;
  `icon:click` reaches only the headless app URL page; `openPanel` URLs are
  relative to the app URL. App icons: two square SVGs under 5,000 bytes, one
  monochrome (toolbar), one colour (apps panel).
  [Sticky note](https://developers.miro.com/docs/websdk-reference-sticky-note) ·
  [Board](https://developers.miro.com/docs/websdk-reference-board) ·
  [UI](https://developers.miro.com/docs/websdk-reference-ui) ·
  [Icons](https://developers.miro.com/docs/add-a-logo-to-your-app)

### Company Miro accounts

- Members can add any app by default. Business and Enterprise team admins can
  turn off "Allow non-admins to install apps"; only Enterprise company admins
  can restrict to an approved list. No controls documented on Free or Starter.
  [App management](https://help.miro.com/hc/en-us/articles/4404659741458)
- **Approval is by client ID**, so an unlisted app shared by install link is
  approved like a Marketplace one. On Enterprise a blocked member gets "Send
  request" with a reason, every company admin is emailed, and the member is told
  the decision. No turnaround time is given. A May 2026 thread shows the request
  flow can lose requests (Miro called it a bug).
  [App requests](https://help.miro.com/hc/en-us/articles/4592785249810)
- Install-link sharing is official and needs no review, but is still subject to
  the admin controls. [Updated submission process](https://developers.miro.com/changelog/updated-submission-process-for-the-miro-marketplace)
- **The Marketplace is not a near-term route.** Since 2026: apply through a
  partner form, more than 50 monthly active users in each of two consecutive
  months, installs in more than 10 organisations, then up to 8–12 weeks of
  review. A listing does not exempt an app from an admin's allowlist.
  [Submit your app](https://developers.miro.com/docs/submit-your-app)
- Unsettled: whether a Web SDK app and a REST app face exactly the same admin
  controls (only pre-authorisation is documented as Web SDK-only), and what a
  member sees when an install starts from a direct install link.

### Miro as a developer platform

Staff answer how-to and sign-in questions on the forum quickly and accurately
(7 minutes to a few days in the threads found); feature requests get "vote for
it" and nothing more. Evidence came almost entirely from Miro's docs and its
forum; nothing first-hand surfaced on GitHub, Reddit or Discord.

## The relay that was costed and parked

Kept so the next person does not cost it again. A stateless sign-in relay on a
Cloudflare Worker (about 50 lines): it adds the secret to the code-for-token
swap and passes the reply back, stores nothing, accepts only our client ID and
redirect. About £0 a year on the free tier (100,000 requests a day), about five
hours a year of account upkeep, half a day to build plus SECURITY.md and both
privacy pages. It would give true one-click (2 clicks per send, no paste) and
boards in the researcher's own team. Ruled out because it means running a server
that holds a secret and sees users' tokens, which a company admin is likely to
veto, and which contradicts "Bristlenose has no servers". Code interception on
the user's machine stays possible with any relay, because Miro has no PKCE.

## Hosting the in-Miro app

Tonight: static files at `https://bristlenose.app/miro/` (DreamHost), with a
folder `.htaccess` that lifts the site's no-framing headers for `miro.com` only.
Recommended before testers are invited: GitHub Pages at `miro.bristlenose.app`,
built by CI from this public repository, so the answer to "who can change the
code that runs in our boards?" is "this public source, built by this public
workflow". GitHub Pages cannot send custom headers; Cloudflare Pages can, if
that matters. Moving is one field, the app's App URL. Owner to rule.
