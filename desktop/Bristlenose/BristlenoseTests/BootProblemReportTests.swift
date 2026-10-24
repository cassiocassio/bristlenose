import Foundation
import Testing
@testable import Bristlenose

/// What a problem report from the boot pane (N08) starts with: the pane's own
/// title and sentence, in the researcher's language, without the engine output
/// the sentence ends with on screen. That output can name a study folder, and
/// the prefill is sent as the person's message. Real locales, pinned to a
/// language, never the developer's own.
@MainActor
@Suite struct BootProblemReportTests {

    private func i18n(_ locale: String = "en") throws -> I18n {
        let i18n = I18n()
        i18n.configure(localesDirectory: try #require(I18n.findLocalesDirectory()))
        i18n.setLocale(locale)
        return i18n
    }

    private static let output = """
        INFO  opening /Users/jane/Documents/NHS diabetes P07/bristlenose-output/x.db
        sqlite3.OperationalError: unable to open database file
        """

    @Test(arguments: ["exitedBeforeReady", "exitedWithCode"])
    func theEngineOutputStaysBehind(key: String) throws {
        let failure = FailureMessage.keyed(
            "desktop.boot.failure." + key, vars: ["status": "1", "details": Self.output])
        let message = BootView.problemReportMessage(for: failure, i18n: try i18n())

        #expect(!message.contains("NHS diabetes"))
        #expect(!message.contains("sqlite3"))
        #expect(message.hasPrefix("Couldn’t start Bristlenose\n"))
        #expect(message.contains("(code 1)") || message.contains("code 1."))
        #expect(!message.hasSuffix("\n"))
    }

    @Test func theExactLineForAnEarlyExit() throws {
        let failure = FailureMessage.keyed(
            "desktop.boot.failure.exitedBeforeReady", vars: ["status": "1", "details": Self.output])
        #expect(BootView.problemReportMessage(for: failure, i18n: try i18n()) == """
            Couldn’t start Bristlenose
            Bristlenose stopped before it finished starting (code 1).
            """)
    }

    /// The app's own path keeps its shape but not the user's name. A literal
    /// path: under the sandbox `NSHomeDirectory()` is the container, so a path
    /// built from it would prove nothing about a real home folder.
    @Test func aPathInTheHomeFolderIsShortened() throws {
        let path = "/Users/jane/Applications/Bristlenose.app/Contents/Resources/x"
        let failure = FailureMessage.keyed("desktop.boot.failure.sidecarMissing", vars: ["path": path])
        let message = BootView.problemReportMessage(for: failure, i18n: try i18n())
        #expect(!message.contains("jane"))
        #expect(message.contains("~/Applications/Bristlenose.app"))
    }

    @Test func aPathOutsideAHomeFolderIsKept() throws {
        let path = "/Applications/Bristlenose.app/Contents/Resources/x"
        let failure = FailureMessage.keyed("desktop.boot.failure.sidecarMissing", vars: ["path": path])
        #expect(BootView.problemReportMessage(for: failure, i18n: try i18n()).contains(path))
    }

    @Test func itIsInTheResearchersLanguage() throws {
        let failure = FailureMessage.keyed("desktop.boot.failure.startTimeout")
        let german = try i18n("de")
        let message = BootView.problemReportMessage(for: failure, i18n: german)
        #expect(message.hasPrefix(german.t("desktop.boot.failedTitle") + "\n"))
        #expect(!message.hasPrefix("Couldn’t start"))
    }

    /// Someone else's words come through whole; there is nothing to drop.
    @Test func aPassthroughComesThroughWhole() throws {
        let message = BootView.problemReportMessage(
            for: .passthrough("exit 1"), i18n: try i18n())
        #expect(message == "Couldn’t start Bristlenose\nexit 1")
    }
}
