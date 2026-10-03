import Foundation

// The Quotes search menu and tokens as they arrive from the SPA, and the
// choices the native field sends back (docs/design-search.md §7).
//
// The SPA recognises, counts and localises; this side only decodes what to
// draw and encodes what was chosen. So nothing here holds a locale key, and
// every label is shown as it arrives. The shapes are pinned on both sides by
// tests/fixtures/search-bridge-contract.json (BridgeSearchContractTests here,
// searchBridge.test.ts in the SPA).
//
// Tolerance: a newer SPA may send a kind this app does not know. That row or
// token is dropped and the rest kept; a message is never rejected whole,
// because a dropped menu reads as "search is broken" and a dropped row only as
// "one fewer suggestion".

/// A person or a tag — how the SPA addresses a token. Never a position: the
/// list can change between drawing a menu and clicking it.
enum SearchSubject: Equatable, Hashable {
    case person(code: String)
    case tag(name: String)

    init?(wire: Any?) {
        guard let dict = wire as? [String: Any], let kind = dict["kind"] as? String else { return nil }
        switch kind {
        case "person":
            guard let code = dict["code"] as? String, !code.isEmpty else { return nil }
            self = .person(code: code)
        case "tag":
            guard let name = dict["name"] as? String, !name.isEmpty else { return nil }
            self = .tag(name: name)
        default:
            return nil
        }
    }

    /// The payload the SPA's `parseSubject` reads.
    var wire: [String: Any] {
        switch self {
        case .person(let code): return ["kind": "person", "code": code]
        case .tag(let name): return ["kind": "tag", "name": name]
        }
    }
}

/// One row of the native search menu.
struct SearchSuggestionRow: Equatable, Identifiable {
    enum Kind: String { case text, person, tag }

    /// Stable for the subject (`text`, `person:<code>`, `tag:<folded name>`);
    /// sent back as-is when the row is chosen. A badge style is keyed by the
    /// part after the prefix.
    let id: String
    let kind: Kind
    /// Localised by the SPA, drawn as-is.
    let label: String
    /// Where the typed words fall in `label`, as UTF-16 [start, end) offsets.
    let typed: [Range<Int>]
    let count: Int
    /// Person rows: the speaker code the badge shows.
    let code: String?

    init?(wire: Any) {
        guard let d = wire as? [String: Any],
              let id = d["id"] as? String,
              let kindRaw = d["kind"] as? String, let kind = Kind(rawValue: kindRaw),
              let label = d["label"] as? String,
              let count = d["count"] as? Int
        else { return nil }
        self.id = id
        self.kind = kind
        self.label = label
        self.count = count
        self.code = d["code"] as? String
        let pairs = d["typed"] as? [[Int]] ?? []
        let length = label.utf16.count
        // A malformed or out-of-range pair is dropped, not trusted: emphasis
        // drawn on the wrong letters is worse than none.
        self.typed = pairs.compactMap { pair in
            guard pair.count == 2, pair[0] >= 0, pair[0] < pair[1], pair[1] <= length else { return nil }
            return pair[0]..<pair[1]
        }
    }

    /// `typed` as ranges of `label` itself. Offsets are UTF-16, the unit of a
    /// JS string, so they are walked on the `utf16` view — counting
    /// `Character`s instead would put the emphasis on the wrong letters after
    /// any emoji or accented letter written as two code points.
    var typedRanges: [Range<String.Index>] {
        let utf16 = label.utf16
        return typed.compactMap { r in
            let lo = utf16.index(utf16.startIndex, offsetBy: r.lowerBound)
            let hi = utf16.index(utf16.startIndex, offsetBy: r.upperBound)
            guard let start = lo.samePosition(in: label), let end = hi.samePosition(in: label) else {
                return nil  // the range splits a character: draw no emphasis rather than half of one
            }
            return start..<end
        }
    }
}

/// The menu as a whole: the query it answers, and its rows. Empty rows close it.
struct SearchSuggestions: Equatable {
    var query: String
    var rows: [SearchSuggestionRow]

    static let empty = SearchSuggestions(query: "", rows: [])

    init(query: String, rows: [SearchSuggestionRow]) {
        self.query = query
        self.rows = rows
    }

    init(message body: [String: Any]) {
        query = body["query"] as? String ?? ""
        rows = (body["rows"] as? [Any] ?? []).compactMap(SearchSuggestionRow.init(wire:))
    }
}

