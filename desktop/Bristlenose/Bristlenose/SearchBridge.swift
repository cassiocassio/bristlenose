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

    /// Stable for the subject (`text`, `person:<code>`, `tag:<name>`); sent
    /// back as-is when the row is chosen.
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
        let label: String
        let enabled: Bool
    }

    enum Kind: String { case person, tag }

    let kind: Kind
    let subject: SearchSubject
    /// Key into the SPA's badge styles (a speaker code, or a tag name already
    /// folded by the SPA), so this side never has to reproduce its folding.
    let styleKey: String
    let label: String
    let mode: String
    let modes: [Mode]

    var id: SearchSubject { subject }

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
        self.mode = mode
        self.modes = (d["modes"] as? [[String: Any]] ?? []).compactMap { m in
            guard let id = m["id"] as? String, let label = m["label"] as? String else { return nil }
            return Mode(id: id, label: label, enabled: m["enabled"] as? Bool ?? true)
        }
    }

    static func decodeAll(_ wire: Any?) -> [SearchTokenChip] {
        (wire as? [Any] ?? []).compactMap(SearchTokenChip.init(wire:))
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
}
