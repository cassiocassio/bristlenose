import AppKit
import SwiftUI

// The Quotes search field's native parts (docs/design-search.md §5–§7): the
// token chips inside the field, and the suggestions list under it. Everything a
// researcher reads arrives localised from the SPA (`SearchBridge.swift`), and
// every badge is painted from the styles the SPA measured off its own cards
// (§7a), so nothing here holds a colour, a size or a locale key.

// MARK: - Badges painted from measured styles

extension BadgeColour {
    /// The colour as the SPA measured it, in the space it measured it in.
    var color: Color { Color(.displayP3, red: red, green: green, blue: blue, opacity: opacity) }
}

extension SearchBadgeStyle {
    /// The face the card uses: SF Mono for the mono stack, the system font
    /// otherwise (`--bn-font-mono` and the body font resolve to these in
    /// WKWebView), at the measured size and weight.
    var nsFont: NSFont {
        let w = NSFont.Weight(rawValue: CGFloat(Self.appKitWeight(css: weight)))
        return family == .mono
            ? NSFont.monospacedSystemFont(ofSize: CGFloat(size), weight: w)
            : NSFont.systemFont(ofSize: CGFloat(size), weight: w)
    }

    /// CSS weight (100…900) to AppKit's scale, interpolated over Apple's own
    /// named weights rather than a straight line: 490 lands just under medium.
    /// (The picker lab carries the same table for its debug-only chip.)
    static func appKitWeight(css: Double) -> Double {
        let table: [(Double, Double)] = [
            (100, NSFont.Weight.ultraLight.rawValue), (200, NSFont.Weight.thin.rawValue),
            (300, NSFont.Weight.light.rawValue), (400, NSFont.Weight.regular.rawValue),
            (500, NSFont.Weight.medium.rawValue), (600, NSFont.Weight.semibold.rawValue),
            (700, NSFont.Weight.bold.rawValue), (800, NSFont.Weight.heavy.rawValue),
            (900, NSFont.Weight.black.rawValue),
        ].map { ($0.0, Double($0.1)) }
        let w = min(max(css, 100), 900)
        guard let hi = table.firstIndex(where: { $0.0 >= w }), hi > 0 else { return table[0].1 }
        let (x0, y0) = table[hi - 1], (x1, y1) = table[hi]
        return y0 + (y1 - y0) * (w - x0) / (x1 - x0)
    }
}

/// One half of a badge (or a whole tag badge): the text in the measured face,
/// padded side by side as the CSS box is, on the measured fill.
private struct MeasuredBadgeHalf: View {
    let text: String
    let style: SearchBadgeStyle
    /// The border's width on the outer edges this half owns; the outline itself
    /// is drawn by the whole badge, inside its shape, as CSS's border box does.
    var leadingBorder: Double = 0
    var trailingBorder: Double = 0

    var body: some View {
        let bw = style.border?.width ?? 0
        Text(text)
            .font(Font(style.nsFont))
            .foregroundStyle(style.text.color)
            .lineLimit(1)
            // CSS centres the glyphs in the line box; a fixed frame does the same.
            .frame(height: style.lineHeight.map { CGFloat($0) })
            .padding(.leading, style.padX + leadingBorder)
            .padding(.trailing, style.padRight + trailingBorder)
            .padding(.top, style.padY + bw)
            .padding(.bottom, style.padBottom + bw)
            .background(style.fill.map(\.color) ?? .clear)
    }
}

/// A tag badge, exactly as on a quote card. Before the first measurement
/// arrives it is drawn plainly rather than guessed at (§7a).
struct MeasuredTagBadge: View {
    let text: String
    let style: SearchBadgeStyle?

    var body: some View {
        if let s = style {
            let bw = s.border?.width ?? 0
            MeasuredBadgeHalf(text: text, style: s, leadingBorder: bw, trailingBorder: bw)
                .clipShape(RoundedRectangle(cornerRadius: s.radius))
                .overlay {
                    RoundedRectangle(cornerRadius: s.radius)
                        .strokeBorder(s.border?.colour.color ?? .clear, lineWidth: bw)
                }
        } else {
            Text(text).lineLimit(1).foregroundStyle(.secondary)
        }
    }
}

