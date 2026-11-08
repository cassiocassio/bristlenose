---
status: archived
archived: 2026-11-08
---

# Miro one-click sign-in (archived)

Archived 8 Nov 2026, kept in case it is ever useful. This was the plan for a
one-click "Connect to Miro" with OAuth, written while Send to Miro was being
built (`docs/design-miro-bridge.md`). It is not coming back in this form:

- Miro refuses a sign-in without the app's client secret (PKCE with no secret
  gave `401 tokenNotProvided`, measured 8 Nov 2026 in both request shapes).
- Holding the secret needs a relay server, which the owner ruled out ("no
  servers"); the relay was costed and parked, and is in the backlog.
- The end-user route is now the in-Miro app (`docs/design-miro-in-board-app.md`);
  the developer-token Send to Miro stays for keen beta testers only.

The full account, with sources: `docs/research/miro-integration-2026-11.md`.
The OAuth code it describes is still in `bristlenose/server/routes/miro.py`,
written and dormant (`miro_client_id` is empty).

The sections below are moved here verbatim from `design-miro-bridge.md`.

## The 21 Oct 2026 note on Miro's OAuth

> **Trued 21 Oct 2026 (OAuth facts).** The sign-in plan below was written before anyone read Miro's OAuth reference closely. Miro's reference, read on 19 and 20 Oct, says:
>
> - **No PKCE, a confidential secret.** The [authorization request](https://developers.miro.com/reference/create-authorization-request-link) takes no `code_challenge`, and the [token exchange](https://developers.miro.com/reference/exchange-authorization-code-with-access-token) requires a `client_secret`, which "must be kept confidential", with no `code_verifier`.
> - **Redirect URIs match exactly**, trailing slash included, and [Miro's OAuth troubleshooting page](https://developers.miro.com/docs/troubleshooting-oauth20) documents no wildcard for a localhost port.
> - **Token expiry is fixed when the app is created** and can't be changed afterwards ([expiring access tokens](https://developers.miro.com/reference/authorization-flow-for-expiring-access-tokens)). Our app has it off (owner, 20 Oct), so a token lasts until the user uninstalls the app, and there is no refresh token.
> - **"Share app" gives an install URL** to users outside the developer team without a Marketplace listing, and Miro documents no review for it ([sharing an app outside a developer team](https://developers.miro.com/docs/share-an-app-outside-of-a-developer-team)).
> - **Untested:** whether Miro quietly accepts PKCE without a secret. `experiments/miro-pkce-probe/probe.py` answers that with one sign-in.
> - **Pending, the owner's decision:** PKCE, if the probe passes, or a small broker on bristlenose.app that holds the secret. Neither is chosen.
>
> The sections below that assume PKCE and refresh tokens are marked where they say so, not rewritten.

## Status of the dormant code (as of 18 Aug 2026)

**Phase 2 is written but dormant, which is not the same as unbuilt** — `routes/miro.py` carries
`auth-url`, the PKCE exchange and the `/miro/callback` handler in full, and none of it is
reachable: `miro_client_id` defaults to `""`, no SPA component calls `auth-url`, and the Swift
host never sets `MIRO_CLIENT_ID`. Worth stating plainly because dormant-but-present code gets
neither the testing of a shipped path nor the scrutiny of a proposed one. It cost exactly that on
18 Aug 2026: the callback reported "Connected to Miro ✓" without ever reading the token back, and
had no in-session fallback, so a credential-store write that silently no-opped (the ordinary
sandbox case) left the token in **no** store at all while the browser tab said it had worked.
Fixed in `d3c5f572`; nobody had hit it because nobody can reach the path.

## Cross-app flow & setup (the adoption surface)

The make-or-break is the journey across two apps and getting past first-run
setup, not sticky detail. Design goals: **cross the app boundary as few times as
possible; never make someone do setup twice.**

- **The menu encodes state.** Export popover shows `Connect to Miro…` when
  disconnected (routes to consent) and `Send to Miro board…` once connected
  (jumps to configure).
- **First run** crosses the boundary twice (consent out + auto-return). **Every
  run after** crosses once (the final `Open in Miro`). Consent never reappears —
  token + refresh live in the keychain _(refresh: see the 21 Oct note)_.
- **No dead-ends:** the browser handoff sets the expectation ("come back here"),
  the return is automatic via localhost callback, the finish gives one obvious
  `Open in Miro` button.
- **Consent + privacy** stated at the moment of action: quote count shown, data
  leaves the machine, hidden quotes excluded. Miro is a sub-processor — document
  in `SECURITY.md`.

See `docs/mockups/miro-flow.html` and `miro-setup-help.html`.

---

## OAuth flow (M2 detail)

> **Marked 21 Oct 2026.** These steps assume PKCE and refresh tokens. Miro documents a
> confidential client secret instead, and our app's tokens don't expire. Step 4's `{port}`
> also collides with Miro's exact-match redirect URIs, so either way the sign-in needs a fixed
> localhost port or a redirect that lands on a broker. The decision is pending; see the note at
> the top. The steps are kept as written.

1. Frontend gets the authorize URL (`GET /api/miro/auth-url`).
2. System browser opens Miro's consent page.
3. User clicks **Allow**.
4. Miro redirects to `http://localhost:{port}/api/miro/callback`.
5. Callback exchanges the code for tokens (PKCE — no client secret).
6. Access + refresh tokens stored in keychain. _(refresh: see the 21 Oct note)_
7. Report shows Connected; menu flips to `Send to Miro board…`.

Security: random-UUID `state` validated on callback (CSRF); auto-refresh before
calls when token age > 50 min _(moot with non-expiring tokens)_; disconnect deletes both tokens; client ID is
build-time `.env`, not user-facing. Paste-token remains a fallback for orgs that
block third-party app authorisation.


## Mockups of the old flow

Moved to `docs/archive/mockups/`: `miro-flow.html` (flow and setup),
`miro-setup-help.html` (the setup help page), `miro-native-flow.html` (the SPA
against the proposed macOS-native flow, screen by screen).
