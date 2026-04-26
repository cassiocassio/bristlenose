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

    @Test func allCases_haveFive() {
        #expect(Tab.allCases.count == 5)
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
