# Sidebar IA and UX Patterns

Date: 2026-03-01  
Status: Draft design note

## Purpose

Capture common sidebar UX patterns (macOS-native and cross-platform) and map them to Bristlenose's current and future information architecture (IA), including project-level and cross-project navigation.

## Summary

The strongest cross-app pattern is not a single universal shortcut. It is a stable role split:

- Left sidebar: structure/navigation ("where am I?")
- Right sidebar: context/filter/inspector ("what am I viewing?")

For Bristlenose, this maps cleanly to:

- Left: IA/navigation (project + sections/themes/session jump points)
- Right: tag/codebook/filter controls

## Current Bristlenose IA Baseline

Top-level IA is currently tabbed:

- `Project`
- `Sessions`
- `Quotes`
- `Codebook`
- `Analysis`
- Plus `Settings` and `About` icons

Relevant implementation references:

- `frontend/src/router.tsx` (route structure)
- `frontend/src/components/NavBar.tsx` (global tab bar)
- `frontend/src/islands/QuoteSections.tsx` (sections anchors and filtered quote groups)
- `frontend/src/islands/QuoteThemes.tsx` (themes anchors and filtered quote groups)
- `frontend/src/hooks/useKeyboardShortcuts.ts` (existing keyboard model)

Existing sidebar direction already documented:

- `docs/BRANCHES.md` (`sidebar` branch intent)
- `docs/mockups/mockup-sidebar-tags.html` (dual-sidebar prototype)

Important architectural constraint:

- Server currently assumes a single loaded project (`/api/projects/1`); multi-project IA is future-state.
- See `bristlenose/server/CLAUDE.md`.

## External Pattern Scan

### Commonality

- No universal sidebar keybinding across all app categories.
- Mature apps are consistent about sidebar semantics, not specific keys.
- Apps with two sidebars typically provide:
- Separate left/right toggles
- A "toggle both" action
- Persistent sidebar open/closed + width state

### Typical role split

- Left rail/panel: navigation hierarchy (files/channels/pages/sections)
- Right panel: filters, details, inspectors, properties

### Keyboard norms by ecosystem

- macOS-native/file-manager muscle memory: `⌥⌘S` is highly familiar.
- Developer tooling commonly uses `⌘B`/`Ctrl+B` for sidebars/activity bars.
- Collaboration/design tools often use bracket/backslash style panel toggles.

Implication: pick defaults by platform and app intent, then make them rebindable.

## Proposed Bristlenose Sidebar Model

## 1) Semantic contract (stable across product)

Use this everywhere sidebars appear:

- Left = location/scope/navigation
- Right = filters/facets/inspection/actions

This prevents relearning when users move across tabs.

## 2) Quotes tab (near-term)

Use dual sidebar as planned:

- Left TOC: sections + themes + scroll-spy
- Right tags: codebook tree, checkboxes, eye toggles, counts, micro-bars

Rationale:

- Matches current quote data model and planned implementation.
- Preserves center column for reading quote cards.

## 3) Cross-tab and future cross-project (mid-term)

When multi-project arrives, left sidebar should become a scope tree with explicit context labels:

- Workspace (all projects)
- Project
- Tab-local subsection

Example progression:

- `Workspace > Project A > Quotes > Sections > Checkout`
- `Workspace > Project A > Analysis > Codebook Signals`

Right sidebar remains contextual to current view:

- Quotes: tags/filters
- Sessions: session filters/facets
- Analysis: signal filters (confidence, source type, codebook)

## Keybinding Strategy

Recommended defaults:

- macOS primary sidebar toggle: `⌥⌘S`
- Advanced dual-sidebar controls:
- `⌘[` toggle left
- `⌘]` toggle right
- `⌘.` toggle both

Avoid making `⌘B` the primary macOS default in Bristlenose:

- High collision risk with bold/text-editing muscle memory.
- Particularly problematic in text-heavy researcher workflows.

## Edge Cases to Design Explicitly

## Focus and filtering

- Focused quote is hidden by filter/hide action:
- Move focus to nearest visible sibling; if none, clear focus and announce state.

## Sidebar persistence

- Persist per-tab open/closed and width.
- Avoid one global width if tabs need different reading density.

## Narrow windows

- Define breakpoints when both sidebars cannot stay open.
- Priority rule: keep active sidebar; collapse inactive side first.

## Very large IA trees

- Support disclosure groups and efficient rendering for long lists.
- Keep keyboard traversal predictable after expand/collapse.

## Mode clarity (project vs cross-project)

- Always show current scope label near top-left.
- Never let users wonder whether they are looking at one project or aggregated data.

## Interaction and Accessibility Notes

- Sidebars should not hijack existing quote navigation shortcuts (`j/k`, `/`, `?`, selection keys).
- Sidebar shortcuts must respect editing contexts (input/contenteditable open).
- Include sidebar shortcuts in help modal.
- Ensure focus order includes rail buttons, sidebar content, and resize controls.

## Phased Implementation Plan

1. Ship Quotes-tab dual sidebar with current planned components.
2. Stabilize shortcut map and persistence behavior.
3. Extend left sidebar schema to include project-level and then workspace-level scope nodes.
4. Add analysis/sessions contextual right-sidebar variants reusing shared primitives.
5. Add shortcut rebinding in Settings once cross-platform desktop surfaces are active.

## Decision Log (current)

- Chosen semantic split: left=where, right=what.
- Chosen macOS primary toggle recommendation: `⌥⌘S`.
- Keep bracket/both toggles for power use in dual-sidebar mode.
- Preserve top tab IA; sidebar augments it, does not replace it.

## Source References

Internal references:

- `/Users/cassio/Code/bristlenose/frontend/src/router.tsx`
- `/Users/cassio/Code/bristlenose/frontend/src/components/NavBar.tsx`
- `/Users/cassio/Code/bristlenose/frontend/src/islands/QuoteSections.tsx`
- `/Users/cassio/Code/bristlenose/frontend/src/islands/QuoteThemes.tsx`
- `/Users/cassio/Code/bristlenose/frontend/src/hooks/useKeyboardShortcuts.ts`
- `/Users/cassio/Code/bristlenose/docs/BRANCHES.md`
- `/Users/cassio/Code/bristlenose/docs/mockups/mockup-sidebar-tags.html`
- `/Users/cassio/Code/bristlenose/bristlenose/server/CLAUDE.md`

External references consulted:

- Apple Finder keyboard shortcuts: https://support.apple.com/en-mk/102650
- VS Code default keybindings: https://code.visualstudio.com/docs/reference/default-keybindings
- Slack keyboard shortcuts: https://slack.com/help/articles/201374536-Slack-keyboard-shortcuts
- Figma keyboard shortcuts: https://help.figma.com/hc/en-us/articles/360040328653-Use-keyboard-shortcuts-in-Figma
- Obsidian help (commands/shortcuts): https://help.obsidian.md/Plugins/Command+palette
- JetBrains macOS keymap reference: https://www.jetbrains.com/help/idea/reference-keymap-mac-default.html
