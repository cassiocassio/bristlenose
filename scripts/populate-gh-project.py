#!/usr/bin/env python3
"""Populate GitHub Projects board from 100days.md categories."""

import json
import subprocess
import sys
import time

PROJECT_ID = "PVT_kwHOAEYXlM4BORbY"
STATUS_FIELD_ID = "PVTSSF_lAHOAEYXlM4BORbYzg9Becg"

# Status = workflow stage (keep it simple)
STATUSES = [
    "Todo",
    "In Progress",
    "Done",
    "Legacy Backlog",
]

# Kind = the 14 categories + supplementary sections
KINDS = [
    "1. Missing",
    "2. Broken",
    "3. Embarrassing",
    "4. Value",
    "5. Blocking",
    "6. Risk",
    "7. Halo",
    "8. Quality of Life",
    "9. Technical Debt",
    "10. Documentation",
    "11. Operations",
    "12. Legal/Compliance",
    "13. Go-to-Market",
    "14. Accessibility",
    "Active Branches",
    "Needs Design Doc",
    "Investigations",
]

PRIORITIES = ["Must", "Should", "Could", "Won't"]

# All items from 100days.md: (kind, priority, title, body)
ITEMS = [
    # 1. Missing
    ("1. Missing", "Must", "Desktop app v0.1", "SwiftUI shell, PyInstaller sidecar, folder picker, pipeline runner, 'Open Report' button. ~365-435 MB bundle. (design-desktop-app.md)"),
    ("1. Missing", "Must", "Export: standalone HTML from serve mode", "POST /api/projects/{id}/export, self-contained zip with report + transcripts. Phases 0-1 of export roadmap. (design-export-sharing.md)"),
    ("1. Missing", "Must", "Multi-project support", "Home screen, project list, create/switch without restart. Milestone 4 in ROADMAP. Needs design doc"),
    ("1. Missing", "Must", "File import (drag-and-drop)", "Add recordings to project from GUI. Milestone 5. Needs design doc"),
    ("1. Missing", "Must", "Run pipeline from GUI", "'Analyse' button, background task, progress streaming. Milestone 7. Needs design doc"),
    ("1. Missing", "Must", "Settings UI", "Provider selection, API key entry, redaction toggle, model choice. Milestone 6. Needs design doc. Currently CLI-only config is a hard block for App Store users"),
    ("1. Missing", "Must", "App Store subscription infrastructure", "StoreKit 2, receipt validation, entitlement check. Not yet designed"),
    ("1. Missing", "Must", "Auto-serve after run", "Pipeline finishes -> auto-launch serve + open browser. (TODO.md immediate)"),
    ("1. Missing", "Should", "Session enable/disable toggle", "Exclude sessions without re-running pipeline. Option A (is_disabled bool). (design-session-management.md)"),
    ("1. Missing", "Should", "Incremental re-run", "Add new recordings, preserve researcher work. Milestone 8. Quote stable key already in place"),
    ("1. Missing", "Should", "Left-hand nav content for all tabs", "Signal cards, speaker badges, codebook titles, sessions list, analysis views in left sidebar"),
    ("1. Missing", "Should", "Standard modal with nav for Settings and About", "Consistent modal pattern, consider unifying help + about"),
    ("1. Missing", "Should", "New title bar design", "Current title bar needs refresh"),
    ("1. Missing", "Should", "Post-analysis review panel", "Non-modal, dismissable panel after pipeline completes: name correction, token summary, coverage overview"),
    ("1. Missing", "Should", ".docx export", "Word document output for sharing with stakeholders (#20)"),
    ("1. Missing", "Should", "Video clip export", "Starred quotes as trimmed clips. Phase 4 of export. (design-export-sharing.md)"),
    ("1. Missing", "Could", "Batch processing dashboard", "Queue multiple projects (#27)"),
    ("1. Missing", "Could", "Custom prompts", "User-defined tag categories / analysis instructions"),
    ("1. Missing", "Could", "Published reports", "Cloudflare R2 hosted sharing. Phase 2-3 of export"),
    ("1. Missing", "Won't", "Windows app", "winget installer (#44), Windows credential store"),
    ("1. Missing", "Won't", "Miro bridge", "CSV export works as stopgap"),
    ("1. Missing", "Won't", "In-app report viewing (WKWebView)", "Defer to v0.2 desktop"),
    ("1. Missing", "Won't", "Multi-page report", "Tabs or linked pages (#51). Large effort, defer post-launch"),
    ("1. Missing", "Won't", "Project setup UI for new projects", "#49 - large effort, defer post-launch"),

    # 2. Broken
    ("2. Broken", "Must", "Dark mode selection highlight", "Invisible in dark mode (#52)"),
    ("2. Broken", "Must", "Dark logo", "Placeholder inverted image, needs proper albino bristlenose pleco (#18, logo.css HACK)"),
    ("2. Broken", "Must", "Circular dependency in production build", "Fixed in 0.13.6 but regression-prone (SidebarStore import cycle)"),
    ("2. Broken", "Must", "Import FK constraint", "Fixed in 0.13.4 (ProposedTag cleanup) but needs E2E coverage to prevent regression"),
    ("2. Broken", "Should", "Local model reliability", "~85% vs ~99% cloud. Investigate parse failure patterns (llm/CLAUDE.md)"),
    ("2. Broken", "Should", "Speaker diarisation", "Cross-session moderator linking not working (#25, #26)"),
    ("2. Broken", "Should", "Badge x character", "Platform-inconsistent rendering, replace with SVG (badge.css TODO)"),
    ("2. Broken", "Could", "Edit writeback to transcript files", "Edits only persist in DB, not source files (#21)"),
    ("2. Broken", "Could", "Word timestamp pruning", "Unused data accumulates after merge stage (#35)"),

    # 3. Embarrassing
    ("3. Embarrassing", "Must", "Logo size", "80px feels tiny, increase to ~100px (#6)"),
    ("3. Embarrassing", "Must", "Responsive quote grid", "Phase 1 CSS-only, design ready, not implemented (design-responsive-layout.md)"),
    ("3. Embarrassing", "Must", "Help modal polish", "Renders but styling rough (memory note)"),
    ("3. Embarrassing", "Must", "'Made with Bristlenose' branding footer", "Phase 5 of export, quick win (design-export-sharing.md)"),
    ("3. Embarrassing", "Must", "Export polish", "Inline logo as base64, fix footer 'Bristlenoseversion' missing space, fix in-report navigation links (hash router)"),
    ("3. Embarrassing", "Should", "Typography audit", "16 font-sizes -> ~10 with proper tokens (ROADMAP theme refactoring)"),
    ("3. Embarrassing", "Should", "Tag density", "AI generates too many tags, overwhelming (#12)"),
    ("3. Embarrassing", "Should", "Histogram bar alignment", "Right-align user-tags bars (#13)"),
    ("3. Embarrassing", "Should", "Day of week in session Start column", "#11"),
    ("3. Embarrassing", "Should", "Animated logo", "living-fish branch: breathing, gill pulsing, fin movement. Statement piece"),
    ("3. Embarrassing", "Should", "Right-hand sidebar animations", "Match left-hand sidebar push/slide animations"),
    ("3. Embarrassing", "Could", "Symbology", "Consistent Unicode prefixes across navigation. Active branch"),
    ("3. Embarrassing", "Could", "SVG icon set", "Replace character glyphs with proper icons"),
    ("3. Embarrassing", "Could", "Close button CSS", "Extract .close-btn atom (theme refactoring)"),
    ("3. Embarrassing", "Could", "Content density setting", "Compact (14px) / Normal (16px) / Generous (18px) toggle. --bn-content-scale token"),
    ("3. Embarrassing", "Could", "Colour themes", "Named themes (e.g. 'edo') as appearance switch. Beyond custom CSS - curated, designed themes"),
    ("3. Embarrassing", "Could", "Grid, spacing, type, colours audit", "Holistic visual fit-and-finish pass"),

    # 4. Value
    ("4. Value", "Must", "Signal elaboration", "Interpretive names + one-sentence summaries on signal cards. Designed (design-signal-elaboration.md)"),
    ("4. Value", "Must", "Codebook-aware tagging QA", "Shipped in 0.13.0, verify it works end-to-end on real data"),
    ("4. Value", "Must", "Quick-repeat tag shortcut (r key) QA", "Shipped, verify discoverability"),
    ("4. Value", "Must", "Bulk actions QA", "Shipped in 0.13.3, verify on real multi-session projects"),
    ("4. Value", "Must", "Threshold review dialog QA on real data", "Run AutoCode against real projects, evaluate confidence histogram + dual slider UX"),
    ("4. Value", "Should", "Analysis Phase 4", "Two-pane layout, grid-as-selector. Medium effort (design-analysis-future.md)"),
    ("4. Value", "Should", "Clickable histogram bars", "Filtered view (#14)"),
    ("4. Value", "Should", "Lost quotes rescue", "Surface unselected quotes (#19)"),
    ("4. Value", "Should", "Moderator question pill", "Hover-triggered context (design-moderator-question-pill.md)"),
    ("4. Value", "Should", "Quote sequences", "Consecutive quote detection, ordinal-based for non-timecoded transcripts (design-quote-sequences.md)"),
    ("4. Value", "Should", "Sidebar tag assign", "Hover hint matching 'add tag' visual language + toast undo"),
    ("4. Value", "Should", "Dashboard stats coverage", "Increase pipeline metrics surfaced on dashboard"),
    ("4. Value", "Should", "Drag-and-drop tags to quotes", "Drag tag badge onto quote card to apply"),
    ("4. Value", "Could", "Analysis Phase 5", "LLM narration of signal cards"),
    ("4. Value", "Could", "User-tag x group grid", "New heatmap view"),
    ("4. Value", "Could", "Tag definitions page", "#53"),
    ("4. Value", "Could", "Transcript page user tags", "Tag directly from transcript view"),
    ("4. Value", "Could", "Framework acronym prefixes on badges", "Small-caps 2-3 letter author prefix (e.g. JJG, DN)"),
    ("4. Value", "Could", "Drag-to-reorder codebook frameworks", "Researchers drag framework sections to prioritise, persist per project"),
    ("4. Value", "Could", "People.yaml web UI", "In-report UI to update unidentified participants. Part of Moderator Phase 2 (#25)"),
    ("4. Value", "Could", "Relocate AI tag toggle", "Removed from toolbar (too crowded); needs a new home"),
    ("4. Value", "Could", "Delete/quarantine session from UI", ".bristlenose-ignore file (safe, reversible). (design-session-management.md)"),
    ("4. Value", "Could", "Re-run pipeline from serve mode", "POST /api/projects/{id}/rerun, background task with progress streaming"),
    ("4. Value", "Could", "User research panel opt-in", "Optional email field in feedback modal"),
    ("4. Value", "Could", "Pass transcript data to renderer", "Avoid redundant disk I/O"),

    # 5. Blocking
    ("5. Blocking", "Must", "First-run experience", "New user opens app, has no project, no API key, no recordings. What happens? Needs design"),
    ("5. Blocking", "Must", "API key entry in GUI", "Currently requires terminal. Absolute blocker for App Store users"),
    ("5. Blocking", "Must", "Error messaging", "Pipeline failures need clear, actionable messages (not stack traces)"),
    ("5. Blocking", "Must", "bristlenose doctor in GUI", "Dependency health checks visible in app, not just CLI"),
    ("5. Blocking", "Must", "Homebrew formula: spaCy model", "post_install step (#42). Without it, first run fails"),
    ("5. Blocking", "Must", "Demo dataset", "5h IKEA study as public, credible test data. Exercise all frameworks, test with real user tags"),
    ("5. Blocking", "Should", "Time estimate warning", "Warn before long transcription jobs (#39)"),
    ("5. Blocking", "Should", "Provider documentation", "Which provider to choose, cost comparison (#38)"),
    ("5. Blocking", "Should", "Whisper prefetch flag", "--prefetch-model to avoid surprise downloads (#41)"),
    ("5. Blocking", "Could", "Shell completion", "--install-completion for power users"),
    ("5. Blocking", "Could", "Snap Store publishing", "Linux adoption path (#45)"),
    ("5. Blocking", "Could", "Cancel button", "Cancel running pipeline (desktop app stretch goal)"),

    # 6. Risk
    ("6. Risk", "Must", "Rotate API key", "Was visible in terminal (TODO.md immediate)"),
    ("6. Risk", "Must", "Privacy policy", "Required for App Store submission. Local-first model simplifies this but document must exist"),
    ("6. Risk", "Must", "Terms of service", "Subscription terms, refund policy, data handling"),
    ("6. Risk", "Must", "App Store review compliance", "Sandbox, entitlements, code signing, notarisation pipeline"),
    ("6. Risk", "Must", "PII redaction audit", "Verify Presidio catches names/emails in transcripts before shipping to paying users"),
    ("6. Risk", "Must", "Security scanning", "npm audit, pip-audit, CodeQL before public release (design-test-strategy.md)"),
    ("6. Risk", "Must", "Alembic/migration strategy", "DB schema changes without data loss. Currently no migration framework"),
    ("6. Risk", "Should", "Vulnerability disclosure page", "SECURITY.md exists but not public-facing"),
    ("6. Risk", "Should", "GDPR/data processor statement", "Even though local-first, API calls send data to LLM providers"),
    ("6. Risk", "Should", "Crash reporting", "Know when the app breaks in the field. Sentry or similar"),
    ("6. Risk", "Should", "Windows credential store", "Env var fallback is insecure (SECURITY.md gap)"),
    ("6. Risk", "Should", "PostMessage origin tightening", "Currently '*', should be same-origin (ROADMAP)"),
    ("6. Risk", "Should", "localStorage namespace by project", "Data collision risk (ROADMAP)"),
    ("6. Risk", "Could", "Export anonymisation", "Checkbox to strip names/display-names from exported HTML"),
    ("6. Risk", "Could", "Rate limiting", "If server ever exposed beyond localhost"),
    ("6. Risk", "Could", "pip-audit in CI", "Dependency vulnerability scanning"),

    # 7. Halo
    ("7. Halo", "Must", "Local-first story", "'Nothing leaves your laptop' messaging. Core differentiator. Needs landing page copy"),
    ("7. Halo", "Must", "One-command install", "brew install bristlenose already works. Showcase this"),
    ("7. Halo", "Should", "Living logo", "Animated bristlenose pleco (living-fish branch). Memorable, delightful"),
    ("7. Halo", "Should", "Dark mode polish", "Already implemented, polish the rough edges"),
    ("7. Halo", "Should", "Speed demo", "'Folder in, report out in 5 minutes' video/GIF for landing page"),
    ("7. Halo", "Should", "Keyboard-first UX showcase", "Shortcuts already deep. Showcase in marketing"),
    ("7. Halo", "Should", "Open source (AGPL) positioning", "Trust signal for researchers. Emphasise in positioning"),
    ("7. Halo", "Should", "Microinteractions", "Bounces/slides for opens/closes, flashes of acceptance, staggered fly-up for bulk hide"),
    ("7. Halo", "Could", "Video clip sharing", "'Share the moment, not the transcript'"),
    ("7. Halo", "Could", "Ollama integration showcase", "'Free, no account required' local LLM story"),
    ("7. Halo", "Could", "Multi-language", "i18n infrastructure shipped (0.13.6), add 2-3 languages"),

    # 8. Quality of Life
    ("8. Quality of Life", "Must", "Keyboard shortcuts help modal polish", "Shipped but needs polish. Platform-aware Cmd/Ctrl"),
    ("8. Quality of Life", "Should", "Sidebar drag-to-push", "Active branch (drag-push), replaces overlay mode"),
    ("8. Quality of Life", "Should", "Responsive signal cards", "Active branch (responsive-signal-cards)"),
    ("8. Quality of Life", "Should", "Undo bulk tag", "Cmd+Z for last tag action (ROADMAP)"),
    ("8. Quality of Life", "Should", "Sticky header", "Decision pending (#15)"),
    ("8. Quality of Life", "Should", "Density setting", "Compact/comfortable/spacious for quote grid"),
    ("8. Quality of Life", "Should", "Highlighter feature", "Active branch, scope TBD"),
    ("8. Quality of Life", "Could", "Theme management in browser", "Custom CSS themes (#17)"),
    ("8. Quality of Life", "Could", "Transcript expand/collapse", "Collapsible sections and themes"),
    ("8. Quality of Life", "Could", "Drag-and-drop quote reordering", "Large effort"),
    ("8. Quality of Life", "Could", "Transcript pulldown menu", "Margin annotations (ROADMAP)"),
    ("8. Quality of Life", "Could", "Measure-aware leading", "Line-height interpolation based on column width (Bringhurst). Playground has slider"),

    # 9. Technical Debt
    ("9. Technical Debt", "Must", "Frontend CI", "Vitest + ESLint + Prettier + TypeScript strict mode in CI pipeline. Currently not gated"),
    ("9. Technical Debt", "Must", "Playwright E2E layers 4-5", "Layers 1-3 done, need layers 4-5 for DB-mutating actions (design-playwright-testing.md)"),
    ("9. Technical Debt", "Must", "pytest coverage in CI", "Trivial to enable, currently blind to dead code"),
    ("9. Technical Debt", "Must", "Multi-Python CI", "Test 3.10, 3.11, 3.12, 3.13 (trivial, avoids EOL surprises)"),
    ("9. Technical Debt", "Should", "Alembic setup", "DB migration framework before any schema change"),
    ("9. Technical Debt", "Should", "Visual regression baselines", "Playwright screenshots, light + dark"),
    ("9. Technical Debt", "Should", "Cross-browser Playwright", "Chromium + Firefox + WebKit"),
    ("9. Technical Debt", "Should", "Bundle size budget", "Track and gate frontend bundle growth"),
    ("9. Technical Debt", "Should", "Platform detection refactor", "Shared utils/system.py (#43)"),
    ("9. Technical Debt", "Should", "Skip logo copy when unchanged", "#31"),
    ("9. Technical Debt", "Should", "Temp WAV cleanup", "#33"),
    ("9. Technical Debt", "Should", "Pipeline concurrent chaining", "#32"),
    ("9. Technical Debt", "Should", "LLM response cache", "#34"),
    ("9. Technical Debt", "Should", "Logging tiers 2-3", "Cache hit/miss decisions, concurrency queue depth, PII entity breakdown, FFmpeg command/return code, keychain resolution, manifest load/save"),
    ("9. Technical Debt", "Could", "a11y lint rules", "eslint-plugin-jsx-a11y"),
    ("9. Technical Debt", "Could", "axe-core in E2E", "Automated accessibility assertions"),
    ("9. Technical Debt", "Could", "Component Storybook", "Visual component catalogue"),
    ("9. Technical Debt", "Could", "Typography token consolidation", "16 sizes -> ~10"),
    ("9. Technical Debt", "Could", "Tag-count dedup", "3 implementations -> shared countUserTags()"),
    ("9. Technical Debt", "Could", "isEditing() guard dedup", "Shared EditGuard class"),
    ("9. Technical Debt", "Could", "Inline edit commit pattern", "Shared inlineEdit() helper"),
    ("9. Technical Debt", "Won't", "JS module cleanup", "#7, #8, #9, #10, #22, #23 - vanilla JS is frozen/deprecated"),
    ("9. Technical Debt", "Won't", "'use strict' in all modules", "#7 - frozen path"),
    ("9. Technical Debt", "Won't", "Explicit cross-module state management", "#23 - React replaced this"),

    # 10. Documentation
    ("10. Documentation", "Must", "App Store description", "Short + long description, keywords, screenshots"),
    ("10. Documentation", "Must", "In-app onboarding", "First-run wizard or guided tour for new users"),
    ("10. Documentation", "Must", "Provider setup guide", "Which LLM provider, how to get API key, cost expectations"),
    ("10. Documentation", "Must", "README polish", "Landing page README for GitHub (currently dev-focused)"),
    ("10. Documentation", "Must", "Hero image of report on GitHub README", "Screenshot showing a real report, above the fold"),
    ("10. Documentation", "Should", "Video walkthrough", "2-minute 'here's what Bristlenose does' screencast"),
    ("10. Documentation", "Should", "FAQ / troubleshooting", "Common issues (FFmpeg, API keys, large files)"),
    ("10. Documentation", "Should", "INSTALL.md desktop section", "'Download, drag to Applications, done'"),
    ("10. Documentation", "Should", "Changelog for users", "User-facing changelog (not dev changelog)"),
    ("10. Documentation", "Should", "How-to-get-API-key screenshots", "Step-by-step visual guide for Claude, ChatGPT, Gemini console"),
    ("10. Documentation", "Could", "Research methodology guide", "How Bristlenose analyses data, for researchers who want to understand"),
    ("10. Documentation", "Could", "Academic citation", "BibTeX entry for papers"),
    ("10. Documentation", "Could", "API documentation", "For power users who want to script against serve mode"),

    # 11. Operations
    ("11. Operations", "Must", "Desktop app build pipeline", "Xcode archive -> .dmg -> notarisation -> upload. CI: automate .dmg build on push"),
    ("11. Operations", "Must", "App Store Connect setup", "App record, pricing, TestFlight beta group"),
    ("11. Operations", "Must", "Code signing", "Apple Developer Program membership, Developer ID certificate"),
    ("11. Operations", "Must", "CI: add macOS runner", "Currently Linux-only"),
    ("11. Operations", "Must", ".dmg README", "Include 'Open Anyway' Gatekeeper instructions"),
    ("11. Operations", "Should", "Desktop app polish", "Keychain migration, SwiftUI .fileImporter(), AsyncBytes, hasAnyAPIKey() extend beyond Anthropic-only"),
    ("11. Operations", "Should", "Doctor serve-mode checks", "Vite auto-discovery via /__vite_ping, replace hardcoded port"),
    ("11. Operations", "Should", "Extract design tokens for Figma", "Colours, spacing, typography, radii -> JSON/CSS variables"),
    ("11. Operations", "Should", "Crash reporting setup", "Sentry or Apple's built-in crash reporting"),
    ("11. Operations", "Should", "Update mechanism", "Sparkle framework or App Store auto-update"),
    ("11. Operations", "Should", "CI snap smoke test", "Verify Snap package installs cleanly (TODO.md)"),
    ("11. Operations", "Should", "TestFlight beta", "Pre-launch testing with real users"),
    ("11. Operations", "Should", "Windows CI", "pytest on windows-latest runner"),
    ("11. Operations", "Could", "Analytics", "Privacy-respecting usage analytics (opt-in only)"),
    ("11. Operations", "Could", "Feedback endpoint", "Deploy to Dreamhost (TODO.md)"),
    ("11. Operations", "Could", "Weekly install smoke tests", "Automated pip/pipx/brew verification"),

    # 12. Legal/Compliance
    ("12. Legal/Compliance", "Must", "Apple Developer Program", "$99/year membership"),
    ("12. Legal/Compliance", "Must", "Privacy policy URL", "Required for App Store submission"),
    ("12. Legal/Compliance", "Must", "Terms of service", "Subscription terms"),
    ("12. Legal/Compliance", "Must", "App sandbox compliance", "Entitlements for file access, network (LLM API calls)"),
    ("12. Legal/Compliance", "Must", "Export compliance", "HTTPS only, no custom encryption = simplified declaration"),
    ("12. Legal/Compliance", "Must", "Age rating", "Likely 4+ (no objectionable content)"),
    ("12. Legal/Compliance", "Must", "EULA", "Standard Apple EULA or custom"),
    ("12. Legal/Compliance", "Should", "GDPR statement", "Data processing description (local-first, API calls to LLM providers)"),
    ("12. Legal/Compliance", "Should", "Accessibility statement", "VoiceOver compatibility, keyboard navigation"),
    ("12. Legal/Compliance", "Should", "Open source license display", "AGPL notice in app + dependency licenses"),
    ("12. Legal/Compliance", "Could", "Cookie/tracking transparency", "App Tracking Transparency framework (likely N/A for local-first)"),

    # 13. Go-to-Market
    ("13. Go-to-Market", "Must", "Pricing decision", "$/month, what's included, free tier?"),
    ("13. Go-to-Market", "Must", "Public-facing website", "Product landing page with install CTA, 'nothing leaves your laptop' messaging, speed demo GIF, comparison. Needs domain registration"),
    ("13. Go-to-Market", "Must", "Domain registration", "bristlenose.app (~$15/yr) recommended. Alternatives: .dev, .io, .research"),
    ("13. Go-to-Market", "Must", "App Store screenshots", "3-5 screenshots at required resolutions"),
    ("13. Go-to-Market", "Must", "App Store preview video", "15-30 second demo (optional but high impact)"),
    ("13. Go-to-Market", "Must", "Demo dataset (GTM)", "Sample project that ships with app or is downloadable, so new users see a real report immediately"),
    ("13. Go-to-Market", "Should", "Product Hunt launch", "Prepared assets, description, maker comment"),
    ("13. Go-to-Market", "Should", "Twitter/LinkedIn announcement", "Launch thread with GIF/video"),
    ("13. Go-to-Market", "Should", "HN Show post", "Show HN: Local-first user research analysis"),
    ("13. Go-to-Market", "Should", "UX research community outreach", "ResearchOps Slack, UXPA, mixed methods communities"),
    ("13. Go-to-Market", "Should", "Comparison page", "vs Dovetail, vs EnjoyHQ, vs manual spreadsheet"),
    ("13. Go-to-Market", "Could", "Blog post", "'Why we built Bristlenose' story"),
    ("13. Go-to-Market", "Could", "Academic outreach", "HCI conferences, PhD students"),
    ("13. Go-to-Market", "Could", "Referral/word-of-mouth", "'Share with a colleague' in-app prompt"),

    # 14. Accessibility
    ("14. Accessibility", "Must", "Keyboard navigation audit", "Verify all interactive elements reachable via Tab"),
    ("14. Accessibility", "Must", "VoiceOver testing", "Basic screen reader pass on report and desktop app"),
    ("14. Accessibility", "Must", "Colour contrast", "WCAG AA on all text (light + dark mode)"),
    ("14. Accessibility", "Must", "Focus indicators", "Visible focus rings on all interactive elements"),
    ("14. Accessibility", "Should", "ARIA attributes", "Proper roles on custom widgets (sidebar, tag input, dropdowns) (#24)"),
    ("14. Accessibility", "Should", "Reduced motion", "prefers-reduced-motion respected (partially shipped in 0.13.0)"),
    ("14. Accessibility", "Should", "eslint-plugin-jsx-a11y", "Lint-time a11y checks"),
    ("14. Accessibility", "Should", "axe-core in Playwright", "Automated a11y assertions in E2E"),
    ("14. Accessibility", "Could", "High contrast mode", "Windows high contrast / forced-colors support"),
    ("14. Accessibility", "Could", "Screen reader announcements", "Live regions for async operations (tag applied, quote hidden)"),

    # Active Branches
    ("Active Branches", None, "Branch: symbology", "Unicode prefix symbols across UI. Started 12 Feb. Merge target: main"),
    ("Active Branches", None, "Branch: highlighter", "Highlighter feature (scope TBD). Started 13 Feb. Merge target: main"),
    ("Active Branches", None, "Branch: living-fish", "Animated bristlenose logo for serve mode. Started 26 Feb. Merge target: main"),
    ("Active Branches", None, "Branch: drag-push", "Sidebar rail drag-to-open -> push mode. Started 14 Mar. Merge target: main"),
    ("Active Branches", None, "Branch: responsive-signal-cards", "Responsive signal/analysis card layout. Started 15 Mar. Merge target: main"),

    # Needs Design Doc
    ("Needs Design Doc", "Must", "Design doc: Multi-project support", "Milestone 4"),
    ("Needs Design Doc", "Must", "Design doc: File import / drag-and-drop", "Milestone 5"),
    ("Needs Design Doc", "Must", "Design doc: Settings UI", "Milestone 6"),
    ("Needs Design Doc", "Must", "Design doc: Run pipeline from GUI", "Milestone 7"),
    ("Needs Design Doc", "Must", "Design doc: First-run experience / onboarding", ""),
    ("Needs Design Doc", "Must", "Design doc: App Store subscription infrastructure", ""),
    ("Needs Design Doc", "Must", "Design doc: Pricing model", ""),

    # Investigations
    ("Investigations", None, "Investigate: Sentiment badges as built-in codebook framework", "Sentiments are conceptually just another codebook; unifying would simplify thresholds, review dialog, accept/deny. Big but significant"),
    ("Investigations", None, "Investigate: Tag namespace uniqueness + import merge strategy", "Flat namespace, clash detection, provenance tracking (user vs framework vs AutoCode)"),
    ("Investigations", None, "Investigate: Canonical tag -> colour as first-class schema", "Persist colour_set/colour_index on TagDefinition to survive reordering; eliminate client-side colour computation"),
    ("Investigations", None, "Investigate: Sidebar filter undo history stack", "Multi-step undo for tag filter state changes (show-only clicks, tick toggles)"),
    ("Investigations", None, "Investigate: Measure-aware leading", "Line-height should increase with wider columns (Bringhurst). Explore interpolating across 23rem-52rem range"),
    ("Investigations", None, "Investigate: Tokenise acceptance flash as design system pattern", "Generalise badge-accept-flash into reusable .bn-confirm-flash + useFlash(key) hook"),
    ("Investigations", None, "Dependency: Quarterly review May 2026", "pip list --outdated, bump for security/features"),
    ("Investigations", None, "Dependency: Python 3.10 EOL Oct 2026", "Decide minimum version before launch"),
    ("Investigations", None, "Dependency: faster-whisper/ctranslate2 health check", "HIGH risk dependency, monitor"),

    # GitHub issues to close (reminders in Legacy Backlog)
    ("Legacy Backlog", None, "Close obsolete issue #29", "Reactive UI architecture (superseded by React migration, complete)"),
    ("Legacy Backlog", None, "Close obsolete issue #16", "Refactor render_html.py (done in 0.13.2)"),
    ("Legacy Backlog", None, "Close obsolete issues #7, #8, #9, #10, #22, #23", "Vanilla JS improvements (frozen/deprecated path)"),
]