/// The split speaker badge, `p3 | Priya Shah`, as on a quote card; the code
/// alone when the report shows no name for the person.
struct MeasuredPersonBadge: View {
    let code: String
    let name: String?
    let style: SearchPersonBadgeStyle?

    var body: some View {
        if let s = style {
            let bw = s.code.border?.width ?? 0
            let nameStyle = name == nil ? nil : s.name
            HStack(spacing: 0) {
                MeasuredBadgeHalf(text: code, style: s.code, leadingBorder: bw,
                                  trailingBorder: nameStyle == nil ? bw : 0)
                if let name, let n = nameStyle {
                    MeasuredBadgeHalf(text: name, style: n, trailingBorder: bw)
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: s.code.radius))
            .overlay {
                RoundedRectangle(cornerRadius: s.code.radius)
                    .strokeBorder(s.code.border?.colour.color ?? .clear, lineWidth: bw)
            }
        } else {
            Text(name.map { "\(code) \($0)" } ?? code).lineLimit(1).foregroundStyle(.secondary)
        }
    }
}

// MARK: - The keyboard, as pure decisions

/// What the field's keys do to the suggestions list and the tokens. A view's
/// decisions in a helper (desktop/CLAUDE.md, Testing), so the wrap, the
/// two-press ⌫ and the open rule are pinned without driving key events.
enum SearchFieldKeys {
    /// The key ⌫ sends. SwiftUI's `KeyEquivalent.delete` is U+0008, which the
    /// Mac's delete key never sends (it sends U+007F, NSDeleteCharacter), so a
    /// handler keyed on `.delete` never fires — measured 3 Oct 2026.
    static let deleteKey = KeyEquivalent("\u{7F}")

    /// ↓ / ↑ move the highlight by row id and wrap; from no highlight (which
    /// means the first row) ↓ goes to the second and ↑ to the last.
    static func move(_ highlight: String?, by step: Int, rows: [String]) -> String? {
        guard !rows.isEmpty else { return nil }
        let at = highlight.flatMap { rows.firstIndex(of: $0) } ?? 0
        return rows[((at + step) % rows.count + rows.count) % rows.count]
    }

    /// The highlighted row: the one with this id if it is still offered,
    /// else the first (the free text, which ↩ takes by default, §6).
    static func highlighted(_ id: String?, rows: [String]) -> String? {
        if let id, rows.contains(id) { return id }
        return rows.first
    }

    /// ⌫ in an empty field: the first press selects the last token, the second
    /// removes it, so one slip can't delete a token (§6). Typing anything
    /// clears the selection (the view does that).
    enum Backspace: Equatable {
        case select(SearchSubject)
        case remove(SearchSubject)
        case passThrough
    }

    static func backspace(text: String, tokens: [SearchTokenChip], selected: SearchSubject?) -> Backspace {
        guard text.isEmpty, let last = tokens.last else { return .passThrough }
        return selected == last.subject ? .remove(last.subject) : .select(last.subject)
    }

    /// The list is open while the field has focus, holds text, has rows to
    /// offer, and the researcher has typed since it last closed. It opens on
    /// an edit, never on state alone: text put back by a lens switch or a
    /// store reset must not pop it open over the report.
    static func isOpen(focused: Bool, text: String, rows: Int, dismissed: Bool) -> Bool {
        focused && !text.isEmpty && rows > 0 && !dismissed
    }

    /// True while an input method is composing in the key window's field
    /// editor (Japanese, Chinese, Korean). Its candidates own ↑ ↓ ↩ ⌫ then.
    @MainActor static var isComposing: Bool {
        (NSApp.keyWindow?.firstResponder as? NSTextView)?.hasMarkedText() ?? false
    }
}

/// The free-text row's label: what was typed in primary text, the rest of the
/// template in secondary, as Photos draws it (§4). Highlighted rows are drawn
/// in one colour, so the split only applies unhighlighted.
enum SuggestionLabel {
    static func attributed(_ row: SearchSuggestionRow, highlighted: Bool) -> AttributedString {
        var out = AttributedString(row.label)
        out.foregroundColor = highlighted ? SearchMenuColours.selectedText : .secondary
        guard !highlighted else { return out }
        for r in row.typedRanges {
            guard let lo = AttributedString.Index(r.lowerBound, within: out),
                  let hi = AttributedString.Index(r.upperBound, within: out) else { continue }
            out[lo..<hi].foregroundColor = .primary
        }
        return out
    }

