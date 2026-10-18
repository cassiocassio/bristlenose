import Foundation

/// How far a Miro board build has got — the server's `BoardBuild` (`routes/miro.py`), the same
/// for the quotes board and the screens board.
///
/// `phase` names what `count_done`/`count_total` count: `preparing` (screenshots, before any Miro
/// call), `opening` (the board and its first frames — Miro refuses a new board's frames for about
/// half a minute, so no fraction or estimate is claimed), then `quotes`, `groups` or `screens`.
/// `fraction` is the share of the board's Miro calls made; `eta_seconds` is nil until every kind of
/// call still to come has an earned rate, from this build or kept from earlier ones on this machine
/// (the pipeline's thresholds, `bristlenose/board_progress.py`).
struct MiroBoardBuild: Decodable, Equatable {
    let phase: String
    let done: Int
    let total: Int
    let count_done: Int
    let count_total: Int
    let waiting: Bool
    let fraction: Double?
    let eta_seconds: Double?
}

/// What the sheet says while a board builds — the web panel's `buildLine`/`etaLine`, so both
/// surfaces say the same. Pure, so the decision is tested without a sheet.
enum MiroBoardBuildText {
    /// The line's key and its counts. A count rather than a percentage, because a count is the
    /// question a glance asks; Miro's own waits are said as waiting, except while the board is
    /// opening, whose line already explains the wait.
    static func lineKey(_ build: MiroBoardBuild?) -> (key: String, vars: [String: String]) {
        guard let b = build else { return ("common.miro.creatingBoard", [:]) }
        if b.waiting && b.phase != "opening" { return ("common.miro.progressWaiting", [:]) }
        let counts = ["done": String(b.count_done), "total": String(b.count_total)]
        switch b.phase {
        case "preparing": return ("common.miro.progressPreparing", counts)
        case "opening": return ("common.miro.progressOpening", [:])
        case "quotes": return ("common.miro.progressQuotes", counts)
        // No long quote to group: only the title is left, a single call.
        case "groups": return b.count_total > 0 ? ("common.miro.progressGroups", counts)
                                                 : ("common.miro.creatingBoard", [:])
        case "screens": return ("common.miro.progressScreens", counts)
        default: return ("common.miro.creatingBoard", [:])
        }
    }

    static func line(_ build: MiroBoardBuild?, localize: (String, [String: String]) -> String) -> String {
        let (key, vars) = lineKey(build)
        return localize(key, vars)
    }

    /// The bar's value, or nil for the indeterminate bar: no honest fraction yet.
    static func fraction(_ build: MiroBoardBuild?) -> Double? {
        guard let f = build?.fraction, f.isFinite else { return nil }
        return min(1, max(0, f))
    }

    /// Time left, in the run's own words (`RunProgressSubtitle.etaText`): whole minutes, or
    /// "<1 min". Nothing until the server has earned an estimate.
    static func eta(_ build: MiroBoardBuild?, localize: (String, [String: String]) -> String) -> String? {
        RunProgressSubtitle.etaText(build?.eta_seconds, localize: localize)
    }
}