def gh_graphql(query: str, retries: int = 3) -> dict:
    """Run a GraphQL query via gh CLI with retry."""
    for attempt in range(retries):
        result = subprocess.run(
            ["gh", "api", "graphql", "-f", f"query={query}"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if "errors" in data:
                print(f"  GraphQL error: {data['errors']}", file=sys.stderr)
                if attempt < retries - 1:
                    time.sleep(1)
                    continue
            return data
        else:
            print(f"  gh error: {result.stderr}", file=sys.stderr)
            if attempt < retries - 1:
                time.sleep(1)
    return {"errors": ["max retries exceeded"]}


def create_or_get_field(name: str, options: list[str]) -> tuple[str, dict[str, str]]:
    """Create a single-select field (or fetch if it exists). Returns (field_id, {name: id})."""
    options_str = ", ".join(
        f'{{name: "{o}", description: "", color: GRAY}}' for o in options
    )
    query = f'''
    mutation {{
      createProjectV2Field(input: {{
        projectId: "{PROJECT_ID}"
        dataType: SINGLE_SELECT
        name: "{name}"
        singleSelectOptions: [{options_str}]
      }}) {{
        projectV2Field {{
          ... on ProjectV2SingleSelectField {{
            id
            options {{ id name }}
          }}
        }}
      }}
    }}
    '''
    result = gh_graphql(query)
    if result.get("data") and result["data"].get("createProjectV2Field"):
        field = result["data"]["createProjectV2Field"]["projectV2Field"]
        return field["id"], {o["name"]: o["id"] for o in field["options"]}

    # Field already exists — fetch it
    print(f"  {name} field may already exist, querying...")
    query = f'''
    {{
      node(id: "{PROJECT_ID}") {{
        ... on ProjectV2 {{
          field(name: "{name}") {{
            ... on ProjectV2SingleSelectField {{
              id
              options {{ id name }}
            }}
          }}
        }}
      }}
    }}
    '''
    result = gh_graphql(query)
    field = result["data"]["node"]["field"]
    return field["id"], {o["name"]: o["id"] for o in field["options"]}


def set_field(item_id: str, field_id: str, option_id: str):
    """Set a single-select field value on a project item."""
    query = f'''
    mutation {{
      updateProjectV2ItemFieldValue(input: {{
        projectId: "{PROJECT_ID}"
        itemId: "{item_id}"
        fieldId: "{field_id}"
        value: {{singleSelectOptionId: "{option_id}"}}
      }}) {{
        projectV2Item {{ id }}
      }}
    }}
    '''
    return gh_graphql(query)


def main():
    # ── Step 1: Update Status field (add Legacy Backlog, keep Todo/In Progress/Done) ──
    print("Step 1: Updating Status field options...")
    options_str = ", ".join(
        f'{{name: "{s}", description: "", color: GRAY}}' for s in STATUSES
    )
    query = f'''
    mutation {{
      updateProjectV2Field(input: {{
        fieldId: "{STATUS_FIELD_ID}"
        singleSelectOptions: [{options_str}]
      }}) {{
        projectV2Field {{
          ... on ProjectV2SingleSelectField {{
            options {{ id name }}
          }}
        }}
      }}
    }}
    '''
    result = gh_graphql(query)
    if result.get("data") is None:
        print(f"  FAILED to update status field: {result}", file=sys.stderr)
        sys.exit(1)

    status_options = result["data"]["updateProjectV2Field"]["projectV2Field"]["options"]
    status_map = {opt["name"]: opt["id"] for opt in status_options}
    print(f"  Status options: {list(status_map.keys())}")

    # ── Step 2: Create Kind field ──
    print("\nStep 2: Creating Kind field...")
    kind_field_id, kind_map = create_or_get_field("Kind", KINDS)
    print(f"  Kind field ID: {kind_field_id}")
    print(f"  Kind options: {list(kind_map.keys())}")

    # ── Step 3: Create Priority field ──
    print("\nStep 3: Creating Priority field...")
    priority_field_id, priority_map = create_or_get_field("Priority", PRIORITIES)
    print(f"  Priority field ID: {priority_field_id}")
    print(f"  Priority options: {list(priority_map.keys())}")

    # ── Step 4: Move existing items to Legacy Backlog ──
    print("\nStep 4: Moving existing items to Legacy Backlog...")
    query = f'''
    {{
      node(id: "{PROJECT_ID}") {{
        ... on ProjectV2 {{
          items(first: 100) {{
            nodes {{
              id
              content {{
                ... on DraftIssue {{ title }}
                ... on Issue {{ title number }}
                ... on PullRequest {{ title number }}
              }}
            }}
          }}
        }}
      }}
    }}
    '''
    result = gh_graphql(query)
    existing_items = result["data"]["node"]["items"]["nodes"]
    legacy_id = status_map["Legacy Backlog"]

    for item in existing_items:
        title = item["content"].get("title", "unknown")
        set_field(item["id"], STATUS_FIELD_ID, legacy_id)
        print(f"  OK: {title}")
        time.sleep(0.3)

    # ── Step 5: Create new draft items ──
    print(f"\nStep 5: Creating {len(ITEMS)} draft items...")
    todo_id = status_map["Todo"]

    for i, (kind, priority, title, body) in enumerate(ITEMS):
        safe_title = title.replace('"', '\\"').replace("\n", " ")
        safe_body = body.replace('"', '\\"').replace("\n", " ")

        query = f'''
        mutation {{
          addProjectV2DraftIssue(input: {{
            projectId: "{PROJECT_ID}"
            title: "{safe_title}"
            body: "{safe_body}"
          }}) {{
            projectItem {{ id }}
          }}
        }}
        '''
        result = gh_graphql(query)
        if result.get("data") is None:
            print(f"  FAIL [{i+1}/{len(ITEMS)}]: {title} - {result.get('errors')}")
            continue

        item_id = result["data"]["addProjectV2DraftIssue"]["projectItem"]["id"]

        # Set Status = Todo (or Legacy Backlog for the close-issue reminders)
        if kind == "Legacy Backlog":
            set_field(item_id, STATUS_FIELD_ID, legacy_id)
        else:
            set_field(item_id, STATUS_FIELD_ID, todo_id)

        # Set Kind
        kind_option_id = kind_map.get(kind)
        if kind_option_id:
            set_field(item_id, kind_field_id, kind_option_id)

        # Set Priority
        if priority and priority in priority_map:
            set_field(item_id, priority_field_id, priority_map[priority])

        print(f"  OK [{i+1}/{len(ITEMS)}]: {title} -> Kind={kind} / Priority={priority or '-'}")
        time.sleep(0.3)

    print(f"\nDone! {len(ITEMS)} items created, {len(existing_items)} existing items -> Legacy Backlog.")
    print("View at: https://github.com/users/cassiocassio/projects/1")


if __name__ == "__main__":
    main()