    /// What VoiceOver hears for a row: its label and its count.
    static func spoken(_ row: SearchSuggestionRow) -> String {
        let label = row.kind == .person && row.code != nil && row.label != row.code
            ? "\(row.code!) \(row.label)" : row.label
        return "\(label), \(row.count.formatted())"
    }
}

/// The system's selection colours, so the list follows Graphite, Increase
/// Contrast and the user's accent as a menu does.
enum SearchMenuColours {
    static var selection: Color { Color(nsColor: .selectedContentBackgroundColor) }
    static var selectedText: Color { Color(nsColor: .alternateSelectedControlTextColor) }
}

// MARK: - A token chip

/// A token inside the field: a light container holding the meaning word, the
/// badge exactly as on a card, and ▾ (§5). Clicking opens a real `NSMenu` of
/// the meanings and Remove, below the chip as Mail's and Finder's tokens do —
/// a SwiftUI `Menu` cannot draw a coloured badge in its label on macOS, it
/// flattens the label to a title.
struct SearchTokenChipView: View {
    let chip: SearchTokenChip
    let styles: SearchBadgeStyles
    /// Selected by a first ⌫ in an empty field; the next ⌫ removes it. Filled
    /// with the selection colour, as Mail fills a selected token.
    let selected: Bool
    /// Called before the menu opens, so the suggestions list closes first.
    let onOpen: () -> Void
    let onMode: (String) -> Void
    let onRemove: () -> Void

    @StateObject private var presenter = NSMenuPresenter()

    var body: some View {
        Button {
            onOpen()
            presenter.show(menu)
        } label: {
            HStack(spacing: 4) {
                if !chip.word.isEmpty {
                    Text(chip.word)
                        .foregroundStyle(selected ? AnyShapeStyle(SearchMenuColours.selectedText) : AnyShapeStyle(.secondary))
                        .font(.system(size: 11))
                }
                badge
                Image(systemName: "chevron.down")
                    .font(.system(size: 8, weight: .semibold))
                    .foregroundStyle(selected ? AnyShapeStyle(SearchMenuColours.selectedText) : AnyShapeStyle(.secondary))
            }
            .padding(.leading, 6)
            .padding(.trailing, 4)
            .frame(minHeight: 20)
            .background(
                RoundedRectangle(cornerRadius: 6)
                    .fill(selected ? AnyShapeStyle(SearchMenuColours.selection) : AnyShapeStyle(.quaternary))
            )
            .contentShape(RoundedRectangle(cornerRadius: 6))
        }
        .buttonStyle(.plain)
        .background(NSMenuAnchor(presenter: presenter))
        .fixedSize()
        .accessibilityLabel(chip.modes.first { $0.id == chip.mode }?.label ?? chip.label)
        .accessibilityAddTraits(selected ? .isSelected : [])
        .accessibilityAction(named: Text(chip.removeLabel.isEmpty ? chip.label : chip.removeLabel)) {
            onRemove()
        }
    }

    @ViewBuilder private var badge: some View {
        switch chip.subject {
        case .person(let code):
            MeasuredPersonBadge(code: code, name: chip.label == code ? nil : chip.label,
                                style: styles.people[chip.styleKey])
        case .tag:
            MeasuredTagBadge(text: chip.label, style: styles.tags[chip.styleKey])
        }
    }

    private var menu: NSMenu {
        presenter.reset()
        let menu = NSMenu()
        for mode in chip.modes {
            let item = presenter.item(mode.label) { onMode(mode.id) }
            item.state = mode.id == chip.mode ? .on : .off
            item.isEnabled = mode.enabled
            menu.addItem(item)
        }
        if !chip.removeLabel.isEmpty {
            menu.addItem(.separator())
            menu.addItem(presenter.item(chip.removeLabel, onRemove))
        }
        menu.autoenablesItems = false
        return menu
    }
}

/// Pops an `NSMenu` under the view it is anchored to, and runs the chosen
/// item's closure.
final class NSMenuPresenter: NSObject, ObservableObject {
    weak var anchor: NSView?
    private var actions: [() -> Void] = []

