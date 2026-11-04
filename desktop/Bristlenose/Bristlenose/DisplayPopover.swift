import SwiftUI

/// The toolbar's Display button and its popover: Layout, Density, Break long
/// paragraphs, Focus Mode (docs/design-display-preferences.md §7).
///
/// The shape follows the system's own Energy Mode popover: a one-of-two choice
/// as icon rows (the chosen row's icon becomes an accent disc), a continuous
/// slider for Density, and the two on/off settings as plain rows with a tick on
/// the left. Built beside the Export popover and unlike it in two decided ways:
/// the choices persist (the SPA saves them), so every row reads the live value
/// the report mirrors back, never a `@State` default; and the popover stays open
/// while the reader tries settings. A SwiftUI `.popover` already closes on
/// Escape or a click outside, which is all the closing it needs.
///
/// Nothing here writes a preference. A choice goes to the SPA through
/// `menuAction`, which validates, saves and mirrors it back; the Focus Mode row
/// uses the same `focusMode` action as the View menu's toggle.
struct DisplayMenuButton: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    @State private var isPresented = false

    var body: some View {
        Button {
            isPresented.toggle()
        } label: {
            Label(i18n.t("common.toolbar.display"), systemImage: "textformat.size")
        }
        .help(i18n.t("common.toolbar.display"))
        // Nothing to send a choice to without a live report; dim the button, not just what it opens.
        .disabled(bridgeHandler.commandTab == nil)
        .popover(isPresented: $isPresented, arrowEdge: .bottom) {
            DisplayPopoverContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }
    }
}

