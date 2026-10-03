#if DEBUG
import AppKit
import SwiftUI
import WebKit

/// DEBUG-only Picker Lab — the moderator-identity picker (docs/design-people.md,
/// "UX iteration 3") built twice and shown side by side, so web against native
/// is judged on the real rendering rather than on a mockup of either.
///
/// - **Native half:** stock AppKit in a real `NSPopover` — a segmented control,
///   a `List` with system selection, SF Symbols, a rounded text field. Nothing
///   is approximated; the material, arrow, radius and type are the system's.
/// - **Web half:** `/report/picker-specimen` on the fronted project's sidecar —
///   the shipped classes and the real `PersonBadge`, under the real tokens and
///   `data-platform="desktop"`.
///
/// The badges are the one shared element, and the native half holds no colour
/// for them: the web half measures the real `PersonBadge` and posts the result
/// over the production `search-badge-styles` message (docs/design-search.md
/// §7a), and `BadgeStyleChip` paints exactly those values. If the two halves'
/// badges ever differ, that is a finding about the bridge, not the lab.
///
/// The scenario control drives both halves; inside each, the controls are live.
struct PickerLabView: View {
    @EnvironmentObject private var serveFleet: ServeFleet
    @EnvironmentObject private var i18n: I18n
    @StateObject private var bridge = BridgeHandler()
    @StateObject private var model = PickerLabModel()
    @State private var scenario = "proposed"

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                Picker("Scenario", selection: $scenario) {
                    Text("Opened on a proposed name").tag("proposed")
                    Text("Reopened after confirming").tag("confirmed")
                    Text("Opened on an unknown slot").tag("unknown")
                    Text("Participant slot").tag("participant")
                }
                .fixedSize()
                Spacer()
                Text(bridge.searchBadgeStyles.people.isEmpty
                     ? "Waiting for badge styles from the web half…"
                     : "Native badges: \(bridge.searchBadgeStyles.people.count) styles measured by the web half")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding(10)
            Divider()
            HStack(spacing: 0) {
                nativeHalf
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                Divider()
                webHalf
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .onChange(of: scenario) { _, name in apply(name) }
        .onChange(of: bridge.isReady) { _, ready in if ready { apply(scenario) } }
    }

    private func apply(_ name: String) {
        model.apply(scenario: name)
        guard let webView = bridge.webView else { return }
        Task { @MainActor in
            // Structured argument (security rule 3) — no interpolation into JS.
            _ = try? await webView.callAsyncJavaScript(
                "window.__pickerLab && window.__pickerLab.setScenario(name);",
                arguments: ["name": name], in: nil, contentWorld: .page)
        }
    }

    // MARK: Native half

    private var nativeHalf: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("AppKit · NSPopover").font(.caption).foregroundStyle(.secondary)
                .padding(.bottom, 16)
            PopoverAnchor(model: model, bridge: bridge)
                .fixedSize()
            Spacer()
        }
        .padding(24)
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: Web half

    @ViewBuilder
    private var webHalf: some View {
        if let base = serveFleet.fronted?.serveURL,
           let project = serveFleet.frontedProject,
           let port = URLComponents(url: base, resolvingAgainstBaseURL: false)?.port {
            WebView(
                url: base.appendingPathComponent("picker-specimen"),
                bridgeHandler: bridge,
                session: ServeSession(projectID: project, port: port),
                authToken: serveFleet.fronted?.authToken
            )
            .environmentObject(i18n)
        } else {
            ContentUnavailableView(
                "No serve running",
                systemImage: "bolt.horizontal.circle",
                description: Text("Open a project in the main window first — the web half is the real SPA on that project's sidecar, and it is also what measures the badges the native half draws.")
            )
        }
    }
}

// MARK: - Model

enum PickerRole: String, CaseIterable, Identifiable {
    case moderator, participant, observer
    var id: String { rawValue }
    var label: String { rawValue.capitalized }
    var prefix: String { String(rawValue.prefix(1)) }
    var newPrompt: String { "New \(rawValue)" }
}

struct PickerPerson: Hashable { let code: String; let name: String }

/// The slot's answer: who it is, and whether a person has said yes.
struct PickerAnswer: Equatable { let code: String; let name: String; let confirmed: Bool }

@MainActor
final class PickerLabModel: ObservableObject {
    static let me = "Martin Storey"
    static let meRow = "me"

