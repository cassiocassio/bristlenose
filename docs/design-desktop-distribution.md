---
status: archived-historical
last-trued: 2026-04-28
supersedes: []
superseded-by:
  - docs/design-desktop-python-runtime.md
  - docs/design-modularity.md
---

# Desktop App Distribution — moved to archive

This doc was archived 28 Apr 2026. The Feb 2026 body, which evaluated `.dmg` + Developer ID distribution paths, lives at [`docs/archive/design-desktop-distribution.md`](archive/design-desktop-distribution.md) for historical reference.

**Where the active material now lives:**

- [`docs/design-desktop-python-runtime.md`](design-desktop-python-runtime.md) — Mac sidecar mechanics, entitlements (including the empty-ents retest result), signing pipeline, App Store distribution flow, and the deferred Developer ID flow preserved as future-state reference
- [`docs/design-modularity.md`](design-modularity.md) — cross-channel "what ships where" decisions; includes the 28 Apr 2026 App-Store-only / Developer-ID-deferred-until-~10k-users callout
- [`desktop/scripts/build-all.sh`](../desktop/scripts/build-all.sh) — the end-to-end build script that produces the `.pkg` for App Store Connect upload

**Distribution decision summary** (28 Apr 2026): App Store only, alpha through early commercial. Direct download via Developer ID + notarytool + Sparkle is deferred — not rejected — until ~10k paying users or first enterprise MDM ask. Pricing via Apple In-App Purchase, not Stripe.
</content>
