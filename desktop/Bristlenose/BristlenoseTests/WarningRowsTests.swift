import AppKit
import Foundation
import SwiftUI
import Testing

@testable import Bristlenose

/// The rows for what a finished run is missing that the researcher would expect, resolved with the
/// shipped locale files (owner, 11 Nov 2026; docs/mockups/done-with-warnings-mac-row.html). Every
/// row says why: a reason this build does not know falls back to the shipped "Detailed cause not
/// captured." and never shows a raw wire value.
@MainActor
@Suite struct WarningRowsTests {
    private func i18n(_ locale: String) throws -> I18n {
        let i18n = I18n()
        i18n.configure(localesDirectory: try #require(I18n.findLocalesDirectory()))
        i18n.setLocale(locale)
        return i18n
    }

    @Test func theLensSaysWhyInPlainEnglish() throws {
        let en = try i18n("en")
        let w = RunWarning(kind: RunWarning.discussionLens, reason: "no_clear_moderator", line: nil)
        #expect(WarningRows.name(of: w, i18n: en) == "Discussion")
        #expect(WarningRows.message(for: w, i18n: en) == "Couldn\u{2019}t tell who the moderator is in any session.")
    }

    @Test func aModelFailureUsesTheShortCauseLabelTheOtherRowsUse() throws {
        let en = try i18n("en")
        let quota = RunWarning(kind: RunWarning.discussionLens, reason: "quota", line: nil)
        #expect(WarningRows.message(for: quota, i18n: en) == "Rate limited")
        let credit = RunWarning(kind: RunWarning.discussionLens, reason: "out_of_credit", line: nil)
        #expect(WarningRows.message(for: credit, i18n: en) == "Out of credit")
        let server = RunWarning(kind: RunWarning.discussionLens, reason: "api_server", line: nil)
        #expect(WarningRows.message(for: server, i18n: en) == "Provider unavailable")
    }

    @Test func anUnknownCauseSaysItWasNotCapturedNeverARawValue() throws {
        let en = try i18n("en")
        for reason in ["unknown", "a_reason_from_a_newer_sidecar", ""] {
            let w = RunWarning(kind: RunWarning.discussionLens, reason: reason, line: nil)
            #expect(WarningRows.message(for: w, i18n: en) == "Detailed cause not captured.", "reason \(reason)")
        }
        let odd = RunWarning(kind: RunWarning.peopleFile, reason: "something_new", line: nil)
        #expect(WarningRows.message(for: odd, i18n: en) == "Detailed cause not captured.")
    }

    @Test func theNamesFileSaysWhichLineAndWhatItCosts() throws {
        let en = try i18n("en")
        let w = RunWarning(kind: RunWarning.peopleFile, reason: "unreadable", line: 14)
        #expect(WarningRows.name(of: w, i18n: en) == "people.yaml")
        #expect(WarningRows.message(for: w, i18n: en)
                == "Couldn\u{2019}t be read (line 14), so names you added aren\u{2019}t shown.")
        let noLine = RunWarning(kind: RunWarning.peopleFile, reason: "unreadable", line: nil)
        #expect(WarningRows.message(for: noLine, i18n: en)
                == "Couldn\u{2019}t be read, so names you added aren\u{2019}t shown.")
    }

    @Test func everyLocaleHasAllThreeStrings() throws {
        // A missing key reads as the raw key; this catches a locale the seeding missed.
        let lines: [(RunWarning, String)] = [
            (RunWarning(kind: RunWarning.discussionLens, reason: "no_clear_moderator", line: nil), "warningNoClear"),
            (RunWarning(kind: RunWarning.peopleFile, reason: "unreadable", line: 9), "warningPeople"),
            (RunWarning(kind: RunWarning.peopleFile, reason: "unreadable", line: nil), "warningPeople"),
        ]
        let en = try i18n("en")
        for locale in ["ca", "cs", "da", "de", "es", "fi", "fr", "it", "ja", "ko", "nb", "nl",
                       "pl", "pt-BR", "pt-PT", "ru", "sv", "tr", "uk", "zh-Hant"] {
            let i = try i18n(locale)
            for (w, prefix) in lines {
                let m = WarningRows.message(for: w, i18n: i)
                // `I18n.t` falls back to English for a key the locale lacks, so the raw-key
                // check below cannot see a missed locale; the English sentence can.
                #expect(m != WarningRows.message(for: w, i18n: en), "\(locale): English shown: \(m)")
                #expect(!m.contains(prefix), "\(locale): raw key shown: \(m)")
                #expect(!m.contains("{{"), "\(locale): placeholder left in: \(m)")
                #expect(!m.isEmpty)
            }
        }
    }
}
