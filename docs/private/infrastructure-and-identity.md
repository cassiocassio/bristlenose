# Infrastructure & Identity Plan — 25 Mar 2026

## Domain Architecture

| Domain | Role | Registrar | Status |
|--------|------|-----------|--------|
| `cassiocassio.co.uk` | Parent entity / personal professional identity | DreamHost | Active |
| `bristlenose.app` | Product public face (landing page, docs, downloads) | TBD | Available — to register |
| `blog.bristlenose.app` | Substack (portable — CNAME) | N/A (subdomain) | After domain registration |

**bristlenose.com is taken.** Registered 18 Jan 2026 via Namecheap — suspiciously close to when the repo started getting GitHub activity. Likely automated domain squatting bot. Don't engage. Renewal is Jan 2027; squatter may let it lapse. Revisit then.

**`.research` is not a real TLD.** Original plan was `bristlenose.research` — doesn't exist. `bristlenose.app` is the primary product domain (Google-operated gTLD, HSTS-preloaded, trusted by enterprise email filters).

### DNS records to configure on bristlenose.app (day one)

```
; Anti-spoofing (publish even before sending any email)
bristlenose.app.          TXT   "v=spf1 -all"
_dmarc.bristlenose.app.   TXT   "v=DMARC1; p=reject; rua=mailto:dmarc-reports@cassiocassio.co.uk"

; Substack blog
blog.bristlenose.app.     CNAME target.substack-custom-domains.com.
```

When email hosting is configured (DreamHost), update SPF to include DreamHost's mail servers and add DKIM.

### DreamHost email setup

Host product email on DreamHost (same account as cassiocassio.co.uk). Use Apple Mail via IMAP. No Google Workspace needed.

### Registrar consolidation

Register `bristlenose.app` at DreamHost — one login, one bill, one DNS panel alongside cassiocassio.co.uk.

| Address | Purpose |
|---------|---------|
| `hello@bristlenose.app` | Public-facing (press, partnerships, App Store contact) |
| `support@bristlenose.app` | User support |
| `security@bristlenose.app` | Vulnerability reports (update SECURITY.md) |
| `no-reply@bristlenose.app` | Substack sends, transactional |

`martin@cassiocassio.co.uk` stays separate — personal/professional identity for freelancing.

---

## Apple Developer Account

### Phase 1: Individual enrollment (now)

- Enroll as individual ($99/year)
- **Bundle ID: `app.bristlenose.desktop`** — reverse-DNS of owned domain, product identity not parent company
- Sufficient for notarisation, .dmg distribution, and App Store submission
- Publisher name on App Store: "Martin Storey"

### Phase 2: Organisation enrollment (if/when Bristlenose succeeds)

Trigger: revenue justifies the overhead of running a Ltd.

1. Register Ltd at Companies House (£12 online, same day)
2. Request D-U-N-S number from Dun & Bradstreet (free, 1–2 weeks — Apple requires this globally, not just UK)
3. Enroll the Ltd as Apple Developer Organisation (£79/year)
4. **Team transfer** the app from individual → organisation account

What transfers intact: app listing, reviews, ratings, download history, App Store URL (`apps.apple.com/app/bristlenose/id123456789`). The numeric ID is permanent. What changes: publisher name flips from "Martin Storey" to "Bristlenose Ltd" (or whatever).

### Copyright structure

- **You personally own the copyright** (author, CLA assigns contributor rights to you)
- **You license the Ltd** to exploit the commercial version — the IP never transfers to the company
- **If the Ltd folds**, you still own everything
- **AGPL source stays yours** — the Ltd has a commercial licence from you

This is the standard solo-founder structure. See `docs/private/licensing-and-legal.md` for dual-licensing details and lawyer recommendations.

---

## Bundle ID

Changed from `CassioCassio.Bristlenose` → `research.bristlenose.app` (25 Mar) → `app.bristlenose.desktop` (27 Mar 2026).

Rationale: reverse-DNS of the owned domain `bristlenose.app`. Users see the product, not the holding company. The bundle ID appears in system logs, crash reports, Finder's app library, and Apple's notarisation records. Irrevocable after first App Store submission.

The v0.1-archive retains the old `CassioCassio.Bristlenose` bundle ID (frozen snapshot).

---

## Security Checklist (pre-launch)

From adversarial security review (25 Mar 2026):

### Before domain goes live

- [x] SPF/DKIM/DMARC on bristlenose.app (even before sending email: `-all` reject policy) — done 27 Mar 2026. Email + DKIM + SPF update done 15 Apr 2026
- [ ] SPF/DKIM/DMARC on cassiocassio.co.uk (if not already configured)
- [x] WHOIS privacy on both domains — enabled at registration 27 Mar 2026
- [x] Registrar lock (clientTransferProhibited) on bristlenose.app — default on, 27 Mar 2026
- [x] Registrar 2FA — enabled (authenticator app on phone)
- [x] Auto-renew with reliable payment method — default on, 27 Mar 2026
- [ ] Register for 5+ years upfront (new gTLD pricing can change) — registered for 2 years (expires 2029-03-27), renewable from 2027-03-27

### Before App Store submission

- [ ] security.txt at `bristlenose.app/.well-known/security.txt` (RFC 9116)
- [ ] Update SECURITY.md to include `security@bristlenose.app`
- [ ] AGPL + App Store legal opinion (see licensing-and-legal.md for lawyers)
- [ ] Decide individual vs Ltd enrollment (see Phase 2 above)

### Supply chain defence

- [ ] GitHub 2FA with hardware key (YubiKey)
- [ ] Branch protection on `main` (required status checks)
- [ ] PyPI 2FA with hardware key, project-scoped API token
- [ ] Register PyPI typosquats: `bristle-nose`, `bristlenose-cli` (empty packages)
- [ ] Document credential compromise recovery procedure

### Succession plan

- [ ] "Bus factor" document: every account, credential, recovery path
- [ ] Password manager emergency access for one trusted person
- [ ] Written runbook: "if compromised, do X" / "if unavailable, do Y"

---

## Substack Setup

1. Create Substack (e.g. `bristlenose.substack.com`)
2. Settings → Custom domain → `blog.bristlenose.app`
3. DNS: `blog.bristlenose.app CNAME target.substack-custom-domains.com`
4. Substack provisions SSL automatically
5. If moving off Substack later: export posts, stand up Ghost/Hugo, update CNAME. Same URL, zero broken links

---

## Identifiers Summary

| System | Identifier |
|--------|-----------|
| Apple bundle ID | `app.bristlenose.desktop` |
| Apple Developer | Individual (→ Organisation when Ltd justified) |
| Product domain | `bristlenose.app` |
| Blog | `blog.bristlenose.app` |
| GitHub org | `cassiocassio` |
| PyPI package | `bristlenose` |
| Homebrew tap | `cassiocassio/homebrew-bristlenose` |
| Keychain services | `Bristlenose *` |
| Keychain account | `bristlenose` |
| Author email | `martin@cassiocassio.co.uk` |
| Product email | `hello@bristlenose.app` |
| Support email | `support@bristlenose.app` |
| Security email | `security@bristlenose.app` |

---

*Created 25 Mar 2026 from brand architecture discussion + adversarial security review.*
