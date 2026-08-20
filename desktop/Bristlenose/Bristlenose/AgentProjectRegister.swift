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

    /// What an agent can read **right now**: projects, and the sessions in them.
    ///
    /// Deliberately computed from the same predicate as the rows rather than
    /// from `ServeFleet.handshakeProjectPaths`, so the headline count and the
    /// ticks under it cannot disagree. The handshake additionally requires a
    /// token and an instance id, which arrive a beat later on a cold start — a
    /// roll-up that dropped to zero for that beat would read as a fault.
    ///
    /// Sessions sums only the counts we have. An unknown count contributes
    /// nothing rather than being guessed at, which can make the total an
    /// undercount — correct, and the alternative is a number nobody can check.
    static func readable(_ rows: [Row]) -> (projects: Int, sessions: Int) {
        let live = rows.filter { $0.group == .windowOpen && $0.access }
        return (live.count, live.compactMap(\.sessions).reduce(0, +))
    }
}
