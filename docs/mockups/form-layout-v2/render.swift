// Renders the Send to Miro and Send to FigJam sheets as real AppKit pixels for
// docs/mockups/form-layout-v2.html: BEFORE is each sheet's shipped modifier chain, copied from
// MiroSheet.swift and FigJamSheet.swift (19 Nov 2026); AFTER is the proposal. Strings are read
// from bristlenose/locales; the few proposed strings are written in PROPOSED below.
//
// Run (from the repo root):  docs/mockups/form-layout-v2/render.sh
// It must run as an app bundle so the window becomes key: an inactive window draws the default
// button and the checked controls grey, which is not what a researcher sees.

import AppKit
import SwiftUI

let ROOT = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : FileManager.default.currentDirectoryPath
let OUT = ROOT + "/docs/mockups/form-layout-v2"

// MARK: strings

struct L10n {
    let lang: String
    let bundles: [String: Any]
    let en: [String: Any]

    init(_ lang: String) {
        self.lang = lang
        func load(_ l: String) -> [String: Any] {
            var out: [String: Any] = [:]
            for ns in ["common", "desktop"] {
                let url = URL(fileURLWithPath: "\(ROOT)/bristlenose/locales/\(l)/\(ns).json")
                out[ns] = (try? JSONSerialization.jsonObject(with: Data(contentsOf: url))) ?? [:]
            }
            return out
        }
        bundles = load(lang)
        en = load("en")
    }

    private func look(_ root: [String: Any], _ key: String) -> String? {
        var node: Any = root
        for part in key.split(separator: ".") {
            guard let d = node as? [String: Any], let next = d[String(part)] else { return nil }
            node = next
        }
        return node as? String
    }

    /// "common.miro.title", falling back to English, then to the key (never silently).
    func t(_ key: String, _ vars: [String: String] = [:]) -> String {
        fill(look(bundles, key) ?? look(en, key) ?? "⟦\(key)⟧", vars)
    }

    func fill(_ s: String, _ vars: [String: String]) -> String {
        var s = s
        for (k, v) in vars { s = s.replacingOccurrences(of: "{{\(k)}}", with: v) }
        return s
    }

    /// The proposal's string when one is written, else the shipped one.
    func after(_ key: String, _ vars: [String: String] = [:]) -> String {
        if let p = AFTER_STRINGS[lang]?[key] { return fill(p, vars) }
        return t(key, vars)
    }
}

// AFTER-only strings. English is owner-to-approve copy; de is drafted only so the German frames
// measure a realistic length, and is flagged as such on the page.
let AFTER_STRINGS: [String: [String: String]] = [
    "en": [
        // Item 2: one casing for Mac buttons (title case), and the segments with them.
        "desktop.miro.copyBoard": "Copy Board Data",
        "desktop.miro.createBoard": "Create Board",
        "desktop.miro.tabApp": "Miro App",
        "desktop.miro.tabToken": "Developer Access Token",
        // Item 5: no em dash, no "we".
        "common.miro.uploadNotice": "Uploads all quotes in this project to Miro. Hidden quotes are excluded.",
        "common.miro.connectIntro": "Push your quotes onto a new Miro board as sticky notes, grouped by section and theme. Connect once. Bristlenose never changes your existing boards.",
        "common.miro.boardReady_other": "Board ready. {{count}} quote stickies placed.",
    ],
    "de": [
        "desktop.miro.copyBoard": "Board-Daten kopieren",
        "desktop.miro.createBoard": "Board erstellen",
        "desktop.miro.tabApp": "Miro-App",
        "desktop.miro.tabToken": "Entwickler-Zugriffstoken",
        "common.miro.uploadNotice": "Lädt alle Zitate dieses Projekts zu Miro hoch. Ausgeblendete Zitate werden nicht übertragen.",
    ],
]

let SAMPLE_PROJECT = "Talismanic"
let SAMPLE_TEAM = "Dev team"
let SAMPLE_ACCOUNT = "Sam Taylor · Dev team"
let SAMPLE_COUNT = "29"

// MARK: shared pieces

struct Sheet<Content: View>: View {
    @ViewBuilder var content: Content
    var body: some View {
        content
            .padding(20)
            .frame(width: 460)
            .frame(minHeight: 400)
    }
}