    /// Forget the last menu's actions; the menu is rebuilt on every click.
    func reset() { actions = [] }

    func item(_ title: String, _ action: @escaping () -> Void) -> NSMenuItem {
        let item = NSMenuItem(title: title, action: #selector(run(_:)), keyEquivalent: "")
        item.target = self
        item.tag = actions.count
        actions.append(action)
        return item
    }

    func show(_ menu: NSMenu) {
        guard let anchor else { return }
        // Below the chip, as a pull-down opens. The anchor is unflipped, so
        // its bottom edge is y = 0.
        menu.popUp(positioning: nil, at: NSPoint(x: 0, y: -4), in: anchor)
    }

    @objc private func run(_ sender: NSMenuItem) {
        guard actions.indices.contains(sender.tag) else { return }
        actions[sender.tag]()
    }
}

private struct NSMenuAnchor: NSViewRepresentable {
    let presenter: NSMenuPresenter
    func makeNSView(context: Context) -> NSView {
        let v = NSView()
        presenter.anchor = v
        return v
    }
    func updateNSView(_ nsView: NSView, context: Context) { presenter.anchor = nsView }
}

// MARK: - The suggestions list

/// The rows under the field (§4): a lens glyph for rows that point at a lens,
/// the badge itself for people and tags, and the count right-aligned. The
/// highlight is the system selection, as in any Mac menu. Every row is one
/// height — the tallest badge's — so the list does not jitter between styles.
struct SearchSuggestionsList: View {
    let rows: [SearchSuggestionRow]
    let styles: SearchBadgeStyles
    let highlightID: String?
    let width: CGFloat
    let onChoose: (String) -> Void
    let onHover: (String) -> Void

    var body: some View {
        let height = Self.rowHeight(styles)
        VStack(spacing: 0) {
            ForEach(Array(rows.enumerated()), id: \.element.id) { index, row in
                rowView(row, highlighted: row.id == highlightID)
                    .frame(height: height)
                    .contentShape(Rectangle())
                    .onTapGesture { onChoose(row.id) }
                    .onContinuousHover { phase in
                        if case .active = phase { onHover(row.id) }
                    }
                // The free text points at a lens; the badges below name things.
                if row.kind == .text, index + 1 < rows.count {
                    Divider().padding(.horizontal, 6).padding(.vertical, 3)
                }
            }
        }
        .padding(4)
        .frame(width: width)
        .fixedSize(horizontal: false, vertical: true)
    }

    /// One row height for the whole list: the tallest measured badge plus a
    /// little air, and never less than a menu row.
    static func rowHeight(_ styles: SearchBadgeStyles) -> CGFloat {
        func h(_ s: SearchBadgeStyle) -> Double {
            (s.lineHeight ?? s.size * 1.25) + s.padY + s.padBottom + 2 * (s.border?.width ?? 0)
        }
        let all = styles.tags.values.map(h)
            + styles.people.values.flatMap { [h($0.code)] + ($0.name.map { [h($0)] } ?? []) }
        return max(24, CGFloat((all.max() ?? 0) + 6))
    }

    private func rowView(_ row: SearchSuggestionRow, highlighted: Bool) -> some View {
        HStack(spacing: 8) {
            switch row.kind {
            case .text:
                Image(systemName: LensItem.systemImage(for: .quotes))
                    .foregroundStyle(highlighted ? AnyShapeStyle(SearchMenuColours.selectedText) : AnyShapeStyle(.secondary))
                    .frame(width: 16)
                Text(SuggestionLabel.attributed(row, highlighted: highlighted)).lineLimit(1)
            case .person:
                MeasuredPersonBadge(code: row.code ?? row.label,
                                    name: row.label == row.code ? nil : row.label,
                                    style: styles.personStyle(for: row))
                    .background(cardBacking(highlighted))
                    .overlay(highlightRing(highlighted))
            case .tag:
                MeasuredTagBadge(text: row.label, style: styles.tagStyle(for: row))
                    .background(cardBacking(highlighted))
                    .overlay(highlightRing(highlighted))
            }
            Spacer(minLength: 12)
            Text(row.count, format: .number)
                .monospacedDigit()
                .foregroundStyle(highlighted ? AnyShapeStyle(SearchMenuColours.selectedText.opacity(0.85)) : AnyShapeStyle(.secondary))
        }
        .font(.system(size: 13))
        .padding(.horizontal, 8)
        .frame(maxHeight: .infinity)
        .background(
            RoundedRectangle(cornerRadius: 5).fill(highlighted ? SearchMenuColours.selection : .clear)
        )
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(SuggestionLabel.spoken(row))
        .accessibilityAddTraits(highlighted ? .isSelected : [])
    }

