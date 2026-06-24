import Foundation

/// Substrate-free reproduction of `ProjectRow`'s subtitle **text** composition
/// (the i18n + date + CLDR-plural string production) for the native AppKit cell.
///
/// **Copied verbatim from `ProjectRow`, not shared by refactor.** Refactoring the
/// shipping flag-OFF SwiftUI row to share this would risk a regression in the
/// sidebar users run today, to serve the flag-ON WIP — a bad trade. `ProjectRow`'s
/// inline copy is deleted at cutover, leaving this as the single source; the
/// gallery diff + snapshot tests guard against transcription drift until then.
/// Every method cites the `ProjectRow.swift` lines it mirrors.
///
/// TEXT ONLY — the prefix/failure glyphs and trailing ring/affordances are the
/// cell's job (Phases 2–4). Returns `nil` for `.placeholder` (→ single-line row).
///
/// `@MainActor` because `I18n` is main-actor-isolated (the project defaults to
/// nonisolated); the cell builds on the main thread, same as `ProjectRow`.
@MainActor
enum SidebarSubtitleText {

    /// The visible subtitle string for a resolved variant, or `nil` when the row
    /// shows no subtitle line (`.placeholder`). Mirrors `ProjectRow.subtitleContent`
    /// (`ProjectRow.swift:228-277`) — text production only.
    static func text(for variant: SubtitleVariant,
                     availability: ProjectAvailability,
                     progress: PipelineProgress?,
                     i18n: I18n) -> String? {
        switch variant {
        case .cantFind:
            // Text + glyph both derive from `availability` (`:234`).
            return availability.subtitle(using: i18n)
        case .failed(let summary):
            return summary                                                   // :242-243
        case .failedDiagnostic:
            return i18n.t("desktop.pipeline.diagnostic.header.failed")       // :250-251
        case .completedPartial:
            return i18n.t("desktop.pipeline.diagnostic.header.completed_partial")  // :252-254
        case .stopping, .running, .queued, .stopped, .partial, .unreachable,
             .copying, .copyCancelling:
            return activityText(variant, progress: progress, separator: " · ", i18n: i18n)  // :255-259
        case .ready(let date, let delta):
            return readyText(date: date, delta: delta, i18n: i18n)           // :260-267
        case .deltaOnly(let delta):
            return deltaText(for: delta, i18n: i18n)                         // :268-272
        case .placeholder:
            return nil                                                       // :273-275 → collapse
        }
    }

    /// Localised text for the verb-led activity variants. Verbatim
    /// `ProjectRow.pipelineActivityText` (`:284-313`); `.running` composes the
    /// live ladder via the already-pure `RunProgressSubtitle`.
    static func activityText(_ variant: SubtitleVariant,
                             progress: PipelineProgress?,
                             separator: String,
                             i18n: I18n) -> String? {
        switch variant {
        case .stopping:
            return i18n.t("desktop.chrome.pipeline.stopping")
        case .running:
            return RunProgressSubtitle.compose(
                stage: progress?.stage,
                sessionsComplete: progress?.sessionsComplete,
                sessionsTotal: progress?.sessionsTotal,
                etaRemainingSeconds: progress?.etaRemainingSeconds,
                separator: separator,
                localize: { i18n.t($0, $1) }
            )
        case .queued(let position):
            return i18n.t("desktop.chrome.pipeline.queuedPosition", ["position": String(position)])
        case .stopped:
            return i18n.t("desktop.chrome.pipeline.stopped")
        case .partial(let transcribeOnly):
            return i18n.t(transcribeOnly
                ? "desktop.chrome.pipeline.transcribed"
                : "desktop.chrome.pipeline.partialRun")
        case .unreachable(let reason):
            return reason
        case .copying(let fraction):
            let percent = min(100, max(0, Int((fraction * 100).rounded())))
            return i18n.t("desktop.chrome.pipeline.copying", ["percent": String(percent)])
        case .copyCancelling:
            return i18n.t("desktop.chrome.copyCancelling")
        case .cantFind, .failed, .failedDiagnostic, .completedPartial,
             .ready, .deltaOnly, .placeholder:
            return nil
        }
    }

    /// `.ready` rendering: bare date, then `· <delta>` when a delta rides along
    /// (`ProjectRow.swift:260-267` — the visible string; the delta's *button-ness*
    /// for `.unanalysed` is the cell's job, Phase 4).
    static func readyText(date: Date, delta: SubtitleDelta?, i18n: I18n) -> String {
        let dateText = formatBareDate(date, i18n: i18n)
        guard let delta else { return dateText }
        return "\(dateText) · \(deltaText(for: delta, i18n: i18n))"
    }

    /// Delta segment → string. `ProjectRow.deltaSegment` (`:421-444`).
    static func deltaText(for delta: SubtitleDelta, i18n: I18n) -> String {
        switch delta {
        case .unanalysed(let count): return deltaText(prefix: "unanalysedSubtitle", count: count, i18n: i18n)
        case .missing(let count):    return deltaText(prefix: "missingSubtitle", count: count, i18n: i18n)
        }
    }

    /// CLDR-plural count phrase. Verbatim `ProjectRow.deltaText` (`:449-463`) —
    /// Czech needs one/few/many/other; ko/ja carry only `_other` (defensive fallback).
    static func deltaText(prefix: String, count: Int, i18n: I18n) -> String {
        let base = "desktop.chrome.\(prefix)"
        let key = "\(base)_\(i18n.pluralCategory(count))"
        let rendered = i18n.t(key, ["count": String(count)])
        if rendered == key {
            return i18n.t("\(base)_other", ["count": String(count)])
        }
        return rendered
    }

    /// Bare progressive-coarsen date. Verbatim `ProjectRow.formatBareDate`
    /// (`:528-557`) — Just now / Today / Yesterday / D MMM / MMM YYYY; future
    /// dates (clock skew) skip the relative branches.
    static func formatBareDate(_ date: Date, i18n: I18n) -> String {
        let appLocale = Locale(identifier: i18n.locale)
        let now = Date()
        let elapsed = now.timeIntervalSince(date)

        if elapsed >= 0 && elapsed < 5 * 60 {
            return i18n.t("desktop.chrome.dateRelativeJustNow")
        }

        let calendar = Calendar(identifier: .gregorian)
        if elapsed >= 0 {
            if calendar.isDateInToday(date) || calendar.isDateInYesterday(date) {
                return relative(date, now: now, locale: appLocale)
            }
        }

        let nowYear = calendar.component(.year, from: now)
        let dateYear = calendar.component(.year, from: date)
        let f = DateFormatter()
        f.locale = appLocale
        if dateYear == nowYear {
            f.setLocalizedDateFormatFromTemplate("d MMM")
        } else {
            f.setLocalizedDateFormatFromTemplate("MMM yyyy")
        }
        return f.string(from: date)
    }

    /// Named relative ("today"/"yesterday"), sentence-cased. Verbatim
    /// `ProjectRow.relative` (`:563-570`).
    static func relative(_ date: Date, now: Date, locale: Locale) -> String {
        let f = RelativeDateTimeFormatter()
        f.locale = locale
        f.dateTimeStyle = .named
        f.unitsStyle = .full
        let s = f.localizedString(for: date, relativeTo: now)
        return s.prefix(1).uppercased() + s.dropFirst()
    }
}
