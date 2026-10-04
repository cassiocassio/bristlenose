#if DEBUG
import AppKit
import SwiftUI
import WebKit

/// DEBUG-only Picker Lab — the moderator-identity picker (docs/design-people.md,
/// "UX iteration 3") as both channels ship it, side by side, so web against
/// native is judged on the real rendering rather than on a mockup of either.
///
/// - **Native half:** the production `PersonPickerView` (PersonPickerPopover.swift)
///   in a real `NSPopover` — the owner's hybrid: a Mac pull-down menu in
///   everything but its container (the menu font, a 24 pt row measured from
///   `NSMenu`, the menu's own checkmark, the source-list capsule) with the
///   person drawn as the house native badge, `SpeakerBadgeView`. Regular and
///   Small follow the two pull-down sizes; the app ships Small.
/// - **Web half:** `/report/picker-specimen` on the fronted project's sidecar —
///   the production `PersonPicker` under the real tokens and
///   `data-platform="desktop"`.
///
/// The scenario control drives both halves; inside each, the controls are live.
/// The web half takes its scenario from the URL (`?scenario=`), so a reload or
/// a project switch cannot leave the halves showing different things; Reset
/// starts both again from the chosen scenario. The lab's strings are English:
/// in the app the native picker's come localised from the SPA.
struct PickerLabView: View {
    @EnvironmentObject private var serveFleet: ServeFleet
    @EnvironmentObject private var i18n: I18n
    @StateObject private var bridge = BridgeHandler()
    @StateObject private var model = PickerLabModel()
    @State private var scenario = "proposed"
    /// Bumped by Reset: a new URL reloads the web half from the scenario.
    @State private var resetCount = 0

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
                Button("Reset") {
                    resetCount += 1
                    model.apply(scenario: scenario)
                }
                Picker("Native size", selection: $model.small) {
                    Text("Regular").tag(false)
                    Text("Small").tag(true)
                }
                .pickerStyle(.segmented)
                .fixedSize()
                Spacer()
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
        .onChange(of: scenario) { _, name in model.apply(scenario: name) }
        .onChange(of: model.small) { _, _ in model.rebuild() }
    }

    private func specimenURL(_ base: URL) -> URL {
        var c = URLComponents(url: base.appendingPathComponent("picker-specimen"),
                              resolvingAgainstBaseURL: false)
        c?.queryItems = [URLQueryItem(name: "scenario", value: scenario),
                         URLQueryItem(name: "reset", value: String(resetCount))]
        return c?.url ?? base
    }

    // MARK: Native half

    private var nativeHalf: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("AppKit · NSPopover").font(.caption).foregroundStyle(.secondary)
                .padding(.bottom, 16)
            PopoverAnchor(model: model)
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
                url: specimenURL(base),
                bridgeHandler: bridge,
                session: ServeSession(projectID: project, port: port),
                authToken: serveFleet.fronted?.authToken
            )
            .environmentObject(i18n)
            // A new sidecar is a new view: the auth token is injected only when
            // the view is made (desktop/CLAUDE.md, "keyed on project.id + port").
            .id(ServeSession(projectID: project, port: port).viewID)
        } else {
            ContentUnavailableView(
                "No serve running",
                systemImage: "bolt.horizontal.circle",
                description: Text("Open a project in the main window first — the web half is the real SPA on that project's sidecar.")
            )
        }
    }
}

// MARK: - Model

/// The lab's fixture study and the slot being named. It plays the web side's
/// part — building the request and deciding what a pick means, as
/// `personPickerRows` and `personPickerChoice` do in the SPA.
@MainActor
final class PickerLabModel: ObservableObject {
    typealias Role = PersonPickerRequest.Role

    @Published var slot = PersonPickerRequest.Slot(code: "m1", role: .moderator,
                                                   name: "Martin B Storey", confirmed: false)
    @Published var known: [Role: [String]] = [
        .moderator: ["Martin B Storey", "Kerri Ng"],
        .participant: ["Sarah Chen", "Dr Amara Nwosu", "Mary Adeyemi"],
        .observer: ["Jane Smith"],
    ]
    @Published var isOpen = true
    /// The small pull-down size, as the app ships it (owner, 4 Oct 2026).
    @Published var small = true
    @Published private(set) var picker: PersonPickerModel?

    init() { rebuild() }

    func apply(scenario: String) {
        switch scenario {
        case "confirmed":
            slot = .init(code: "m1", role: .moderator, name: "Martin B Storey", confirmed: true)
        case "unknown":
            slot = .init(code: "m1", role: .moderator, name: "", confirmed: false)
        case "participant":
            slot = .init(code: "p3", role: .participant, name: "Mary Adeyemi", confirmed: false)
        default:
            slot = .init(code: "m1", role: .moderator, name: "Martin B Storey", confirmed: false)
        }
        isOpen = true
        rebuild()
    }

