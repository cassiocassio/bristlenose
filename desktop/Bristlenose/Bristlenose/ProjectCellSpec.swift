import AppKit

/// Layout + typography spec for the native AppKit project cell, reverse-engineered
/// VERBATIM from the SwiftUI `ProjectRow` (the cutover source-of-truth) so the
/// ported cell matches it. Every constant cites the `ProjectRow.swift` line it
/// mirrors — this is the "bulletproof spec" the rebuild is measured against; the
/// gallery harness diffs the rendered cell back to `ProjectRow` per state.
///
/// **The ONE deliberate divergence — row height.** `ProjectRow` reserves the
/// second line even when empty, via a hidden placeholder glyph
/// (`ProjectRow.swift:273-275`, "Hidden but layout-occupying so row heights remain
/// consistent"). Per the 22 Jun decision we drop that: a `.placeholder` row
/// collapses to a single line. This is the sole expected gallery-diff — recorded
/// here so a future check measures against the new baseline, not the old one.
///
/// Pure + substrate-free (only `AppKit` for `NSFont`/`CGFloat`); `isTwoLine` is
/// unit-tested. The layout *constants* are consumed by `ProjectSidebarOutline`'s
/// cell builder; the *content/state* mapping reuses `SubtitleVariant` /
/// `RunProgressSubtitle` unchanged (those already ARE the frozen logic spec).
enum ProjectCellSpec {

    // MARK: - Spacing (traceable to ProjectRow.body / titleLine / subtitleLine)

    /// Identity icon → text-stack gap. `HStack(alignment: .firstTextBaseline,
    /// spacing: 6)` — `ProjectRow.swift:119`.
    static let iconToText: CGFloat = 6

    /// Title line → subtitle line vertical gap. `VStack(spacing: 1)` — `:121`.
    static let titleToSubtitle: CGFloat = 1

    /// Title internal gap (name ↔ right slot). `HStack(spacing: 6)` with a
    /// `Spacer(minLength: 4)` — `:173`, `:179`.
    static let titleInternal: CGFloat = 6

    /// Subtitle internal gap (prefix glyph ↔ text, segment ↔ segment).
    /// `HStack(spacing: 4)` — `:211`, `:367`, `:388`.
    static let subtitleInternal: CGFloat = 4

    /// Trailing inset — right slot (count / cloud) to the cell's trailing edge.
    /// Matches the existing `iconCell` (`-4`) and `ProjectRow`'s `Spacer(minLength: 4)`.
    static let trailingInset: CGFloat = 4

    /// Uniform icon-column width. Kept consistent across lens / folder / project
    /// rows — the sidebar's "uniform icon column" (`design-project-sidebar.md`
    /// §1.2), NOT `ProjectRow`'s standalone default size. 18pt + `.medium` scale,
    /// as the existing `iconCell`.
    static let iconWidth: CGFloat = 18

    /// Native source-list row pitch (single-line, baseline-to-baseline) — MEASURED
    /// 22 Jun against Finder / Notes / Mail = 64px @2x = **32pt**. The fonts already
    /// matched; only the spacing was tight. The earlier font-derived height (~25pt)
    /// overrode the table's natural source-list pitch and cramped every row — pin to
    /// the platform value. (Tracks the user's measurement, not the icon-size setting;
    /// revisit if Dynamic-Type / sidebar-icon-size scaling becomes a concern.)
    static let singleLineHeight: CGFloat = 32

    /// Top inset for the two-line cell — places the title at the SAME vertical centre
    /// as a single-line row, so the title line never shifts when a subtitle appears
    /// or leaves: `(singleLineHeight − titleHeight) / 2`.
    static var verticalInset: CGFloat {
        max(2, (singleLineHeight - ceil(titleFont.boundingRectForFont.height)) / 2)
    }

    // MARK: - Typography (SwiftUI text-style → AppKit preferred font)

    /// Project name. SwiftUI default in a row resolves to `.body` — `:175`.
    static var titleFont: NSFont { .preferredFont(forTextStyle: .body) }

    /// Session count (title-right). `.font(.footnote)` / `.tertiary` — `:198-199`.
    static var countFont: NSFont { .preferredFont(forTextStyle: .footnote) }

    /// Subtitle text + glyphs. `.font(.caption)` / `.secondary` — `:374`, `:411`,
    /// `:427`. (`.caption` ⇒ AppKit `.caption1`.)
    static var subtitleFont: NSFont { .preferredFont(forTextStyle: .caption1) }

    // MARK: - Row height (the deliberate divergence)

    /// Whether this state shows a subtitle line (two-line) or collapses to a
    /// single line (`.placeholder`). The SOLE height-divergence from `ProjectRow`.
    static func isTwoLine(_ variant: SubtitleVariant) -> Bool {
        if case .placeholder = variant { return false }
        return true
    }

    /// The `NSOutlineView.heightOfRowByItem` value for a project row. Derived from
    /// the font line heights + the title↔subtitle gap + symmetric insets, so it
    /// tracks Dynamic Type rather than hard-coding pixels. `twoLine == false`
    /// (placeholder) → single-line — the divergence above.
    static func rowHeight(twoLine: Bool) -> CGFloat {
        if !twoLine { return singleLineHeight }
        // No native two-line source-list reference (Finder / Notes / Mail are
        // single-line); grow the single-line pitch by the subtitle line + the
        // title↔subtitle gap, keeping the same top/bottom breathing room.
        return singleLineHeight + titleToSubtitle + ceil(subtitleFont.boundingRectForFont.height)
    }
}
