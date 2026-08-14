import SwiftUI

/// Settings tab for appearance and language preferences.
///
/// Appearance choice is injected into the embedded web app via bridge
/// (native wins — web Settings modal hides its own appearance picker
/// in embedded mode).
struct AppearanceSettingsView: View {

    @EnvironmentObject var i18n: I18n
    @AppStorage("appearance") private var appearance: String = "auto"
    @AppStorage("palette") private var palette: String = "default"
    @AppStorage("typography") private var typography: String = "sf"
    @AppStorage("language") private var language: String = "en"
    @AppStorage(RandomProjectIcon.defaultsKey) private var randomProjectIcons: Bool = true
    @AppStorage("showAnalysisAnimation") private var showAnalysisAnimation: Bool = true
    @AppStorage(DiagnosticsPreference.key)
    private var showDiagnosticsMenu: Bool = DiagnosticsPreference.defaultValue

    var body: some View {
        Form {
            Section {
                Picker(i18n.t("settings.appearance.legend"), selection: $appearance) {
                    Text(i18n.t("settings.appearance.auto")).tag("auto")
                    Text(i18n.t("settings.appearance.light")).tag("light")
                    Text(i18n.t("settings.appearance.dark")).tag("dark")
                }
                .pickerStyle(.radioGroup)
            }

            Section {
                // Colour palette — the two colour axes (appearance = light/dark,
                // palette = colour set) sit together, above Typography (font).
                // Bare label like Typography (the audience knows the term); a
                // pop-up menu (the default Picker style in a Form), not radios,
                // since the set will grow. Options mirror the frontend PALETTES
                // list (default/edo) — keep both in sync when a palette lands.
                Picker(i18n.t("settings.palette.legend"), selection: $palette) {
                    Text(i18n.t("settings.palette.default")).tag("default")
                    Text(i18n.t("settings.palette.edo")).tag("edo")
                }
            }

            Section {
                // Font names are brand names, shown as-is (like the language
                // autonyms below) — not translated. SF Pro is the native macOS
                // type system; Inter matches the web report. Desktop only — the
                // web app is always Inter (SF Pro is Apple-licensed).
                Picker(i18n.t("settings.typography.legend"), selection: $typography) {
                    Text("SF Pro").tag("sf")
                    Text("Inter").tag("inter")
                }
            }

            Section {
                // Language sits directly under Typography — the three "how it
                // reads" axes (colour, font, language) grouped together, above
                // the behaviour toggles below.
                //
                // Language names are always in their own language (autonyms),
                // not translated — a Spanish speaker needs to recognise "Español"
                // even when the UI is currently in Japanese.
                Picker(i18n.t("settings.language.legend"), selection: $language) {
                    Text("English").tag("en")
                    Text("Español").tag("es")
                    Text("Català").tag("ca")
                    Text("日本語").tag("ja")
                    Text("Français").tag("fr")
                    Text("Deutsch").tag("de")
                    Text("한국어").tag("ko")
                    Text("Čeština").tag("cs")
                    Text("Italiano").tag("it")
                    Text("Polski").tag("pl")
                    Text("Русский").tag("ru")
                    Text("Українська").tag("uk")
                    Text("Dansk").tag("da")
                    Text("Svenska").tag("sv")
                    Text("Norsk bokmål").tag("nb")
                    Text("Türkçe").tag("tr")
                    Text("Nederlands").tag("nl")
                    Text("Suomi").tag("fi")
                    Text("Português (Brasil)").tag("pt-BR")
                    Text("Português (Portugal)").tag("pt-PT")
                    Text("繁體中文").tag("zh-Hant")
                    Text("繁體中文（香港）").tag("zh-Hant-HK")
                }
            } footer: {
                // A group footnote (below the box, no in-cell keyline) — an
                // invitation to contribute, not a description of the picker.
                HStack(spacing: 4) {
                    Text(i18n.t("settings.language.helpTranslate"))
                    Link("Weblate", destination: URL(string: "https://hosted.weblate.org/projects/bristlenose/")!)
                }
            }

            Section {
                // Help text as an in-cell subtitle (title + secondary Text in
                // the control's label) — the System Settings idiom (cf. Stage
                // Manager's description), which drops the row keyline the old
                // separate-Text-row layout drew.
                Toggle(isOn: $randomProjectIcons) {
                    Text(i18n.t("settings.appearance.randomIconsLegend"))
                    Text(i18n.t("settings.appearance.randomIconsHelp"))
                        .foregroundStyle(.secondary)
                }
            }

            Section {
                Toggle(isOn: $showAnalysisAnimation) {
                    Text(i18n.t("settings.appearance.animationLegend"))
                    Text(i18n.t("settings.appearance.animationHelp"))
                        .foregroundStyle(.secondary)
                }
            }

            Section {
                // Tier-U diagnostics gate (docs/design-diagnostics-menu.md).
                // The helper text is where the Web Inspector side-effect is
                // disclosed — it's not a menu item (no public API to open a
                // hosted WKWebView's inspector; users right-click ▸ Inspect
                // Element once enabled).
                Toggle(isOn: $showDiagnosticsMenu) {
                    Text(i18n.t("settings.appearance.diagnosticsLegend"))
                    Text(i18n.t("settings.appearance.diagnosticsHelp"))
                        .foregroundStyle(.secondary)
                }
            }
        }
        .formStyle(.grouped)
        .frame(width: 660)
        // NB: appearance deliberately has NO .onChange here. It reaches the web
        // report through the platform, not through us: AppAppearance's KVO sets
        // NSApp.appearance, the WKWebView inherits its window's effective
        // appearance, and the report CSS follows prefers-color-scheme. Nothing
        // in BristlenoseShared.childEnvironment reads this pref, so a
        // .bristlenosePrefsChanged post here bought a serve restart that served
        // byte-identical HTML — and, because the restart takes a fresh bind(0)
        // port, it changed the detail WebView's .id and cold-remounted the SPA
        // (route, scroll, panels, focus all lost) on every light↔dark switch.
        // The control experiment: on "auto", flipping the SYSTEM theme posts
        // nothing, restarts nothing, and re-themes the report anyway.
        .onChange(of: typography) { _, _ in
            // The server renders data-typography onto <html> from
            // BRISTLENOSE_TYPOGRAPHY at sidecar start, so the change lands on
            // restart — same mechanism (and same prefs notification) as the
            // language setting below. Appearance does NOT belong in this
            // company: it produces no env var, so it needs no restart.
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
        }
        .onChange(of: palette) { _, _ in
            // Live, NOT a restart (deliberately not .bristlenosePrefsChanged):
            // post .bristlenosePaletteChanged, which ContentView forwards to the
            // web layer via bridgeHandler.setColorPalette() — a runtime
            // data-color-theme CSS swap. The @AppStorage value is also the
            // cold-start seed (BRISTLENOSE_PALETTE) for the next serve start.
            NotificationCenter.default.post(name: .bristlenosePaletteChanged, object: nil)
        }
        .onChange(of: language) { _, newValue in
            i18n.setLocale(newValue)
            // VoiceOver language for web content is set via the bridge
            // (syncLocale → HTML lang attribute). Native SwiftUI elements
            // inherit the system language — no per-window override needed.
            // Restart serve to update BRISTLENOSE_WHISPER_LANGUAGE
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
        }
    }
}
