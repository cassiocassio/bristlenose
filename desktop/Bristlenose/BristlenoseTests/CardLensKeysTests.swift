import Testing
@testable import Bristlenose

/// ⌘A selects quote cards as objects on every lens that shows them, and stays
/// native text select-all elsewhere and while editing.
@Suite struct CardLensKeysTests {
    @Test func quotesAndScreensClaimSelectAll() {
        #expect(CardLensKeys.claimsSelectAll(tab: .quotes, isEditing: false))
        #expect(CardLensKeys.claimsSelectAll(tab: .screens, isEditing: false))
    }

    @Test func editingAndOtherLensesLeaveItNative() {
        #expect(!CardLensKeys.claimsSelectAll(tab: .screens, isEditing: true))
        for tab in [Tab.project, .sessions, .codebook, .signals, .discussion] {
            #expect(!CardLensKeys.claimsSelectAll(tab: tab, isEditing: false))
        }
        #expect(!CardLensKeys.claimsSelectAll(tab: nil, isEditing: false))
    }
}
