import Settings

// A collision-free handle on the package's `Settings` namespace enum.
//
// Sindre Sorhus's package declares a top-level `enum Settings`, and SwiftUI
// declares a top-level `struct Settings` (the scene). Any file that imports
// BOTH sees `Settings` as ambiguous, so `Settings.Pane` / `Settings.PaneIdentifier`
// won't compile there (and module-qualifying as `Settings.Settings` stays
// ambiguous on the leading `Settings`).
//
// This file deliberately does NOT `import SwiftUI`, so `Settings` resolves
// unambiguously to the package's enum. The resulting `PkgSettings` alias is a
// distinct name every other file can use freely — including SettingsView.swift,
// which needs SwiftUI for its panes.
typealias PkgSettings = Settings
