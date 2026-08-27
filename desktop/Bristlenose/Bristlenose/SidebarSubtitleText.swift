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
        case .failed:
            // **Not the summary.** `.failed` used to pass Python's raw sentence
            // straight through — "All topic segmentation calls failed." is 36
            // chars against a ~22-char row budget, so it truncated mid-phrase in
            // English, before any locale swell. Its sibling `.failedDiagnostic`
            // had already solved this: a short localised header on the row, the
            // detail in the popover. Which of the two a researcher saw depended
            // only on whether Python happened to write a `summary` field, so the
            // row said different things about the same event. Now both say
            // "Run failed"; the summary is rendered by `degradedBody` in
            // `ProjectDiagnosticPopover`, which is sized for it. (26 Aug 2026.)
            return i18n.t("desktop.pipeline.diagnostic.header.failed")
        case .failedDiagnostic:
            return i18n.t("desktop.pipeline.diagnostic.header.failed")       // :250-251
        case .completedPartial:
            return i18n.t("desktop.pipeline.diagnostic.header.completed_partial")  // :252-254
        case .stopping, .running, .queued, .stopped, .partial, .unreachable,
             .addingInterviews, .copying, .importingBatch, .copyCancelling:
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
        case .importingBatch(let done, let total):
            // **The whole sentence, and it has no verb.**
            // `docs/mockups/cloud-import-sidebar-progress.html` §3: "the
            // download phase needs no verb at all — '3 of 4' is the whole
            // sentence." A count rather than a percentage or an ETA, because a
            // count is the question a closed window leaves: not how fast, not
            // which file, but how many are still to wait for.
            return i18n.t("desktop.chrome.pipeline.importBatch",
                          ["done": String(done), "total": String(total)])
        case .stopping:
            return i18n.t("desktop.chrome.pipeline.stopping")
        case .running:
            return RunProgressSubtitle.compose(
                stage: progress?.stage,
                sessionsComplete: progress?.sessionsComplete,
                sessionsTotal: progress?.sessionsTotal,
                etaRemainingSeconds: progress?.etaRemainingSeconds,
                resuming: progress?.attachedFromOrphan ?? false,
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
            return i18n.t(reason.localeKey)
        case .addingInterviews(let count):
            return i18n.plural("desktop.chrome.addingInterviews", count: count)
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

    /// CLDR-plural count phrase. Mirrors `ProjectRow.deltaText` — Czech needs
    /// one/few/many/other; ko/ja carry only `_other`. Selection + `_other`
    /// fallback both live in `I18n.plural`.
    static func deltaText(prefix: String, count: Int, i18n: I18n) -> String {
        i18n.plural("desktop.chrome.\(prefix)", count: count)
    }

    /// The composed hover tooltip — everything the one-line subtitle could not
    /// say. Mirrors `ProjectRow.rowTooltip` (`ProjectRow.swift:617-640`).
    ///
    /// **A v1 stopgap, and deliberately not the design.** `design-desktop-
    /// project-status.md` §5 fixes one condition per line and forbids composing
    /// two, so a running project's drift and a drifted project's session count
    /// are *deliberately* dropped from the visible row. §5 names **the detail
    /// pane** as where the non-winners get room — "that's its reason to exist".
    /// It does not say hover. This tooltip is `ProjectRow`'s own local answer,
    /// ported here only so the AppKit cell isn't strictly worse than the row it
    /// replaces; the intended direction is a cycling departure-board line that
    /// shows each condition in turn, which is a real design and not this.
    ///
    /// So: **do not grow this.** Hover is a rock to look under — it is
    /// undiscoverable, unavailable to touch and keyboard, and every segment
    /// added here is one the row should have found a way to say. If you are
    /// reaching for it to surface something new, that is the signal the row
    /// needs the departure board, not that the tooltip needs another clause.
    ///
    /// PII: **counts only — never interpolate `newFiles` / `missingFiles`
    /// basenames.** Accessibility services have system-wide read access, and the
    /// watcher's filenames-stay-UI-only invariant means rendered text and
    /// nothing else. `RunProgressEvent` is counts/timings, so the progress
    /// ladder is safe to lead with.
    ///
    /// Returns `nil` when there is nothing to add, so the caller can leave
    /// `toolTip` unset rather than showing an empty bubble.
    static func tooltip(for variant: SubtitleVariant,
                        data: UnanalysedState?,
                        progress: PipelineProgress?,
                        i18n: I18n) -> String? {
        var parts: [String] = []
        // Lead with the FULL progress ladder while a run is in flight: the
        // visible subtitle truncates it on a narrow column, so hover is also
        // where the untruncated form lives. `.stopping` is excluded — it
        // outranks progress and has nothing to expand.
        if case .running = variant,
           let ladder = activityText(variant, progress: progress,
                                     separator: " · ", i18n: i18n) {
            parts.append(ladder)
        }
        if let count = data?.sessionCount {
            parts.append(deltaText(prefix: "interviewCount", count: count, i18n: i18n))
        }
        if let data {
            if !data.newFiles.isEmpty {
                parts.append(i18n.t("desktop.chrome.tooltipWaiting",
                                    ["count": String(data.newFiles.count)]))
            }
            if !data.missingFiles.isEmpty {
                parts.append(deltaText(prefix: "missingSubtitle",
                                       count: data.missingFiles.count, i18n: i18n))
            }
        }
        return parts.isEmpty ? nil : parts.joined(separator: " · ")
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