    /// A badge with no fill of its own (a speaker code) is drawn on the card's
    /// background on the web; on the selection colour it would be dark text on
    /// blue. So a highlighted badge sits on the card's background, and reads
    /// exactly as it does on a quote card.
    @ViewBuilder private func cardBacking(_ on: Bool) -> some View {
        if on {
            RoundedRectangle(cornerRadius: 3).fill(Color(nsColor: .textBackgroundColor)).padding(-1)
        }
    }

    /// On the selection colour a badge keeps its own colours and gains a thin
    /// light ring, so it still reads as the card's badge.
    @ViewBuilder private func highlightRing(_ on: Bool) -> some View {
        if on {
            RoundedRectangle(cornerRadius: 3)
                .strokeBorder(SearchMenuColours.selectedText.opacity(0.55), lineWidth: 1)
                .padding(-1.5)
        }
    }
}

/// Shows SwiftUI content in a borderless child window under an anchor view,
/// never taking focus from the field above it. This is the pattern of Apple's
/// "CustomMenus" sample (a search field's suggestions window), and of Safari's
/// address bar: an `NSPopover` would take key status from the field mid-typing,
/// and an `NSMenu` runs its own tracking loop and swallows the typing. Keys stay
/// with the field; the window only draws and takes clicks.
///
/// Dismissal is the window's job as much as the field's, as in CustomMenus: a
/// click anywhere outside the list and the field, the parent losing key (a
/// second window, Settings, another app), and the parent starting a live
/// resize or a full-screen change all close it, and say so through `onDismiss`
/// so the field does not reopen it until the next edit.
@MainActor
final class SuggestionsWindowController {
    private var panel: SuggestionsPanel?
    private var host: FirstMouseHostingView<AnyView>?
    private weak var anchor: NSView?
    private var observers: [NSObjectProtocol] = []
    private var mouseMonitor: Any?
    var onDismiss: (() -> Void)?

    var isShown: Bool { panel?.isVisible ?? false }

    func show(_ content: AnyView, below anchor: NSView) {
        guard let parent = anchor.window else { return hide() }
        let panel = self.panel ?? makePanel()
        host?.rootView = content
        host?.layoutSubtreeIfNeeded()
        let size = host?.fittingSize ?? .zero
        let anchorRect = parent.convertToScreen(anchor.convert(anchor.bounds, to: nil))
        var origin = NSPoint(x: anchorRect.minX, y: anchorRect.minY - size.height - 6)
        if let screen = parent.screen?.visibleFrame {
            origin.x = min(max(origin.x, screen.minX + 4), screen.maxX - size.width - 4)
        }
        panel.setFrame(NSRect(origin: origin, size: size), display: true)
        panel.invalidateShadow()  // the row count changes its shape
        if panel.parent !== parent || !panel.isVisible || self.anchor !== anchor {
            panel.parent?.removeChildWindow(panel)
            parent.addChildWindow(panel, ordered: .above)
            panel.orderFront(nil)
            watch(parent: parent, anchor: anchor)
        }
    }

    func hide() {
        unwatch()
        guard let panel, panel.isVisible || panel.parent != nil else { return }
        panel.parent?.removeChildWindow(panel)
        panel.orderOut(nil)
    }

    /// Close because something outside the field happened, and tell the field.
    private func dismiss() {
        guard isShown else { return }
        hide()
        onDismiss?()
    }

