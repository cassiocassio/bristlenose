import SwiftUI

/// Settings tab for appearance and language preferences.
///
/// Appearance choice is injected into the embedded web app via bridge
/// (native wins — web Settings modal hides its own appearance picker
/// in embedded mode).
struct AppearanceSettingsView: View {

    @EnvironmentObject var i18n: I18n
    @AppStorage("appearance") private var appearance: String = "auto"
    @AppStorage("typography") private var typography: String = "sf"
    @AppStorage("language") private var language: String = "en"
    @AppStorage(RandomProjectIcon.defaultsKey) private var randomProjectIcons: Bool = true

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
                Toggle(i18n.t("settings.appearance.randomIconsLegend"), isOn: $randomProjectIcons)
                Text(i18n.t("settings.appearance.randomIconsHelp"))
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }

            Section {
                // Language names are always in their own language (autonyms),
                // not translated — a Spanish speaker needs to recognise "Español"
                // even when the UI is currently in Japanese.
                Picker(i18n.t("settings.language.legend"), selection: $language) {
                    Text("English").tag("en")
                    Text("Español").tag("es")
                    Text("日本語").tag("ja")
                    Text("Français").tag("fr")
                    Text("Deutsch").tag("de")
                    Text("한국어").tag("ko")
                    Text("Čeština").tag("cs")
                    Text("Italiano").tag("it")
                    Text("Português (Brasil)").tag("pt-BR")
                    Text("Português (Portugal)").tag("pt-PT")
                    Text("繁體中文").tag("zh-Hant")
                    Text("繁體中文（香港）").tag("zh-Hant-HK")
                }

                HStack(spacing: 4) {
                    Text(i18n.t("settings.language.helpTranslate"))
                        .font(.callout)
                        .foregroundStyle(.secondary)
                    Link("Weblate", destination: URL(string: "https://hosted.weblate.org/projects/bristlenose/")!)
                        .font(.callout)
                }
            }
        }
        .formStyle(.grouped)
        .frame(width: 660)
        .onChange(of: appearance) { _, _ in
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
        }
        .onChange(of: typography) { _, _ in
            // The server renders data-typography onto <html> from
            // BRISTLENOSE_TYPOGRAPHY at sidecar start, so the change lands on
            // restart — same mechanism (and same prefs notification) as the
            // appearance and language settings in this tab.
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
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
