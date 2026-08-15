import Foundation

/// The three meeting platforms, and everything about them the shared import
/// surface needs in order to speak each one's language.
///
/// This type exists because of a rule the codebase already holds twice over
/// (`feedback_shared_taxonomy_render_native_per_surface`): share the taxonomy,
/// render it natively per surface. One window, one state machine, one set of
/// row states — but the *words* are the vendor's, and getting them wrong is not
/// a style problem. Microsoft's brand guidelines permit exactly two strings on
/// their sign-in button and forbid three synonyms for the account noun; Google
/// requires its own unaltered mark; Zoom has its own.
///
/// So: everything platform-shaped that the UI says lives here, and the window
/// reads it. A `switch` in a view body is the smell this replaces.
enum CloudPlatform: String, CaseIterable, Identifiable, Sendable {
    case teams
    case meet
    case zoom

    var id: String { rawValue }

    /// The platforms with a live adapter, in the order `docs/design-cloud-import.md`
    /// §5 sequences them.
    ///
    /// The File menu reads this, not `allCases`: a menu item that opens a
    /// window which then says "not built yet" is worse than no item, because a
    /// menu is a promise about what the app can do. `allCases` still drives the
    /// Diagnostics fixture menu, where seeing an unbuilt platform's states is
    /// the entire point.
    static var shipping: [CloudPlatform] { [.meet] }

    // MARK: Naming

    /// The full product name, used in menus and window titles for parallelism
    /// (`docs/design-cloud-import.md` §9: the submenu "takes the fuller product
    /// name there").
    var displayName: String {
        switch self {
        case .teams: return "Microsoft Teams"
        case .meet:  return "Google Meet"
        case .zoom:  return "Zoom"
        }
    }

    /// The window title. "Import from X" reads as the act, which is what a
    /// window title should name.
    var windowTitle: String { "Import from \(displayName)" }

    /// The vendor's own sign-in string. **Look these up; never compose them.**
    ///
    /// Microsoft permits "Sign in with Microsoft" or bare "Sign in" and nothing
    /// else — "Sign in *to* Microsoft" is not a permitted variant. Google
    /// specifies "Sign in with Google" beside its unaltered mark. Both publish
    /// localised strings, so the 21 translations are *looked up* rather than
    /// machine-translated — the same trick as the `TCC.loctable` lift for the
    /// macOS permission prompt, third vendor.
    var signInTitle: String {
        switch self {
        case .teams: return "Sign in with Microsoft"
        case .meet:  return "Sign in with Google"
        case .zoom:  return "Sign in with Zoom"
        }
    }

    /// What the account is called, in the vendor's own words.
    ///
    /// Microsoft mandates "work or school account" and explicitly forbids
    /// "enterprise account", "business account" and "corporate account" — and
    /// forbids *Azure* and *Active Directory* anywhere an end user can see
    /// them. Google has no equivalent requirement, and naming the account type
    /// there would actively mislead: a personal Google Account signs in
    /// perfectly and can never hold a recording.
    var accountNoun: String? {
        switch self {
        case .teams: return "work or school account"
        case .meet:  return nil
        case .zoom:  return nil
        }
    }

    /// SF Symbol for menus. A placeholder in every case: each vendor requires
    /// its own unaltered mark on the sign-in button, shipped as an official
    /// asset rather than redrawn.
    var symbolName: String {
        switch self {
        case .teams: return "person.2.badge.gearshape"
        case .meet:  return "video"
        case .zoom:  return "video.badge.waveform"
        }
    }

    // MARK: Capability differences the UI must render

    /// Whether the platform exposes a per-file expiry the list can count down.
    ///
    /// Teams: **yes** — its own product shows "Expires in 4 days" on exactly
    /// this data, which is the affordance §9 proposes, already validated by the
    /// vendor.
    ///
    /// Meet: **no.** Drive's file resource has no expiration field of any kind;
    /// retention is an admin policy. The column is omitted rather than filled
    /// with em-dashes, because a column of em-dashes pretending to be data is
    /// worse than an absent one. (Note the *conference record* does expire at
    /// 30 days — but that governs the transcript and metadata, not the MP4.)
    ///
    /// Zoom: **pending** — an auto-delete setting exists at account level; the
    /// open question is whether it surfaces per recording. Set from research
    /// before the adapter ships, and do not guess: guessing `true` here draws a
    /// countdown column that silently reads "—" on every row.
    var hasPerFileExpiry: Bool {
        switch self {
        case .teams: return true
        case .meet:  return false
        case .zoom:  return false
        }
    }

    /// Whether a meeting can yield more than one media file, so the adapter has
    /// to *choose* rather than take the only one.
    ///
    /// Zoom is the one that does: a single meeting commonly returns several
    /// MP4s (speaker view, gallery view, shared screen) plus an M4A, and taking
    /// the first is how a study ends up analysing a screen-share with no face
    /// in it. Teams and Meet each yield one video.
    var yieldsMultipleMediaFiles: Bool {
        switch self {
        case .zoom:         return true
        case .teams, .meet: return false
        }
    }

    /// Whether the platform serves a speaker-attributed transcript on a scope
    /// we are willing to hold.
    ///
    /// Meet: yes — `conferenceRecords.transcripts.entries` gives per-utterance
    /// participant, timings and text on a *sensitive* scope.
    /// Teams: no — `OnlineMeetingTranscript.Read.All` is admin-consent-only.
    /// Zoom: pending research; the VTT rides the same call as the video, which
    /// would make Zoom the only platform where §8's comparison can be asked
    /// cheaply.
    var servesTranscript: Bool {
        switch self {
        case .meet:  return true
        case .teams: return false
        case .zoom:  return false
        }
    }
}
