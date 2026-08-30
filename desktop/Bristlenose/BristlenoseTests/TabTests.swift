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

    /// Five lenses ship; the enum carries six.
    ///
    /// `.codebookV2` is the replacement Codebook lens, built beside the shipped
    /// one (`docs/design-codebook-v2.md` D29). The *enum* holds it
    /// unconditionally so every switch over `Tab` stays simple; only its rail
    /// row is `#if DEBUG`, which is what keeps it out of a researcher's
    /// sidebar. `LensItemTests` pins that side.
    ///
    /// Counting `allCases` is therefore no longer a statement about what ships.
    /// Asserting the roster is: a case added or dropped fails here and names
    /// itself, which the count could not do.
    @Test func allCases_areTheKnownRoster() {
        #expect(Tab.allCases == [
            .project, .sessions, .quotes, .codebook, .codebookV2, .analysis,
        ])
    }

    /// A route that is a prefix of another must not swallow it — and this pair
    /// is the first in the enum where that is possible.
    @Test func codebookRoutes_doNotCollide() {
        #expect(Tab.codebookV2.route != Tab.codebook.route)
        #expect(Tab.from(path: Tab.codebookV2.route) == .codebookV2)
        #expect(Tab.from(path: Tab.codebook.route) == .codebook)
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
/// Show/Hide item. Adding `codebookV2` reached three and missed the gate — so
/// the lens had a panel, a menu item that toggled it and a working ⌘⌥L, and no
/// toolbar button. On the Mac that button is the ONLY affordance: embedded mode
/// removes the SPA's own rails, so a missing gate means an unreachable panel.
@Suite struct TabLeftPanelTests {

    @Test func theFourLensesWithANavigatorHaveOne() {
        #expect(Tab.quotes.hasLeftPanel)
        #expect(Tab.codebook.hasLeftPanel)
        #expect(Tab.codebookV2.hasLeftPanel)
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
        #expect(Tab.allCases.count == 6)
    }
}
