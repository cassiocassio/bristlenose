# HOWTO — Implementation Notes

## Responsive signal cards (Mar 2026)

CSS grid (`auto-fill, minmax(26rem, 1fr)`) on `.signal-cards` gives 2 columns on wide screens. Narrow stacking (`@media ≤500px`) collapses card internals vertically.

### Open issues — needs real-data testing

1. **Expanded cards tower over neighbors.** Fix: `.signal-card.expanded { grid-column: 1 / -1; }` — expanded card spans full width.
2. **Column flip when sidebar opens/closes.** 26rem × 2 + gap ≈ 864px of container width triggers 2-col. Sidebar toggle changes center column width — cards may jump between 1/2 columns. May need a wider minmax or container query instead of viewport query.
3. **Metrics grid width in narrow stacking.** `flex-shrink: 0` is inert in column direction, but `align-self: flex-start` keeps metrics compact. Eyeball whether concentration bars should stretch full-width on mobile.