    private func watch(parent: NSWindow, anchor: NSView) {
        unwatch()
        self.anchor = anchor
        let center = NotificationCenter.default
        for name in [NSWindow.didResignKeyNotification, NSWindow.willStartLiveResizeNotification,
                     NSWindow.willEnterFullScreenNotification, NSWindow.willExitFullScreenNotification,
                     NSWindow.willCloseNotification] {
            observers.append(center.addObserver(forName: name, object: parent, queue: .main) { [weak self] _ in
                MainActor.assumeIsolated { self?.dismiss() }
            })
        }
        // A click outside the list and outside the field closes it. Compared by
        // window, so a click in another Bristlenose window's field is "outside"
        // (desktop/CLAUDE.md: a per-window monitor sees every window's clicks).
        mouseMonitor = NSEvent.addLocalMonitorForEvents(
            matching: [.leftMouseDown, .rightMouseDown, .otherMouseDown]
        ) { [weak self] event in
            MainActor.assumeIsolated {
                guard let self, let panel = self.panel else { return }
                if event.window === panel { return }
                if let anchor = self.anchor, event.window === anchor.window {
                    let p = anchor.convert(event.locationInWindow, from: nil)
                    if anchor.bounds.contains(p) { return }
                }
                self.dismiss()
            }
            return event
        }
    }

    private func unwatch() {
        observers.forEach(NotificationCenter.default.removeObserver)
        observers = []
        if let mouseMonitor { NSEvent.removeMonitor(mouseMonitor) }
        mouseMonitor = nil
    }

    private func makePanel() -> SuggestionsPanel {
        let panel = SuggestionsPanel()
        let effect = NSVisualEffectView()
        effect.material = .menu
        effect.state = .active
        effect.blendingMode = .behindWindow
        effect.maskImage = Self.roundedMask(radius: 8)
        let host = FirstMouseHostingView(rootView: AnyView(EmptyView()))
        host.translatesAutoresizingMaskIntoConstraints = false
        effect.addSubview(host)
        NSLayoutConstraint.activate([
            host.leadingAnchor.constraint(equalTo: effect.leadingAnchor),
            host.trailingAnchor.constraint(equalTo: effect.trailingAnchor),
            host.topAnchor.constraint(equalTo: effect.topAnchor),
            host.bottomAnchor.constraint(equalTo: effect.bottomAnchor),
        ])
        panel.contentView = effect
        self.panel = panel
        self.host = host
        return panel
    }

    /// A resizable rounded-rect mask: the corner is drawn once and stretched,
    /// so it fits any height. (The shadow gives the edge; no rim is drawn.)
    private static func roundedMask(radius: CGFloat) -> NSImage {
        let edge = radius * 2 + 1
        let image = NSImage(size: NSSize(width: edge, height: edge), flipped: false) { rect in
            NSColor.black.setFill()
            NSBezierPath(roundedRect: rect, xRadius: radius, yRadius: radius).fill()
            return true
        }
        image.capInsets = NSEdgeInsets(top: radius, left: radius, bottom: radius, right: radius)
        image.resizingMode = .stretch
        return image
    }
}

/// A window that draws and takes clicks but never becomes key, so the search
/// field keeps the caret while the list is open.
final class SuggestionsPanel: NSPanel {
    init() {
        super.init(contentRect: .zero, styleMask: [.borderless, .nonactivatingPanel],
                   backing: .buffered, defer: true)
        isOpaque = false
        backgroundColor = .clear
        hasShadow = true
        hidesOnDeactivate = true
        becomesKeyOnlyIfNeeded = true
        isReleasedWhenClosed = false  // desktop/CLAUDE.md: an NSWindow made in code
    }
    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }
}

/// A click on a row in a window that is not key must act at once, as a menu's
/// does, not first make the window key.
final class FirstMouseHostingView<Content: View>: NSHostingView<Content> {
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
}

/// Puts the list under the view this sits behind, and keeps it in step with
/// `isOpen` and the rows.
struct SuggestionsAnchor: NSViewRepresentable {
    let isOpen: Bool
    let content: AnyView
    let onDismiss: () -> Void

    func makeCoordinator() -> SuggestionsWindowController { SuggestionsWindowController() }
    func makeNSView(context: Context) -> NSView { NSView() }

    func updateNSView(_ view: NSView, context: Context) {
        let controller = context.coordinator
        controller.onDismiss = onDismiss
        let open = isOpen, content = self.content
        // After layout, so the anchor's frame is where the field now is.
        DispatchQueue.main.async {
            if open, view.window != nil { controller.show(content, below: view) } else { controller.hide() }
        }
    }

    static func dismantleNSView(_ view: NSView, coordinator: SuggestionsWindowController) {
        coordinator.hide()
    }
}
