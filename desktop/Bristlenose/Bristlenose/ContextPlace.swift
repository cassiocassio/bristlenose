import Foundation

/// Where a link in the report goes and what clicking it does, as the page
/// declares it (`frontend/src/utils/contextPlace.ts`). The report's right-click
/// menu is built from this, never from the link's href: two hrefs in the report
/// point at the wrong lens (docs/design-webview-context-menu.md §4.2).
///
/// Decoded strictly: a place this build does not understand decodes to nothing,
/// and the menu then offers none of its own items rather than a wrong one.
struct ContextPlace: Codable, Hashable {
    /// The single click, which is the menu's first item.
    enum Click: String, Codable { case play, navigate, window }
    /// How going there reads: Show in X, Open X, or Go to Section.
    enum Verb: String, Codable { case show, open, go }
    /// What `path` shows.
    enum Dest: String, Codable { case transcript, quotes, lens }
    /// A recording at a moment: the player's `seekTo(key, seconds)`.
    struct Media: Codable, Hashable {
        let key: String
        let seconds: Double
    }

    let click: Click
    let verb: Verb
    let dest: Dest
    /// The router path; empty where there is nowhere to go (a moment with no session).
    let path: String
    let media: Media?
    /// Go to Section: the heading's id on the page already showing.
    let anchor: String?
}

/// A quote card under the pointer.
struct ContextCard: Codable, Hashable {
    let domId: String
    let starred: Bool
    /// What Star will do, by the rule every surface uses: Unstar only when all
    /// it acts on are starred.
    let unstar: Bool
    /// How many quotes the card's commands act on: the selection it sits in, or
    /// 0 for the card alone.
    let count: Int
    /// The card's own transcript place, its speaker link's.
    let place: ContextPlace?

    init(domId: String, starred: Bool, unstar: Bool? = nil, count: Int = 0, place: ContextPlace?) {
        self.domId = domId
        self.starred = starred
        self.unstar = unstar ?? starred
        self.count = count
        self.place = place
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let starred = try c.decode(Bool.self, forKey: .starred)
        self.init(domId: try c.decode(String.self, forKey: .domId), starred: starred,
                  unstar: try c.decodeIfPresent(Bool.self, forKey: .unstar),
                  count: try c.decodeIfPresent(Int.self, forKey: .count) ?? 0,
                  place: try c.decodeIfPresent(ContextPlace.self, forKey: .place))
    }
}

/// One right-click's `context-target` message.
struct ContextTarget: Codable, Equatable {
    /// A link into this report (its href is a loopback address that dies with
    /// the serve) or out of it.
    enum Link: String, Codable {
        case inReport = "internal"
        case outside = "external"
    }

    let seq: Int
    let place: ContextPlace?
    /// The place's transcript is the page showing (Show in Transcript would go nowhere).
    let here: Bool
    let card: ContextCard?
    let link: Link?

    init(seq: Int, place: ContextPlace?, here: Bool = false, card: ContextCard? = nil, link: Link? = nil) {
        self.seq = seq
        self.place = place
        self.here = here
        self.card = card
        self.link = link
    }

    /// Nil for a body this build cannot read in full.
    static func from(_ body: [String: Any]) -> ContextTarget? {
        guard JSONSerialization.isValidJSONObject(body),
              let data = try? JSONSerialization.data(withJSONObject: body) else { return nil }
        return try? JSONDecoder().decode(ContextTarget.self, from: data)
    }
}

/// The latest right-click's target, kept from the page's message until WebKit
/// asks for the menu.
///
/// A target is used once, by the menu it describes, and only while young enough
/// to be that right-click's. The page numbers right-clicks per document, so the
/// numbering starts again whenever the report reloads (⌘R, Reload Report, the
/// reload after a run): `newDocument()` resets it. Without that, every
/// right-click after a reload read as already used, until the count caught up.
struct ContextTargetSlot {
    /// How old a target may be and still describe the menu being opened.
    static let lifetime: TimeInterval = 0.25

    private var pending: (target: ContextTarget, at: Date)?
    private var lastSeq = 0

    /// Why the last `take` found no target although one was pending, for the
    /// log: a menu that silently lacks its items is otherwise undiagnosable.
    enum Rejection: Equatable {
        case alreadyUsed(seq: Int, lastSeq: Int)
        case tooOld(ageMs: Int)
    }
    private(set) var lastRejection: Rejection?

    mutating func receive(_ target: ContextTarget, at: Date) {
        pending = (target, at)
    }

    /// The page said something this build cannot read: no target for this menu.
    mutating func receiveUnreadable() {
        pending = nil
    }

    mutating func newDocument() {
        pending = nil
        lastSeq = 0
    }

    /// The target for a menu opening now, or nil: none, already used, or too old.
    mutating func take(now: Date) -> ContextTarget? {
        defer { pending = nil }
        lastRejection = nil
        guard let pending else { return nil }
        let seq = pending.target.seq
        guard seq > lastSeq else {
            lastRejection = .alreadyUsed(seq: seq, lastSeq: lastSeq)
            return nil
        }
        lastSeq = seq
        let age = now.timeIntervalSince(pending.at)
        guard age <= Self.lifetime else {
            lastRejection = .tooOld(ageMs: Int((age * 1000).rounded()))
            return nil
        }
        return pending.target
    }
}

/// Where a new window on the same study opens: the report applies it once, the
/// way the link's own click would (`goToPlace`), and then forgets it.
struct WindowPlace: Codable, Hashable {
    let path: String
    let anchor: String?
    /// Play there, in that window's own player.
    let play: ContextPlace.Media?

    /// From a link's place. A new window plays only when asked and when there is
    /// a recording (D1: from a target whose click plays).
    init(place: ContextPlace, play: Bool) {
        self.path = place.path
        self.anchor = nil
        self.play = play ? place.media : nil
    }

    init(path: String, anchor: String?, play: ContextPlace.Media?) {
        self.path = path
        self.anchor = anchor
        self.play = play
    }

    /// The lens the path shows, for the new window's seed.
    var lens: Tab? { Tab.from(path: path.split(separator: "#", maxSplits: 1).first.map(String.init) ?? path) }

    /// The `goToPlace` menu action's payload.
    var payload: [String: Any] {
        var p: [String: Any] = ["path": path]
        if let anchor { p["anchor"] = anchor }
        if let play { p["play"] = ["key": play.key, "seconds": play.seconds] }
        return p
    }

    /// From an `open-in-new-window` message.
    static func from(message body: [String: Any]) -> WindowPlace? {
        guard let raw = body["place"] as? [String: Any],
              JSONSerialization.isValidJSONObject(raw),
              let data = try? JSONSerialization.data(withJSONObject: raw),
              let place = try? JSONDecoder().decode(ContextPlace.self, from: data),
              !place.path.isEmpty else { return nil }
        return WindowPlace(place: place, play: body["play"] as? Bool ?? false)
    }
}
