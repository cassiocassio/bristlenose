import CoreGraphics
import Testing

@testable import Bristlenose

/// The Welcome window's two arrangements (design-welcome-screen.md, Model 2).
///
/// What is worth pinning is the promise the owner made about the narrow window:
/// it reflows in exactly ONE step. Only the outermost split flips, and the rest of
/// the spiral keeps its shape, so AI never wraps under Tip at any width the window
/// allows. A layout that "helpfully" reflowed further would still render, still
/// pass every other test, and break that promise.
@Suite("Welcome spiral layout")
struct WelcomeSpiralLayoutTests {
    private typealias L = WelcomeSpiralLayout

    @Test("at the natural size the cells form the golden spiral")
    func naturalIsTheSpiral() {
        let f = L.frames(width: L.naturalWidth, stacked: false)
        let (study, science, tip, ai, delight) = (f[0], f[1], f[2], f[3], f[4])
        #expect(f.count == 5)
        // Study tools beside the rest, full height.
        #expect(study.minX == 0 && study.minY == 0)
        #expect(abs(study.height - L.naturalHeight) < 0.5)
        #expect(science.minX > study.maxX)
        // Science over Tip; AI beside Tip; Delight under AI.
        #expect(tip.minY > science.maxY)
        #expect(ai.minX > tip.maxX && ai.minY == tip.minY)
        #expect(delight.minY > ai.maxY && delight.minX == ai.minX)
        // Everything inside the spiral's own box.
        #expect(f.allSatisfy { $0.maxX <= L.naturalWidth + 0.5 && $0.maxY <= L.naturalHeight + 0.5 })
    }

    @Test("narrowed but not stacked, the spiral keeps its φ proportions")
    func narrowedSpiralKeepsPhi() {
        let w: CGFloat = 560
        let f = L.frames(width: w, stacked: false)
        #expect(abs((f.map(\.maxY).max() ?? 0) - w / 1.618) < 0.5)
        #expect(f[2].minY > f[1].maxY && f[3].minX > f[2].maxX)
    }

    @Test("stacked, only the outermost split flips — at every width the window allows")
    func oneStepReflow() {
        for width in [L.minimumWidth, 400, 600, L.naturalWidth] {
            let f = L.frames(width: width, stacked: true)
            let (study, science, tip, ai, delight) = (f[0], f[1], f[2], f[3], f[4])
            // Study tools on top, at the full width.
            #expect(study.minY == 0 && abs(study.width - width) < 0.5)
            #expect(science.minY > study.maxY)
            // The rest keeps the spiral's inner shape: AI beside Tip, never under it.
            #expect(ai.minX > tip.maxX, "AI wrapped under Tip at \(width)")
            #expect(ai.minY == tip.minY)
            #expect(delight.minX == ai.minX && delight.minY > ai.maxY)
            // …at the spiral's natural height.
            #expect(abs((delight.maxY - science.minY) - L.naturalHeight) < 0.5)
        }
    }

    @Test("the spiral holds down to ~600 pt and stacks only below it")
    func breakpoint() {
        #expect(!WelcomeWindow.stacks(atContentWidth: WelcomeWindow.naturalContentWidth))
        #expect(!WelcomeWindow.stacks(atContentWidth: WelcomeWindow.stackBelowContentWidth))
        #expect(WelcomeWindow.stacks(atContentWidth: WelcomeWindow.stackBelowContentWidth - 1))
        #expect(WelcomeWindow.stacks(atContentWidth: WelcomeWindow.minimumContentWidth))
        // The breakpoint sits strictly between the window's limits, or one of the
        // two arrangements would be unreachable.
        #expect(WelcomeWindow.minimumContentWidth < WelcomeWindow.stackBelowContentWidth)
        #expect(WelcomeWindow.stackBelowContentWidth < WelcomeWindow.naturalContentWidth)
    }

    @Test("at the minimum width the inner block is exactly its natural size")
    func minimumIsTheScienceCell() {
        let natural = L.frames(width: L.naturalWidth, stacked: false)
        let narrow = L.frames(width: L.minimumWidth, stacked: true)
        for i in 1...4 {
            #expect(abs(narrow[i].width - natural[i].width) < 0.5, "cell \(i) changed width")
            #expect(abs(narrow[i].height - natural[i].height) < 0.5, "cell \(i) changed height")
        }
    }
}
