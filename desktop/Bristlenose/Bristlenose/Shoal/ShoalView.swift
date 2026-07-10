import SpriteKit
import SwiftUI

/// SwiftUI wrapper for the typographic shoal SpriteKit scene.
///
/// Displays the flocking word animation with a soft gradient dissolve
/// at the bottom edge (no hard boundary between the shoal and the log area).
struct ShoalView: View {
    @Binding var phase: ShoalPhase

    /// Set to true when the pipeline fails — triggers the death animation.
    @Binding var failed: Bool

    /// DEBUG behaviour-picker overlay — shown only by the standalone debug
    /// window (`ShoalDebugView`), never in the embedded run view.
    var showsDebugControls: Bool = false

    /// DEBUG stress-test population (the `ShoalDebugView` slider). Applied only
    /// when `showsDebugControls`; the production embed leaves it 0 and stays
    /// phase-driven. Lets us eyeball density + GPU load far above the real cap.
    var debugPopulation: Int = 0

    /// Live transcript words from the run feed (production embed). Applied to the
    /// scene as they arrive; empty leaves the canned pool in place.
    var liveWords: [WordPool.Word] = []

    @State private var scene: ShoalScene = {
        let s = ShoalScene(size: CGSize(width: 480, height: 300))
        s.scaleMode = .resizeFill
        return s
    }()

    @State private var selectedBehaviorIndex = 0

    /// On-screen FPS + node/draw counters — the live cost probe for the density
    /// experiment. Debug harness only.
    private var debugOverlay: SpriteView.DebugOptions {
        #if DEBUG
        return showsDebugControls ? [.showsFPS, .showsNodeCount, .showsDrawCount] : []
        #else
        return []
        #endif
    }

    var body: some View {
        ZStack {
            // SpriteKit scene
            SpriteView(
                scene: scene,
                preferredFramesPerSecond: ShoalConfig.preferredFPS,
                options: [.allowsTransparency],
                debugOptions: debugOverlay
            )

            // Gradient dissolve at bottom edge
            VStack {
                Spacer()
                LinearGradient(
                    colors: [.clear, Color(nsColor: .windowBackgroundColor)],
                    startPoint: UnitPoint(x: 0.5, y: 0.0),
                    endPoint: UnitPoint(x: 0.5, y: 1.0)
                )
                .frame(height: 30)
            }
            .allowsHitTesting(false)

            #if DEBUG
            // Debug behaviour picker — top right corner (standalone debug window only)
            if showsDebugControls {
                VStack {
                    HStack {
                        Spacer()
                        Picker("", selection: $selectedBehaviorIndex) {
                            ForEach(allFlockingBehaviors.indices, id: \.self) { index in
                                Text(allFlockingBehaviors[index].name).tag(index)
                            }
                        }
                        .pickerStyle(.menu)
                        .fixedSize()
                        .padding(6)
                        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 6))
                        .padding(8)
                    }
                    Spacer()
                }
            }
            #endif
        }
        .onChange(of: phase) { oldPhase, newPhase in
            if newPhase == .early, oldPhase != .early {
                scene.reset()
            } else {
                scene.advanceToPhase(newPhase)
            }
        }
        .onChange(of: failed) { _, hasFailed in
            if hasFailed {
                scene.die()
            } else {
                scene.reset()
                #if DEBUG
                if showsDebugControls { scene.debugSetPopulation(debugPopulation) }
                #endif
            }
        }
        .onChange(of: liveWords.count) { _, _ in
            scene.liveWords = liveWords
        }
        #if DEBUG
        .onChange(of: selectedBehaviorIndex) { _, newIndex in
            scene.behavior = allFlockingBehaviors[newIndex]
        }
        .onChange(of: debugPopulation, initial: true) { _, count in
            if showsDebugControls { scene.debugSetPopulation(count) }
        }
        #endif
    }
}