/// A token in the search field, with the meanings its menu offers.
struct SearchTokenChip: Equatable, Identifiable {
    struct Mode: Equatable, Identifiable {
        let id: String
        /// The menu item: "Said by Priya Shah".
        let label: String
        /// The chip's word while this meaning is chosen: "said by".
        let word: String
        let enabled: Bool
    }

    enum Kind: String { case person, tag }

    let kind: Kind
    let subject: SearchSubject
    /// Key into the SPA's badge styles (a speaker code, or a tag name already
    /// folded by the SPA), so this side never has to reproduce its folding.
    let styleKey: String
    let label: String
    /// The last item of the chip's menu ("Remove"); empty from an SPA that
    /// predates it, in which case the menu has no Remove (Esc and ⓧ still clear).
    let removeLabel: String
    let mode: String
    let modes: [Mode]

    var id: SearchSubject { subject }

    /// The word the chip shows before its badge.
    var word: String { modes.first { $0.id == mode }?.word ?? "" }

    init?(wire: Any) {
        guard let d = wire as? [String: Any],
              let kindRaw = d["kind"] as? String, let kind = Kind(rawValue: kindRaw),
              let subject = SearchSubject(wire: d["subject"]),
              let label = d["label"] as? String,
              let mode = d["mode"] as? String
        else { return nil }
        self.kind = kind
        self.subject = subject
        self.styleKey = d["styleKey"] as? String ?? ""
        self.label = label
        self.removeLabel = d["removeLabel"] as? String ?? ""
        self.mode = mode
        self.modes = (d["modes"] as? [[String: Any]] ?? []).compactMap { m in
            guard let id = m["id"] as? String, let label = m["label"] as? String else { return nil }
            return Mode(id: id, label: label, word: m["word"] as? String ?? "",
                        enabled: m["enabled"] as? Bool ?? true)
        }
    }

    static func decodeAll(_ wire: Any?) -> [SearchTokenChip] {
        (wire as? [Any] ?? []).compactMap(SearchTokenChip.init(wire:))
    }
}

/// A colour in display-P3, each component 0…1, as the SPA measured it.
struct BadgeColour: Equatable {
    let red: Double
    let green: Double
    let blue: Double
    let opacity: Double

    init(red: Double, green: Double, blue: Double, opacity: Double) {
        self.red = red
        self.green = green
        self.blue = blue
        self.opacity = opacity
    }

    init?(wire: Any?) {
        guard let d = wire as? [String: Any],
              let r = SearchBadgeStyle.number(d["r"]), let g = SearchBadgeStyle.number(d["g"]),
              let b = SearchBadgeStyle.number(d["b"]), let a = SearchBadgeStyle.number(d["a"])
        else { return nil }
        let unit = { (x: Double) in min(max(x, 0), 1) }
        self.init(red: unit(r), green: unit(g), blue: unit(b), opacity: unit(a))
    }
}

/// How one badge is drawn, measured by the SPA from the report's own CSS
/// (docs/design-search.md §7a), so a chip in the native field matches the
/// badge on the card without this side knowing any colour or size.
struct SearchBadgeStyle: Equatable {
    enum Family: String { case mono, body }

    struct Border: Equatable {
        let colour: BadgeColour
        let width: Double
    }

    /// Nil when the badge has no fill.
    let fill: BadgeColour?
    let text: BadgeColour
    let border: Border?
    let family: Family
    /// CSS pixels, which are points.
    let size: Double
    /// CSS font weight, 100…900.
    let weight: Double
    /// Left and top padding (the names readers that pad symmetrically use).
    let padX: Double
    let padY: Double
    /// Right and bottom padding. A person's name half is padded on one side
    /// only; an older SPA that sends neither means "as left and top".
    let padRight: Double
    let padBottom: Double
    /// The line box in points, or nil when the CSS left it `normal`.
    let lineHeight: Double?
    let radius: Double

