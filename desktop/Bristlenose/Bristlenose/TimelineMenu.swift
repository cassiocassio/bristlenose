import AppKit
import WebKit

// The transcript's timeline pulldown, native
// (docs/mockups/transcript-timeline-native-menu.html).
//
// In the Mac app the caret of the transcript's split control does not open the
// web menu: the SPA sends `timeline-menu` with the state, where the control is,
// and every string already localised, and this side pops an NSMenu under the
// control. A pick goes back as the View menu's own actions
// (`toggleSessionTimeline`, `setSessionTimelineLanes`), and the close as
// `timelineMenuClosed`, so the SPA can hand focus back to the caret.
//
// Opened from the keyboard, the menu highlights no row until an arrow key: a
// pull-down has no public way to highlight a row without moving it over the
// control (passing it as `positioning:` makes a pop-up), so this is accepted.

/// What the SPA asks for: the slot's state and the menu's words.
struct TimelineMenuRequest: Equatable {
    struct Lane: Equatable {
        let lanes: Int
        let title: String
        let hint: String
    }

    let on: Bool
    let lanes: Int
    /// The split control, in CSS pixels from the web view's top-left.
    let anchor: CGRect
    let journey: String
    let timeline: String
    let detail: String
    let laneItems: [Lane]

    init(on: Bool, lanes: Int, anchor: CGRect, journey: String, timeline: String,
         detail: String, laneItems: [Lane]) {
        self.on = on
        self.lanes = lanes
        self.anchor = anchor
        self.journey = journey
        self.timeline = timeline
        self.detail = detail
        self.laneItems = laneItems
    }

    init?(message body: [String: Any]) {
        func num(_ v: Any?) -> CGFloat? { (v as? NSNumber).map { CGFloat($0.doubleValue) } }
        guard let on = body["on"] as? Bool,
              let lanes = (body["lanes"] as? NSNumber)?.intValue,
              let a = body["anchor"] as? [String: Any],
              let x = num(a["x"]), let y = num(a["y"]), let w = num(a["width"]), let h = num(a["height"]),
              let l = body["labels"] as? [String: Any],
              let journey = l["journey"] as? String,
              let timeline = l["timeline"] as? String,
              let detail = l["detail"] as? String,
              let rows = l["lanes"] as? [[String: Any]]
        else { return nil }
        let laneItems = rows.compactMap { row -> Lane? in
            guard let n = (row["lanes"] as? NSNumber)?.intValue,
                  let title = row["title"] as? String else { return nil }
            return Lane(lanes: n, title: title, hint: row["hint"] as? String ?? "")
        }
        guard laneItems.count == rows.count, !laneItems.isEmpty else { return nil }
        self.init(on: on, lanes: lanes, anchor: CGRect(x: x, y: y, width: w, height: h),
                  journey: journey, timeline: timeline, detail: detail, laneItems: laneItems)
    }
}

/// The menu as data, so its decisions (what is ticked, what a pick sends) are
/// tested without AppKit.
enum TimelineMenuEntry: Equatable {
    /// What choosing a row does. A row that names the state already showing
    /// does nothing: the store's toggle would flip it away.
    enum Pick: Equatable {
        case none
        case toggle
        case lanes(Int)

        /// The menu action and payload the SPA's store already answers.
        var action: (name: String, payload: [String: Any])? {
            switch self {
            case .none: return nil
            case .toggle: return ("toggleSessionTimeline", [:])
            case .lanes(let n): return ("setSessionTimelineLanes", ["lanes": n])
            }
        }
    }

    case item(title: String, subtitle: String?, checked: Bool, pick: Pick)
    case separator
    case header(String)

    static func entries(for r: TimelineMenuRequest) -> [TimelineMenuEntry] {
        [
            .item(title: r.journey, subtitle: nil, checked: !r.on, pick: r.on ? .toggle : .none),
            .item(title: r.timeline, subtitle: nil, checked: r.on, pick: r.on ? .none : .toggle),
            .separator,
            .header(r.detail),
        ] + r.laneItems.map {
            .item(title: $0.title, subtitle: $0.hint.isEmpty ? nil : $0.hint,
                  checked: r.lanes == $0.lanes, pick: .lanes($0.lanes))
        }
    }

    /// Where the menu's top-left goes: its right edge on the control's right
    /// edge (the control sits at the window's trailing edge, so a left-aligned
    /// menu would hang outside the window), a few points below it, as a
    /// pull-down opens (owner, 18 Oct 2026). Left-to-right only: a right-to-left
    /// locale would hang it from the control's leading edge instead (`minX`).
    static func origin(anchor: NSRect, menuWidth: CGFloat, flipped: Bool, gap: CGFloat = 4) -> NSPoint {
        NSPoint(x: anchor.maxX - menuWidth,
                y: flipped ? anchor.maxY + gap : anchor.minY - gap)
    }
}

@MainActor
final class TimelineMenuPresenter: NSObject {
    private var picks: [TimelineMenuEntry.Pick] = []
    private var choose: ((_ action: String, _ payload: [String: Any]) -> Void)?
    /// A menu is tracking. Main-actor work still runs during tracking, so a
    /// second request (a double-click on the caret) would otherwise build a
    /// menu inside this one and overwrite `picks`, losing the outer pick.
    private var isPresenting = false

    /// Pops the menu under the control and returns when it closes. A request
    /// while one is open is dropped with no echo: the open menu's own close
    /// answers for both, and an early echo would tell the SPA the menu had
    /// closed while it was still on screen.
    func present(_ request: TimelineMenuRequest, over webView: WKWebView,
                 choose: @escaping (_ action: String, _ payload: [String: Any]) -> Void,
                 closed: () -> Void) {
        guard !isPresenting else { return }
        isPresenting = true
        defer { isPresenting = false }
        picks = []
        // Kept after the menu closes: AppKit may send the item's action after
        // `popUp` returns, and the next `present` replaces it anyway.
        self.choose = choose
        let menu = NSMenu(title: request.detail)
        menu.autoenablesItems = false
        for entry in TimelineMenuEntry.entries(for: request) {
            switch entry {
            case .separator:
                menu.addItem(.separator())
            case .header(let title):
                menu.addItem(.sectionHeader(title: title))
            case let .item(title, subtitle, checked, pick):
                let item = NSMenuItem(title: title, action: #selector(run(_:)), keyEquivalent: "")
                item.target = self
                item.tag = picks.count
                item.state = checked ? .on : .off
                item.subtitle = subtitle
                picks.append(pick)
                menu.addItem(item)
            }
        }
        let rect = PersonPickerPresenter.viewRect(for: request.anchor, in: webView)
        menu.minimumWidth = rect.width
        let at = TimelineMenuEntry.origin(anchor: rect, menuWidth: menu.size.width,
                                          flipped: webView.isFlipped)
        menu.popUp(positioning: nil, at: at, in: webView)
        closed()
    }

    @objc private func run(_ sender: NSMenuItem) {
        guard picks.indices.contains(sender.tag),
              let action = picks[sender.tag].action else { return }
        choose?(action.name, action.payload)
    }
}