    @Published var role: PickerRole = .moderator
    @Published var people: [PickerRole: [PickerPerson]] = [
        .moderator: [.init(code: "m1", name: "Martin B Storey"), .init(code: "m2", name: "Kerri Ng")],
        .participant: [.init(code: "p1", name: "Sarah Chen"), .init(code: "p2", name: "Dr Amara Nwosu"),
                       .init(code: "p3", name: "Mary Adeyemi"), .init(code: "p4", name: "Marrian Boateng"),
                       .init(code: "p5", name: "Mary Okafor"), .init(code: "p6", name: "Mickael Hurley")],
        .observer: [.init(code: "o1", name: "Jane Smith")],
    ]
    @Published var answer: PickerAnswer? = .init(code: "m1", name: "Martin B Storey", confirmed: false)
    @Published var selection: String? = "m1"
    @Published var draft = ""
    @Published var isOpen = true

    var rows: [String] {
        (people[role] ?? []).map(\.code) + (role == .participant ? [] : [Self.meRow])
    }

    func apply(scenario: String) {
        switch scenario {
        case "confirmed":
            role = .moderator; answer = .init(code: "m1", name: "Martin B Storey", confirmed: true)
        case "unknown":
            role = .moderator; answer = nil
        case "participant":
            role = .participant; answer = .init(code: "p3", name: "Mary Adeyemi", confirmed: false)
        default:
            role = .moderator; answer = .init(code: "m1", name: "Martin B Storey", confirmed: false)
        }
        selection = answer?.code ?? people[role]?.first?.code
        draft = ""
        isOpen = true
    }

    func setRole(_ r: PickerRole) {
        role = r
        selection = rows.first
    }

    func choose(_ id: String) {
        if id == Self.meRow {
            answer = .init(code: answer?.code ?? "m1", name: Self.me, confirmed: true)
        } else if let p = people[role]?.first(where: { $0.code == id }) {
            answer = .init(code: p.code, name: p.name, confirmed: true)
        }
        isOpen = false
    }

    func create() {
        let name = draft.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else { return }
        let code = "\(role.prefix)\((people[role]?.count ?? 0) + 1)"
        people[role, default: []].append(.init(code: code, name: name))
        answer = .init(code: code, name: name, confirmed: true)
        draft = ""
        isOpen = false
    }

    /// Type-to-jump on code or name, the way a menu does.
    private var typed = ""
    private var typedAt = Date.distantPast
    func jump(_ character: String) {
        let now = Date()
        typed = (now.timeIntervalSince(typedAt) < 0.8 ? typed : "") + character.lowercased()
        typedAt = now
        if let hit = people[role]?.first(where: {
            $0.code.hasPrefix(typed) || $0.name.lowercased().hasPrefix(typed)
        }) {
            selection = hit.code
        }
    }
}

// MARK: - The anchor and its real NSPopover

/// The badge in the grid that opens the picker. The popover is AppKit's own,
/// `.applicationDefined` so it stays up while you look at the web half.
private struct PopoverAnchor: View {
    @ObservedObject var model: PickerLabModel
    @ObservedObject var bridge: BridgeHandler

    var body: some View {
        Button { model.isOpen.toggle() } label: {
            if let a = model.answer {
                BadgeStyleChip(code: a.code, name: a.name, proposed: !a.confirmed,
                               styles: bridge.searchBadgeStyles)
            } else {
                Text(model.role.label).italic().foregroundStyle(.secondary)
            }
        }
        .buttonStyle(.plain)
        .background(PopoverHost(isOpen: model.isOpen) {
            NativePersonPicker(model: model, bridge: bridge)
        })
    }
}

private struct PopoverHost<Content: View>: NSViewRepresentable {
    let isOpen: Bool
    @ViewBuilder let content: () -> Content

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeNSView(context: Context) -> NSView { NSView() }

    func updateNSView(_ view: NSView, context: Context) {
        let popover = context.coordinator.popover
        if popover.contentViewController == nil {
            let host = NSHostingController(rootView: content())
            host.sizingOptions = .preferredContentSize
            popover.contentViewController = host
            popover.behavior = .applicationDefined
        }
        DispatchQueue.main.async {
            if isOpen, !popover.isShown, view.window != nil {
                popover.show(relativeTo: view.bounds, of: view, preferredEdge: .maxY)
            } else if !isOpen, popover.isShown {
                popover.close()
            }
        }
    }

    static func dismantleNSView(_ view: NSView, coordinator: Coordinator) {
        coordinator.popover.close()
    }

    final class Coordinator { let popover = NSPopover() }
}

// MARK: - The picker, in stock controls

