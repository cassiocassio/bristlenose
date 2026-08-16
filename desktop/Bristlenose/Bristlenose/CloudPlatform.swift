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
    /// §5 sequences them. **Built, not necessarily offered** — see `shipping`.
    static let built: [CloudPlatform] = [.teams, .meet, .zoom]

    /// Which of `built` the UI actually offers, given the parking flags.
    ///
    /// Pure and injectable so the parking rule is testable without touching
    /// `UserDefaults` — a test that read the live flag would pass or fail based
    /// on the developer's own machine, which is the environment-dependence CI
    /// has burned this project on before.
    static func offered(zoomEnabled: Bool) -> [CloudPlatform] {
        built.filter { $0 != .zoom || zoomEnabled }
    }

    /// The platforms offered in `File ▸ Import`, right now, on this machine.
    ///
    /// The File menu reads this, not `allCases`: a menu item that opens a
    /// window which then says "not built yet" is worse than no item, because a
    /// menu is a promise about what the app can do. `allCases` still drives the
    /// Diagnostics fixture menu, where seeing a parked platform's states is
    /// the entire point.
    ///
    /// **Zoom is parked here as of 16 Aug 2026** (`BristlenoseFlags.cloudImportZoom`,
    /// default off) so Teams and Meet can reach releasable quality first. The
    /// adapter is complete and still compiled, tested and fixture-driveable;
    /// only the menu item is withheld. Any future import surface — the project
    /// context-menu twin, a Settings ▸ Accounts pane — should read `shipping`
    /// and inherit the parking rather than re-deriving it.
    static var shipping: [CloudPlatform] {
        offered(zoomEnabled: BristlenoseFlags.cloudImportZoom)
    }

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
    /// Zoom: **yes, but derived rather than served.** There is no per-file
    /// expiry field; there is an account setting, `auto_delete_cmr` with
    /// `auto_delete_cmr_days`, readable from `GET /users/me/settings`. Add the
    /// days to a recording's own start time and every row has a real, correct
    /// countdown — computed once from one preflight call rather than fetched
    /// per row. When auto-delete is off the column is genuinely empty, which is
    /// the honest answer and not a gap.
    ///
    /// So the rule is not "does the API return an expiry date" but "can this
    /// platform tell the researcher how long they have". Teams and Zoom can;
    /// Drive cannot, at all.
    var hasPerFileExpiry: Bool {
        switch self {
        case .teams, .zoom: return true
        case .meet:         return false
        }
    }

    /// How far back this platform can honestly be asked to look, shortest
    /// first. The first entry is the default.
    ///
    /// **A window is a query bound, not a claim about what exists** — and the
    /// two come apart badly on one of these platforms, which is why this is a
    /// per-platform property rather than a constant.
    ///
    /// Google's recording lives in Drive indefinitely, but the *conference
    /// record* — the only route from a calendar event to that file — expires,
    /// documented at 30 days. So a 90-day window there returns sixty days of
    /// meetings whose recordings exist, are perfectly downloadable, and read
    /// "Not recorded". Systematic false negatives, indistinguishable from the
    /// honest kind.
    ///
    /// **All three still offer 30/60/90 today, deliberately.** The 30-day
    /// ceiling is documented and not measured, and removing an affordance on a
    /// number we have not seen would hide two thirds of a researcher's
    /// recordings if the documentation is stale. `conferenceRecords` carries
    /// `expireTime`; one live listing settles it, and then `.meet` shrinks to
    /// `[30]` here and nowhere else — the picker hides itself at one choice,
    /// so that change costs no UI work.
    ///
    /// Deliberately **no "All available"**: it would mean 30 days on Google
    /// whatever it said, and "whatever your admin chose, which we cannot read"
    /// on Teams. A control that lies on one platform and shrugs on another is
    /// worse than its absence.
    var windowChoices: [Int] {
        switch self {
        case .teams, .meet, .zoom: return [30, 60, 90]
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

    /// Whether a sign-in commonly stalls on someone else's approval, with no
    /// error ever reaching this app.
    ///
    /// **This is the failure that has no error code, and it is not rare.** On
    /// Zoom, Marketplace pre-approval is enabled *by default* for every
    /// multi-seat account, and the block is enforced on Zoom's own consent
    /// screen — before any redirect. The researcher clicks Sign In, reads a
    /// page telling them to ask their admin, and comes back to an app that is
    /// still spinning. Nothing failed; nothing arrived. Teams has the same
    /// shape via Entra's user-consent policy ("Need admin approval").
    ///
    /// Google is the exception: a Workspace admin can restrict apps, but there
    /// is no equivalent default-on gate, so promising a Google user that their
    /// admin might be the problem would be a guess.
    ///
    /// The UI consequence: when a sign-in ends without credentials on these
    /// platforms, the copy must offer "your admin may need to approve this"
    /// alongside "you cancelled" — because the two are indistinguishable from
    /// here, and only one of them is the researcher's own doing.
    var signInMayAwaitAdminApproval: Bool {
        switch self {
        case .zoom, .teams: return true
        case .meet:         return false
        }
    }

    /// Whether the platform serves a speaker-attributed transcript on a scope
    /// we are willing to hold.
    ///
    /// Meet: yes — `conferenceRecords.transcripts.entries` gives per-utterance
    /// participant, timings and text on a *sensitive* scope.
    /// Teams: no — `OnlineMeetingTranscript.Read.All` is admin-consent-only.
    /// Zoom: **yes, and on the same call as the video** — a `TRANSCRIPT` file
    /// in VTT, speaker names carried as a `Name: ` prefix in each cue.
    /// Conditional on the host's "Create audio transcript" setting and, on
    /// every plan, **English only** — which excludes more real researchers than
    /// any tier boundary and is invisible until a VTT fails to arrive. So this
    /// flag says the platform *can*; `ZoomPreflight` says whether this account
    /// *will*.
    ///
    /// Both Meet and Zoom therefore make §8's comparison askable. Meet's is the
    /// better artefact (per-utterance, participant-resolved); Zoom's is the
    /// cheaper to obtain (no second call, no extra scope).
    var servesTranscript: Bool {
        switch self {
        case .meet, .zoom: return true
        case .teams:       return false
        }
    }
}
