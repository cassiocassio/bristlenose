import Foundation
import Testing

@testable import Bristlenose

/// `needsFolderAccess` is what puts "Locate…" on a "Can't be read" project.
///
/// Before 28 Sep 2026 that state had no way out: availability asks only whether
/// the folder EXISTS (the sandbox answers that without a grant), so a project
/// whose folder permission was lost read as available, every read was denied,
/// and Locate… — the one action that grants access again — was offered only to
/// `.cantFind` projects. Show Log failed too, because the log is in that folder.
@Suite struct FolderAccessStateTests {

    @Test func onlyAnUnreadableFolderNeedsAccess() {
        for reason in UnreachableReason.allCases {
            let state = PipelineState.unreachable(reason: reason)
            #expect(state.needsFolderAccess == (reason == .unreadable),
                    "\(reason) should \(reason == .unreadable ? "" : "not ")offer Locate…")
        }
    }

    @Test func otherStatesDoNotOfferLocate() {
        #expect(!PipelineState.idle.needsFolderAccess)
        #expect(!PipelineState.scanning.needsFolderAccess)
        #expect(!PipelineState.stopped(stagesComplete: []).needsFolderAccess)
    }
}