    var request: PersonPickerRequest {
        var names: [String]
        if slot.role == .participant {
            names = slot.name.isEmpty ? [] : [slot.name]
        } else {
            names = []
            for n in known[slot.role] ?? [] where !n.isEmpty && !names.contains(n) { names.append(n) }
            if !slot.name.isEmpty && !names.contains(slot.name) { names.insert(slot.name, at: 0) }
        }
        let prompt = slot.role == .moderator ? "New moderator"
            : slot.role == .observer ? "New observer" : "New name for \(slot.code)"
        return PersonPickerRequest(
            sessionId: "s1", slot: slot, names: names, anchor: .zero,
            labels: .init(roles: [.moderator: "Moderator", .participant: "Participant", .observer: "Observer"],
                          roleGroup: "Role", newPrompt: prompt,
                          thatsMe: slot.role == .participant ? nil : "That’s Me ({{name}})",
                          menu: "Edit name for \(slot.code)"))
    }

    func rebuild() {
        picker = PersonPickerModel(
            request: request, small: small,
            onChoose: { [weak self] name in self?.picked(name) },
            onClose: { [weak self] in self?.isOpen = false })
    }

    /// What the SPA does with a picked name: the slot's own proposed name is a
    /// yes; any other name renames it.
    private func picked(_ name: String) {
        slot = .init(code: slot.code, role: slot.role, name: name, confirmed: true)
        if !(known[slot.role] ?? []).contains(name) { known[slot.role, default: []].append(name) }
        rebuild()
    }
}

// MARK: - The anchor and its real NSPopover

/// The badge in the grid that opens the picker. The popover is AppKit's own,
/// `.applicationDefined` so it stays up while you look at the web half (the
/// app's is `.transient`).
private struct PopoverAnchor: View {
    @ObservedObject var model: PickerLabModel

    var body: some View {
        Button { model.isOpen.toggle() } label: {
            if model.slot.name.isEmpty {
                Text(model.slot.role.rawValue.capitalized).italic().foregroundStyle(.secondary)
            } else {
                PersonLabel(code: model.slot.code, name: model.slot.name, proposed: !model.slot.confirmed)
                    .fixedSize()
            }
        }
        .buttonStyle(.plain)
        .background(PopoverHost(isOpen: model.isOpen, onClose: { model.isOpen = false }) {
            LabPickerContent(lab: model)
        })
    }
}

/// The production picker for the lab's current slot, rebuilt when it changes.
private struct LabPickerContent: View {
    @ObservedObject var lab: PickerLabModel

    var body: some View {
        if let picker = lab.picker { PersonPickerView(model: picker) }
    }
}

/// The grid's person, as the anchor: the house badge, then the name — grey
/// while proposed, as the grid draws it.
private struct PersonLabel: NSViewRepresentable {
    let code: String
    let name: String
    let proposed: Bool

    func makeNSView(context: Context) -> NSView { NSView() }

    func updateNSView(_ view: NSView, context: Context) {
        view.subviews.forEach { $0.removeFromSuperview() }
        let label = NSTextField(labelWithString: name)
        label.font = PickerMetrics(small: false).nameFont
        label.textColor = proposed ? .secondaryLabelColor : .labelColor
        let row = PickerRowView(tick: nil, lead: PickerBadge(code: code, proposed: proposed),
                                name: label, column: SpeakerBadgeView.width(for: code),
                                metrics: PickerMetrics(small: false))
        row.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(row)
        NSLayoutConstraint.activate([
            row.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            row.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            row.topAnchor.constraint(equalTo: view.topAnchor),
            row.bottomAnchor.constraint(equalTo: view.bottomAnchor),
        ])
    }
}

private struct PopoverHost<Content: View>: NSViewRepresentable {
    let isOpen: Bool
    let onClose: () -> Void
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
            popover.delegate = context.coordinator
        }
        context.coordinator.onClose = onClose
        DispatchQueue.main.async {
            if isOpen, !popover.isShown, view.window != nil {
                // Below the badge, as menus and pop-ups open. The host view is
                // unflipped, so its bottom edge is minY.
                popover.show(relativeTo: view.bounds, of: view, preferredEdge: .minY)
            } else if !isOpen, popover.isShown {
                popover.close()
            }
        }
    }

    static func dismantleNSView(_ view: NSView, coordinator: Coordinator) {
        coordinator.popover.close()
    }

    /// Every close reaches the model here, so the next click on the badge
    /// opens it again.
    final class Coordinator: NSObject, NSPopoverDelegate {
        let popover = NSPopover()
        var onClose: (() -> Void)?
        func popoverDidClose(_ notification: Notification) { onClose?() }
    }
}
#endif
