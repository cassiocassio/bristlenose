import Foundation

/// The rows of Settings ▸ MCP Agents ▸ Projects, derived.
///
/// **What this list is.** A register of what you have shared or might be
/// sharing — not a control surface. Granting Agent Access happens in the
/// sidebar, where the project lives; this pane answers *"what is exposed, and
/// what could be"*. That is why a project with access **off** is absent rather
/// than listed-and-unticked: it is out of scope by definition, not missing from
/// a set it belongs to. (Settled 20 Aug 2026, `docs/mockups/mcp-agents-pane.html`.)
///
/// **The one exception is a receipt.** Unticking a row revokes access, and a
/// row that vanished on the click would read as *"removed the project"* — which
/// the sidebar has a real act for. So the row stays for the session, dimmed and
/// unticked, and can be re-ticked to undo. It is gone the next time the pane
/// opens, because a receipt is about what you just did, not about state.
///
/// **Grouping restates the predicate that decides exposure.** `HandshakeExposure`
/// exposes a project when a live window holds it *and* access is on; here the
/// window half becomes the group and the access half becomes the tick, so the
/// two halves of one rule are separately visible. `Active` is the window half —
/// deliberately the same set (`WindowRoster.shownProjects`) the handshake reads,
/// never serve liveness, which outlives its windows by `ServeReaping.defaultGrace`.
///
/// Pure and substrate-free, the same shape as `HandshakeExposure` and
/// `AgentAccessPolicy`: no window server, no sidecar, no clock.
///
/// **Naming.** "Active" collides three ways in this codebase — `agentActiveNow`
/// and `mcp.active` mean *an agent asked recently*, `PipelineState` has its own.
/// Here it means *a window is open*. The user-facing name is fixed by the
/// mockup; `Group.windowOpen` is the internal spelling so the code never reads
/// as if it meant one of the other two.
enum AgentProjectRegister {

    /// Which half of the exposure rule this project satisfies.
    enum Group: Equatable {
        /// A live window holds it, so access-on means an agent can read it now.
        case windowOpen
        /// Access is on, but nothing is open — it becomes readable when a
        /// window opens, and not before.
        case availableWhenOpened
    }

    /// One project, as the register needs it.
    struct Candidate: Equatable {
        let id: UUID
        let name: String
        /// The sidebar's per-project glyph, or nil for the default.
        let icon: String?
        /// Agent Access, the persisted permission.
        let access: Bool
        /// Nil when the watcher has not read this project yet. Rendered as an
        /// empty cell, never as a guess — the sheet precedent (`nowShowingLine`)
        /// is that a count we do not have is a count we do not print.
        let sessions: Int?
        /// When an agent last called a tool on this project, from
        /// `ServeFleet.lastAgentCallAt`. In memory per serve, so nil after a
        /// relaunch even for a project asked about yesterday — which is why the
        /// pane says so under the table rather than implying a history it keeps.
        let lastAsked: Date?
    }

    struct Row: Identifiable, Equatable {
        let id: UUID
        let name: String
        let icon: String?
        let group: Group
        let access: Bool
        let sessions: Int?
        let lastAsked: Date?

        /// Unticked and still on screen: the session receipt. Dimmed, reversible
        /// until the pane closes.
        var isReceipt: Bool { !access }
    }