private struct NativePersonPicker: View {
    @ObservedObject var model: PickerLabModel
    @ObservedObject var bridge: BridgeHandler

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Picker("Role", selection: Binding(get: { model.role }, set: { model.setRole($0) })) {
                ForEach(PickerRole.allCases) { Text($0.label).tag($0) }
            }
            .pickerStyle(.segmented)
            .labelsHidden()

            List(selection: $model.selection) {
                ForEach(model.people[model.role] ?? [], id: \.code) { p in
                    row(p).tag(p.code)
                }
                if model.role != .participant {
                    Label("That’s Me (\(PickerLabModel.me))", systemImage: "person.crop.circle.badge.checkmark")
                        .padding(.leading, 20)
                        .tag(PickerLabModel.meRow)
                }
            }
            .listStyle(.plain)
            .scrollDisabled(true)
            .frame(height: CGFloat(model.rows.count) * 24 + 4)
            // Return and double-click choose — the native primary action.
            .contextMenu(forSelectionType: String.self, menu: { _ in }) { ids in
                if let id = ids.first { model.choose(id) }
            }
            .onKeyPress(characters: .alphanumerics, phases: .down) { press in
                model.jump(press.characters)
                return .handled
            }

            TextField("", text: $model.draft, prompt: Text(model.role.newPrompt))
                .textFieldStyle(.roundedBorder)
                .onSubmit { model.create() }
        }
        .padding(10)
        .frame(width: 280)
    }

    private func row(_ p: PickerPerson) -> some View {
        let isAnswer = model.answer?.code == p.code && model.answer?.name == p.name
        return HStack(spacing: 4) {
            Image(systemName: "checkmark")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(Color(nsColor: .systemGreen))
                .opacity(isAnswer ? 1 : 0)
                .frame(width: 16)
            BadgeStyleChip(code: p.code, name: p.name,
                           proposed: isAnswer && !(model.answer?.confirmed ?? true),
                           styles: bridge.searchBadgeStyles)
        }
    }
}

// MARK: - A badge painted from measured styles

/// Paints a person badge from the values the SPA measured off the real
/// `PersonBadge` (SearchPersonBadgeStyle). No colour, size or radius here is
/// ours. Before the first measurement arrives it says so rather than guess.
struct BadgeStyleChip: View {
    let code: String
    let name: String
    let proposed: Bool
    let styles: SearchBadgeStyles

    var body: some View {
        if let style = styles.people[code] ?? sameRoleStyle {
            chip(style)
        } else {
            Text("\(code) \(name)").foregroundStyle(.tertiary)
        }
    }

    /// A person created in the native half was never measured by the web
    /// half; any badge of the same role has the same style.
    private var sameRoleStyle: SearchPersonBadgeStyle? {
        styles.people.first(where: { $0.key.first == code.first })?.value
    }

    private func chip(_ s: SearchPersonBadgeStyle) -> some View {
        let radius = s.code.radius
        let outline = s.code.border.map { colour($0.colour) } ?? .clear
        let ring = colour((s.name ?? s.code).text)
        return HStack(spacing: 0) {
            half(code, s.code)
            if let n = s.name { half(name, n) }
        }
        .clipShape(RoundedRectangle(cornerRadius: radius))
        .overlay {
            if proposed {
                // One dotted ring while proposed (design-people.md, iteration 3).
                RoundedRectangle(cornerRadius: radius)
                    .strokeBorder(ring, style: StrokeStyle(lineWidth: 1, dash: [3, 2]))
            } else {
                RoundedRectangle(cornerRadius: radius)
                    .strokeBorder(outline, lineWidth: s.code.border?.width ?? 0)
            }
        }
    }

    private func half(_ text: String, _ s: SearchBadgeStyle) -> some View {
        Text(text)
            .font(Font(font(s)))
            .foregroundStyle(colour(s.text))
            .padding(.horizontal, s.padX)
            .padding(.vertical, s.padY + (s.border?.width ?? 0))
            .background(s.fill.map { colour($0) } ?? .clear)
    }

    private func font(_ s: SearchBadgeStyle) -> NSFont {
        // CSS weight → AppKit's -1…1 scale: 400 is regular (0), 500 medium (0.23).
        let w = NSFont.Weight(rawValue: CGFloat((s.weight - 400) / 100 * 0.23))
        return s.family == .mono
            ? NSFont.monospacedSystemFont(ofSize: CGFloat(s.size), weight: w)
            : NSFont.systemFont(ofSize: CGFloat(s.size), weight: w)
    }

    private func colour(_ c: BadgeColour) -> Color {
        Color(.displayP3, red: c.red, green: c.green, blue: c.blue, opacity: c.opacity)
    }
}
#endif
