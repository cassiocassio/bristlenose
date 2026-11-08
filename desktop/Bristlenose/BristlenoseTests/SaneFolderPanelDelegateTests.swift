import Foundation
import Testing
@testable import Bristlenose

/// R44: the default-folder chooser refuses the volume root and the volume list itself, so a pick
/// of them is not accepted and then silently dropped by `setConfigured`.
struct SaneFolderPanelDelegateTests {
    private let delegate = SaneFolderPanelDelegate()

    @Test("The volume root and the volume list are not offered")
    func rootAndVolumesAreGreyedOut() {
        for path in ["/", "/Volumes", "/Volumes/"] {
            #expect(!delegate.panel(NSObject(), shouldEnable: URL(fileURLWithPath: path)), "\(path)")
        }
    }

    @Test("Any other folder is offered, including one on an external volume")
    func ordinaryFoldersAreOffered() {
        for path in ["/Users", "/Users/Shared/studies", "/Volumes/Iona", "/Volumes/Iona/studies"] {
            #expect(delegate.panel(NSObject(), shouldEnable: URL(fileURLWithPath: path)), "\(path)")
        }
    }

    @Test("Choose on the volume root or list is refused, quietly, and an ordinary folder is accepted")
    func validateRefusesOnlyTheHostileTargets() throws {
        #expect(throws: CocoaError.self) {
            try delegate.panel(NSObject(), validate: URL(fileURLWithPath: "/"))
        }
        #expect(throws: CocoaError.self) {
            try delegate.panel(NSObject(), validate: URL(fileURLWithPath: "/Volumes"))
        }
        try delegate.panel(NSObject(), validate: URL(fileURLWithPath: "/Users/Shared"))
    }
}