struct DisplayPopoverContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    /// The slider's value while it is being moved. The report echoes each value
    /// back a moment later, and showing the echo mid-drag makes the thumb stutter.
    @State private var dragging: Double?
    @State private var editing = false
    @State private var lastSent = Date.distantPast
    /// A send held back by the throttle, so the last step is never dropped.
    @State private var trailing: Task<Void, Never>?
    /// Gives up waiting for an echo, so the thumb can never stay frozen.
    @State private var settle: Task<Void, Never>?

    private var prefs: DisplayPrefs { bridgeHandler.displayPrefs }

    /// A choice goes to the SPA, which owns and saves it.
    private func choose(_ action: String, _ value: Any) {
        bridgeHandler.menuAction(action, payload: ["value": value])
    }

    // MARK: - Pieces

    private func sectionHeader(_ title: String) -> some View {
        Text(title)
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(.secondary)
            .padding(.horizontal, 14)
            .padding(.top, 8)
            .padding(.bottom, 4)
    }

    /// One of a pair: the chosen row's icon is an accent disc.
    private func layoutRow(_ value: String, symbol: String, title: String) -> some View {
        let selected = prefs.layout == value
        return Button {
            choose("setDisplayLayout", value)
        } label: {
            HStack(spacing: 10) {
                Image(systemName: symbol)
                    .font(.system(size: 13))
                    .foregroundStyle(selected ? Color.white : Color.primary)
                    .frame(width: 28, height: 28)
                    .background(Circle().fill(selected ? Color.accentColor : Color.secondary.opacity(0.18)))
                    .accessibilityHidden(true)
                Text(title)
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 3)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }

    /// A plain menu item with a tick on the left when it is on.
    private func tickRow(_ title: String, on: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 8) {
                Image(systemName: "checkmark")
                    .font(.system(size: 12, weight: .semibold))
                    .opacity(on ? 1 : 0)
                    .frame(width: 14)
                    .accessibilityHidden(true)
                Text(title)
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 5)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(on ? .isSelected : [])
    }

    // MARK: - Density

    /// Nearest of the three named stops, for VoiceOver to say.
    private func densityWord(_ d: Double) -> String {
        if d < 0.25 { return i18n.t("common.toolbar.displayCompact") }
        if d > 0.75 { return i18n.t("common.toolbar.displaySpacious") }
        return i18n.t("common.toolbar.displayNormal")
    }

    private func sendDensity(_ v: Double) {
        lastSent = Date()
        choose("setDisplayDensity", DensitySliderLogic.rounded(v))
    }

    /// Live while dragging so the quotes follow, but not every pixel; a step the
    /// throttle holds back still goes out a moment later.
    private func scheduleDensity(_ v: Double) {
        trailing?.cancel()
        if DensitySliderLogic.shouldSendNow(now: Date(), lastSent: lastSent) {
            sendDensity(v)
        } else {
            trailing = Task {
                try? await Task.sleep(nanoseconds: DensitySliderLogic.trailingDelay)
                if !Task.isCancelled { sendDensity(v) }
            }
        }
        armSettle()
    }

    /// After the last change, stop showing the slider's own value and follow the
    /// report again, whether or not an echo arrived.
    private func armSettle() {
        settle?.cancel()
        settle = Task {
            try? await Task.sleep(nanoseconds: DensitySliderLogic.settleDelay)
            if !Task.isCancelled { dragging = nil }
        }
    }

    private var densityControl: some View {
        let shown = dragging ?? prefs.density
        return VStack(spacing: 2) { densitySlider(shown); densityWords }
            // The report's echo of what was sent hands the thumb back to it.
            .onChange(of: prefs.density) { _, newValue in
                if !editing, let d = dragging, DensitySliderLogic.echoMatches(shown: d, report: newValue) { dragging = nil }
            }
    }

    /// The three named stops under the slider: Compact and Spacious at the ends,
    /// Normal exactly in the middle, where the thumb settles. Hidden from
    /// VoiceOver, which reads the slider's own value.
    private var densityWords: some View {
        ZStack {
            HStack {
                Text(i18n.t("common.toolbar.displayCompact"))
                Spacer(minLength: 0)
                Text(i18n.t("common.toolbar.displaySpacious"))
            }
            Text(i18n.t("common.toolbar.displayNormal"))
        }
        .font(.caption)
        .foregroundStyle(.secondary)
        .padding(.horizontal, 14)
        .accessibilityHidden(true)
    }

    private func densitySlider(_ shown: Double) -> some View {
        HStack(spacing: 10) {
            Image(systemName: "textformat.size.smaller")
                .foregroundStyle(.secondary)
                .accessibilityHidden(true)
            Slider(
                value: Binding(
                    get: { shown },
                    set: { v in
                        let s = DensitySliderLogic.snapped(v, mouseEditing: editing)
                        dragging = s
                        scheduleDensity(s)
                    }
                ),
                in: 0...1,
                onEditingChanged: { began in
                    editing = began
                    if !began, let d = dragging {
                        // The final value always goes, and the thumb stays where it was
                        // let go until the report echoes it: handing it back to a
                        // stale echo made it jump backwards.
                        trailing?.cancel()
                        sendDensity(d)
                        armSettle()
                    }
                }
            )
            .accessibilityLabel(i18n.t("common.toolbar.displayDensity"))
            // The nearest name and the number, so each step says something.
            .accessibilityValue("\(densityWord(shown)), \(Int((shown * 100).rounded()))%")
            Image(systemName: "textformat.size.larger")
                .foregroundStyle(.secondary)
                .accessibilityHidden(true)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 2)
    }

    // MARK: - Body

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            sectionHeader(i18n.t("common.toolbar.displayLayout"))
            layoutRow("columns", symbol: "rectangle.split.2x1", title: i18n.t("common.toolbar.displayColumns"))
            layoutRow("single", symbol: "rectangle.portrait", title: i18n.t("common.toolbar.displaySingleColumn"))

            Divider().padding(.vertical, 6)

            sectionHeader(i18n.t("common.toolbar.displayDensity"))
            densityControl

            Divider().padding(.vertical, 6)

            tickRow(i18n.t("common.toolbar.displayBreakParagraphs"), on: prefs.breaksOn) {
                choose("setDisplayBreaks", prefs.breaksOn ? "off" : "on")
            }
            // The View menu's toggle, bound the same way: the SPA owns Focus Mode.
            tickRow(i18n.t("common.toolbar.focusMode"), on: bridgeHandler.focusModeActive) {
                bridgeHandler.menuAction("focusMode")
            }
            .disabled(bridgeHandler.commandTab != .quotes)
            .padding(.bottom, 4)
        }
        .frame(width: 270)
        // No live report channel, nothing to send a choice to.
        .disabled(bridgeHandler.commandTab == nil)
    }
}
