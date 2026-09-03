import AppKit
import SwiftUI
import Testing
@testable import Bristlenose

/// The Settings window's on-demand re-fit, and the LLM pane's shape.
///
/// Two halves of one rule. `refitTarget` decides *whether* to move; the height
/// measurements say whether the deadband it is given still separates "browsing"
/// from "a genuinely different shape".
@Suite @MainActor struct SettingsRefitTests {

    // MARK: - The decision

    private func target(from current: CGFloat, to fitting: CGFloat,
                        threshold: CGFloat = LLMSettingsView.shrinkThreshold) -> CGFloat? {
        SettingsWindow.refitTarget(
            current: current, fitting: fitting, shrinkThreshold: threshold)
    }

    @Test func growthIsNeverDeadbanded() {
        // The shipped Azure defect in miniature: content 17pt taller than the
        // window does not get a scrollbar, it gets compressed by the required
        // constraints that pin the pane. So any growth must move the window,
        // however small — even growth far below the shrink threshold.
        #expect(target(from: 484, to: 501) == 501)
        #expect(target(from: 660, to: 681) == 681)
    }

    @Test func smallShrinksAreRefused() {
        // Browsing Claude → ChatGPT is a 15pt saving. Not worth moving a window
        // the user is reading.
        #expect(target(from: 499, to: 484) == nil)
    }

    @Test func aRealShapeChangeShrinks() {
        // Azure → Claude gives back 182pt. That is a different pane, not noise.
        #expect(target(from: 681, to: 499) == 499)
    }

    @Test func aZeroThresholdFitsExactlyBothWays() {
        // What MCP Agents passes (the default): no browsing to protect, so the
        // window takes the height each client tab actually needs.
        #expect(target(from: 499, to: 484, threshold: 0) == 484)
        #expect(target(from: 484, to: 499, threshold: 0) == 499)
    }

    @Test func layoutNoiseNeverMovesTheWindow() {
        // Sub-point differences arrive on every render pass; animating on them
        // would make the window shiver.
        #expect(target(from: 499, to: 499.2, threshold: 0) == nil)
        #expect(target(from: 499, to: 498.8, threshold: 0) == nil)
    }

    // MARK: - The shapes it is deciding between

    /// The height this provider's pane wants, read the way the window reads it.
    private func height(_ provider: LLMProvider) -> CGFloat {
        let host = NSHostingController(
            rootView: LLMSettingsView(measuring: provider).environmentObject(I18n()))
        host.sizingOptions = .preferredContentSize
        host.view.layoutSubtreeIfNeeded()
        return host.view.fittingSize.height
    }

    private var others: [LLMProvider] { LLMProvider.allCases.filter { $0 != .azure } }

    @Test func azureIsTheOutlier() {
        // The premise of the whole deadband: one provider is a different shape
        // and the rest are the same shape. If a second provider grows an extra
        // section this fails, and the threshold needs looking at again.
        let azure = height(.azure)
        for provider in others {
            #expect(azure > height(provider),
                    "azure \(azure) is not taller than \(provider.rawValue) \(height(provider))")
        }
    }

    @Test func browsingTheOthersNeverMovesTheWindow() {
        // The user-visible promise. Measured 3 Sep 2026 the spread was 17pt
        // against a 60pt threshold; asserted as a relation, not a number, so a
        // system font revision does not fail it but a new section does.
        let heights = others.map(height)
        let spread = heights.max()! - heights.min()!
        #expect(spread < LLMSettingsView.shrinkThreshold,
                "the non-Azure providers span \(spread)pt, at or past the \(LLMSettingsView.shrinkThreshold)pt threshold — the window will now move while the user is comparing them")
    }

    @Test func azureIsFarEnoughAwayToEarnTheMove() {
        // The other side: if Azure crept close to the group the threshold would
        // swallow it, and Azure would silently start compressing again.
        let gap = height(.azure) - others.map(height).max()!
        #expect(gap > LLMSettingsView.shrinkThreshold,
                "azure is only \(gap)pt taller than the tallest other provider")
    }
}
