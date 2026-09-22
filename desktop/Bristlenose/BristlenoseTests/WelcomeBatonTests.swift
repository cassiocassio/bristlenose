import Testing
@testable import Bristlenose

// WelcomeBaton is @MainActor; nextHolder is a static on it → suite-level @MainActor.
@Suite @MainActor
struct WelcomeBatonTests {

    @Test func nobodyWants_returnsNil() {
        #expect(WelcomeBaton.nextHolder(after: nil, wants: [:]) == nil)
        #expect(WelcomeBaton.nextHolder(after: .science, wants: [.tip: false, .ai: false]) == nil)
    }

    @Test func fromNil_picksFirstWantingInSpiralOrder() {
        #expect(WelcomeBaton.nextHolder(after: nil, wants: [.science: true]) == .science)
        // study (0) precedes ai (3) in spiral order → study wins from the start
        #expect(WelcomeBaton.nextHolder(after: nil, wants: [.ai: true, .studyTools: true]) == .studyTools)
    }

    @Test func advancesToNextWanting() {
        let wants: [WelcomeSlot: Bool] = [.studyTools: true, .science: true, .ai: true]
        #expect(WelcomeBaton.nextHolder(after: .studyTools, wants: wants) == .science)
        #expect(WelcomeBaton.nextHolder(after: .science, wants: wants) == .ai)
    }

    @Test func wrapsAround() {
        let wants: [WelcomeSlot: Bool] = [.studyTools: true, .science: true]
        #expect(WelcomeBaton.nextHolder(after: .science, wants: wants) == .studyTools)
        #expect(WelcomeBaton.nextHolder(after: .delight, wants: wants) == .studyTools)
    }

    @Test func skipsNonWanting() {
        // science doesn't want it → after study, skip to ai
        let wants: [WelcomeSlot: Bool] = [.studyTools: true, .ai: true]
        #expect(WelcomeBaton.nextHolder(after: .studyTools, wants: wants) == .ai)
    }

    @Test func soleWanter_returnsItself() {
        #expect(WelcomeBaton.nextHolder(after: .science, wants: [.science: true]) == .science)
    }

    // MARK: - Carousel claims
    //
    // Paging a rotator IS the researcher saying "show me this one". Without a claim
    // the new slide sits on its still until the spiral comes round — most of a minute
    // — which reads as a broken illustration rather than as a queue.

    @Test func claim_winsOverSpiralOrder() {
        let wants: [WelcomeSlot: Bool] = [.studyTools: true, .science: true, .ai: true]
        // Spiral order from studyTools would give science; the researcher asked for ai.
        #expect(WelcomeBaton.nextHolder(claimed: .ai, after: .studyTools, wants: wants) == .ai)
    }

    @Test func claim_winsEvenForTheSlotAlreadyHolding() {
        // Paging the cell that is mid-play restarts THAT cell, rather than advancing:
        // the researcher changed the slide, so the pass they are owed is the new one.
        let wants: [WelcomeSlot: Bool] = [.studyTools: true, .science: true]
        #expect(WelcomeBaton.nextHolder(claimed: .science, after: .science, wants: wants) == .science)
    }

    @Test func claim_forACellWithNothingToAnimate_isIgnored() {
        // Paging the Tip cell must not take the baton off a cell that is mid-play and
        // hand it to a turn with nothing in it.
        let wants: [WelcomeSlot: Bool] = [.studyTools: true, .science: true, .tip: false]
        #expect(WelcomeBaton.nextHolder(claimed: .tip, after: .studyTools, wants: wants) == .science)
    }

    @Test func claim_forACellThatNeverReported_isIgnored() {
        // Absent is not the same as false anywhere else in this file; it must not be
        // here either, or an unreported slot could claim an empty turn.
        let wants: [WelcomeSlot: Bool] = [.studyTools: true]
        #expect(WelcomeBaton.nextHolder(claimed: .delight, after: nil, wants: wants) == .studyTools)
    }

    @Test func noClaim_behavesExactlyAsBefore() {
        // The parameter defaults to nil, so every pre-existing call site keeps its
        // meaning — this pins that rather than trusting the default.
        let wants: [WelcomeSlot: Bool] = [.studyTools: true, .science: true]
        #expect(WelcomeBaton.nextHolder(claimed: nil, after: .studyTools, wants: wants)
                == WelcomeBaton.nextHolder(after: .studyTools, wants: wants))
    }
}

// MARK: - The curtain's shape
//
// `WelcomeTempo` is the only place the rhythm is written down, and both halves of the
// implementation read it — the Swift natives through `WelcomeCurtain`, the webviews
// through the interpolated `BN` constants. These pin the relationships that make the
// grammar legible, not the numbers, which are taste and will move.

@Suite @MainActor
struct WelcomeTempoTests {

    @Test func theEndHoldIsLongerThanTheEstablish() {
        // Deliberate asymmetry: the opening frame is a stage nobody has earned yet,
        // the closing one is the result. Someone will eventually "tidy" these to match.
        #expect(WelcomeTempo.holdEndSeconds > WelcomeTempo.establishSeconds)
        #expect(WelcomeTempo.holdEndSeconds > WelcomeTempo.establishReadSeconds)
    }

    @Test func proseOpenersGetTheLongerEstablishingBeat() {
        // Tag and Star&hide open on a real quote card that is then acted on; a beat
        // too short to read the quote is not an establishing beat.
        #expect(WelcomeTempo.establish(for: .tag) == WelcomeTempo.establishReadSeconds)
        #expect(WelcomeTempo.establish(for: .starHide) == WelcomeTempo.establishReadSeconds)
        // Everything else opens on an empty stage — nothing to establish.
        #expect(WelcomeTempo.establish(for: .ingest) == WelcomeTempo.establishSeconds)
        #expect(WelcomeTempo.establish(for: .miro) == WelcomeTempo.establishSeconds)
    }

    @Test func restIsARecessionNotABlackout() {
        // The curtain has to fall somewhere that is neither a hole in the grid nor the
        // same strength as the playing cell, or it punctuates nothing.
        #expect(WelcomeTempo.restOpacity > 0)
        #expect(WelcomeTempo.restOpacity < 1)
    }

    @Test func theWatchdogClearsTheWholeGrammarForEveryIllustration() {
        // The ceiling only exists for the case where `finish` never arrives. If it can
        // trip during a healthy pass it is the two-clock bug all over again, so it must
        // sit above the curtain's own overhead by a margin for every illustration.
        for kind in [WelcomeIllustration.sentimentFan, .books, .emergentThemes, .quote,
                     .signal, .autocode, .manualTags, .tag, .starHide, .agentChat,
                     .ingest, .clips, .miro] {
            let overhead = WelcomeTempo.establish(for: kind)
                + 2 * WelcomeTempo.fadeSeconds
                + WelcomeTempo.holdEndSeconds
            #expect(kind.welcomeTurn > overhead,
                    "\(kind) watchdog would fire before its curtain finished")
        }
        #expect(WelcomeIllustration.none.welcomeTurn == 0)
    }
}
