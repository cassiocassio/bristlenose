import Foundation

/// Why a project can't be scanned right now — the payload of
/// `PipelineState.unreachable`.
///
/// **This exists because the payload used to be a `String`.** Five English
/// sentences were written into `PipelineRunner` (the oldest on 20 Apr 2026, two
/// months before the `MessageKind` taxonomy was settled) and rendered verbatim
/// by the sidebar: `case .unreachable(let reason): return reason`. That made it
/// the one case in `SubtitleVariant` carrying a baked display string, against
/// that enum's own doc-comment ("cases carry **raw** data … never a baked,
/// localised, or date-formatted string"). The consequences were all invisible to
/// gates: no locale key existed in *any* file including `en`, so
/// `check-locales.py` was green in all 21 locales — a key absent from English
/// cannot be reported missing (`CLAUDE.md`, the third i18n blind spot); the row
/// carried no `MessageKind`, so `subtitlePrefixGlyph`'s `default:` arm drew no
/// glyph and there was nothing to click; and four of the five strings overflowed
/// the ~22-char sidebar budget in English, before any locale swell.
///
/// A `String` payload on an enum case is an unchecked hole in a checked system.
/// Every other `SubtitleVariant` case carries data the view must *interpret* —
/// a `Date`, a count, an enum. This one carried a finished sentence, so the view
/// had no decision left to get wrong and no gate had anything to inspect.
///
/// Keep it an enum. If a new unreachable condition appears, add a case here (the
/// compiler will then demand a kind, a label and an explanation) rather than
/// reaching for a string.
///
/// Audited 26 Aug 2026; `docs/design-pipeline-diagnostic-popover.md` §303 had
/// specified the glyph + greyed row for this state all along.
enum UnreachableReason: String, Codable, Equatable, CaseIterable, Sendable {

    /// The manifest read exceeded its 5 s timeout — a sleeping drive or a
    /// disconnected network share, typically. Nothing has failed; the read may
    /// well succeed on the next poll.
    case timedOut

    /// The read threw. The folder is present but its contents can't be got at
    /// (permissions, I/O error).
    case unreadable

    /// The project's parent directory isn't there at all.
    case folderMissing

    /// A manifest is present but won't parse.
    case damaged

    /// The scan task group returned no result. Defensive — not reachable in
    /// normal operation, kept so the `guard` has something honest to return.
    case scanFailed

    /// The `MessageKind` this reason renders as, per the operational rule
    /// settled 18 Jun 2026 (`docs/design-desktop-project-status.md` §"The kinds"):
    /// the discriminator is **usability + whether it self-resolves**, not cause.
    ///
    /// - `warning` — a human needs to look, but nothing failed and it may come
    ///   back on its own (a remounted volume, a woken drive).
    /// - `error` — the project cannot be used as it stands; something must change.
    ///
    /// Mirrors the ruling for `.cantFind`, which is `warning` for the same
    /// reason ("project not usable" ≠ "run failed").
    var kind: MessageKind {
        switch self {
        case .timedOut, .folderMissing:
            return .warning
        case .unreadable, .damaged, .scanFailed:
            return .error
        }
    }

    /// Locale key for the **sidebar** subtitle — the short form. Budget is
    /// ~22 EN chars before DE/ES/FR swell truncates (`ProjectRow.swift`), and no
    /// terminal punctuation: nothing else in the subtitle vocabulary has any
    /// ("Stopped", "Partial run", "Transcribed", "Analysing…").
    var localeKey: String {
        "desktop.chrome.pipeline.unreachable.\(rawValue)"
    }

    /// Locale key for the **popover** explanation — one sentence, same register
    /// and em-dash construction as the shipped `desktop.pipeline.diagnostic.reason.*`
    /// family it sits beside.
    var explanationKey: String {
        "desktop.pipeline.diagnostic.unreachable.\(rawValue)"
    }
}