    /// The register.
    ///
    /// - Parameters:
    ///   - candidates: every project the sidebar knows about.
    ///   - shown: `WindowRoster.shownProjects`. Minimised counts, deliberately
    ///     — minimising is how a researcher keeps a project in scope on a small
    ///     screen — and this is the same set the handshake is derived from, so
    ///     the group header cannot disagree with what an agent can reach.
    ///   - receipts: projects unticked during this pane session.
    static func rows(candidates: [Candidate],
                     shown: Set<UUID>,
                     receipts: Set<UUID>) -> [Row] {
        candidates
            .filter { $0.access || receipts.contains($0.id) }
            .map { c in
                Row(id: c.id,
                    name: c.name,
                    icon: c.icon,
                    group: shown.contains(c.id) ? .windowOpen : .availableWhenOpened,
                    access: c.access,
                    sessions: c.sessions,
                    lastAsked: c.lastAsked)
            }
            // Window-open first, then by name — and `id` breaks the tie rather
            // than leaving it to array order. Folder basenames collide
            // routinely ("~/clients/acme/interviews", "~/clients/zeta/
            // interviews"); two rows swapping places under the pointer as a
            // health poll lands is the kind of flicker that reads as a bug.
            .sorted { a, b in
                if a.group != b.group { return a.group == .windowOpen }
                let byName = a.name.localizedStandardCompare(b.name)
                return byName == .orderedSame ? a.id.uuidString < b.id.uuidString
                                              : byName == .orderedAscending
            }
    }

    /// One row, as VoiceOver should hear it.
    ///
    /// The row is four cells in an `HStack`, so nothing associates a number
    /// with the column header promising it: unlabelled, a reader hears the
    /// project name and the tick and learns neither the group — which decides
    /// whether an agent can read it **now** — nor the count nor the time.
    /// `SessionsPopoverSpec.accessibilityLabel(for:)` and `ProjectRow` already
    /// solve this for the same stacked-row shape; this is the third call site,
    /// which is where the pattern stops being a coincidence.
    ///
    /// **Commas, never `·`.** Straight from `SessionsPopoverSpec`: VoiceOver
    /// pauses on a comma and reads nothing at all for a middot, so the visible
    /// separator and the spoken one are deliberately different characters.
    ///
    /// **The group is repeated on every row on purpose.** The group header is
    /// reachable in a linear read but not in Tab order — the checkbox is the
    /// pane's only focusable row element — so this is the only way the tick and
    /// the group travel together for a keyboard user, which is the pairing the
    /// whole table exists to show.
    ///
    /// Takes rendered strings rather than keys so a test can assert the
    /// *joining* without an `I18n`; a bare `I18n()` returns the raw key, so a
    /// copy assertion here would silently be an assertion about identifiers.
    /// Empty parts are dropped rather than announced as pauses.
    static func accessibilityLabel(name: String,
                                   group: String,
                                   sessions: String?,
                                   lastAsked: String) -> String {
        [name, group, sessions, lastAsked]
            .compactMap { $0 }
            .filter { !$0.isEmpty }
            .joined(separator: ", ")
    }

    /// What an agent can read **right now**: projects, the sessions in them,
    /// and how many of those projects have not reported a count yet.
    ///
    /// **`gate` is `ServeFleet.readableProjects` — the set `syncHandshake`
    /// pushes to every serve — not a second opinion of it.** An earlier version
    /// re-derived `windowOpen && access` here, which was right for the same two
    /// inputs and wrong in the ways two implementations of one rule are always
    /// wrong: it counted a project whose sidecar had *failed*, and it read the
    /// permission by a different key than the handshake did. The headline now
    /// prints the gate, so it cannot disagree with what the gate closes on.
    ///
    /// The set is deliberately wider than the handshake's `entries`, which also
    /// wants a token and an instance id — those arrive a beat later on a cold
    /// start, and a roll-up that dropped to zero for that beat would read as a
    /// fault.
    ///
    /// `unknown` exists because the row policy and the roll-up policy were
    /// different, and only one of them was right. A row with no session count
    /// renders blank — never a guess. The sum had no such option: it rendered
    /// "0 sessions" identically for *we know there are none* and *we know
    /// nothing at all*, and the second is the ordinary state a second after
    /// launch, before the folder watcher's first scan lands. Returning the
    /// count of unknowns lets the caller drop the clause instead of fabricating
    /// a zero — absence being information, which is the rule the rows already
    /// follow.
    static func readable(_ rows: [Row],
                         gate: Set<UUID>) -> (projects: Int, sessions: Int, unknown: Int) {
        let live = rows.filter { gate.contains($0.id) }
        return (live.count,
                live.compactMap(\.sessions).reduce(0, +),
                live.filter { $0.sessions == nil }.count)
    }
}
