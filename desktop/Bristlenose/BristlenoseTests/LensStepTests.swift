import Testing
@testable import Bristlenose

/// View ▸ Next/Previous follows the lens: screens on Screens, questions on
/// Discussion, dimmed (reading Screen) everywhere else.
@Suite struct LensStepTests {
    @Test func screensStepsScreens() {
        #expect(LensStep.isEnabled(tab: .screens))
        #expect(LensStep.labelKey(tab: .screens, next: true) == "desktop.menu.view.nextScreen")
        #expect(LensStep.labelKey(tab: .screens, next: false) == "desktop.menu.view.previousScreen")
        #expect(LensStep.action(tab: .screens, next: true) == "nextScreen")
        #expect(LensStep.action(tab: .screens, next: false) == "previousScreen")
    }

    @Test func discussionStepsQuestions() {
        #expect(LensStep.isEnabled(tab: .discussion))
        #expect(LensStep.labelKey(tab: .discussion, next: true) == "desktop.menu.view.nextQuestion")
        #expect(LensStep.action(tab: .discussion, next: false) == "previousQuestion")
    }

    @Test func otherLensesDimAndReadScreen() {
        for tab in [Tab.project, .sessions, .quotes, .codebook, .signals] {
            #expect(!LensStep.isEnabled(tab: tab))
            #expect(LensStep.labelKey(tab: tab, next: true) == "desktop.menu.view.nextScreen")
        }
        #expect(!LensStep.isEnabled(tab: nil))
    }
}
