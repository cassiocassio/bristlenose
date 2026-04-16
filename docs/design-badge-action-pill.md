# Badge Action Pill (Proposed Badges)

Floating `[✗ | ✓]` pill bar on autocode-proposed badges. Replaces the old inline `✓/✗` approach that caused layout shift (badge width grew on hover, pushing the `+` button). Working context lives in `bristlenose/theme/CLAUDE.md`.

## Design decision

7 variations explored in `docs/mockups/mockup-proposed-badge-actions.html` (A–G). **Var G chosen** — combines E's pill concept, D's 16px hit targets, and A's positioning at the existing delete-circle location.

## Spec

| Property | Value | Notes |
|---|---|---|
| position (vertical) | `top: calc(-0.3rem - 1px)` | Same as delete `×` circles |
| position (horizontal) | `right: calc(-0.3rem - 1px - 1rem)` | `✗` aligns with delete `×`, `✓` hangs right |
| compartment size | `1rem × 1rem` (16px) | Larger than delete circles (14.5px) for better Fitts' law |
| border-radius | `8px` | Pill shape |
| shadow | `0 1px 4px rgba(0,0,0,0.16), 0 0 1px rgba(0,0,0,0.06)` | Matches delete circles |
| `✗` colour | `var(--bn-colour-danger)` / `#fef2f2` bg on hover | Same red as all delete/deny actions |
| `✓` colour | `var(--bn-colour-success)` / `#dcfce7` bg on hover | Green accept |
| divider | `1px solid var(--bn-colour-border)` | Between compartments |

## CSS classes

- **`.badge-action-pill`** — absolute-positioned pill container, `opacity: 0` → `1` on `.badge-proposed:hover`
- **`.badge-action-deny`** — left compartment (`✗`), red
- **`.badge-action-accept`** — right compartment (`✓`), green, `border-left` divider

## React

`Badge.tsx` proposed variant: DOM order is deny-then-accept (left-to-right in pill). Click handlers via `onAccept` / `onDeny` props.

## Colour unification

All delete/deny actions across badge types use `var(--bn-colour-danger)` (red):
- Sentiment badge `::after` delete circle
- User tag `.badge-delete` circle
- Proposed badge pill `.badge-action-deny` compartment

This replaced the previous grey `var(--bn-colour-muted)` on delete circles. Rationale: delete IS deny ("I don't want this tag"), so the colour should be consistent.