    init?(wire: Any?) {
        guard let d = wire as? [String: Any],
              let text = BadgeColour(wire: d["fg"]),
              let size = Self.number(d["sizePx"]), size > 0,
              let weight = Self.number(d["weight"]),
              let padX = Self.number(d["padX"]), let padY = Self.number(d["padY"]),
              let radius = Self.number(d["radius"])
        else { return nil }
        // Absent and null both mean "none"; a fill or border that is present
        // but unreadable is dropped rather than drawn wrong.
        self.fill = BadgeColour(wire: d["bg"])
        if let b = d["border"] as? [String: Any], let colour = BadgeColour(wire: b["colour"]),
           let width = Self.number(b["widthPx"]), width > 0 {
            self.border = Border(colour: colour, width: width)
        } else {
            self.border = nil
        }
        self.text = text
        // A family a newer SPA adds is drawn in the body font: degraded, not wrong.
        self.family = (d["fontFamily"] as? String).flatMap(Family.init(rawValue:)) ?? .body
        self.size = size
        self.weight = min(max(weight, 100), 900)
        self.padX = max(padX, 0)
        self.padY = max(padY, 0)
        self.padRight = max(Self.number(d["padRight"]) ?? padX, 0)
        self.padBottom = max(Self.number(d["padBottom"]) ?? padY, 0)
        self.lineHeight = Self.number(d["lineHeightPx"]).flatMap { $0 > 0 ? $0 : nil }
        self.radius = max(radius, 0)
    }

    /// A finite JSON number. `JSONSerialization` hands numbers over as
    /// `NSNumber`, which bridges to `Double` whether it was written 12 or 12.0;
    /// a JSON boolean also bridges, so it is refused by its type first.
    static func number(_ value: Any?) -> Double? {
        guard let n = value as? NSNumber, CFGetTypeID(n) != CFBooleanGetTypeID() else { return nil }
        let x = n.doubleValue
        return x.isFinite ? x : nil
    }
}

/// A person's badge: the speaker code, and the name beside it when the report
/// shows one.
struct SearchPersonBadgeStyle: Equatable {
    let code: SearchBadgeStyle
    let name: SearchBadgeStyle?

    init?(wire: Any?) {
        guard let d = wire as? [String: Any], let code = SearchBadgeStyle(wire: d["code"]) else {
            return nil
        }
        self.code = code
        // A malformed name half draws the code alone rather than losing the badge.
        self.name = SearchBadgeStyle(wire: d["name"])
    }
}

/// The styles of every badge the menu and chips currently show
/// (`search-badge-styles`). Each message replaces the last. Tags are keyed by
/// folded name (a row's id after `tag:`, a token's `styleKey`), people by code.
struct SearchBadgeStyles: Equatable {
    var tags: [String: SearchBadgeStyle]
    var people: [String: SearchPersonBadgeStyle]

    static let empty = SearchBadgeStyles(tags: [:], people: [:])

    init(tags: [String: SearchBadgeStyle], people: [String: SearchPersonBadgeStyle]) {
        self.tags = tags
        self.people = people
    }

    init(message body: [String: Any]) {
        tags = (body["tags"] as? [String: Any] ?? [:]).compactMapValues(SearchBadgeStyle.init(wire:))
        people = (body["people"] as? [String: Any] ?? [:]).compactMapValues(SearchPersonBadgeStyle.init(wire:))
    }

    /// A person row's badge style. A token looks up `people[styleKey]` directly.
    func personStyle(for row: SearchSuggestionRow) -> SearchPersonBadgeStyle? {
        guard row.kind == .person, let code = row.code else { return nil }
        return people[code]
    }

    /// A tag row's badge style. A token looks up `tags[styleKey]` directly.
    func tagStyle(for row: SearchSuggestionRow) -> SearchBadgeStyle? {
        guard row.kind == .tag, row.id.hasPrefix("tag:") else { return nil }
        return tags[String(row.id.dropFirst("tag:".count))]
    }
}

/// What the native field sends back, as `(action, payload)` for
/// `BridgeHandler.menuAction`. Pure, so the contract test can compare them with
/// the fixture without a web view.
enum SearchBridgeAction {
    static func applySuggestion(id: String) -> (String, [String: Any]) {
        ("applySearchSuggestion", ["id": id])
    }

    static func setTokenMode(_ subject: SearchSubject, mode: String) -> (String, [String: Any]) {
        ("setSearchTokenMode", ["subject": subject.wire, "mode": mode])
    }

    static func removeToken(_ subject: SearchSubject) -> (String, [String: Any]) {
        ("removeSearchToken", ["subject": subject.wire])
    }

    /// The field's clear button or Esc: the text and every token.
    static func clear() -> (String, [String: Any]) {
        ("clearSearch", [:])
    }
}
