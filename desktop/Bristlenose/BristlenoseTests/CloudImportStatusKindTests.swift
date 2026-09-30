import Foundation
import Testing

@testable import Bristlenose

// Whether a row's Status cell has both halves it needs to draw: a label and a
// kind. The view renders a status only when both are present.
//
// From 400028d3 to this fix the kind came from `localState.messageKind`
// alone, which is nil for a row not yet imported. So "Needs access",
// "Not recorded", "Needs a paid plan" and the organiser's name were computed
// and then thrown away, and the cell sat empty on exactly the rows whose
// Status column is the only thing explaining the dead checkbox.

@Suite("Status column kind")
@MainActor
struct CloudImportStatusKindTests {

    nonisolated private static let localesURL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()   // BristlenoseTests
        .deletingLastPathComponent()   // Bristlenose
        .deletingLastPathComponent()   // desktop
        .deletingLastPathComponent()   // repo root
        .appendingPathComponent("bristlenose/locales")

    private func english() -> I18n {
        let i = I18n()
        i.configure(localesDirectory: Self.localesURL)
        i.setLocale("en")
        return i
    }

    private func row(video: ArtifactAvailability, local: ImportRowState = .notImported) -> CloudImportRow {
        CloudImportRow(
            id: "r", title: "t", startsAt: Date(), duration: nil, sizeBytes: nil,
            expiresAt: nil, attendees: [], localState: local,
            video: video, roster: .available, transcript: .available, organiser: nil
        )
    }

    nonisolated static let unavailable: [(ArtifactAvailability, MessageKind)] = [
        (.notOrganiser(organiser: "A. Bianchi"), .info),
        (.notOrganiser(organiser: nil), .info),
        (.notRecorded, .info),
        (.notResolved, .warning),
        (.notOnThisPlan, .warning),
        (.needsScope("drive.readonly"), .warning),
        (.unsupported, .warning),
    ]

    @Test("A not-imported row with no obtainable video shows its status",
          arguments: unavailable)
    func unavailableVideoIsShown(video: ArtifactAvailability, kind: MessageKind) {
        let i18n = english()
        let r = row(video: video)
        let label = r.statusLabel(i18n)
        #expect(label != nil)
        // A lookup that missed returns its own key, which is non-nil and would
        // pass the line above while rendering "desktop.cloudImport…" in the cell.
        #expect(label?.hasPrefix("desktop.") == false)
        #expect(r.statusKind == kind)
    }

    @Test("The common row stays silent")
    func availableNotImportedIsSilent() {
        let r = row(video: .available)
        #expect(r.statusLabel(english()) == nil)
        #expect(r.statusKind == nil)
    }

    /// The label is the video's when the video is unavailable, so the kind must
    /// be too — otherwise a held file under "Needs access" draws the held file's
    /// glyph beside the refusal's words.
    @Test("The video decides the kind wherever it decides the label")
    func videoWinsOverLocalState() {
        let r = row(video: .needsScope("drive.readonly"), local: .imported)
        #expect(r.statusLabel(english()) == english().t("desktop.cloudImport.statusNeedsAccess"))
        #expect(r.statusKind == .warning)
        #expect(row(video: .available, local: .imported).statusKind == .info)
    }
}