/// SwiftUI's Picker(.segmented) needs a binding; a constant is enough to draw it.
func seg(_ l: L10n, after: Bool, selected: Int) -> some View {
    let app = after ? l.after("desktop.miro.tabApp") : l.t("common.miro.tabApp")
    let tok = after ? l.after("desktop.miro.tabToken") : l.t("common.miro.tabToken")
    return Picker(l.t("common.miro.quotesTitle"), selection: .constant(selected)) {
        Text(app).tag(0)
        Text(tok).tag(1)
    }
    .pickerStyle(.segmented)
    .labelsHidden()
    .fixedSize()
    .frame(maxWidth: .infinity, alignment: .center)
}

func header(_ l: L10n, after: Bool, selected: Int) -> some View {
    VStack(spacing: 12) {
        Text(l.t("common.miro.quotesTitle")).font(.headline)
            .frame(maxWidth: .infinity, alignment: .center)
        seg(l, after: after, selected: selected)
    }
}

func shapePicker(_ l: L10n, first: String) -> some View {
    Picker(l.t("common.miro.stickyShape"), selection: .constant(first)) {
        if first == "rectangle" {
            Text(l.t("common.miro.stickyShapeRectangle")).tag("rectangle")
            Text(l.t("common.miro.stickyShapeSquare")).tag("square")
        } else {
            Text(l.t("common.miro.stickyShapeSquare")).tag("square")
            Text(l.t("common.miro.stickyShapeRectangle")).tag("rectangle")
        }
    }
    .pickerStyle(.radioGroup)
    .horizontalRadioGroupLayout()
    .labelsHidden()
}

func pairLabel(_ titles: [String], shown: String) -> some View {
    ZStack {
        ForEach(titles, id: \.self) { title in
            Text(title).opacity(title == shown ? 1 : 0)
        }
    }
}

// MARK: Miro, app route (MiroSheet.appRoute)

