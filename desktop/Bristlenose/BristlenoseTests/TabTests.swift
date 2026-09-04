import Testing
@testable import Bristlenose

// MARK: - Tab.from(path:) tests

@MainActor
@Suite("Tab route parsing")
struct TabTests {

    @Test func fromPath_project_exact() {
        #expect(Tab.from(path: "/report/") == .project)
    }

    @Test func fromPath_project_noTrailingSlash() {
        #expect(Tab.from(path: "/report") == .project)
    }

    @Test func fromPath_sessions() {
        #expect(Tab.from(path: "/report/sessions/") == .sessions)
    }

    @Test func fromPath_sessions_withId() {
        #expect(Tab.from(path: "/report/sessions/abc123") == .sessions)
    }

    @Test func fromPath_quotes() {
        #expect(Tab.from(path: "/report/quotes/") == .quotes)
    }

    @Test func fromPath_codebook() {
        #expect(Tab.from(path: "/report/codebook/") == .codebook)
    }

    @Test func fromPath_analysis() {
        #expect(Tab.from(path: "/report/analysis/") == .analysis)
    }

    @Test func fromPath_unknown_returnsNil() {
        #expect(Tab.from(path: "/unknown") == nil)
    }

    @Test func fromPath_empty_returnsNil() {
        #expect(Tab.from(path: "") == nil)
    }

    @Test func fromPath_root_returnsNil() {
        #expect(Tab.from(path: "/") == nil)
    }

    @Test func fromPath_reportPrefix_doesNotMatchProject() {
        // /report/something should not match project (exact match only)
        #expect(Tab.from(path: "/report/something") == nil)
    }

    // MARK: - Tab properties

    /// Five lenses ship and the enum carries five — `.codebookV2` retired on
    /// 31 Aug 2026 when v2 became the only Codebook lens.
    ///
    /// Asserting the roster rather than counting it: a case added or dropped
    /// fails here and names itself, which a count could not do. That mattered
    /// while the enum and the rail disagreed on purpose, and it still earns its
    /// keep now they agree.
    @Test func allCases_areTheKnownRoster() {
        #expect(Tab.allCases == [
            .project, .sessions, .quotes, .codebook, .analysis,
        ])
    }

    /// Every route round-trips through `Tab.from(path:)`.
    ///
    /// Was `codebookRoutes_doNotCollide`, guarding the one prefix pair the enum
    /// held (`/report/codebook` vs `/report/codebook-v2`). That pair retired
    /// with the v2 lens; generalised rather than deleted, so the next route
    /// that fails to round-trip is caught by name.
    @Test func everyRouteRoundTrips() {
        for tab in Tab.allCases {
            #expect(Tab.from(path: tab.route) == tab)
        }
    }

    @Test func routes_startWithReport() {
        for tab in Tab.allCases {
            #expect(tab.route.hasPrefix("/report/"))
        }
    }

    @Test func labels_areNonEmpty() {
        for tab in Tab.allCases {
            #expect(!tab.label.isEmpty)
        }
    }

    @Test func rawValues_matchConfigKeys() {
        // Raw values must match the keys used by bristlenose config
        #expect(Tab.project.rawValue == "project")
        #expect(Tab.sessions.rawValue == "sessions")
        #expect(Tab.quotes.rawValue == "quotes")
        #expect(Tab.codebook.rawValue == "codebook")
        #expect(Tab.analysis.rawValue == "analysis")
    }
}

// MARK: - Which lenses have a content navigator

/// `hasLeftPanel` exists because the same fact was enumerated in four places:
/// the toolbar button's gate, its label, its tooltip, and the View menu's
/// Show/Hide item. Adding a lens once reached three and missed the gate — so
/// the lens had a panel, a menu item that toggled it and a working ⌘⌥L, and no
/// toolbar button. On the Mac that button is the ONLY affordance: embedded mode
/// removes the SPA's own rails, so a missing gate means an unreachable panel.
@Suite struct TabLeftPanelTests {

    @Test func theThreeLensesWithANavigatorHaveOne() {
        #expect(Tab.quotes.hasLeftPanel)
        #expect(Tab.codebook.hasLeftPanel)
        #expect(Tab.analysis.hasLeftPanel)
    }

    @Test func theTwoWithoutOneDoNot() {
        // Project has no panel. Sessions' was removed in embedded mode in
        // favour of the native switcher popover, and the browser one is
        // mounted by AppLayout rather than gated here.
        #expect(!Tab.project.hasLeftPanel)
        #expect(!Tab.sessions.hasLeftPanel)
    }

    @Test func everyCaseIsDecided() {
        // The switch is exhaustive with no `default:`, so a new Tab case fails
        // to compile rather than silently inheriting "no panel" — which is how
        // a lens ships with an unreachable navigator.
        for tab in Tab.allCases {
            _ = tab.hasLeftPanel
        }
        // Five since `codebookV2` was folded into `codebook` (baa1aa0e). The
        // number is the tripwire, so move it deliberately — it went stale there
        // and the suite was red on main until 31 Aug 2026.
        #expect(Tab.allCases.count == 6)  // DELIBERATELY WRONG — proving the CI step can go red; reverted next commit
    }
}