struct MiroApp: View {
    let l: L10n
    let after: Bool
    var body: some View {
        let save = l.t("desktop.figjam.saveBoardFile")
        let copy = after ? l.after("desktop.miro.copyBoard") : l.t("common.miro.copyBoard")
        let copied = l.t("common.miro.copied")
        let link = l.t("common.miro.appAddLink").replacingOccurrences(of: "↗", with: "").trimmingCharacters(in: .whitespaces)
        Sheet {
            VStack(alignment: .leading, spacing: 12) {
                header(l, after: after, selected: 0)
                VStack(alignment: .leading, spacing: 12) {
                    Grid(alignment: .leading, horizontalSpacing: 8, verticalSpacing: 12) {
                        GridRow(alignment: .firstTextBaseline) {
                            Color.clear.gridCellUnsizedAxes([.horizontal, .vertical])
                                .gridColumnAlignment(.trailing)
                            Toggle(isOn: .constant(true)) {
                                Text(l.t("common.miro.splitLongQuotes")).fixedSize(horizontal: false, vertical: true)
                            }
                        }
                        GridRow(alignment: .firstTextBaseline) {
                            Text(l.t("common.miro.stickyShapeLabel"))
                            shapePicker(l, first: "rectangle")
                        }
                        Divider()
                        GridRow(alignment: .firstTextBaseline) {
                            Text(l.t("common.miro.appOnce"))
                            Link(link, destination: URL(string: "https://miro.com")!)
                        }
                        GridRow(alignment: .firstTextBaseline) {
                            Text(l.t("common.miro.appEither"))
                            Button {} label: { pairLabel([save, copy, copied], shown: save) }
                        }
                        GridRow(alignment: .firstTextBaseline) {
                            Text(l.t("common.miro.appOr"))
                            Button {} label: { pairLabel([save, copy, copied], shown: copy) }
                                .keyboardShortcut(.defaultAction)
                        }
                        GridRow(alignment: .top) {
                            Text(l.t("common.miro.appThen"))
                            Text(l.t("common.miro.appStep3")).fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    Spacer(minLength: 16)
                    HStack {
                        HelpLink {}
                        Spacer()
                        Button(l.t("common.miro.done")) {}.keyboardShortcut(.cancelAction)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }
}

// MARK: Miro, token route, connect step (MiroSheet.connect)

struct MiroConnect: View {
    let l: L10n
    let after: Bool
    var body: some View {
        Sheet {
            VStack(alignment: .leading, spacing: 12) {
                header(l, after: after, selected: 1)
                VStack(alignment: .leading, spacing: 12) {
                    Text(after ? l.after("common.miro.connectIntro") : l.t("common.miro.connectIntro"))
                        .font(.callout).foregroundStyle(.secondary)
                    SecureField(l.t("common.miro.tokenPlaceholder"), text: .constant(""))
                        .textFieldStyle(.roundedBorder)
                    Spacer(minLength: 16)
                    HStack {
                        HelpLink {}
                        Spacer()
                        Button(l.t("common.miro.cancel")) {}.keyboardShortcut(.cancelAction)
                        Button(l.t("common.miro.connect")) {}.keyboardShortcut(.defaultAction).disabled(true)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }
}

// MARK: Miro, token route, configure step (MiroSheet.configure)

struct MiroConfigure: View {
    let l: L10n
    let after: Bool
    /// AFTER only. 0: colours stacked, shape side by side (the proposal). 1: both stacked.
    /// 2: both side by side (drawn to show the truncation).
    var layout: Int = 0

    func notice() -> Text {
        let template = l.t("desktop.miro.boardDestination")
        let upload = after ? l.after("common.miro.uploadNotice") : l.t("common.miro.uploadNotice")
        let parts = template.components(separatedBy: "{{team}}")
        return Text(parts[0]) + Text(SAMPLE_TEAM).bold() + Text((parts.count > 1 ? parts[1] : "") + " " + upload)
    }

    var body: some View {
        Sheet {
            VStack(alignment: .leading, spacing: 12) {
                header(l, after: after, selected: 1)
                VStack(alignment: .leading, spacing: 12) {
                    Grid(alignment: .leading, horizontalSpacing: 8, verticalSpacing: 12) {
                        GridRow(alignment: .firstTextBaseline) {
                            Text(l.t("desktop.miro.miroStatusLabel")).gridColumnAlignment(.trailing)
                            HStack(spacing: 6) {
                                Image(systemName: "checkmark.circle").foregroundStyle(.green)
                                Text(l.t("desktop.miro.connected"))
                                Spacer()
                                Button(l.t("common.miro.disconnect")) {}.controlSize(.small)
                            }
                        }
                        GridRow(alignment: .firstTextBaseline) {
                            Text(l.t("desktop.miro.accountLabel"))
                            Text(SAMPLE_ACCOUNT)
                        }
                        GridRow(alignment: .firstTextBaseline) {
                            Text(l.t("desktop.miro.boardNameLabel"))
                            TextField(l.t("common.miro.boardNamePlaceholder"), text: .constant(SAMPLE_PROJECT))
                                .textFieldStyle(.roundedBorder)
                        }
                        if after {
                            // Q1: radios, both states named. Then shape, then the checkbox under it (item 12).
                            GridRow(alignment: .firstTextBaseline) {
                                Text(l.t("desktop.miro.stickyColoursLabel"))
                                Picker(l.t("desktop.miro.stickyColoursLabel"), selection: .constant("none")) {
                                    Text(l.t("common.miro.colourByNone")).tag("none")
                                    Text(l.t("common.miro.colourBySentiment")).tag("sentiment")
                                }
                                .pickerStyle(.radioGroup)
                                .modifier(Horizontal(on: layout == 2))
                                .labelsHidden()
                            }
                            GridRow(alignment: .firstTextBaseline) {
                                Text(l.t("common.miro.stickyShapeLabel"))
                                if layout == 1 {
                                    Picker(l.t("common.miro.stickyShape"), selection: .constant("rectangle")) {
                                        Text(l.t("common.miro.stickyShapeRectangle")).tag("rectangle")
                                        Text(l.t("common.miro.stickyShapeSquare")).tag("square")
                                    }
                                    .pickerStyle(.radioGroup).labelsHidden()
                                } else {
                                    shapePicker(l, first: "rectangle")
                                }
                            }
                            GridRow(alignment: .firstTextBaseline) {
                                Color.clear.gridCellUnsizedAxes([.horizontal, .vertical])
                                Toggle(isOn: .constant(true)) {
                                    Text(l.t("common.miro.splitLongQuotes")).fixedSize(horizontal: false, vertical: true)
                                }
                            }
                        } else {
                            GridRow(alignment: .firstTextBaseline) {
                                Text(l.t("desktop.miro.stickyColoursLabel"))
                                Toggle(l.t("common.miro.colourBySentiment"), isOn: .constant(false))
                            }
                            GridRow(alignment: .firstTextBaseline) {
                                Color.clear.gridCellUnsizedAxes([.horizontal, .vertical])
                                Toggle(isOn: .constant(true)) {
                                    Text(l.t("common.miro.splitLongQuotes")).fixedSize(horizontal: false, vertical: true)
                                }
                            }
                            GridRow(alignment: .firstTextBaseline) {
                                Text(l.t("common.miro.stickyShapeLabel"))
                                shapePicker(l, first: "rectangle")
                            }
                        }
                    }
                    notice().font(.subheadline).foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    Spacer(minLength: 16)
                    HStack {
                        HelpLink {}
                        Spacer()
                        Button(l.t("common.miro.cancel")) {}.keyboardShortcut(.cancelAction)
                        Button(after ? l.after("desktop.miro.createBoard") : l.t("common.miro.createBoard")) {}
                            .keyboardShortcut(.defaultAction)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }
}

struct Horizontal: ViewModifier {
    let on: Bool
    func body(content: Content) -> some View {
        if on { content.horizontalRadioGroupLayout() } else { content }
    }
}

// MARK: Miro, done (MiroSheet.done)

struct MiroDone: View {
    let l: L10n
    let after: Bool
    var body: some View {
        let text = after ? l.after("common.miro.boardReady_other", ["count": SAMPLE_COUNT])
                         : l.t("common.miro.boardReady_other", ["count": SAMPLE_COUNT])
        Sheet {
            VStack(spacing: 12) {
                Spacer()
                Image(systemName: "checkmark.circle").font(.system(size: 34)).foregroundStyle(.green)
                Text(text).font(.headline).fontWeight(.regular).multilineTextAlignment(.center)
                Spacer()
                HStack {
                    Spacer()
                    Button(l.t("common.miro.done")) {}.keyboardShortcut(.cancelAction)
                    Button(l.t("desktop.miro.openInMiro")) {}.keyboardShortcut(.defaultAction)
                }
            }
            .frame(maxWidth: .infinity)
        }
    }
}

// MARK: FigJam (FigJamSheet.configure)

struct FigJam: View {
    let l: L10n
    let after: Bool
    var body: some View {
        Sheet {
            VStack(alignment: .leading, spacing: 12) {
                Text(l.t("common.figjam.title")).font(.headline)
                    .frame(maxWidth: .infinity, alignment: .center)
                Text(l.t("common.figjam.intro")).font(.callout).foregroundStyle(.secondary)
                Grid(alignment: .leading, horizontalSpacing: 8, verticalSpacing: 12) {
                    GridRow(alignment: .firstTextBaseline) {
                        Text(l.t("desktop.miro.boardNameLabel"))
                            .foregroundStyle(after ? .primary : .secondary)
                            .gridColumnAlignment(.trailing)
                        // AFTER names the field for VoiceOver (item 3); the pixels do not change.
                        TextField(after ? l.t("desktop.miro.boardNameLabel") : "", text: .constant(SAMPLE_PROJECT))
                            .textFieldStyle(.roundedBorder)
                            .labelsHidden()
                    }
                    GridRow(alignment: .firstTextBaseline) {
                        Text(l.t("desktop.figjam.stickyShapeLabel"))
                            .foregroundStyle(after ? .primary : .secondary)
                        shapePicker(l, first: "square")
                    }
                    GridRow(alignment: .firstTextBaseline) {
                        Color.clear.gridCellUnsizedAxes([.horizontal, .vertical])
                        if after {
                            Toggle(isOn: .constant(true)) {
                                Text(l.t("common.miro.splitLongQuotes")).fixedSize(horizontal: false, vertical: true)
                            }
                        } else {
                            Toggle(l.t("common.miro.splitLongQuotes"), isOn: .constant(true))
                        }
                    }
                }
                Text(l.t("common.figjam.notice")).font(.subheadline).foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                Spacer(minLength: 16)
                HStack {
                    Spacer()
                    Button(l.t("common.miro.cancel")) {}.keyboardShortcut(.cancelAction)
                    Button(l.t("desktop.figjam.saveBoardFile")) {}.keyboardShortcut(.defaultAction)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

// MARK: rendering

final class KeyWin: NSWindow {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }
}

struct Scene { let name: String; let lang: String; let dark: Bool; let view: AnyView }

func scenes() -> [Scene] {
    var out: [Scene] = []
    func add(_ name: String, _ lang: String, dark: [Bool] = [false], _ make: (L10n) -> AnyView) {
        let l = L10n(lang)
        for d in dark { out.append(Scene(name: "\(name)-\(lang)-\(d ? "dark" : "light")", lang: lang, dark: d, view: make(l))) }
    }
    for after in [false, true] {
        let tag = after ? "after" : "before"
        add("miro-app-\(tag)", "en", dark: [false, true]) { AnyView(MiroApp(l: $0, after: after)) }
        add("miro-app-\(tag)", "de") { AnyView(MiroApp(l: $0, after: after)) }
        add("miro-connect-\(tag)", "en") { AnyView(MiroConnect(l: $0, after: after)) }
        add("miro-configure-\(tag)", "en", dark: [false, true]) { AnyView(MiroConfigure(l: $0, after: after)) }
        add("miro-configure-\(tag)", "de") { AnyView(MiroConfigure(l: $0, after: after)) }
        if after {
            for (name, layout) in [("miro-configure-bothstacked", 1), ("miro-configure-sidebyside", 2)] {
                add(name, "en") { AnyView(MiroConfigure(l: $0, after: true, layout: layout)) }
                add(name, "de") { AnyView(MiroConfigure(l: $0, after: true, layout: layout)) }
            }
        }
        add("miro-done-\(tag)", "en") { AnyView(MiroDone(l: $0, after: after)) }
        add("figjam-\(tag)", "en", dark: [false, true]) { AnyView(FigJam(l: $0, after: after)) }
        add("figjam-\(tag)", "de") { AnyView(FigJam(l: $0, after: after)) }
        add("figjam-\(tag)", "ca") { AnyView(FigJam(l: $0, after: after)) }
    }
    return out
}

let app = NSApplication.shared
app.setActivationPolicy(.regular)
app.activate(ignoringOtherApps: true)
var manifest: [String] = []
for s in scenes() {
    let root = s.view
        .background(Color(nsColor: .windowBackgroundColor))
        .environment(\.controlActiveState, .key)
        .environment(\.locale, Locale(identifier: s.lang))
    let host = NSHostingView(rootView: root)
    let size = host.fittingSize
    let win = KeyWin(contentRect: NSRect(origin: NSPoint(x: -6000, y: -6000), size: size),
                     styleMask: [.titled], backing: .buffered, defer: false)
    win.appearance = NSAppearance(named: s.dark ? .darkAqua : .aqua)
    win.contentView = host
    host.frame = NSRect(origin: .zero, size: size)
    win.makeKeyAndOrderFront(nil)
    host.layoutSubtreeIfNeeded()
    RunLoop.main.run(until: Date().addingTimeInterval(0.25))
    let rep = host.bitmapImageRepForCachingDisplay(in: host.bounds)!
    host.cacheDisplay(in: host.bounds, to: rep)
    let file = "\(OUT)/\(s.name).png"
    try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: file))
    manifest.append("\(s.name) \(Int(size.width))x\(Int(size.height)) key=\(win.isKeyWindow)")
    win.orderOut(nil)
}
let os = ProcessInfo.processInfo.operatingSystemVersionString
manifest.insert("rendered on macOS \(os), \(Date())", at: 0)
try! manifest.joined(separator: "\n").write(toFile: "\(OUT)/manifest.txt", atomically: true, encoding: .utf8)
exit(0)
